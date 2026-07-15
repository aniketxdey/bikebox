import Combine
import Foundation

/// Hotspot states matching the Pi's HOTSPOT_* constants in config.py.
enum HotspotState: UInt8 {
    case off          = 0x00
    case activating   = 0x01
    case active       = 0x02
    case deactivating = 0x03
}

/// Describes the current phase of the clip download workflow.
enum ClipTransferPhase: Equatable {
    case idle
    case requestingHotspot
    case waitingForHotspot
    case hotspotReady
    case connecting
    case downloading
    case done
    case failed(String)
}

final class ClipManager: ObservableObject {
    static let shared = ClipManager()

    @Published var clips: [CrashClip] = []
    @Published var isTransferring: Bool = false
    @Published var transferStatus: String = ""
    @Published var pendingClipCount: Int = 0
    @Published var hotspotState: HotspotState = .off
    @Published var transferPhase: ClipTransferPhase = .idle

    private let localClient = LocalNetworkClient(host: "192.168.4.1", port: 8080)
    private let queue = DispatchQueue(label: "com.bikebox.clipmanager")
    private var connectivityTimer: Timer?

    private init() {
        loadCachedClips()
    }

    // MARK: - Public API

    /// Called by BluetoothManager when a crash alert with clipAvailable=true arrives.
    func markClipPending() {
        DispatchQueue.main.async { [weak self] in
            self?.pendingClipCount += 1
        }
    }

    /// User taps "Download Clips" — sends BLE command to Pi to start hotspot.
    func startClipDownload() {
        guard transferPhase == .idle || transferPhase == .done else { return }

        setPhase(.requestingHotspot)
        setTransferring(true, status: "Requesting hotspot from BikeBox...")
        BluetoothManager.shared.requestHotspotActivation()
    }

    /// User or system requests to stop the hotspot and end the transfer session.
    func endClipDownload() {
        stopConnectivityPolling()
        BluetoothManager.shared.requestHotspotDeactivation()
        setTransferring(false, status: "")
        setPhase(.idle)
    }

    /// Called by BluetoothManager when the Pi notifies us of a hotspot state change.
    func handleHotspotStateUpdate(_ rawState: UInt8) {
        let newState = HotspotState(rawValue: rawState) ?? .off
        DispatchQueue.main.async { [weak self] in
            self?.hotspotState = newState
        }

        switch newState {
        case .active:
            setPhase(.hotspotReady)
            setTransferring(true, status: "Hotspot ready — join BikeBox WiFi in Settings")
            startConnectivityPolling()
        case .activating:
            setPhase(.waitingForHotspot)
            setTransferring(true, status: "Pi is starting the hotspot...")
        case .deactivating:
            setTransferring(true, status: "Pi is shutting down hotspot...")
        case .off:
            stopConnectivityPolling()
            if transferPhase != .done {
                setTransferring(false, status: "")
                setPhase(.idle)
            }
        }
    }

    /// Manual refresh — only works if already on the BikeBox WiFi.
    func refreshClips() {
        queue.async { [weak self] in
            self?.performTransfer()
        }
    }

    /// Download a specific clip (must already be on BikeBox WiFi).
    func downloadClip(_ clip: CrashClip) {
        guard !clip.isDownloaded else { return }
        queue.async { [weak self] in
            guard let self else { return }
            self.setTransferring(true, status: "Downloading \(clip.filename)...")
            self.downloadSingleClip(clip) {
                self.setTransferring(false, status: "")
            }
        }
    }

    // MARK: - Connectivity Polling

    /// Polls to detect when the user has joined the BikeBox WiFi.
    private func startConnectivityPolling() {
        stopConnectivityPolling()
        DispatchQueue.main.async { [weak self] in
            self?.connectivityTimer = Timer.scheduledTimer(withTimeInterval: 3.0, repeats: true) { [weak self] _ in
                self?.queue.async {
                    self?.checkAndTransfer()
                }
            }
        }
    }

    private func stopConnectivityPolling() {
        DispatchQueue.main.async { [weak self] in
            self?.connectivityTimer?.invalidate()
            self?.connectivityTimer = nil
        }
    }

    private func checkAndTransfer() {
        guard isPiReachable() else { return }
        stopConnectivityPolling()
        setPhase(.connecting)
        performTransfer()
    }

    private func isPiReachable() -> Bool {
        let semaphore = DispatchSemaphore(value: 0)
        var reachable = false

        localClient.request(path: "/clips", timeout: 4) { _, statusCode, _ in
            reachable = statusCode != nil
            semaphore.signal()
        }

        semaphore.wait()
        return reachable
    }

    // MARK: - Transfer Flow

    private func performTransfer() {
        setPhase(.downloading)
        setTransferring(true, status: "Checking for clips...")

        fetchClipList { [weak self] remoteClips in
            guard let self else { return }

            guard !remoteClips.isEmpty else {
                self.setTransferring(true, status: "No clips on device")
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    self.setPhase(.done)
                    self.setTransferring(false, status: "")
                    self.pendingClipCount = 0
                }
                return
            }

            let newClips = remoteClips.filter { remote in
                !self.clips.contains(where: { $0.filename == remote.filename && $0.isDownloaded })
            }

            self.mergeRemoteList(remoteClips)

            if newClips.isEmpty {
                self.setPhase(.done)
                self.setTransferring(true, status: "All clips up to date")
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    self.setTransferring(false, status: "")
                    self.pendingClipCount = 0
                }
                return
            }

            self.downloadClipsSequentially(newClips) {
                DispatchQueue.main.async {
                    self.pendingClipCount = 0
                }
                self.setPhase(.done)
                self.setTransferring(true, status: "All clips downloaded")
                DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                    self.setTransferring(false, status: "")
                }
            }
        }
    }

    // MARK: - HTTP

    private func fetchClipList(completion: @escaping ([CrashClip]) -> Void) {
        localClient.request(path: "/clips", timeout: 10) { data, statusCode, error in
            guard let data, statusCode == 200, error == nil else {
                print("ClipManager: clip list fetch failed — \(error?.localizedDescription ?? "status \(statusCode ?? 0)")")
                completion([])
                return
            }

            do {
                let items = try JSONDecoder().decode([[String: ClipListValue]].self, from: data)
                let clips = items.compactMap { item -> CrashClip? in
                    guard let filename = item["filename"]?.stringValue,
                          let ts = item["timestamp"]?.intValue,
                          let sizeKB = item["size_kb"]?.intValue else { return nil }
                    return CrashClip(
                        id: UUID(),
                        filename: filename,
                        timestamp: Date(timeIntervalSince1970: TimeInterval(ts)),
                        sizeKB: sizeKB,
                        localURL: nil
                    )
                }
                completion(clips)
            } catch {
                print("ClipManager: JSON decode failed — \(error)")
                completion([])
            }
        }
    }

    private func downloadSingleClip(_ clip: CrashClip, completion: @escaping () -> Void) {
        let docsDir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let clipsDir = docsDir.appendingPathComponent("clips", isDirectory: true)
        try? FileManager.default.createDirectory(at: clipsDir, withIntermediateDirectories: true)
        let destURL = clipsDir.appendingPathComponent(clip.filename)
        try? FileManager.default.removeItem(at: destURL)

        localClient.downloadToFile(
            path: "/clips/\(clip.filename)",
            destination: destURL,
            timeout: 120
        ) { [weak self] success, error in
            if success {
                print("ClipManager: saved \(clip.filename)")
                var updated = clip
                updated.localURL = destURL
                self?.upsertClip(updated)
            } else {
                print("ClipManager: download failed for \(clip.filename) — \(error?.localizedDescription ?? "unknown")")
            }
            completion()
        }
    }

    private func downloadClipsSequentially(_ clips: [CrashClip], completion: @escaping () -> Void) {
        var remaining = clips
        guard !remaining.isEmpty else {
            completion()
            return
        }

        let clip = remaining.removeFirst()
        setTransferring(true, status: "Downloading \(clip.filename)...")

        downloadSingleClip(clip) { [weak self] in
            self?.downloadClipsSequentially(remaining, completion: completion)
        }
    }

    // MARK: - Local State

    private func upsertClip(_ clip: CrashClip) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            if let idx = self.clips.firstIndex(where: { $0.filename == clip.filename }) {
                self.clips[idx] = clip
            } else {
                self.clips.append(clip)
                self.clips.sort { $0.timestamp > $1.timestamp }
            }
            self.saveCachedClips()
        }
    }

    private func mergeRemoteList(_ remoteClips: [CrashClip]) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            for remote in remoteClips {
                if !self.clips.contains(where: { $0.filename == remote.filename }) {
                    self.clips.append(remote)
                }
            }
            self.clips.sort { $0.timestamp > $1.timestamp }
            self.saveCachedClips()
        }
    }

    private func setTransferring(_ active: Bool, status: String) {
        DispatchQueue.main.async { [weak self] in
            self?.isTransferring = active
            self?.transferStatus = status
        }
    }

    private func setPhase(_ phase: ClipTransferPhase) {
        DispatchQueue.main.async { [weak self] in
            self?.transferPhase = phase
        }
    }

    // MARK: - Persistence

    private var cacheURL: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
            .appendingPathComponent("clip_index.json")
    }

    private func saveCachedClips() {
        do {
            let data = try JSONEncoder().encode(clips)
            try data.write(to: cacheURL)
        } catch {
            print("ClipManager: cache save failed — \(error)")
        }
    }

    private func loadCachedClips() {
        guard FileManager.default.fileExists(atPath: cacheURL.path) else { return }
        do {
            let data = try Data(contentsOf: cacheURL)
            var loaded = try JSONDecoder().decode([CrashClip].self, from: data)
            for i in loaded.indices {
                if let url = loaded[i].localURL, !FileManager.default.fileExists(atPath: url.path) {
                    loaded[i].localURL = nil
                }
            }
            clips = loaded.sorted { $0.timestamp > $1.timestamp }
        } catch {
            print("ClipManager: cache load failed — \(error)")
        }
    }
}

// MARK: - JSON Decoding Helper

private enum ClipListValue: Decodable {
    case string(String)
    case int(Int)

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let s = try? container.decode(String.self) { self = .string(s); return }
        if let i = try? container.decode(Int.self)    { self = .int(i); return }
        throw DecodingError.typeMismatch(
            ClipListValue.self,
            .init(codingPath: decoder.codingPath, debugDescription: "Expected String or Int")
        )
    }

    var stringValue: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    var intValue: Int? {
        if case .int(let i) = self { return i }
        return nil
    }
}

import Combine
import Foundation

final class ClipFeedViewModel: ObservableObject {
    @Published var clips: [CrashClip] = []
    @Published var isTransferring: Bool = false
    @Published var transferStatus: String = ""
    @Published var pendingClipCount: Int = 0
    @Published var transferPhase: ClipTransferPhase = .idle

    private var cancellables = Set<AnyCancellable>()
    private let clipManager = ClipManager.shared

    init() {
        clipManager.$clips
            .receive(on: RunLoop.main)
            .assign(to: &$clips)

        clipManager.$isTransferring
            .receive(on: RunLoop.main)
            .assign(to: &$isTransferring)

        clipManager.$transferStatus
            .receive(on: RunLoop.main)
            .assign(to: &$transferStatus)

        clipManager.$pendingClipCount
            .receive(on: RunLoop.main)
            .assign(to: &$pendingClipCount)

        clipManager.$transferPhase
            .receive(on: RunLoop.main)
            .assign(to: &$transferPhase)
    }

    var hasClips: Bool { !clips.isEmpty }
    var hasPendingClips: Bool { pendingClipCount > 0 }
    var downloadedCount: Int { clips.filter(\.isDownloaded).count }
    var totalCount: Int { clips.count }

    var canStartDownload: Bool {
        switch transferPhase {
        case .idle, .done, .failed:
            return true
        default:
            return false
        }
    }

    var showWiFiPrompt: Bool {
        transferPhase == .hotspotReady
    }

    func startDownload() {
        clipManager.startClipDownload()
    }

    func stopDownload() {
        clipManager.endClipDownload()
    }

    func refresh() {
        clipManager.refreshClips()
    }

    func download(_ clip: CrashClip) {
        clipManager.downloadClip(clip)
    }
}

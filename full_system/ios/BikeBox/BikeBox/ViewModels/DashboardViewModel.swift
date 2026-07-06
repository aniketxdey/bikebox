import Combine
import CoreLocation
import Foundation

final class DashboardViewModel: ObservableObject {
    @Published var connectionStateText = "Disconnected"
    @Published var batteryText = "--"
    @Published var batteryLevel: Int = 0
    @Published var uptimeText = "--"
    @Published var lastUpdateText = "No data"
    @Published var signalText = "--"
    @Published var signalStrength: Int = 0
    @Published var showAlert = false
    @Published var currentAlert: CrashAlert?
    @Published var lastStatusText = "—"
    @Published var lastImpactText = "None this session"
    @Published var locationText = "Searching..."
    @Published var hasGPSFix = false
    @Published var showSettings = false

    private var cancellables = Set<AnyCancellable>()
    private var heartbeatTimer: Timer?
    private let bluetooth = BluetoothManager.shared
    private let location = LocationService.shared
    private let store = SensorDataStore.shared

    init() {
        bind()
        startHeartbeatRefresh()
    }

    deinit { heartbeatTimer?.invalidate() }

    func simulateCrash() { bluetooth.simulateCrash() }
    func dismissAlert()  { bluetooth.dismissAlert() }

    private func bind() {
        bluetooth.$connectionState
            .receive(on: RunLoop.main)
            .map(\.rawValue)
            .assign(to: &$connectionStateText)

        bluetooth.$deviceStatus
            .receive(on: RunLoop.main)
            .sink { [weak self] s in
                self?.batteryText = s.map { "\($0.batteryLevel)%" } ?? "--"
                self?.batteryLevel = s?.batteryLevel ?? 0
                self?.uptimeText = s?.formattedUptime ?? "--"
                self?.lastStatusText = s?.deviceState.description ?? "—"
            }
            .store(in: &cancellables)

        bluetooth.$currentAlert
            .receive(on: RunLoop.main)
            .sink { [weak self] alert in
                self?.currentAlert = alert
                self?.showAlert = alert != nil
            }
            .store(in: &cancellables)

        bluetooth.$signalStrength
            .receive(on: RunLoop.main)
            .sink { [weak self] rssi in
                self?.signalStrength = rssi
                if rssi > -60      { self?.signalText = "Strong" }
                else if rssi > -80 { self?.signalText = "Good" }
                else if rssi < 0   { self?.signalText = "Weak" }
                else               { self?.signalText = "--" }
            }
            .store(in: &cancellables)

        location.$currentLocation
            .receive(on: RunLoop.main)
            .sink { [weak self] loc in
                guard let self else { return }
                if let loc, loc.horizontalAccuracy >= 0, loc.horizontalAccuracy < 100 {
                    self.hasGPSFix = true
                    self.locationText = String(
                        format: "%.4f, %.4f",
                        loc.coordinate.latitude,
                        loc.coordinate.longitude
                    )
                } else {
                    self.hasGPSFix = false
                    self.locationText = "Searching..."
                }
            }
            .store(in: &cancellables)

        store.$lastImpact
            .receive(on: RunLoop.main)
            .sink { [weak self] impact in
                if let impact {
                    self?.lastImpactText = String(
                        format: "%.1fg at %@",
                        impact.peakGForce,
                        impact.formattedTime
                    )
                } else {
                    self?.lastImpactText = "None this session"
                }
            }
            .store(in: &cancellables)
    }

    private func startHeartbeatRefresh() {
        heartbeatTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self, let hb = bluetooth.lastHeartbeat else {
                self?.lastUpdateText = "No data"
                return
            }
            let elapsed = Int(Date().timeIntervalSince(hb))
            self.lastUpdateText = elapsed < 2 ? "Just now" : "\(elapsed)s ago"
        }
    }
}

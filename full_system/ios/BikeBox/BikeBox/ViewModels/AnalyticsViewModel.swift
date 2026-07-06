import Combine
import Foundation

enum TimeWindow: String, CaseIterable, Identifiable {
    case tenMin    = "10 min"
    case oneHour   = "1 hr"
    case threeHour = "3 hr"

    var id: String { rawValue }

    var seconds: TimeInterval {
        switch self {
        case .tenMin:    return 600
        case .oneHour:   return 3600
        case .threeHour: return 10800
        }
    }
}

final class AnalyticsViewModel: ObservableObject {
    @Published var timeWindow: TimeWindow = .tenMin
    @Published var filteredSamples: [SensorSample] = []
    @Published var durationText = "0m 0s"
    @Published var sampleCount = 0
    @Published var peakAccelText = "0.00g"
    @Published var peakTiltText = "0\u{00B0}"
    @Published var crashCount = 0
    @Published var nearCrashCount = 0

    private var cancellables = Set<AnyCancellable>()
    private let store = SensorDataStore.shared
    private var refreshTimer: Timer?

    init() {
        bind()
        startRefresh()
    }

    deinit { refreshTimer?.invalidate() }

    private func bind() {
        $timeWindow
            .combineLatest(store.$samples)
            .receive(on: RunLoop.main)
            .map { window, allSamples -> [SensorSample] in
                let cutoff = Date().addingTimeInterval(-window.seconds)
                return allSamples.filter { $0.timestamp >= cutoff }
            }
            .assign(to: &$filteredSamples)

        store.$crashEvents
            .receive(on: RunLoop.main)
            .map(\.count)
            .assign(to: &$crashCount)
    }

    private func startRefresh() {
        refreshTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.durationText = self.store.formattedDuration
            self.sampleCount = self.store.samples.count
            self.peakAccelText = String(format: "%.2fg", self.store.peakAccel)
            self.peakTiltText = String(format: "%.0f\u{00B0}", self.store.peakTilt)
            self.nearCrashCount = self.store.nearCrashCount
        }
    }
}

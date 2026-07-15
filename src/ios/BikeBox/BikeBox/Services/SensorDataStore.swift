import Combine
import Foundation

final class SensorDataStore: ObservableObject {
    static let shared = SensorDataStore()

    static let nearCrashThreshold = 1.2

    @Published var samples: [SensorSample] = []
    @Published var crashEvents: [CrashAlert] = []
    @Published var lastImpact: CrashAlert?
    @Published var peakAccel: Double = 0.0
    @Published var peakTilt: Double = 0.0

    let sessionStart = Date()

    private var lastStoredTime: Date = .distantPast
    private let downsampleInterval: TimeInterval = 1.0
    private let maxSamples = 3600

    private init() {}

    func addSample(accel: Double, tilt: Double) {
        let now = Date()
        guard now.timeIntervalSince(lastStoredTime) >= downsampleInterval else { return }
        lastStoredTime = now

        let sample = SensorSample(timestamp: now, accelMagnitude: accel, tiltAngle: tilt)

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.samples.append(sample)
            if self.samples.count > self.maxSamples {
                self.samples.removeFirst(self.samples.count - self.maxSamples)
            }
            if accel > self.peakAccel { self.peakAccel = accel }
            if tilt > self.peakTilt { self.peakTilt = tilt }
        }
    }

    func addCrashEvent(_ alert: CrashAlert) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.crashEvents.append(alert)
            self.lastImpact = alert

            let spike = SensorSample(
                timestamp: alert.timestamp,
                accelMagnitude: alert.peakGForce,
                tiltAngle: Double(alert.tiltAngle)
            )
            self.samples.append(spike)
            if alert.peakGForce > self.peakAccel { self.peakAccel = alert.peakGForce }
            if Double(alert.tiltAngle) > self.peakTilt { self.peakTilt = Double(alert.tiltAngle) }
        }
    }

    var sessionDuration: TimeInterval {
        Date().timeIntervalSince(sessionStart)
    }

    var formattedDuration: String {
        let total = Int(sessionDuration)
        let h = total / 3600
        let m = (total % 3600) / 60
        let s = total % 60
        if h > 0 { return "\(h)h \(m)m" }
        return "\(m)m \(s)s"
    }

    var nearCrashCount: Int {
        samples.filter { $0.accelMagnitude >= Self.nearCrashThreshold }.count
    }

    func reset() {
        samples.removeAll()
        crashEvents.removeAll()
        lastImpact = nil
        peakAccel = 0.0
        peakTilt = 0.0
        lastStoredTime = .distantPast
    }
}

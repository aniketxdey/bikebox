import CoreMotion
import Combine
import Foundation

final class MotionService: ObservableObject {
    static let shared = MotionService()

    @Published var currentAccelMagnitude: Double = 0.0
    @Published var currentTilt: Double = 0.0
    @Published var isActive: Bool = false

    private let manager = CMMotionManager()
    private let queue = OperationQueue()
    private var sampleCallback: ((Double, Double) -> Void)?

    private init() {
        queue.name = "com.bikebox.motion"
        queue.maxConcurrentOperationCount = 1
    }

    func startUpdates(onSample: @escaping (Double, Double) -> Void) {
        guard manager.isDeviceMotionAvailable, !isActive else { return }

        sampleCallback = onSample
        manager.deviceMotionUpdateInterval = 0.1

        manager.startDeviceMotionUpdates(
            using: .xArbitraryCorrectedZVertical,
            to: queue
        ) { [weak self] motion, error in
            guard let self, let motion else { return }

            let ua = motion.userAcceleration
            let accel = sqrt(ua.x * ua.x + ua.y * ua.y + ua.z * ua.z)

            let g = motion.gravity
            let horizontal = sqrt(g.x * g.x + g.y * g.y)
            let tilt = atan2(horizontal, abs(g.z)) * 180.0 / .pi

            DispatchQueue.main.async {
                self.currentAccelMagnitude = accel
                self.currentTilt = tilt
                self.isActive = true
            }

            onSample(accel, tilt)
        }
    }

    func stopUpdates() {
        manager.stopDeviceMotionUpdates()
        sampleCallback = nil
        DispatchQueue.main.async { self.isActive = false }
    }
}

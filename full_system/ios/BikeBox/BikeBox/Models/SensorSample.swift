import Foundation

struct SensorSample: Identifiable {
    let id = UUID()
    let timestamp: Date
    let accelMagnitude: Double
    let tiltAngle: Double
}

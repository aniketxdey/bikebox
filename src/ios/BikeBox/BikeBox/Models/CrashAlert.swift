import Foundation

enum AlertType: UInt8 {
    case crashDetected = 0x01
    case cancelled     = 0x02
    case confirmed     = 0x03
}

struct CrashAlert: Identifiable {
    let id = UUID()
    let alertType: AlertType
    let latitude: Double
    let longitude: Double
    let peakGForce: Double
    let tiltAngle: Int
    let timestamp: Date
    let batteryLevel: Int
    var clipAvailable: Bool = false

    var hasGPSFix: Bool {
        latitude != 0.0 || longitude != 0.0
    }

    var formattedTime: String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f.string(from: timestamp)
    }

    var locationString: String {
        hasGPSFix
            ? String(format: "%.6f, %.6f", latitude, longitude)
            : "No GPS Fix"
    }

    var mapsURL: URL? {
        guard hasGPSFix else { return nil }
        return URL(string: "https://maps.apple.com/?ll=\(latitude),\(longitude)&q=Crash+Location")
    }
}

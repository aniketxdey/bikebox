import Foundation

enum DeviceState: UInt8, CustomStringConvertible {
    case booting     = 0x00
    case monitoring  = 0x01
    case gracePeriod = 0x02
    case alertSent   = 0x03
    case lowBattery  = 0x04

    var description: String {
        switch self {
        case .booting:     return "Booting"
        case .monitoring:  return "Monitoring"
        case .gracePeriod: return "Grace Period"
        case .alertSent:   return "Alert Sent"
        case .lowBattery:  return "Low Battery"
        }
    }
}

struct DeviceStatus {
    let deviceState: DeviceState
    let batteryLevel: Int
    let gpsFix: Bool
    let uptimeMinutes: Int

    var formattedUptime: String {
        let h = uptimeMinutes / 60
        let m = uptimeMinutes % 60
        return h > 0 ? "\(h)h \(m)m" : "\(m)m"
    }
}

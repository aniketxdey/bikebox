import Foundation

/// Decodes raw BLE GATT payloads into typed Swift structs.
///
/// Crash Alert (17 bytes):
///   B=alertType, ff=lat/lon, H=peakG×100, B=tilt, I=timestamp, B=battery
///
/// Device Status (5 bytes):
///   B=state, B=battery, B=gpsFix, H=uptimeMinutes
///
/// Grace Period (2 bytes):
///   B=graceState, B=secondsRemaining
enum PayloadDecoder {

    static func decodeCrashAlert(from data: Data) -> CrashAlert? {
        guard data.count >= 17 else { return nil }

        guard let rawType = data.readUInt8(at: 0),
              let alertType = AlertType(rawValue: rawType) else { return nil }

        guard let latFloat  = data.readFloat32LE(at: 1),
              let lonFloat  = data.readFloat32LE(at: 5),
              let peakGx100 = data.readUInt16LE(at: 9),
              let tilt      = data.readUInt8(at: 11),
              let ts        = data.readUInt32LE(at: 12),
              let battery   = data.readUInt8(at: 16) else { return nil }

        let clipAvailable = data.count >= 18 ? (data.readUInt8(at: 17) == 1) : false

        return CrashAlert(
            alertType: alertType,
            latitude: Double(latFloat),
            longitude: Double(lonFloat),
            peakGForce: Double(peakGx100) / 100.0,
            tiltAngle: Int(tilt),
            timestamp: Date(timeIntervalSince1970: TimeInterval(ts)),
            batteryLevel: Int(battery),
            clipAvailable: clipAvailable
        )
    }

    static func decodeDeviceStatus(from data: Data) -> DeviceStatus? {
        guard data.count >= 5 else { return nil }

        guard let rawState = data.readUInt8(at: 0),
              let state    = DeviceState(rawValue: rawState),
              let battery  = data.readUInt8(at: 1),
              let gps      = data.readUInt8(at: 2),
              let uptime   = data.readUInt16LE(at: 3) else { return nil }

        return DeviceStatus(
            deviceState: state,
            batteryLevel: Int(battery),
            gpsFix: gps == 0x01,
            uptimeMinutes: Int(uptime)
        )
    }

    static func decodeGracePeriod(from data: Data) -> GracePeriodUpdate? {
        guard data.count >= 2 else { return nil }

        guard let rawState = data.readUInt8(at: 0),
              let state = GraceState(rawValue: rawState),
              let seconds = data.readUInt8(at: 1) else { return nil }

        return GracePeriodUpdate(state: state, secondsRemaining: Int(seconds))
    }
}

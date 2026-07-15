import CoreBluetooth

enum BLEConstants {
    static let bikeBoxServiceUUID    = CBUUID(string: "CB000001-0B1C-4E5D-8A9F-1234567890AB")
    static let crashAlertUUID        = CBUUID(string: "CB000002-0B1C-4E5D-8A9F-1234567890AB")
    static let deviceStatusUUID      = CBUUID(string: "CB000003-0B1C-4E5D-8A9F-1234567890AB")
    static let gracePeriodUUID       = CBUUID(string: "CB000004-0B1C-4E5D-8A9F-1234567890AB")
    static let hotspotControlUUID    = CBUUID(string: "CB000005-0B1C-4E5D-8A9F-1234567890AB")

    static let restoreIdentifier = "com.bikebox.central"
    static let peripheralIdKey   = "BikeBoxPeripheralId"

    // WiFi hotspot for crash clip transfer
    static let piHotspotSSID       = "BikeBox"
    static let piHotspotPassphrase = "bikebox123"
    static let piClipServerBaseURL = "http://192.168.4.1:8080"
}

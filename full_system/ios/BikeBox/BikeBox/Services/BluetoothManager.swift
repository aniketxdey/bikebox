import Combine
import CoreBluetooth
import Foundation

enum ConnectionState: String {
    case disconnected = "Disconnected"
    case scanning     = "Scanning"
    case connecting   = "Connecting"
    case connected    = "Connected"
}

final class BluetoothManager: NSObject, ObservableObject {
    static let shared = BluetoothManager()

    // MARK: - Published state

    @Published var connectionState: ConnectionState = .disconnected
    @Published var deviceStatus: DeviceStatus?
    @Published var currentAlert: CrashAlert?
    @Published var graceUpdate: GracePeriodUpdate?
    @Published var discoveredPeripherals: [(peripheral: CBPeripheral, rssi: Int, name: String)] = []
    @Published var signalStrength: Int = 0
    @Published var lastHeartbeat: Date?
    @Published var isSimulationMode: Bool = false

    // MARK: - Private BLE state

    private var centralManager: CBCentralManager!
    private var connectedPeripheral: CBPeripheral?
    private var crashAlertChar: CBCharacteristic?
    private var deviceStatusChar: CBCharacteristic?
    private var gracePeriodChar: CBCharacteristic?
    private var hotspotControlChar: CBCharacteristic?
    private var simulationTimer: Timer?
    private var rssiTimer: Timer?

    // MARK: - Init

    override init() {
        super.init()
        centralManager = CBCentralManager(
            delegate: self,
            queue: nil,
            options: [
                CBCentralManagerOptionRestoreIdentifierKey: BLEConstants.restoreIdentifier
            ]
        )
    }

    // MARK: - Public API

    func startScanning() {
        guard centralManager.state == .poweredOn else { return }
        connectionState = .scanning
        discoveredPeripherals = []
        centralManager.scanForPeripherals(
            withServices: [BLEConstants.bikeBoxServiceUUID],
            options: [CBCentralManagerScanOptionAllowDuplicatesKey: false]
        )
    }

    func stopScanning() {
        centralManager.stopScan()
        if connectionState == .scanning { connectionState = .disconnected }
    }

    func connect(to peripheral: CBPeripheral) {
        stopScanning()
        connectionState = .connecting
        connectedPeripheral = peripheral
        peripheral.delegate = self
        centralManager.connect(peripheral, options: [
            CBConnectPeripheralOptionNotifyOnDisconnectionKey: true
        ])
    }

    func disconnect() {
        rssiTimer?.invalidate()
        rssiTimer = nil
        if let p = connectedPeripheral {
            centralManager.cancelPeripheralConnection(p)
        }
        resetState()
    }

    func dismissAlert() {
        currentAlert = nil
        graceUpdate = nil
    }

    func forgetDevice() {
        disconnect()
        UserDefaults.standard.removeObject(forKey: BLEConstants.peripheralIdKey)
    }

    var savedPeripheralId: String? {
        UserDefaults.standard.string(forKey: BLEConstants.peripheralIdKey)
    }

    func attemptReconnect() {
        guard let idString = savedPeripheralId,
              let uuid = UUID(uuidString: idString) else { return }
        let peripherals = centralManager.retrievePeripherals(withIdentifiers: [uuid])
        if let p = peripherals.first {
            connect(to: p)
        }
    }

    /// Write a cancel command to the Grace Period characteristic.
    func sendCancelToDevice() {
        guard let char = gracePeriodChar,
              let peripheral = connectedPeripheral else { return }
        let cancelData = Data([0x00])
        peripheral.writeValue(cancelData, for: char, type: .withResponse)
    }

    /// Tell the Pi to activate its WiFi hotspot for clip transfer.
    func requestHotspotActivation() {
        guard centralManager.state == .poweredOn,
              let char = hotspotControlChar,
              let peripheral = connectedPeripheral,
              peripheral.state == .connected else {
            print("BLE: cannot request hotspot — not connected or BLE not ready")
            return
        }
        peripheral.writeValue(Data([0x01]), for: char, type: .withResponse)
    }

    /// Tell the Pi to deactivate its WiFi hotspot.
    func requestHotspotDeactivation() {
        guard centralManager.state == .poweredOn,
              let char = hotspotControlChar,
              let peripheral = connectedPeripheral,
              peripheral.state == .connected else { return }
        peripheral.writeValue(Data([0x00]), for: char, type: .withResponse)
    }

    // MARK: - Simulation Mode

    func startSimulation() {
        isSimulationMode = true
        connectionState = .connected
        deviceStatus = DeviceStatus(
            deviceState: .monitoring,
            batteryLevel: 78,
            gpsFix: true,
            uptimeMinutes: 12
        )
        lastHeartbeat = Date()
        signalStrength = -55

        simulationTimer = Timer.scheduledTimer(withTimeInterval: 5.0, repeats: true) { [weak self] _ in
            guard let self else { return }
            self.lastHeartbeat = Date()
            let prev = self.deviceStatus
            self.deviceStatus = DeviceStatus(
                deviceState: .monitoring,
                batteryLevel: max(0, (prev?.batteryLevel ?? 78) - (Bool.random() ? 1 : 0)),
                gpsFix: true,
                uptimeMinutes: (prev?.uptimeMinutes ?? 12) + 1
            )
        }
    }

    func stopSimulation() {
        simulationTimer?.invalidate()
        simulationTimer = nil
        isSimulationMode = false
        resetState()
    }

    func simulateCrash() {
        guard isSimulationMode else { return }
        let location = LocationService.shared
        let alert = CrashAlert(
            alertType: .crashDetected,
            latitude: location.hasValidFix ? location.latitude : 43.7044,
            longitude: location.hasValidFix ? location.longitude : -72.2887,
            peakGForce: 5.23,
            tiltAngle: 78,
            timestamp: Date(),
            batteryLevel: deviceStatus?.batteryLevel ?? 78
        )
        currentAlert = alert
        SensorDataStore.shared.addCrashEvent(alert)
        graceUpdate = GracePeriodUpdate(state: .countdown, secondsRemaining: 30)
        NotificationService.shared.fireCrashNotification(alert: alert)
    }

    // MARK: - Helpers

    private func resetState() {
        connectionState = .disconnected
        connectedPeripheral = nil
        deviceStatus = nil
        currentAlert = nil
        graceUpdate = nil
        crashAlertChar = nil
        deviceStatusChar = nil
        gracePeriodChar = nil
        hotspotControlChar = nil
    }

    private func startRSSIPolling() {
        rssiTimer?.invalidate()
        rssiTimer = Timer.scheduledTimer(withTimeInterval: 10.0, repeats: true) { [weak self] _ in
            self?.connectedPeripheral?.readRSSI()
        }
    }
}

// MARK: - CBCentralManagerDelegate

extension BluetoothManager: CBCentralManagerDelegate {

    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        if central.state == .poweredOn {
            attemptReconnect()
        } else {
            connectionState = .disconnected
        }
    }

    func centralManager(
        _ central: CBCentralManager,
        willRestoreState dict: [String: Any]
    ) {
        if let peripherals = dict[CBCentralManagerRestoredStatePeripheralsKey] as? [CBPeripheral],
           let p = peripherals.first {
            connectedPeripheral = p
            p.delegate = self
            if p.state == .connected {
                connectionState = .connected
                p.discoverServices([BLEConstants.bikeBoxServiceUUID])
            }
        }
    }

    func centralManager(
        _ central: CBCentralManager,
        didDiscover peripheral: CBPeripheral,
        advertisementData: [String: Any],
        rssi RSSI: NSNumber
    ) {
        let name = peripheral.name
            ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String
            ?? "BikeBox Device"

        if !discoveredPeripherals.contains(where: { $0.peripheral.identifier == peripheral.identifier }) {
            discoveredPeripherals.append((peripheral: peripheral, rssi: RSSI.intValue, name: name))
        }
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        connectionState = .connected
        UserDefaults.standard.set(
            peripheral.identifier.uuidString,
            forKey: BLEConstants.peripheralIdKey
        )
        peripheral.discoverServices([BLEConstants.bikeBoxServiceUUID])
        startRSSIPolling()
    }

    func centralManager(
        _ central: CBCentralManager,
        didFailToConnect peripheral: CBPeripheral,
        error: Error?
    ) {
        connectionState = .disconnected
    }

    func centralManager(
        _ central: CBCentralManager,
        didDisconnectPeripheral peripheral: CBPeripheral,
        error: Error?
    ) {
        rssiTimer?.invalidate()
        rssiTimer = nil
        connectionState = .disconnected
        deviceStatus = nil

        guard !isSimulationMode else { return }

        centralManager.connect(peripheral, options: [
            CBConnectPeripheralOptionNotifyOnDisconnectionKey: true
        ])
        connectionState = .connecting
        NotificationService.shared.fireDisconnectionNotification()
    }
}

// MARK: - CBPeripheralDelegate

extension BluetoothManager: CBPeripheralDelegate {

    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        guard let services = peripheral.services else { return }
        for svc in services where svc.uuid == BLEConstants.bikeBoxServiceUUID {
            peripheral.discoverCharacteristics([
                BLEConstants.crashAlertUUID,
                BLEConstants.deviceStatusUUID,
                BLEConstants.gracePeriodUUID,
                BLEConstants.hotspotControlUUID,
            ], for: svc)
        }
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didDiscoverCharacteristicsFor service: CBService,
        error: Error?
    ) {
        guard let chars = service.characteristics else { return }
        for c in chars {
            switch c.uuid {
            case BLEConstants.crashAlertUUID:
                crashAlertChar = c
                peripheral.setNotifyValue(true, for: c)
            case BLEConstants.deviceStatusUUID:
                deviceStatusChar = c
                peripheral.setNotifyValue(true, for: c)
                peripheral.readValue(for: c)
            case BLEConstants.gracePeriodUUID:
                gracePeriodChar = c
                peripheral.setNotifyValue(true, for: c)
            case BLEConstants.hotspotControlUUID:
                hotspotControlChar = c
                peripheral.setNotifyValue(true, for: c)
            default:
                break
            }
        }
    }

    func peripheral(
        _ peripheral: CBPeripheral,
        didUpdateValueFor characteristic: CBCharacteristic,
        error: Error?
    ) {
        guard let data = characteristic.value else { return }
        DispatchQueue.main.async { [weak self] in
            switch characteristic.uuid {
            case BLEConstants.crashAlertUUID:
                if let alert = PayloadDecoder.decodeCrashAlert(from: data) {
                    self?.handleCrashAlert(alert)
                }
            case BLEConstants.deviceStatusUUID:
                if let status = PayloadDecoder.decodeDeviceStatus(from: data) {
                    self?.deviceStatus = status
                    self?.lastHeartbeat = Date()
                }
            case BLEConstants.gracePeriodUUID:
                if let update = PayloadDecoder.decodeGracePeriod(from: data) {
                    self?.graceUpdate = update
                }
            case BLEConstants.hotspotControlUUID:
                if let state = data.first {
                    ClipManager.shared.handleHotspotStateUpdate(state)
                }
            default:
                break
            }
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didReadRSSI RSSI: NSNumber, error: Error?) {
        signalStrength = RSSI.intValue
    }

    private func handleCrashAlert(_ alert: CrashAlert) {
        switch alert.alertType {
        case .crashDetected:
            graceUpdate = nil
            let location = LocationService.shared
            let enrichedAlert = CrashAlert(
                alertType: alert.alertType,
                latitude: location.hasValidFix ? location.latitude : alert.latitude,
                longitude: location.hasValidFix ? location.longitude : alert.longitude,
                peakGForce: alert.peakGForce,
                tiltAngle: alert.tiltAngle,
                timestamp: alert.timestamp,
                batteryLevel: alert.batteryLevel,
                clipAvailable: alert.clipAvailable
            )
            currentAlert = enrichedAlert
            if enrichedAlert.clipAvailable {
                ClipManager.shared.markClipPending()
            }
            SensorDataStore.shared.addCrashEvent(enrichedAlert)
            NotificationService.shared.fireCrashNotification(alert: enrichedAlert)
        case .cancelled:
            break
        case .confirmed:
            let contacts = EmergencyContactStore.shared.contacts
            if !contacts.isEmpty {
                let location = LocationService.shared
                EmergencyService.shared.dispatch(
                    contacts: contacts,
                    latitude: location.latitude,
                    longitude: location.longitude
                )
            }
        }
    }
}

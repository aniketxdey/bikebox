import Combine
import CoreBluetooth
import Foundation

final class PairingViewModel: ObservableObject {
    @Published var isScanning = false
    @Published var discoveredDevices: [(id: UUID, name: String, rssi: Int)] = []
    @Published var isConnected = false

    private var cancellables = Set<AnyCancellable>()
    private let bluetooth = BluetoothManager.shared

    init() {
        bluetooth.$connectionState
            .receive(on: RunLoop.main)
            .sink { [weak self] state in
                self?.isScanning   = state == .scanning
                self?.isConnected  = state == .connected
            }
            .store(in: &cancellables)

        bluetooth.$discoveredPeripherals
            .receive(on: RunLoop.main)
            .map { list in list.map { (id: $0.peripheral.identifier, name: $0.name, rssi: $0.rssi) } }
            .assign(to: &$discoveredDevices)
    }

    func startScanning()  { bluetooth.startScanning() }
    func stopScanning()   { bluetooth.stopScanning() }

    func connect(deviceId: UUID) {
        guard let match = bluetooth.discoveredPeripherals
                .first(where: { $0.peripheral.identifier == deviceId }) else { return }
        bluetooth.connect(to: match.peripheral)
    }

    func startSimulation() { bluetooth.startSimulation() }
}

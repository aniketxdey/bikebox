import SwiftUI

struct PairingView: View {
    @StateObject private var viewModel = PairingViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                VStack(spacing: 24) {
                    header
                    deviceList
                    actionButtons
                    footerHint
                }
            }
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
    }

    // MARK: - Header

    private var header: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: [.blue.opacity(0.3), .clear],
                            center: .center,
                            startRadius: 10,
                            endRadius: 60
                        )
                    )
                    .frame(width: 120, height: 120)

                Image(systemName: "bicycle")
                    .font(.system(size: 60))
                    .foregroundStyle(.blue)
                    .symbolEffect(.pulse, isActive: viewModel.isScanning)
            }

            Text("Connect Your BikeBox")
                .font(.title.bold())

            Text("Make sure your BikeBox is powered on.\nIt will appear below.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal)
        }
        .padding(.top, 32)
    }

    // MARK: - Device list / scanning indicator

    @ViewBuilder
    private var deviceList: some View {
        if viewModel.isScanning && viewModel.discoveredDevices.isEmpty {
            VStack(spacing: 16) {
                ProgressView()
                    .controlSize(.large)
                Text("Searching for devices...")
                    .foregroundStyle(.secondary)
            }
            .frame(maxHeight: .infinity)
        } else if !viewModel.discoveredDevices.isEmpty {
            List(viewModel.discoveredDevices, id: \.id) { device in
                HStack {
                    Image(systemName: "sensor.tag.radiowaves.forward")
                        .foregroundStyle(.blue)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(device.name).font(.headline)
                        Text(rssiLabel(device.rssi))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Button("Connect") { viewModel.connect(deviceId: device.id) }
                        .buttonStyle(.borderedProminent)
                        .controlSize(.small)
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
        } else {
            Spacer()
        }
    }

    // MARK: - Buttons

    private var actionButtons: some View {
        VStack(spacing: 12) {
            Button {
                viewModel.isScanning ? viewModel.stopScanning() : viewModel.startScanning()
            } label: {
                Label(
                    viewModel.isScanning ? "Stop Scanning" : "Scan for Devices",
                    systemImage: viewModel.isScanning ? "stop.circle" : "antenna.radiowaves.left.and.right"
                )
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .tint(.blue)
            .controlSize(.large)

            Button {
                viewModel.startSimulation()
            } label: {
                Label("Demo Mode (No Device)", systemImage: "play.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)
        }
        .padding(.horizontal)
    }

    private var footerHint: some View {
        Text("Not seeing your device? Make sure it's powered on and within 30 feet.")
            .font(.caption)
            .foregroundStyle(.secondary)
            .multilineTextAlignment(.center)
            .padding(.horizontal)
            .padding(.bottom, 12)
    }

    private func rssiLabel(_ rssi: Int) -> String {
        if rssi > -60 { return "Signal: Strong" }
        if rssi > -80 { return "Signal: Good" }
        return "Signal: Weak"
    }
}

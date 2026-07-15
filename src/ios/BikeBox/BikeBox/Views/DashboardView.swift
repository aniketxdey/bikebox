import SwiftUI

struct DashboardView: View {
    @StateObject private var viewModel = DashboardViewModel()
    @State private var showDeviceScanner = false

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                ScrollView {
                    VStack(spacing: 20) {
                        statusCirclesRow
                        monitoringHeroCard
                        quickStatsRow
                        activityFeedCard

                        if BluetoothManager.shared.isSimulationMode {
                            Button {
                                viewModel.simulateCrash()
                            } label: {
                                Label("Simulate Crash", systemImage: "exclamationmark.triangle.fill")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(.red)
                            .controlSize(.large)
                        }
                    }
                    .padding()
                }
            }
            .navigationTitle("BikeBox")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button { viewModel.showSettings = true } label: {
                        Image(systemName: "gearshape.fill")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .sheet(isPresented: $viewModel.showSettings) { SettingsView() }
            .sheet(isPresented: $showDeviceScanner) { DeviceScannerSheet() }
            .fullScreenCover(isPresented: $viewModel.showAlert) {
                if let alert = viewModel.currentAlert {
                    AlertView(alert: alert, onDismiss: viewModel.dismissAlert)
                }
            }
        }
    }

    // MARK: - Status Circles

    private var statusCirclesRow: some View {
        HStack(spacing: 16) {
            Button { showDeviceScanner = true } label: {
                StatusCircle(
                    icon: "antenna.radiowaves.left.and.right",
                    label: "Bluetooth",
                    value: isBluetoothConnected ? "Connected" : "Not Connected",
                    ringColor: isBluetoothConnected ? .blue : .red,
                    progress: isBluetoothConnected ? 1.0 : 0.0
                )
            }
            .buttonStyle(.plain)

            StatusCircle(
                icon: "location.fill",
                label: "Location",
                value: viewModel.hasGPSFix ? viewModel.locationText : "Searching",
                ringColor: viewModel.hasGPSFix ? .green : .gray,
                progress: viewModel.hasGPSFix ? 1.0 : 0.3
            )

            StatusCircle(
                icon: batteryIcon,
                label: "Battery",
                value: viewModel.batteryText,
                ringColor: batteryColor,
                progress: Double(viewModel.batteryLevel) / 100.0
            )
        }
        .padding(.top, 4)
    }

    private var isBluetoothConnected: Bool {
        BluetoothManager.shared.connectionState == .connected
    }

    private var batteryColor: Color {
        if viewModel.batteryLevel > 50 { return .green }
        if viewModel.batteryLevel > 20 { return .yellow }
        return .red
    }

    private var batteryIcon: String {
        if viewModel.batteryLevel > 75 { return "battery.100percent" }
        if viewModel.batteryLevel > 50 { return "battery.75percent" }
        if viewModel.batteryLevel > 25 { return "battery.50percent" }
        return "battery.25percent"
    }

    // MARK: - Monitoring Hero

    private var monitoringHeroCard: some View {
        let isActive = BluetoothManager.shared.connectionState == .connected
        return VStack(spacing: 10) {
            ZStack {
                Circle()
                    .fill(
                        RadialGradient(
                            colors: isActive
                                ? [.teal.opacity(0.25), .clear]
                                : [.gray.opacity(0.1), .clear],
                            center: .center,
                            startRadius: 10,
                            endRadius: 60
                        )
                    )
                    .frame(width: 120, height: 120)

                Image(systemName: isActive ? "shield.checkered" : "shield.slash")
                    .font(.system(size: 54, weight: .medium))
                    .foregroundStyle(isActive ? .teal : .gray)
                    .symbolEffect(.pulse, options: .repeating, isActive: isActive)
            }

            Text(isActive ? "Monitoring Active" : "Inactive")
                .font(.title2.weight(.black))
                .foregroundStyle(isActive ? .primary : .secondary)

            Text(isActive ? "Crash detection is running" : "Connect your BikeBox to begin")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Quick Stats Row

    private var quickStatsRow: some View {
        HStack(spacing: 12) {
            MiniStat(
                icon: "timer",
                label: "Uptime",
                value: viewModel.uptimeText,
                color: .indigo
            )
            MiniStat(
                icon: "waveform.badge.magnifyingglass",
                label: "Signal",
                value: viewModel.signalText,
                color: .cyan
            )
            MiniStat(
                icon: "bolt.fill",
                label: "Impacts",
                value: "\(SensorDataStore.shared.crashEvents.count)",
                color: .orange
            )
        }
    }

    // MARK: - Activity Feed

    private var activityFeedCard: some View {
        VStack(spacing: 0) {
            feedRow(
                icon: "heart.fill",
                iconColor: .pink,
                label: "Last Heartbeat",
                value: viewModel.lastUpdateText
            )
            Divider().padding(.leading, 44)
            feedRow(
                icon: "waveform.path.ecg",
                iconColor: .teal,
                label: "Device Status",
                value: viewModel.lastStatusText
            )
            Divider().padding(.leading, 44)
            feedRow(
                icon: "bolt.trianglebadge.exclamationmark.fill",
                iconColor: .orange,
                label: "Last Impact",
                value: viewModel.lastImpactText
            )
        }
        .padding(.vertical, 4)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private func feedRow(icon: String, iconColor: Color, label: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .font(.body.weight(.semibold))
                .foregroundStyle(iconColor)
                .frame(width: 28)
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .lineLimit(1)
            Spacer()
            Text(value)
                .font(.subheadline.weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.8)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

// MARK: - Mini Stat Component

struct MiniStat: View {
    let icon: String
    let label: String
    let value: String
    let color: Color

    var body: some View {
        VStack(spacing: 6) {
            Image(systemName: icon)
                .font(.title3.weight(.semibold))
                .foregroundStyle(color)
            Text(value)
                .font(.subheadline.weight(.bold))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(label)
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 14)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

// MARK: - Status Circle Component

struct StatusCircle: View {
    let icon: String
    let label: String
    let value: String
    let ringColor: Color
    let progress: Double

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle()
                    .stroke(ringColor.opacity(0.2), lineWidth: 4)
                    .frame(width: 72, height: 72)

                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(ringColor, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                    .frame(width: 72, height: 72)
                    .rotationEffect(.degrees(-90))

                Image(systemName: icon)
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(ringColor)
            }

            Text(label)
                .font(.caption2.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)

            Text(value)
                .font(.caption.weight(.medium))
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Device Scanner Sheet

struct DeviceScannerSheet: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var viewModel = PairingViewModel()

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                VStack(spacing: 20) {
                    if viewModel.isScanning && viewModel.discoveredDevices.isEmpty {
                        Spacer()
                        ProgressView()
                            .controlSize(.large)
                        Text("Searching for devices...")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                        Spacer()
                    } else if viewModel.discoveredDevices.isEmpty {
                        Spacer()
                        Image(systemName: "antenna.radiowaves.left.and.right")
                            .font(.system(size: 44))
                            .foregroundStyle(.blue.opacity(0.6))
                        Text("Tap Scan to find nearby BikeBox devices")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                        Spacer()
                    } else {
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
                                Button("Connect") {
                                    viewModel.connect(deviceId: device.id)
                                    dismiss()
                                }
                                .buttonStyle(.borderedProminent)
                                .controlSize(.small)
                            }
                        }
                        .listStyle(.insetGrouped)
                    }

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
                    .padding(.horizontal)
                    .padding(.bottom, 8)
                }
            }
            .navigationTitle("Find Devices")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func rssiLabel(_ rssi: Int) -> String {
        if rssi > -60 { return "Signal: Strong" }
        if rssi > -80 { return "Signal: Good" }
        return "Signal: Weak"
    }
}

// MARK: - App Background

struct AppBackground: View {
    var body: some View {
        LinearGradient(
            colors: [
                Color(red: 0.05, green: 0.08, blue: 0.18),
                Color(red: 0.08, green: 0.14, blue: 0.28),
                Color(red: 0.04, green: 0.06, blue: 0.14),
            ],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
        .ignoresSafeArea()
    }
}

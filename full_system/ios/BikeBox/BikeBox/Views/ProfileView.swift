import SwiftUI

struct ProfileView: View {
    @AppStorage("profile_displayName") private var displayName = "Aniket Dey"
    @AppStorage("profile_email") private var email = "aniket@dartmouth.edu"
    @AppStorage("profile_memberSince") private var memberSince = "Mar 2026"

    @State private var showEmergencyContacts = false
    @State private var showNotifications = false
    @State private var showDetection = false

    private let bluetooth = BluetoothManager.shared

    var body: some View {
        NavigationStack {
            ZStack {
                AppBackground()
                ScrollView {
                    VStack(spacing: 20) {
                        profileHeader
                        accountSection
                        devicesSection
                        settingsSection
                    }
                    .padding()
                    .padding(.bottom, 20)
                }
            }
            .navigationTitle("Profile")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .sheet(isPresented: $showEmergencyContacts) { emergencyContactsSheet }
            .sheet(isPresented: $showNotifications) { notificationsSheet }
            .sheet(isPresented: $showDetection) { detectionSheet }
        }
    }

    // MARK: - Profile Header

    private var profileHeader: some View {
        VStack(spacing: 14) {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [.blue, .cyan, .teal],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 96, height: 96)
                    .shadow(color: .blue.opacity(0.4), radius: 12, y: 4)

                Image(systemName: "figure.outdoor.cycle")
                    .font(.system(size: 40, weight: .semibold))
                    .foregroundStyle(.white)
            }

            Text(displayName)
                .font(.title2.weight(.black))

            Text(email)
                .font(.subheadline)
                .foregroundStyle(.secondary)

            HStack(spacing: 4) {
                Image(systemName: "calendar")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text("Member since \(memberSince)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
    }

    // MARK: - Account

    private var accountSection: some View {
        VStack(spacing: 0) {
            sectionHeader("Account")
            editableRow(icon: "person.fill", iconColor: .teal, label: "Name", value: $displayName)
            Divider().padding(.leading, 52)
            editableRow(icon: "envelope.fill", iconColor: .blue, label: "Email", value: $email)
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Devices

    private var devicesSection: some View {
        VStack(spacing: 0) {
            sectionHeader("Connected Devices")
            HStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(bluetooth.connectionState == .connected
                              ? Color.green.opacity(0.15)
                              : Color.gray.opacity(0.1))
                        .frame(width: 40, height: 40)
                    Image(systemName: "shield.checkered")
                        .font(.body.weight(.semibold))
                        .foregroundStyle(bluetooth.connectionState == .connected ? .teal : .gray)
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text("BikeBox")
                        .font(.subheadline.weight(.semibold))
                    Text(bluetooth.connectionState.rawValue)
                        .font(.caption)
                        .foregroundStyle(
                            bluetooth.connectionState == .connected ? .green : .secondary
                        )
                }

                Spacer()

                if bluetooth.connectionState == .connected {
                    SignalBars(rssi: bluetooth.signalStrength)
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)

            if bluetooth.connectionState == .connected || bluetooth.isSimulationMode {
                Divider().padding(.leading, 52)
                Button(role: .destructive) {
                    if bluetooth.isSimulationMode {
                        bluetooth.stopSimulation()
                    } else {
                        bluetooth.forgetDevice()
                    }
                } label: {
                    HStack {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.red)
                            .frame(width: 32)
                        Text(bluetooth.isSimulationMode ? "Exit Demo Mode" : "Forget Device")
                            .font(.subheadline)
                            .foregroundStyle(.red)
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                }
            }
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Settings Navigation

    private var settingsSection: some View {
        VStack(spacing: 0) {
            sectionHeader("Settings")
            navRow(icon: "person.2.fill", iconColor: .pink, label: "Emergency Contacts") {
                showEmergencyContacts = true
            }
            Divider().padding(.leading, 52)
            navRow(icon: "bell.fill", iconColor: .orange, label: "Notifications") {
                showNotifications = true
            }
            Divider().padding(.leading, 52)
            navRow(icon: "waveform.path.ecg", iconColor: .teal, label: "Detection Settings") {
                showDetection = true
            }
        }
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    // MARK: - Sheet Contents

    private var emergencyContactsSheet: some View {
        NavigationStack {
            EmergencyContactsListView()
                .navigationTitle("Emergency Contacts")
                .toolbarBackground(.visible, for: .navigationBar)
                .toolbarColorScheme(.dark, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { showEmergencyContacts = false }
                    }
                }
        }
    }

    private var notificationsSheet: some View {
        NavigationStack {
            NotificationsSettingsView()
                .navigationTitle("Notifications")
                .toolbarBackground(.visible, for: .navigationBar)
                .toolbarColorScheme(.dark, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { showNotifications = false }
                    }
                }
        }
    }

    private var detectionSheet: some View {
        NavigationStack {
            DetectionSettingsView()
                .navigationTitle("Detection")
                .toolbarBackground(.visible, for: .navigationBar)
                .toolbarColorScheme(.dark, for: .navigationBar)
                .toolbar {
                    ToolbarItem(placement: .confirmationAction) {
                        Button("Done") { showDetection = false }
                    }
                }
        }
    }

    // MARK: - Row Builders

    private func sectionHeader(_ title: String) -> some View {
        HStack {
            Text(title)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.top, 14)
        .padding(.bottom, 4)
    }

    private func editableRow(icon: String, iconColor: Color, label: String, value: Binding<String>) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.body.weight(.semibold))
                .foregroundStyle(iconColor)
                .frame(width: 28)
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            TextField(label, text: value)
                .font(.subheadline.weight(.semibold))
                .multilineTextAlignment(.trailing)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private func navRow(icon: String, iconColor: Color, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(iconColor)
                    .frame(width: 28)
                Text(label)
                    .font(.subheadline)
                    .foregroundStyle(.primary)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
    }
}

// MARK: - Signal Bars

struct SignalBars: View {
    let rssi: Int

    private var activeBars: Int {
        if rssi > -60 { return 3 }
        if rssi > -80 { return 2 }
        if rssi < 0   { return 1 }
        return 0
    }

    var body: some View {
        HStack(alignment: .bottom, spacing: 2) {
            ForEach(0..<3, id: \.self) { i in
                RoundedRectangle(cornerRadius: 1)
                    .fill(i < activeBars ? Color.green : Color.gray.opacity(0.3))
                    .frame(width: 4, height: CGFloat(6 + i * 4))
            }
        }
    }
}

// MARK: - Settings Sub-Views

struct EmergencyContactsListView: View {
    @StateObject private var contactStore = EmergencyContactStore.shared
    @State private var showAddContact = false

    var body: some View {
        Form {
            if contactStore.contacts.isEmpty {
                Text("No emergency contacts configured.")
                    .foregroundStyle(.secondary)
                    .font(.subheadline)
            } else {
                ForEach(contactStore.contacts) { contact in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(contact.name).font(.headline)
                        Text(contact.phone).font(.subheadline).foregroundStyle(.secondary)
                        HStack(spacing: 12) {
                            if contact.shouldCall {
                                Label("Call", systemImage: "phone.fill")
                                    .font(.caption).foregroundStyle(.blue)
                            }
                            if contact.shouldText {
                                Label("Text", systemImage: "message.fill")
                                    .font(.caption).foregroundStyle(.green)
                            }
                        }
                    }
                }
                .onDelete(perform: contactStore.remove)
            }

            Button { showAddContact = true } label: {
                Label("Add Emergency Contact", systemImage: "plus.circle.fill")
            }
        }
        .sheet(isPresented: $showAddContact) { AddContactSheet() }
    }
}

struct NotificationsSettingsView: View {
    @State private var crashNotifications = true
    @State private var batteryWarnings = true
    @State private var disconnectWarnings = true

    var body: some View {
        Form {
            Toggle(isOn: $crashNotifications) {
                Label("Crash Alerts", systemImage: "exclamationmark.triangle")
            }
            Toggle(isOn: $batteryWarnings) {
                Label("Low Battery", systemImage: "battery.25percent")
            }
            Toggle(isOn: $disconnectWarnings) {
                Label("Disconnection", systemImage: "wifi.slash")
            }
        }
    }
}

struct DetectionSettingsView: View {
    var body: some View {
        Form {
            HStack {
                Label("Impact Threshold", systemImage: "waveform.path.ecg")
                Spacer()
                Text("1.5g").foregroundStyle(.secondary)
            }
            HStack {
                Label("Gyro Threshold", systemImage: "arrow.triangle.2.circlepath")
                Spacer()
                Text("100\u{00B0}/s").foregroundStyle(.secondary)
            }
            HStack {
                Label("Tilt Threshold", systemImage: "angle")
                Spacer()
                Text("30\u{00B0}").foregroundStyle(.secondary)
            }
            Text("Crash detection sensitivity is configured on the device.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

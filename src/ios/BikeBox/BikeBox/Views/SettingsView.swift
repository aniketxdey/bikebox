import SwiftUI

struct SettingsView: View {
    @Environment(\.dismiss) private var dismiss
    @StateObject private var contactStore = EmergencyContactStore.shared
    @State private var crashNotifications = true
    @State private var batteryWarnings = true
    @State private var disconnectWarnings = true
    @State private var showAddContact = false

    var body: some View {
        NavigationStack {
            List {
                deviceSection
                emergencyContactsSection
                notificationSection
                detectionSection
                aboutSection
            }
            .navigationTitle("Settings")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: $showAddContact) {
                AddContactSheet()
            }
        }
    }

    // MARK: - Device

    private var deviceSection: some View {
        Section("Device") {
            HStack {
                Label("Status",
                      systemImage: BluetoothManager.shared.connectionState == .connected
                        ? "checkmark.circle.fill" : "xmark.circle")
                Spacer()
                Text(BluetoothManager.shared.connectionState.rawValue)
                    .foregroundStyle(
                        BluetoothManager.shared.connectionState == .connected ? .green : .red
                    )
            }

            if BluetoothManager.shared.isSimulationMode {
                HStack {
                    Label("Mode", systemImage: "play.circle")
                    Spacer()
                    Text("Demo").foregroundStyle(.orange)
                }
            }

            Button(role: .destructive) {
                if BluetoothManager.shared.isSimulationMode {
                    BluetoothManager.shared.stopSimulation()
                } else {
                    BluetoothManager.shared.forgetDevice()
                }
            } label: {
                Label(
                    BluetoothManager.shared.isSimulationMode ? "Exit Demo" : "Forget Device",
                    systemImage: "trash"
                )
            }
        }
    }

    // MARK: - Emergency Contacts

    private var emergencyContactsSection: some View {
        Section {
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
                                    .font(.caption)
                                    .foregroundStyle(.blue)
                            }
                            if contact.shouldText {
                                Label("Text", systemImage: "message.fill")
                                    .font(.caption)
                                    .foregroundStyle(.green)
                            }
                            if !contact.relationship.isEmpty {
                                Text(contact.relationship)
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
                .onDelete(perform: contactStore.remove)
            }

            Button {
                showAddContact = true
            } label: {
                Label("Add Emergency Contact", systemImage: "plus.circle.fill")
            }
        } header: {
            Text("Emergency Contacts")
        } footer: {
            Text("These contacts will be notified automatically if a crash alert is confirmed.")
        }
    }

    // MARK: - Notifications

    private var notificationSection: some View {
        Section("Notifications") {
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

    // MARK: - Detection

    private var detectionSection: some View {
        Section("Detection") {
            HStack {
                Label("Impact Threshold", systemImage: "waveform.path.ecg")
                Spacer()
                Text("3.0g").foregroundStyle(.secondary)
            }
            HStack {
                Label("Gyro Threshold", systemImage: "arrow.triangle.2.circlepath")
                Spacer()
                Text("200\u{00B0}/s").foregroundStyle(.secondary)
            }
            HStack {
                Label("Tilt Threshold", systemImage: "angle")
                Spacer()
                Text("45\u{00B0}").foregroundStyle(.secondary)
            }
            Text("Crash detection sensitivity is configured on the device.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    // MARK: - About

    private var aboutSection: some View {
        Section("About") {
            HStack {
                Text("Version")
                Spacer()
                Text("1.0.0").foregroundStyle(.secondary)
            }
            HStack {
                Text("Team")
                Spacer()
                Text("Team 1 — ENGS 21").foregroundStyle(.secondary)
            }
            Text("BikeBox — Dartmouth College")
                .font(.caption).foregroundStyle(.secondary)
            Text("All data is stored locally on this device. No information is transmitted to external servers.")
                .font(.caption).foregroundStyle(.secondary)
        }
    }
}


struct AddContactSheet: View {
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var phone = ""
    @State private var relationship = ""
    @State private var shouldCall = true
    @State private var shouldText = true

    var body: some View {
        NavigationStack {
            Form {
                Section("Contact Info") {
                    TextField("Name", text: $name)
                    TextField("Phone Number", text: $phone)
                        .keyboardType(.phonePad)
                    TextField("Relationship (optional)", text: $relationship)
                }
                Section("Alert Method") {
                    Toggle("Call", isOn: $shouldCall)
                    Toggle("Text Message", isOn: $shouldText)
                }
            }
            .navigationTitle("Add Contact")
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        let contact = EmergencyContact(
                            name: name,
                            phone: phone,
                            relationship: relationship,
                            shouldCall: shouldCall,
                            shouldText: shouldText
                        )
                        EmergencyContactStore.shared.add(contact)
                        dismiss()
                    }
                    .disabled(name.isEmpty || phone.isEmpty)
                }
            }
        }
    }
}

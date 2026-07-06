import Combine
import Foundation

final class AlertViewModel: ObservableObject {
    @Published var secondsRemaining: Int = 30
    @Published var isCancelled: Bool = false
    @Published var isConfirmed: Bool = false
    @Published var graceActive: Bool = true

    let alert: CrashAlert

    private var cancellables = Set<AnyCancellable>()
    private let bluetooth = BluetoothManager.shared
    private var countdownTimer: Timer?

    init(alert: CrashAlert) {
        self.alert = alert
        bind()
        startLocalCountdown()
    }

    deinit {
        countdownTimer?.invalidate()
    }

    var emergencyContactName: String? {
        EmergencyContactStore.shared.contacts.first(where: \.shouldCall)?.name
            ?? EmergencyContactStore.shared.contacts.first?.name
    }

    // MARK: - Actions

    func cancelAlert() {
        bluetooth.sendCancelToDevice()
        isCancelled = true
        graceActive = false
        countdownTimer?.invalidate()
        bluetooth.dismissAlert()
    }

    func callEmergencyContact() {
        let contacts = EmergencyContactStore.shared.contacts
        let location = LocationService.shared

        if let callContact = contacts.first(where: \.shouldCall) ?? contacts.first {
            EmergencyService.shared.initiateCall(to: callContact)
        }

        let textContacts = contacts.filter(\.shouldText)
        for contact in textContacts {
            EmergencyService.shared.sendSMS(
                to: contact,
                latitude: location.latitude,
                longitude: location.longitude
            )
        }
    }

    func call911() {
        EmergencyService.shared.call911()
    }

    func sendHelpNow() {
        isConfirmed = true
        graceActive = false
        countdownTimer?.invalidate()
        callEmergencyContact()
    }

    func dismiss() {
        bluetooth.dismissAlert()
    }

    // MARK: - Private

    private func bind() {
        bluetooth.$graceUpdate
            .compactMap { $0 }
            .receive(on: RunLoop.main)
            .sink { [weak self] update in
                guard let self else { return }
                self.secondsRemaining = update.secondsRemaining

                switch update.state {
                case .cancelledByButton, .cancelledByApp:
                    self.isCancelled = true
                    self.graceActive = false
                    self.countdownTimer?.invalidate()
                case .idle:
                    if self.graceActive {
                        self.isConfirmed = true
                        self.graceActive = false
                        self.countdownTimer?.invalidate()
                    }
                case .countdown:
                    break
                }
            }
            .store(in: &cancellables)
    }

    private func startLocalCountdown() {
        secondsRemaining = 30
        countdownTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { [weak self] _ in
            guard let self, self.graceActive else {
                self?.countdownTimer?.invalidate()
                return
            }
            if self.secondsRemaining > 0 {
                self.secondsRemaining -= 1
            }
            if self.secondsRemaining <= 0 {
                self.isConfirmed = true
                self.graceActive = false
                self.countdownTimer?.invalidate()
            }
        }
    }
}

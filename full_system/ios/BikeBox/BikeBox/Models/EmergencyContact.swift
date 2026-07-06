import Foundation

struct EmergencyContact: Identifiable, Codable, Equatable {
    let id: UUID
    var name: String
    var phone: String
    var relationship: String
    var shouldCall: Bool
    var shouldText: Bool

    init(
        id: UUID = UUID(),
        name: String,
        phone: String,
        relationship: String = "",
        shouldCall: Bool = true,
        shouldText: Bool = true
    ) {
        self.id = id
        self.name = name
        self.phone = phone
        self.relationship = relationship
        self.shouldCall = shouldCall
        self.shouldText = shouldText
    }

    var formattedPhone: String {
        phone.replacingOccurrences(of: "[^0-9+]", with: "", options: .regularExpression)
    }

    func smsBody(latitude: Double, longitude: Double) -> String {
        let locationURL = "https://maps.apple.com/?ll=\(latitude),\(longitude)&q=Crash+Location"
        return "I may have been in a bicycle accident. "
             + "My last known location: \(locationURL). "
             + "This is an automated message from BikeBox."
    }
}


final class EmergencyContactStore: ObservableObject {
    static let shared = EmergencyContactStore()

    @Published var contacts: [EmergencyContact] = [] {
        didSet { save() }
    }

    private let storageKey = "BikeBoxEmergencyContacts"

    init() {
        load()
    }

    func add(_ contact: EmergencyContact) {
        contacts.append(contact)
    }

    func remove(at offsets: IndexSet) {
        contacts.remove(atOffsets: offsets)
    }

    func update(_ contact: EmergencyContact) {
        if let idx = contacts.firstIndex(where: { $0.id == contact.id }) {
            contacts[idx] = contact
        }
    }

    private func save() {
        if let data = try? JSONEncoder().encode(contacts) {
            UserDefaults.standard.set(data, forKey: storageKey)
        }
    }

    private func load() {
        guard let data = UserDefaults.standard.data(forKey: storageKey),
              let decoded = try? JSONDecoder().decode([EmergencyContact].self, from: data)
        else { return }
        contacts = decoded
    }
}

import Foundation
import UIKit

final class EmergencyService {
    static let shared = EmergencyService()

    func dispatch(contacts: [EmergencyContact], latitude: Double, longitude: Double) {
        let callContacts = contacts.filter(\.shouldCall)
        let textContacts = contacts.filter(\.shouldText)

        if let primary = callContacts.first {
            initiateCall(to: primary)
        }

        for contact in textContacts {
            sendSMS(to: contact, latitude: latitude, longitude: longitude)
        }
    }

    func initiateCall(to contact: EmergencyContact) {
        let phone = contact.formattedPhone
        guard !phone.isEmpty,
              let url = URL(string: "tel://\(phone)") else { return }
        DispatchQueue.main.async {
            UIApplication.shared.open(url)
        }
    }

    func sendSMS(to contact: EmergencyContact, latitude: Double, longitude: Double) {
        let phone = contact.formattedPhone
        let body = contact.smsBody(latitude: latitude, longitude: longitude)
            .addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        guard !phone.isEmpty,
              let url = URL(string: "sms:\(phone)&body=\(body)") else { return }
        DispatchQueue.main.async {
            UIApplication.shared.open(url)
        }
    }

    func call911() {
        guard let url = URL(string: "tel://911") else { return }
        DispatchQueue.main.async {
            UIApplication.shared.open(url)
        }
    }
}

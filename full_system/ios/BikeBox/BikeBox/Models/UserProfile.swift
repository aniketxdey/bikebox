import Foundation
import SwiftUI

struct UserProfile {
    var displayName: String
    var email: String
    var memberSince: Date

    static let demo = UserProfile(
        displayName: "Aniket Dey",
        email: "aniket@dartmouth.edu",
        memberSince: {
            var comps = DateComponents()
            comps.year = 2026
            comps.month = 3
            return Calendar.current.date(from: comps) ?? Date()
        }()
    )

    var formattedMemberSince: String {
        let f = DateFormatter()
        f.dateFormat = "MMM yyyy"
        return f.string(from: memberSince)
    }
}

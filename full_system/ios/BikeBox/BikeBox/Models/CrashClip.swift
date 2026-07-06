import Foundation

struct CrashClip: Identifiable, Codable {
    let id: UUID
    let filename: String
    let timestamp: Date
    let sizeKB: Int
    var localURL: URL?

    var isDownloaded: Bool { localURL != nil }

    var formattedTime: String {
        let f = DateFormatter()
        f.dateFormat = "MMM d, h:mm a"
        return f.string(from: timestamp)
    }

    var formattedSize: String {
        if sizeKB >= 1024 {
            return String(format: "%.1f MB", Double(sizeKB) / 1024.0)
        }
        return "\(sizeKB) KB"
    }
}

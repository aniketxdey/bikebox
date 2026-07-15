import UserNotifications

final class NotificationService {
    static let shared = NotificationService()

    func requestPermissions() {
        UNUserNotificationCenter.current().requestAuthorization(
            options: [.alert, .sound, .badge]
        ) { _, error in
            if let error { print("Notification permission error: \(error)") }
        }
    }

    func setupNotificationCategories() {
        let okAction   = UNNotificationAction(identifier: "IM_OK",    title: "I'm OK",   options: .destructive)
        let helpAction = UNNotificationAction(identifier: "GET_HELP", title: "Get Help",  options: .foreground)

        let crashCategory = UNNotificationCategory(
            identifier: "CRASH_ALERT",
            actions: [okAction, helpAction],
            intentIdentifiers: [],
            options: .customDismissAction
        )

        UNUserNotificationCenter.current().setNotificationCategories([crashCategory])
    }

    func fireCrashNotification(alert: CrashAlert) {
        let content = UNMutableNotificationContent()
        content.title = "BikeBox Alert"
        content.body  = "Possible crash detected at \(alert.locationString). "
                      + "Peak: \(String(format: "%.1f", alert.peakGForce))g. Tap to respond."
        content.sound = .defaultCritical
        content.categoryIdentifier = "CRASH_ALERT"

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 0.5, repeats: false)
        let request = UNNotificationRequest(
            identifier: "crash-\(UUID().uuidString)",
            content: content,
            trigger: trigger
        )
        UNUserNotificationCenter.current().add(request)
    }

    func fireDisconnectionNotification() {
        let content = UNMutableNotificationContent()
        content.title = "BikeBox Disconnected"
        content.body  = "Your crash detection device has disconnected. Attempting to reconnect..."
        content.sound = .default

        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 0.5, repeats: false)
        let request = UNNotificationRequest(
            identifier: "disconnect-\(UUID().uuidString)",
            content: content,
            trigger: trigger
        )
        UNUserNotificationCenter.current().add(request)
    }
}

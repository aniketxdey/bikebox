import SwiftUI

@main
struct BikeBoxApp: App {
    @StateObject private var bluetooth = BluetoothManager.shared
    @StateObject private var location = LocationService.shared
    @StateObject private var sensorStore = SensorDataStore.shared
    @StateObject private var motionService = MotionService.shared

    init() {
        NotificationService.shared.requestPermissions()
        NotificationService.shared.setupNotificationCategories()

        let darkBG = UIColor(red: 0.05, green: 0.08, blue: 0.18, alpha: 1.0)
        let nav = UINavigationBarAppearance()
        nav.configureWithOpaqueBackground()
        nav.backgroundColor = darkBG
        nav.titleTextAttributes = [.foregroundColor: UIColor.white]
        nav.largeTitleTextAttributes = [.foregroundColor: UIColor.white]
        UINavigationBar.appearance().standardAppearance = nav
        UINavigationBar.appearance().scrollEdgeAppearance = nav
        UINavigationBar.appearance().compactAppearance = nav
        UINavigationBar.appearance().tintColor = .white
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .preferredColorScheme(.dark)
                .environmentObject(bluetooth)
                .environmentObject(location)
                .environmentObject(sensorStore)
                .environmentObject(motionService)
                .onAppear {
                    location.requestPermission()
                }
                .onChange(of: bluetooth.connectionState) { _, newState in
                    if newState == .connected {
                        startMotionTracking()
                    } else if newState == .disconnected {
                        motionService.stopUpdates()
                    }
                }
        }
    }

    private func startMotionTracking() {
        motionService.startUpdates { accel, tilt in
            sensorStore.addSample(accel: accel, tilt: tilt)
        }
    }
}

struct RootView: View {
    @EnvironmentObject var bluetooth: BluetoothManager
    @AppStorage(BLEConstants.peripheralIdKey) private var savedId: String?

    var body: some View {
        if bluetooth.connectionState == .connected
            || bluetooth.connectionState == .connecting
            || savedId != nil
        {
            MainTabView()
        } else {
            PairingView()
        }
    }
}

struct MainTabView: View {
    var body: some View {
        TabView {
            DashboardView()
                .tabItem {
                    Label("Monitor", systemImage: "shield.checkered")
                }
            AnalyticsView()
                .tabItem {
                    Label("Analytics", systemImage: "chart.xyaxis.line")
                }
            ClipFeedView()
                .tabItem {
                    Label("Clips", systemImage: "film.stack")
                }
            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person.crop.circle")
                }
        }
        .tint(.teal)
        .toolbarBackground(
            Color(red: 0.04, green: 0.06, blue: 0.14).opacity(0.95),
            for: .tabBar
        )
        .toolbarBackground(.visible, for: .tabBar)
        .toolbarColorScheme(.dark, for: .tabBar)
    }
}

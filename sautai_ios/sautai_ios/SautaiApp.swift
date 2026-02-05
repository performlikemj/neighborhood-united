//
//  SautaiApp.swift
//  sautai_ios
//
//  Main entry point for the sautai iOS application.
//  Chef-first design with full streaming AI support.
//

import SwiftUI
import SwiftData

@main
struct SautaiApp: App {
    @StateObject private var authManager = AuthManager.shared

    var sharedModelContainer: ModelContainer = {
        let schema = Schema([
            // Add SwiftData models here
        ])
        let modelConfiguration = ModelConfiguration(
            schema: schema,
            isStoredInMemoryOnly: false
        )

        do {
            return try ModelContainer(for: schema, configurations: [modelConfiguration])
        } catch {
            fatalError("Could not create ModelContainer: \(error)")
        }
    }()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(authManager)
                .preferredColorScheme(nil) // Respect system setting
        }
        .modelContainer(sharedModelContainer)
    }
}

// MARK: - Root Content View

struct ContentView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        Group {
            if authManager.isAuthenticated {
                if authManager.currentRole == .chef {
                    ChefTabView()
                } else {
                    CustomerTabView()
                }
            } else {
                LoginView()
            }
        }
        .animation(.easeInOut(duration: SautaiDesign.animationDuration), value: authManager.isAuthenticated)
    }
}

// MARK: - Tab Notification

extension Notification.Name {
    static let switchToTab = Notification.Name("switchToTab")
}

// MARK: - Chef Tab View

struct ChefTabView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ChefDashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.bar.fill")
                }
                .tag(0)

            OrdersListView()
                .tabItem {
                    Label("Orders", systemImage: "bag.fill")
                }
                .tag(1)

            KitchenView()
                .tabItem {
                    Label("Kitchen", systemImage: "fork.knife")
                }
                .tag(2)

            ClientsListView()
                .tabItem {
                    Label("Clients", systemImage: "person.2.fill")
                }
                .tag(3)

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(4)
        }
        .tint(Color.sautai.earthenClay)
        .onReceive(NotificationCenter.default.publisher(for: .switchToTab)) { notification in
            if let tab = notification.object as? Int {
                withAnimation {
                    selectedTab = tab
                }
            }
        }
    }
}

// MARK: - Customer Tab View

struct CustomerTabView: View {
    var body: some View {
        TabView {
            CustomerDashboardView()
                .tabItem {
                    Label("Home", systemImage: "house.fill")
                }

            ChefDiscoveryView()
                .tabItem {
                    Label("Find Chefs", systemImage: "magnifyingglass")
                }

            ConversationsListView()
                .tabItem {
                    Label("Messages", systemImage: "bubble.left.fill")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
        }
        .tint(Color.sautai.earthenClay)
    }
}

// MARK: - Preview

#Preview {
    ContentView()
        .environmentObject(AuthManager.shared)
}

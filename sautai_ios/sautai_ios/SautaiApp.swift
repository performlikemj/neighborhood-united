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

// MARK: - Chef Tab View

struct ChefTabView: View {
    var body: some View {
        TabView {
            ChefDashboardView()
                .tabItem {
                    Label("Dashboard", systemImage: "chart.bar.fill")
                }

            ClientsListView()
                .tabItem {
                    Label("Clients", systemImage: "person.2.fill")
                }

            LeadsListView()
                .tabItem {
                    Label("Leads", systemImage: "person.badge.plus")
                }

            SousChefView()
                .tabItem {
                    Label("Sous Chef", systemImage: "bubble.left.and.bubble.right.fill")
                }

            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
        }
        .tint(Color.sautai.earthenClay)
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

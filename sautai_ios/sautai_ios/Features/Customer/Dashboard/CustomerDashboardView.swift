//
//  CustomerDashboardView.swift
//  sautai_ios
//
//  Main dashboard for customer users.
//

import SwiftUI

struct CustomerDashboardView: View {
    @State private var myChefs: [ConnectedChef] = []
    @State private var upcomingOrders: [Order] = []
    @State private var isLoading = true

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    // Greeting
                    greetingSection

                    // Quick Actions
                    quickActionsSection

                    // My Chefs
                    myChefsSection

                    // Upcoming Orders
                    upcomingOrdersSection
                }
                .padding(SautaiDesign.spacing)
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Home")
            .refreshable {
                await loadDashboardData()
            }
        }
        .task {
            await loadDashboardData()
        }
    }

    // MARK: - Greeting Section

    private var greetingSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
            Text(greetingText)
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Text("What's cooking today?")
                .font(SautaiFont.title2)
                .foregroundColor(.sautai.slateTile)

            Text("\"Make time for love. We'll handle dinner.\"")
                .font(SautaiFont.handwritten)
                .foregroundColor(.sautai.earthenClay)
                .padding(.top, SautaiDesign.spacingXS)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        switch hour {
        case 0..<12: return "Good morning"
        case 12..<17: return "Good afternoon"
        default: return "Good evening"
        }
    }

    // MARK: - Quick Actions

    private var quickActionsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Quick Actions")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            HStack(spacing: SautaiDesign.spacingM) {
                NavigationLink {
                    ChefDiscoveryView()
                } label: {
                    quickActionCard(
                        icon: "magnifyingglass",
                        title: "Find Chef",
                        color: .sautai.earthenClay
                    )
                }

                NavigationLink {
                    ConversationsListView()
                } label: {
                    quickActionCard(
                        icon: "bubble.left.fill",
                        title: "Messages",
                        color: .sautai.herbGreen
                    )
                }

                NavigationLink {
                    Text("My Orders") // Placeholder
                } label: {
                    quickActionCard(
                        icon: "bag.fill",
                        title: "Orders",
                        color: .sautai.sunlitApricot
                    )
                }
            }
        }
    }

    private func quickActionCard(icon: String, title: String, color: Color) -> some View {
        VStack(spacing: SautaiDesign.spacingS) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(color)

            Text(title)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - My Chefs Section

    private var myChefsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("My Chefs")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if !myChefs.isEmpty {
                    NavigationLink {
                        MyChefsListView()
                    } label: {
                        Text("See All")
                            .font(SautaiFont.buttonSmall)
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }

            if myChefs.isEmpty {
                // Empty state
                VStack(spacing: SautaiDesign.spacingM) {
                    Image(systemName: "person.2.slash")
                        .font(.system(size: 32))
                        .foregroundColor(.sautai.slateTile.opacity(0.3))

                    Text("No chefs yet")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))

                    NavigationLink {
                        ChefDiscoveryView()
                    } label: {
                        Text("Find a Chef")
                            .font(SautaiFont.buttonSmall)
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(SautaiDesign.spacingL)
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadius)
            } else {
                // Chef list
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: SautaiDesign.spacingM) {
                        ForEach(myChefs) { chef in
                            NavigationLink {
                                ChefProfileView(chefId: chef.id)
                            } label: {
                                connectedChefCard(chef)
                            }
                        }
                    }
                }
            }
        }
    }

    private func connectedChefCard(_ chef: ConnectedChef) -> some View {
        VStack(spacing: SautaiDesign.spacingS) {
            // Avatar
            Circle()
                .fill(Color.sautai.herbGreen.opacity(0.2))
                .frame(width: 60, height: 60)
                .overlay(
                    Text(String(chef.displayName.prefix(1)).uppercased())
                        .font(SautaiFont.title3)
                        .foregroundColor(.sautai.herbGreen)
                )

            Text(chef.displayName)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)
                .lineLimit(1)

            // Message button
            Button {
                // TODO: Navigate to chat
            } label: {
                Image(systemName: "bubble.left.fill")
                    .font(.system(size: 14))
                    .foregroundColor(.sautai.earthenClay)
                    .padding(SautaiDesign.spacingS)
                    .background(Color.sautai.earthenClay.opacity(0.1))
                    .clipShape(Circle())
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Upcoming Orders Section

    private var upcomingOrdersSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Upcoming Orders")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            if upcomingOrders.isEmpty {
                VStack(spacing: SautaiDesign.spacingM) {
                    Image(systemName: "bag")
                        .font(.system(size: 32))
                        .foregroundColor(.sautai.slateTile.opacity(0.3))

                    Text("No upcoming orders")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
                .frame(maxWidth: .infinity)
                .padding(SautaiDesign.spacingL)
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadius)
            } else {
                ForEach(upcomingOrders.prefix(3)) { order in
                    orderCard(order)
                }
            }
        }
    }

    private func orderCard(_ order: Order) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Icon
            Image(systemName: order.status.icon)
                .font(.system(size: 20))
                .foregroundColor(.sautai.earthenClay)
                .frame(width: 40, height: 40)
                .background(Color.sautai.earthenClay.opacity(0.1))
                .clipShape(Circle())

            // Info
            VStack(alignment: .leading, spacing: 2) {
                Text(order.chefName ?? "Order")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                if let date = order.deliveryDate {
                    Text(formatDeliveryDate(date))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            Spacer()

            // Status
            Text(order.status.displayName)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.herbGreen)
                .padding(.horizontal, SautaiDesign.spacingS)
                .padding(.vertical, SautaiDesign.spacingXS)
                .background(Color.sautai.herbGreen.opacity(0.1))
                .cornerRadius(SautaiDesign.cornerRadiusS)
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func formatDeliveryDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMM d"
        return formatter.string(from: date)
    }

    // MARK: - Data Loading

    private func loadDashboardData() async {
        isLoading = true
        do {
            async let chefsTask = APIClient.shared.getMyChefs()
            // async let ordersTask = APIClient.shared.getUpcomingOrders()

            myChefs = try await chefsTask
            // upcomingOrders = try await ordersTask
        } catch {
            // Handle error
        }
        isLoading = false
    }
}

// MARK: - Connected Chef Model

struct ConnectedChef: Codable, Identifiable {
    let id: Int
    let displayName: String
    let profileImageUrl: String?
    let cuisines: [String]?
    let lastOrderAt: Date?
}

// MARK: - My Chefs List View

struct MyChefsListView: View {
    @State private var chefs: [ConnectedChef] = []
    @State private var isLoading = true

    var body: some View {
        List {
            ForEach(chefs) { chef in
                NavigationLink {
                    ChefProfileView(chefId: chef.id)
                } label: {
                    HStack(spacing: SautaiDesign.spacingM) {
                        Circle()
                            .fill(Color.sautai.herbGreen.opacity(0.2))
                            .frame(width: SautaiDesign.avatarSize, height: SautaiDesign.avatarSize)
                            .overlay(
                                Text(String(chef.displayName.prefix(1)).uppercased())
                                    .font(SautaiFont.headline)
                                    .foregroundColor(.sautai.herbGreen)
                            )

                        VStack(alignment: .leading) {
                            Text(chef.displayName)
                                .font(SautaiFont.headline)
                                .foregroundColor(.sautai.slateTile)

                            if let cuisines = chef.cuisines, !cuisines.isEmpty {
                                Text(cuisines.joined(separator: " • "))
                                    .font(SautaiFont.caption)
                                    .foregroundColor(.sautai.slateTile.opacity(0.6))
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle("My Chefs")
        .task {
            do {
                chefs = try await APIClient.shared.getMyChefs()
            } catch {}
            isLoading = false
        }
    }
}

// MARK: - Preview

#Preview {
    CustomerDashboardView()
}

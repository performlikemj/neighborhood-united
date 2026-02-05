//
//  ClientsListView.swift
//  sautai_ios
//
//  List of chef's clients with search and filtering.
//

import SwiftUI

struct ClientsListView: View {
    @State private var clients: [Client] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddLeadSheet = false

    var filteredClients: [Client] {
        if searchText.isEmpty {
            return clients
        }
        return clients.filter { client in
            client.displayName.localizedCaseInsensitiveContains(searchText) ||
            (client.email?.localizedCaseInsensitiveContains(searchText) ?? false) ||
            (client.username?.localizedCaseInsensitiveContains(searchText) ?? false)
        }
    }

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    loadingView
                } else if clients.isEmpty {
                    emptyView
                } else {
                    clientsList
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Clients")
            .searchable(text: $searchText, prompt: "Search clients")
            .refreshable {
                await loadClients()
            }
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingAddLeadSheet = true
                    } label: {
                        Image(systemName: "person.badge.plus")
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }
            .sheet(isPresented: $showingAddLeadSheet) {
                AddLeadView { _ in
                    // Lead added - they'll become a client when they convert
                }
            }
        }
        .task {
            await loadClients()
        }
    }

    // MARK: - Clients List

    private var clientsList: some View {
        List {
            ForEach(filteredClients) { client in
                NavigationLink {
                    ClientDetailView(client: client)
                } label: {
                    ClientRowView(client: client)
                }
                .listRowBackground(Color.white)
                .listRowSeparator(.hidden)
                .listRowInsets(EdgeInsets(
                    top: SautaiDesign.spacingS,
                    leading: SautaiDesign.spacing,
                    bottom: SautaiDesign.spacingS,
                    trailing: SautaiDesign.spacing
                ))
            }
        }
        .listStyle(.plain)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading clients...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "person.2.slash")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text("No clients yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Clients appear here once leads convert to paying customers. Start by adding leads to your pipeline.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddLeadSheet = true
            } label: {
                Label("Add Lead", systemImage: "person.badge.plus")
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingXL)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
            }

            Button {
                // Navigate to Leads tab
                NotificationCenter.default.post(name: .switchToTab, object: 2)
            } label: {
                Text("View Leads")
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacingXL)
    }

    // MARK: - Data Loading

    private func loadClients() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getClients()
            clients = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

// MARK: - Client Row View

struct ClientRowView: View {
    let client: Client

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Avatar
            Circle()
                .fill(Color.sautai.herbGreen.opacity(0.2))
                .frame(width: SautaiDesign.avatarSize, height: SautaiDesign.avatarSize)
                .overlay(
                    Text(client.initials)
                        .font(SautaiFont.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.sautai.herbGreen)
                )

            // Info
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                Text(client.displayName)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                if let email = client.email {
                    Text(email)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }

            Spacer()

            // Order count
            if let orders = client.totalOrders, orders > 0 {
                VStack(alignment: .trailing, spacing: 2) {
                    Text("\(orders)")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.earthenClay)
                    Text("orders")
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }
}

// MARK: - Client Detail View (Placeholder)

struct ClientDetailView: View {
    let client: Client

    var body: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                // Header
                VStack(spacing: SautaiDesign.spacingM) {
                    Circle()
                        .fill(Color.sautai.herbGreen.opacity(0.2))
                        .frame(width: 80, height: 80)
                        .overlay(
                            Text(client.initials)
                                .font(SautaiFont.title)
                                .foregroundColor(.sautai.herbGreen)
                        )

                    Text(client.displayName)
                        .font(SautaiFont.title)
                        .foregroundColor(.sautai.slateTile)

                    if let email = client.email {
                        Text(email)
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }
                .padding(.top, SautaiDesign.spacingL)

                // Stats
                HStack(spacing: SautaiDesign.spacingL) {
                    statItem(value: "\(client.totalOrders ?? 0)", label: "Orders")
                    statItem(value: client.totalSpentDisplay ?? "$0", label: "Total Spent")
                }

                // Connection info
                if let status = client.connectionStatus {
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                        Text("Connection Status")
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.slateTile)

                        Text(status.capitalized)
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile.opacity(0.8))

                        if let since = client.connectedSince {
                            Text("Connected since \(since.formatted(date: .abbreviated, time: .omitted))")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.6))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(SautaiDesign.spacing)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadius)
                }
            }
            .padding(SautaiDesign.spacing)
        }
        .background(Color.sautai.softCream)
        .navigationTitle("Client Details")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func statItem(value: String, label: String) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            Text(value)
                .font(SautaiFont.title2)
                .foregroundColor(.sautai.earthenClay)
            Text(label)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }
}

// MARK: - Preview

#Preview {
    ClientsListView()
}

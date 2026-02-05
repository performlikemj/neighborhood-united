//
//  ServicesListView.swift
//  sautai_ios
//
//  List of chef's service offerings.
//

import SwiftUI

struct ServicesListView: View {
    @State private var services: [ServiceOffering] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddSheet = false

    var filteredServices: [ServiceOffering] {
        if searchText.isEmpty {
            return services
        }
        return services.filter { service in
            service.name.localizedCaseInsensitiveContains(searchText) ||
            service.serviceType.displayName.localizedCaseInsensitiveContains(searchText)
        }
    }

    var body: some View {
        Group {
            if isLoading {
                loadingView
            } else if services.isEmpty {
                emptyView
            } else {
                servicesList
            }
        }
        .searchable(text: $searchText, prompt: "Search services")
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showingAddSheet = true
                } label: {
                    Image(systemName: "plus")
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .sheet(isPresented: $showingAddSheet) {
            AddServiceView { newService in
                services.insert(newService, at: 0)
            }
        }
        .refreshable {
            await loadServices()
        }
        .task {
            await loadServices()
        }
    }

    // MARK: - Services List

    private var servicesList: some View {
        List {
            ForEach(filteredServices) { service in
                NavigationLink {
                    ServiceDetailView(serviceId: service.id)
                } label: {
                    ServiceRowView(service: service)
                }
                .listRowBackground(Color.clear)
                .listRowSeparator(.hidden)
                .listRowInsets(EdgeInsets(
                    top: SautaiDesign.spacingS,
                    leading: SautaiDesign.spacing,
                    bottom: SautaiDesign.spacingS,
                    trailing: SautaiDesign.spacing
                ))
            }
            .onDelete(perform: deleteServices)
        }
        .listStyle(.plain)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading services...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "briefcase")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text("No services yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Create service offerings to let customers know what you provide.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddSheet = true
            } label: {
                Label("Create Service", systemImage: "plus")
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingXL)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
            }
        }
        .padding(SautaiDesign.spacingXL)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Data Loading

    private func loadServices() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getServiceOfferings()
            services = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteServices(at offsets: IndexSet) {
        for index in offsets {
            let service = filteredServices[index]
            Task {
                do {
                    try await APIClient.shared.deleteServiceOffering(id: service.id)
                    await MainActor.run {
                        services.removeAll { $0.id == service.id }
                    }
                } catch {
                    // Handle error
                }
            }
        }
    }
}

// MARK: - Service Row View

struct ServiceRowView: View {
    let service: ServiceOffering

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Type icon
            Image(systemName: service.serviceType.icon)
                .font(.system(size: 20))
                .foregroundColor(typeColor)
                .frame(width: 48, height: 48)
                .background(typeColor.opacity(0.15))
                .cornerRadius(SautaiDesign.cornerRadiusM)

            // Info
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                HStack {
                    Text(service.name)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if !service.isActive {
                        Text("Inactive")
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.warning)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.sautai.warningBackground)
                            .cornerRadius(SautaiDesign.cornerRadiusXS)
                    }
                }

                HStack(spacing: SautaiDesign.spacingS) {
                    Text(service.serviceType.displayName)
                        .font(SautaiFont.caption)
                        .foregroundColor(typeColor)

                    if let duration = service.durationDisplay {
                        Text("•")
                            .foregroundColor(.sautai.slateTile.opacity(0.3))
                        Label(duration, systemImage: "clock")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let priceRange = service.priceRangeDisplay {
                    Text(priceRange)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }

            Spacer()

            // Tier count
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(service.tierCount)")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.earthenClay)
                Text(service.tierCount == 1 ? "tier" : "tiers")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var typeColor: Color {
        switch service.serviceType.colorName {
        case "herbGreen": return .sautai.herbGreen
        case "earthenClay": return .sautai.earthenClay
        case "sunlitApricot": return .sautai.sunlitApricot
        case "info": return .sautai.info
        case "pending": return .sautai.pending
        case "clayPotBrown": return .sautai.clayPotBrown
        case "success": return .sautai.success
        default: return .sautai.slateTile
        }
    }
}

#Preview {
    NavigationStack {
        ServicesListView()
    }
}

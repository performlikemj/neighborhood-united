//
//  ServiceDetailView.swift
//  sautai_ios
//
//  Detailed view of a service offering with price tiers.
//

import SwiftUI

struct ServiceDetailView: View {
    let serviceId: Int

    @Environment(\.dismiss) var dismiss
    @State private var service: ServiceOffering?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingEditSheet = false
    @State private var showingDeleteAlert = false
    @State private var showingAddTierSheet = false

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let service = service {
                serviceContent(service)
            } else {
                errorView
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle(service?.name ?? "Service")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        showingEditSheet = true
                    } label: {
                        Label("Edit", systemImage: "pencil")
                    }

                    Divider()

                    Button(role: .destructive) {
                        showingDeleteAlert = true
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .sheet(isPresented: $showingEditSheet) {
            if let service = service {
                EditServiceView(service: service) { updatedService in
                    self.service = updatedService
                }
            }
        }
        .sheet(isPresented: $showingAddTierSheet) {
            if let service = service {
                AddPriceTierView(serviceId: service.id) { newTier in
                    // Reload to get updated tiers
                    Task { await loadService() }
                }
            }
        }
        .alert("Delete Service", isPresented: $showingDeleteAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) {
                deleteService()
            }
        } message: {
            Text("Are you sure you want to delete this service? This cannot be undone.")
        }
        .refreshable {
            await loadService()
        }
        .task {
            await loadService()
        }
    }

    // MARK: - Service Content

    @ViewBuilder
    private func serviceContent(_ service: ServiceOffering) -> some View {
        VStack(spacing: SautaiDesign.spacingL) {
            // Header
            headerSection(service)

            // Quick stats
            statsRow(service)

            // Description
            if let description = service.description, !description.isEmpty {
                descriptionSection(description)
            }

            // Price Tiers
            tiersSection(service)

            // Metadata
            metadataSection(service)
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Header Section

    private func headerSection(_ service: ServiceOffering) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Icon
            Image(systemName: service.serviceType.icon)
                .font(.system(size: 32))
                .foregroundColor(.white)
                .frame(width: 72, height: 72)
                .background(typeColor(service))
                .cornerRadius(SautaiDesign.cornerRadiusL)

            HStack {
                Text(service.name)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if !service.isActive {
                    Text("Inactive")
                        .font(SautaiFont.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingXS)
                        .background(Color.sautai.warning)
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }

            HStack {
                Text(service.serviceType.displayName)
                    .font(SautaiFont.body)
                    .foregroundColor(typeColor(service))
                Spacer()

                if let price = service.priceRangeDisplay {
                    Text(price)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Stats Row

    private func statsRow(_ service: ServiceOffering) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            statItem(value: "\(service.tierCount)", label: "Tiers", icon: "list.bullet")

            if let duration = service.durationDisplay {
                statItem(value: duration, label: "Duration", icon: "clock")
            }

            if let lead = service.leadTimeHours {
                statItem(value: "\(lead)h", label: "Lead Time", icon: "calendar.badge.clock")
            }

            if let maxOrders = service.maxOrdersPerDay {
                statItem(value: "\(maxOrders)", label: "Max/Day", icon: "bag")
            }
        }
    }

    private func statItem(value: String, label: String, icon: String) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(.sautai.earthenClay)

            Text(value)
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(label)
                .font(SautaiFont.caption2)
                .foregroundColor(.sautai.slateTile.opacity(0.6))
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Description Section

    private func descriptionSection(_ description: String) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text("Description")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(description)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.8))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Tiers Section

    private func tiersSection(_ service: ServiceOffering) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Price Tiers")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Button {
                    showingAddTierSheet = true
                } label: {
                    Label("Add", systemImage: "plus")
                        .font(SautaiFont.buttonSmall)
                        .foregroundColor(.sautai.earthenClay)
                }
            }

            if let tiers = service.priceTiers, !tiers.isEmpty {
                VStack(spacing: SautaiDesign.spacingS) {
                    ForEach(tiers.sorted { ($0.sortOrder ?? 0) < ($1.sortOrder ?? 0) }) { tier in
                        tierCard(tier)
                    }
                }
            } else {
                Text("No price tiers yet. Add tiers to offer different pricing options.")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(SautaiDesign.spacing)
                    .background(Color.sautai.softCream)
                    .cornerRadius(SautaiDesign.cornerRadiusM)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func tierCard(_ tier: PriceTier) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                HStack {
                    Text(tier.name)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if tier.isPopular {
                        Text("Popular")
                            .font(SautaiFont.caption2)
                            .foregroundColor(.white)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 2)
                            .background(Color.sautai.herbGreen)
                            .cornerRadius(SautaiDesign.cornerRadiusFull)
                    }
                }

                if let description = tier.description {
                    Text(description)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                if let servings = tier.servingsDisplay {
                    Text(servings)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            Spacer()

            Text(tier.priceDisplay)
                .font(SautaiFont.title3)
                .foregroundColor(.sautai.earthenClay)
        }
        .padding(SautaiDesign.spacing)
        .background(tier.isPopular ? Color.sautai.herbGreen.opacity(0.05) : Color.sautai.softCream)
        .cornerRadius(SautaiDesign.cornerRadiusM)
        .overlay(
            RoundedRectangle(cornerRadius: SautaiDesign.cornerRadiusM)
                .stroke(tier.isPopular ? Color.sautai.herbGreen.opacity(0.3) : Color.clear, lineWidth: 1)
        )
    }

    // MARK: - Metadata Section

    private func metadataSection(_ service: ServiceOffering) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            if let createdAt = service.createdAt {
                HStack {
                    Text("Created")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                    Spacer()
                    Text(createdAt.formatted(date: .abbreviated, time: .omitted))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            if let updatedAt = service.updatedAt {
                HStack {
                    Text("Last Updated")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                    Spacer()
                    Text(updatedAt.formatted(date: .abbreviated, time: .omitted))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Helpers

    private func typeColor(_ service: ServiceOffering) -> Color {
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

    // MARK: - Loading/Error Views

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading service...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.top, 100)
    }

    private var errorView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Could not load service")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Button {
                Task { await loadService() }
            } label: {
                Text("Try Again")
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacingXL)
    }

    // MARK: - Data Loading

    private func loadService() async {
        isLoading = true
        error = nil
        do {
            service = try await APIClient.shared.getServiceOfferingDetail(id: serviceId)
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteService() {
        Task {
            do {
                try await APIClient.shared.deleteServiceOffering(id: serviceId)
                await MainActor.run {
                    dismiss()
                }
            } catch {
                // Handle error
            }
        }
    }
}

#Preview {
    NavigationStack {
        ServiceDetailView(serviceId: 1)
    }
}

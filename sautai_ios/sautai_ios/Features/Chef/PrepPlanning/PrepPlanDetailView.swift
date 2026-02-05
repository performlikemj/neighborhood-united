//
//  PrepPlanDetailView.swift
//  sautai_ios
//
//  Detailed view of a prep plan with items and shopping list.
//

import SwiftUI

struct PrepPlanDetailView: View {
    let planId: Int

    @State private var plan: PrepPlan?
    @State private var shoppingList: ShoppingList?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var selectedTab = 0

    var body: some View {
        VStack(spacing: 0) {
            // Tab Selector
            Picker("View", selection: $selectedTab) {
                Text("Prep Items").tag(0)
                Text("Shopping List").tag(1)
            }
            .pickerStyle(.segmented)
            .padding(SautaiDesign.spacing)
            .background(Color.white)

            // Content
            if isLoading {
                loadingView
            } else if let error = error {
                errorView(error)
            } else if let plan = plan {
                TabView(selection: $selectedTab) {
                    prepItemsView(plan)
                        .tag(0)

                    if let shoppingList = shoppingList {
                        ShoppingListView(
                            shoppingList: shoppingList,
                            planId: planId,
                            onUpdate: { updatedList in
                                self.shoppingList = updatedList
                            }
                        )
                        .tag(1)
                    } else {
                        noShoppingListView
                            .tag(1)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle(plan?.displayName ?? "Prep Plan")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable {
            await loadData()
        }
        .task {
            await loadData()
        }
    }

    // MARK: - Prep Items View

    private func prepItemsView(_ plan: PrepPlan) -> some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                // Plan Info
                planInfoCard(plan)

                // Clients
                if let clients = plan.clients, !clients.isEmpty {
                    clientsSection(clients)
                }

                // Items
                if let items = plan.items, !items.isEmpty {
                    prepItemsSection(items)
                } else {
                    emptyItemsView
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Plan Info Card

    private func planInfoCard(_ plan: PrepPlan) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Label(plan.dateRange, systemImage: "calendar")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                HStack(spacing: 4) {
                    Image(systemName: plan.status.icon)
                    Text(plan.status.displayName)
                }
                .font(SautaiFont.caption)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(statusColor(plan.status).opacity(0.15))
                .foregroundColor(statusColor(plan.status))
                .cornerRadius(SautaiDesign.cornerRadiusS)
            }

            Divider()

            HStack(spacing: SautaiDesign.spacingL) {
                if let servings = plan.totalServings {
                    VStack {
                        Text("\(servings)")
                            .font(SautaiFont.title2)
                            .foregroundColor(.sautai.earthenClay)
                        Text("Servings")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let prepTime = plan.estimatedPrepTime {
                    VStack {
                        Text("\(prepTime)")
                            .font(SautaiFont.title2)
                            .foregroundColor(.sautai.herbGreen)
                        Text("Minutes")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let items = plan.items {
                    VStack {
                        Text("\(items.count)")
                            .font(SautaiFont.title2)
                            .foregroundColor(.sautai.sunlitApricot)
                        Text("Items")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }
            }
            .frame(maxWidth: .infinity)

            if let notes = plan.notes, !notes.isEmpty {
                Divider()
                Text(notes)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.8))
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Clients Section

    private func clientsSection(_ clients: [PrepPlanClient]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Clients")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(clients) { client in
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(client.clientName)
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile)

                        if let instructions = client.specialInstructions, !instructions.isEmpty {
                            Text(instructions)
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.7))
                                .lineLimit(2)
                        }
                    }

                    Spacer()

                    VStack(alignment: .trailing, spacing: 2) {
                        Text("\(client.servings) servings")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.earthenClay)

                        if let date = client.deliveryDate {
                            Text(date.formatted(date: .abbreviated, time: .omitted))
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.slateTile.opacity(0.6))
                        }
                    }
                }
                .padding(SautaiDesign.spacingM)
                .background(Color.sautai.softCream)
                .cornerRadius(SautaiDesign.cornerRadiusS)
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Prep Items Section

    private func prepItemsSection(_ items: [PrepPlanItem]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Prep Items")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                let completed = items.filter { $0.isPrepared }.count
                Text("\(completed)/\(items.count)")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
            }

            // Group by category
            let grouped = Dictionary(grouping: items) { $0.category ?? "Other" }
            let sortedCategories = grouped.keys.sorted()

            ForEach(sortedCategories, id: \.self) { category in
                if let categoryItems = grouped[category] {
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                        Text(category)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                            .textCase(.uppercase)

                        ForEach(categoryItems) { item in
                            PrepItemRow(item: item)
                        }
                    }
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Empty Views

    private var emptyItemsView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "tray")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No prep items")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private var noShoppingListView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "cart")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No shopping list generated")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Loading & Error Views

    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView()
                .scaleEffect(1.5)
            Spacer()
        }
    }

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load prep plan")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadData() }
            }
            .buttonStyle(.borderedProminent)

            Spacer()
        }
        .padding()
    }

    // MARK: - Helpers

    private func statusColor(_ status: PrepPlanStatus) -> Color {
        switch status {
        case .active: return .sautai.herbGreen
        case .draft: return .sautai.slateTile
        case .completed: return .sautai.success
        case .cancelled: return .sautai.danger
        }
    }

    private func loadData() async {
        isLoading = true
        error = nil

        do {
            plan = try await APIClient.shared.getPrepPlanDetail(id: planId)
            shoppingList = try await APIClient.shared.getShoppingList(prepPlanId: planId)
        } catch {
            self.error = error
        }

        isLoading = false
    }
}

// MARK: - Prep Item Row

struct PrepItemRow: View {
    let item: PrepPlanItem

    var body: some View {
        HStack {
            Image(systemName: item.isPrepared ? "checkmark.circle.fill" : "circle")
                .foregroundColor(item.isPrepared ? .sautai.success : .sautai.slateTile.opacity(0.3))

            VStack(alignment: .leading, spacing: 2) {
                Text(item.name)
                    .font(SautaiFont.body)
                    .foregroundColor(item.isPrepared ? .sautai.slateTile.opacity(0.5) : .sautai.slateTile)
                    .strikethrough(item.isPrepared)

                if let instructions = item.prepInstructions, !instructions.isEmpty {
                    Text(instructions)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                        .lineLimit(1)
                }
            }

            Spacer()

            Text(item.displayQuantity)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.earthenClay)

            if let time = item.estimatedPrepTime {
                Text("\(time)m")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.softCream)
        .cornerRadius(SautaiDesign.cornerRadiusS)
    }
}

// MARK: - Quick Generate View

struct QuickGenerateView: View {
    @Environment(\.dismiss) var dismiss
    let onGenerated: (PrepPlan) -> Void

    @State private var orders: [Order] = []
    @State private var selectedOrderIds: Set<Int> = []
    @State private var isLoading = false
    @State private var isLoadingOrders = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            VStack {
                if isLoadingOrders {
                    ProgressView()
                } else if orders.isEmpty {
                    emptyOrdersView
                } else {
                    ordersList
                }
            }
            .navigationTitle("Quick Generate")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Generate") {
                        generatePlan()
                    }
                    .disabled(selectedOrderIds.isEmpty || isLoading)
                }
            }
        }
        .task {
            await loadOrders()
        }
    }

    private var ordersList: some View {
        List {
            Section {
                ForEach(orders) { order in
                    Button {
                        if selectedOrderIds.contains(order.id) {
                            selectedOrderIds.remove(order.id)
                        } else {
                            selectedOrderIds.insert(order.id)
                        }
                    } label: {
                        HStack {
                            Image(systemName: selectedOrderIds.contains(order.id) ? "checkmark.circle.fill" : "circle")
                                .foregroundColor(selectedOrderIds.contains(order.id) ? .sautai.earthenClay : .sautai.slateTile.opacity(0.3))

                            VStack(alignment: .leading, spacing: 2) {
                                Text(order.customerName ?? "Order #\(order.id)")
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)

                                if let date = order.deliveryDate {
                                    Text(date.formatted(date: .abbreviated, time: .omitted))
                                        .font(SautaiFont.caption)
                                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                                }
                            }

                            Spacer()

                            Text(order.displayTotal)
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.earthenClay)
                        }
                    }
                    .buttonStyle(.plain)
                }
            } header: {
                Text("Select orders to include")
            } footer: {
                if let error = errorMessage {
                    Text(error)
                        .foregroundColor(.sautai.danger)
                }
            }
        }
    }

    private var emptyOrdersView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "bag")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No pending orders")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
    }

    private func loadOrders() async {
        isLoadingOrders = true
        do {
            let response = try await APIClient.shared.getChefOrders(status: "confirmed")
            orders = response.results
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoadingOrders = false
    }

    private func generatePlan() {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let newPlan = try await APIClient.shared.quickGeneratePrepPlan(orderIds: Array(selectedOrderIds))
                await MainActor.run {
                    onGenerated(newPlan)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

#Preview {
    NavigationStack {
        PrepPlanDetailView(planId: 1)
    }
}

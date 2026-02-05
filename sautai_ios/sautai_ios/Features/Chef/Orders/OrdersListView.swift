//
//  OrdersListView.swift
//  sautai_ios
//
//  Main orders list with status filters for chef order management.
//

import SwiftUI

struct OrdersListView: View {
    @State private var orders: [Order] = []
    @State private var selectedStatus: OrderStatus? = nil
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingCalendar = false

    private let statusFilters: [OrderStatus?] = [nil, .pending, .confirmed, .preparing, .ready, .completed, .cancelled]

    var filteredOrders: [Order] {
        guard let status = selectedStatus else {
            return orders
        }
        return orders.filter { $0.status == status }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Status filter tabs
                statusFilterBar

                // Orders list
                Group {
                    if isLoading {
                        loadingView
                    } else if filteredOrders.isEmpty {
                        emptyView
                    } else {
                        ordersList
                    }
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Orders")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingCalendar = true
                    } label: {
                        Image(systemName: "calendar")
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }
            .refreshable {
                await loadOrders()
            }
            .sheet(isPresented: $showingCalendar) {
                OrderCalendarView()
            }
        }
        .task {
            await loadOrders()
        }
    }

    // MARK: - Status Filter Bar

    private var statusFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                ForEach(statusFilters, id: \.self) { status in
                    filterChip(for: status)
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.vertical, SautaiDesign.spacingM)
        }
        .background(Color.white)
    }

    private func filterChip(for status: OrderStatus?) -> some View {
        let isSelected = selectedStatus == status
        let label = status?.displayName ?? "All"
        let count = countForStatus(status)

        return Button {
            withAnimation(.sautaiQuick) {
                selectedStatus = status
            }
        } label: {
            HStack(spacing: SautaiDesign.spacingXS) {
                Text(label)
                    .font(SautaiFont.buttonSmall)

                if count > 0 {
                    Text("\(count)")
                        .font(SautaiFont.caption2)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(isSelected ? Color.white.opacity(0.3) : Color.sautai.earthenClay.opacity(0.2))
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }
            .foregroundColor(isSelected ? .white : .sautai.slateTile)
            .padding(.horizontal, SautaiDesign.spacingM)
            .padding(.vertical, SautaiDesign.spacingS)
            .background(isSelected ? Color.sautai.earthenClay : Color.sautai.softCream)
            .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }

    private func countForStatus(_ status: OrderStatus?) -> Int {
        guard let status = status else {
            return orders.count
        }
        return orders.filter { $0.status == status }.count
    }

    // MARK: - Orders List

    private var ordersList: some View {
        List {
            ForEach(filteredOrders) { order in
                NavigationLink {
                    OrderDetailView(orderId: order.id)
                } label: {
                    OrderRowView(order: order)
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
        }
        .listStyle(.plain)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading orders...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: selectedStatus == nil ? "bag" : "bag.badge.questionmark")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text(selectedStatus == nil ? "No orders yet" : "No \(selectedStatus!.displayName.lowercased()) orders")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(selectedStatus == nil
                ? "Orders from your meal events and services will appear here."
                : "Try selecting a different filter to see more orders.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            if selectedStatus != nil {
                Button {
                    withAnimation(.sautaiQuick) {
                        selectedStatus = nil
                    }
                } label: {
                    Text("Show All Orders")
                        .font(SautaiFont.button)
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .padding(SautaiDesign.spacingXL)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Data Loading

    private func loadOrders() async {
        isLoading = true
        error = nil
        do {
            let response = try await APIClient.shared.getChefOrders()
            orders = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

#Preview {
    OrdersListView()
}

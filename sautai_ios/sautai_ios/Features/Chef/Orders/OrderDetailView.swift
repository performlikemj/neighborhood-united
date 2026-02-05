//
//  OrderDetailView.swift
//  sautai_ios
//
//  Detailed order view with actions for confirming, cancelling, etc.
//

import SwiftUI

struct OrderDetailView: View {
    let orderId: Int

    @Environment(\.dismiss) var dismiss
    @State private var order: Order?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingCancelSheet = false
    @State private var showingConfirmAlert = false
    @State private var isProcessing = false
    @State private var actionError: String?

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let order = order {
                orderContent(order)
            } else {
                errorView
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle("Order #\(orderId)")
        .navigationBarTitleDisplayMode(.inline)
        .refreshable {
            await loadOrder()
        }
        .alert("Confirm Order", isPresented: $showingConfirmAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Confirm") {
                Task { await confirmOrder() }
            }
        } message: {
            Text("This will confirm the order and notify the customer. Are you sure?")
        }
        .sheet(isPresented: $showingCancelSheet) {
            CancelOrderSheet(orderId: orderId) { updatedOrder in
                order = updatedOrder
            }
        }
        .task {
            await loadOrder()
        }
    }

    // MARK: - Order Content

    @ViewBuilder
    private func orderContent(_ order: Order) -> some View {
        VStack(spacing: SautaiDesign.spacingL) {
            // Status header
            statusHeader(order)

            // Action buttons
            if order.status == .pending || order.status == .confirmed {
                actionButtons(order)
            }

            // Customer info
            customerSection(order)

            // Delivery info
            deliverySection(order)

            // Order items
            itemsSection(order)

            // Special requests
            if let requests = order.specialRequests, !requests.isEmpty {
                specialRequestsSection(requests)
            }

            // Order timeline
            timelineSection(order)
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Status Header

    private func statusHeader(_ order: Order) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Circle()
                .fill(statusColor(order).opacity(0.15))
                .frame(width: 64, height: 64)
                .overlay(
                    Image(systemName: order.status.icon)
                        .font(.system(size: 28))
                        .foregroundColor(statusColor(order))
                )

            Text(order.status.displayName)
                .font(SautaiFont.title3)
                .foregroundColor(statusColor(order))

            Text(order.displayTotal)
                .font(SautaiFont.stats)
                .foregroundColor(.sautai.slateTile)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Action Buttons

    private func actionButtons(_ order: Order) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            if let error = actionError {
                Text(error)
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.danger)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }

            HStack(spacing: SautaiDesign.spacingM) {
                if order.status == .pending {
                    Button {
                        showingConfirmAlert = true
                    } label: {
                        HStack {
                            if isProcessing {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "checkmark.circle.fill")
                            }
                            Text("Confirm Order")
                        }
                        .font(SautaiFont.button)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, SautaiDesign.spacingM)
                        .background(Color.sautai.herbGreen)
                        .cornerRadius(SautaiDesign.cornerRadius)
                    }
                    .disabled(isProcessing)
                }

                Button {
                    showingCancelSheet = true
                } label: {
                    HStack {
                        Image(systemName: "xmark.circle")
                        Text("Cancel")
                    }
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.danger)
                    .frame(maxWidth: order.status == .pending ? nil : .infinity)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .padding(.horizontal, SautaiDesign.spacingL)
                    .background(Color.sautai.dangerBackground)
                    .cornerRadius(SautaiDesign.cornerRadius)
                }
                .disabled(isProcessing)
            }
        }
    }

    // MARK: - Customer Section

    private func customerSection(_ order: Order) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            sectionHeader("Customer")

            HStack(spacing: SautaiDesign.spacingM) {
                Circle()
                    .fill(Color.sautai.herbGreen.opacity(0.2))
                    .frame(width: 44, height: 44)
                    .overlay(
                        Text(String(order.customerName?.prefix(1) ?? "?").uppercased())
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.herbGreen)
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text(order.customerName ?? "Unknown Customer")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if let customerId = order.customerId {
                        Text("Customer #\(customerId)")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                Spacer()

                Button {
                    // Navigate to messaging or client detail
                } label: {
                    Image(systemName: "message.fill")
                        .font(.system(size: 18))
                        .foregroundColor(.sautai.earthenClay)
                        .padding(SautaiDesign.spacingS)
                        .background(Color.sautai.earthenClay.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Delivery Section

    private func deliverySection(_ order: Order) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            sectionHeader("Delivery")

            HStack {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    Label {
                        if let date = order.deliveryDate {
                            Text(date.formatted(date: .complete, time: .omitted))
                        } else {
                            Text("Not scheduled")
                        }
                    } icon: {
                        Image(systemName: "calendar")
                            .foregroundColor(.sautai.earthenClay)
                    }
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                    if let time = order.deliveryTime {
                        Label {
                            Text(time)
                        } icon: {
                            Image(systemName: "clock")
                                .foregroundColor(.sautai.earthenClay)
                        }
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)
                    }
                }

                Spacer()

                if order.isUpcoming {
                    VStack(alignment: .trailing, spacing: 2) {
                        Text(daysUntilDelivery(order.deliveryDate))
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.earthenClay)
                        Text("until delivery")
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }
            }

            if let address = order.deliveryAddress {
                Divider()

                Label {
                    VStack(alignment: .leading, spacing: 2) {
                        if let street = address.street, !street.isEmpty {
                            Text(street)
                        }
                        Text("\(address.city ?? ""), \(address.state ?? "") \(address.displayPostalCode)")
                    }
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)
                } icon: {
                    Image(systemName: "location")
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Items Section

    private func itemsSection(_ order: Order) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            sectionHeader("Items")

            if let items = order.items, !items.isEmpty {
                VStack(spacing: 0) {
                    ForEach(items) { item in
                        itemRow(item)
                        if item.id != items.last?.id {
                            Divider()
                                .padding(.horizontal, SautaiDesign.spacing)
                        }
                    }
                }
            } else {
                Text("No items")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func itemRow(_ item: OrderItem) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(item.name)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                if let notes = item.notes, !notes.isEmpty {
                    Text(notes)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            Spacer()

            Text("×\(item.quantity)")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            if let total = item.totalPrice {
                Text("$\(total)")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)
                    .frame(width: 70, alignment: .trailing)
            }
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Special Requests Section

    private func specialRequestsSection(_ requests: String) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            sectionHeader("Special Requests")

            Text(requests)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.sautai.sunlitApricot.opacity(0.15))
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Timeline Section

    private func timelineSection(_ order: Order) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            sectionHeader("Timeline")

            VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
                if let createdAt = order.createdAt {
                    timelineItem(icon: "plus.circle", label: "Order Created", date: createdAt)
                }

                if let paidAt = order.paidAt {
                    timelineItem(icon: "creditcard", label: "Payment Received", date: paidAt)
                }

                if let updatedAt = order.updatedAt, order.status != .pending {
                    timelineItem(icon: order.status.icon, label: "Status: \(order.status.displayName)", date: updatedAt)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func timelineItem(icon: String, label: String, date: Date) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundColor(.sautai.earthenClay)
                .frame(width: 24)

            Text(label)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)

            Spacer()

            Text(date.formatted(date: .abbreviated, time: .shortened))
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.6))
        }
    }

    // MARK: - Helpers

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(SautaiFont.headline)
            .foregroundColor(.sautai.slateTile)
    }

    private func statusColor(_ order: Order) -> Color {
        switch order.status.colorName {
        case "warning": return .sautai.warning
        case "info": return .sautai.info
        case "primary": return .sautai.earthenClay
        case "success": return .sautai.herbGreen
        case "danger": return .sautai.danger
        default: return .sautai.slateTile
        }
    }

    private func daysUntilDelivery(_ date: Date?) -> String {
        guard let date = date else { return "-" }
        let calendar = Calendar.current
        let days = calendar.dateComponents([.day], from: Date(), to: date).day ?? 0
        if days == 0 { return "Today" }
        if days == 1 { return "1 day" }
        return "\(days) days"
    }

    // MARK: - Loading/Error Views

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading order...")
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

            Text("Could not load order")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            if let error = error {
                Text(error.localizedDescription)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
                    .multilineTextAlignment(.center)
            }

            Button {
                Task { await loadOrder() }
            } label: {
                Text("Try Again")
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacingXL)
    }

    // MARK: - Data Loading

    private func loadOrder() async {
        isLoading = true
        error = nil
        do {
            order = try await APIClient.shared.getChefOrderDetail(id: orderId)
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func confirmOrder() async {
        isProcessing = true
        actionError = nil
        do {
            order = try await APIClient.shared.confirmOrder(id: orderId)
        } catch {
            actionError = error.localizedDescription
        }
        isProcessing = false
    }
}

// MARK: - Cancel Order Sheet

struct CancelOrderSheet: View {
    @Environment(\.dismiss) var dismiss
    let orderId: Int
    let onCancel: (Order) -> Void

    @State private var reason = ""
    @State private var isProcessing = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Why are you cancelling this order?", text: $reason, axis: .vertical)
                        .lineLimit(3...6)
                } header: {
                    Text("Reason (optional)")
                } footer: {
                    Text("The customer will be notified of the cancellation.")
                }

                if let error = error {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Cancel Order")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Back") { dismiss() }
                }
                ToolbarItem(placement: .destructiveAction) {
                    Button("Cancel Order") {
                        Task { await cancelOrder() }
                    }
                    .foregroundColor(.sautai.danger)
                    .disabled(isProcessing)
                }
            }
        }
    }

    private func cancelOrder() async {
        isProcessing = true
        error = nil
        do {
            let updatedOrder = try await APIClient.shared.cancelOrder(
                id: orderId,
                reason: reason.isEmpty ? nil : reason
            )
            await MainActor.run {
                onCancel(updatedOrder)
                dismiss()
            }
        } catch {
            await MainActor.run {
                self.error = error.localizedDescription
                isProcessing = false
            }
        }
    }
}

#Preview {
    NavigationStack {
        OrderDetailView(orderId: 1)
    }
}

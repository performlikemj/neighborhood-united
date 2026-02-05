//
//  MealEventDetailView.swift
//  sautai_ios
//
//  Detailed view of a meal event with orders and management.
//

import SwiftUI

struct MealEventDetailView: View {
    let eventId: Int

    @Environment(\.dismiss) var dismiss
    @State private var event: ChefMealEvent?
    @State private var orders: [ChefMealOrder] = []
    @State private var isLoading = true
    @State private var isLoadingOrders = true
    @State private var error: Error?
    @State private var showingEditSheet = false
    @State private var showingDuplicateSheet = false
    @State private var showingCancelAlert = false

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let event = event {
                eventContent(event)
            } else {
                errorView
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle(event?.title ?? "Event")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        showingEditSheet = true
                    } label: {
                        Label("Edit", systemImage: "pencil")
                    }

                    Button {
                        showingDuplicateSheet = true
                    } label: {
                        Label("Duplicate", systemImage: "doc.on.doc")
                    }

                    Divider()

                    Button(role: .destructive) {
                        showingCancelAlert = true
                    } label: {
                        Label("Cancel Event", systemImage: "xmark.circle")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .sheet(isPresented: $showingEditSheet) {
            if let event = event {
                EditMealEventView(event: event) { updatedEvent in
                    self.event = updatedEvent
                }
            }
        }
        .sheet(isPresented: $showingDuplicateSheet) {
            DuplicateEventSheet(eventId: eventId) { newEvent in
                // Navigate to new event or just dismiss
            }
        }
        .alert("Cancel Event", isPresented: $showingCancelAlert) {
            Button("Keep Event", role: .cancel) {}
            Button("Cancel Event", role: .destructive) {
                cancelEvent()
            }
        } message: {
            Text("Are you sure you want to cancel this event? Customers with orders will be notified.")
        }
        .refreshable {
            await loadEvent()
            await loadOrders()
        }
        .task {
            await loadEvent()
            await loadOrders()
        }
    }

    // MARK: - Event Content

    @ViewBuilder
    private func eventContent(_ event: ChefMealEvent) -> some View {
        VStack(spacing: SautaiDesign.spacingL) {
            // Header
            headerSection(event)

            // Quick stats
            statsRow(event)

            // Description
            if let description = event.description, !description.isEmpty {
                descriptionSection(description)
            }

            // Orders section
            ordersSection

            // Tags
            if let tags = event.dietaryTags, !tags.isEmpty {
                tagsSection(tags)
            }
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Header Section

    private func headerSection(_ event: ChefMealEvent) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            if let imageUrl = event.imageUrl, let url = URL(string: imageUrl) {
                AsyncImage(url: url) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    imagePlaceholder
                }
                .frame(height: 180)
                .cornerRadius(SautaiDesign.cornerRadius)
                .clipped()
            }

            HStack {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    Text(event.title)
                        .font(SautaiFont.title2)
                        .foregroundColor(.sautai.slateTile)

                    HStack(spacing: SautaiDesign.spacingM) {
                        Label {
                            Text(event.eventDate.formatted(date: .complete, time: .omitted))
                        } icon: {
                            Image(systemName: "calendar")
                                .foregroundColor(.sautai.earthenClay)
                        }
                        .font(SautaiFont.body)

                        if let time = event.eventTime {
                            Label {
                                Text(time)
                            } icon: {
                                Image(systemName: "clock")
                                    .foregroundColor(.sautai.earthenClay)
                            }
                            .font(SautaiFont.body)
                        }
                    }
                    .foregroundColor(.sautai.slateTile)
                }

                Spacer()

                statusBadge(event)
            }

            // Price display
            HStack {
                Text("Price per serving")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
                Spacer()
                Text(event.displayPrice)
                    .font(SautaiFont.title3)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private var imagePlaceholder: some View {
        Rectangle()
            .fill(Color.sautai.sunlitApricot.opacity(0.2))
            .frame(height: 180)
            .cornerRadius(SautaiDesign.cornerRadius)
            .overlay(
                Image(systemName: "fork.knife")
                    .font(.system(size: 48))
                    .foregroundColor(.sautai.sunlitApricot.opacity(0.5))
            )
    }

    private func statusBadge(_ event: ChefMealEvent) -> some View {
        Group {
            if event.isClosed {
                Text("Closed")
                    .font(SautaiFont.caption)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingM)
                    .padding(.vertical, SautaiDesign.spacingXS)
                    .background(Color.sautai.slateTile)
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            } else if event.isAvailable {
                Text("Open")
                    .font(SautaiFont.caption)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingM)
                    .padding(.vertical, SautaiDesign.spacingXS)
                    .background(Color.sautai.herbGreen)
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            } else {
                Text("Full")
                    .font(SautaiFont.caption)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingM)
                    .padding(.vertical, SautaiDesign.spacingXS)
                    .background(Color.sautai.warning)
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            }
        }
    }

    // MARK: - Stats Row

    private func statsRow(_ event: ChefMealEvent) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            if let max = event.maxServings {
                let current = event.currentServings ?? 0
                statItem(value: "\(current)/\(max)", label: "Servings", icon: "person.2")
            }

            if let available = event.availableServings {
                statItem(value: "\(available)", label: "Available", icon: "checkmark.circle")
            }

            statItem(value: "\(orders.count)", label: "Orders", icon: "bag")
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

    // MARK: - Orders Section

    private var ordersSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Orders")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Text("\(orders.count)")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.earthenClay)
            }

            if isLoadingOrders {
                ProgressView()
                    .frame(maxWidth: .infinity)
                    .padding()
            } else if orders.isEmpty {
                Text("No orders yet")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(SautaiDesign.spacing)
                    .background(Color.sautai.softCream)
                    .cornerRadius(SautaiDesign.cornerRadiusM)
            } else {
                VStack(spacing: SautaiDesign.spacingS) {
                    ForEach(orders) { order in
                        orderRow(order)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func orderRow(_ order: ChefMealOrder) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            Circle()
                .fill(Color.sautai.herbGreen.opacity(0.2))
                .frame(width: 36, height: 36)
                .overlay(
                    Text(String(order.customerName?.prefix(1) ?? "?").uppercased())
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.herbGreen)
                )

            VStack(alignment: .leading, spacing: 2) {
                Text(order.customerName ?? "Customer")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                Text("\(order.quantity) serving\(order.quantity == 1 ? "" : "s")")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
            }

            Spacer()

            Text(order.displayStatus)
                .font(SautaiFont.caption)
                .foregroundColor(orderStatusColor(order.status))
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.softCream)
        .cornerRadius(SautaiDesign.cornerRadiusM)
    }

    private func orderStatusColor(_ status: String) -> Color {
        switch status.lowercased() {
        case "confirmed": return .sautai.herbGreen
        case "pending": return .sautai.warning
        case "cancelled": return .sautai.danger
        default: return .sautai.slateTile
        }
    }

    // MARK: - Tags Section

    private func tagsSection(_ tags: [String]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text("Dietary Info")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            FlowLayout(spacing: SautaiDesign.spacingS) {
                ForEach(tags, id: \.self) { tag in
                    Text(tag)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.herbGreen)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingXS)
                        .background(Color.sautai.herbGreen.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Loading/Error Views

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading event...")
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

            Text("Could not load event")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Button {
                Task { await loadEvent() }
            } label: {
                Text("Try Again")
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacingXL)
    }

    // MARK: - Data Loading

    private func loadEvent() async {
        isLoading = true
        error = nil
        do {
            event = try await APIClient.shared.getMealEventDetail(id: eventId)
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func loadOrders() async {
        isLoadingOrders = true
        do {
            orders = try await APIClient.shared.getMealEventOrders(eventId: eventId)
        } catch {
            // Handle error silently
        }
        isLoadingOrders = false
    }

    private func cancelEvent() {
        Task {
            do {
                try await APIClient.shared.cancelMealEvent(id: eventId)
                await MainActor.run {
                    dismiss()
                }
            } catch {
                // Handle error
            }
        }
    }
}

// MARK: - Duplicate Event Sheet

struct DuplicateEventSheet: View {
    @Environment(\.dismiss) var dismiss
    let eventId: Int
    let onDuplicate: (ChefMealEvent) -> Void

    @State private var selectedDate = Date()
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    DatePicker("Event Date", selection: $selectedDate, displayedComponents: .date)
                } header: {
                    Text("New Event Date")
                } footer: {
                    Text("Select a date for the duplicated event")
                }

                if let error = error {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Duplicate Event")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Duplicate") {
                        duplicateEvent()
                    }
                    .disabled(isLoading)
                }
            }
        }
    }

    private func duplicateEvent() {
        isLoading = true
        error = nil

        Task {
            do {
                let newEvent = try await APIClient.shared.duplicateMealEvent(id: eventId, newDate: selectedDate)
                await MainActor.run {
                    onDuplicate(newEvent)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    self.error = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

#Preview {
    NavigationStack {
        MealEventDetailView(eventId: 1)
    }
}

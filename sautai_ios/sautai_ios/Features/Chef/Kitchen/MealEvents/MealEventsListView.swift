//
//  MealEventsListView.swift
//  sautai_ios
//
//  List of chef's meal events (meal shares).
//

import SwiftUI

struct MealEventsListView: View {
    @State private var events: [ChefMealEvent] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddSheet = false
    @State private var filterMode: EventFilterMode = .upcoming

    enum EventFilterMode: String, CaseIterable {
        case upcoming
        case past
        case all

        var displayName: String {
            rawValue.capitalized
        }
    }

    var filteredEvents: [ChefMealEvent] {
        var filtered = events

        switch filterMode {
        case .upcoming:
            filtered = filtered.filter { $0.eventDate >= Date() && !$0.isClosed }
        case .past:
            filtered = filtered.filter { $0.eventDate < Date() || $0.isClosed }
        case .all:
            break
        }

        if !searchText.isEmpty {
            filtered = filtered.filter { event in
                event.title.localizedCaseInsensitiveContains(searchText) ||
                (event.cuisineType?.localizedCaseInsensitiveContains(searchText) ?? false)
            }
        }

        return filtered.sorted { $0.eventDate > $1.eventDate }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Filter picker
            filterPicker

            // Events list
            Group {
                if isLoading {
                    loadingView
                } else if filteredEvents.isEmpty {
                    emptyView
                } else {
                    eventsList
                }
            }
        }
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
            AddMealEventView { newEvent in
                events.insert(newEvent, at: 0)
            }
        }
        .refreshable {
            await loadEvents()
        }
        .task {
            await loadEvents()
        }
    }

    // MARK: - Filter Picker

    private var filterPicker: some View {
        HStack(spacing: SautaiDesign.spacingS) {
            ForEach(EventFilterMode.allCases, id: \.self) { mode in
                Button {
                    withAnimation(.sautaiQuick) {
                        filterMode = mode
                    }
                } label: {
                    Text(mode.displayName)
                        .font(SautaiFont.buttonSmall)
                        .foregroundColor(filterMode == mode ? .white : .sautai.slateTile)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingS)
                        .background(filterMode == mode ? Color.sautai.earthenClay : Color.sautai.softCream)
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }

            Spacer()
        }
        .padding(.horizontal, SautaiDesign.spacing)
        .padding(.vertical, SautaiDesign.spacingS)
    }

    // MARK: - Events List

    private var eventsList: some View {
        List {
            ForEach(filteredEvents) { event in
                NavigationLink {
                    MealEventDetailView(eventId: event.id)
                } label: {
                    MealEventRowView(event: event)
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
            Text("Loading events...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "calendar.badge.clock")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text(filterMode == .upcoming ? "No upcoming events" : "No events found")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Create a meal event to share your cooking with the community.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddSheet = true
            } label: {
                Label("Create Event", systemImage: "plus")
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

    private func loadEvents() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getMealEvents()
            events = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

// MARK: - Meal Event Row View

struct MealEventRowView: View {
    let event: ChefMealEvent

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            // Header with title and status
            HStack {
                Text(event.title)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                statusBadge
            }

            // Date and time
            HStack(spacing: SautaiDesign.spacingM) {
                Label {
                    Text(event.eventDate.formatted(date: .abbreviated, time: .omitted))
                } icon: {
                    Image(systemName: "calendar")
                        .foregroundColor(.sautai.earthenClay)
                }
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)

                if let time = event.eventTime {
                    Label {
                        Text(time)
                    } icon: {
                        Image(systemName: "clock")
                            .foregroundColor(.sautai.earthenClay)
                    }
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile)
                }
            }

            // Availability and price
            HStack {
                // Servings progress
                if let max = event.maxServings {
                    let current = event.currentServings ?? 0
                    let available = max - current

                    VStack(alignment: .leading, spacing: 4) {
                        HStack(spacing: 4) {
                            Text("\(available)")
                                .font(SautaiFont.headline)
                                .foregroundColor(available > 0 ? .sautai.herbGreen : .sautai.danger)
                            Text("/ \(max) available")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.6))
                        }

                        GeometryReader { geometry in
                            ZStack(alignment: .leading) {
                                Rectangle()
                                    .fill(Color.sautai.slateTile.opacity(0.1))
                                    .frame(height: 4)
                                    .cornerRadius(2)

                                Rectangle()
                                    .fill(progressColor(current: current, max: max))
                                    .frame(width: geometry.size.width * CGFloat(current) / CGFloat(max), height: 4)
                                    .cornerRadius(2)
                            }
                        }
                        .frame(height: 4)
                    }
                }

                Spacer()

                // Price
                Text(event.displayPrice)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.earthenClay)
            }

            // Tags
            if let cuisine = event.cuisineType {
                HStack(spacing: SautaiDesign.spacingXS) {
                    Text(cuisine)
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.earthenClay)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(Color.sautai.earthenClay.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusFull)

                    if let tags = event.dietaryTags?.prefix(2) {
                        ForEach(Array(tags), id: \.self) { tag in
                            Text(tag)
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.herbGreen)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 4)
                                .background(Color.sautai.herbGreen.opacity(0.1))
                                .cornerRadius(SautaiDesign.cornerRadiusFull)
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

    private var statusBadge: some View {
        Group {
            if event.isClosed {
                Text("Closed")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sautai.slateTile)
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            } else if event.eventDate < Date() {
                Text("Past")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sautai.slateTile.opacity(0.6))
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            } else if event.isAvailable {
                Text("Open")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sautai.herbGreen)
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            } else {
                Text("Full")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.white)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sautai.warning)
                    .cornerRadius(SautaiDesign.cornerRadiusFull)
            }
        }
    }

    private func progressColor(current: Int, max: Int) -> Color {
        let ratio = Double(current) / Double(max)
        if ratio >= 1.0 { return .sautai.danger }
        if ratio >= 0.75 { return .sautai.warning }
        return .sautai.herbGreen
    }
}

#Preview {
    NavigationStack {
        MealEventsListView()
    }
}

//
//  MealPlanDetailView.swift
//  sautai_ios
//
//  Detailed view of a meal plan with days and items.
//

import SwiftUI

struct MealPlanDetailView: View {
    let planId: Int

    @Environment(\.dismiss) var dismiss
    @State private var plan: MealPlan?
    @State private var suggestions: [MealPlanSuggestion] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddDay = false
    @State private var showingGenerateAI = false
    @State private var selectedDay: MealPlanDay?

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let plan = plan {
                planContent(plan)
            } else if let error = error {
                errorView(error)
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle(plan?.displayTitle ?? "Meal Plan")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        showingGenerateAI = true
                    } label: {
                        Label("Generate with AI", systemImage: "wand.and.stars")
                    }

                    Button {
                        showingAddDay = true
                    } label: {
                        Label("Add Day", systemImage: "plus")
                    }

                    if plan?.status == .draft {
                        Button {
                            Task { await publishPlan() }
                        } label: {
                            Label("Publish Plan", systemImage: "paperplane.fill")
                        }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                }
            }
        }
        .sheet(isPresented: $showingAddDay) {
            if let plan = plan {
                AddPlanDayView(planId: plan.id) { newDay in
                    // Reload to get updated plan
                    Task { await loadPlan() }
                }
            }
        }
        .sheet(isPresented: $showingGenerateAI) {
            if let plan = plan {
                GenerateMealsView(planId: plan.id) {
                    Task { await loadPlan() }
                }
            }
        }
        .sheet(item: $selectedDay) { day in
            if let plan = plan {
                PlanDayDetailView(plan: plan, day: day) {
                    Task { await loadPlan() }
                }
            }
        }
        .refreshable {
            await loadPlan()
        }
        .task {
            await loadPlan()
        }
    }

    // MARK: - Plan Content

    @ViewBuilder
    private func planContent(_ plan: MealPlan) -> some View {
        VStack(spacing: SautaiDesign.spacingL) {
            // Header Card
            headerCard(plan)

            // Suggestions Section
            if !suggestions.isEmpty {
                suggestionsSection
            }

            // Days Section
            if let days = plan.days, !days.isEmpty {
                daysSection(days)
            } else {
                emptyDaysView
            }
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Header Card

    private func headerCard(_ plan: MealPlan) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            // Client & Status
            HStack {
                if let clientName = plan.clientName {
                    Label(clientName, systemImage: "person.fill")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)
                }

                Spacer()

                StatusBadge(status: plan.status)
            }

            Divider()

            // Date Range
            Label(plan.dateRange, systemImage: "calendar")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.8))

            // Progress
            if let totalMeals = plan.totalMeals, totalMeals > 0 {
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text("Progress")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                        Spacer()
                        Text("\(plan.completedMeals ?? 0) of \(totalMeals) meals")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile)
                    }
                    ProgressView(value: plan.progress)
                        .tint(.sautai.herbGreen)
                }
            }

            // Notes
            if let notes = plan.notes, !notes.isEmpty {
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

    // MARK: - Suggestions Section

    private var suggestionsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.sautai.sunlitApricot)
                Text("Pending Suggestions")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)
                Spacer()
                Text("\(suggestions.filter { $0.status == .pending }.count)")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.sunlitApricot)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sautai.sunlitApricot.opacity(0.15))
                    .cornerRadius(SautaiDesign.cornerRadiusS)
            }

            ForEach(suggestions.filter { $0.status == .pending }) { suggestion in
                SuggestionRowView(suggestion: suggestion) { response in
                    Task { await respondToSuggestion(suggestion, response: response) }
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Days Section

    private func daysSection(_ days: [MealPlanDay]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Schedule")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(days) { day in
                Button {
                    selectedDay = day
                } label: {
                    DayRowView(day: day)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Empty Days View

    private var emptyDaysView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "calendar.badge.plus")
                .font(.system(size: 48))
                .foregroundColor(.sautai.earthenClay.opacity(0.5))

            Text("No days added yet")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            HStack(spacing: SautaiDesign.spacingM) {
                Button {
                    showingAddDay = true
                } label: {
                    Label("Add Day", systemImage: "plus")
                }
                .buttonStyle(.bordered)

                Button {
                    showingGenerateAI = true
                } label: {
                    Label("Generate", systemImage: "wand.and.stars")
                }
                .buttonStyle(.borderedProminent)
                .tint(.sautai.earthenClay)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView()
                .scaleEffect(1.5)
            Spacer()
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    // MARK: - Error View

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load plan")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadPlan() }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    // MARK: - Actions

    private func loadPlan() async {
        isLoading = true
        error = nil

        do {
            plan = try await APIClient.shared.getMealPlanDetail(id: planId)
            suggestions = try await APIClient.shared.getMealPlanSuggestions(planId: planId)
        } catch {
            self.error = error
        }

        isLoading = false
    }

    private func publishPlan() async {
        do {
            plan = try await APIClient.shared.publishMealPlan(id: planId)
        } catch {
            self.error = error
        }
    }

    private func respondToSuggestion(_ suggestion: MealPlanSuggestion, response: SuggestionStatus) async {
        do {
            let request = SuggestionResponseRequest(status: response, responseNote: nil)
            _ = try await APIClient.shared.respondToSuggestion(suggestionId: suggestion.id, data: request)
            await loadPlan()
        } catch {
            self.error = error
        }
    }
}

// MARK: - Day Row View

struct DayRowView: View {
    let day: MealPlanDay

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            // Date header
            HStack {
                Text(day.displayDate)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.3))
            }

            // Items preview
            if let items = day.items, !items.isEmpty {
                ForEach(items.prefix(3)) { item in
                    HStack(spacing: SautaiDesign.spacingS) {
                        Image(systemName: item.mealType.icon)
                            .foregroundColor(.sautai.earthenClay)
                            .frame(width: 20)

                        Text(item.mealType.displayName)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                            .frame(width: 60, alignment: .leading)

                        Text(item.displayName)
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile)
                            .lineLimit(1)

                        Spacer()

                        if item.isCompleted {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.sautai.success)
                        }
                    }
                }

                if items.count > 3 {
                    Text("+\(items.count - 3) more")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            } else {
                Text("No meals planned")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                    .italic()
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }
}

// MARK: - Suggestion Row View

struct SuggestionRowView: View {
    let suggestion: MealPlanSuggestion
    let onRespond: (SuggestionStatus) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            HStack {
                if let mealType = suggestion.mealType {
                    Image(systemName: mealType.icon)
                        .foregroundColor(.sautai.earthenClay)
                }

                Text(suggestion.displaySuggestion)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Text("by \(suggestion.suggestedBy)")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }

            if let reason = suggestion.reason {
                Text(reason)
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
            }

            HStack(spacing: SautaiDesign.spacingM) {
                Button {
                    onRespond(.accepted)
                } label: {
                    Label("Accept", systemImage: "checkmark")
                        .font(SautaiFont.caption)
                }
                .buttonStyle(.borderedProminent)
                .tint(.sautai.success)

                Button {
                    onRespond(.rejected)
                } label: {
                    Label("Decline", systemImage: "xmark")
                        .font(SautaiFont.caption)
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.sunlitApricot.opacity(0.05))
        .cornerRadius(SautaiDesign.cornerRadiusS)
    }
}

#Preview {
    NavigationStack {
        MealPlanDetailView(planId: 1)
    }
}

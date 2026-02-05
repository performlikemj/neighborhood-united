//
//  MealPlansListView.swift
//  sautai_ios
//
//  List of collaborative meal plans.
//

import SwiftUI

struct MealPlansListView: View {
    @State private var plans: [MealPlan] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var selectedStatus: MealPlanStatus?
    @State private var showingCreatePlan = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Status Filter
                statusFilterBar

                // Content
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else if plans.isEmpty {
                    emptyStateView
                } else {
                    plansList
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Meal Plans")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingCreatePlan = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingCreatePlan) {
                CreateMealPlanView { newPlan in
                    plans.insert(newPlan, at: 0)
                }
            }
            .refreshable {
                await loadPlans()
            }
        }
        .task {
            await loadPlans()
        }
    }

    // MARK: - Status Filter Bar

    private var statusFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                FilterChip(title: "All", isSelected: selectedStatus == nil) {
                    selectedStatus = nil
                    Task { await loadPlans() }
                }

                ForEach(MealPlanStatus.allCases, id: \.self) { status in
                    FilterChip(title: status.displayName, isSelected: selectedStatus == status) {
                        selectedStatus = status
                        Task { await loadPlans() }
                    }
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.vertical, SautaiDesign.spacingS)
        }
        .background(Color.white)
    }

    // MARK: - Plans List

    private var plansList: some View {
        ScrollView {
            LazyVStack(spacing: SautaiDesign.spacingM) {
                ForEach(plans) { plan in
                    NavigationLink {
                        MealPlanDetailView(planId: plan.id)
                    } label: {
                        MealPlanRowView(plan: plan)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView()
                .scaleEffect(1.5)
            Spacer()
        }
    }

    // MARK: - Error View

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load meal plans")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button("Try Again") {
                Task { await loadPlans() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)

            Spacer()
        }
        .padding()
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Spacer()
            Image(systemName: "calendar.badge.plus")
                .font(.system(size: 64))
                .foregroundColor(.sautai.earthenClay.opacity(0.5))

            Text("No Meal Plans")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Create personalized meal plans for your clients")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingCreatePlan = true
            } label: {
                Label("Create Plan", systemImage: "plus")
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)

            Spacer()
        }
        .padding()
    }

    // MARK: - Load Plans

    private func loadPlans() async {
        isLoading = true
        error = nil

        do {
            let response = try await APIClient.shared.getMealPlans(status: selectedStatus)
            plans = response.results
        } catch {
            self.error = error
        }

        isLoading = false
    }
}

// MARK: - Meal Plan Row View

struct MealPlanRowView: View {
    let plan: MealPlan

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            // Header
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(plan.displayTitle)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)
                        .lineLimit(1)

                    if let clientName = plan.clientName {
                        Text(clientName)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                Spacer()

                StatusBadge(status: plan.status)
            }

            // Date Range
            Label(plan.dateRange, systemImage: "calendar")
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            // Progress
            if let totalMeals = plan.totalMeals, totalMeals > 0 {
                HStack {
                    ProgressView(value: plan.progress)
                        .tint(.sautai.herbGreen)

                    Text("\(plan.completedMeals ?? 0)/\(totalMeals) meals")
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            // Pending Suggestions
            if let pending = plan.pendingSuggestions, pending > 0 {
                HStack {
                    Image(systemName: "lightbulb.fill")
                        .foregroundColor(.sautai.sunlitApricot)
                    Text("\(pending) pending suggestion\(pending == 1 ? "" : "s")")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.sunlitApricot)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }
}

// MARK: - Status Badge

struct StatusBadge: View {
    let status: MealPlanStatus

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: status.icon)
                .font(.system(size: 10))
            Text(status.displayName)
                .font(SautaiFont.caption2)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(statusColor.opacity(0.15))
        .foregroundColor(statusColor)
        .cornerRadius(SautaiDesign.cornerRadiusS)
    }

    private var statusColor: Color {
        switch status.color {
        case "success": return .sautai.success
        case "warning": return .sautai.warning
        case "danger": return .sautai.danger
        case "info": return .sautai.info
        case "herbGreen": return .sautai.herbGreen
        default: return .sautai.slateTile
        }
    }
}

// MARK: - Filter Chip

struct FilterChip: View {
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(SautaiFont.caption)
                .padding(.horizontal, SautaiDesign.spacingM)
                .padding(.vertical, SautaiDesign.spacingS)
                .background(isSelected ? Color.sautai.earthenClay : Color.sautai.slateTile.opacity(0.1))
                .foregroundColor(isSelected ? .white : .sautai.slateTile)
                .cornerRadius(SautaiDesign.cornerRadiusS)
        }
    }
}

#Preview {
    MealPlansListView()
}

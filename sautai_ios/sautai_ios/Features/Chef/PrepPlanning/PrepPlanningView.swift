//
//  PrepPlanningView.swift
//  sautai_ios
//
//  Prep planning and shopping list management.
//

import SwiftUI

struct PrepPlanningView: View {
    @State private var prepPlans: [PrepPlan] = []
    @State private var commitments: [PrepPlanClient] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var selectedStatus: PrepPlanStatus?
    @State private var showingQuickGenerate = false

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
                } else {
                    contentView
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Prep Planning")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingQuickGenerate = true
                    } label: {
                        Image(systemName: "wand.and.stars")
                    }
                }
            }
            .sheet(isPresented: $showingQuickGenerate) {
                QuickGenerateView { newPlan in
                    prepPlans.insert(newPlan, at: 0)
                }
            }
            .refreshable {
                await loadData()
            }
        }
        .task {
            await loadData()
        }
    }

    // MARK: - Status Filter Bar

    private var statusFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                FilterChip(title: "All", isSelected: selectedStatus == nil) {
                    selectedStatus = nil
                    Task { await loadData() }
                }

                ForEach([PrepPlanStatus.active, .draft, .completed], id: \.self) { status in
                    FilterChip(title: status.displayName, isSelected: selectedStatus == status) {
                        selectedStatus = status
                        Task { await loadData() }
                    }
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.vertical, SautaiDesign.spacingS)
        }
        .background(Color.white)
    }

    // MARK: - Content View

    private var contentView: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                // Live Commitments
                if !commitments.isEmpty {
                    commitmentsSection
                }

                // Prep Plans
                if prepPlans.isEmpty {
                    emptyStateView
                } else {
                    prepPlansSection
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Commitments Section

    private var commitmentsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Image(systemName: "clock.badge.exclamationmark")
                    .foregroundColor(.sautai.warning)
                Text("Live Commitments")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Text("\(commitments.count)")
                    .font(SautaiFont.caption)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.sautai.warning.opacity(0.15))
                    .foregroundColor(.sautai.warning)
                    .cornerRadius(SautaiDesign.cornerRadiusS)
            }

            ForEach(commitments) { commitment in
                CommitmentRowView(commitment: commitment)
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Prep Plans Section

    private var prepPlansSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Prep Plans")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(prepPlans) { plan in
                NavigationLink {
                    PrepPlanDetailView(planId: plan.id)
                } label: {
                    PrepPlanRowView(plan: plan)
                }
                .buttonStyle(.plain)
            }
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

            Text("Failed to load prep plans")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button("Try Again") {
                Task { await loadData() }
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
            Image(systemName: "list.clipboard")
                .font(.system(size: 64))
                .foregroundColor(.sautai.earthenClay.opacity(0.5))

            Text("No Prep Plans")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Generate prep plans from your orders")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingQuickGenerate = true
            } label: {
                Label("Quick Generate", systemImage: "wand.and.stars")
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Load Data

    private func loadData() async {
        isLoading = true
        error = nil

        do {
            async let plansTask = APIClient.shared.getPrepPlans(status: selectedStatus)
            async let commitmentsTask = APIClient.shared.getLiveCommitments()

            let (plansResponse, commitmentsResult) = try await (plansTask, commitmentsTask)
            prepPlans = plansResponse.results
            commitments = commitmentsResult
        } catch {
            self.error = error
        }

        isLoading = false
    }
}

// MARK: - Prep Plan Row View

struct PrepPlanRowView: View {
    let plan: PrepPlan

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(plan.displayName)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    Text(plan.dateRange)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                Spacer()

                HStack(spacing: 4) {
                    Image(systemName: plan.status.icon)
                        .font(.system(size: 10))
                    Text(plan.status.displayName)
                        .font(SautaiFont.caption2)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(statusColor.opacity(0.15))
                .foregroundColor(statusColor)
                .cornerRadius(SautaiDesign.cornerRadiusS)
            }

            HStack(spacing: SautaiDesign.spacingM) {
                if let servings = plan.totalServings {
                    Label("\(servings) servings", systemImage: "person.2")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                if let prepTime = plan.estimatedPrepTime {
                    Label("\(prepTime) min", systemImage: "clock")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                if let clients = plan.clients {
                    Label("\(clients.count) client\(clients.count == 1 ? "" : "s")", systemImage: "person")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var statusColor: Color {
        switch plan.status {
        case .active: return .sautai.herbGreen
        case .draft: return .sautai.slateTile
        case .completed: return .sautai.success
        case .cancelled: return .sautai.danger
        }
    }
}

// MARK: - Commitment Row View

struct CommitmentRowView: View {
    let commitment: PrepPlanClient

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(commitment.clientName)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                HStack(spacing: SautaiDesign.spacingS) {
                    Text("\(commitment.servings) servings")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))

                    if let date = commitment.deliveryDate {
                        Text("•")
                        Text(date.formatted(date: .abbreviated, time: .omitted))
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }

                    if let time = commitment.deliveryTime {
                        Text(time)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.3))
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.warning.opacity(0.05))
        .cornerRadius(SautaiDesign.cornerRadiusS)
    }
}

#Preview {
    PrepPlanningView()
}

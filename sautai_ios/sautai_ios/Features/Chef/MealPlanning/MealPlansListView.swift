//
//  MealPlansListView.swift
//  sautai_ios
//
//  List of meal plans for chef users.
//

import SwiftUI

struct MealPlansListView: View {
    @State private var selectedTab = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Tab selector
                tabSelector

                // Content
                TabView(selection: $selectedTab) {
                    activePlansView
                        .tag(0)

                    archivedPlansView
                        .tag(1)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Meal Plans")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        // TODO: Create new plan
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }
        }
    }

    // MARK: - Tab Selector

    private var tabSelector: some View {
        HStack(spacing: 0) {
            tabButton(title: "Active", index: 0)
            tabButton(title: "Archived", index: 1)
        }
        .padding(SautaiDesign.spacingXS)
        .background(Color.white)
    }

    private func tabButton(title: String, index: Int) -> some View {
        Button {
            withAnimation(.sautaiQuick) {
                selectedTab = index
            }
        } label: {
            Text(title)
                .font(SautaiFont.buttonSmall)
                .foregroundColor(selectedTab == index ? .white : .sautai.slateTile)
                .frame(maxWidth: .infinity)
                .padding(.vertical, SautaiDesign.spacingS)
                .background(selectedTab == index ? Color.sautai.earthenClay : Color.clear)
                .cornerRadius(SautaiDesign.cornerRadiusS)
        }
    }

    // MARK: - Active Plans

    private var activePlansView: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingM) {
                // Placeholder cards
                ForEach(0..<3) { index in
                    mealPlanCard(
                        title: "Weekly Plan #\(index + 1)",
                        client: "Sample Client",
                        status: index == 0 ? "In Progress" : "Draft",
                        statusColor: index == 0 ? .sautai.herbGreen : .sautai.slateTile.opacity(0.5)
                    )
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Archived Plans

    private var archivedPlansView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Spacer()

            Image(systemName: "archivebox")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No archived plans")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Spacer()
        }
    }

    // MARK: - Meal Plan Card

    private func mealPlanCard(title: String, client: String, status: String, statusColor: Color) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            HStack {
                Text(title)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Text(status)
                    .font(SautaiFont.caption)
                    .foregroundColor(statusColor)
                    .padding(.horizontal, SautaiDesign.spacingS)
                    .padding(.vertical, SautaiDesign.spacingXS)
                    .background(statusColor.opacity(0.1))
                    .cornerRadius(SautaiDesign.cornerRadiusS)
            }

            HStack {
                Image(systemName: "person.fill")
                    .font(.system(size: 12))
                    .foregroundColor(.sautai.slateTile.opacity(0.5))

                Text(client)
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))

                Spacer()

                Text("7 days")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }

            // Day preview
            HStack(spacing: SautaiDesign.spacingXS) {
                ForEach(["M", "T", "W", "T", "F", "S", "S"], id: \.self) { day in
                    Text(day)
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                        .frame(width: 28, height: 28)
                        .background(Color.sautai.softCream)
                        .cornerRadius(SautaiDesign.cornerRadiusXS)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }
}

// MARK: - Preview

#Preview {
    MealPlansListView()
}

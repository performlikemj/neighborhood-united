//
//  ShoppingListView.swift
//  sautai_ios
//
//  Interactive shopping list with checkboxes.
//

import SwiftUI

struct ShoppingListView: View {
    let shoppingList: ShoppingList
    let planId: Int
    let onUpdate: (ShoppingList) -> Void

    @State private var items: [ShoppingListItem]
    @State private var isMarkingAll = false

    init(shoppingList: ShoppingList, planId: Int, onUpdate: @escaping (ShoppingList) -> Void) {
        self.shoppingList = shoppingList
        self.planId = planId
        self.onUpdate = onUpdate
        _items = State(initialValue: shoppingList.items)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                // Progress Header
                progressHeader

                // Shopping Items
                itemsSection

                // Mark All Button
                if items.contains(where: { !$0.isPurchased }) {
                    markAllButton
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Progress Header

    private var progressHeader: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Progress Ring
            ZStack {
                Circle()
                    .stroke(Color.sautai.slateTile.opacity(0.1), lineWidth: 8)

                Circle()
                    .trim(from: 0, to: progress)
                    .stroke(Color.sautai.herbGreen, style: StrokeStyle(lineWidth: 8, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                    .animation(.easeInOut, value: progress)

                VStack(spacing: 2) {
                    Text("\(purchasedCount)")
                        .font(SautaiFont.title)
                        .foregroundColor(.sautai.slateTile)
                    Text("of \(items.count)")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }
            .frame(width: 100, height: 100)

            // Stats Row
            HStack(spacing: SautaiDesign.spacingL) {
                VStack {
                    Text("\(items.count)")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)
                    Text("Total Items")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }

                if let cost = shoppingList.estimatedCost {
                    VStack {
                        Text(cost)
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.herbGreen)
                        Text("Est. Cost")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                VStack {
                    Text("\(remainingCount)")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.warning)
                    Text("Remaining")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Items Section

    private var itemsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            // Group by category
            let grouped = Dictionary(grouping: items) { $0.category ?? "Other" }
            let sortedCategories = grouped.keys.sorted()

            ForEach(sortedCategories, id: \.self) { category in
                if let categoryItems = grouped[category] {
                    categorySection(category: category, items: categoryItems)
                }
            }
        }
    }

    private func categorySection(category: String, items: [ShoppingListItem]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            // Category Header
            HStack {
                Text(category)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                let purchased = items.filter { $0.isPurchased }.count
                Text("\(purchased)/\(items.count)")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
            }

            // Items
            ForEach(items) { item in
                ShoppingItemRow(item: item) {
                    toggleItem(item)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Mark All Button

    private var markAllButton: some View {
        Button {
            markAllPurchased()
        } label: {
            HStack {
                if isMarkingAll {
                    ProgressView()
                        .tint(.white)
                } else {
                    Image(systemName: "checkmark.circle.fill")
                }
                Text("Mark All Purchased")
            }
            .frame(maxWidth: .infinity)
        }
        .buttonStyle(.borderedProminent)
        .tint(.sautai.herbGreen)
        .disabled(isMarkingAll)
    }

    // MARK: - Computed Properties

    private var purchasedCount: Int {
        items.filter { $0.isPurchased }.count
    }

    private var remainingCount: Int {
        items.count - purchasedCount
    }

    private var progress: Double {
        guard !items.isEmpty else { return 0 }
        return Double(purchasedCount) / Double(items.count)
    }

    // MARK: - Actions

    private func toggleItem(_ item: ShoppingListItem) {
        guard let index = items.firstIndex(where: { $0.id == item.id }) else { return }

        let newPurchased = !item.isPurchased
        items[index].isPurchased = newPurchased

        Task {
            do {
                _ = try await APIClient.shared.markItemPurchased(
                    prepPlanId: planId,
                    itemId: item.id,
                    purchased: newPurchased
                )
            } catch {
                // Revert on error
                await MainActor.run {
                    items[index].isPurchased = !newPurchased
                }
            }
        }
    }

    private func markAllPurchased() {
        isMarkingAll = true

        // Optimistically update UI
        for index in items.indices {
            items[index].isPurchased = true
        }

        Task {
            do {
                try await APIClient.shared.markAllPurchased(prepPlanId: planId)
            } catch {
                // Reload on error
                if let newList = try? await APIClient.shared.getShoppingList(prepPlanId: planId) {
                    await MainActor.run {
                        items = newList.items
                    }
                }
            }

            await MainActor.run {
                isMarkingAll = false
            }
        }
    }
}

// MARK: - Shopping Item Row

struct ShoppingItemRow: View {
    let item: ShoppingListItem
    let onToggle: () -> Void

    var body: some View {
        Button(action: onToggle) {
            HStack(spacing: SautaiDesign.spacingM) {
                // Checkbox
                Image(systemName: item.isPurchased ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 24))
                    .foregroundColor(item.isPurchased ? .sautai.success : .sautai.slateTile.opacity(0.3))

                // Item Details
                VStack(alignment: .leading, spacing: 2) {
                    Text(item.name)
                        .font(SautaiFont.body)
                        .foregroundColor(item.isPurchased ? .sautai.slateTile.opacity(0.5) : .sautai.slateTile)
                        .strikethrough(item.isPurchased)

                    HStack(spacing: SautaiDesign.spacingS) {
                        Text(item.displayQuantity)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.earthenClay)

                        if let notes = item.notes, !notes.isEmpty {
                            Text("• \(notes)")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.6))
                                .lineLimit(1)
                        }
                    }
                }

                Spacer()

                // Price
                if let price = item.estimatedPrice {
                    Text(price)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }

                // Shelf Life Warning
                if let shelfLife = item.shelfLife, shelfLife <= 3 {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.caption)
                        .foregroundColor(.sautai.warning)
                }
            }
            .padding(SautaiDesign.spacingM)
            .background(item.isPurchased ? Color.sautai.success.opacity(0.05) : Color.sautai.softCream)
            .cornerRadius(SautaiDesign.cornerRadiusS)
        }
        .buttonStyle(.plain)
    }
}

#Preview {
    ShoppingListView(
        shoppingList: ShoppingList(
            id: 1,
            planId: 1,
            items: [
                ShoppingListItem(id: 1, name: "Chicken Breast", quantity: "2", unit: "lbs", category: "Meat", estimatedPrice: "$12.99", isPurchased: false, notes: "Organic preferred", shelfLife: 3, storageInstructions: nil),
                ShoppingListItem(id: 2, name: "Brown Rice", quantity: "1", unit: "bag", category: "Grains", estimatedPrice: "$4.99", isPurchased: true, notes: nil, shelfLife: nil, storageInstructions: nil),
                ShoppingListItem(id: 3, name: "Broccoli", quantity: "2", unit: "heads", category: "Vegetables", estimatedPrice: "$3.99", isPurchased: false, notes: nil, shelfLife: 5, storageInstructions: nil)
            ],
            totalItems: 3,
            purchasedCount: 1,
            estimatedCost: "$21.97",
            generatedAt: Date()
        ),
        planId: 1,
        onUpdate: { _ in }
    )
}

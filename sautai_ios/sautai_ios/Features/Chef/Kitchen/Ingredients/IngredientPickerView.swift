//
//  IngredientPickerView.swift
//  sautai_ios
//
//  Reusable ingredient picker for use in dish creation.
//

import SwiftUI

struct IngredientPickerView: View {
    @Environment(\.dismiss) var dismiss
    @Binding var selectedIngredients: [DishIngredientInput]
    let existingIngredientIds: Set<Int>

    @State private var ingredients: [Ingredient] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var showingAddNew = false
    @State private var pendingSelections: [Int: DishIngredientInput] = [:]

    var filteredIngredients: [Ingredient] {
        if searchText.isEmpty {
            return ingredients
        }
        return ingredients.filter { $0.name.localizedCaseInsensitiveContains(searchText) }
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Search bar
                searchBar

                // Ingredients list
                if isLoading {
                    loadingView
                } else if filteredIngredients.isEmpty {
                    emptyView
                } else {
                    ingredientsList
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Add Ingredients")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add \(pendingSelections.count)") {
                        addSelectedIngredients()
                    }
                    .disabled(pendingSelections.isEmpty)
                }
            }
            .sheet(isPresented: $showingAddNew) {
                AddIngredientView { newIngredient in
                    ingredients.insert(newIngredient, at: 0)
                    // Auto-select the new ingredient
                    pendingSelections[newIngredient.id] = DishIngredientInput(
                        ingredientId: newIngredient.id,
                        quantity: nil,
                        unit: newIngredient.unit,
                        notes: nil
                    )
                }
            }
        }
        .task {
            await loadIngredients()
        }
    }

    // MARK: - Search Bar

    private var searchBar: some View {
        HStack(spacing: SautaiDesign.spacingS) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            TextField("Search ingredients...", text: $searchText)
                .font(SautaiFont.body)

            if !searchText.isEmpty {
                Button {
                    searchText = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }

            Divider()
                .frame(height: 24)

            Button {
                showingAddNew = true
            } label: {
                Image(systemName: "plus.circle.fill")
                    .foregroundColor(.sautai.herbGreen)
            }
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.white)
    }

    // MARK: - Ingredients List

    private var ingredientsList: some View {
        List {
            ForEach(filteredIngredients) { ingredient in
                let isAlreadyAdded = existingIngredientIds.contains(ingredient.id)
                let isSelected = pendingSelections[ingredient.id] != nil

                Button {
                    toggleSelection(ingredient)
                } label: {
                    HStack(spacing: SautaiDesign.spacingM) {
                        // Selection indicator
                        Image(systemName: isSelected ? "checkmark.circle.fill" : isAlreadyAdded ? "checkmark.circle" : "circle")
                            .font(.system(size: 22))
                            .foregroundColor(isSelected ? .sautai.herbGreen : isAlreadyAdded ? .sautai.slateTile.opacity(0.3) : .sautai.slateTile.opacity(0.3))

                        // Info
                        VStack(alignment: .leading, spacing: 2) {
                            Text(ingredient.name)
                                .font(SautaiFont.body)
                                .foregroundColor(isAlreadyAdded && !isSelected ? .sautai.slateTile.opacity(0.5) : .sautai.slateTile)

                            HStack(spacing: SautaiDesign.spacingS) {
                                Text(ingredient.categoryDisplay)
                                    .font(SautaiFont.caption2)
                                    .foregroundColor(.sautai.slateTile.opacity(0.6))

                                if let unit = ingredient.unit {
                                    Text("•")
                                        .foregroundColor(.sautai.slateTile.opacity(0.3))
                                    Text(unit)
                                        .font(SautaiFont.caption2)
                                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                                }
                            }
                        }

                        Spacer()

                        if isAlreadyAdded && !isSelected {
                            Text("Added")
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.slateTile.opacity(0.5))
                        }
                    }
                }
                .disabled(isAlreadyAdded && !isSelected)
                .listRowBackground(Color.white)
                .listRowSeparator(.hidden)
            }
        }
        .listStyle(.plain)
    }

    private func toggleSelection(_ ingredient: Ingredient) {
        if pendingSelections[ingredient.id] != nil {
            pendingSelections.removeValue(forKey: ingredient.id)
        } else {
            pendingSelections[ingredient.id] = DishIngredientInput(
                ingredientId: ingredient.id,
                quantity: nil,
                unit: ingredient.unit,
                notes: nil
            )
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading ingredients...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "carrot")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text(searchText.isEmpty ? "No ingredients yet" : "No matches found")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Create an ingredient to get started.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddNew = true
            } label: {
                Label("Add Ingredient", systemImage: "plus")
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingXL)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .background(Color.sautai.herbGreen)
                    .cornerRadius(SautaiDesign.cornerRadius)
            }
        }
        .padding(SautaiDesign.spacingXL)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Actions

    private func addSelectedIngredients() {
        selectedIngredients.append(contentsOf: pendingSelections.values)
        dismiss()
    }

    private func loadIngredients() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getIngredients()
            ingredients = response.results
        } catch {
            // Handle error
        }
        isLoading = false
    }
}

#Preview {
    IngredientPickerView(
        selectedIngredients: .constant([]),
        existingIngredientIds: []
    )
}

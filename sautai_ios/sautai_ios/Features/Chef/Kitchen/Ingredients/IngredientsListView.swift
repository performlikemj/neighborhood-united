//
//  IngredientsListView.swift
//  sautai_ios
//
//  List of chef's ingredients with search and add functionality.
//

import SwiftUI

struct IngredientsListView: View {
    @State private var ingredients: [Ingredient] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddSheet = false
    @State private var selectedCategory: IngredientCategory? = nil

    var filteredIngredients: [Ingredient] {
        var filtered = ingredients

        if let category = selectedCategory {
            filtered = filtered.filter { $0.category?.lowercased() == category.rawValue }
        }

        if !searchText.isEmpty {
            filtered = filtered.filter { ingredient in
                ingredient.name.localizedCaseInsensitiveContains(searchText)
            }
        }

        return filtered.sorted { $0.name < $1.name }
    }

    var groupedIngredients: [(String, [Ingredient])] {
        let grouped = Dictionary(grouping: filteredIngredients) { ingredient in
            ingredient.category?.capitalized ?? "Other"
        }
        return grouped.sorted { $0.key < $1.key }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Search and filter bar
            searchBar

            // Category filter
            categoryFilter

            // Ingredients list
            Group {
                if isLoading {
                    loadingView
                } else if filteredIngredients.isEmpty {
                    emptyView
                } else {
                    ingredientsList
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
            AddIngredientView { newIngredient in
                ingredients.insert(newIngredient, at: 0)
            }
        }
        .refreshable {
            await loadIngredients()
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
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.softCream)
        .cornerRadius(SautaiDesign.cornerRadius)
        .padding(.horizontal, SautaiDesign.spacing)
        .padding(.vertical, SautaiDesign.spacingS)
    }

    // MARK: - Category Filter

    private var categoryFilter: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                filterChip(category: nil, label: "All")

                ForEach(IngredientCategory.allCases, id: \.self) { category in
                    filterChip(category: category, label: category.displayName)
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.bottom, SautaiDesign.spacingS)
        }
    }

    private func filterChip(category: IngredientCategory?, label: String) -> some View {
        let isSelected = selectedCategory == category

        return Button {
            withAnimation(.sautaiQuick) {
                selectedCategory = category
            }
        } label: {
            HStack(spacing: SautaiDesign.spacingXS) {
                if let cat = category {
                    Image(systemName: cat.icon)
                        .font(.system(size: 12))
                }
                Text(label)
                    .font(SautaiFont.caption)
            }
            .foregroundColor(isSelected ? .white : .sautai.slateTile)
            .padding(.horizontal, SautaiDesign.spacingM)
            .padding(.vertical, SautaiDesign.spacingXS)
            .background(isSelected ? Color.sautai.herbGreen : Color.white)
            .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }

    // MARK: - Ingredients List

    private var ingredientsList: some View {
        List {
            ForEach(groupedIngredients, id: \.0) { category, items in
                Section {
                    ForEach(items) { ingredient in
                        ingredientRow(ingredient)
                            .listRowBackground(Color.white)
                            .listRowSeparator(.hidden)
                    }
                    .onDelete { indexSet in
                        deleteIngredients(at: indexSet, in: items)
                    }
                } header: {
                    Text(category)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                        .textCase(nil)
                }
            }
        }
        .listStyle(.plain)
    }

    private func ingredientRow(_ ingredient: Ingredient) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Category icon
            Image(systemName: categoryIcon(for: ingredient.category))
                .font(.system(size: 16))
                .foregroundColor(.sautai.herbGreen)
                .frame(width: 32, height: 32)
                .background(Color.sautai.herbGreen.opacity(0.1))
                .cornerRadius(SautaiDesign.cornerRadiusS)

            // Info
            VStack(alignment: .leading, spacing: 2) {
                Text(ingredient.name)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                HStack(spacing: SautaiDesign.spacingS) {
                    if let unit = ingredient.unit {
                        Text(unit)
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }

                    if ingredient.isCustom {
                        Text("Custom")
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.earthenClay)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.sautai.earthenClay.opacity(0.1))
                            .cornerRadius(SautaiDesign.cornerRadiusXS)
                    }
                }
            }

            Spacer()
        }
        .padding(SautaiDesign.spacingM)
    }

    private func categoryIcon(for category: String?) -> String {
        guard let cat = category?.lowercased(),
              let ingredientCat = IngredientCategory(rawValue: cat) else {
            return "archivebox"
        }
        return ingredientCat.icon
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
            Image(systemName: searchText.isEmpty ? "carrot" : "magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text(searchText.isEmpty ? "No ingredients yet" : "No matches found")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(searchText.isEmpty
                ? "Add ingredients you commonly use to easily build dishes and shopping lists."
                : "Try a different search term or clear filters.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            if searchText.isEmpty {
                Button {
                    showingAddSheet = true
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
        }
        .padding(SautaiDesign.spacingXL)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Data Loading

    private func loadIngredients() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getIngredients()
            ingredients = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteIngredients(at offsets: IndexSet, in items: [Ingredient]) {
        for index in offsets {
            let ingredient = items[index]
            Task {
                do {
                    try await APIClient.shared.deleteIngredient(id: ingredient.id)
                    await MainActor.run {
                        ingredients.removeAll { $0.id == ingredient.id }
                    }
                } catch {
                    // Handle error
                }
            }
        }
    }
}

#Preview {
    NavigationStack {
        IngredientsListView()
    }
}

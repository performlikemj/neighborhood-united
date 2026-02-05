//
//  DishesListView.swift
//  sautai_ios
//
//  List of chef's dishes with search and management.
//

import SwiftUI

struct DishesListView: View {
    @State private var dishes: [Dish] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddSheet = false

    var filteredDishes: [Dish] {
        if searchText.isEmpty {
            return dishes
        }
        return dishes.filter { dish in
            dish.name.localizedCaseInsensitiveContains(searchText) ||
            (dish.cuisineType?.localizedCaseInsensitiveContains(searchText) ?? false)
        }
    }

    var body: some View {
        Group {
            if isLoading {
                loadingView
            } else if dishes.isEmpty {
                emptyView
            } else {
                dishesList
            }
        }
        .searchable(text: $searchText, prompt: "Search dishes")
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
            AddDishView { newDish in
                dishes.insert(newDish, at: 0)
            }
        }
        .refreshable {
            await loadDishes()
        }
        .task {
            await loadDishes()
        }
    }

    // MARK: - Dishes List

    private var dishesList: some View {
        List {
            ForEach(filteredDishes) { dish in
                NavigationLink {
                    DishDetailView(dishId: dish.id)
                } label: {
                    DishRowView(dish: dish)
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
            .onDelete(perform: deleteDishes)
        }
        .listStyle(.plain)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading dishes...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "fork.knife")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text("No dishes yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Create your signature dishes to use in meals and events.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddSheet = true
            } label: {
                Label("Create Dish", systemImage: "plus")
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

    private func loadDishes() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getDishes()
            dishes = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteDishes(at offsets: IndexSet) {
        for index in offsets {
            let dish = filteredDishes[index]
            Task {
                do {
                    try await APIClient.shared.deleteDish(id: dish.id)
                    await MainActor.run {
                        dishes.removeAll { $0.id == dish.id }
                    }
                } catch {
                    // Handle error
                }
            }
        }
    }
}

// MARK: - Dish Row View

struct DishRowView: View {
    let dish: Dish

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Image or placeholder
            if let imageUrl = dish.imageUrl, let url = URL(string: imageUrl) {
                AsyncImage(url: url) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    dishPlaceholder
                }
                .frame(width: 64, height: 64)
                .cornerRadius(SautaiDesign.cornerRadiusM)
            } else {
                dishPlaceholder
            }

            // Info
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                HStack {
                    Text(dish.name)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if !dish.isActive {
                        Text("Inactive")
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.warning)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.sautai.warningBackground)
                            .cornerRadius(SautaiDesign.cornerRadiusXS)
                    }
                }

                HStack(spacing: SautaiDesign.spacingS) {
                    if let cuisine = dish.cuisineType {
                        Label(cuisine, systemImage: "globe")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }

                    if let time = dish.totalTimeDisplay {
                        Label(time, systemImage: "clock")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let tags = dish.dietaryTags, !tags.isEmpty {
                    HStack(spacing: SautaiDesign.spacingXS) {
                        ForEach(tags.prefix(3), id: \.self) { tag in
                            Text(tag)
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.herbGreen)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.sautai.herbGreen.opacity(0.1))
                                .cornerRadius(SautaiDesign.cornerRadiusXS)
                        }
                        if tags.count > 3 {
                            Text("+\(tags.count - 3)")
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.slateTile.opacity(0.5))
                        }
                    }
                }
            }

            Spacer()

            // Ingredient count
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(dish.ingredientCount)")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.earthenClay)
                Text("ingredients")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var dishPlaceholder: some View {
        Rectangle()
            .fill(Color.sautai.earthenClay.opacity(0.1))
            .frame(width: 64, height: 64)
            .cornerRadius(SautaiDesign.cornerRadiusM)
            .overlay(
                Image(systemName: "fork.knife")
                    .font(.system(size: 24))
                    .foregroundColor(.sautai.earthenClay.opacity(0.5))
            )
    }
}

#Preview {
    NavigationStack {
        DishesListView()
    }
}

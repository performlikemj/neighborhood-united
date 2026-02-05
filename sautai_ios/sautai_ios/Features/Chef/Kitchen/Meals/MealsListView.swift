//
//  MealsListView.swift
//  sautai_ios
//
//  List of chef's meals (composed of dishes).
//

import SwiftUI

struct MealsListView: View {
    @State private var meals: [Meal] = []
    @State private var searchText = ""
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddSheet = false

    var filteredMeals: [Meal] {
        if searchText.isEmpty {
            return meals
        }
        return meals.filter { meal in
            meal.name.localizedCaseInsensitiveContains(searchText) ||
            (meal.cuisineType?.localizedCaseInsensitiveContains(searchText) ?? false)
        }
    }

    var body: some View {
        Group {
            if isLoading {
                loadingView
            } else if meals.isEmpty {
                emptyView
            } else {
                mealsList
            }
        }
        .searchable(text: $searchText, prompt: "Search meals")
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
            AddMealView { newMeal in
                meals.insert(newMeal, at: 0)
            }
        }
        .refreshable {
            await loadMeals()
        }
        .task {
            await loadMeals()
        }
    }

    // MARK: - Meals List

    private var mealsList: some View {
        List {
            ForEach(filteredMeals) { meal in
                NavigationLink {
                    MealDetailView(mealId: meal.id)
                } label: {
                    MealRowView(meal: meal)
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
            .onDelete(perform: deleteMeals)
        }
        .listStyle(.plain)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading meals...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "takeoutbag.and.cup.and.straw")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.5))

            Text("No meals yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Combine your dishes into meals for meal events and client orders.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddSheet = true
            } label: {
                Label("Create Meal", systemImage: "plus")
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

    private func loadMeals() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getChefMeals()
            meals = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteMeals(at offsets: IndexSet) {
        for index in offsets {
            let meal = filteredMeals[index]
            Task {
                do {
                    try await APIClient.shared.deleteMeal(id: meal.id)
                    await MainActor.run {
                        meals.removeAll { $0.id == meal.id }
                    }
                } catch {
                    // Handle error
                }
            }
        }
    }
}

// MARK: - Meal Row View

struct MealRowView: View {
    let meal: Meal

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Image or placeholder
            if let imageUrl = meal.imageUrl, let url = URL(string: imageUrl) {
                AsyncImage(url: url) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    mealPlaceholder
                }
                .frame(width: 64, height: 64)
                .cornerRadius(SautaiDesign.cornerRadiusM)
            } else {
                mealPlaceholder
            }

            // Info
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                HStack {
                    Text(meal.name)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if !meal.isActive {
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
                    if let cuisine = meal.cuisineType {
                        Label(cuisine, systemImage: "globe")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }

                    if let time = meal.prepTimeDisplay {
                        Label(time, systemImage: "clock")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let tags = meal.dietaryTags, !tags.isEmpty {
                    HStack(spacing: SautaiDesign.spacingXS) {
                        ForEach(tags.prefix(2), id: \.self) { tag in
                            Text(tag)
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.herbGreen)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.sautai.herbGreen.opacity(0.1))
                                .cornerRadius(SautaiDesign.cornerRadiusXS)
                        }
                        if tags.count > 2 {
                            Text("+\(tags.count - 2)")
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.slateTile.opacity(0.5))
                        }
                    }
                }
            }

            Spacer()

            // Dish count
            VStack(alignment: .trailing, spacing: 2) {
                Text("\(meal.dishCount)")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.earthenClay)
                Text("dishes")
                    .font(SautaiFont.caption2)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var mealPlaceholder: some View {
        Rectangle()
            .fill(Color.sautai.sunlitApricot.opacity(0.2))
            .frame(width: 64, height: 64)
            .cornerRadius(SautaiDesign.cornerRadiusM)
            .overlay(
                Image(systemName: "takeoutbag.and.cup.and.straw")
                    .font(.system(size: 24))
                    .foregroundColor(.sautai.sunlitApricot.opacity(0.7))
            )
    }
}

#Preview {
    NavigationStack {
        MealsListView()
    }
}

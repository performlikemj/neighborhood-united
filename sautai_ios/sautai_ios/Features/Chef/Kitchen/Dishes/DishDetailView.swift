//
//  DishDetailView.swift
//  sautai_ios
//
//  Detailed view of a dish with ingredients and editing.
//

import SwiftUI

struct DishDetailView: View {
    let dishId: Int

    @Environment(\.dismiss) var dismiss
    @State private var dish: Dish?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingEditSheet = false
    @State private var showingDeleteAlert = false

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let dish = dish {
                dishContent(dish)
            } else {
                errorView
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle(dish?.name ?? "Dish")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        showingEditSheet = true
                    } label: {
                        Label("Edit", systemImage: "pencil")
                    }

                    Divider()

                    Button(role: .destructive) {
                        showingDeleteAlert = true
                    } label: {
                        Label("Delete", systemImage: "trash")
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .sheet(isPresented: $showingEditSheet) {
            if let dish = dish {
                EditDishView(dish: dish) { updatedDish in
                    self.dish = updatedDish
                }
            }
        }
        .alert("Delete Dish", isPresented: $showingDeleteAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) {
                deleteDish()
            }
        } message: {
            Text("Are you sure you want to delete this dish? This cannot be undone.")
        }
        .refreshable {
            await loadDish()
        }
        .task {
            await loadDish()
        }
    }

    // MARK: - Dish Content

    @ViewBuilder
    private func dishContent(_ dish: Dish) -> some View {
        VStack(spacing: SautaiDesign.spacingL) {
            // Header with image
            headerSection(dish)

            // Quick stats
            statsRow(dish)

            // Description
            if let description = dish.description, !description.isEmpty {
                descriptionSection(description)
            }

            // Ingredients
            ingredientsSection(dish)

            // Tags
            if let tags = dish.dietaryTags, !tags.isEmpty {
                tagsSection(tags)
            }

            // Metadata
            metadataSection(dish)
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Header Section

    private func headerSection(_ dish: Dish) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            if let imageUrl = dish.imageUrl, let url = URL(string: imageUrl) {
                AsyncImage(url: url) { image in
                    image
                        .resizable()
                        .aspectRatio(contentMode: .fill)
                } placeholder: {
                    imagePlaceholder
                }
                .frame(height: 200)
                .cornerRadius(SautaiDesign.cornerRadius)
                .clipped()
            } else {
                imagePlaceholder
            }

            HStack {
                Text(dish.name)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if !dish.isActive {
                    Text("Inactive")
                        .font(SautaiFont.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingXS)
                        .background(Color.sautai.warning)
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }

            if let cuisine = dish.cuisineType {
                HStack {
                    Image(systemName: "globe")
                        .foregroundColor(.sautai.earthenClay)
                    Text(cuisine)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)
                    Spacer()
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private var imagePlaceholder: some View {
        Rectangle()
            .fill(Color.sautai.earthenClay.opacity(0.1))
            .frame(height: 200)
            .cornerRadius(SautaiDesign.cornerRadius)
            .overlay(
                Image(systemName: "fork.knife")
                    .font(.system(size: 48))
                    .foregroundColor(.sautai.earthenClay.opacity(0.3))
            )
    }

    // MARK: - Stats Row

    private func statsRow(_ dish: Dish) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            if let prepTime = dish.prepTimeMinutes {
                statItem(value: "\(prepTime)m", label: "Prep", icon: "timer")
            }

            if let cookTime = dish.cookTimeMinutes {
                statItem(value: "\(cookTime)m", label: "Cook", icon: "flame")
            }

            if let servings = dish.servings {
                statItem(value: "\(servings)", label: "Servings", icon: "person.2")
            }

            if let calories = dish.caloriesDisplay {
                statItem(value: calories, label: "Per Serving", icon: "bolt")
            }
        }
    }

    private func statItem(value: String, label: String, icon: String) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(.sautai.earthenClay)

            Text(value)
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(label)
                .font(SautaiFont.caption2)
                .foregroundColor(.sautai.slateTile.opacity(0.6))
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Description Section

    private func descriptionSection(_ description: String) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text("Description")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(description)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.8))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Ingredients Section

    private func ingredientsSection(_ dish: Dish) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Ingredients")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Text("\(dish.ingredientCount)")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.earthenClay)
            }

            if let ingredients = dish.ingredients, !ingredients.isEmpty {
                VStack(spacing: 0) {
                    ForEach(ingredients) { ingredient in
                        ingredientRow(ingredient)
                        if ingredient.id != ingredients.last?.id {
                            Divider()
                                .padding(.horizontal, SautaiDesign.spacing)
                        }
                    }
                }
                .background(Color.sautai.softCream)
                .cornerRadius(SautaiDesign.cornerRadiusM)
            } else {
                Text("No ingredients added yet")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func ingredientRow(_ ingredient: DishIngredient) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            Circle()
                .fill(Color.sautai.herbGreen.opacity(0.2))
                .frame(width: 8, height: 8)

            Text(ingredient.ingredientName)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)

            Spacer()

            Text(ingredient.displayQuantity)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .padding(SautaiDesign.spacingM)
    }

    // MARK: - Tags Section

    private func tagsSection(_ tags: [String]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text("Dietary Info")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            FlowLayout(spacing: SautaiDesign.spacingS) {
                ForEach(tags, id: \.self) { tag in
                    Text(tag)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.herbGreen)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingXS)
                        .background(Color.sautai.herbGreen.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Metadata Section

    private func metadataSection(_ dish: Dish) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            if let createdAt = dish.createdAt {
                HStack {
                    Text("Created")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                    Spacer()
                    Text(createdAt.formatted(date: .abbreviated, time: .omitted))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            if let updatedAt = dish.updatedAt {
                HStack {
                    Text("Last Updated")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                    Spacer()
                    Text(updatedAt.formatted(date: .abbreviated, time: .omitted))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Loading/Error Views

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading dish...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.top, 100)
    }

    private var errorView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Could not load dish")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Button {
                Task { await loadDish() }
            } label: {
                Text("Try Again")
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacingXL)
    }

    // MARK: - Data Loading

    private func loadDish() async {
        isLoading = true
        error = nil
        do {
            dish = try await APIClient.shared.getDishDetail(id: dishId)
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteDish() {
        Task {
            do {
                try await APIClient.shared.deleteDish(id: dishId)
                await MainActor.run {
                    dismiss()
                }
            } catch {
                // Handle error
            }
        }
    }
}

#Preview {
    NavigationStack {
        DishDetailView(dishId: 1)
    }
}

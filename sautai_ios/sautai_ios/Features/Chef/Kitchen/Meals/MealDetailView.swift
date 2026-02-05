//
//  MealDetailView.swift
//  sautai_ios
//
//  Detailed view of a meal with its dishes.
//

import SwiftUI

struct MealDetailView: View {
    let mealId: Int

    @Environment(\.dismiss) var dismiss
    @State private var meal: Meal?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingEditSheet = false
    @State private var showingDeleteAlert = false

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let meal = meal {
                mealContent(meal)
            } else {
                errorView
            }
        }
        .background(Color.sautai.softCream)
        .navigationTitle(meal?.name ?? "Meal")
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
            if let meal = meal {
                AddMealView(editingMeal: meal) { updatedMeal in
                    self.meal = updatedMeal
                }
            }
        }
        .alert("Delete Meal", isPresented: $showingDeleteAlert) {
            Button("Cancel", role: .cancel) {}
            Button("Delete", role: .destructive) {
                deleteMeal()
            }
        } message: {
            Text("Are you sure you want to delete this meal? This cannot be undone.")
        }
        .refreshable {
            await loadMeal()
        }
        .task {
            await loadMeal()
        }
    }

    // MARK: - Meal Content

    @ViewBuilder
    private func mealContent(_ meal: Meal) -> some View {
        VStack(spacing: SautaiDesign.spacingL) {
            // Header
            headerSection(meal)

            // Quick stats
            statsRow(meal)

            // Description
            if let description = meal.description, !description.isEmpty {
                descriptionSection(description)
            }

            // Dishes
            dishesSection(meal)

            // Tags
            if let tags = meal.dietaryTags, !tags.isEmpty {
                tagsSection(tags)
            }

            // Create Event Button
            createEventButton(meal)

            // Metadata
            metadataSection(meal)
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Header Section

    private func headerSection(_ meal: Meal) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            if let imageUrl = meal.imageUrl, let url = URL(string: imageUrl) {
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
                Text(meal.name)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if !meal.isActive {
                    Text("Inactive")
                        .font(SautaiFont.caption)
                        .foregroundColor(.white)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingXS)
                        .background(Color.sautai.warning)
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }

            if let cuisine = meal.cuisineType {
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
            .fill(Color.sautai.sunlitApricot.opacity(0.2))
            .frame(height: 200)
            .cornerRadius(SautaiDesign.cornerRadius)
            .overlay(
                Image(systemName: "takeoutbag.and.cup.and.straw")
                    .font(.system(size: 48))
                    .foregroundColor(.sautai.sunlitApricot.opacity(0.5))
            )
    }

    // MARK: - Stats Row

    private func statsRow(_ meal: Meal) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            statItem(value: "\(meal.dishCount)", label: "Dishes", icon: "fork.knife")

            if let prepTime = meal.prepTimeDisplay {
                statItem(value: prepTime, label: "Total Time", icon: "clock")
            }

            if let servings = meal.servings {
                statItem(value: "\(servings)", label: "Servings", icon: "person.2")
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

    // MARK: - Dishes Section

    private func dishesSection(_ meal: Meal) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Dishes")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Text("\(meal.dishCount)")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.earthenClay)
            }

            if let dishes = meal.dishes, !dishes.isEmpty {
                VStack(spacing: SautaiDesign.spacingS) {
                    ForEach(dishes) { dish in
                        dishRow(dish)
                    }
                }
            } else {
                Text("No dishes added yet")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.6))
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func dishRow(_ dish: Dish) -> some View {
        NavigationLink {
            DishDetailView(dishId: dish.id)
        } label: {
            HStack(spacing: SautaiDesign.spacingM) {
                // Placeholder image
                Rectangle()
                    .fill(Color.sautai.earthenClay.opacity(0.1))
                    .frame(width: 48, height: 48)
                    .cornerRadius(SautaiDesign.cornerRadiusS)
                    .overlay(
                        Image(systemName: "fork.knife")
                            .font(.system(size: 16))
                            .foregroundColor(.sautai.earthenClay.opacity(0.5))
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text(dish.name)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)

                    if let time = dish.totalTimeDisplay {
                        Text(time)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 12))
                    .foregroundColor(.sautai.slateTile.opacity(0.3))
            }
            .padding(SautaiDesign.spacingM)
            .background(Color.sautai.softCream)
            .cornerRadius(SautaiDesign.cornerRadiusM)
        }
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

    // MARK: - Create Event Button

    private func createEventButton(_ meal: Meal) -> some View {
        NavigationLink {
            AddMealEventView(preselectedMeal: meal) { _ in }
        } label: {
            HStack {
                Image(systemName: "calendar.badge.plus")
                Text("Create Meal Event")
            }
            .font(SautaiFont.button)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, SautaiDesign.spacingM)
            .background(Color.sautai.earthenClay)
            .cornerRadius(SautaiDesign.cornerRadius)
        }
    }

    // MARK: - Metadata Section

    private func metadataSection(_ meal: Meal) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            if let createdAt = meal.createdAt {
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

            if let updatedAt = meal.updatedAt {
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
            Text("Loading meal...")
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

            Text("Could not load meal")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Button {
                Task { await loadMeal() }
            } label: {
                Text("Try Again")
                    .font(SautaiFont.button)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
        .padding(SautaiDesign.spacingXL)
    }

    // MARK: - Data Loading

    private func loadMeal() async {
        isLoading = true
        error = nil
        do {
            meal = try await APIClient.shared.getMealDetail(id: mealId)
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteMeal() {
        Task {
            do {
                try await APIClient.shared.deleteMeal(id: mealId)
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
        MealDetailView(mealId: 1)
    }
}

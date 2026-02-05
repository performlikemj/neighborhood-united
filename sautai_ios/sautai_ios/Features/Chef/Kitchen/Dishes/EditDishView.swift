//
//  EditDishView.swift
//  sautai_ios
//
//  Form for editing an existing dish.
//

import SwiftUI

struct EditDishView: View {
    @Environment(\.dismiss) var dismiss
    let dish: Dish
    let onUpdate: (Dish) -> Void

    @State private var name: String
    @State private var description: String
    @State private var cuisineType: String
    @State private var prepTimeMinutes: Int?
    @State private var cookTimeMinutes: Int?
    @State private var servings: Int?
    @State private var calories: Int?
    @State private var dietaryTags: [String]
    @State private var ingredients: [DishIngredientInput]
    @State private var ingredientDetails: [Int: Ingredient] = [:]
    @State private var isActive: Bool
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingIngredientPicker = false
    @State private var showingTagPicker = false

    private let commonTags = ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Nut-Free", "Low-Carb", "Keto", "Paleo", "Halal", "Kosher"]
    private let cuisineTypes = ["American", "Italian", "Mexican", "Chinese", "Japanese", "Indian", "Thai", "Mediterranean", "French", "Korean", "Vietnamese", "Greek", "Spanish", "Middle Eastern", "Caribbean", "Other"]

    init(dish: Dish, onUpdate: @escaping (Dish) -> Void) {
        self.dish = dish
        self.onUpdate = onUpdate

        _name = State(initialValue: dish.name)
        _description = State(initialValue: dish.description ?? "")
        _cuisineType = State(initialValue: dish.cuisineType ?? "")
        _prepTimeMinutes = State(initialValue: dish.prepTimeMinutes)
        _cookTimeMinutes = State(initialValue: dish.cookTimeMinutes)
        _servings = State(initialValue: dish.servings)
        _calories = State(initialValue: dish.calories)
        _dietaryTags = State(initialValue: dish.dietaryTags ?? [])
        _isActive = State(initialValue: dish.isActive)

        // Convert existing dish ingredients to input format
        let existingIngredients = dish.ingredients?.map { ingredient in
            DishIngredientInput(
                ingredientId: ingredient.ingredientId,
                quantity: ingredient.quantity,
                unit: ingredient.unit,
                notes: ingredient.notes
            )
        } ?? []
        _ingredients = State(initialValue: existingIngredients)
    }

    var body: some View {
        NavigationStack {
            Form {
                // Basic Info
                Section("Basic Info") {
                    TextField("Dish name", text: $name)
                        .font(SautaiFont.body)

                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                        .font(SautaiFont.body)

                    Picker("Cuisine", selection: $cuisineType) {
                        Text("Select cuisine").tag("")
                        ForEach(cuisineTypes, id: \.self) { cuisine in
                            Text(cuisine).tag(cuisine)
                        }
                    }
                }

                // Time & Servings
                Section("Preparation") {
                    HStack {
                        Text("Prep Time")
                        Spacer()
                        TextField("min", value: $prepTimeMinutes, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                        Text("min")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }

                    HStack {
                        Text("Cook Time")
                        Spacer()
                        TextField("min", value: $cookTimeMinutes, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                        Text("min")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }

                    HStack {
                        Text("Servings")
                        Spacer()
                        TextField("", value: $servings, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }

                    HStack {
                        Text("Calories per Serving")
                        Spacer()
                        TextField("", value: $calories, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                        Text("cal")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                // Ingredients
                Section {
                    ForEach(ingredients.indices, id: \.self) { index in
                        ingredientRow(index: index)
                    }
                    .onDelete(perform: deleteIngredient)

                    Button {
                        showingIngredientPicker = true
                    } label: {
                        Label("Add Ingredients", systemImage: "plus")
                            .foregroundColor(.sautai.herbGreen)
                    }
                } header: {
                    Text("Ingredients")
                } footer: {
                    Text("Add ingredients and specify quantities")
                }

                // Dietary Tags
                Section {
                    FlowLayout(spacing: 8) {
                        ForEach(dietaryTags, id: \.self) { tag in
                            tagChip(tag, isSelected: true) {
                                dietaryTags.removeAll { $0 == tag }
                            }
                        }
                    }

                    Button {
                        showingTagPicker = true
                    } label: {
                        Label("Add Tags", systemImage: "plus")
                            .foregroundColor(.sautai.herbGreen)
                    }
                } header: {
                    Text("Dietary Tags")
                }

                // Status
                Section {
                    Toggle("Active", isOn: $isActive)
                } footer: {
                    Text("Inactive dishes won't appear in meal and event creation")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Edit Dish")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveDish()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
                }
            }
            .sheet(isPresented: $showingIngredientPicker) {
                IngredientPickerView(
                    selectedIngredients: $ingredients,
                    existingIngredientIds: Set(ingredients.map { $0.ingredientId })
                )
            }
            .sheet(isPresented: $showingTagPicker) {
                tagPickerSheet
            }
            .onAppear {
                loadExistingIngredientNames()
            }
        }
    }

    // MARK: - Ingredient Row

    private func ingredientRow(index: Int) -> some View {
        let ingredient = ingredients[index]
        let ingredientName = ingredientDetails[ingredient.ingredientId]?.name ??
            dish.ingredients?.first(where: { $0.ingredientId == ingredient.ingredientId })?.ingredientName ??
            "Ingredient #\(ingredient.ingredientId)"

        return HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(ingredientName)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                HStack(spacing: SautaiDesign.spacingS) {
                    TextField("Qty", text: Binding(
                        get: { ingredient.quantity ?? "" },
                        set: { ingredients[index] = DishIngredientInput(ingredientId: ingredient.ingredientId, quantity: $0.isEmpty ? nil : $0, unit: ingredient.unit, notes: ingredient.notes) }
                    ))
                    .font(SautaiFont.caption)
                    .frame(width: 50)
                    .textFieldStyle(.roundedBorder)

                    TextField("Unit", text: Binding(
                        get: { ingredient.unit ?? "" },
                        set: { ingredients[index] = DishIngredientInput(ingredientId: ingredient.ingredientId, quantity: ingredient.quantity, unit: $0.isEmpty ? nil : $0, notes: ingredient.notes) }
                    ))
                    .font(SautaiFont.caption)
                    .frame(width: 60)
                    .textFieldStyle(.roundedBorder)
                }
            }

            Spacer()
        }
    }

    private func deleteIngredient(at offsets: IndexSet) {
        ingredients.remove(atOffsets: offsets)
    }

    // MARK: - Tag Chip

    private func tagChip(_ tag: String, isSelected: Bool, onTap: @escaping () -> Void) -> some View {
        Button(action: onTap) {
            HStack(spacing: 4) {
                Text(tag)
                if isSelected {
                    Image(systemName: "xmark")
                        .font(.system(size: 10, weight: .bold))
                }
            }
            .font(SautaiFont.caption)
            .foregroundColor(isSelected ? .white : .sautai.herbGreen)
            .padding(.horizontal, SautaiDesign.spacingM)
            .padding(.vertical, SautaiDesign.spacingXS)
            .background(isSelected ? Color.sautai.herbGreen : Color.sautai.herbGreen.opacity(0.1))
            .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }

    // MARK: - Tag Picker Sheet

    private var tagPickerSheet: some View {
        NavigationStack {
            List {
                ForEach(commonTags, id: \.self) { tag in
                    let isSelected = dietaryTags.contains(tag)
                    Button {
                        if isSelected {
                            dietaryTags.removeAll { $0 == tag }
                        } else {
                            dietaryTags.append(tag)
                        }
                    } label: {
                        HStack {
                            Text(tag)
                                .foregroundColor(.sautai.slateTile)
                            Spacer()
                            if isSelected {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.sautai.herbGreen)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Dietary Tags")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") {
                        showingTagPicker = false
                    }
                }
            }
        }
    }

    // MARK: - Data Loading

    private func loadExistingIngredientNames() {
        // Ingredient names are already in dish.ingredients[].ingredientName
        // Only need to load if we add new ones
    }

    private func saveDish() {
        isLoading = true
        errorMessage = nil

        let request = DishCreateRequest(
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            description: description.isEmpty ? nil : description,
            ingredients: ingredients.isEmpty ? nil : ingredients,
            cuisineType: cuisineType.isEmpty ? nil : cuisineType,
            dietaryTags: dietaryTags.isEmpty ? nil : dietaryTags,
            prepTimeMinutes: prepTimeMinutes,
            cookTimeMinutes: cookTimeMinutes,
            servings: servings,
            calories: calories,
            isActive: isActive
        )

        Task {
            do {
                let updatedDish = try await APIClient.shared.updateDish(id: dish.id, data: request)
                await MainActor.run {
                    onUpdate(updatedDish)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

#Preview {
    EditDishView(
        dish: Dish(
            id: 1,
            name: "Test Dish",
            description: "A test dish",
            ingredients: nil,
            imageUrl: nil,
            cuisineType: "Italian",
            dietaryTags: ["Vegetarian"],
            prepTimeMinutes: 15,
            cookTimeMinutes: 30,
            servings: 4,
            calories: 350,
            isActive: true,
            createdAt: nil,
            updatedAt: nil
        )
    ) { _ in }
}

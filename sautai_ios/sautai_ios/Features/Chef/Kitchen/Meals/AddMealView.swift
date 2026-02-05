//
//  AddMealView.swift
//  sautai_ios
//
//  Form for creating or editing a meal with dish selection.
//

import SwiftUI

struct AddMealView: View {
    @Environment(\.dismiss) var dismiss
    let editingMeal: Meal?
    let onSave: (Meal) -> Void

    @State private var name: String
    @State private var description: String
    @State private var cuisineType: String
    @State private var prepTimeMinutes: Int?
    @State private var servings: Int?
    @State private var dietaryTags: [String]
    @State private var selectedDishIds: [Int]
    @State private var isActive: Bool
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingDishPicker = false
    @State private var showingTagPicker = false
    @State private var availableDishes: [Dish] = []

    private let commonTags = ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Nut-Free", "Low-Carb", "Keto", "Paleo", "Halal", "Kosher"]
    private let cuisineTypes = ["American", "Italian", "Mexican", "Chinese", "Japanese", "Indian", "Thai", "Mediterranean", "French", "Korean", "Vietnamese", "Greek", "Spanish", "Middle Eastern", "Caribbean", "Other"]

    init(editingMeal: Meal? = nil, onSave: @escaping (Meal) -> Void) {
        self.editingMeal = editingMeal
        self.onSave = onSave

        _name = State(initialValue: editingMeal?.name ?? "")
        _description = State(initialValue: editingMeal?.description ?? "")
        _cuisineType = State(initialValue: editingMeal?.cuisineType ?? "")
        _prepTimeMinutes = State(initialValue: editingMeal?.prepTimeMinutes)
        _servings = State(initialValue: editingMeal?.servings)
        _dietaryTags = State(initialValue: editingMeal?.dietaryTags ?? [])
        _selectedDishIds = State(initialValue: editingMeal?.dishes?.map { $0.id } ?? [])
        _isActive = State(initialValue: editingMeal?.isActive ?? true)
    }

    var isEditing: Bool {
        editingMeal != nil
    }

    var selectedDishes: [Dish] {
        availableDishes.filter { selectedDishIds.contains($0.id) }
    }

    var body: some View {
        NavigationStack {
            Form {
                // Basic Info
                Section("Basic Info") {
                    TextField("Meal name", text: $name)
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
                Section("Details") {
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
                        Text("Servings")
                        Spacer()
                        TextField("", value: $servings, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }
                }

                // Dishes
                Section {
                    ForEach(selectedDishes) { dish in
                        dishRow(dish)
                    }

                    Button {
                        showingDishPicker = true
                    } label: {
                        Label("Select Dishes", systemImage: "plus")
                            .foregroundColor(.sautai.earthenClay)
                    }
                } header: {
                    Text("Dishes")
                } footer: {
                    Text("Choose the dishes that make up this meal")
                }

                // Dietary Tags
                Section {
                    if !dietaryTags.isEmpty {
                        FlowLayout(spacing: 8) {
                            ForEach(dietaryTags, id: \.self) { tag in
                                tagChip(tag, isSelected: true) {
                                    dietaryTags.removeAll { $0 == tag }
                                }
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
                    Text("Inactive meals won't appear in event creation")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle(isEditing ? "Edit Meal" : "New Meal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(isEditing ? "Save" : "Create") {
                        saveMeal()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
                }
            }
            .sheet(isPresented: $showingDishPicker) {
                DishPickerView(selectedDishIds: $selectedDishIds, dishes: availableDishes)
            }
            .sheet(isPresented: $showingTagPicker) {
                tagPickerSheet
            }
        }
        .task {
            await loadDishes()
        }
    }

    // MARK: - Dish Row

    private func dishRow(_ dish: Dish) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            Rectangle()
                .fill(Color.sautai.earthenClay.opacity(0.1))
                .frame(width: 40, height: 40)
                .cornerRadius(SautaiDesign.cornerRadiusS)
                .overlay(
                    Image(systemName: "fork.knife")
                        .font(.system(size: 14))
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

            Button {
                selectedDishIds.removeAll { $0 == dish.id }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.sautai.slateTile.opacity(0.3))
            }
        }
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

    private func loadDishes() async {
        do {
            let response = try await APIClient.shared.getDishes()
            await MainActor.run {
                availableDishes = response.results
            }
        } catch {
            // Handle error
        }
    }

    private func saveMeal() {
        isLoading = true
        errorMessage = nil

        let request = MealCreateRequest(
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            description: description.isEmpty ? nil : description,
            dishIds: selectedDishIds.isEmpty ? nil : selectedDishIds,
            cuisineType: cuisineType.isEmpty ? nil : cuisineType,
            dietaryTags: dietaryTags.isEmpty ? nil : dietaryTags,
            prepTimeMinutes: prepTimeMinutes,
            servings: servings,
            isActive: isActive
        )

        Task {
            do {
                let savedMeal: Meal
                if let editingMeal = editingMeal {
                    savedMeal = try await APIClient.shared.updateMeal(id: editingMeal.id, data: request)
                } else {
                    savedMeal = try await APIClient.shared.createMeal(data: request)
                }
                await MainActor.run {
                    onSave(savedMeal)
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

// MARK: - Dish Picker View

struct DishPickerView: View {
    @Environment(\.dismiss) var dismiss
    @Binding var selectedDishIds: [Int]
    let dishes: [Dish]

    @State private var searchText = ""

    var filteredDishes: [Dish] {
        if searchText.isEmpty {
            return dishes
        }
        return dishes.filter { $0.name.localizedCaseInsensitiveContains(searchText) }
    }

    var body: some View {
        NavigationStack {
            List {
                ForEach(filteredDishes) { dish in
                    let isSelected = selectedDishIds.contains(dish.id)

                    Button {
                        if isSelected {
                            selectedDishIds.removeAll { $0 == dish.id }
                        } else {
                            selectedDishIds.append(dish.id)
                        }
                    } label: {
                        HStack(spacing: SautaiDesign.spacingM) {
                            Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                                .font(.system(size: 22))
                                .foregroundColor(isSelected ? .sautai.earthenClay : .sautai.slateTile.opacity(0.3))

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

                            if !dish.isActive {
                                Text("Inactive")
                                    .font(SautaiFont.caption2)
                                    .foregroundColor(.sautai.warning)
                            }
                        }
                    }
                }
            }
            .searchable(text: $searchText, prompt: "Search dishes")
            .navigationTitle("Select Dishes")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done (\(selectedDishIds.count))") {
                        dismiss()
                    }
                }
            }
        }
    }
}

#Preview {
    AddMealView { _ in }
}

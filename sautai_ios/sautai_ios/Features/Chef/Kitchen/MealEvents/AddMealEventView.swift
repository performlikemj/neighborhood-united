//
//  AddMealEventView.swift
//  sautai_ios
//
//  Form for creating a new meal event.
//

import SwiftUI

struct AddMealEventView: View {
    @Environment(\.dismiss) var dismiss
    let preselectedMeal: Meal?
    let onAdd: (ChefMealEvent) -> Void

    @State private var title = ""
    @State private var description = ""
    @State private var selectedMealId: Int?
    @State private var eventDate = Date()
    @State private var eventTime = ""
    @State private var pricePerServing = ""
    @State private var maxServings: Int?
    @State private var cuisineType = ""
    @State private var dietaryTags: [String] = []
    @State private var pickupAddress = ""
    @State private var pickupInstructions = ""
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingTagPicker = false
    @State private var showingMealPicker = false
    @State private var availableMeals: [Meal] = []

    private let commonTags = ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Nut-Free", "Low-Carb", "Keto", "Paleo", "Halal", "Kosher"]
    private let cuisineTypes = ["American", "Italian", "Mexican", "Chinese", "Japanese", "Indian", "Thai", "Mediterranean", "French", "Korean", "Vietnamese", "Greek", "Spanish", "Middle Eastern", "Caribbean", "Other"]
    private let commonTimes = ["11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM", "1:00 PM", "5:00 PM", "5:30 PM", "6:00 PM", "6:30 PM", "7:00 PM"]

    init(preselectedMeal: Meal? = nil, onAdd: @escaping (ChefMealEvent) -> Void) {
        self.preselectedMeal = preselectedMeal
        self.onAdd = onAdd

        if let meal = preselectedMeal {
            _selectedMealId = State(initialValue: meal.id)
            _title = State(initialValue: meal.name)
            _cuisineType = State(initialValue: meal.cuisineType ?? "")
            _dietaryTags = State(initialValue: meal.dietaryTags ?? [])
        }
    }

    var selectedMeal: Meal? {
        availableMeals.first { $0.id == selectedMealId } ?? preselectedMeal
    }

    var body: some View {
        NavigationStack {
            Form {
                // Basic Info
                Section("Event Details") {
                    TextField("Event title", text: $title)
                        .font(SautaiFont.body)

                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                        .font(SautaiFont.body)
                }

                // Meal Selection
                Section {
                    if let meal = selectedMeal {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(meal.name)
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)
                                Text("\(meal.dishCount) dishes")
                                    .font(SautaiFont.caption)
                                    .foregroundColor(.sautai.slateTile.opacity(0.6))
                            }

                            Spacer()

                            Button {
                                showingMealPicker = true
                            } label: {
                                Text("Change")
                                    .font(SautaiFont.buttonSmall)
                                    .foregroundColor(.sautai.earthenClay)
                            }
                        }
                    } else {
                        Button {
                            showingMealPicker = true
                        } label: {
                            Label("Select Meal", systemImage: "fork.knife")
                                .foregroundColor(.sautai.earthenClay)
                        }
                    }
                } header: {
                    Text("Meal (Optional)")
                } footer: {
                    Text("Link a meal to help customers understand what's being served")
                }

                // Date & Time
                Section("Date & Time") {
                    DatePicker("Event Date", selection: $eventDate, displayedComponents: .date)

                    HStack {
                        Text("Pickup Time")
                        Spacer()
                        Menu {
                            ForEach(commonTimes, id: \.self) { time in
                                Button(time) {
                                    eventTime = time
                                }
                            }
                        } label: {
                            Text(eventTime.isEmpty ? "Select time" : eventTime)
                                .foregroundColor(eventTime.isEmpty ? .sautai.slateTile.opacity(0.5) : .sautai.slateTile)
                        }
                    }
                }

                // Pricing & Availability
                Section("Pricing & Availability") {
                    HStack {
                        Text("Price per Serving")
                        Spacer()
                        Text("$")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                        TextField("0.00", text: $pricePerServing)
                            .keyboardType(.decimalPad)
                            .frame(width: 80)
                            .multilineTextAlignment(.trailing)
                    }

                    HStack {
                        Text("Max Servings")
                        Spacer()
                        TextField("", value: $maxServings, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }
                }

                // Cuisine & Tags
                Section {
                    Picker("Cuisine", selection: $cuisineType) {
                        Text("Select cuisine").tag("")
                        ForEach(cuisineTypes, id: \.self) { cuisine in
                            Text(cuisine).tag(cuisine)
                        }
                    }

                    if !dietaryTags.isEmpty {
                        FlowLayout(spacing: 8) {
                            ForEach(dietaryTags, id: \.self) { tag in
                                tagChip(tag) {
                                    dietaryTags.removeAll { $0 == tag }
                                }
                            }
                        }
                    }

                    Button {
                        showingTagPicker = true
                    } label: {
                        Label("Add Dietary Tags", systemImage: "plus")
                            .foregroundColor(.sautai.herbGreen)
                    }
                } header: {
                    Text("Cuisine & Dietary")
                }

                // Pickup Details
                Section {
                    TextField("Pickup address", text: $pickupAddress)
                        .font(SautaiFont.body)

                    TextField("Special instructions (optional)", text: $pickupInstructions, axis: .vertical)
                        .lineLimit(2...4)
                        .font(SautaiFont.body)
                } header: {
                    Text("Pickup Location")
                } footer: {
                    Text("Where customers should pick up their orders")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("New Event")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        saveEvent()
                    }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || pricePerServing.isEmpty || isLoading)
                }
            }
            .sheet(isPresented: $showingTagPicker) {
                tagPickerSheet
            }
            .sheet(isPresented: $showingMealPicker) {
                mealPickerSheet
            }
        }
        .task {
            await loadMeals()
        }
    }

    // MARK: - Tag Chip

    private func tagChip(_ tag: String, onRemove: @escaping () -> Void) -> some View {
        Button(action: onRemove) {
            HStack(spacing: 4) {
                Text(tag)
                Image(systemName: "xmark")
                    .font(.system(size: 10, weight: .bold))
            }
            .font(SautaiFont.caption)
            .foregroundColor(.white)
            .padding(.horizontal, SautaiDesign.spacingM)
            .padding(.vertical, SautaiDesign.spacingXS)
            .background(Color.sautai.herbGreen)
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

    // MARK: - Meal Picker Sheet

    private var mealPickerSheet: some View {
        NavigationStack {
            List {
                ForEach(availableMeals.filter { $0.isActive }) { meal in
                    Button {
                        selectedMealId = meal.id
                        if title.isEmpty {
                            title = meal.name
                        }
                        if cuisineType.isEmpty, let cuisine = meal.cuisineType {
                            cuisineType = cuisine
                        }
                        if dietaryTags.isEmpty, let tags = meal.dietaryTags {
                            dietaryTags = tags
                        }
                        showingMealPicker = false
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(meal.name)
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)
                                Text("\(meal.dishCount) dishes")
                                    .font(SautaiFont.caption)
                                    .foregroundColor(.sautai.slateTile.opacity(0.6))
                            }

                            Spacer()

                            if selectedMealId == meal.id {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.sautai.earthenClay)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Select Meal")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        showingMealPicker = false
                    }
                }
            }
        }
    }

    // MARK: - Data Loading

    private func loadMeals() async {
        do {
            let response = try await APIClient.shared.getChefMeals()
            await MainActor.run {
                availableMeals = response.results
            }
        } catch {
            // Handle error
        }
    }

    private func saveEvent() {
        isLoading = true
        errorMessage = nil

        let request = MealEventCreateRequest(
            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
            description: description.isEmpty ? nil : description,
            mealId: selectedMealId,
            eventDate: eventDate,
            eventTime: eventTime.isEmpty ? nil : eventTime,
            pricePerServing: pricePerServing,
            maxServings: maxServings,
            cuisineType: cuisineType.isEmpty ? nil : cuisineType,
            dietaryTags: dietaryTags.isEmpty ? nil : dietaryTags,
            pickupAddress: pickupAddress.isEmpty ? nil : pickupAddress,
            pickupInstructions: pickupInstructions.isEmpty ? nil : pickupInstructions
        )

        Task {
            do {
                let newEvent = try await APIClient.shared.createMealEvent(data: request)
                await MainActor.run {
                    onAdd(newEvent)
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
    AddMealEventView { _ in }
}

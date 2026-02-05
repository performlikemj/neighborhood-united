//
//  CreateMealPlanView.swift
//  sautai_ios
//
//  Create a new meal plan for a client.
//

import SwiftUI

struct CreateMealPlanView: View {
    @Environment(\.dismiss) var dismiss
    let onCreated: (MealPlan) -> Void

    @State private var title = ""
    @State private var selectedClientId: Int?
    @State private var startDate = Date()
    @State private var endDate = Calendar.current.date(byAdding: .day, value: 7, to: Date())!
    @State private var notes = ""
    @State private var clients: [Client] = []
    @State private var isLoading = false
    @State private var isLoadingClients = true
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Plan Details") {
                    TextField("Plan Title (optional)", text: $title)

                    Picker("Client", selection: $selectedClientId) {
                        Text("Select a client").tag(nil as Int?)
                        ForEach(clients) { client in
                            Text(client.displayName).tag(client.id as Int?)
                        }
                    }
                }

                Section("Date Range") {
                    DatePicker("Start Date", selection: $startDate, displayedComponents: .date)
                    DatePicker("End Date", selection: $endDate, in: startDate..., displayedComponents: .date)
                }

                Section("Notes") {
                    TextField("Additional notes...", text: $notes, axis: .vertical)
                        .lineLimit(3...6)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("New Meal Plan")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        createPlan()
                    }
                    .disabled(selectedClientId == nil || isLoading)
                }
            }
            .overlay {
                if isLoadingClients {
                    ProgressView()
                }
            }
        }
        .task {
            await loadClients()
        }
    }

    private func loadClients() async {
        isLoadingClients = true
        do {
            let response = try await APIClient.shared.getClients()
            clients = response.results
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoadingClients = false
    }

    private func createPlan() {
        guard let clientId = selectedClientId else { return }

        isLoading = true
        errorMessage = nil

        let request = MealPlanCreateRequest(
            clientId: clientId,
            title: title.isEmpty ? nil : title,
            startDate: startDate,
            endDate: endDate,
            notes: notes.isEmpty ? nil : notes
        )

        Task {
            do {
                let newPlan = try await APIClient.shared.createMealPlan(data: request)
                await MainActor.run {
                    onCreated(newPlan)
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

// MARK: - Add Plan Day View

struct AddPlanDayView: View {
    @Environment(\.dismiss) var dismiss
    let planId: Int
    let onAdded: (MealPlanDay) -> Void

    @State private var date = Date()
    @State private var notes = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Day Details") {
                    DatePicker("Date", selection: $date, displayedComponents: .date)
                }

                Section("Notes") {
                    TextField("Notes for this day...", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Add Day")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        addDay()
                    }
                    .disabled(isLoading)
                }
            }
        }
    }

    private func addDay() {
        isLoading = true
        errorMessage = nil

        let request = MealPlanDayCreateRequest(
            date: date,
            notes: notes.isEmpty ? nil : notes
        )

        Task {
            do {
                let newDay = try await APIClient.shared.addMealPlanDay(planId: planId, data: request)
                await MainActor.run {
                    onAdded(newDay)
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

// MARK: - Plan Day Detail View

struct PlanDayDetailView: View {
    @Environment(\.dismiss) var dismiss
    let plan: MealPlan
    let day: MealPlanDay
    let onUpdated: () -> Void

    @State private var showingAddItem = false
    @State private var selectedMealType: MealType = .breakfast

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    // Day Header
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                        Text(day.displayDate)
                            .font(SautaiFont.title2)
                            .foregroundColor(.sautai.slateTile)

                        if let notes = day.notes, !notes.isEmpty {
                            Text(notes)
                                .font(SautaiFont.body)
                                .foregroundColor(.sautai.slateTile.opacity(0.7))
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(SautaiDesign.spacing)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadius)

                    // Meals by Type
                    ForEach(MealType.allCases, id: \.self) { mealType in
                        mealTypeSection(mealType)
                    }
                }
                .padding(SautaiDesign.spacing)
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Day Details")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
            .sheet(isPresented: $showingAddItem) {
                AddMealItemView(planId: plan.id, dayId: day.id, mealType: selectedMealType) {
                    onUpdated()
                }
            }
        }
    }

    private func mealTypeSection(_ mealType: MealType) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            HStack {
                Image(systemName: mealType.icon)
                    .foregroundColor(.sautai.earthenClay)
                Text(mealType.displayName)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Button {
                    selectedMealType = mealType
                    showingAddItem = true
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .foregroundColor(.sautai.earthenClay)
                }
            }

            let items = day.items?.filter { $0.mealType == mealType } ?? []

            if items.isEmpty {
                Text("No \(mealType.displayName.lowercased()) planned")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                    .italic()
                    .padding(.vertical, SautaiDesign.spacingS)
            } else {
                ForEach(items) { item in
                    MealItemRow(item: item)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }
}

// MARK: - Meal Item Row

struct MealItemRow: View {
    let item: MealPlanItem

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(item.displayName)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                if let servings = item.servings {
                    Text("\(servings) serving\(servings == 1 ? "" : "s")")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            Spacer()

            if item.isCompleted {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.sautai.success)
            }

            if item.suggestedBy != nil {
                Image(systemName: "lightbulb.fill")
                    .foregroundColor(.sautai.sunlitApricot)
                    .font(.caption)
            }
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.softCream)
        .cornerRadius(SautaiDesign.cornerRadiusS)
    }
}

// MARK: - Add Meal Item View

struct AddMealItemView: View {
    @Environment(\.dismiss) var dismiss
    let planId: Int
    let dayId: Int
    let mealType: MealType
    let onAdded: () -> Void

    @State private var meals: [Meal] = []
    @State private var dishes: [Dish] = []
    @State private var selectedMealId: Int?
    @State private var selectedDishId: Int?
    @State private var servings = 1
    @State private var notes = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Select Meal or Dish") {
                    Picker("Meal", selection: $selectedMealId) {
                        Text("None").tag(nil as Int?)
                        ForEach(meals) { meal in
                            Text(meal.name).tag(meal.id as Int?)
                        }
                    }

                    Picker("Or Dish", selection: $selectedDishId) {
                        Text("None").tag(nil as Int?)
                        ForEach(dishes) { dish in
                            Text(dish.name).tag(dish.id as Int?)
                        }
                    }
                }

                Section("Details") {
                    Stepper("Servings: \(servings)", value: $servings, in: 1...10)

                    TextField("Notes", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Add \(mealType.displayName)")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        addItem()
                    }
                    .disabled(selectedMealId == nil && selectedDishId == nil || isLoading)
                }
            }
        }
        .task {
            await loadOptions()
        }
    }

    private func loadOptions() async {
        do {
            let mealsResponse = try await APIClient.shared.getChefMeals()
            meals = mealsResponse.results

            let dishesResponse = try await APIClient.shared.getDishes()
            dishes = dishesResponse.results
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func addItem() {
        isLoading = true
        errorMessage = nil

        let request = MealPlanItemCreateRequest(
            mealType: mealType,
            mealId: selectedMealId,
            dishId: selectedMealId == nil ? selectedDishId : nil,
            servings: servings,
            notes: notes.isEmpty ? nil : notes
        )

        Task {
            do {
                _ = try await APIClient.shared.addMealPlanItem(planId: planId, dayId: dayId, data: request)
                await MainActor.run {
                    onAdded()
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

// MARK: - Generate Meals View

struct GenerateMealsView: View {
    @Environment(\.dismiss) var dismiss
    let planId: Int
    let onGenerated: () -> Void

    @State private var preferences: [String] = []
    @State private var dietaryRestrictions: [String] = []
    @State private var mealsPerDay = 3
    @State private var isLoading = false
    @State private var errorMessage: String?

    let preferenceOptions = ["Quick & Easy", "Budget Friendly", "High Protein", "Low Carb", "Family Friendly", "Gourmet"]
    let restrictionOptions = ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Nut-Free", "Low Sodium"]

    var body: some View {
        NavigationStack {
            Form {
                Section("Preferences") {
                    ForEach(preferenceOptions, id: \.self) { option in
                        Toggle(option, isOn: Binding(
                            get: { preferences.contains(option) },
                            set: { if $0 { preferences.append(option) } else { preferences.removeAll { $0 == option } } }
                        ))
                    }
                }

                Section("Dietary Restrictions") {
                    ForEach(restrictionOptions, id: \.self) { option in
                        Toggle(option, isOn: Binding(
                            get: { dietaryRestrictions.contains(option) },
                            set: { if $0 { dietaryRestrictions.append(option) } else { dietaryRestrictions.removeAll { $0 == option } } }
                        ))
                    }
                }

                Section("Meals Per Day") {
                    Stepper("\(mealsPerDay) meals", value: $mealsPerDay, in: 1...5)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Generate with AI")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Generate") {
                        generateMeals()
                    }
                    .disabled(isLoading)
                }
            }
            .overlay {
                if isLoading {
                    VStack {
                        ProgressView()
                            .scaleEffect(1.5)
                        Text("Generating meals...")
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile)
                            .padding(.top)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.3))
                }
            }
        }
    }

    private func generateMeals() {
        isLoading = true
        errorMessage = nil

        let request = MealPlanGenerateRequest(
            preferences: preferences.isEmpty ? nil : preferences,
            dietaryRestrictions: dietaryRestrictions.isEmpty ? nil : dietaryRestrictions,
            numberOfDays: nil,
            mealsPerDay: mealsPerDay
        )

        Task {
            do {
                _ = try await APIClient.shared.generateMealPlanMeals(planId: planId, data: request)
                await MainActor.run {
                    onGenerated()
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
    CreateMealPlanView { _ in }
}

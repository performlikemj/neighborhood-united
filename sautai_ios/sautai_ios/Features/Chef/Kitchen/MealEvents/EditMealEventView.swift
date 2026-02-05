//
//  EditMealEventView.swift
//  sautai_ios
//
//  Form for editing an existing meal event.
//

import SwiftUI

struct EditMealEventView: View {
    @Environment(\.dismiss) var dismiss
    let event: ChefMealEvent
    let onUpdate: (ChefMealEvent) -> Void

    @State private var title: String
    @State private var description: String
    @State private var eventDate: Date
    @State private var eventTime: String
    @State private var pricePerServing: String
    @State private var maxServings: Int?
    @State private var cuisineType: String
    @State private var dietaryTags: [String]
    @State private var isClosed: Bool
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingTagPicker = false

    private let commonTags = ["Vegetarian", "Vegan", "Gluten-Free", "Dairy-Free", "Nut-Free", "Low-Carb", "Keto", "Paleo", "Halal", "Kosher"]
    private let cuisineTypes = ["American", "Italian", "Mexican", "Chinese", "Japanese", "Indian", "Thai", "Mediterranean", "French", "Korean", "Vietnamese", "Greek", "Spanish", "Middle Eastern", "Caribbean", "Other"]
    private let commonTimes = ["11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM", "1:00 PM", "5:00 PM", "5:30 PM", "6:00 PM", "6:30 PM", "7:00 PM"]

    init(event: ChefMealEvent, onUpdate: @escaping (ChefMealEvent) -> Void) {
        self.event = event
        self.onUpdate = onUpdate

        _title = State(initialValue: event.title)
        _description = State(initialValue: event.description ?? "")
        _eventDate = State(initialValue: event.eventDate)
        _eventTime = State(initialValue: event.eventTime ?? "")
        _pricePerServing = State(initialValue: event.pricePerServing)
        _maxServings = State(initialValue: event.maxServings)
        _cuisineType = State(initialValue: event.cuisineType ?? "")
        _dietaryTags = State(initialValue: event.dietaryTags ?? [])
        _isClosed = State(initialValue: event.isClosed)
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

                    if let current = event.currentServings, current > 0 {
                        HStack {
                            Text("Current Orders")
                            Spacer()
                            Text("\(current) servings")
                                .foregroundColor(.sautai.slateTile.opacity(0.6))
                        }
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

                // Status
                Section {
                    Toggle("Event Closed", isOn: $isClosed)
                } header: {
                    Text("Status")
                } footer: {
                    Text("Closed events won't accept new orders")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Edit Event")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveEvent()
                    }
                    .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || pricePerServing.isEmpty || isLoading)
                }
            }
            .sheet(isPresented: $showingTagPicker) {
                tagPickerSheet
            }
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

    // MARK: - Save Event

    private func saveEvent() {
        isLoading = true
        errorMessage = nil

        let request = MealEventUpdateRequest(
            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
            description: description.isEmpty ? nil : description,
            mealId: nil,
            eventDate: eventDate,
            eventTime: eventTime.isEmpty ? nil : eventTime,
            pricePerServing: pricePerServing,
            maxServings: maxServings,
            cuisineType: cuisineType.isEmpty ? nil : cuisineType,
            dietaryTags: dietaryTags.isEmpty ? nil : dietaryTags,
            pickupAddress: nil,
            pickupInstructions: nil,
            isClosed: isClosed
        )

        Task {
            do {
                let updatedEvent = try await APIClient.shared.updateMealEvent(id: event.id, data: request)
                await MainActor.run {
                    onUpdate(updatedEvent)
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
    EditMealEventView(
        event: ChefMealEvent(
            id: 1,
            chefId: 1,
            chefName: "Test Chef",
            title: "Sunday Dinner",
            description: "A delicious meal",
            eventDate: Date(),
            eventTime: "6:00 PM",
            pricePerServing: "25.00",
            currency: "USD",
            maxServings: 10,
            currentServings: 3,
            cuisineType: "Italian",
            dietaryTags: ["Vegetarian"],
            imageUrl: nil,
            isClosed: false,
            createdAt: nil
        )
    ) { _ in }
}

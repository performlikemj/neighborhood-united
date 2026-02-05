//
//  AddIngredientView.swift
//  sautai_ios
//
//  Form for adding a new ingredient.
//

import SwiftUI

struct AddIngredientView: View {
    @Environment(\.dismiss) var dismiss
    let onAdd: (Ingredient) -> Void

    @State private var name = ""
    @State private var selectedCategory: IngredientCategory = .other
    @State private var unit = ""
    @State private var isLoading = false
    @State private var errorMessage: String?

    private let commonUnits = ["oz", "lb", "g", "kg", "cup", "tbsp", "tsp", "ml", "L", "piece", "bunch", "can", "jar"]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("Ingredient name", text: $name)
                        .font(SautaiFont.body)
                } header: {
                    Text("Name")
                } footer: {
                    Text("e.g., Olive Oil, Chicken Breast, Fresh Basil")
                }

                Section("Category") {
                    Picker("Category", selection: $selectedCategory) {
                        ForEach(IngredientCategory.allCases, id: \.self) { category in
                            Label(category.displayName, systemImage: category.icon)
                                .tag(category)
                        }
                    }
                    .pickerStyle(.menu)
                }

                Section {
                    HStack {
                        TextField("Default unit (optional)", text: $unit)
                            .font(SautaiFont.body)

                        Spacer()

                        Menu {
                            ForEach(commonUnits, id: \.self) { unitOption in
                                Button(unitOption) {
                                    unit = unitOption
                                }
                            }
                        } label: {
                            Image(systemName: "chevron.down")
                                .foregroundColor(.sautai.earthenClay)
                        }
                    }
                } header: {
                    Text("Unit")
                } footer: {
                    Text("The default measurement unit for this ingredient")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Add Ingredient")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        saveIngredient()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
                }
            }
        }
    }

    private func saveIngredient() {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                let newIngredient = try await APIClient.shared.createIngredient(
                    name: name.trimmingCharacters(in: .whitespacesAndNewlines),
                    category: selectedCategory.rawValue,
                    unit: unit.isEmpty ? nil : unit
                )
                await MainActor.run {
                    onAdd(newIngredient)
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
    AddIngredientView { _ in }
}

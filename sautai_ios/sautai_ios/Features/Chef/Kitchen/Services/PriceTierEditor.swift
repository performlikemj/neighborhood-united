//
//  PriceTierEditor.swift
//  sautai_ios
//
//  Components for managing price tiers.
//

import SwiftUI

// MARK: - Add Price Tier View

struct AddPriceTierView: View {
    @Environment(\.dismiss) var dismiss
    let serviceId: Int
    let onAdd: (PriceTier) -> Void

    @State private var name = ""
    @State private var price = ""
    @State private var description = ""
    @State private var servings: Int?
    @State private var isPopular = false
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Tier Details") {
                    TextField("Tier name", text: $name)
                        .font(SautaiFont.body)

                    HStack {
                        Text("Price")
                        Spacer()
                        Text("$")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                        TextField("0.00", text: $price)
                            .keyboardType(.decimalPad)
                            .frame(width: 80)
                            .multilineTextAlignment(.trailing)
                    }

                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                        .font(SautaiFont.body)
                }

                Section {
                    HStack {
                        Text("Servings")
                        Spacer()
                        TextField("", value: $servings, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }
                } header: {
                    Text("Options")
                } footer: {
                    Text("Number of servings included in this tier")
                }

                Section {
                    Toggle("Mark as Popular", isOn: $isPopular)
                } footer: {
                    Text("Popular tiers are highlighted to customers")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Add Price Tier")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        saveTier()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || price.isEmpty || isLoading)
                }
            }
        }
    }

    private func saveTier() {
        guard let priceDecimal = Decimal(string: price) else {
            errorMessage = "Invalid price format"
            return
        }

        isLoading = true
        errorMessage = nil

        let request = PriceTierCreateRequest(
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            price: priceDecimal,
            description: description.isEmpty ? nil : description,
            servings: servings,
            isPopular: isPopular,
            sortOrder: nil
        )

        Task {
            do {
                let newTier = try await APIClient.shared.addPriceTier(offeringId: serviceId, data: request)
                await MainActor.run {
                    onAdd(newTier)
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

// MARK: - Edit Price Tier View

struct EditPriceTierView: View {
    @Environment(\.dismiss) var dismiss
    let serviceId: Int
    let tier: PriceTier
    let onUpdate: (PriceTier) -> Void

    @State private var name: String
    @State private var price: String
    @State private var description: String
    @State private var servings: Int?
    @State private var isPopular: Bool
    @State private var isLoading = false
    @State private var errorMessage: String?

    init(serviceId: Int, tier: PriceTier, onUpdate: @escaping (PriceTier) -> Void) {
        self.serviceId = serviceId
        self.tier = tier
        self.onUpdate = onUpdate

        _name = State(initialValue: tier.name)
        _price = State(initialValue: String(format: "%.2f", NSDecimalNumber(decimal: tier.price).doubleValue))
        _description = State(initialValue: tier.description ?? "")
        _servings = State(initialValue: tier.servings)
        _isPopular = State(initialValue: tier.isPopular)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Tier Details") {
                    TextField("Tier name", text: $name)
                        .font(SautaiFont.body)

                    HStack {
                        Text("Price")
                        Spacer()
                        Text("$")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                        TextField("0.00", text: $price)
                            .keyboardType(.decimalPad)
                            .frame(width: 80)
                            .multilineTextAlignment(.trailing)
                    }

                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                        .font(SautaiFont.body)
                }

                Section {
                    HStack {
                        Text("Servings")
                        Spacer()
                        TextField("", value: $servings, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }
                } header: {
                    Text("Options")
                } footer: {
                    Text("Number of servings included in this tier")
                }

                Section {
                    Toggle("Mark as Popular", isOn: $isPopular)
                } footer: {
                    Text("Popular tiers are highlighted to customers")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Edit Price Tier")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveTier()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || price.isEmpty || isLoading)
                }
            }
        }
    }

    private func saveTier() {
        guard let priceDecimal = Decimal(string: price) else {
            errorMessage = "Invalid price format"
            return
        }

        isLoading = true
        errorMessage = nil

        let request = PriceTierCreateRequest(
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            price: priceDecimal,
            description: description.isEmpty ? nil : description,
            servings: servings,
            isPopular: isPopular,
            sortOrder: tier.sortOrder
        )

        Task {
            do {
                let updatedTier = try await APIClient.shared.updatePriceTier(offeringId: serviceId, tierId: tier.id, data: request)
                await MainActor.run {
                    onUpdate(updatedTier)
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

#Preview("Add Tier") {
    AddPriceTierView(serviceId: 1) { _ in }
}

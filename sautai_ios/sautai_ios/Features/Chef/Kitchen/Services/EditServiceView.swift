//
//  EditServiceView.swift
//  sautai_ios
//
//  Form for editing an existing service offering.
//

import SwiftUI

struct EditServiceView: View {
    @Environment(\.dismiss) var dismiss
    let service: ServiceOffering
    let onUpdate: (ServiceOffering) -> Void

    @State private var name: String
    @State private var description: String
    @State private var serviceType: ServiceType
    @State private var estimatedDuration: Int?
    @State private var maxOrdersPerDay: Int?
    @State private var leadTimeHours: Int?
    @State private var isActive: Bool
    @State private var isLoading = false
    @State private var errorMessage: String?

    init(service: ServiceOffering, onUpdate: @escaping (ServiceOffering) -> Void) {
        self.service = service
        self.onUpdate = onUpdate

        _name = State(initialValue: service.name)
        _description = State(initialValue: service.description ?? "")
        _serviceType = State(initialValue: service.serviceType)
        _estimatedDuration = State(initialValue: service.estimatedDuration)
        _maxOrdersPerDay = State(initialValue: service.maxOrdersPerDay)
        _leadTimeHours = State(initialValue: service.leadTimeHours)
        _isActive = State(initialValue: service.isActive)
    }

    var body: some View {
        NavigationStack {
            Form {
                // Basic Info
                Section("Service Details") {
                    TextField("Service name", text: $name)
                        .font(SautaiFont.body)

                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                        .font(SautaiFont.body)
                }

                // Service Type
                Section("Type") {
                    Picker("Service Type", selection: $serviceType) {
                        ForEach(ServiceType.allCases, id: \.self) { type in
                            Label(type.displayName, systemImage: type.icon)
                                .tag(type)
                        }
                    }
                    .pickerStyle(.menu)
                }

                // Configuration
                Section {
                    HStack {
                        Text("Duration")
                        Spacer()
                        TextField("min", value: $estimatedDuration, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                        Text("min")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }

                    HStack {
                        Text("Max Orders/Day")
                        Spacer()
                        TextField("", value: $maxOrdersPerDay, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }

                    HStack {
                        Text("Lead Time")
                        Spacer()
                        TextField("hours", value: $leadTimeHours, format: .number)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                        Text("hours")
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                } header: {
                    Text("Configuration")
                } footer: {
                    Text("Set limits and lead times for this service")
                }

                // Status
                Section {
                    Toggle("Active", isOn: $isActive)
                } footer: {
                    Text("Inactive services won't be visible to customers")
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Edit Service")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveService()
                    }
                    .disabled(name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isLoading)
                }
            }
        }
    }

    private func saveService() {
        isLoading = true
        errorMessage = nil

        let request = ServiceOfferingCreateRequest(
            name: name.trimmingCharacters(in: .whitespacesAndNewlines),
            description: description.isEmpty ? nil : description,
            serviceType: serviceType,
            isActive: isActive,
            estimatedDuration: estimatedDuration,
            maxOrdersPerDay: maxOrdersPerDay,
            leadTimeHours: leadTimeHours
        )

        Task {
            do {
                let updatedService = try await APIClient.shared.updateServiceOffering(id: service.id, data: request)
                await MainActor.run {
                    onUpdate(updatedService)
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
    EditServiceView(
        service: ServiceOffering(
            id: 1,
            name: "Meal Prep Service",
            description: "Weekly meal prep",
            serviceType: .mealPrep,
            isActive: true,
            priceTiers: nil,
            imageUrl: nil,
            estimatedDuration: 120,
            maxOrdersPerDay: 5,
            leadTimeHours: 24,
            createdAt: nil,
            updatedAt: nil
        )
    ) { _ in }
}

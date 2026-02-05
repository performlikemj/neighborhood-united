//
//  AddServiceView.swift
//  sautai_ios
//
//  Form for creating a new service offering.
//

import SwiftUI

struct AddServiceView: View {
    @Environment(\.dismiss) var dismiss
    let onAdd: (ServiceOffering) -> Void

    @State private var name = ""
    @State private var description = ""
    @State private var serviceType: ServiceType = .mealPrep
    @State private var estimatedDuration: Int?
    @State private var maxOrdersPerDay: Int?
    @State private var leadTimeHours: Int?
    @State private var isActive = true
    @State private var isLoading = false
    @State private var errorMessage: String?

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
            .navigationTitle("New Service")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
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
                let newService = try await APIClient.shared.createServiceOffering(data: request)
                await MainActor.run {
                    onAdd(newService)
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
    AddServiceView { _ in }
}

//
//  ServiceAreasView.swift
//  sautai_ios
//
//  Manage chef service areas and postal codes.
//

import SwiftUI

struct ServiceAreasView: View {
    @State private var serviceAreas: [ServiceArea] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingAddSheet = false
    @State private var selectedArea: ServiceArea?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    if isLoading {
                        loadingView
                    } else if let error = error {
                        errorView(error)
                    } else if serviceAreas.isEmpty {
                        emptyStateView
                    } else {
                        areasList
                    }
                }
                .padding(SautaiDesign.spacing)
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Service Areas")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingAddSheet = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingAddSheet) {
                AddServiceAreaView { newArea in
                    serviceAreas.append(newArea)
                }
            }
            .sheet(item: $selectedArea) { area in
                EditServiceAreaView(area: area) { updatedArea in
                    if let index = serviceAreas.firstIndex(where: { $0.id == updatedArea.id }) {
                        serviceAreas[index] = updatedArea
                    }
                }
            }
            .refreshable {
                await loadAreas()
            }
        }
        .task {
            await loadAreas()
        }
    }

    // MARK: - Areas List

    private var areasList: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Your Service Areas")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(serviceAreas) { area in
                ServiceAreaRow(area: area, onTap: {
                    selectedArea = area
                }, onDelete: {
                    deleteArea(area)
                })
            }

            // Info Card
            HStack(alignment: .top, spacing: SautaiDesign.spacingM) {
                Image(systemName: "info.circle")
                    .foregroundColor(.sautai.info)

                Text("Customers in your service areas can discover and order from you. You can add specific postal codes to each area for precise coverage.")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
            }
            .padding(SautaiDesign.spacing)
            .background(Color.sautai.info.opacity(0.1))
            .cornerRadius(SautaiDesign.cornerRadius)
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack {
            ProgressView()
                .scaleEffect(1.5)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    // MARK: - Error View

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load service areas")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadAreas() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .padding()
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "map")
                .font(.system(size: 64))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No Service Areas")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Add service areas to let customers in those locations find you.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button {
                showingAddSheet = true
            } label: {
                Label("Add Service Area", systemImage: "plus.circle")
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Actions

    private func loadAreas() async {
        isLoading = true
        error = nil

        do {
            serviceAreas = try await APIClient.shared.getServiceAreas()
        } catch {
            self.error = error
        }

        isLoading = false
    }

    private func deleteArea(_ area: ServiceArea) {
        Task {
            do {
                try await APIClient.shared.removeServiceArea(id: area.id)
                serviceAreas.removeAll { $0.id == area.id }
            } catch {
                self.error = error
            }
        }
    }
}

// MARK: - Service Area Row

struct ServiceAreaRow: View {
    let area: ServiceArea
    let onTap: () -> Void
    let onDelete: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    HStack {
                        Image(systemName: "location.circle.fill")
                            .foregroundColor(.sautai.earthenClay)

                        Text(area.name ?? area.postalCode)
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.slateTile)
                    }

                    HStack(spacing: SautaiDesign.spacingS) {
                        if let radius = area.radiusMiles {
                            Label("\(radius) mile radius", systemImage: "circle.dashed")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.7))
                        }

                        if let postalCodes = area.postalCodes, !postalCodes.isEmpty {
                            Label("\(postalCodes.count) postal codes", systemImage: "number")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.7))
                        }
                    }
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.3))
            }
            .padding(SautaiDesign.spacing)
            .background(Color.white)
            .cornerRadius(SautaiDesign.cornerRadius)
            .sautaiShadow(SautaiDesign.shadowSubtle)
        }
        .buttonStyle(.plain)
        .swipeActions(edge: .trailing) {
            Button(role: .destructive) {
                onDelete()
            } label: {
                Label("Delete", systemImage: "trash")
            }
        }
    }
}

// MARK: - Add Service Area View

struct AddServiceAreaView: View {
    @Environment(\.dismiss) var dismiss
    let onAdded: (ServiceArea) -> Void

    @State private var postalCode = ""
    @State private var radius: Int = 10
    @State private var isAdding = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Location") {
                    TextField("Postal Code", text: $postalCode)
                        .keyboardType(.numberPad)
                }

                Section("Radius") {
                    Stepper("\(radius) miles", value: $radius, in: 1...50)
                }

                Section {
                    Text("Enter a postal code as the center of your service area. Customers within the radius will be able to find you.")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Add Service Area")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Add") {
                        addArea()
                    }
                    .disabled(postalCode.isEmpty || isAdding)
                }
            }
        }
    }

    private func addArea() {
        isAdding = true
        errorMessage = nil

        Task {
            do {
                let newArea = try await APIClient.shared.addServiceArea(
                    postalCode: postalCode,
                    radius: radius
                )
                await MainActor.run {
                    onAdded(newArea)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isAdding = false
                }
            }
        }
    }
}

// MARK: - Edit Service Area View

struct EditServiceAreaView: View {
    @Environment(\.dismiss) var dismiss
    let area: ServiceArea
    let onSaved: (ServiceArea) -> Void

    @State private var postalCodes: [String]
    @State private var newPostalCode = ""
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(area: ServiceArea, onSaved: @escaping (ServiceArea) -> Void) {
        self.area = area
        self.onSaved = onSaved
        _postalCodes = State(initialValue: area.postalCodes ?? [])
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Service Area") {
                    HStack {
                        Text("Center")
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                        Spacer()
                        Text(area.postalCode)
                            .foregroundColor(.sautai.slateTile)
                    }

                    if let radius = area.radiusMiles {
                        HStack {
                            Text("Radius")
                                .foregroundColor(.sautai.slateTile.opacity(0.7))
                            Spacer()
                            Text("\(radius) miles")
                                .foregroundColor(.sautai.slateTile)
                        }
                    }
                }

                Section("Additional Postal Codes") {
                    ForEach(postalCodes, id: \.self) { code in
                        HStack {
                            Text(code)
                            Spacer()
                            Button {
                                postalCodes.removeAll { $0 == code }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(.sautai.slateTile.opacity(0.3))
                            }
                        }
                    }

                    HStack {
                        TextField("Add postal code", text: $newPostalCode)
                            .keyboardType(.numberPad)
                        Button {
                            if !newPostalCode.isEmpty && !postalCodes.contains(newPostalCode) {
                                postalCodes.append(newPostalCode)
                                newPostalCode = ""
                            }
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(.sautai.earthenClay)
                        }
                        .disabled(newPostalCode.isEmpty)
                    }
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Edit Area")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveChanges()
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func saveChanges() {
        isSaving = true
        errorMessage = nil

        Task {
            do {
                let updated = try await APIClient.shared.addPostalCodes(
                    areaId: area.id,
                    postalCodes: postalCodes
                )
                await MainActor.run {
                    onSaved(updated)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isSaving = false
                }
            }
        }
    }
}

#Preview {
    ServiceAreasView()
}

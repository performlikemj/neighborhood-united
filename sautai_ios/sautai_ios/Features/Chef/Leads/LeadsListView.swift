//
//  LeadsListView.swift
//  sautai_ios
//
//  CRM-style leads management for chef client acquisition.
//

import SwiftUI

struct LeadsListView: View {
    @State private var leads: [Lead] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var selectedStatus: LeadStatus?
    @State private var showingAddLead = false
    @State private var searchText = ""

    var filteredLeads: [Lead] {
        var result = leads

        if let status = selectedStatus {
            result = result.filter { $0.status == status }
        }

        if !searchText.isEmpty {
            result = result.filter { lead in
                lead.name.localizedCaseInsensitiveContains(searchText) ||
                (lead.email?.localizedCaseInsensitiveContains(searchText) ?? false) ||
                (lead.phoneNumber?.localizedCaseInsensitiveContains(searchText) ?? false)
            }
        }

        return result
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Status filter
                statusFilterBar

                // Content
                if isLoading {
                    loadingView
                } else if leads.isEmpty {
                    emptyView
                } else if filteredLeads.isEmpty {
                    noResultsView
                } else {
                    leadsList
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Leads")
            .searchable(text: $searchText, prompt: "Search leads...")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingAddLead = true
                    } label: {
                        Image(systemName: "plus")
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }
            .sheet(isPresented: $showingAddLead) {
                AddLeadView { newLead in
                    leads.insert(newLead, at: 0)
                }
            }
            .refreshable {
                await loadLeads()
            }
        }
        .task {
            await loadLeads()
        }
    }

    // MARK: - Status Filter Bar

    private var statusFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                statusChip(nil, label: "All")
                ForEach(LeadStatus.allCases, id: \.self) { status in
                    statusChip(status, label: status.displayName)
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.vertical, SautaiDesign.spacingS)
        }
        .background(Color.white)
    }

    private func statusChip(_ status: LeadStatus?, label: String) -> some View {
        let isSelected = selectedStatus == status

        return Button {
            withAnimation(.sautaiQuick) {
                selectedStatus = status
            }
        } label: {
            Text(label)
                .font(SautaiFont.buttonSmall)
                .foregroundColor(isSelected ? .white : .sautai.slateTile)
                .padding(.horizontal, SautaiDesign.spacingM)
                .padding(.vertical, SautaiDesign.spacingS)
                .background(isSelected ? Color.sautai.earthenClay : Color.sautai.softCream)
                .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }

    // MARK: - Leads List

    private var leadsList: some View {
        List {
            ForEach(filteredLeads) { lead in
                NavigationLink {
                    LeadDetailView(lead: lead)
                } label: {
                    LeadRowView(lead: lead)
                }
                .listRowInsets(EdgeInsets(
                    top: SautaiDesign.spacingS,
                    leading: SautaiDesign.spacing,
                    bottom: SautaiDesign.spacingS,
                    trailing: SautaiDesign.spacing
                ))
                .listRowBackground(Color.clear)
            }
            .onDelete(perform: deleteLead)
        }
        .listStyle(.plain)
        .background(Color.sautai.softCream)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading leads...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "person.badge.plus")
                .font(.system(size: 60))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No leads yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Start tracking potential clients by adding your first lead")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)
                .padding(.horizontal, SautaiDesign.spacingXL)

            Button {
                showingAddLead = true
            } label: {
                Label("Add Lead", systemImage: "plus")
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingXL)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
            }
        }
        .frame(maxHeight: .infinity)
        .padding()
    }

    // MARK: - No Results View

    private var noResultsView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No leads found")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Try adjusting your search or filters")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Actions

    private func loadLeads() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getLeads()
            leads = response.results
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deleteLead(at offsets: IndexSet) {
        for index in offsets {
            let lead = filteredLeads[index]
            Task {
                try? await APIClient.shared.deleteLead(id: lead.id)
                if let idx = leads.firstIndex(where: { $0.id == lead.id }) {
                    leads.remove(at: idx)
                }
            }
        }
    }
}

// MARK: - Lead Row View

struct LeadRowView: View {
    let lead: Lead

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Avatar
            Circle()
                .fill(statusColor.opacity(0.2))
                .frame(width: SautaiDesign.avatarSize, height: SautaiDesign.avatarSize)
                .overlay(
                    Text(lead.initials)
                        .font(SautaiFont.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(statusColor)
                )

            // Info
            VStack(alignment: .leading, spacing: 2) {
                Text(lead.name)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                if let email = lead.email {
                    Text(email)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }

            Spacer()

            // Status badge
            Text(lead.status.displayName)
                .font(SautaiFont.caption2)
                .foregroundColor(statusColor)
                .padding(.horizontal, SautaiDesign.spacingS)
                .padding(.vertical, SautaiDesign.spacingXXS)
                .background(statusColor.opacity(0.1))
                .cornerRadius(SautaiDesign.cornerRadiusS)
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var statusColor: Color {
        switch lead.status {
        case .new: return .sautai.info
        case .contacted: return .sautai.earthenClay
        case .qualified: return .sautai.sunlitApricot
        case .proposal: return .sautai.pending
        case .negotiation: return .sautai.sunlitApricot
        case .won: return .sautai.success
        case .lost: return .sautai.danger
        }
    }
}

// MARK: - Add Lead View (Placeholder)

struct AddLeadView: View {
    @Environment(\.dismiss) var dismiss
    let onAdd: (Lead) -> Void

    @State private var name = ""
    @State private var email = ""
    @State private var phone = ""
    @State private var source: LeadSource = .other
    @State private var notes = ""
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Contact Info") {
                    TextField("Name *", text: $name)
                    TextField("Email", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                    TextField("Phone", text: $phone)
                        .textContentType(.telephoneNumber)
                        .keyboardType(.phonePad)
                }

                Section("Lead Info") {
                    Picker("Source", selection: $source) {
                        ForEach(LeadSource.allCases, id: \.self) { source in
                            Text(source.displayName).tag(source)
                        }
                    }

                    TextField("Notes", text: $notes, axis: .vertical)
                        .lineLimit(3...6)
                }
            }
            .navigationTitle("Add Lead")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveLead()
                    }
                    .disabled(name.isEmpty || isLoading)
                }
            }
        }
    }

    private func saveLead() {
        isLoading = true
        Task {
            do {
                var data: [String: Any] = [
                    "name": name,
                    "source": source.rawValue,
                    "status": LeadStatus.new.rawValue
                ]
                if !email.isEmpty { data["email"] = email }
                if !phone.isEmpty { data["phone_number"] = phone }
                if !notes.isEmpty { data["notes"] = notes }

                let newLead = try await APIClient.shared.createLead(data: data)
                await MainActor.run {
                    onAdd(newLead)
                    dismiss()
                }
            } catch {
                isLoading = false
            }
        }
    }
}

// MARK: - Preview

#Preview {
    LeadsListView()
}

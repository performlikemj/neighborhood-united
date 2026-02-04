//
//  LeadDetailView.swift
//  sautai_ios
//
//  Detailed view of a single lead with interactions timeline.
//

import SwiftUI

struct LeadDetailView: View {
    let lead: Lead

    @State private var currentLead: Lead
    @State private var interactions: [LeadInteraction] = []
    @State private var isLoading = true
    @State private var showingAddInteraction = false
    @State private var showingEditLead = false
    @State private var showingStatusPicker = false

    init(lead: Lead) {
        self.lead = lead
        self._currentLead = State(initialValue: lead)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                // Header Card
                headerCard

                // Contact Info
                contactInfoSection

                // Status Section
                statusSection

                // Notes
                if let notes = currentLead.notes, !notes.isEmpty {
                    notesSection(notes)
                }

                // Interactions Timeline
                interactionsSection
            }
            .padding(SautaiDesign.spacing)
        }
        .background(Color.sautai.softCream)
        .navigationTitle(currentLead.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Menu {
                    Button {
                        showingEditLead = true
                    } label: {
                        Label("Edit Lead", systemImage: "pencil")
                    }

                    Button {
                        showingAddInteraction = true
                    } label: {
                        Label("Log Interaction", systemImage: "plus.bubble")
                    }

                    if let phone = currentLead.phoneNumber {
                        Button {
                            callPhone(phone)
                        } label: {
                            Label("Call", systemImage: "phone")
                        }
                    }

                    if let email = currentLead.email {
                        Button {
                            sendEmail(email)
                        } label: {
                            Label("Email", systemImage: "envelope")
                        }
                    }
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .sheet(isPresented: $showingAddInteraction) {
            AddInteractionView(leadId: currentLead.id) { newInteraction in
                interactions.insert(newInteraction, at: 0)
            }
        }
        .task {
            await loadInteractions()
        }
    }

    // MARK: - Header Card

    private var headerCard: some View {
        HStack(spacing: SautaiDesign.spacingL) {
            // Avatar
            Circle()
                .fill(statusColor.opacity(0.2))
                .frame(width: 72, height: 72)
                .overlay(
                    Text(currentLead.initials)
                        .font(SautaiFont.title2)
                        .fontWeight(.semibold)
                        .foregroundColor(statusColor)
                )

            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                Text(currentLead.name)
                    .font(SautaiFont.title3)
                    .foregroundColor(.sautai.slateTile)

                if let source = currentLead.source {
                    Label(source.displayName, systemImage: "link")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }

                if let created = currentLead.createdAt {
                    Text("Added \(formatDate(created))")
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }

            Spacer()
        }
        .padding(SautaiDesign.spacingL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Contact Info Section

    private var contactInfoSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Contact Info")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            VStack(spacing: SautaiDesign.spacingS) {
                if let email = currentLead.email {
                    contactRow(icon: "envelope.fill", value: email, action: { sendEmail(email) })
                }

                if let phone = currentLead.phoneNumber {
                    contactRow(icon: "phone.fill", value: phone, action: { callPhone(phone) })
                }

                if currentLead.email == nil && currentLead.phoneNumber == nil {
                    Text("No contact info")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(SautaiDesign.spacing)
                        .background(Color.white)
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                }
            }
        }
    }

    private func contactRow(icon: String, value: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.sautai.earthenClay)
                    .frame(width: 24)

                Text(value)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundColor(.sautai.slateTile.opacity(0.3))
            }
            .padding(SautaiDesign.spacing)
            .background(Color.white)
            .cornerRadius(SautaiDesign.cornerRadiusS)
        }
    }

    // MARK: - Status Section

    private var statusSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Status")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Button("Change") {
                    showingStatusPicker = true
                }
                .font(SautaiFont.buttonSmall)
                .foregroundColor(.sautai.earthenClay)
            }

            HStack(spacing: SautaiDesign.spacingM) {
                Image(systemName: currentLead.status.icon)
                    .font(.system(size: 24))
                    .foregroundColor(statusColor)
                    .frame(width: 40, height: 40)
                    .background(statusColor.opacity(0.1))
                    .clipShape(Circle())

                VStack(alignment: .leading, spacing: 2) {
                    Text(currentLead.status.displayName)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if let lastContact = currentLead.lastContactAt {
                        Text("Last contact: \(formatDate(lastContact))")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                Spacer()

                if let value = currentLead.estimatedValue {
                    Text("$\(value)")
                        .font(SautaiFont.money)
                        .foregroundColor(.sautai.herbGreen)
                }
            }
            .padding(SautaiDesign.spacing)
            .background(Color.white)
            .cornerRadius(SautaiDesign.cornerRadiusS)
        }
        .confirmationDialog("Change Status", isPresented: $showingStatusPicker) {
            ForEach(LeadStatus.allCases, id: \.self) { status in
                Button(status.displayName) {
                    updateStatus(to: status)
                }
            }
        }
    }

    // MARK: - Notes Section

    private func notesSection(_ notes: String) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Notes")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(notes)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(SautaiDesign.spacing)
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadiusS)
        }
    }

    // MARK: - Interactions Section

    private var interactionsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Activity")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Button {
                    showingAddInteraction = true
                } label: {
                    Label("Log", systemImage: "plus")
                        .font(SautaiFont.buttonSmall)
                        .foregroundColor(.sautai.earthenClay)
                }
            }

            if isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else if interactions.isEmpty {
                Text("No activity yet")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(SautaiDesign.spacingL)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadiusS)
            } else {
                VStack(spacing: 0) {
                    ForEach(interactions) { interaction in
                        interactionRow(interaction)
                    }
                }
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadiusS)
            }
        }
    }

    private func interactionRow(_ interaction: LeadInteraction) -> some View {
        HStack(alignment: .top, spacing: SautaiDesign.spacingM) {
            // Icon
            Image(systemName: interaction.type.icon)
                .font(.system(size: 14))
                .foregroundColor(.sautai.earthenClay)
                .frame(width: 28, height: 28)
                .background(Color.sautai.earthenClay.opacity(0.1))
                .clipShape(Circle())

            // Content
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(interaction.type.displayName)
                        .font(SautaiFont.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.sautai.slateTile)

                    Spacer()

                    Text(formatDate(interaction.createdAt))
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }

                if let notes = interaction.notes, !notes.isEmpty {
                    Text(notes)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.8))
                }
            }
        }
        .padding(SautaiDesign.spacing)
    }

    // MARK: - Helpers

    private var statusColor: Color {
        switch currentLead.status {
        case .new: return .sautai.info
        case .contacted: return .sautai.earthenClay
        case .qualified: return .sautai.sunlitApricot
        case .proposal: return .sautai.pending
        case .negotiation: return .sautai.sunlitApricot
        case .won: return .sautai.success
        case .lost: return .sautai.danger
        }
    }

    private func formatDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    private func loadInteractions() async {
        isLoading = true
        do {
            interactions = try await APIClient.shared.getLeadInteractions(leadId: currentLead.id)
        } catch {}
        isLoading = false
    }

    private func updateStatus(to status: LeadStatus) {
        Task {
            do {
                let updated = try await APIClient.shared.updateLead(
                    id: currentLead.id,
                    data: ["status": status.rawValue]
                )
                await MainActor.run {
                    currentLead = updated
                }
            } catch {}
        }
    }

    private func callPhone(_ phone: String) {
        if let url = URL(string: "tel:\(phone.replacingOccurrences(of: " ", with: ""))") {
            UIApplication.shared.open(url)
        }
    }

    private func sendEmail(_ email: String) {
        if let url = URL(string: "mailto:\(email)") {
            UIApplication.shared.open(url)
        }
    }
}

// MARK: - Add Interaction View

struct AddInteractionView: View {
    @Environment(\.dismiss) var dismiss
    let leadId: Int
    let onAdd: (LeadInteraction) -> Void

    @State private var type: InteractionType = .note
    @State private var notes = ""
    @State private var isLoading = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Picker("Type", selection: $type) {
                        ForEach(InteractionType.allCases, id: \.self) { type in
                            Label(type.displayName, systemImage: type.icon)
                                .tag(type)
                        }
                    }
                }

                Section("Notes") {
                    TextField("What happened?", text: $notes, axis: .vertical)
                        .lineLimit(4...10)
                }
            }
            .navigationTitle("Log Activity")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveInteraction()
                    }
                    .disabled(isLoading)
                }
            }
        }
    }

    private func saveInteraction() {
        isLoading = true
        Task {
            do {
                let data: [String: Any] = [
                    "type": type.rawValue,
                    "notes": notes
                ]
                let newInteraction = try await APIClient.shared.addLeadInteraction(leadId: leadId, data: data)
                await MainActor.run {
                    onAdd(newInteraction)
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
    NavigationStack {
        LeadDetailView(lead: Lead(
            id: 1,
            name: "John Smith",
            email: "john@example.com",
            phoneNumber: "+1 555-123-4567",
            source: .referral,
            status: .qualified,
            notes: "Interested in weekly meal prep for family of 4",
            estimatedValue: "500",
            createdAt: Date().addingTimeInterval(-86400 * 7),
            lastContactAt: Date().addingTimeInterval(-86400 * 2)
        ))
    }
}

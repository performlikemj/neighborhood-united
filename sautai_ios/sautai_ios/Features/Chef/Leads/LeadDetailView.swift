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
    @State private var householdMembers: [LeadHouseholdMember] = []
    @State private var isLoading = true
    @State private var isLoadingHousehold = true
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

                // Household Members
                householdSection

                // Interactions Timeline
                interactionsSection
            }
            .padding(SautaiDesign.spacing)
        }
        .background(Color.sautai.softCream)
        .navigationTitle(currentLead.displayName)
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

                    if let phone = currentLead.phone {
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
        .sheet(isPresented: $showingEditLead) {
            EditLeadView(lead: currentLead) { updatedLead in
                currentLead = updatedLead
            }
        }
        .task {
            await loadInteractions()
            await loadHousehold()
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
                HStack {
                    Text(currentLead.displayName)
                        .font(SautaiFont.title3)
                        .foregroundColor(.sautai.slateTile)

                    if currentLead.isPriority {
                        Image(systemName: "star.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.sautai.sunlitApricot)
                    }
                }

                if let company = currentLead.company, !company.isEmpty {
                    Text(company)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

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

                if let phone = currentLead.phone {
                    contactRow(icon: "phone.fill", value: phone, action: { callPhone(phone) })
                }

                if currentLead.email == nil && currentLead.phone == nil {
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

                    if let lastContact = currentLead.lastInteractionAt {
                        Text("Last contact: \(formatDate(lastContact))")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    } else if let daysSince = currentLead.daysSinceInteraction {
                        Text("Last contact: \(daysSince) days ago")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                Spacer()

                if let budget = currentLead.budgetDisplay {
                    Text(budget)
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

    // MARK: - Household Section

    private var householdSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Household")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                if let size = currentLead.householdSize {
                    Text("(\(size) members)")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }

                Spacer()
            }

            if isLoadingHousehold {
                ProgressView()
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding()
            } else if householdMembers.isEmpty {
                Text("No household members recorded")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(SautaiDesign.spacing)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadiusS)
            } else {
                VStack(spacing: 0) {
                    ForEach(householdMembers) { member in
                        householdMemberRow(member)
                        if member.id != householdMembers.last?.id {
                            Divider()
                                .padding(.horizontal, SautaiDesign.spacing)
                        }
                    }
                }
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadiusS)
            }
        }
    }

    private func householdMemberRow(_ member: LeadHouseholdMember) -> some View {
        HStack(alignment: .top, spacing: SautaiDesign.spacingM) {
            // Icon
            Circle()
                .fill(Color.sautai.herbGreen.opacity(0.2))
                .frame(width: 36, height: 36)
                .overlay(
                    Image(systemName: memberIcon(for: member.relationship))
                        .font(.system(size: 14))
                        .foregroundColor(.sautai.herbGreen)
                )

            // Details
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(member.name)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)

                    if let age = member.age {
                        Text("(\(age))")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.6))
                    }
                }

                if let relationship = member.relationship {
                    Text(relationship.capitalized)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                // Dietary info
                if let diets = member.dietaryPreferences, !diets.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "leaf.fill")
                            .font(.system(size: 10))
                        Text(diets.joined(separator: ", "))
                            .font(SautaiFont.caption2)
                    }
                    .foregroundColor(.sautai.herbGreen)
                }

                // Allergies
                if let allergies = member.allergies, !allergies.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 10))
                        Text(allergies.joined(separator: ", "))
                            .font(SautaiFont.caption2)
                    }
                    .foregroundColor(.sautai.warning)
                }
            }

            Spacer()
        }
        .padding(SautaiDesign.spacing)
    }

    private func memberIcon(for relationship: String?) -> String {
        switch relationship?.lowercased() {
        case "spouse", "partner", "husband", "wife":
            return "heart.fill"
        case "child", "son", "daughter":
            return "figure.child"
        case "parent", "mother", "father":
            return "person.2.fill"
        default:
            return "person.fill"
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
            Image(systemName: interaction.interactionType.icon)
                .font(.system(size: 14))
                .foregroundColor(.sautai.earthenClay)
                .frame(width: 28, height: 28)
                .background(Color.sautai.earthenClay.opacity(0.1))
                .clipShape(Circle())

            // Content
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(interaction.interactionType.displayName)
                        .font(SautaiFont.caption)
                        .fontWeight(.semibold)
                        .foregroundColor(.sautai.slateTile)

                    Spacer()

                    if let date = interaction.happenedAt ?? interaction.createdAt {
                        Text(formatDate(date))
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.slateTile.opacity(0.5))
                    }
                }

                if let summary = interaction.summary, !summary.isEmpty {
                    Text(summary)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.8))
                }

                if let details = interaction.details, !details.isEmpty {
                    Text(details)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }

                if let nextSteps = interaction.nextSteps, !nextSteps.isEmpty {
                    HStack(spacing: 4) {
                        Image(systemName: "arrow.forward.circle")
                            .font(.system(size: 10))
                        Text(nextSteps)
                            .font(SautaiFont.caption)
                    }
                    .foregroundColor(.sautai.earthenClay)
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

    private func loadHousehold() async {
        isLoadingHousehold = true
        do {
            householdMembers = try await APIClient.shared.getLeadHousehold(leadId: currentLead.id)
        } catch {
            // Household might not exist yet
        }
        isLoadingHousehold = false
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
    @State private var summary = ""
    @State private var details = ""
    @State private var nextSteps = ""
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

                Section("Summary") {
                    TextField("Brief summary", text: $summary)
                }

                Section("Details (optional)") {
                    TextField("Additional details", text: $details, axis: .vertical)
                        .lineLimit(3...6)
                }

                Section("Next Steps (optional)") {
                    TextField("Follow-up actions", text: $nextSteps)
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
                    .disabled(isLoading || summary.isEmpty)
                }
            }
        }
    }

    private func saveInteraction() {
        isLoading = true
        Task {
            do {
                var data: [String: Any] = [
                    "interaction_type": type.rawValue,
                    "summary": summary
                ]
                if !details.isEmpty {
                    data["details"] = details
                }
                if !nextSteps.isEmpty {
                    data["next_steps"] = nextSteps
                }
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

// MARK: - Edit Lead View

struct EditLeadView: View {
    @Environment(\.dismiss) var dismiss
    let lead: Lead
    let onUpdate: (Lead) -> Void

    @State private var firstName: String
    @State private var lastName: String
    @State private var email: String
    @State private var phone: String
    @State private var company: String
    @State private var source: LeadSource
    @State private var status: LeadStatus
    @State private var notes: String
    @State private var isPriority: Bool
    @State private var budgetString: String
    @State private var householdSize: String
    @State private var isLoading = false
    @State private var errorMessage: String?

    init(lead: Lead, onUpdate: @escaping (Lead) -> Void) {
        self.lead = lead
        self.onUpdate = onUpdate

        // Initialize state from lead
        _firstName = State(initialValue: lead.firstName ?? "")
        _lastName = State(initialValue: lead.lastName ?? "")
        _email = State(initialValue: lead.email ?? "")
        _phone = State(initialValue: lead.phone ?? "")
        _company = State(initialValue: lead.company ?? "")
        _source = State(initialValue: lead.source ?? .other)
        _status = State(initialValue: lead.status)
        _notes = State(initialValue: lead.notes ?? "")
        _isPriority = State(initialValue: lead.isPriority)
        _budgetString = State(initialValue: lead.budgetCents.map { String($0 / 100) } ?? "")
        _householdSize = State(initialValue: lead.householdSize.map { String($0) } ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                // Contact Info Section
                Section("Contact Info") {
                    TextField("First Name *", text: $firstName)
                    TextField("Last Name", text: $lastName)
                    TextField("Email", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                    TextField("Phone", text: $phone)
                        .textContentType(.telephoneNumber)
                        .keyboardType(.phonePad)
                    TextField("Company", text: $company)
                }

                // Lead Info Section
                Section("Lead Info") {
                    Picker("Status", selection: $status) {
                        ForEach(LeadStatus.allCases, id: \.self) { status in
                            Label(status.displayName, systemImage: status.icon)
                                .tag(status)
                        }
                    }

                    Picker("Source", selection: $source) {
                        ForEach(LeadSource.allCases, id: \.self) { source in
                            Text(source.displayName).tag(source)
                        }
                    }

                    Toggle("Priority Lead", isOn: $isPriority)
                }

                // Budget & Household Section
                Section("Details") {
                    HStack {
                        Text("$")
                            .foregroundColor(.sautai.slateTile.opacity(0.5))
                        TextField("Budget", text: $budgetString)
                            .keyboardType(.numberPad)
                    }

                    HStack {
                        Text("Household Size")
                        Spacer()
                        TextField("", text: $householdSize)
                            .keyboardType(.numberPad)
                            .frame(width: 60)
                            .multilineTextAlignment(.trailing)
                    }
                }

                // Notes Section
                Section("Notes") {
                    TextField("Notes about this lead...", text: $notes, axis: .vertical)
                        .lineLimit(4...8)
                }

                // Error Display
                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                            .font(SautaiFont.caption)
                    }
                }
            }
            .navigationTitle("Edit Lead")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveLead()
                    }
                    .disabled(firstName.isEmpty || isLoading)
                }
            }
            .interactiveDismissDisabled(isLoading)
        }
    }

    private func saveLead() {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                var data: [String: Any] = [
                    "first_name": firstName,
                    "status": status.rawValue,
                    "source": source.rawValue,
                    "is_priority": isPriority
                ]

                // Optional fields
                if !lastName.isEmpty { data["last_name"] = lastName }
                if !email.isEmpty { data["email"] = email }
                if !phone.isEmpty { data["phone"] = phone }
                if !company.isEmpty { data["company"] = company }
                if !notes.isEmpty { data["notes"] = notes }

                // Parse budget
                if let budgetDollars = Int(budgetString) {
                    data["budget_cents"] = budgetDollars * 100
                }

                // Parse household size
                if let size = Int(householdSize) {
                    data["household_size"] = size
                }

                let updatedLead = try await APIClient.shared.updateLead(id: lead.id, data: data)

                await MainActor.run {
                    onUpdate(updatedLead)
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

// MARK: - Preview

#Preview {
    NavigationStack {
        LeadDetailView(lead: Lead(
            id: 1,
            firstName: "John",
            lastName: "Smith",
            email: "john@example.com",
            phone: "+1 555-123-4567",
            company: "Acme Corp",
            status: .qualified,
            source: .referral,
            isPriority: true,
            budgetCents: 50000,
            notes: "Interested in weekly meal prep for family of 4",
            daysSinceInteraction: 2,
            createdAt: Date().addingTimeInterval(-86400 * 7)
        ))
    }
}

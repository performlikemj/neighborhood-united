//
//  PaymentsView.swift
//  sautai_ios
//
//  Chef payments hub - Stripe setup, payment links, receipts.
//

import SwiftUI

struct PaymentsView: View {
    @State private var selectedTab = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Tab Selector
                Picker("View", selection: $selectedTab) {
                    Text("Overview").tag(0)
                    Text("Payment Links").tag(1)
                    Text("Receipts").tag(2)
                }
                .pickerStyle(.segmented)
                .padding(SautaiDesign.spacing)
                .background(Color.white)

                // Content
                TabView(selection: $selectedTab) {
                    PaymentsOverviewView()
                        .tag(0)

                    PaymentLinksView()
                        .tag(1)

                    ReceiptsView()
                        .tag(2)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Payments")
        }
    }
}

// MARK: - Payments Overview View

struct PaymentsOverviewView: View {
    @State private var stripeStatus: StripeAccountStatus?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var isSettingUp = false

    var body: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else if let status = stripeStatus {
                    // Stripe Status Card
                    stripeStatusCard(status)

                    // Quick Stats
                    if status.isActive {
                        statsSection(status)
                    }

                    // Setup Instructions
                    if !status.isActive {
                        setupInstructionsCard(status)
                    }
                }
            }
            .padding(SautaiDesign.spacing)
        }
        .refreshable {
            await loadStatus()
        }
        .task {
            await loadStatus()
        }
    }

    // MARK: - Stripe Status Card

    private func stripeStatusCard(_ status: StripeAccountStatus) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Icon
            ZStack {
                Circle()
                    .fill(statusColor(status).opacity(0.15))
                    .frame(width: 64, height: 64)

                Image(systemName: statusIcon(status))
                    .font(.system(size: 28))
                    .foregroundColor(statusColor(status))
            }

            // Status Text
            VStack(spacing: SautaiDesign.spacingXS) {
                Text(statusTitle(status))
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Text(statusSubtitle(status))
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
                    .multilineTextAlignment(.center)
            }

            // Action Button
            if !status.isActive {
                Button {
                    setupStripeAccount()
                } label: {
                    HStack {
                        if isSettingUp {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Image(systemName: "creditcard")
                            Text(status.accountId == nil ? "Set Up Payments" : "Continue Setup")
                        }
                    }
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.sautai.earthenClay)
                .disabled(isSettingUp)
            }

            // Capabilities
            if status.isActive {
                HStack(spacing: SautaiDesign.spacingL) {
                    capabilityBadge(
                        title: "Card Payments",
                        isActive: status.chargesEnabled,
                        icon: "creditcard"
                    )
                    capabilityBadge(
                        title: "Payouts",
                        isActive: status.payoutsEnabled,
                        icon: "banknote"
                    )
                }
            }
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func capabilityBadge(title: String, isActive: Bool, icon: String) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(isActive ? .sautai.success : .sautai.slateTile.opacity(0.3))

            Text(title)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Image(systemName: isActive ? "checkmark.circle.fill" : "xmark.circle")
                .font(.caption)
                .foregroundColor(isActive ? .sautai.success : .sautai.slateTile.opacity(0.3))
        }
    }

    // MARK: - Stats Section

    private func statsSection(_ status: StripeAccountStatus) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Account Balance")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            HStack(spacing: SautaiDesign.spacingM) {
                balanceCard(
                    title: "Available",
                    amount: status.availableBalance ?? "$0.00",
                    color: .sautai.success
                )
                balanceCard(
                    title: "Pending",
                    amount: status.pendingBalance ?? "$0.00",
                    color: .sautai.warning
                )
            }
        }
    }

    private func balanceCard(title: String, amount: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
            Text(title)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Text(amount)
                .font(SautaiFont.title2)
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Setup Instructions

    private func setupInstructionsCard(_ status: StripeAccountStatus) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Why Set Up Payments?")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                benefitRow(icon: "creditcard", text: "Accept credit card payments from customers")
                benefitRow(icon: "link", text: "Send secure payment links via text or email")
                benefitRow(icon: "banknote", text: "Get paid directly to your bank account")
                benefitRow(icon: "lock.shield", text: "Secure, PCI-compliant payment processing")
            }

            if let requirements = status.pendingRequirements, !requirements.isEmpty {
                Divider()

                VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                    Text("Pending Requirements")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.warning)

                    ForEach(requirements, id: \.self) { req in
                        HStack(spacing: SautaiDesign.spacingS) {
                            Image(systemName: "exclamationmark.circle")
                                .foregroundColor(.sautai.warning)
                            Text(req)
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.8))
                        }
                    }
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func benefitRow(icon: String, text: String) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: icon)
                .foregroundColor(.sautai.herbGreen)
                .frame(width: 24)

            Text(text)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.8))
        }
    }

    // MARK: - Helper Methods

    private func statusColor(_ status: StripeAccountStatus) -> Color {
        if status.isActive { return .sautai.success }
        if status.accountId != nil { return .sautai.warning }
        return .sautai.slateTile
    }

    private func statusIcon(_ status: StripeAccountStatus) -> String {
        if status.isActive { return "checkmark.circle.fill" }
        if status.accountId != nil { return "clock.fill" }
        return "creditcard.circle"
    }

    private func statusTitle(_ status: StripeAccountStatus) -> String {
        if status.isActive { return "Payments Active" }
        if status.accountId != nil { return "Setup Incomplete" }
        return "Payments Not Set Up"
    }

    private func statusSubtitle(_ status: StripeAccountStatus) -> String {
        if status.isActive { return "You can accept payments and send payment links." }
        if status.accountId != nil { return "Complete setup to start accepting payments." }
        return "Set up Stripe to accept payments from customers."
    }

    // MARK: - Loading & Error

    private var loadingView: some View {
        VStack {
            ProgressView()
                .scaleEffect(1.5)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load payment status")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadStatus() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .padding()
    }

    // MARK: - Actions

    private func loadStatus() async {
        isLoading = true
        error = nil

        do {
            stripeStatus = try await APIClient.shared.getStripeAccountStatus()
        } catch {
            self.error = error
        }

        isLoading = false
    }

    private func setupStripeAccount() {
        isSettingUp = true

        Task {
            do {
                let link = try await APIClient.shared.createStripeAccountLink()
                // Open the Stripe onboarding URL
                if let url = URL(string: link.url) {
                    await MainActor.run {
                        UIApplication.shared.open(url)
                    }
                }
            } catch {
                self.error = error
            }

            await MainActor.run {
                isSettingUp = false
            }
        }
    }
}

// MARK: - Payment Links View

struct PaymentLinksView: View {
    @State private var paymentLinks: [PaymentLink] = []
    @State private var stats: PaymentLinkStats?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingCreateSheet = false

    var body: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else {
                    // Stats Card
                    if let stats = stats {
                        statsCard(stats)
                    }

                    // Create Button
                    Button {
                        showingCreateSheet = true
                    } label: {
                        Label("Create Payment Link", systemImage: "plus.circle")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.sautai.earthenClay)

                    // Links List
                    if paymentLinks.isEmpty {
                        emptyStateView
                    } else {
                        linksSection
                    }
                }
            }
            .padding(SautaiDesign.spacing)
        }
        .sheet(isPresented: $showingCreateSheet) {
            CreatePaymentLinkView { newLink in
                paymentLinks.insert(newLink, at: 0)
            }
        }
        .refreshable {
            await loadData()
        }
        .task {
            await loadData()
        }
    }

    // MARK: - Stats Card

    private func statsCard(_ stats: PaymentLinkStats) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            statItem(value: "\(stats.totalLinks)", label: "Total Links", color: .sautai.earthenClay)
            statItem(value: "\(stats.activeLinks)", label: "Active", color: .sautai.herbGreen)
            statItem(value: stats.totalCollected, label: "Collected", color: .sautai.success)
        }
    }

    private func statItem(value: String, label: String, color: Color) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            Text(value)
                .font(SautaiFont.title2)
                .foregroundColor(color)
            Text(label)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Links Section

    private var linksSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Payment Links")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(paymentLinks) { link in
                PaymentLinkRow(link: link) {
                    sendLink(link)
                }
            }
        }
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "link.circle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No Payment Links")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Create payment links to send to customers for easy payment collection.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Loading & Error

    private var loadingView: some View {
        VStack {
            ProgressView()
                .scaleEffect(1.5)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadData() }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    // MARK: - Actions

    private func loadData() async {
        isLoading = true
        error = nil

        do {
            async let linksTask = APIClient.shared.getPaymentLinks()
            async let statsTask = APIClient.shared.getPaymentLinkStats()

            let (linksResponse, statsResult) = try await (linksTask, statsTask)
            paymentLinks = linksResponse.results
            stats = statsResult
        } catch {
            self.error = error
        }

        isLoading = false
    }

    private func sendLink(_ link: PaymentLink) {
        Task {
            do {
                try await APIClient.shared.sendPaymentLink(id: link.id, method: "sms")
            } catch {
                self.error = error
            }
        }
    }
}

// MARK: - Payment Link Row

struct PaymentLinkRow: View {
    let link: PaymentLink
    let onSend: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(link.description ?? "Payment Link")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if let customer = link.clientName {
                        Text(customer)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                Spacer()

                Text(link.displayAmount)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.herbGreen)
            }

            HStack {
                // Status
                HStack(spacing: 4) {
                    Circle()
                        .fill(statusColor(link.status))
                        .frame(width: 8, height: 8)

                    Text(link.status.displayName)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                Spacer()

                // Created Date
                if let date = link.createdAt {
                    Text(date.formatted(date: .abbreviated, time: .omitted))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }

                // Send Button
                if link.status == .active {
                    Button {
                        onSend()
                    } label: {
                        Image(systemName: "paperplane")
                            .font(.caption)
                            .foregroundColor(.sautai.earthenClay)
                            .padding(SautaiDesign.spacingS)
                            .background(Color.sautai.earthenClay.opacity(0.1))
                            .cornerRadius(SautaiDesign.cornerRadiusS)
                    }
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func statusColor(_ status: PaymentLinkStatus) -> Color {
        switch status {
        case .draft: return .sautai.slateTile
        case .active: return .sautai.herbGreen
        case .sent: return .sautai.info
        case .viewed: return .sautai.warning
        case .paid: return .sautai.success
        case .expired: return .sautai.warning
        case .cancelled: return .sautai.danger
        }
    }
}

// MARK: - Create Payment Link View

struct CreatePaymentLinkView: View {
    @Environment(\.dismiss) var dismiss
    let onCreated: (PaymentLink) -> Void

    @State private var amount = ""
    @State private var description = ""
    @State private var customerName = ""
    @State private var customerPhone = ""
    @State private var expiresInDays = 7
    @State private var isCreating = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Payment Details") {
                    HStack {
                        Text("$")
                            .foregroundColor(.sautai.slateTile)
                        TextField("Amount", text: $amount)
                            .keyboardType(.decimalPad)
                    }

                    TextField("Description (optional)", text: $description)
                }

                Section("Customer (Optional)") {
                    TextField("Customer Name", text: $customerName)
                    TextField("Phone Number", text: $customerPhone)
                        .keyboardType(.phonePad)
                }

                Section("Expiration") {
                    Stepper("Expires in \(expiresInDays) days", value: $expiresInDays, in: 1...30)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Create Payment Link")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        createLink()
                    }
                    .disabled(amount.isEmpty || isCreating)
                }
            }
        }
    }

    private func createLink() {
        guard let amountDecimal = Decimal(string: amount) else {
            errorMessage = "Invalid amount"
            return
        }

        isCreating = true
        errorMessage = nil

        let request = PaymentLinkCreateRequest(
            amount: amountDecimal,
            description: description.isEmpty ? nil : description,
            customerName: customerName.isEmpty ? nil : customerName,
            customerPhone: customerPhone.isEmpty ? nil : customerPhone,
            expiresInDays: expiresInDays
        )

        Task {
            do {
                let newLink = try await APIClient.shared.createPaymentLink(data: request)
                await MainActor.run {
                    onCreated(newLink)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isCreating = false
                }
            }
        }
    }
}

// MARK: - Receipts View

struct ReceiptsView: View {
    @State private var receipts: [Receipt] = []
    @State private var stats: ReceiptStats?
    @State private var isLoading = true
    @State private var error: Error?

    var body: some View {
        ScrollView {
            VStack(spacing: SautaiDesign.spacingL) {
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else {
                    // Stats
                    if let stats = stats {
                        statsSection(stats)
                    }

                    // Receipts List
                    if receipts.isEmpty {
                        emptyStateView
                    } else {
                        receiptsSection
                    }
                }
            }
            .padding(SautaiDesign.spacing)
        }
        .refreshable {
            await loadData()
        }
        .task {
            await loadData()
        }
    }

    // MARK: - Stats Section

    private func statsSection(_ stats: ReceiptStats) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("This Month")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            HStack(spacing: SautaiDesign.spacingM) {
                statCard(value: stats.totalRevenue, label: "Revenue", color: .sautai.success)
                statCard(value: "\(stats.totalOrders)", label: "Orders", color: .sautai.earthenClay)
            }
        }
    }

    private func statCard(value: String, label: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
            Text(label)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Text(value)
                .font(SautaiFont.title2)
                .foregroundColor(color)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Receipts Section

    private var receiptsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Recent Receipts")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(receipts) { receipt in
                ReceiptRow(receipt: receipt)
            }
        }
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "doc.text")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No Receipts Yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Receipts will appear here after customers pay for orders.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Loading & Error

    private var loadingView: some View {
        VStack {
            ProgressView()
                .scaleEffect(1.5)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadData() }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }

    // MARK: - Load Data

    private func loadData() async {
        isLoading = true
        error = nil

        do {
            async let receiptsTask = APIClient.shared.getReceipts()
            async let statsTask = APIClient.shared.getReceiptStats()

            let (receiptsResponse, statsResult) = try await (receiptsTask, statsTask)
            receipts = receiptsResponse.results
            stats = statsResult
        } catch {
            self.error = error
        }

        isLoading = false
    }
}

// MARK: - Receipt Row

struct ReceiptRow: View {
    let receipt: Receipt

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(receipt.clientName ?? "Customer")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Text("Receipt #\(receipt.receiptNumber ?? String(receipt.id))")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))

                if let date = receipt.paidAt {
                    Text(date.formatted(date: .abbreviated, time: .shortened))
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                Text(receipt.displayTotal)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.success)

                HStack(spacing: 4) {
                    Circle()
                        .fill(statusColor(receipt.status))
                        .frame(width: 6, height: 6)

                    Text(receipt.status.displayName)
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func statusColor(_ status: ReceiptStatus) -> Color {
        switch status {
        case .paid: return .sautai.success
        case .pending: return .sautai.warning
        case .refunded, .partialRefund: return .sautai.info
        case .failed: return .sautai.danger
        }
    }
}

#Preview {
    PaymentsView()
}

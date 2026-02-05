//
//  TelegramLinkingView.swift
//  sautai_ios
//
//  Link/unlink Telegram account and manage notification settings.
//

import SwiftUI
import CoreImage.CIFilterBuiltins

struct TelegramLinkingView: View {
    @State private var isLoading = true
    @State private var isLinked = false
    @State private var telegramUsername: String?
    @State private var linkedAt: Date?
    @State private var settings = TelegramSettings()

    // Link code state
    @State private var linkCode: String?
    @State private var botUsername: String?
    @State private var expiresAt: Date?
    @State private var isGeneratingLink = false

    // UI state
    @State private var isSaving = false
    @State private var showUnlinkConfirmation = false
    @State private var error: Error?
    @State private var showError = false

    // Time pickers
    @State private var quietStart = Date()
    @State private var quietEnd = Date()

    var body: some View {
        List {
            if isLoading {
                Section {
                    HStack {
                        Spacer()
                        ProgressView()
                            .padding()
                        Spacer()
                    }
                }
            } else if isLinked {
                linkedSection
                notificationSettingsSection
                quietHoursSection
                unlinkSection
            } else {
                notLinkedSection
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.sautai.softCream)
        .navigationTitle("Telegram")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await loadStatus()
        }
        .alert("Error", isPresented: $showError) {
            Button("OK") {}
        } message: {
            Text(error?.localizedDescription ?? "An error occurred")
        }
        .confirmationDialog(
            "Unlink Telegram",
            isPresented: $showUnlinkConfirmation,
            titleVisibility: .visible
        ) {
            Button("Unlink", role: .destructive) {
                Task { await unlinkTelegram() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("You will stop receiving notifications via Telegram. You can link again anytime.")
        }
    }

    // MARK: - Linked Section

    private var linkedSection: some View {
        Section {
            HStack(spacing: SautaiDesign.spacingM) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 40))
                    .foregroundColor(.sautai.success)

                VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                    Text("Connected")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if let username = telegramUsername {
                        Text("@\(username)")
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.herbGreen)
                    }

                    if let date = linkedAt {
                        Text("Linked \(formatDate(date))")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                Spacer()
            }
            .padding(.vertical, SautaiDesign.spacingS)
        } header: {
            Text("Status")
        } footer: {
            Text("You'll receive notifications about orders, messages, and schedule reminders through Telegram.")
        }
    }

    // MARK: - Notification Settings Section

    private var notificationSettingsSection: some View {
        Section {
            Toggle(isOn: $settings.notifyNewOrders) {
                Label("New Orders", systemImage: "cart.fill")
            }
            .onChange(of: settings.notifyNewOrders) { _, _ in
                saveSettingsDebounced()
            }

            Toggle(isOn: $settings.notifyOrderUpdates) {
                Label("Order Updates", systemImage: "arrow.triangle.2.circlepath")
            }
            .onChange(of: settings.notifyOrderUpdates) { _, _ in
                saveSettingsDebounced()
            }

            Toggle(isOn: $settings.notifyScheduleReminders) {
                Label("Schedule Reminders", systemImage: "calendar.badge.clock")
            }
            .onChange(of: settings.notifyScheduleReminders) { _, _ in
                saveSettingsDebounced()
            }

            Toggle(isOn: $settings.notifyCustomerMessages) {
                Label("Customer Messages", systemImage: "message.fill")
            }
            .onChange(of: settings.notifyCustomerMessages) { _, _ in
                saveSettingsDebounced()
            }
        } header: {
            Text("Notifications")
        }
        .tint(.sautai.herbGreen)
    }

    // MARK: - Quiet Hours Section

    private var quietHoursSection: some View {
        Section {
            Toggle(isOn: $settings.quietHoursEnabled) {
                Label("Quiet Hours", systemImage: "moon.fill")
            }
            .onChange(of: settings.quietHoursEnabled) { _, _ in
                saveSettingsDebounced()
            }

            if settings.quietHoursEnabled {
                DatePicker(
                    "Start",
                    selection: $quietStart,
                    displayedComponents: .hourAndMinute
                )
                .onChange(of: quietStart) { _, newValue in
                    settings.quietHoursStart = formatTimeForAPI(newValue)
                    saveSettingsDebounced()
                }

                DatePicker(
                    "End",
                    selection: $quietEnd,
                    displayedComponents: .hourAndMinute
                )
                .onChange(of: quietEnd) { _, newValue in
                    settings.quietHoursEnd = formatTimeForAPI(newValue)
                    saveSettingsDebounced()
                }
            }
        } header: {
            Text("Do Not Disturb")
        } footer: {
            if settings.quietHoursEnabled {
                Text("Notifications will be paused during quiet hours.")
            }
        }
        .tint(.sautai.herbGreen)
    }

    // MARK: - Unlink Section

    private var unlinkSection: some View {
        Section {
            Button(role: .destructive) {
                showUnlinkConfirmation = true
            } label: {
                HStack {
                    Spacer()
                    Text("Unlink Telegram")
                        .font(SautaiFont.button)
                    Spacer()
                }
            }
        }
    }

    // MARK: - Not Linked Section

    private var notLinkedSection: some View {
        Group {
            Section {
                VStack(spacing: SautaiDesign.spacingL) {
                    Image(systemName: "paperplane.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.sautai.earthenClay)

                    Text("Connect Telegram")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    Text("Get instant notifications about orders, messages, and schedule reminders directly in Telegram.")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                        .multilineTextAlignment(.center)
                }
                .padding(.vertical, SautaiDesign.spacingL)
                .frame(maxWidth: .infinity)
            }

            if let code = linkCode, let bot = botUsername {
                Section {
                    // QR Code
                    VStack(spacing: SautaiDesign.spacingM) {
                        if let qrImage = generateQRCode(from: "https://t.me/\(bot)?start=\(code)") {
                            Image(uiImage: qrImage)
                                .interpolation(.none)
                                .resizable()
                                .scaledToFit()
                                .frame(width: 200, height: 200)
                                .cornerRadius(SautaiDesign.cornerRadius)
                        }

                        Text("Scan with Telegram")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))

                        if let expires = expiresAt {
                            ExpirationCountdown(expiresAt: expires) {
                                Task { await generateLink() }
                            }
                        }
                    }
                    .padding(.vertical, SautaiDesign.spacingM)
                    .frame(maxWidth: .infinity)
                } header: {
                    Text("QR Code")
                }

                Section {
                    Button {
                        openTelegramLink()
                    } label: {
                        HStack {
                            Image(systemName: "arrow.up.right.circle.fill")
                            Text("Open in Telegram")
                        }
                        .font(SautaiFont.button)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: SautaiDesign.buttonHeight)
                        .background(Color(red: 0.0, green: 0.54, blue: 0.89)) // Telegram blue
                        .cornerRadius(SautaiDesign.cornerRadius)
                    }
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
                }
            } else {
                Section {
                    Button {
                        Task { await generateLink() }
                    } label: {
                        HStack {
                            if isGeneratingLink {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "link")
                                Text("Generate Link")
                            }
                        }
                        .font(SautaiFont.button)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: SautaiDesign.buttonHeight)
                        .background(Color.sautai.earthenClay)
                        .cornerRadius(SautaiDesign.cornerRadius)
                    }
                    .disabled(isGeneratingLink)
                    .listRowInsets(EdgeInsets())
                    .listRowBackground(Color.clear)
                }
            }
        }
    }

    // MARK: - Actions

    private func loadStatus() async {
        isLoading = true
        do {
            let status = try await APIClient.shared.getTelegramFullStatus()
            isLinked = status.linked
            telegramUsername = status.telegramUsername
            linkedAt = status.linkedAt
            if let s = status.settings {
                settings = s
                // Parse quiet hours times
                if let start = s.quietHoursStart {
                    quietStart = parseTime(start) ?? Date()
                }
                if let end = s.quietHoursEnd {
                    quietEnd = parseTime(end) ?? Date()
                }
            }
        } catch {
            // Fallback to basic status
            do {
                let basicStatus = try await APIClient.shared.getTelegramStatus()
                isLinked = basicStatus.isLinked
                telegramUsername = basicStatus.username
                linkedAt = basicStatus.linkedAt
            } catch {
                self.error = error
                showError = true
            }
        }
        isLoading = false

        // Generate link if not linked
        if !isLinked {
            await generateLink()
        }
    }

    private func generateLink() async {
        isGeneratingLink = true
        do {
            let response = try await APIClient.shared.generateTelegramLink()
            linkCode = response.linkCode
            botUsername = response.botUsername
            expiresAt = response.expiresAt
        } catch {
            self.error = error
            showError = true
        }
        isGeneratingLink = false
    }

    private var saveTask: Task<Void, Never>?

    private func saveSettingsDebounced() {
        // Simple debounce - save after toggle changes
        Task {
            try? await Task.sleep(nanoseconds: 500_000_000) // 0.5s debounce
            await saveSettings()
        }
    }

    private func saveSettings() async {
        isSaving = true
        do {
            settings = try await APIClient.shared.updateTelegramSettings(data: settings)
        } catch {
            self.error = error
            showError = true
        }
        isSaving = false
    }

    private func unlinkTelegram() async {
        do {
            try await APIClient.shared.unlinkTelegram()
            isLinked = false
            telegramUsername = nil
            linkedAt = nil
            linkCode = nil
            await generateLink()
        } catch {
            self.error = error
            showError = true
        }
    }

    private func openTelegramLink() {
        guard let code = linkCode, let bot = botUsername else { return }
        let urlString = "tg://resolve?domain=\(bot)&start=\(code)"
        if let url = URL(string: urlString) {
            UIApplication.shared.open(url)
        }
    }

    // MARK: - Helpers

    private func formatDate(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    private func formatTimeForAPI(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }

    private func parseTime(_ timeString: String) -> Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.date(from: timeString)
    }

    private func generateQRCode(from string: String) -> UIImage? {
        let context = CIContext()
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(string.utf8)

        guard let outputImage = filter.outputImage else { return nil }

        // Scale up the QR code
        let scale = CGAffineTransform(scaleX: 10, y: 10)
        let scaledImage = outputImage.transformed(by: scale)

        guard let cgImage = context.createCGImage(scaledImage, from: scaledImage.extent) else {
            return nil
        }

        return UIImage(cgImage: cgImage)
    }
}

// MARK: - Expiration Countdown

struct ExpirationCountdown: View {
    let expiresAt: Date
    let onExpire: () -> Void

    @State private var timeRemaining: TimeInterval = 0
    @State private var timer: Timer?

    var body: some View {
        HStack {
            if timeRemaining > 0 {
                Image(systemName: "clock")
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                Text("Expires in \(formatCountdown(timeRemaining))")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            } else {
                Button {
                    onExpire()
                } label: {
                    HStack {
                        Image(systemName: "arrow.clockwise")
                        Text("Code expired - Tap to refresh")
                    }
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .onAppear {
            updateTimeRemaining()
            timer = Timer.scheduledTimer(withTimeInterval: 1, repeats: true) { _ in
                updateTimeRemaining()
            }
        }
        .onDisappear {
            timer?.invalidate()
            timer = nil
        }
    }

    private func updateTimeRemaining() {
        timeRemaining = expiresAt.timeIntervalSinceNow
        if timeRemaining <= 0 {
            timer?.invalidate()
            timer = nil
        }
    }

    private func formatCountdown(_ interval: TimeInterval) -> String {
        let minutes = Int(interval) / 60
        let seconds = Int(interval) % 60
        return String(format: "%d:%02d", minutes, seconds)
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        TelegramLinkingView()
    }
}

//
//  NotificationsView.swift
//  sautai_ios
//
//  In-app notifications list.
//

import SwiftUI

struct NotificationsView: View {
    @State private var notifications: [AppNotification] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingPreferences = false

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    loadingView
                } else if let error = error {
                    errorView(error)
                } else if notifications.isEmpty {
                    emptyStateView
                } else {
                    notificationsList
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Notifications")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button {
                            showingPreferences = true
                        } label: {
                            Label("Preferences", systemImage: "gearshape")
                        }

                        if notifications.contains(where: { !$0.isRead }) {
                            Button {
                                Task { await markAllRead() }
                            } label: {
                                Label("Mark All Read", systemImage: "checkmark.circle")
                            }
                        }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .sheet(isPresented: $showingPreferences) {
                NotificationPreferencesView()
            }
            .refreshable {
                await loadNotifications()
            }
        }
        .task {
            await loadNotifications()
        }
    }

    // MARK: - Notifications List

    private var notificationsList: some View {
        ScrollView {
            LazyVStack(spacing: SautaiDesign.spacingS) {
                ForEach(notifications) { notification in
                    NotificationRowView(notification: notification) {
                        handleNotificationTap(notification)
                    } onDismiss: {
                        dismissNotification(notification)
                    }
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView()
                .scaleEffect(1.5)
            Spacer()
        }
    }

    // MARK: - Error View

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load notifications")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button("Try Again") {
                Task { await loadNotifications() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)

            Spacer()
        }
        .padding()
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Spacer()
            Image(systemName: "bell.slash")
                .font(.system(size: 64))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No Notifications")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("You're all caught up!")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Spacer()
        }
        .padding()
    }

    // MARK: - Actions

    private func loadNotifications() async {
        isLoading = true
        error = nil

        do {
            let response = try await APIClient.shared.getNotifications()
            notifications = response.results
        } catch {
            self.error = error
        }

        isLoading = false
    }

    private func markAllRead() async {
        do {
            try await APIClient.shared.markAllNotificationsRead()
            // Update local state
            for index in notifications.indices {
                notifications[index] = AppNotification(
                    id: notifications[index].id,
                    type: notifications[index].type,
                    title: notifications[index].title,
                    message: notifications[index].message,
                    data: notifications[index].data,
                    isRead: true,
                    isDismissed: notifications[index].isDismissed,
                    createdAt: notifications[index].createdAt,
                    readAt: Date()
                )
            }
        } catch {
            self.error = error
        }
    }

    private func handleNotificationTap(_ notification: AppNotification) {
        // Mark as read
        if !notification.isRead {
            Task {
                try? await APIClient.shared.markNotificationRead(id: notification.id)
            }
        }

        // Handle navigation based on notification type/data
        // This would typically use NavigationPath or similar
    }

    private func dismissNotification(_ notification: AppNotification) {
        Task {
            do {
                try await APIClient.shared.dismissNotification(id: notification.id)
                notifications.removeAll { $0.id == notification.id }
            } catch {
                self.error = error
            }
        }
    }
}

// MARK: - Notification Row View

struct NotificationRowView: View {
    let notification: AppNotification
    let onTap: () -> Void
    let onDismiss: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(alignment: .top, spacing: SautaiDesign.spacingM) {
                // Icon
                Circle()
                    .fill(typeColor.opacity(0.15))
                    .frame(width: 44, height: 44)
                    .overlay(
                        Image(systemName: notification.type.icon)
                            .foregroundColor(typeColor)
                    )

                // Content
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    HStack {
                        Text(notification.title)
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.slateTile)

                        Spacer()

                        Text(notification.timeAgo)
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.slateTile.opacity(0.5))
                    }

                    Text(notification.message)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.8))
                        .lineLimit(2)
                }

                // Unread indicator
                if !notification.isRead {
                    Circle()
                        .fill(Color.sautai.earthenClay)
                        .frame(width: 8, height: 8)
                }
            }
            .padding(SautaiDesign.spacing)
            .background(notification.isRead ? Color.white : Color.sautai.earthenClay.opacity(0.03))
            .cornerRadius(SautaiDesign.cornerRadius)
            .sautaiShadow(SautaiDesign.shadowSubtle)
        }
        .buttonStyle(.plain)
        .swipeActions(edge: .trailing) {
            Button(role: .destructive) {
                onDismiss()
            } label: {
                Label("Dismiss", systemImage: "xmark")
            }
        }
    }

    private var typeColor: Color {
        switch notification.type.color {
        case "success": return .sautai.success
        case "warning": return .sautai.warning
        case "danger": return .sautai.danger
        case "info": return .sautai.info
        case "herbGreen": return .sautai.herbGreen
        case "sunlitApricot": return .sautai.sunlitApricot
        default: return .sautai.slateTile
        }
    }
}

// MARK: - Notification Preferences View

struct NotificationPreferencesView: View {
    @Environment(\.dismiss) var dismiss
    @State private var preferences = NotificationPreferences.defaults
    @State private var isLoading = true
    @State private var isSaving = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Delivery Methods") {
                    Toggle("Push Notifications", isOn: $preferences.pushEnabled)
                    Toggle("Email Notifications", isOn: $preferences.emailEnabled)
                    Toggle("SMS Notifications", isOn: $preferences.smsEnabled)
                }

                Section("Notification Types") {
                    Toggle("Orders", isOn: $preferences.orderNotifications)
                    Toggle("Messages", isOn: $preferences.messageNotifications)
                    Toggle("Reviews", isOn: $preferences.reviewNotifications)
                    Toggle("Meal Plans", isOn: $preferences.planNotifications)
                    Toggle("Payments", isOn: $preferences.paymentNotifications)
                    Toggle("Reminders", isOn: $preferences.reminderNotifications)
                    Toggle("Marketing", isOn: $preferences.marketingNotifications)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Notification Preferences")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        savePreferences()
                    }
                    .disabled(isSaving)
                }
            }
            .overlay {
                if isLoading {
                    ProgressView()
                }
            }
        }
        .task {
            await loadPreferences()
        }
    }

    private func loadPreferences() async {
        isLoading = true
        do {
            preferences = try await APIClient.shared.getNotificationPreferences()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    private func savePreferences() {
        isSaving = true
        errorMessage = nil

        Task {
            do {
                preferences = try await APIClient.shared.updateNotificationPreferences(data: preferences)
                await MainActor.run {
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
    NotificationsView()
}

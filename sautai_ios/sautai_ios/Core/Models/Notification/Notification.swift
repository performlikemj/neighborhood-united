//
//  Notification.swift
//  sautai_ios
//
//  Notification models for in-app notifications.
//

import Foundation

// MARK: - App Notification

struct AppNotification: Codable, Identifiable {
    let id: Int
    let type: NotificationType
    let title: String
    let message: String
    let data: NotificationData?
    let isRead: Bool
    let isDismissed: Bool
    let createdAt: Date
    let readAt: Date?

    var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: createdAt, relativeTo: Date())
    }
}

// MARK: - Notification Type

enum NotificationType: String, Codable {
    case newOrder = "new_order"
    case orderConfirmed = "order_confirmed"
    case orderCancelled = "order_cancelled"
    case orderReady = "order_ready"
    case newMessage = "new_message"
    case newReview = "new_review"
    case planSuggestion = "plan_suggestion"
    case suggestionResponse = "suggestion_response"
    case paymentReceived = "payment_received"
    case documentExpiring = "document_expiring"
    case eventReminder = "event_reminder"
    case leadActivity = "lead_activity"
    case systemAlert = "system_alert"
    case general

    var icon: String {
        switch self {
        case .newOrder: return "bag.fill"
        case .orderConfirmed: return "checkmark.circle.fill"
        case .orderCancelled: return "xmark.circle.fill"
        case .orderReady: return "bell.fill"
        case .newMessage: return "message.fill"
        case .newReview: return "star.fill"
        case .planSuggestion: return "lightbulb.fill"
        case .suggestionResponse: return "arrow.turn.down.left"
        case .paymentReceived: return "dollarsign.circle.fill"
        case .documentExpiring: return "doc.badge.clock"
        case .eventReminder: return "calendar.badge.clock"
        case .leadActivity: return "person.badge.plus"
        case .systemAlert: return "exclamationmark.triangle.fill"
        case .general: return "bell.fill"
        }
    }

    var color: String {
        switch self {
        case .newOrder, .orderReady: return "warning"
        case .orderConfirmed, .paymentReceived: return "success"
        case .orderCancelled, .documentExpiring, .systemAlert: return "danger"
        case .newMessage, .newReview: return "info"
        case .planSuggestion, .suggestionResponse: return "herbGreen"
        case .eventReminder, .leadActivity: return "sunlitApricot"
        case .general: return "slateTile"
        }
    }
}

// MARK: - Notification Data

struct NotificationData: Codable {
    let orderId: Int?
    let eventId: Int?
    let conversationId: Int?
    let reviewId: Int?
    let planId: Int?
    let suggestionId: Int?
    let leadId: Int?
    let clientId: Int?
    let documentId: Int?
    let url: String?

    var hasDeepLink: Bool {
        orderId != nil || eventId != nil || conversationId != nil ||
        reviewId != nil || planId != nil || leadId != nil || clientId != nil
    }
}

// MARK: - Notification Preferences

struct NotificationPreferences: Codable {
    var pushEnabled: Bool
    var emailEnabled: Bool
    var smsEnabled: Bool

    var orderNotifications: Bool
    var messageNotifications: Bool
    var reviewNotifications: Bool
    var planNotifications: Bool
    var paymentNotifications: Bool
    var reminderNotifications: Bool
    var marketingNotifications: Bool

    static var defaults: NotificationPreferences {
        NotificationPreferences(
            pushEnabled: true,
            emailEnabled: true,
            smsEnabled: false,
            orderNotifications: true,
            messageNotifications: true,
            reviewNotifications: true,
            planNotifications: true,
            paymentNotifications: true,
            reminderNotifications: true,
            marketingNotifications: false
        )
    }
}

// MARK: - Notification Badge

struct NotificationBadge: Codable {
    let unreadCount: Int
    let hasUrgent: Bool
}

//
//  ProactiveInsight.swift
//  sautai_ios
//
//  Proactive insights from the AI engine for chef notifications.
//

import Foundation

// MARK: - Proactive Insight

struct ProactiveInsight: Codable, Identifiable {
    let id: Int
    let type: InsightType
    let priority: InsightPriority
    let title: String
    let message: String
    let actionLabel: String?
    let actionUrl: String?
    let metadata: [String: String]?
    let createdAt: Date
    let expiresAt: Date?
    let isDismissed: Bool
    let isActedOn: Bool

    var isExpired: Bool {
        guard let expires = expiresAt else { return false }
        return expires < Date()
    }

    var isActive: Bool {
        !isDismissed && !isActedOn && !isExpired
    }
}

// MARK: - Insight Type

enum InsightType: String, Codable {
    case clientBirthday = "client_birthday"
    case clientAnniversary = "client_anniversary"
    case seasonalIngredient = "seasonal_ingredient"
    case reorderSuggestion = "reorder_suggestion"
    case priceChange = "price_change"
    case lowStock = "low_stock"
    case clientInactive = "client_inactive"
    case menuSuggestion = "menu_suggestion"
    case weatherAlert = "weather_alert"
    case other

    var displayName: String {
        switch self {
        case .clientBirthday: return "Birthday"
        case .clientAnniversary: return "Anniversary"
        case .seasonalIngredient: return "Seasonal"
        case .reorderSuggestion: return "Reorder"
        case .priceChange: return "Price Alert"
        case .lowStock: return "Low Stock"
        case .clientInactive: return "Follow Up"
        case .menuSuggestion: return "Menu Idea"
        case .weatherAlert: return "Weather"
        case .other: return "Insight"
        }
    }

    var icon: String {
        switch self {
        case .clientBirthday: return "gift.fill"
        case .clientAnniversary: return "heart.fill"
        case .seasonalIngredient: return "leaf.fill"
        case .reorderSuggestion: return "arrow.clockwise"
        case .priceChange: return "dollarsign.circle.fill"
        case .lowStock: return "exclamationmark.triangle.fill"
        case .clientInactive: return "person.crop.circle.badge.questionmark"
        case .menuSuggestion: return "lightbulb.fill"
        case .weatherAlert: return "cloud.sun.fill"
        case .other: return "sparkles"
        }
    }
}

// MARK: - Insight Priority

enum InsightPriority: String, Codable {
    case low
    case medium
    case high
    case urgent

    var displayName: String {
        rawValue.capitalized
    }

    var sortOrder: Int {
        switch self {
        case .urgent: return 0
        case .high: return 1
        case .medium: return 2
        case .low: return 3
        }
    }
}

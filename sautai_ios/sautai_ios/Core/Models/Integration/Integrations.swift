//
//  Integrations.swift
//  sautai_ios
//
//  Models for third-party integrations (Telegram, Stripe, etc.)
//

import Foundation

// MARK: - Telegram

struct TelegramLinkResponse: Codable {
    let linkCode: String
    let expiresAt: Date
    let botUsername: String
}

struct TelegramStatus: Codable {
    let isLinked: Bool
    let chatId: String?
    let username: String?
    let linkedAt: Date?
    let notificationsEnabled: Bool
}

/// Extended Telegram status with notification settings
struct TelegramFullStatus: Codable {
    let linked: Bool
    let telegramUsername: String?
    let linkedAt: Date?
    let settings: TelegramSettings?
}

/// Telegram notification settings
struct TelegramSettings: Codable {
    var notifyNewOrders: Bool
    var notifyOrderUpdates: Bool
    var notifyScheduleReminders: Bool
    var notifyCustomerMessages: Bool
    var quietHoursStart: String?  // "HH:mm" format
    var quietHoursEnd: String?
    var quietHoursEnabled: Bool

    init(
        notifyNewOrders: Bool = true,
        notifyOrderUpdates: Bool = true,
        notifyScheduleReminders: Bool = true,
        notifyCustomerMessages: Bool = true,
        quietHoursStart: String? = nil,
        quietHoursEnd: String? = nil,
        quietHoursEnabled: Bool = false
    ) {
        self.notifyNewOrders = notifyNewOrders
        self.notifyOrderUpdates = notifyOrderUpdates
        self.notifyScheduleReminders = notifyScheduleReminders
        self.notifyCustomerMessages = notifyCustomerMessages
        self.quietHoursStart = quietHoursStart
        self.quietHoursEnd = quietHoursEnd
        self.quietHoursEnabled = quietHoursEnabled
    }
}

/// Workspace settings for Sous Chef AI customization
struct WorkspaceSettings: Codable {
    var soulPrompt: String?
    var businessRules: String?
    var includeAnalytics: Bool?
    var includeSeasonal: Bool?
    var autoMemorySave: Bool?
    var chefNickname: String?
    var sousChefName: String?

    init(
        soulPrompt: String? = nil,
        businessRules: String? = nil,
        includeAnalytics: Bool? = true,
        includeSeasonal: Bool? = true,
        autoMemorySave: Bool? = true,
        chefNickname: String? = nil,
        sousChefName: String? = nil
    ) {
        self.soulPrompt = soulPrompt
        self.businessRules = businessRules
        self.includeAnalytics = includeAnalytics
        self.includeSeasonal = includeSeasonal
        self.autoMemorySave = autoMemorySave
        self.chefNickname = chefNickname
        self.sousChefName = sousChefName
    }
}

// MARK: - Stripe / Payments

struct PaymentIntentResponse: Codable {
    let clientSecret: String
    let paymentIntentId: String
    let amount: Int
    let currency: String
    let status: String
}

struct PaymentStatus: Codable {
    let orderId: Int
    let status: PaymentStatusType
    let amount: String?
    let currency: String?
    let paidAt: Date?
    let receiptUrl: String?
}

enum PaymentStatusType: String, Codable {
    case pending
    case processing
    case succeeded
    case failed
    case cancelled
    case refunded

    var displayName: String {
        rawValue.capitalized
    }

    var icon: String {
        switch self {
        case .pending: return "clock"
        case .processing: return "arrow.triangle.2.circlepath"
        case .succeeded: return "checkmark.circle.fill"
        case .failed: return "xmark.circle.fill"
        case .cancelled: return "xmark.circle"
        case .refunded: return "arrow.uturn.backward.circle"
        }
    }
}

// MARK: - Chef Hub (Customer View)

struct ChefHub: Codable {
    let chef: PublicChef
    let orders: [Order]?
    let mealEvents: [ChefMealEvent]?
    let canOrder: Bool
    let relationship: ChefRelationship?
}

struct ChefRelationship: Codable {
    let connectedAt: Date?
    let totalOrders: Int
    let totalSpent: String?
    let lastOrderAt: Date?
}

// MARK: - Chef Meal Event

struct ChefMealEvent: Codable, Identifiable {
    let id: Int
    let chefId: Int
    let chefName: String?
    let title: String
    let description: String?
    let eventDate: Date
    let eventTime: String?
    let pricePerServing: String
    let currency: String?
    let maxServings: Int?
    let currentServings: Int?
    let cuisineType: String?
    let dietaryTags: [String]?
    let imageUrl: String?
    let isClosed: Bool
    let createdAt: Date?

    var availableServings: Int? {
        guard let max = maxServings, let current = currentServings else { return nil }
        return max - current
    }

    var isAvailable: Bool {
        guard let available = availableServings else { return !isClosed }
        return available > 0 && !isClosed
    }

    var displayPrice: String {
        let symbol = currency == "USD" ? "$" : currency ?? "$"
        return "\(symbol)\(pricePerServing)/serving"
    }
}

// MARK: - Customer Meal Plan

struct CustomerMealPlan: Codable, Identifiable {
    let id: Int
    let name: String?
    let weekOf: Date
    let status: String
    let days: [CustomerMealPlanDay]?
    let totalMeals: Int?
    let createdAt: Date?
    let approvedAt: Date?

    var displayWeek: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return "Week of \(formatter.string(from: weekOf))"
    }
}

struct CustomerMealPlanDay: Codable, Identifiable {
    let id: Int
    let date: Date
    let breakfast: MealPlanMeal?
    let lunch: MealPlanMeal?
    let dinner: MealPlanMeal?
    let snacks: [MealPlanMeal]?

    var displayDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMM d"
        return formatter.string(from: date)
    }
}

struct MealPlanMeal: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let calories: Int?
    let prepTime: Int?
    let imageUrl: String?
    let chefId: Int?
    let chefName: String?
}

// MARK: - Chef Service

struct ChefService: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let serviceType: String
    let basePrice: String?
    let currency: String?
    let duration: String?
    let isActive: Bool
}

struct GalleryPhoto: Codable, Identifiable {
    let id: Int
    let imageUrl: String
    let thumbnailUrl: String?
    let caption: String?
    let createdAt: Date?
}

//
//  MealPlan.swift
//  sautai_ios
//
//  Collaborative meal plan models for chef-client meal planning.
//

import Foundation

// MARK: - Meal Plan

struct MealPlan: Codable, Identifiable {
    let id: Int
    let clientId: Int
    let clientName: String?
    let title: String?
    let startDate: Date
    let endDate: Date
    let status: MealPlanStatus
    let days: [MealPlanDay]?
    let totalMeals: Int?
    let completedMeals: Int?
    let pendingSuggestions: Int?
    let notes: String?
    let createdAt: Date?
    let updatedAt: Date?
    let publishedAt: Date?

    var displayTitle: String {
        title ?? "Meal Plan for \(clientName ?? "Client")"
    }

    var dateRange: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return "\(formatter.string(from: startDate)) - \(formatter.string(from: endDate))"
    }

    var progress: Double {
        guard let total = totalMeals, total > 0, let completed = completedMeals else { return 0 }
        return Double(completed) / Double(total)
    }
}

// MARK: - Meal Plan Status

enum MealPlanStatus: String, Codable, CaseIterable {
    case draft
    case published
    case active
    case completed
    case cancelled

    var displayName: String {
        switch self {
        case .draft: return "Draft"
        case .published: return "Published"
        case .active: return "Active"
        case .completed: return "Completed"
        case .cancelled: return "Cancelled"
        }
    }

    var icon: String {
        switch self {
        case .draft: return "pencil"
        case .published: return "paperplane.fill"
        case .active: return "flame.fill"
        case .completed: return "checkmark.circle.fill"
        case .cancelled: return "xmark.circle"
        }
    }

    var color: String {
        switch self {
        case .draft: return "slateTile"
        case .published: return "info"
        case .active: return "herbGreen"
        case .completed: return "success"
        case .cancelled: return "danger"
        }
    }
}

// MARK: - Meal Plan Day

struct MealPlanDay: Codable, Identifiable {
    let id: Int
    let planId: Int
    let date: Date
    let dayOfWeek: String?
    let items: [MealPlanItem]?
    let notes: String?

    var displayDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMM d"
        return formatter.string(from: date)
    }

    var shortDate: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter.string(from: date)
    }
}

// MARK: - Meal Plan Item

struct MealPlanItem: Codable, Identifiable {
    let id: Int
    let dayId: Int
    let mealType: MealType
    let mealId: Int?
    let mealName: String?
    let dishId: Int?
    let dishName: String?
    let servings: Int?
    let notes: String?
    let isCompleted: Bool
    let suggestedBy: String?  // "chef", "ai", "client"
    let suggestionId: Int?

    var displayName: String {
        mealName ?? dishName ?? "Unassigned"
    }
}

// MARK: - Meal Type

enum MealType: String, Codable, CaseIterable {
    case breakfast
    case lunch
    case dinner
    case snack

    var displayName: String {
        rawValue.capitalized
    }

    var icon: String {
        switch self {
        case .breakfast: return "sunrise.fill"
        case .lunch: return "sun.max.fill"
        case .dinner: return "moon.stars.fill"
        case .snack: return "leaf.fill"
        }
    }
}

// MARK: - Meal Plan Suggestion

struct MealPlanSuggestion: Codable, Identifiable {
    let id: Int
    let planId: Int
    let dayId: Int?
    let mealType: MealType?
    let suggestedMealId: Int?
    let suggestedMealName: String?
    let suggestedDishId: Int?
    let suggestedDishName: String?
    let reason: String?
    let suggestedBy: String  // "chef", "client", "ai"
    let status: SuggestionStatus
    let responseNote: String?
    let createdAt: Date?
    let respondedAt: Date?

    var displaySuggestion: String {
        suggestedMealName ?? suggestedDishName ?? "Suggestion"
    }
}

// MARK: - Suggestion Status

enum SuggestionStatus: String, Codable {
    case pending
    case accepted
    case rejected
    case modified

    var displayName: String {
        rawValue.capitalized
    }

    var icon: String {
        switch self {
        case .pending: return "clock"
        case .accepted: return "checkmark.circle.fill"
        case .rejected: return "xmark.circle"
        case .modified: return "pencil.circle"
        }
    }
}

// MARK: - Create/Update Requests

struct MealPlanCreateRequest: Codable {
    let clientId: Int
    let title: String?
    let startDate: Date
    let endDate: Date
    let notes: String?
}

struct MealPlanDayCreateRequest: Codable {
    let date: Date
    let notes: String?
}

struct MealPlanItemCreateRequest: Codable {
    let mealType: MealType
    let mealId: Int?
    let dishId: Int?
    let servings: Int?
    let notes: String?
}

struct SuggestionResponseRequest: Codable {
    let status: SuggestionStatus
    let responseNote: String?
}

// MARK: - AI Generation Request

struct MealPlanGenerateRequest: Codable {
    let preferences: [String]?
    let dietaryRestrictions: [String]?
    let numberOfDays: Int?
    let mealsPerDay: Int?
}

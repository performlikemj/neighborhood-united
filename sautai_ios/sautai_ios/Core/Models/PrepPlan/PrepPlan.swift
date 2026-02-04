//
//  PrepPlan.swift
//  sautai_ios
//
//  Prep plan models for chef meal preparation workflow.
//

import Foundation

// MARK: - Prep Plan

struct PrepPlan: Codable, Identifiable {
    let id: Int
    let name: String?
    let startDate: Date
    let endDate: Date
    let status: PrepPlanStatus
    let clients: [PrepPlanClient]?
    let items: [PrepPlanItem]?
    let totalServings: Int?
    let estimatedPrepTime: Int?  // minutes
    let notes: String?
    let createdAt: Date?
    let updatedAt: Date?

    var displayName: String {
        name ?? "Plan \(id)"
    }

    var dateRange: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return "\(formatter.string(from: startDate)) - \(formatter.string(from: endDate))"
    }
}

// MARK: - Prep Plan Status

enum PrepPlanStatus: String, Codable {
    case draft
    case active
    case completed
    case cancelled

    var displayName: String {
        rawValue.capitalized
    }

    var icon: String {
        switch self {
        case .draft: return "pencil"
        case .active: return "flame.fill"
        case .completed: return "checkmark.circle.fill"
        case .cancelled: return "xmark.circle"
        }
    }
}

// MARK: - Prep Plan Client

struct PrepPlanClient: Codable, Identifiable {
    let id: Int
    let clientId: Int
    let clientName: String
    let servings: Int
    let deliveryDate: Date?
    let deliveryTime: String?
    let specialInstructions: String?
}

// MARK: - Prep Plan Item

struct PrepPlanItem: Codable, Identifiable {
    let id: Int
    let name: String
    let category: String?
    let quantity: String
    let unit: String?
    let servings: Int?
    let prepInstructions: String?
    let estimatedPrepTime: Int?  // minutes
    let isPrepared: Bool
    let batchNumber: Int?

    var displayQuantity: String {
        if let unit = unit {
            return "\(quantity) \(unit)"
        }
        return quantity
    }
}

// MARK: - Shopping List

struct ShoppingList: Codable {
    let id: Int?
    let planId: Int?
    let items: [ShoppingListItem]
    let totalItems: Int
    let purchasedCount: Int
    let estimatedCost: String?
    let generatedAt: Date?

    var progressPercentage: Double {
        guard totalItems > 0 else { return 0 }
        return Double(purchasedCount) / Double(totalItems)
    }
}

// MARK: - Shopping List Item

struct ShoppingListItem: Codable, Identifiable {
    let id: Int
    var name: String
    var quantity: String
    var unit: String?
    var category: String?
    var estimatedPrice: String?
    var isPurchased: Bool
    var notes: String?
    var shelfLife: Int?  // days
    var storageInstructions: String?

    var displayQuantity: String {
        if let unit = unit {
            return "\(quantity) \(unit)"
        }
        return quantity
    }
}

// MARK: - Batch Suggestion

struct BatchSuggestion: Codable, Identifiable {
    let id: String
    let items: [String]
    let reason: String
    let estimatedTimeSaved: Int?  // minutes
    let difficulty: String?
}

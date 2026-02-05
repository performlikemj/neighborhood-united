//
//  Kitchen.swift
//  sautai_ios
//
//  Kitchen models: Meals, Dishes, and Ingredients for chef management.
//

import Foundation

// MARK: - Meal

struct Meal: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let dishes: [Dish]?
    let imageUrl: String?
    let cuisineType: String?
    let dietaryTags: [String]?
    let prepTimeMinutes: Int?
    let servings: Int?
    let isActive: Bool
    let createdAt: Date?
    let updatedAt: Date?

    var dishCount: Int {
        dishes?.count ?? 0
    }

    var prepTimeDisplay: String? {
        guard let minutes = prepTimeMinutes else { return nil }
        if minutes >= 60 {
            let hours = minutes / 60
            let remainingMinutes = minutes % 60
            if remainingMinutes == 0 {
                return "\(hours)h"
            }
            return "\(hours)h \(remainingMinutes)m"
        }
        return "\(minutes)m"
    }
}

// MARK: - Meal Create/Update Request

struct MealCreateRequest: Codable {
    let name: String
    let description: String?
    let dishIds: [Int]?
    let cuisineType: String?
    let dietaryTags: [String]?
    let prepTimeMinutes: Int?
    let servings: Int?
    let isActive: Bool

    init(
        name: String,
        description: String? = nil,
        dishIds: [Int]? = nil,
        cuisineType: String? = nil,
        dietaryTags: [String]? = nil,
        prepTimeMinutes: Int? = nil,
        servings: Int? = nil,
        isActive: Bool = true
    ) {
        self.name = name
        self.description = description
        self.dishIds = dishIds
        self.cuisineType = cuisineType
        self.dietaryTags = dietaryTags
        self.prepTimeMinutes = prepTimeMinutes
        self.servings = servings
        self.isActive = isActive
    }
}

// MARK: - Dish

struct Dish: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let ingredients: [DishIngredient]?
    let imageUrl: String?
    let cuisineType: String?
    let dietaryTags: [String]?
    let prepTimeMinutes: Int?
    let cookTimeMinutes: Int?
    let servings: Int?
    let calories: Int?
    let isActive: Bool
    let createdAt: Date?
    let updatedAt: Date?

    var ingredientCount: Int {
        ingredients?.count ?? 0
    }

    var totalTimeMinutes: Int? {
        let prep = prepTimeMinutes ?? 0
        let cook = cookTimeMinutes ?? 0
        return prep + cook > 0 ? prep + cook : nil
    }

    var totalTimeDisplay: String? {
        guard let total = totalTimeMinutes else { return nil }
        if total >= 60 {
            let hours = total / 60
            let minutes = total % 60
            if minutes == 0 {
                return "\(hours)h"
            }
            return "\(hours)h \(minutes)m"
        }
        return "\(total)m"
    }

    var caloriesDisplay: String? {
        guard let cal = calories else { return nil }
        return "\(cal) cal"
    }
}

// MARK: - Dish Ingredient (junction with quantity)

struct DishIngredient: Codable, Identifiable {
    let id: Int
    let ingredientId: Int
    let ingredientName: String
    let quantity: String?
    let unit: String?
    let notes: String?

    var displayQuantity: String {
        var parts: [String] = []
        if let qty = quantity, !qty.isEmpty {
            parts.append(qty)
        }
        if let u = unit, !u.isEmpty {
            parts.append(u)
        }
        return parts.joined(separator: " ")
    }
}

// MARK: - Dish Create/Update Request

struct DishCreateRequest: Codable {
    let name: String
    let description: String?
    let ingredients: [DishIngredientInput]?
    let cuisineType: String?
    let dietaryTags: [String]?
    let prepTimeMinutes: Int?
    let cookTimeMinutes: Int?
    let servings: Int?
    let calories: Int?
    let isActive: Bool

    init(
        name: String,
        description: String? = nil,
        ingredients: [DishIngredientInput]? = nil,
        cuisineType: String? = nil,
        dietaryTags: [String]? = nil,
        prepTimeMinutes: Int? = nil,
        cookTimeMinutes: Int? = nil,
        servings: Int? = nil,
        calories: Int? = nil,
        isActive: Bool = true
    ) {
        self.name = name
        self.description = description
        self.ingredients = ingredients
        self.cuisineType = cuisineType
        self.dietaryTags = dietaryTags
        self.prepTimeMinutes = prepTimeMinutes
        self.cookTimeMinutes = cookTimeMinutes
        self.servings = servings
        self.calories = calories
        self.isActive = isActive
    }
}

// MARK: - Dish Ingredient Input (for create/update)

struct DishIngredientInput: Codable {
    let ingredientId: Int
    let quantity: String?
    let unit: String?
    let notes: String?

    init(ingredientId: Int, quantity: String? = nil, unit: String? = nil, notes: String? = nil) {
        self.ingredientId = ingredientId
        self.quantity = quantity
        self.unit = unit
        self.notes = notes
    }
}

// MARK: - Ingredient

struct Ingredient: Codable, Identifiable {
    let id: Int
    let name: String
    let category: String?
    let unit: String?
    let isCustom: Bool
    let createdAt: Date?

    var categoryDisplay: String {
        category?.capitalized ?? "Uncategorized"
    }

    init(id: Int, name: String, category: String? = nil, unit: String? = nil, isCustom: Bool = false, createdAt: Date? = nil) {
        self.id = id
        self.name = name
        self.category = category
        self.unit = unit
        self.isCustom = isCustom
        self.createdAt = createdAt
    }
}

// MARK: - Ingredient Category

enum IngredientCategory: String, Codable, CaseIterable {
    case produce
    case protein
    case dairy
    case grains
    case spices
    case oils
    case condiments
    case pantry
    case frozen
    case other

    var displayName: String {
        switch self {
        case .produce: return "Produce"
        case .protein: return "Protein"
        case .dairy: return "Dairy"
        case .grains: return "Grains & Pasta"
        case .spices: return "Spices & Herbs"
        case .oils: return "Oils & Fats"
        case .condiments: return "Condiments"
        case .pantry: return "Pantry"
        case .frozen: return "Frozen"
        case .other: return "Other"
        }
    }

    var icon: String {
        switch self {
        case .produce: return "leaf"
        case .protein: return "fish"
        case .dairy: return "cup.and.saucer"
        case .grains: return "takeoutbag.and.cup.and.straw"
        case .spices: return "sparkles"
        case .oils: return "drop"
        case .condiments: return "waterbottle"
        case .pantry: return "cabinet"
        case .frozen: return "snowflake"
        case .other: return "archivebox"
        }
    }
}

// MARK: - Meal Event Create/Update Request

struct MealEventCreateRequest: Codable {
    let title: String
    let description: String?
    let mealId: Int?
    let eventDate: Date
    let eventTime: String?
    let pricePerServing: String
    let maxServings: Int?
    let cuisineType: String?
    let dietaryTags: [String]?
    let pickupAddress: String?
    let pickupInstructions: String?

    init(
        title: String,
        description: String? = nil,
        mealId: Int? = nil,
        eventDate: Date,
        eventTime: String? = nil,
        pricePerServing: String,
        maxServings: Int? = nil,
        cuisineType: String? = nil,
        dietaryTags: [String]? = nil,
        pickupAddress: String? = nil,
        pickupInstructions: String? = nil
    ) {
        self.title = title
        self.description = description
        self.mealId = mealId
        self.eventDate = eventDate
        self.eventTime = eventTime
        self.pricePerServing = pricePerServing
        self.maxServings = maxServings
        self.cuisineType = cuisineType
        self.dietaryTags = dietaryTags
        self.pickupAddress = pickupAddress
        self.pickupInstructions = pickupInstructions
    }
}

struct MealEventUpdateRequest: Codable {
    let title: String?
    let description: String?
    let mealId: Int?
    let eventDate: Date?
    let eventTime: String?
    let pricePerServing: String?
    let maxServings: Int?
    let cuisineType: String?
    let dietaryTags: [String]?
    let pickupAddress: String?
    let pickupInstructions: String?
    let isClosed: Bool?
}

// MARK: - Order Calendar Item

struct OrderCalendarItem: Codable, Identifiable {
    let id: Int
    let type: CalendarItemType
    let title: String
    let date: Date
    let time: String?
    let customerName: String?
    let status: String
    let orderId: Int?
    let eventId: Int?

    var displayTime: String {
        time ?? "TBD"
    }

    var statusColor: String {
        switch status.lowercased() {
        case "pending": return "warning"
        case "confirmed": return "info"
        case "preparing": return "primary"
        case "ready", "completed": return "success"
        case "cancelled": return "danger"
        default: return "default"
        }
    }
}

enum CalendarItemType: String, Codable {
    case order
    case mealEvent = "meal_event"
    case prepPlan = "prep_plan"

    var icon: String {
        switch self {
        case .order: return "bag"
        case .mealEvent: return "fork.knife"
        case .prepPlan: return "checklist"
        }
    }
}

//
//  Service.swift
//  sautai_ios
//
//  Service offering models for chef service management.
//

import Foundation

// MARK: - Service Offering

struct ServiceOffering: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let serviceType: ServiceType
    let isActive: Bool
    let priceTiers: [PriceTier]?
    let imageUrl: String?
    let estimatedDuration: Int?  // Minutes
    let maxOrdersPerDay: Int?
    let leadTimeHours: Int?
    let createdAt: Date?
    let updatedAt: Date?

    var tierCount: Int {
        priceTiers?.count ?? 0
    }

    var basePriceDisplay: String? {
        guard let tiers = priceTiers, let firstTier = tiers.first else { return nil }
        return firstTier.priceDisplay
    }

    var priceRangeDisplay: String? {
        guard let tiers = priceTiers, !tiers.isEmpty else { return nil }
        let prices = tiers.compactMap { $0.price }
        guard let minPrice = prices.min(), let maxPrice = prices.max() else { return nil }

        if minPrice == maxPrice {
            return String(format: "$%.2f", NSDecimalNumber(decimal: minPrice).doubleValue)
        }

        return String(format: "$%.0f - $%.0f",
                     NSDecimalNumber(decimal: minPrice).doubleValue,
                     NSDecimalNumber(decimal: maxPrice).doubleValue)
    }

    var durationDisplay: String? {
        guard let minutes = estimatedDuration else { return nil }
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

// MARK: - Service Type

enum ServiceType: String, Codable, CaseIterable {
    case mealPrep = "meal_prep"
    case personalChef = "personal_chef"
    case catering
    case mealDelivery = "meal_delivery"
    case cookingClass = "cooking_class"
    case consultation
    case mealShare = "meal_share"
    case custom

    var displayName: String {
        switch self {
        case .mealPrep: return "Meal Prep"
        case .personalChef: return "Personal Chef"
        case .catering: return "Catering"
        case .mealDelivery: return "Meal Delivery"
        case .cookingClass: return "Cooking Class"
        case .consultation: return "Consultation"
        case .mealShare: return "Meal Share"
        case .custom: return "Custom"
        }
    }

    var icon: String {
        switch self {
        case .mealPrep: return "bag.fill"
        case .personalChef: return "person.fill"
        case .catering: return "fork.knife.circle.fill"
        case .mealDelivery: return "shippingbox.fill"
        case .cookingClass: return "book.fill"
        case .consultation: return "message.fill"
        case .mealShare: return "person.2.fill"
        case .custom: return "star.fill"
        }
    }

    var colorName: String {
        switch self {
        case .mealPrep: return "herbGreen"
        case .personalChef: return "earthenClay"
        case .catering: return "sunlitApricot"
        case .mealDelivery: return "info"
        case .cookingClass: return "pending"
        case .consultation: return "clayPotBrown"
        case .mealShare: return "success"
        case .custom: return "default"
        }
    }
}

// MARK: - Price Tier

struct PriceTier: Codable, Identifiable {
    let id: Int
    let name: String
    let price: Decimal
    let description: String?
    let servings: Int?
    let isPopular: Bool
    let sortOrder: Int?
    let createdAt: Date?

    var priceDisplay: String {
        String(format: "$%.2f", NSDecimalNumber(decimal: price).doubleValue)
    }

    var servingsDisplay: String? {
        guard let s = servings else { return nil }
        return s == 1 ? "1 serving" : "\(s) servings"
    }

    enum CodingKeys: String, CodingKey {
        case id, name, price, description, servings, isPopular, sortOrder, createdAt
    }

    init(id: Int, name: String, price: Decimal, description: String? = nil, servings: Int? = nil, isPopular: Bool = false, sortOrder: Int? = nil, createdAt: Date? = nil) {
        self.id = id
        self.name = name
        self.price = price
        self.description = description
        self.servings = servings
        self.isPopular = isPopular
        self.sortOrder = sortOrder
        self.createdAt = createdAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        name = try container.decode(String.self, forKey: .name)
        description = try container.decodeIfPresent(String.self, forKey: .description)
        servings = try container.decodeIfPresent(Int.self, forKey: .servings)
        isPopular = try container.decodeIfPresent(Bool.self, forKey: .isPopular) ?? false
        sortOrder = try container.decodeIfPresent(Int.self, forKey: .sortOrder)
        createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt)

        // Handle price as String or Number
        if let priceString = try? container.decode(String.self, forKey: .price) {
            price = Decimal(string: priceString) ?? 0
        } else {
            price = try container.decode(Decimal.self, forKey: .price)
        }
    }
}

// MARK: - Service Offering Create/Update Request

struct ServiceOfferingCreateRequest: Codable {
    let name: String
    let description: String?
    let serviceType: String
    let isActive: Bool
    let estimatedDuration: Int?
    let maxOrdersPerDay: Int?
    let leadTimeHours: Int?

    init(
        name: String,
        description: String? = nil,
        serviceType: ServiceType,
        isActive: Bool = true,
        estimatedDuration: Int? = nil,
        maxOrdersPerDay: Int? = nil,
        leadTimeHours: Int? = nil
    ) {
        self.name = name
        self.description = description
        self.serviceType = serviceType.rawValue
        self.isActive = isActive
        self.estimatedDuration = estimatedDuration
        self.maxOrdersPerDay = maxOrdersPerDay
        self.leadTimeHours = leadTimeHours
    }
}

// MARK: - Price Tier Create Request

struct PriceTierCreateRequest: Codable {
    let name: String
    let price: String
    let description: String?
    let servings: Int?
    let isPopular: Bool
    let sortOrder: Int?

    init(
        name: String,
        price: Decimal,
        description: String? = nil,
        servings: Int? = nil,
        isPopular: Bool = false,
        sortOrder: Int? = nil
    ) {
        self.name = name
        self.price = String(format: "%.2f", NSDecimalNumber(decimal: price).doubleValue)
        self.description = description
        self.servings = servings
        self.isPopular = isPopular
        self.sortOrder = sortOrder
    }
}

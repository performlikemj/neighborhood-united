//
//  User.swift
//  sautai_ios
//
//  User model matching Django's CustomUser.
//

import Foundation

// MARK: - User

struct User: Codable, Identifiable {
    let id: Int
    let username: String
    let email: String
    var phoneNumber: String?
    var emailConfirmed: Bool
    var isEmailVerified: Bool?
    var preferredLanguage: String
    var timezone: String
    var measurementSystem: MeasurementSystem
    var dietaryPreferences: [DietaryPreference]?
    var allergies: [String]?
    var customAllergies: [String]?
    var weekShift: Int?
    var emergencySupplyGoal: Int?
    var householdMemberCount: Int
    var householdMembers: [HouseholdMember]?
    var autoMealPlansEnabled: Bool
    var isChef: Bool
    var currentRole: String
    var address: Address?

    // MARK: - Computed Properties

    var displayName: String {
        username
    }

    var isVerified: Bool {
        emailConfirmed || (isEmailVerified ?? false)
    }

    var role: UserRole {
        currentRole == "chef" ? .chef : .customer
    }
}

// MARK: - Measurement System

enum MeasurementSystem: String, Codable {
    case us = "US"
    case metric = "METRIC"

    var displayName: String {
        switch self {
        case .us: return "US (cups, oz)"
        case .metric: return "Metric (ml, g)"
        }
    }
}

// MARK: - Dietary Preference

struct DietaryPreference: Codable, Identifiable, Hashable {
    let id: Int?
    let name: String

    var displayName: String { name }

    // Common preferences
    static let vegetarian = DietaryPreference(id: nil, name: "Vegetarian")
    static let vegan = DietaryPreference(id: nil, name: "Vegan")
    static let glutenFree = DietaryPreference(id: nil, name: "Gluten-Free")
    static let dairyFree = DietaryPreference(id: nil, name: "Dairy-Free")
    static let keto = DietaryPreference(id: nil, name: "Keto")
    static let paleo = DietaryPreference(id: nil, name: "Paleo")
}

// MARK: - Household Member

struct HouseholdMember: Codable, Identifiable {
    let id: Int
    var name: String
    var age: Int?
    var dietaryPreferences: [DietaryPreference]?
    var allergies: [String]?
    var customAllergies: [String]?
    var notes: String?
}

// MARK: - Address

struct Address: Codable, Identifiable {
    let id: Int?
    var street: String?
    var city: String?
    var state: String?
    var postalCode: String?
    var inputPostalcode: String?
    var normalizedPostalcode: String?
    var country: String?

    var formattedAddress: String {
        [street, city, state, postalCode]
            .compactMap { $0 }
            .filter { !$0.isEmpty }
            .joined(separator: ", ")
    }

    var displayPostalCode: String {
        postalCode ?? inputPostalcode ?? normalizedPostalcode ?? ""
    }
}

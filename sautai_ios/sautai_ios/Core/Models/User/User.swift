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

    // Custom init for creating preferences locally
    init(id: Int? = nil, name: String) {
        self.id = id
        self.name = name
    }

    // Handle both string and object formats from API
    init(from decoder: Decoder) throws {
        // Try decoding as a simple string first
        if let container = try? decoder.singleValueContainer(),
           let stringValue = try? container.decode(String.self) {
            self.id = nil
            self.name = stringValue
            return
        }

        // Otherwise decode as object
        let container = try decoder.container(keyedBy: CodingKeys.self)
        self.id = try container.decodeIfPresent(Int.self, forKey: .id)
        self.name = try container.decode(String.self, forKey: .name)
    }

    enum CodingKeys: String, CodingKey {
        case id, name
    }

    // Common preferences
    static let vegetarian = DietaryPreference(name: "Vegetarian")
    static let vegan = DietaryPreference(name: "Vegan")
    static let glutenFree = DietaryPreference(name: "Gluten-Free")
    static let dairyFree = DietaryPreference(name: "Dairy-Free")
    static let keto = DietaryPreference(name: "Keto")
    static let paleo = DietaryPreference(name: "Paleo")
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

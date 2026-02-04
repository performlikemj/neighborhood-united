//
//  Chef.swift
//  sautai_ios
//
//  Chef profile and dashboard models.
//

import Foundation

// MARK: - Chef Dashboard

struct ChefDashboard: Codable {
    let revenue: RevenueStats
    let clients: ClientStats
    let orders: OrderStats
    let topServices: [TopService]
}

// MARK: - Revenue Stats

struct RevenueStats: Codable {
    let today: String
    let thisWeek: String
    let thisMonth: String

    var todayDecimal: Decimal {
        Decimal(string: today) ?? 0
    }

    var thisWeekDecimal: Decimal {
        Decimal(string: thisWeek) ?? 0
    }

    var thisMonthDecimal: Decimal {
        Decimal(string: thisMonth) ?? 0
    }
}

// MARK: - Client Stats

struct ClientStats: Codable {
    let total: Int
    let active: Int
    let newThisMonth: Int
}

// MARK: - Order Stats

struct OrderStats: Codable {
    let upcoming: Int
    let pendingConfirmation: Int
    let completedThisMonth: Int
}

// MARK: - Top Service

struct TopService: Codable, Identifiable {
    let id: Int
    let name: String
    let serviceType: String
    let orderCount: Int
}

// MARK: - Client

struct Client: Codable, Identifiable {
    let id: Int
    let userId: Int?
    let name: String
    let email: String?
    let phoneNumber: String?
    let address: Address?
    let dietaryPreferences: [DietaryPreference]?
    let allergies: [String]?
    let notes: String?
    let createdAt: Date?
    let lastOrderAt: Date?
    let totalOrders: Int?
    let totalSpent: String?

    var displayName: String { name }

    var initials: String {
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))".uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }
}

// MARK: - Lead

struct Lead: Codable, Identifiable {
    let id: Int
    var name: String
    var email: String?
    var phoneNumber: String?
    var source: String?
    var status: LeadStatus
    var notes: String?
    var estimatedValue: String?
    var createdAt: Date?
    var lastContactAt: Date?

    var displayName: String { name }
}

// MARK: - Lead Status

enum LeadStatus: String, Codable, CaseIterable {
    case new
    case contacted
    case qualified
    case proposal
    case negotiation
    case won
    case lost

    var displayName: String {
        switch self {
        case .new: return "New"
        case .contacted: return "Contacted"
        case .qualified: return "Qualified"
        case .proposal: return "Proposal"
        case .negotiation: return "Negotiation"
        case .won: return "Won"
        case .lost: return "Lost"
        }
    }

    var color: String {
        switch self {
        case .new: return "info"
        case .contacted: return "primary"
        case .qualified: return "warning"
        case .proposal: return "pending"
        case .negotiation: return "warning"
        case .won: return "success"
        case .lost: return "danger"
        }
    }
}

// MARK: - Chef Profile

struct ChefProfile: Codable, Identifiable {
    let id: Int
    let userId: Int
    let username: String?
    let displayName: String?
    let bio: String?
    let specialties: [String]?
    let cuisines: [String]?
    let yearsExperience: Int?
    let profileImageUrl: String?
    let coverImageUrl: String?
    let rating: Double?
    let reviewCount: Int?
    let isVerified: Bool
    let isLive: Bool
    let onBreak: Bool
    let serviceAreas: [ServiceArea]?
}

// MARK: - Service Area

struct ServiceArea: Codable, Identifiable {
    let id: Int
    let name: String
    let postalCodes: [String]?
}

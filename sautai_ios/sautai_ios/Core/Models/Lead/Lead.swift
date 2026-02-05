//
//  Lead.swift
//  sautai_ios
//
//  Lead and CRM models - aligned with Django API.
//

import Foundation

// MARK: - Lead Status (matches Django Lead.status choices)

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

    var colorName: String {
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

    var icon: String {
        switch self {
        case .new: return "sparkles"
        case .contacted: return "phone.fill"
        case .qualified: return "checkmark.circle"
        case .proposal: return "doc.text"
        case .negotiation: return "bubble.left.and.bubble.right"
        case .won: return "star.fill"
        case .lost: return "xmark.circle"
        }
    }
}

// MARK: - Lead Source (matches Django Lead.source choices)

enum LeadSource: String, Codable, CaseIterable {
    case website
    case referral
    case social
    case event
    case other

    var displayName: String {
        switch self {
        case .website: return "Website"
        case .referral: return "Referral"
        case .social: return "Social Media"
        case .event: return "Event"
        case .other: return "Other"
        }
    }
}

// MARK: - Lead (matches Django LeadListSerializer)

struct Lead: Codable, Identifiable {
    let id: Int
    var firstName: String?
    var lastName: String?
    var fullName: String?
    var email: String?
    var phone: String?
    var company: String?
    var status: LeadStatus
    var source: LeadSource?
    var isPriority: Bool
    var budgetCents: Int?
    var notes: String?
    var householdSize: Int?
    var householdMemberCount: Int?
    var dietaryPreferences: [String]?
    var allergies: [String]?
    var lastInteractionAt: Date?
    var daysSinceInteraction: Int?
    var createdAt: Date?

    // Computed properties for display
    var displayName: String {
        if let full = fullName, !full.isEmpty {
            return full
        }
        let first = firstName ?? ""
        let last = lastName ?? ""
        let combined = "\(first) \(last)".trimmingCharacters(in: .whitespaces)
        return combined.isEmpty ? "Lead" : combined
    }

    var initials: String {
        let parts = displayName.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))".uppercased()
        }
        return String(displayName.prefix(2)).uppercased()
    }

    var budgetDisplay: String? {
        guard let cents = budgetCents else { return nil }
        let dollars = Double(cents) / 100.0
        return String(format: "$%.0f", dollars)
    }

    // Memberwise initializer
    init(
        id: Int,
        firstName: String? = nil,
        lastName: String? = nil,
        fullName: String? = nil,
        email: String? = nil,
        phone: String? = nil,
        company: String? = nil,
        status: LeadStatus = .new,
        source: LeadSource? = nil,
        isPriority: Bool = false,
        budgetCents: Int? = nil,
        notes: String? = nil,
        householdSize: Int? = nil,
        householdMemberCount: Int? = nil,
        dietaryPreferences: [String]? = nil,
        allergies: [String]? = nil,
        lastInteractionAt: Date? = nil,
        daysSinceInteraction: Int? = nil,
        createdAt: Date? = nil
    ) {
        self.id = id
        self.firstName = firstName
        self.lastName = lastName
        self.fullName = fullName
        self.email = email
        self.phone = phone
        self.company = company
        self.status = status
        self.source = source
        self.isPriority = isPriority
        self.budgetCents = budgetCents
        self.notes = notes
        self.householdSize = householdSize
        self.householdMemberCount = householdMemberCount
        self.dietaryPreferences = dietaryPreferences
        self.allergies = allergies
        self.lastInteractionAt = lastInteractionAt
        self.daysSinceInteraction = daysSinceInteraction
        self.createdAt = createdAt
    }
}

// MARK: - Lead Interaction (matches Django ClientNoteSerializer)

struct LeadInteraction: Codable, Identifiable {
    let id: Int
    var interactionType: InteractionType
    var summary: String?
    var details: String?
    var happenedAt: Date?
    var nextSteps: String?
    var authorName: String?
    var createdAt: Date?

    // Memberwise initializer
    init(
        id: Int,
        interactionType: InteractionType = .note,
        summary: String? = nil,
        details: String? = nil,
        happenedAt: Date? = nil,
        nextSteps: String? = nil,
        authorName: String? = nil,
        createdAt: Date? = nil
    ) {
        self.id = id
        self.interactionType = interactionType
        self.summary = summary
        self.details = details
        self.happenedAt = happenedAt
        self.nextSteps = nextSteps
        self.authorName = authorName
        self.createdAt = createdAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        interactionType = try container.decodeIfPresent(InteractionType.self, forKey: .interactionType) ?? .note
        summary = try container.decodeIfPresent(String.self, forKey: .summary)
        details = try container.decodeIfPresent(String.self, forKey: .details)
        happenedAt = try container.decodeIfPresent(Date.self, forKey: .happenedAt)
        nextSteps = try container.decodeIfPresent(String.self, forKey: .nextSteps)
        authorName = try container.decodeIfPresent(String.self, forKey: .authorName)
        createdAt = try container.decodeIfPresent(Date.self, forKey: .createdAt)
    }

    enum CodingKeys: String, CodingKey {
        case id, interactionType, summary, details, happenedAt, nextSteps, authorName, createdAt
    }
}

// MARK: - Interaction Type (matches Django interaction_type choices)

enum InteractionType: String, Codable, CaseIterable {
    case call
    case email
    case meeting
    case note
    case message
    case other

    var displayName: String {
        switch self {
        case .call: return "Call"
        case .email: return "Email"
        case .meeting: return "Meeting"
        case .note: return "Note"
        case .message: return "Message"
        case .other: return "Other"
        }
    }

    var icon: String {
        switch self {
        case .call: return "phone.fill"
        case .email: return "envelope.fill"
        case .meeting: return "person.2.fill"
        case .note: return "note.text"
        case .message: return "message.fill"
        case .other: return "ellipsis.circle.fill"
        }
    }
}

// MARK: - Lead Household Member (matches Django LeadHouseholdMemberSerializer)

struct LeadHouseholdMember: Codable, Identifiable {
    let id: Int
    var name: String
    var relationship: String?
    var age: Int?
    var dietaryPreferences: [String]?
    var allergies: [String]?
    var customAllergies: [String]?
    var notes: String?
    var createdAt: Date?
    var updatedAt: Date?
}

//
//  Lead.swift
//  sautai_ios
//
//  Lead and CRM models for chef client acquisition.
//

import Foundation

// MARK: - Lead

struct Lead: Codable, Identifiable {
    let id: Int
    var name: String
    var email: String?
    var phoneNumber: String?
    var source: LeadSource?
    var status: LeadStatus
    var notes: String?
    var estimatedValue: String?
    var createdAt: Date?
    var lastContactAt: Date?
    var dietaryPreferences: [DietaryPreference]?
    var allergies: [String]?
    var householdSize: Int?
    var address: Address?

    var displayName: String { name }

    var initials: String {
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))".uppercased()
        }
        return String(name.prefix(2)).uppercased()
    }
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

// MARK: - Lead Source

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

// MARK: - Lead Interaction

struct LeadInteraction: Codable, Identifiable {
    let id: Int
    let leadId: Int
    let type: InteractionType
    let notes: String?
    let createdAt: Date
    let createdByName: String?
}

// MARK: - Interaction Type

enum InteractionType: String, Codable, CaseIterable {
    case call
    case email
    case meeting
    case note
    case proposal
    case other

    var displayName: String {
        switch self {
        case .call: return "Phone Call"
        case .email: return "Email"
        case .meeting: return "Meeting"
        case .note: return "Note"
        case .proposal: return "Proposal Sent"
        case .other: return "Other"
        }
    }

    var icon: String {
        switch self {
        case .call: return "phone.fill"
        case .email: return "envelope.fill"
        case .meeting: return "person.2.fill"
        case .note: return "note.text"
        case .proposal: return "doc.text.fill"
        case .other: return "ellipsis.circle.fill"
        }
    }
}

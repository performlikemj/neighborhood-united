//
//  Profile.swift
//  sautai_ios
//
//  Chef profile and related models.
//

import Foundation

// MARK: - Chef Profile

struct ChefProfile: Codable, Identifiable {
    let id: Int
    let userId: Int
    let username: String
    let email: String?
    let displayName: String
    let bio: String?
    let location: String?
    let specialties: [String]?
    let cuisines: [String]?
    let yearsExperience: Int?
    let hourlyRate: Decimal?
    let profileImageUrl: String?
    let coverImageUrl: String?
    let isVerified: Bool
    let isLive: Bool
    let isOnBreak: Bool
    let breakReturnDate: Date?
    let averageRating: Double?
    let totalReviews: Int?
    let totalOrders: Int?
    let totalClients: Int?
    let memberSince: Date?
    let lastActive: Date?
    let socialLinks: SocialLinks?
    let settings: ChefSettings?

    var displayRating: String {
        guard let rating = averageRating else { return "New" }
        return String(format: "%.1f", rating)
    }

    var statusText: String {
        if isOnBreak {
            return "On Break"
        } else if isLive {
            return "Available"
        } else {
            return "Offline"
        }
    }
}

// MARK: - Social Links

struct SocialLinks: Codable {
    var website: String?
    var instagram: String?
    var facebook: String?
    var twitter: String?
    var youtube: String?
    var tiktok: String?
}

// MARK: - Chef Settings

struct ChefSettings: Codable {
    var acceptingOrders: Bool?
    var maxOrdersPerDay: Int?
    var leadTimeHours: Int?
    var autoConfirmOrders: Bool?
    var notifyNewOrders: Bool?
    var notifyMessages: Bool?
}

// MARK: - Chef Profile Update Request

struct ChefProfileUpdateRequest: Codable {
    var displayName: String?
    var bio: String?
    var location: String?
    var specialties: [String]?
    var cuisines: [String]?
    var yearsExperience: Int?
    var hourlyRate: Decimal?
    var socialLinks: SocialLinks?
    var settings: ChefSettings?
}

// MARK: - Chef Photo

struct ChefPhoto: Codable, Identifiable {
    let id: Int
    let imageUrl: String
    let thumbnailUrl: String?
    let caption: String?
    let sortOrder: Int?
    let isPrimary: Bool?
    let createdAt: Date?
}

// MARK: - Service Area

struct ServiceArea: Codable, Identifiable {
    let id: Int
    let name: String?
    let centerPostalCode: String
    let radiusMiles: Int?
    let postalCodes: [String]?
    let isActive: Bool?
    let createdAt: Date?

    // Alias for views
    var postalCode: String { centerPostalCode }

    var displayName: String {
        name ?? centerPostalCode
    }

    var postalCodeCount: Int {
        postalCodes?.count ?? 0
    }

    enum CodingKeys: String, CodingKey {
        case id, name, centerPostalCode, radiusMiles, postalCodes, isActive, createdAt
    }
}

// MARK: - Verification Document

struct VerificationDocument: Codable, Identifiable {
    let id: Int
    let documentType: DocumentType
    let fileName: String?
    let fileUrl: String?
    let status: DocumentStatus
    let expiryDate: Date?
    let rejectionReason: String?
    let uploadedAt: Date?
    let reviewedAt: Date?

    var isExpired: Bool {
        guard let expiryDate = expiryDate else { return false }
        return expiryDate < Date()
    }

    var isExpiringSoon: Bool {
        guard let expiryDate = expiryDate else { return false }
        let thirtyDays = Calendar.current.date(byAdding: .day, value: 30, to: Date())!
        return expiryDate < thirtyDays && expiryDate >= Date()
    }
}

// MARK: - Document Type

enum DocumentType: String, Codable, CaseIterable {
    case foodHandlersCert = "food_handlers_cert"
    case businessLicense = "business_license"
    case insurance = "insurance"
    case idDocument = "id_document"
    case other

    var displayName: String {
        switch self {
        case .foodHandlersCert: return "Food Handler's Certificate"
        case .businessLicense: return "Business License"
        case .insurance: return "Insurance"
        case .idDocument: return "ID Document"
        case .other: return "Other"
        }
    }

    var icon: String {
        switch self {
        case .foodHandlersCert: return "checkmark.seal.fill"
        case .businessLicense: return "building.2.fill"
        case .insurance: return "shield.fill"
        case .idDocument: return "person.text.rectangle.fill"
        case .other: return "doc.fill"
        }
    }
}

// MARK: - Document Status

enum DocumentStatus: String, Codable {
    case pending
    case approved
    case rejected
    case expired

    var displayName: String {
        rawValue.capitalized
    }

    var color: String {
        switch self {
        case .pending: return "warning"
        case .approved: return "success"
        case .rejected: return "danger"
        case .expired: return "slateTile"
        }
    }
}

// MARK: - Verification Status

struct VerificationStatus: Codable {
    let isVerified: Bool
    let isPending: Bool
    let documentsSubmitted: Bool
    let documentsApproved: Bool
    let meetingCompleted: Bool
    var upcomingMeeting: VerificationMeeting?
    let pendingRequirements: [String]?
}

// MARK: - Verification Meeting

struct VerificationMeeting: Codable, Identifiable {
    let id: Int
    let scheduledDate: Date
    let status: MeetingStatus
    let meetingUrl: String?
    let notes: String?
    let createdAt: Date?

    var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .full
        formatter.timeStyle = .short
        return formatter.string(from: scheduledDate)
    }
}

// MARK: - Meeting Status

enum MeetingStatus: String, Codable {
    case scheduled
    case confirmed
    case completed
    case cancelled
    case noShow = "no_show"

    var displayName: String {
        switch self {
        case .scheduled: return "Scheduled"
        case .confirmed: return "Confirmed"
        case .completed: return "Completed"
        case .cancelled: return "Cancelled"
        case .noShow: return "No Show"
        }
    }
}

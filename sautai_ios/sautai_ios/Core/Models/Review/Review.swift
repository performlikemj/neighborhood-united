//
//  Review.swift
//  sautai_ios
//
//  Review and rating models.
//

import Foundation

// MARK: - Review

struct Review: Codable, Identifiable {
    let id: Int
    let reviewerId: Int
    let reviewerName: String
    let reviewerAvatar: String?
    let chefId: Int?
    let orderId: Int?
    let eventId: Int?
    let rating: Int  // 1-5
    let title: String?
    let content: String?
    let response: ReviewResponse?
    let isVerifiedPurchase: Bool?
    let serviceName: String?
    let createdAt: Date
    let updatedAt: Date?

    // Aliases for views
    var customerName: String { reviewerName }
    var comment: String? { content }

    var starRating: String {
        String(repeating: "★", count: rating) + String(repeating: "☆", count: 5 - rating)
    }

    var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        return formatter.localizedString(for: createdAt, relativeTo: Date())
    }
}

// MARK: - Review Response

struct ReviewResponse: Codable {
    let id: Int
    let content: String
    let createdAt: Date

    var timeAgo: String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .full
        return formatter.localizedString(for: createdAt, relativeTo: Date())
    }
}

// MARK: - Review Summary

struct ReviewSummary: Codable {
    let totalReviews: Int
    let averageRating: Double
    let fiveStarCount: Int
    let fourStarCount: Int
    let threeStarCount: Int
    let twoStarCount: Int
    let oneStarCount: Int
    let pendingResponseCount: Int
    let recentReviews: [Review]?

    var displayRating: String {
        String(format: "%.1f", averageRating)
    }

    var fullStars: Int {
        Int(averageRating)
    }

    var hasHalfStar: Bool {
        averageRating - Double(fullStars) >= 0.5
    }
}

// MARK: - Create Review Request

struct ReviewCreateRequest: Codable {
    let rating: Int
    let title: String?
    let content: String?
    let orderId: Int?
    let eventId: Int?
}

// MARK: - Review Response Request

struct ReviewResponseRequest: Codable {
    let content: String
}

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
    let recentOrders: [Order]?
    let upcomingEvents: [ChefMealEvent]?
}

// MARK: - Revenue Stats (matches Django RevenueStatsSerializer)

struct RevenueStats: Codable {
    // Django returns Decimal as numbers, we parse flexibly
    let today: Decimal
    let thisWeek: Decimal
    let thisMonth: Decimal

    enum CodingKeys: String, CodingKey {
        case today, thisWeek, thisMonth
    }

    init(today: Decimal = 0, thisWeek: Decimal = 0, thisMonth: Decimal = 0) {
        self.today = today
        self.thisWeek = thisWeek
        self.thisMonth = thisMonth
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Handle both String and Number from API
        if let str = try? container.decode(String.self, forKey: .today) {
            today = Decimal(string: str) ?? 0
        } else {
            today = try container.decodeIfPresent(Decimal.self, forKey: .today) ?? 0
        }

        if let str = try? container.decode(String.self, forKey: .thisWeek) {
            thisWeek = Decimal(string: str) ?? 0
        } else {
            thisWeek = try container.decodeIfPresent(Decimal.self, forKey: .thisWeek) ?? 0
        }

        if let str = try? container.decode(String.self, forKey: .thisMonth) {
            thisMonth = Decimal(string: str) ?? 0
        } else {
            thisMonth = try container.decodeIfPresent(Decimal.self, forKey: .thisMonth) ?? 0
        }
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

// MARK: - Top Service (matches Django TopServiceSerializer)

struct TopService: Codable, Identifiable {
    let id: Int
    let name: String
    let serviceType: String?  // Optional in Django API
    let orderCount: Int
}

// MARK: - Client (matches Django ClientListItemSerializer)

struct Client: Codable, Identifiable {
    // Django returns customer_id, we use it as our id
    var id: Int { customerId }

    let customerId: Int
    let username: String?
    let email: String?
    let firstName: String?
    let lastName: String?
    let connectionStatus: String?
    let connectedSince: Date?
    let totalOrders: Int?
    let totalSpent: Decimal?

    var displayName: String {
        let first = firstName ?? ""
        let last = lastName ?? ""
        let combined = "\(first) \(last)".trimmingCharacters(in: .whitespaces)
        if !combined.isEmpty { return combined }
        return username ?? "Client"
    }

    var initials: String {
        let parts = displayName.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))".uppercased()
        }
        return String(displayName.prefix(2)).uppercased()
    }

    var totalSpentDisplay: String? {
        guard let spent = totalSpent else { return nil }
        return String(format: "$%.2f", NSDecimalNumber(decimal: spent).doubleValue)
    }

    // Memberwise initializer
    init(
        customerId: Int,
        username: String? = nil,
        email: String? = nil,
        firstName: String? = nil,
        lastName: String? = nil,
        connectionStatus: String? = nil,
        connectedSince: Date? = nil,
        totalOrders: Int? = nil,
        totalSpent: Decimal? = nil
    ) {
        self.customerId = customerId
        self.username = username
        self.email = email
        self.firstName = firstName
        self.lastName = lastName
        self.connectionStatus = connectionStatus
        self.connectedSince = connectedSince
        self.totalOrders = totalOrders
        self.totalSpent = totalSpent
    }
}

// MARK: - Client Note

struct ClientNote: Codable, Identifiable {
    let id: Int
    let content: String
    let authorName: String?
    let createdAt: Date?

    init(id: Int, content: String, authorName: String? = nil, createdAt: Date? = nil) {
        self.id = id
        self.content = content
        self.authorName = authorName
        self.createdAt = createdAt
    }
}

// MARK: - Expense Receipt (Client expense tracking)

struct ExpenseReceipt: Codable, Identifiable {
    let id: Int
    let thumbnailUrl: String?
    let amount: String
    let currency: String?
    let category: String?
    let categoryDisplay: String?
    let merchantName: String?
    let purchaseDate: Date?
    let status: String?
    let statusDisplay: String?
    let createdAt: Date?

    var displayAmount: String {
        let symbol = currency == "USD" ? "$" : currency ?? "$"
        return "\(symbol)\(amount)"
    }

    var statusColor: String {
        switch status {
        case "uploaded": return "pending"
        case "reviewed": return "info"
        case "reimbursed": return "success"
        case "rejected": return "danger"
        default: return "default"
        }
    }
}

// MARK: - Client Receipts Response

struct ClientReceiptsResponse: Codable {
    let results: [ExpenseReceipt]?
    let totals: ReceiptTotals
    let count: Int?
    let next: String?
    let previous: String?

    // Handle both paginated and non-paginated responses
    var receipts: [ExpenseReceipt] {
        results ?? []
    }
}

struct ReceiptTotals: Codable {
    let totalAmount: Double
    let totalCount: Int
    let reimbursedAmount: Double
    let pendingAmount: Double

    var totalDisplay: String {
        String(format: "$%.2f", totalAmount)
    }

    var reimbursedDisplay: String {
        String(format: "$%.2f", reimbursedAmount)
    }

    var pendingDisplay: String {
        String(format: "$%.2f", pendingAmount)
    }
}

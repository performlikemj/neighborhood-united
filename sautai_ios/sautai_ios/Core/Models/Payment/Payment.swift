//
//  Payment.swift
//  sautai_ios
//
//  Payment, Stripe, and receipt models.
//

import Foundation

// MARK: - Stripe Account Status

struct StripeAccountStatus: Codable {
    let hasAccount: Bool
    let accountId: String?
    let isOnboarded: Bool
    let chargesEnabled: Bool
    let payoutsEnabled: Bool
    let requiresAction: Bool
    let pendingVerification: Bool
    let currentlyDue: [String]?
    let eventuallyDue: [String]?
    let errors: [String]?
    let availableBalance: String?
    let pendingBalance: String?

    var isFullySetup: Bool {
        hasAccount && isOnboarded && chargesEnabled && payoutsEnabled
    }

    var isActive: Bool { isFullySetup }

    var pendingRequirements: [String]? { currentlyDue }

    var statusText: String {
        if !hasAccount {
            return "Not Connected"
        } else if !isOnboarded {
            return "Setup Incomplete"
        } else if pendingVerification {
            return "Pending Verification"
        } else if requiresAction {
            return "Action Required"
        } else if isFullySetup {
            return "Active"
        } else {
            return "Limited"
        }
    }

    var statusColor: String {
        if isFullySetup {
            return "success"
        } else if requiresAction || pendingVerification {
            return "warning"
        } else {
            return "slateTile"
        }
    }
}

// MARK: - Stripe Account Link

struct StripeAccountLink: Codable {
    let url: String
    let expiresAt: Date?

    var linkURL: URL? {
        URL(string: url)
    }
}

// MARK: - Payment Link

struct PaymentLink: Codable, Identifiable {
    let id: Int
    let title: String
    let description: String?
    let amount: Decimal
    let currency: String
    let clientId: Int?
    let clientName: String?
    let status: PaymentLinkStatus
    let url: String?
    let shortCode: String?
    let expiresAt: Date?
    let paidAt: Date?
    let createdAt: Date?
    let sentAt: Date?
    let sentVia: String?

    var displayAmount: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = currency
        return formatter.string(from: amount as NSDecimalNumber) ?? "$\(amount)"
    }

    var isExpired: Bool {
        guard let expiresAt = expiresAt else { return false }
        return expiresAt < Date()
    }

    var linkURL: URL? {
        guard let url = url else { return nil }
        return URL(string: url)
    }
}

// MARK: - Payment Link Status

enum PaymentLinkStatus: String, Codable {
    case draft
    case active
    case sent
    case viewed
    case paid
    case expired
    case cancelled

    var displayName: String {
        rawValue.capitalized
    }

    var icon: String {
        switch self {
        case .draft: return "pencil"
        case .active: return "link"
        case .sent: return "paperplane.fill"
        case .viewed: return "eye.fill"
        case .paid: return "checkmark.circle.fill"
        case .expired: return "clock.badge.xmark"
        case .cancelled: return "xmark.circle"
        }
    }

    var color: String {
        switch self {
        case .draft: return "slateTile"
        case .active: return "herbGreen"
        case .sent: return "info"
        case .viewed: return "warning"
        case .paid: return "success"
        case .expired, .cancelled: return "danger"
        }
    }
}

// MARK: - Payment Link Create Request

struct PaymentLinkCreateRequest: Codable {
    let amount: Decimal
    let description: String?
    let customerName: String?
    let customerPhone: String?
    let expiresInDays: Int?
}

// MARK: - Payment Link Stats

struct PaymentLinkStats: Codable {
    let totalLinks: Int
    let activeLinks: Int
    let totalSent: Int
    let totalPaid: Int
    let totalRevenue: Decimal
    let conversionRate: Double?
    let averageAmount: Decimal?

    var totalCollected: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        return formatter.string(from: totalRevenue as NSDecimalNumber) ?? "$0"
    }

    var displayRevenue: String { totalCollected }

    var displayConversionRate: String {
        guard let rate = conversionRate else { return "N/A" }
        return String(format: "%.1f%%", rate * 100)
    }
}

// MARK: - Receipt

struct Receipt: Codable, Identifiable {
    let id: Int
    let receiptNumber: String?
    let orderId: Int?
    let eventId: Int?
    let paymentLinkId: Int?
    let clientId: Int
    let clientName: String?
    let amount: Decimal
    let currency: String
    let paymentMethod: String?
    let status: ReceiptStatus
    let items: [ReceiptItem]?
    let subtotal: Decimal?
    let tax: Decimal?
    let tip: Decimal?
    let discount: Decimal?
    let paidAt: Date?
    let createdAt: Date?
    let notes: String?
    let pdfUrl: String?

    var displayAmount: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        formatter.currencyCode = currency
        return formatter.string(from: amount as NSDecimalNumber) ?? "$\(amount)"
    }

    // Alias for views
    var displayTotal: String { displayAmount }

    var displayDate: String {
        guard let date = paidAt ?? createdAt else { return "" }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: date)
    }
}

// MARK: - Receipt Status

enum ReceiptStatus: String, Codable {
    case pending
    case paid
    case refunded
    case partialRefund = "partial_refund"
    case failed

    var displayName: String {
        switch self {
        case .pending: return "Pending"
        case .paid: return "Paid"
        case .refunded: return "Refunded"
        case .partialRefund: return "Partial Refund"
        case .failed: return "Failed"
        }
    }

    var color: String {
        switch self {
        case .pending: return "warning"
        case .paid: return "success"
        case .refunded, .partialRefund: return "info"
        case .failed: return "danger"
        }
    }
}

// MARK: - Receipt Item

struct ReceiptItem: Codable, Identifiable {
    let id: Int
    let name: String
    let description: String?
    let quantity: Int
    let unitPrice: Decimal
    let totalPrice: Decimal

    var displayUnitPrice: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        return formatter.string(from: unitPrice as NSDecimalNumber) ?? "$\(unitPrice)"
    }

    var displayTotalPrice: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        return formatter.string(from: totalPrice as NSDecimalNumber) ?? "$\(totalPrice)"
    }
}

// MARK: - Receipt Stats

struct ReceiptStats: Codable {
    let totalReceipts: Int
    let totalRevenueDecimal: Decimal
    let averageOrderValue: Decimal?
    let thisMonthRevenue: Decimal?
    let lastMonthRevenue: Decimal?
    let revenueGrowth: Double?

    // Alias for views
    var totalOrders: Int { totalReceipts }

    var totalRevenue: String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .currency
        return formatter.string(from: totalRevenueDecimal as NSDecimalNumber) ?? "$0"
    }

    var displayTotalRevenue: String { totalRevenue }

    var displayGrowth: String {
        guard let growth = revenueGrowth else { return "N/A" }
        let prefix = growth >= 0 ? "+" : ""
        return "\(prefix)\(String(format: "%.1f", growth * 100))%"
    }

    enum CodingKeys: String, CodingKey {
        case totalReceipts
        case totalRevenueDecimal = "totalRevenue"
        case averageOrderValue, thisMonthRevenue, lastMonthRevenue, revenueGrowth
    }
}

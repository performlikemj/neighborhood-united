//
//  Order.swift
//  sautai_ios
//
//  Order and cart models.
//

import Foundation

// MARK: - Order

struct Order: Codable, Identifiable {
    let id: Int
    let customerId: Int?
    let customerName: String?
    let chefId: Int?
    let chefName: String?
    let status: OrderStatus
    let totalAmount: String?
    let currency: String?
    let items: [OrderItem]?
    let specialRequests: String?
    let deliveryDate: Date?
    let deliveryTime: String?
    let deliveryAddress: Address?
    let createdAt: Date?
    let updatedAt: Date?
    let paidAt: Date?

    var displayTotal: String {
        guard let amount = totalAmount else { return "$0.00" }
        let currencySymbol = currency == "USD" ? "$" : currency ?? "$"
        return "\(currencySymbol)\(amount)"
    }

    var isUpcoming: Bool {
        guard let date = deliveryDate else { return false }
        return date > Date()
    }
}

// MARK: - Order Status

enum OrderStatus: String, Codable, CaseIterable {
    case pending
    case confirmed
    case preparing
    case ready
    case delivered
    case completed
    case cancelled

    var displayName: String {
        switch self {
        case .pending: return "Pending"
        case .confirmed: return "Confirmed"
        case .preparing: return "Preparing"
        case .ready: return "Ready"
        case .delivered: return "Delivered"
        case .completed: return "Completed"
        case .cancelled: return "Cancelled"
        }
    }

    var colorName: String {
        switch self {
        case .pending: return "warning"
        case .confirmed: return "info"
        case .preparing: return "primary"
        case .ready: return "success"
        case .delivered: return "success"
        case .completed: return "success"
        case .cancelled: return "danger"
        }
    }

    var icon: String {
        switch self {
        case .pending: return "clock"
        case .confirmed: return "checkmark.circle"
        case .preparing: return "flame"
        case .ready: return "bag.fill"
        case .delivered: return "shippingbox"
        case .completed: return "checkmark.seal.fill"
        case .cancelled: return "xmark.circle"
        }
    }
}

// MARK: - Order Item

struct OrderItem: Codable, Identifiable {
    let id: Int
    let name: String
    let quantity: Int
    let unitPrice: String?
    let totalPrice: String?
    let notes: String?
    let mealId: Int?
    let serviceOfferingId: Int?
}

// MARK: - Chef Meal Order

struct ChefMealOrder: Codable, Identifiable {
    let id: Int
    let mealEventId: Int?
    let customerId: Int?
    let customerName: String?
    let quantity: Int
    let status: String
    let specialRequests: String?
    let createdAt: Date?

    var displayStatus: String {
        status.capitalized
    }
}

// MARK: - Cart

struct Cart: Codable {
    let items: [CartItem]
    let subtotal: String?
    let tax: String?
    let total: String?
    let currency: String?

    var isEmpty: Bool {
        items.isEmpty
    }

    var itemCount: Int {
        items.reduce(0) { $0 + $1.quantity }
    }
}

// MARK: - Cart Item

struct CartItem: Codable, Identifiable {
    let id: String  // Could be UUID or composite key
    let type: CartItemType
    let name: String
    let description: String?
    let quantity: Int
    let unitPrice: String
    let totalPrice: String
    let serviceOfferingId: Int?
    let tierId: Int?
}

// MARK: - Cart Item Type

enum CartItemType: String, Codable {
    case mealShare = "meal_share"
    case chefService = "chef_service"
    case subscription
}

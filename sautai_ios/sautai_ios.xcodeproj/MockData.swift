//
//  MockData.swift
//  sautai_iosTests
//
//  Mock data helpers for testing
//

import Foundation
@testable import sautai_ios

// MARK: - Mock Users

extension User {
    static func mockChef() -> User {
        User(
            id: 1,
            email: "chef@sautai.com",
            displayName: "Chef Maria Rodriguez",
            role: .chef,
            isVerified: true
        )
    }
    
    static func mockCustomer() -> User {
        User(
            id: 2,
            email: "customer@sautai.com",
            displayName: "John Smith",
            role: .customer,
            isVerified: true
        )
    }
    
    static func mockUnverifiedChef() -> User {
        User(
            id: 3,
            email: "newchef@sautai.com",
            displayName: "New Chef",
            role: .chef,
            isVerified: false
        )
    }
}

// MARK: - Mock Chef Dashboard

extension ChefDashboard {
    static func mock() -> ChefDashboard {
        ChefDashboard(
            revenue: .mock(),
            clients: .mock(),
            orders: .mock(),
            topServices: TopService.mockArray()
        )
    }
    
    static func mockEmpty() -> ChefDashboard {
        ChefDashboard(
            revenue: RevenueStats(today: "0.00", thisWeek: "0.00", thisMonth: "0.00"),
            clients: ClientStats(total: 0, active: 0, newThisMonth: 0),
            orders: OrderStats(upcoming: 0, completedThisMonth: 0),
            topServices: []
        )
    }
}

extension RevenueStats {
    static func mock() -> RevenueStats {
        RevenueStats(
            today: "125.50",
            thisWeek: "850.75",
            thisMonth: "3200.00"
        )
    }
}

extension ClientStats {
    static func mock() -> ClientStats {
        ClientStats(
            total: 15,
            active: 12,
            newThisMonth: 3
        )
    }
}

extension OrderStats {
    static func mock() -> OrderStats {
        OrderStats(
            upcoming: 8,
            completedThisMonth: 24
        )
    }
}

extension TopService {
    static func mockArray() -> [TopService] {
        [
            TopService(name: "Meal Prep - Weekly", orderCount: 12),
            TopService(name: "Private Dinner", orderCount: 8),
            TopService(name: "Cooking Class", orderCount: 5)
        ]
    }
}

// MARK: - Mock Messages

extension SousChefMessage {
    static func mockUserMessage() -> SousChefMessage {
        SousChefMessage(
            content: "Help me plan a vegetarian meal for 4 people",
            role: .user
        )
    }
    
    static func mockAssistantMessage() -> SousChefMessage {
        SousChefMessage(
            content: "I'd be happy to help! For a vegetarian meal for 4, I recommend a Mediterranean-inspired menu...",
            role: .assistant
        )
    }
    
    static func mockStreamingMessage() -> SousChefMessage {
        SousChefMessage(
            content: "I'm thinking about",
            role: .assistant,
            isStreaming: true
        )
    }
    
    static func mockConversation() -> [SousChefMessage] {
        [
            SousChefMessage(
                content: "Hello! I'm your Sous Chef AI assistant. How can I help you today?",
                role: .assistant
            ),
            SousChefMessage(
                content: "I need ideas for a quick dinner",
                role: .user
            ),
            SousChefMessage(
                content: "I have some great 30-minute dinner ideas! What type of cuisine are you in the mood for?",
                role: .assistant
            )
        ]
    }
}

extension Message {
    static func mockFromChef() -> Message {
        Message(
            id: 1,
            conversationId: 10,
            senderId: 1,
            senderName: "Chef Maria",
            content: "Hi! I'd love to help you with your meal planning. When would you like to start?",
            createdAt: Date().addingTimeInterval(-3600),
            readAt: Date(),
            isFromCurrentUser: false
        )
    }
    
    static func mockFromCustomer() -> Message {
        Message(
            id: 2,
            conversationId: 10,
            senderId: 2,
            senderName: "You",
            content: "I'm interested in weekly meal prep. Do you do vegetarian options?",
            createdAt: Date().addingTimeInterval(-1800),
            readAt: nil,
            isFromCurrentUser: true
        )
    }
    
    static func mockConversation() -> [Message] {
        [
            mockFromChef(),
            mockFromCustomer(),
            Message(
                id: 3,
                conversationId: 10,
                senderId: 1,
                senderName: "Chef Maria",
                content: "Absolutely! I specialize in plant-based meal prep. I can create a custom plan for you.",
                createdAt: Date().addingTimeInterval(-900),
                readAt: nil,
                isFromCurrentUser: false
            )
        ]
    }
}

// MARK: - Mock Conversations

extension Conversation {
    static func mockWithChef() -> Conversation {
        Conversation(
            id: 1,
            otherUserId: 10,
            otherUserName: "Chef Maria Rodriguez",
            otherUserAvatar: nil,
            lastMessage: "I can help you with that!",
            lastMessageAt: Date().addingTimeInterval(-3600),
            unreadCount: 2,
            isChefConversation: true
        )
    }
    
    static func mockWithCustomer() -> Conversation {
        Conversation(
            id: 2,
            otherUserId: 20,
            otherUserName: "John Smith",
            otherUserAvatar: nil,
            lastMessage: "When can we schedule the meal prep?",
            lastMessageAt: Date().addingTimeInterval(-7200),
            unreadCount: 0,
            isChefConversation: false
        )
    }
    
    static func mockArray() -> [Conversation] {
        [
            mockWithChef(),
            Conversation(
                id: 3,
                otherUserId: 11,
                otherUserName: "Chef David Chen",
                otherUserAvatar: nil,
                lastMessage: "Looking forward to cooking for you!",
                lastMessageAt: Date().addingTimeInterval(-86400),
                unreadCount: 0,
                isChefConversation: true
            ),
            mockWithCustomer()
        ]
    }
}

// MARK: - Mock Chef Profiles

extension ChefProfileDetail {
    static func mock() -> ChefProfileDetail {
        ChefProfileDetail(
            id: 1,
            email: "chef@sautai.com",
            displayName: "Chef Maria Rodriguez",
            username: "mariarodriguez",
            role: .chef,
            isVerified: true,
            bio: "Passionate chef with 10 years of experience in farm-to-table cuisine. I specialize in Mediterranean and plant-based cooking, creating delicious meals that nourish both body and soul.",
            cuisines: ["Mediterranean", "Italian", "Plant-Based", "Farm-to-Table"],
            specialties: ["Meal Prep", "Private Dinners", "Cooking Classes"],
            yearsExperience: 10,
            rating: 4.8,
            reviewCount: 47,
            serviceRadius: 25,
            gallery: [
                ChefPhotoItem(id: 1, imageUrl: "https://example.com/photo1.jpg", caption: "Fresh pasta"),
                ChefPhotoItem(id: 2, imageUrl: "https://example.com/photo2.jpg", caption: "Garden salad")
            ]
        )
    }
    
    static func mockNewChef() -> ChefProfileDetail {
        ChefProfileDetail(
            id: 2,
            email: "newchef@sautai.com",
            displayName: "Chef Alex Kim",
            username: "alexkim",
            role: .chef,
            isVerified: false,
            bio: "Just starting my culinary journey! Specializing in Korean fusion cuisine.",
            cuisines: ["Korean", "Asian Fusion"],
            specialties: ["Meal Prep"],
            yearsExperience: 2,
            rating: nil,
            reviewCount: 0,
            serviceRadius: 10,
            gallery: []
        )
    }
}

// MARK: - Mock Connected Chefs

extension ConnectedChef {
    static func mockArray() -> [ConnectedChef] {
        [
            ConnectedChef(
                id: 1,
                displayName: "Chef Maria",
                username: "mariarodriguez",
                cuisines: ["Mediterranean", "Italian"],
                rating: 4.8,
                avatarUrl: nil,
                lastOrderDate: Date().addingTimeInterval(-86400 * 7)
            ),
            ConnectedChef(
                id: 2,
                displayName: "Chef David",
                username: "davidchen",
                cuisines: ["Asian", "Fusion"],
                rating: 4.9,
                avatarUrl: nil,
                lastOrderDate: Date().addingTimeInterval(-86400 * 3)
            )
        ]
    }
}

// MARK: - Mock Orders

extension Order {
    static func mockUpcoming() -> Order {
        Order(
            id: 1,
            customerId: 2,
            customerName: "John Smith",
            chefId: 1,
            chefName: "Chef Maria",
            serviceType: "Weekly Meal Prep",
            status: .confirmed,
            deliveryDate: Date().addingTimeInterval(86400 * 2),
            totalAmount: "150.00",
            createdAt: Date().addingTimeInterval(-86400)
        )
    }
    
    static func mockCompleted() -> Order {
        Order(
            id: 2,
            customerId: 3,
            customerName: "Sarah Johnson",
            chefId: 1,
            chefName: "Chef Maria",
            serviceType: "Private Dinner",
            status: .completed,
            deliveryDate: Date().addingTimeInterval(-86400 * 5),
            totalAmount: "250.00",
            createdAt: Date().addingTimeInterval(-86400 * 7)
        )
    }
    
    static func mockArray() -> [Order] {
        [
            mockUpcoming(),
            Order(
                id: 3,
                customerId: 4,
                customerName: "Mike Wilson",
                chefId: 1,
                chefName: "Chef Maria",
                serviceType: "Cooking Class",
                status: .pending,
                deliveryDate: Date().addingTimeInterval(86400 * 5),
                totalAmount: "75.00",
                createdAt: Date()
            )
        ]
    }
}

// MARK: - Mock Auth Responses

struct MockAuthResponse {
    static func loginSuccess() -> LoginResponse {
        LoginResponse(
            access: "mock-access-token-12345",
            refresh: "mock-refresh-token-67890",
            user: .mockChef()
        )
    }
    
    static func loginCustomer() -> LoginResponse {
        LoginResponse(
            access: "mock-access-token-54321",
            refresh: "mock-refresh-token-09876",
            user: .mockCustomer()
        )
    }
}

// MARK: - Test Helpers

enum TestHelper {
    /// Creates a date offset from now by the specified number of days
    static func date(daysFromNow days: Int) -> Date {
        Date().addingTimeInterval(TimeInterval(86400 * days))
    }
    
    /// Creates a date offset from now by the specified number of hours
    static func date(hoursFromNow hours: Int) -> Date {
        Date().addingTimeInterval(TimeInterval(3600 * hours))
    }
    
    /// Creates a date offset from now by the specified number of minutes
    static func date(minutesFromNow minutes: Int) -> Date {
        Date().addingTimeInterval(TimeInterval(60 * minutes))
    }
}

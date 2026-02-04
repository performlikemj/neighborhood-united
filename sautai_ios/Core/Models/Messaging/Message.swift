//
//  Message.swift
//  sautai_ios
//
//  Messaging models for conversations and Sous Chef AI.
//

import Foundation

// MARK: - Conversation

struct Conversation: Codable, Identifiable {
    let id: Int
    let otherUserId: Int
    let otherUserName: String
    let otherUserAvatar: String?
    let lastMessage: String?
    let lastMessageAt: Date?
    let unreadCount: Int
    let isChefConversation: Bool?

    var displayName: String { otherUserName }

    var hasUnread: Bool { unreadCount > 0 }
}

// MARK: - Message

struct Message: Codable, Identifiable {
    let id: Int
    let conversationId: Int
    let senderId: Int
    let senderName: String?
    let content: String
    let createdAt: Date
    let readAt: Date?
    let isFromCurrentUser: Bool?

    var isRead: Bool { readAt != nil }
}

// MARK: - Sous Chef Message

struct SousChefMessage: Identifiable, Equatable {
    let id: UUID
    var content: String
    let role: SousChefRole
    var isStreaming: Bool
    let timestamp: Date
    let familyType: String?
    let familyId: Int?

    init(
        id: UUID = UUID(),
        content: String,
        role: SousChefRole,
        isStreaming: Bool = false,
        timestamp: Date = Date(),
        familyType: String? = nil,
        familyId: Int? = nil
    ) {
        self.id = id
        self.content = content
        self.role = role
        self.isStreaming = isStreaming
        self.timestamp = timestamp
        self.familyType = familyType
        self.familyId = familyId
    }

    static func == (lhs: SousChefMessage, rhs: SousChefMessage) -> Bool {
        lhs.id == rhs.id
    }
}

// MARK: - Sous Chef Role

enum SousChefRole: String, Codable {
    case user
    case assistant
    case system

    var isUser: Bool { self == .user }
    var isAssistant: Bool { self == .assistant }
}

// MARK: - Sous Chef Suggestion

struct SousChefSuggestion: Codable, Identifiable {
    let id: String
    let title: String
    let description: String?
    let action: String?
    let icon: String?

    init(id: String = UUID().uuidString, title: String, description: String? = nil, action: String? = nil, icon: String? = nil) {
        self.id = id
        self.title = title
        self.description = description
        self.action = action
        self.icon = icon
    }
}

// MARK: - Unread Counts

struct UnreadCounts: Codable {
    let total: Int
    let conversations: [Int: Int]?  // conversationId: count
}

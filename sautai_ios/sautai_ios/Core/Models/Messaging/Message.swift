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

struct SousChefMessage: Codable, Identifiable, Equatable {
    let id: UUID
    var content: String
    let role: SousChefRole
    var isStreaming: Bool
    let timestamp: Date
    let familyType: String?
    let familyId: Int?

    enum CodingKeys: String, CodingKey {
        case id, content, role, timestamp
        case familyType = "family_type"
        case familyId = "family_id"
    }

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

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        // Handle id as either UUID or String
        if let uuidString = try? container.decode(String.self, forKey: .id) {
            self.id = UUID(uuidString: uuidString) ?? UUID()
        } else if let uuid = try? container.decode(UUID.self, forKey: .id) {
            self.id = uuid
        } else {
            self.id = UUID()
        }

        self.content = try container.decode(String.self, forKey: .content)
        self.role = try container.decode(SousChefRole.self, forKey: .role)
        self.timestamp = try container.decodeIfPresent(Date.self, forKey: .timestamp) ?? Date()
        self.familyType = try container.decodeIfPresent(String.self, forKey: .familyType)
        self.familyId = try container.decodeIfPresent(Int.self, forKey: .familyId)
        self.isStreaming = false  // Never streaming when decoded from API
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id.uuidString, forKey: .id)
        try container.encode(content, forKey: .content)
        try container.encode(role, forKey: .role)
        try container.encode(timestamp, forKey: .timestamp)
        try container.encodeIfPresent(familyType, forKey: .familyType)
        try container.encodeIfPresent(familyId, forKey: .familyId)
    }

    static func == (lhs: SousChefMessage, rhs: SousChefMessage) -> Bool {
        // Compare all relevant fields for SwiftUI updates
        lhs.id == rhs.id &&
        lhs.content == rhs.content &&
        lhs.role == rhs.role &&
        lhs.isStreaming == rhs.isStreaming
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

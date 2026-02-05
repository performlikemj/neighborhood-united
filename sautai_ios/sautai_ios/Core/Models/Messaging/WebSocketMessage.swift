//
//  WebSocketMessage.swift
//  sautai_ios
//
//  WebSocket message models for real-time messaging.
//

import Foundation

// MARK: - Outgoing Messages

/// Message sent from client to server via WebSocket
struct WebSocketOutgoingMessage: Encodable {
    let type: WebSocketMessageType
    var content: String?
    var isTyping: Bool?

    enum CodingKeys: String, CodingKey {
        case type, content
        case isTyping = "is_typing"
    }
}

// MARK: - Incoming Messages

/// Message received from server via WebSocket
struct WebSocketIncomingMessage: Decodable {
    let type: String
    let message: WebSocketMessageData?
    let userId: Int?
    let isTyping: Bool?
    let readerId: Int?
    let errorMessage: String?

    enum CodingKeys: String, CodingKey {
        case type, message
        case userId = "user_id"
        case isTyping = "is_typing"
        case readerId = "reader_id"
        case errorMessage = "error_message"
    }
}

/// Message data payload from WebSocket
struct WebSocketMessageData: Decodable {
    let id: Int
    let senderId: Int
    let senderName: String?
    let content: String
    let createdAt: Date
    let conversationId: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case senderId = "sender_id"
        case senderName = "sender_name"
        case content
        case createdAt = "created_at"
        case conversationId = "conversation_id"
    }

    /// Convert to standard Message model
    func toMessage(isFromCurrentUser: Bool = false) -> Message {
        Message(
            id: id,
            conversationId: conversationId ?? 0,
            senderId: senderId,
            senderName: senderName,
            content: content,
            createdAt: createdAt,
            readAt: nil,
            isFromCurrentUser: isFromCurrentUser
        )
    }
}

// MARK: - Message Types

enum WebSocketMessageType: String, Codable {
    case message
    case typing
    case read
    case ping
    case pong
}

// MARK: - Connection State

enum WebSocketConnectionState {
    case disconnected
    case connecting
    case connected
    case reconnecting

    var description: String {
        switch self {
        case .disconnected: return "Disconnected"
        case .connecting: return "Connecting..."
        case .connected: return "Connected"
        case .reconnecting: return "Reconnecting..."
        }
    }

    var isConnected: Bool {
        self == .connected
    }
}

// MARK: - WebSocket Error

enum WebSocketError: LocalizedError {
    case connectionFailed
    case authenticationFailed
    case messageEncodingFailed
    case invalidResponse
    case serverError(String)

    var errorDescription: String? {
        switch self {
        case .connectionFailed:
            return "Failed to connect to chat server"
        case .authenticationFailed:
            return "Chat authentication failed"
        case .messageEncodingFailed:
            return "Failed to send message"
        case .invalidResponse:
            return "Invalid response from server"
        case .serverError(let message):
            return message
        }
    }
}

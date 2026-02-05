//
//  WebSocketClient.swift
//  sautai_ios
//
//  WebSocket client for real-time messaging.
//  Handles connection management, auto-reconnection, and message routing.
//

import Foundation
import Combine

@MainActor
class WebSocketClient: ObservableObject {

    // MARK: - Singleton

    static let shared = WebSocketClient()

    // MARK: - Published State

    @Published private(set) var connectionState: WebSocketConnectionState = .disconnected
    @Published private(set) var currentConversationId: Int?

    // MARK: - Callbacks

    var onMessage: ((Message) -> Void)?
    var onTypingIndicator: ((Int, Bool) -> Void)?
    var onMessagesRead: ((Int) -> Void)?
    var onError: ((Error) -> Void)?

    // MARK: - Private Properties

    private var webSocket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var reconnectAttempts = 0
    private var maxReconnectAttempts = 5
    private var reconnectDelay: TimeInterval = 1.0
    private var pingTask: Task<Void, Never>?
    private var receiveTask: Task<Void, Never>?
    private var isManuallyDisconnected = false

    private let baseURL: URL
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    // MARK: - Initialization

    private init() {
        #if DEBUG
        self.baseURL = URL(string: "ws://127.0.0.1:8000")!
        #else
        self.baseURL = URL(string: "wss://api.sautai.com")!
        #endif

        self.decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601

        self.encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    // MARK: - Public Methods

    /// Connect to a conversation's WebSocket channel
    func connect(conversationId: Int) async {
        // Don't reconnect if already connected to the same conversation
        if connectionState == .connected && currentConversationId == conversationId {
            return
        }

        // Disconnect from any existing connection
        if connectionState != .disconnected {
            disconnect()
        }

        isManuallyDisconnected = false
        currentConversationId = conversationId
        connectionState = .connecting

        #if DEBUG
        print("🔌 WebSocket: Connecting to conversation \(conversationId)")
        #endif

        do {
            let token = try await AuthManager.shared.getAccessToken()

            // Build WebSocket URL with auth token
            guard var components = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
                throw WebSocketError.connectionFailed
            }

            components.path = "/ws/chat/\(conversationId)/"
            components.queryItems = [URLQueryItem(name: "token", value: token)]

            guard let url = components.url else {
                throw WebSocketError.connectionFailed
            }

            #if DEBUG
            print("🔌 WebSocket: URL = \(url.absoluteString.prefix(80))...")
            #endif

            // Create session and task
            let config = URLSessionConfiguration.default
            session = URLSession(configuration: config)
            webSocket = session?.webSocketTask(with: url)

            // Start connection
            webSocket?.resume()

            // Start receiving messages
            startReceiving()

            // Start ping/pong for keep-alive
            startPingPong()

            connectionState = .connected
            reconnectAttempts = 0

            #if DEBUG
            print("✅ WebSocket: Connected to conversation \(conversationId)")
            #endif

        } catch {
            #if DEBUG
            print("❌ WebSocket: Connection failed - \(error.localizedDescription)")
            #endif
            connectionState = .disconnected
            onError?(WebSocketError.connectionFailed)
        }
    }

    /// Disconnect from WebSocket
    func disconnect() {
        isManuallyDisconnected = true
        cleanupConnection()

        #if DEBUG
        print("🔌 WebSocket: Disconnected manually")
        #endif
    }

    /// Send a chat message
    func sendMessage(_ content: String) async throws {
        guard connectionState == .connected else {
            throw WebSocketError.connectionFailed
        }

        let message = WebSocketOutgoingMessage(type: .message, content: content)
        try await send(message)

        #if DEBUG
        print("📤 WebSocket: Sent message - \(content.prefix(50))...")
        #endif
    }

    /// Send typing indicator
    func sendTyping(_ isTyping: Bool) async throws {
        guard connectionState == .connected else { return }

        let message = WebSocketOutgoingMessage(type: .typing, isTyping: isTyping)
        try await send(message)

        #if DEBUG
        print("📤 WebSocket: Typing = \(isTyping)")
        #endif
    }

    /// Send read receipt
    func sendRead() async throws {
        guard connectionState == .connected else { return }

        let message = WebSocketOutgoingMessage(type: .read)
        try await send(message)

        #if DEBUG
        print("📤 WebSocket: Sent read receipt")
        #endif
    }

    // MARK: - Private Methods

    private func send(_ message: WebSocketOutgoingMessage) async throws {
        guard let webSocket = webSocket else {
            throw WebSocketError.connectionFailed
        }

        do {
            let data = try encoder.encode(message)
            guard let json = String(data: data, encoding: .utf8) else {
                throw WebSocketError.messageEncodingFailed
            }

            try await webSocket.send(.string(json))
        } catch {
            throw WebSocketError.messageEncodingFailed
        }
    }

    private func startReceiving() {
        receiveTask?.cancel()
        receiveTask = Task { [weak self] in
            guard let self = self else { return }

            while !Task.isCancelled {
                do {
                    guard let webSocket = self.webSocket else { break }

                    let message = try await webSocket.receive()

                    switch message {
                    case .string(let text):
                        await self.handleMessage(text)

                    case .data(let data):
                        if let text = String(data: data, encoding: .utf8) {
                            await self.handleMessage(text)
                        }

                    @unknown default:
                        break
                    }
                } catch {
                    if !Task.isCancelled && !self.isManuallyDisconnected {
                        #if DEBUG
                        print("❌ WebSocket: Receive error - \(error.localizedDescription)")
                        #endif
                        await self.handleDisconnect()
                    }
                    break
                }
            }
        }
    }

    private func handleMessage(_ text: String) async {
        guard let data = text.data(using: .utf8) else { return }

        #if DEBUG
        print("📥 WebSocket: Received - \(text.prefix(100))")
        #endif

        do {
            let incoming = try decoder.decode(WebSocketIncomingMessage.self, from: data)

            switch incoming.type {
            case "message":
                if let messageData = incoming.message {
                    // Determine if message is from current user
                    let currentUserId = AuthManager.shared.currentUser?.id
                    let isFromMe = incoming.userId == currentUserId || messageData.senderId == currentUserId
                    let message = messageData.toMessage(isFromCurrentUser: isFromMe)
                    onMessage?(message)
                }

            case "typing":
                if let userId = incoming.userId, let isTyping = incoming.isTyping {
                    onTypingIndicator?(userId, isTyping)
                }

            case "read":
                if let readerId = incoming.readerId {
                    onMessagesRead?(readerId)
                }

            case "error":
                if let errorMessage = incoming.errorMessage {
                    #if DEBUG
                    print("❌ WebSocket: Server error - \(errorMessage)")
                    #endif
                    onError?(WebSocketError.serverError(errorMessage))
                }

            default:
                #if DEBUG
                print("⚠️ WebSocket: Unknown message type - \(incoming.type)")
                #endif
            }
        } catch {
            #if DEBUG
            print("❌ WebSocket: Decode error - \(error.localizedDescription)")
            #endif
        }
    }

    private func startPingPong() {
        pingTask?.cancel()
        pingTask = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 30_000_000_000) // 30 seconds

                guard let self = self,
                      let webSocket = self.webSocket,
                      self.connectionState == .connected else {
                    break
                }

                webSocket.sendPing { error in
                    if let error = error {
                        #if DEBUG
                        print("⚠️ WebSocket: Ping failed - \(error.localizedDescription)")
                        #endif
                        Task { @MainActor in
                            await self.handleDisconnect()
                        }
                    }
                }
            }
        }
    }

    private func handleDisconnect() async {
        guard !isManuallyDisconnected else { return }

        connectionState = .disconnected
        cleanupConnection()

        // Attempt reconnection
        if reconnectAttempts < maxReconnectAttempts {
            reconnectAttempts += 1
            let delay = reconnectDelay * pow(2.0, Double(reconnectAttempts - 1)) // Exponential backoff
            connectionState = .reconnecting

            #if DEBUG
            print("🔄 WebSocket: Reconnecting in \(delay)s (attempt \(reconnectAttempts)/\(maxReconnectAttempts))")
            #endif

            try? await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))

            if let conversationId = currentConversationId, !isManuallyDisconnected {
                await connect(conversationId: conversationId)
            }
        } else {
            #if DEBUG
            print("❌ WebSocket: Max reconnection attempts reached")
            #endif
            onError?(WebSocketError.connectionFailed)
        }
    }

    private func cleanupConnection() {
        pingTask?.cancel()
        pingTask = nil

        receiveTask?.cancel()
        receiveTask = nil

        webSocket?.cancel(with: .goingAway, reason: nil)
        webSocket = nil

        session?.invalidateAndCancel()
        session = nil

        if isManuallyDisconnected {
            currentConversationId = nil
            reconnectAttempts = 0
        }

        connectionState = .disconnected
    }
}

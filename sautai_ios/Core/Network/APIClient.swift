//
//  APIClient.swift
//  sautai_ios
//
//  URLSession-based API client with JWT authentication.
//  Handles token refresh and request retrying.
//

import Foundation

// MARK: - API Client

class APIClient {

    // MARK: - Singleton

    static let shared = APIClient()

    // MARK: - Configuration

    private let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    // MARK: - Initialization

    private init() {
        // Configure base URL (update for production)
        #if DEBUG
        self.baseURL = URL(string: "http://localhost:8000")!
        #else
        self.baseURL = URL(string: "https://api.sautai.com")!
        #endif

        // Configure session
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)

        // Configure decoder
        self.decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601

        // Configure encoder
        self.encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
    }

    // MARK: - Auth Endpoints

    /// Login with email and password
    func login(email: String, password: String) async throws -> TokenResponse {
        let body = ["email": email, "password": password]
        return try await post("/auth/api/login/", body: body, authenticated: false)
    }

    /// Register a new user
    func register(
        email: String,
        password: String,
        username: String,
        phoneNumber: String? = nil
    ) async throws -> User {
        var body: [String: Any] = [
            "email": email,
            "password": password,
            "username": username
        ]
        if let phone = phoneNumber {
            body["phone_number"] = phone
        }
        return try await post("/auth/api/register/", body: body, authenticated: false)
    }

    /// Refresh access token
    func refreshToken(refreshToken: String) async throws -> RefreshTokenResponse {
        let body = ["refresh": refreshToken]
        return try await post("/auth/api/token/refresh/", body: body, authenticated: false)
    }

    /// Get current user profile
    func getUserProfile() async throws -> User {
        return try await get("/auth/api/user_details/")
    }

    /// Switch user role
    func switchRole(to role: String) async throws {
        let body = ["role": role]
        let _: EmptyResponse = try await post("/auth/api/switch_role/", body: body)
    }

    // MARK: - Chef Dashboard Endpoints

    /// Get chef dashboard summary
    func getChefDashboard() async throws -> ChefDashboard {
        return try await get("/chefs/api/me/dashboard/")
    }

    /// Get chef's clients
    func getClients(page: Int = 1) async throws -> PaginatedResponse<Client> {
        return try await get("/chefs/api/me/clients/?page=\(page)")
    }

    /// Get client details
    func getClient(id: Int) async throws -> Client {
        return try await get("/chefs/api/me/clients/\(id)/")
    }

    /// Get upcoming orders
    func getUpcomingOrders() async throws -> [Order] {
        return try await get("/chefs/api/me/orders/upcoming/")
    }

    // MARK: - Sous Chef AI Endpoints

    /// Start new conversation
    func startSousChefConversation() async throws -> ConversationStart {
        return try await post("/chefs/api/me/sous-chef/new-conversation/", body: [:])
    }

    /// Get conversation history
    func getSousChefHistory(familyType: String, familyId: Int) async throws -> [SousChefMessage] {
        return try await get("/chefs/api/me/sous-chef/history/\(familyType)/\(familyId)/")
    }

    // MARK: - Customer Endpoints

    /// Get public chef directory
    func getPublicChefs(page: Int = 1) async throws -> [PublicChef] {
        let response: PaginatedResponse<PublicChef> = try await get("/chefs/api/public/?page=\(page)")
        return response.results
    }

    /// Get chef profile details
    func getChefProfile(id: Int) async throws -> ChefProfileDetail {
        return try await get("/chefs/api/public/\(id)/")
    }

    /// Check if chef serves customer's area
    func checkChefServesArea(chefId: Int) async throws -> Bool {
        struct AreaResponse: Decodable {
            let servesArea: Bool
        }
        let response: AreaResponse = try await get("/chefs/api/public/\(chefId)/serves-my-area/")
        return response.servesArea
    }

    /// Get customer's connected chefs
    func getMyChefs() async throws -> [ConnectedChef] {
        return try await get("/customer_dashboard/api/my-chefs/")
    }

    // MARK: - Messaging Endpoints

    /// Get all conversations
    func getConversations() async throws -> [Conversation] {
        return try await get("/messaging/api/conversations/")
    }

    /// Get messages for a conversation
    func getMessages(conversationId: Int) async throws -> [Message] {
        return try await get("/messaging/api/conversations/\(conversationId)/")
    }

    /// Send a message
    func sendMessage(conversationId: Int, content: String) async throws -> Message {
        let body = ["content": content]
        return try await post("/messaging/api/conversations/\(conversationId)/send/", body: body)
    }

    /// Mark conversation as read
    func markConversationAsRead(conversationId: Int) async throws {
        let _: EmptyResponse = try await post("/messaging/api/conversations/\(conversationId)/read/", body: [:])
    }

    /// Start conversation with a chef
    func startConversationWithChef(chefId: Int, message: String) async throws -> Conversation {
        let body = ["message": message]
        return try await post("/messaging/api/conversations/with-chef/\(chefId)/", body: body)
    }

    // MARK: - Generic Request Methods

    /// GET request
    func get<T: Decodable>(_ path: String, authenticated: Bool = true) async throws -> T {
        let request = try await buildRequest(path: path, method: "GET", authenticated: authenticated)
        return try await execute(request)
    }

    /// POST request
    func post<T: Decodable>(_ path: String, body: [String: Any], authenticated: Bool = true) async throws -> T {
        var request = try await buildRequest(path: path, method: "POST", authenticated: authenticated)
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await execute(request)
    }

    /// PUT request
    func put<T: Decodable>(_ path: String, body: [String: Any], authenticated: Bool = true) async throws -> T {
        var request = try await buildRequest(path: path, method: "PUT", authenticated: authenticated)
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await execute(request)
    }

    /// PATCH request
    func patch<T: Decodable>(_ path: String, body: [String: Any], authenticated: Bool = true) async throws -> T {
        var request = try await buildRequest(path: path, method: "PATCH", authenticated: authenticated)
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return try await execute(request)
    }

    /// DELETE request
    func delete(_ path: String, authenticated: Bool = true) async throws {
        let request = try await buildRequest(path: path, method: "DELETE", authenticated: authenticated)
        let _: EmptyResponse = try await execute(request)
    }

    // MARK: - Private Methods

    /// Build URLRequest with headers
    private func buildRequest(path: String, method: String, authenticated: Bool) async throws -> URLRequest {
        let url = baseURL.appendingPathComponent(path)
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        if authenticated {
            let token = try await AuthManager.shared.getAccessToken()
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        return request
    }

    /// Execute request and decode response
    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        // Handle specific status codes
        switch httpResponse.statusCode {
        case 200...299:
            // Success
            if T.self == EmptyResponse.self {
                return EmptyResponse() as! T
            }
            do {
                return try decoder.decode(T.self, from: data)
            } catch {
                print("Decoding error: \(error)")
                throw APIError.decodingFailed(error)
            }

        case 401:
            // Unauthorized - try to refresh token and retry
            try await AuthManager.shared.refreshAccessToken()
            var newRequest = request
            let newToken = try await AuthManager.shared.getAccessToken()
            newRequest.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
            return try await execute(newRequest)

        case 400:
            throw APIError.badRequest(parseErrorMessage(from: data))

        case 403:
            throw APIError.forbidden

        case 404:
            throw APIError.notFound

        case 429:
            throw APIError.rateLimited

        case 500...599:
            throw APIError.serverError(httpResponse.statusCode)

        default:
            throw APIError.unexpectedStatus(httpResponse.statusCode)
        }
    }

    /// Parse error message from response data
    private func parseErrorMessage(from data: Data) -> String {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let message = json["message"] as? String {
                return message
            }
            if let detail = json["detail"] as? String {
                return detail
            }
            if let errors = json["errors"] as? [String: [String]] {
                return errors.values.flatMap { $0 }.joined(separator: ", ")
            }
        }
        return "An unknown error occurred"
    }
}

// MARK: - API Error

enum APIError: LocalizedError {
    case invalidResponse
    case decodingFailed(Error)
    case badRequest(String)
    case forbidden
    case notFound
    case rateLimited
    case serverError(Int)
    case unexpectedStatus(Int)

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid response from server"
        case .decodingFailed(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .badRequest(let message):
            return message
        case .forbidden:
            return "You don't have permission to perform this action"
        case .notFound:
            return "The requested resource was not found"
        case .rateLimited:
            return "Too many requests. Please try again later."
        case .serverError(let code):
            return "Server error (\(code)). Please try again later."
        case .unexpectedStatus(let code):
            return "Unexpected response (\(code))"
        }
    }
}

// MARK: - Empty Response

struct EmptyResponse: Decodable {}

// MARK: - Paginated Response

struct PaginatedResponse<T: Decodable>: Decodable {
    let count: Int
    let next: String?
    let previous: String?
    let results: [T]
}

// MARK: - Conversation Start

struct ConversationStart: Decodable {
    let conversationId: String?
    let message: String?
}

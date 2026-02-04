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
        // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
        self.baseURL = URL(string: "http://127.0.0.1:8000")!
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

    /// Login with username and password
    func login(username: String, password: String) async throws -> TokenResponse {
        let body = ["username": username, "password": password]
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

    /// Request password reset
    func requestPasswordReset(email: String) async throws {
        let body = ["email": email]
        let _: EmptyResponse = try await post("/auth/api/password_reset_request/", body: body, authenticated: false)
    }

    /// Reset password with token
    func resetPassword(token: String, newPassword: String) async throws {
        let body = ["token": token, "new_password": newPassword]
        let _: EmptyResponse = try await post("/auth/api/reset_password/", body: body, authenticated: false)
    }

    /// Resend activation email
    func resendActivationEmail(email: String) async throws {
        let body = ["email": email]
        let _: EmptyResponse = try await post("/auth/api/resend-activation-link/", body: body, authenticated: false)
    }

    /// Update user profile
    func updateProfile(data: [String: Any]) async throws -> User {
        return try await patch("/auth/api/update_profile/", body: data)
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

    /// Get revenue breakdown
    func getRevenueBreakdown() async throws -> RevenueStats {
        return try await get("/chefs/api/me/revenue/")
    }

    // MARK: - Leads Endpoints

    /// Get all leads
    func getLeads(page: Int = 1) async throws -> PaginatedResponse<Lead> {
        return try await get("/chefs/api/me/leads/?page=\(page)")
    }

    /// Get lead details
    func getLead(id: Int) async throws -> Lead {
        return try await get("/chefs/api/me/leads/\(id)/")
    }

    /// Create a new lead
    func createLead(data: [String: Any]) async throws -> Lead {
        return try await post("/chefs/api/me/leads/", body: data)
    }

    /// Update a lead
    func updateLead(id: Int, data: [String: Any]) async throws -> Lead {
        return try await patch("/chefs/api/me/leads/\(id)/", body: data)
    }

    /// Delete a lead
    func deleteLead(id: Int) async throws {
        try await delete("/chefs/api/me/leads/\(id)/")
    }

    /// Get lead interactions
    func getLeadInteractions(leadId: Int) async throws -> [LeadInteraction] {
        return try await get("/chefs/api/me/leads/\(leadId)/interactions/")
    }

    /// Add lead interaction
    func addLeadInteraction(leadId: Int, data: [String: Any]) async throws -> LeadInteraction {
        return try await post("/chefs/api/me/leads/\(leadId)/interactions/", body: data)
    }

    // MARK: - Prep Plans Endpoints

    /// Get all prep plans
    func getPrepPlans() async throws -> [PrepPlan] {
        return try await get("/chefs/api/me/prep-plans/")
    }

    /// Get prep plan details
    func getPrepPlan(id: Int) async throws -> PrepPlan {
        return try await get("/chefs/api/me/prep-plans/\(id)/")
    }

    /// Create prep plan
    func createPrepPlan(data: [String: Any]) async throws -> PrepPlan {
        return try await post("/chefs/api/me/prep-plans/", body: data)
    }

    /// Quick generate prep plan
    func quickGeneratePrepPlan(clientIds: [Int], days: Int) async throws -> PrepPlan {
        let body: [String: Any] = ["client_ids": clientIds, "days": days]
        return try await post("/chefs/api/me/prep-plans/quick-generate/", body: body)
    }

    /// Get prep plan shopping list
    func getPrepPlanShoppingList(planId: Int) async throws -> ShoppingList {
        return try await get("/chefs/api/me/prep-plans/\(planId)/shopping-list/")
    }

    /// Get live shopping list (upcoming commitments)
    func getLiveShoppingList() async throws -> ShoppingList {
        return try await get("/chefs/api/me/prep-plans/live/shopping-list/")
    }

    // MARK: - Proactive Insights Endpoints

    /// Get proactive insights
    func getProactiveInsights() async throws -> [ProactiveInsight] {
        return try await get("/chefs/api/me/insights/")
    }

    /// Dismiss or act on insight
    func handleInsight(id: Int, action: String) async throws {
        let body = ["action": action]
        let _: EmptyResponse = try await post("/chefs/api/me/insights/\(id)/", body: body)
    }

    // MARK: - Telegram Integration

    /// Generate Telegram link code
    func generateTelegramLink() async throws -> TelegramLinkResponse {
        return try await post("/chefs/api/telegram/generate-link/", body: [:])
    }

    /// Unlink Telegram
    func unlinkTelegram() async throws {
        let _: EmptyResponse = try await post("/chefs/api/telegram/unlink/", body: [:])
    }

    /// Get Telegram status
    func getTelegramStatus() async throws -> TelegramStatus {
        return try await get("/chefs/api/telegram/status/")
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

    /// Get chef hub (customer view of specific chef)
    func getChefHub(chefId: Int) async throws -> ChefHub {
        return try await get("/customer_dashboard/api/my-chefs/\(chefId)/")
    }

    // MARK: - Customer Meal Plan Endpoints

    /// Get customer's meal plans
    func getMyMealPlans() async throws -> [CustomerMealPlan] {
        return try await get("/meals/api/my-plans/")
    }

    /// Get current meal plan
    func getCurrentMealPlan() async throws -> CustomerMealPlan {
        return try await get("/meals/api/my-plans/current/")
    }

    /// Get meal plan details
    func getMealPlanDetail(id: Int) async throws -> CustomerMealPlan {
        return try await get("/meals/api/my-plans/\(id)/")
    }

    /// Submit meal plan suggestion
    func submitMealPlanSuggestion(planId: Int, suggestion: String) async throws {
        let body = ["suggestion": suggestion]
        let _: EmptyResponse = try await post("/meals/api/my-plans/\(planId)/suggest/", body: body)
    }

    // MARK: - Customer Orders Endpoints

    /// Get customer's orders
    func getMyOrders() async throws -> [Order] {
        return try await get("/meals/api/my-orders/")
    }

    /// Get chef meal order details
    func getChefMealOrder(orderId: Int) async throws -> ChefMealOrder {
        return try await get("/meals/api/chef-meal-orders/\(orderId)/")
    }

    /// Create chef meal order
    func createChefMealOrder(eventId: Int, quantity: Int, specialRequests: String?) async throws -> ChefMealOrder {
        var body: [String: Any] = ["quantity": quantity]
        if let requests = specialRequests {
            body["special_requests"] = requests
        }
        return try await post("/meals/api/chef-meal-events/\(eventId)/order/", body: body)
    }

    /// Cancel chef meal order
    func cancelChefMealOrder(orderId: Int) async throws {
        let _: EmptyResponse = try await post("/meals/api/chef-meal-orders/\(orderId)/cancel/", body: [:])
    }

    // MARK: - Stripe Payment Endpoints

    /// Process chef meal payment
    func processChefMealPayment(orderId: Int) async throws -> PaymentIntentResponse {
        return try await post("/meals/api/process-chef-meal-payment/\(orderId)/", body: [:])
    }

    /// Get order payment status
    func getOrderPaymentStatus(orderId: Int) async throws -> PaymentStatus {
        return try await get("/meals/api/order-payment-status/\(orderId)/")
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
        // Use URL(string:relativeTo:) to preserve query parameters
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw APIError.invalidURL
        }
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
    case invalidURL
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
        case .invalidURL:
            return "Invalid URL"
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

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

    /// Logout and blacklist refresh token
    func logout(refreshToken: String) async throws {
        let body = ["refresh": refreshToken]
        let _: EmptyResponse = try await post("/auth/api/logout/", body: body, authenticated: true)
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

    /// Change password (authenticated user)
    func changePassword(currentPassword: String, newPassword: String) async throws {
        let body = ["current_password": currentPassword, "new_password": newPassword]
        let _: EmptyResponse = try await post("/auth/api/change_password/", body: body)
    }

    /// Delete account (requires password confirmation)
    func deleteAccount(password: String) async throws {
        let body = ["password": password]
        let _: EmptyResponse = try await post("/auth/api/delete_account/", body: body)
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

    /// Get client notes
    func getClientNotes(clientId: Int) async throws -> [ClientNote] {
        return try await get("/chefs/api/me/clients/\(clientId)/notes/")
    }

    /// Add client note
    func addClientNote(clientId: Int, content: String) async throws -> ClientNote {
        let body = ["content": content]
        return try await post("/chefs/api/me/clients/\(clientId)/notes/", body: body)
    }

    /// Get client receipts
    func getClientReceipts(clientId: Int) async throws -> ClientReceiptsResponse {
        return try await get("/chefs/api/me/clients/\(clientId)/receipts/")
    }

    /// Update client notes (bulk update)
    func updateClientNotes(clientId: Int, notes: String) async throws {
        let body = ["notes": notes]
        let _: EmptyResponse = try await put("/chefs/api/me/clients/\(clientId)/notes/", body: body)
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

    /// Get lead household members
    func getLeadHousehold(leadId: Int) async throws -> [LeadHouseholdMember] {
        return try await get("/chefs/api/me/leads/\(leadId)/household/")
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

    // MARK: - Chef Order Management Endpoints

    /// Get chef's orders with optional status filter
    func getChefOrders(status: String? = nil, page: Int = 1) async throws -> PaginatedResponse<Order> {
        var path = "/chefs/api/me/orders/?page=\(page)"
        if let status = status {
            path += "&status=\(status)"
        }
        return try await get(path)
    }

    /// Get order details
    func getChefOrderDetail(id: Int) async throws -> Order {
        return try await get("/chefs/api/me/orders/\(id)/")
    }

    /// Confirm an order
    func confirmOrder(id: Int) async throws -> Order {
        return try await post("/chefs/api/me/orders/\(id)/confirm/", body: [:])
    }

    /// Cancel an order
    func cancelOrder(id: Int, reason: String?) async throws -> Order {
        var body: [String: Any] = [:]
        if let reason = reason {
            body["reason"] = reason
        }
        return try await post("/chefs/api/me/orders/\(id)/cancel/", body: body)
    }

    /// Adjust order quantity
    func adjustOrderQuantity(id: Int, quantity: Int) async throws -> Order {
        let body: [String: Any] = ["quantity": quantity]
        return try await patch("/chefs/api/me/orders/\(id)/", body: body)
    }

    /// Get calendar items for date range
    func getChefCalendar(startDate: Date, endDate: Date) async throws -> [OrderCalendarItem] {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withFullDate]
        let start = formatter.string(from: startDate)
        let end = formatter.string(from: endDate)
        return try await get("/chefs/api/me/calendar/?start_date=\(start)&end_date=\(end)")
    }

    // MARK: - Chef Meal Events Endpoints

    /// Get chef's meal events
    func getMealEvents(page: Int = 1) async throws -> PaginatedResponse<ChefMealEvent> {
        return try await get("/chefs/api/me/meal-events/?page=\(page)")
    }

    /// Get meal event details
    func getMealEventDetail(id: Int) async throws -> ChefMealEvent {
        return try await get("/chefs/api/me/meal-events/\(id)/")
    }

    /// Create a meal event
    func createMealEvent(data: MealEventCreateRequest) async throws -> ChefMealEvent {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/meal-events/", body: body)
    }

    /// Update a meal event
    func updateMealEvent(id: Int, data: MealEventUpdateRequest) async throws -> ChefMealEvent {
        let body = try encodeToDictionary(data)
        return try await patch("/chefs/api/me/meal-events/\(id)/", body: body)
    }

    /// Cancel a meal event
    func cancelMealEvent(id: Int) async throws {
        let _: EmptyResponse = try await post("/chefs/api/me/meal-events/\(id)/cancel/", body: [:])
    }

    /// Duplicate a meal event
    func duplicateMealEvent(id: Int, newDate: Date?) async throws -> ChefMealEvent {
        var body: [String: Any] = [:]
        if let date = newDate {
            let formatter = ISO8601DateFormatter()
            body["event_date"] = formatter.string(from: date)
        }
        return try await post("/chefs/api/me/meal-events/\(id)/duplicate/", body: body)
    }

    /// Get orders for a meal event
    func getMealEventOrders(eventId: Int) async throws -> [ChefMealOrder] {
        return try await get("/chefs/api/me/meal-events/\(eventId)/orders/")
    }

    // MARK: - Chef Meals Endpoints

    /// Get chef's meals
    func getChefMeals(page: Int = 1) async throws -> PaginatedResponse<Meal> {
        return try await get("/chefs/api/me/meals/?page=\(page)")
    }

    /// Get meal details
    func getMealDetail(id: Int) async throws -> Meal {
        return try await get("/chefs/api/me/meals/\(id)/")
    }

    /// Create a meal
    func createMeal(data: MealCreateRequest) async throws -> Meal {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/meals/", body: body)
    }

    /// Update a meal
    func updateMeal(id: Int, data: MealCreateRequest) async throws -> Meal {
        let body = try encodeToDictionary(data)
        return try await patch("/chefs/api/me/meals/\(id)/", body: body)
    }

    /// Delete a meal
    func deleteMeal(id: Int) async throws {
        try await delete("/chefs/api/me/meals/\(id)/")
    }

    // MARK: - Chef Dishes Endpoints

    /// Get chef's dishes
    func getDishes(page: Int = 1) async throws -> PaginatedResponse<Dish> {
        return try await get("/chefs/api/me/dishes/?page=\(page)")
    }

    /// Get dish details
    func getDishDetail(id: Int) async throws -> Dish {
        return try await get("/chefs/api/me/dishes/\(id)/")
    }

    /// Create a dish
    func createDish(data: DishCreateRequest) async throws -> Dish {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/dishes/", body: body)
    }

    /// Update a dish
    func updateDish(id: Int, data: DishCreateRequest) async throws -> Dish {
        let body = try encodeToDictionary(data)
        return try await patch("/chefs/api/me/dishes/\(id)/", body: body)
    }

    /// Delete a dish
    func deleteDish(id: Int) async throws {
        try await delete("/chefs/api/me/dishes/\(id)/")
    }

    // MARK: - Chef Ingredients Endpoints

    /// Get chef's ingredients
    func getIngredients(page: Int = 1) async throws -> PaginatedResponse<Ingredient> {
        return try await get("/chefs/api/me/ingredients/?page=\(page)")
    }

    /// Search ingredients
    func searchIngredients(query: String) async throws -> [Ingredient] {
        let encoded = query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query
        return try await get("/chefs/api/me/ingredients/search/?q=\(encoded)")
    }

    /// Create an ingredient
    func createIngredient(name: String, category: String?, unit: String?) async throws -> Ingredient {
        var body: [String: Any] = ["name": name]
        if let category = category {
            body["category"] = category
        }
        if let unit = unit {
            body["unit"] = unit
        }
        return try await post("/chefs/api/me/ingredients/", body: body)
    }

    /// Update an ingredient
    func updateIngredient(id: Int, name: String, category: String?, unit: String?) async throws -> Ingredient {
        var body: [String: Any] = ["name": name]
        if let category = category {
            body["category"] = category
        }
        if let unit = unit {
            body["unit"] = unit
        }
        return try await patch("/chefs/api/me/ingredients/\(id)/", body: body)
    }

    /// Delete an ingredient
    func deleteIngredient(id: Int) async throws {
        try await delete("/chefs/api/me/ingredients/\(id)/")
    }

    // MARK: - Chef Service Offerings Endpoints

    /// Get chef's service offerings
    func getServiceOfferings(page: Int = 1) async throws -> PaginatedResponse<ServiceOffering> {
        return try await get("/chefs/api/me/services/?page=\(page)")
    }

    /// Get service offering details
    func getServiceOfferingDetail(id: Int) async throws -> ServiceOffering {
        return try await get("/chefs/api/me/services/\(id)/")
    }

    /// Create a service offering
    func createServiceOffering(data: ServiceOfferingCreateRequest) async throws -> ServiceOffering {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/services/", body: body)
    }

    /// Update a service offering
    func updateServiceOffering(id: Int, data: ServiceOfferingCreateRequest) async throws -> ServiceOffering {
        let body = try encodeToDictionary(data)
        return try await patch("/chefs/api/me/services/\(id)/", body: body)
    }

    /// Delete a service offering
    func deleteServiceOffering(id: Int) async throws {
        try await delete("/chefs/api/me/services/\(id)/")
    }

    /// Add price tier to service offering
    func addPriceTier(offeringId: Int, data: PriceTierCreateRequest) async throws -> PriceTier {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/services/\(offeringId)/tiers/", body: body)
    }

    /// Update price tier
    func updatePriceTier(offeringId: Int, tierId: Int, data: PriceTierCreateRequest) async throws -> PriceTier {
        let body = try encodeToDictionary(data)
        return try await patch("/chefs/api/me/services/\(offeringId)/tiers/\(tierId)/", body: body)
    }

    /// Delete price tier
    func deletePriceTier(offeringId: Int, tierId: Int) async throws {
        try await delete("/chefs/api/me/services/\(offeringId)/tiers/\(tierId)/")
    }

    // MARK: - Collaborative Meal Plan Endpoints

    /// Get meal plans for a client
    func getClientMealPlans(clientId: Int, page: Int = 1) async throws -> PaginatedResponse<MealPlan> {
        return try await get("/chefs/api/me/clients/\(clientId)/plans/?page=\(page)")
    }

    /// Get all meal plans
    func getMealPlans(status: MealPlanStatus? = nil, page: Int = 1) async throws -> PaginatedResponse<MealPlan> {
        var path = "/chefs/api/me/plans/?page=\(page)"
        if let status = status {
            path += "&status=\(status.rawValue)"
        }
        return try await get(path)
    }

    /// Get meal plan details
    func getMealPlanDetail(id: Int) async throws -> MealPlan {
        return try await get("/chefs/api/me/plans/\(id)/")
    }

    /// Create a meal plan
    func createMealPlan(data: MealPlanCreateRequest) async throws -> MealPlan {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/plans/", body: body)
    }

    /// Publish a meal plan
    func publishMealPlan(id: Int) async throws -> MealPlan {
        return try await post("/chefs/api/me/plans/\(id)/publish/", body: [:])
    }

    /// Add a day to meal plan
    func addMealPlanDay(planId: Int, data: MealPlanDayCreateRequest) async throws -> MealPlanDay {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/plans/\(planId)/days/", body: body)
    }

    /// Add item to meal plan day
    func addMealPlanItem(planId: Int, dayId: Int, data: MealPlanItemCreateRequest) async throws -> MealPlanItem {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/plans/\(planId)/days/\(dayId)/items/", body: body)
    }

    /// Delete meal plan item
    func deleteMealPlanItem(planId: Int, dayId: Int, itemId: Int) async throws {
        try await delete("/chefs/api/me/plans/\(planId)/days/\(dayId)/items/\(itemId)/")
    }

    /// Get meal plan suggestions
    func getMealPlanSuggestions(planId: Int) async throws -> [MealPlanSuggestion] {
        return try await get("/chefs/api/me/plans/\(planId)/suggestions/")
    }

    /// Respond to meal plan suggestion
    func respondToSuggestion(suggestionId: Int, data: SuggestionResponseRequest) async throws -> MealPlanSuggestion {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/suggestions/\(suggestionId)/respond/", body: body)
    }

    /// AI generate meals for plan
    func generateMealPlanMeals(planId: Int, data: MealPlanGenerateRequest) async throws -> MealPlan {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/plans/\(planId)/generate/", body: body)
    }

    // MARK: - Prep Planning Endpoints

    /// Get prep plans
    func getPrepPlans(status: PrepPlanStatus? = nil, page: Int = 1) async throws -> PaginatedResponse<PrepPlan> {
        var path = "/chefs/api/me/prep-plans/?page=\(page)"
        if let status = status {
            path += "&status=\(status.rawValue)"
        }
        return try await get(path)
    }

    /// Get prep plan details
    func getPrepPlanDetail(id: Int) async throws -> PrepPlan {
        return try await get("/chefs/api/me/prep-plans/\(id)/")
    }

    /// Get shopping list for prep plan
    func getShoppingList(prepPlanId: Int) async throws -> ShoppingList {
        return try await get("/chefs/api/me/prep-plans/\(prepPlanId)/shopping-list/")
    }

    /// Mark shopping list item as purchased
    func markItemPurchased(prepPlanId: Int, itemId: Int, purchased: Bool) async throws -> ShoppingListItem {
        let body: [String: Any] = ["is_purchased": purchased]
        return try await patch("/chefs/api/me/prep-plans/\(prepPlanId)/shopping-list/\(itemId)/", body: body)
    }

    /// Mark all items as purchased
    func markAllPurchased(prepPlanId: Int) async throws {
        let _: EmptyResponse = try await post("/chefs/api/me/prep-plans/\(prepPlanId)/mark-purchased/", body: [:])
    }

    /// Quick generate prep plan from orders
    func quickGeneratePrepPlan(orderIds: [Int]) async throws -> PrepPlan {
        let body: [String: Any] = ["order_ids": orderIds]
        return try await post("/chefs/api/me/prep-plans/quick-generate/", body: body)
    }

    /// Get live commitments
    func getLiveCommitments() async throws -> [PrepPlanClient] {
        return try await get("/chefs/api/me/prep-plans/live/commitments/")
    }

    // MARK: - Notification Endpoints

    /// Get notifications
    func getNotifications(page: Int = 1) async throws -> PaginatedResponse<AppNotification> {
        return try await get("/chefs/api/me/notifications/?page=\(page)")
    }

    /// Get unread notification count
    func getUnreadNotificationCount() async throws -> NotificationBadge {
        return try await get("/chefs/api/me/notifications/unread-count/")
    }

    /// Mark notification as read
    func markNotificationRead(id: Int) async throws {
        let _: EmptyResponse = try await post("/chefs/api/me/notifications/\(id)/read/", body: [:])
    }

    /// Mark all notifications as read
    func markAllNotificationsRead() async throws {
        let _: EmptyResponse = try await post("/chefs/api/me/notifications/mark-all-read/", body: [:])
    }

    /// Dismiss notification
    func dismissNotification(id: Int) async throws {
        let _: EmptyResponse = try await post("/chefs/api/me/notifications/\(id)/dismiss/", body: [:])
    }

    /// Get notification preferences
    func getNotificationPreferences() async throws -> NotificationPreferences {
        return try await get("/chefs/api/me/notifications/preferences/")
    }

    /// Update notification preferences
    func updateNotificationPreferences(data: NotificationPreferences) async throws -> NotificationPreferences {
        let body = try encodeToDictionary(data)
        return try await patch("/chefs/api/me/notifications/preferences/", body: body)
    }

    // MARK: - Messaging Endpoints

    /// Get conversations
    func getConversations(page: Int = 1) async throws -> PaginatedResponse<Conversation> {
        return try await get("/messaging/api/conversations/?page=\(page)")
    }

    /// Get conversation messages
    func getConversationMessages(conversationId: Int, page: Int = 1) async throws -> PaginatedResponse<Message> {
        return try await get("/messaging/api/conversations/\(conversationId)/?page=\(page)")
    }

    /// Send message
    func sendMessage(conversationId: Int, content: String) async throws -> Message {
        let body: [String: Any] = ["content": content]
        return try await post("/messaging/api/conversations/\(conversationId)/send/", body: body)
    }

    /// Get unread message counts
    func getUnreadMessageCounts() async throws -> UnreadCounts {
        return try await get("/messaging/api/unread-counts/")
    }

    /// Mark conversation as read
    func markConversationRead(conversationId: Int) async throws {
        let _: EmptyResponse = try await post("/messaging/api/conversations/\(conversationId)/read/", body: [:])
    }

    /// Start conversation with user
    func startConversation(userId: Int, message: String) async throws -> Conversation {
        let body: [String: Any] = ["user_id": userId, "message": message]
        return try await post("/messaging/api/conversations/start/", body: body)
    }

    // MARK: - Review Endpoints

    /// Get my reviews
    func getMyReviews(page: Int = 1) async throws -> PaginatedResponse<Review> {
        return try await get("/reviews/my_reviews/?page=\(page)")
    }

    /// Get review summary
    func getReviewSummary() async throws -> ReviewSummary {
        return try await get("/reviews/my_reviews/summary/")
    }

    /// Reply to review
    func replyToReview(reviewId: Int, content: String) async throws -> ReviewResponse {
        let body: [String: Any] = ["content": content]
        return try await post("/reviews/\(reviewId)/reply/", body: body)
    }

    // MARK: - Chef Profile Endpoints

    /// Get chef profile
    func getChefProfile() async throws -> ChefProfile {
        return try await get("/chefs/api/me/chef/profile/")
    }

    /// Update chef profile
    func updateChefProfile(data: ChefProfileUpdateRequest) async throws -> ChefProfile {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/chef/profile/update/", body: body)
    }

    /// Get chef photos
    func getChefPhotos() async throws -> [ChefPhoto] {
        return try await get("/chefs/api/me/chef/photos/")
    }

    /// Delete chef photo
    func deleteChefPhoto(id: Int) async throws {
        try await delete("/chefs/api/me/chef/photos/\(id)/")
    }

    /// Set break status
    func setBreakStatus(onBreak: Bool, returnDate: Date?) async throws -> ChefProfile {
        var body: [String: Any] = ["on_break": onBreak]
        if let returnDate = returnDate {
            let formatter = ISO8601DateFormatter()
            body["return_date"] = formatter.string(from: returnDate)
        }
        return try await post("/chefs/api/me/chef/break/", body: body)
    }

    /// Set live status
    func setLiveStatus(isLive: Bool) async throws -> ChefProfile {
        let body: [String: Any] = ["is_live": isLive]
        return try await post("/chefs/api/me/chef/live/", body: body)
    }

    // MARK: - Service Area Endpoints

    /// Get service areas
    func getServiceAreas() async throws -> [ServiceArea] {
        return try await get("/local_chefs/api/chef/service-areas/")
    }

    /// Add service area
    func addServiceArea(postalCode: String, radius: Int?) async throws -> ServiceArea {
        var body: [String: Any] = ["postal_code": postalCode]
        if let radius = radius {
            body["radius"] = radius
        }
        return try await post("/local_chefs/api/chef/service-areas/add/", body: body)
    }

    /// Remove service area
    func removeServiceArea(id: Int) async throws {
        try await delete("/local_chefs/api/chef/service-areas/\(id)/remove/")
    }

    /// Add postal codes to service area
    func addPostalCodes(areaId: Int, postalCodes: [String]) async throws -> ServiceArea {
        let body: [String: Any] = ["postal_codes": postalCodes]
        return try await post("/local_chefs/api/chef/service-areas/\(areaId)/postal-codes/add/", body: body)
    }

    // MARK: - Verification Endpoints

    /// Get verification documents
    func getVerificationDocuments() async throws -> [VerificationDocument] {
        return try await get("/chefs/api/me/documents/")
    }

    /// Get verification status
    func getVerificationStatus() async throws -> VerificationStatus {
        return try await get("/chefs/api/me/documents/status/")
    }

    /// Schedule verification meeting
    func scheduleVerificationMeeting(date: Date, notes: String?) async throws -> VerificationMeeting {
        var body: [String: Any] = [:]
        let formatter = ISO8601DateFormatter()
        body["date"] = formatter.string(from: date)
        if let notes = notes {
            body["notes"] = notes
        }
        return try await post("/chefs/api/me/verification-meeting/schedule/", body: body)
    }

    // MARK: - Payment Endpoints

    /// Get Stripe account status
    func getStripeAccountStatus() async throws -> StripeAccountStatus {
        return try await get("/meals/api/stripe-account-status/")
    }

    /// Create Stripe account link
    func createStripeAccountLink() async throws -> StripeAccountLink {
        return try await post("/meals/api/stripe-account-link/", body: [:])
    }

    /// Get payment links
    func getPaymentLinks(page: Int = 1) async throws -> PaginatedResponse<PaymentLink> {
        return try await get("/chefs/api/me/payment-links/?page=\(page)")
    }

    /// Create payment link
    func createPaymentLink(data: PaymentLinkCreateRequest) async throws -> PaymentLink {
        let body = try encodeToDictionary(data)
        return try await post("/chefs/api/me/payment-links/", body: body)
    }

    /// Send payment link
    func sendPaymentLink(id: Int, method: String) async throws {
        let body: [String: Any] = ["method": method]
        let _: EmptyResponse = try await post("/chefs/api/me/payment-links/\(id)/send/", body: body)
    }

    /// Get payment link stats
    func getPaymentLinkStats() async throws -> PaymentLinkStats {
        return try await get("/chefs/api/me/payment-links/stats/")
    }

    /// Get receipts
    func getReceipts(page: Int = 1) async throws -> PaginatedResponse<Receipt> {
        return try await get("/chefs/api/me/receipts/?page=\(page)")
    }

    /// Get receipt details
    func getReceiptDetail(id: Int) async throws -> Receipt {
        return try await get("/chefs/api/me/receipts/\(id)/")
    }

    /// Get receipt stats
    func getReceiptStats() async throws -> ReceiptStats {
        return try await get("/chefs/api/me/receipts/stats/")
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
        #if DEBUG
        print("🌐 API: \(request.httpMethod ?? "?") \(request.url?.absoluteString ?? "?")")
        #endif

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        #if DEBUG
        print("📥 \(httpResponse.statusCode) \(request.url?.path ?? "")")
        if httpResponse.statusCode >= 400 {
            if let body = String(data: data, encoding: .utf8) {
                print("❌ Error: \(body.prefix(500))")
            }
        }
        #endif

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
                #if DEBUG
                print("❌ Decoding error: \(error)")
                if let body = String(data: data, encoding: .utf8) {
                    print("📄 Body: \(body.prefix(1000))")
                }
                #endif
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

    /// Encode Codable object to dictionary
    private func encodeToDictionary<T: Encodable>(_ value: T) throws -> [String: Any] {
        let data = try encoder.encode(value)
        guard let dictionary = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw APIError.invalidResponse
        }
        return dictionary
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

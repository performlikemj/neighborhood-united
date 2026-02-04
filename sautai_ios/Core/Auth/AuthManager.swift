//
//  AuthManager.swift
//  sautai_ios
//
//  Handles authentication state, JWT tokens, and role switching.
//  Uses Keychain for secure token storage.
//

import Foundation
import SwiftUI

// MARK: - User Role

enum UserRole: String, Codable {
    case chef
    case customer
}

// MARK: - Auth Manager

@MainActor
class AuthManager: ObservableObject {

    // MARK: - Singleton

    static let shared = AuthManager()

    // MARK: - Published State

    @Published var isAuthenticated = false
    @Published var currentUser: User?
    @Published var currentRole: UserRole = .customer
    @Published var isLoading = false
    @Published var error: AuthError?

    // MARK: - Private Properties

    private let keychainService = KeychainService.shared
    private let apiClient = APIClient.shared

    /// In-memory access token for fast access
    private var accessToken: String?

    // MARK: - Token Keys

    private enum TokenKey {
        static let access = "sautai.accessToken"
        static let refresh = "sautai.refreshToken"
    }

    // MARK: - Initialization

    private init() {
        // Check for existing session on launch
        Task {
            await restoreSession()
        }
    }

    // MARK: - Public Methods

    /// Login with email and password
    func login(email: String, password: String) async throws {
        isLoading = true
        error = nil

        defer { isLoading = false }

        do {
            let response = try await apiClient.login(email: email, password: password)

            // Store tokens
            accessToken = response.access
            try keychainService.save(response.access, forKey: TokenKey.access)
            try keychainService.save(response.refresh, forKey: TokenKey.refresh)

            // Fetch user profile
            try await fetchUserProfile()

            isAuthenticated = true

        } catch let apiError as APIError {
            error = .apiError(apiError)
            throw error!
        } catch {
            self.error = .unknown(error)
            throw self.error!
        }
    }

    /// Register a new account
    func register(
        email: String,
        password: String,
        username: String,
        phoneNumber: String? = nil
    ) async throws {
        isLoading = true
        error = nil

        defer { isLoading = false }

        do {
            _ = try await apiClient.register(
                email: email,
                password: password,
                username: username,
                phoneNumber: phoneNumber
            )

            // Registration successful - user needs to verify email
            // Don't auto-login; show verification screen

        } catch let apiError as APIError {
            error = .apiError(apiError)
            throw error!
        } catch {
            self.error = .unknown(error)
            throw self.error!
        }
    }

    /// Logout and clear all tokens
    func logout() {
        accessToken = nil
        try? keychainService.delete(forKey: TokenKey.access)
        try? keychainService.delete(forKey: TokenKey.refresh)

        currentUser = nil
        isAuthenticated = false
        currentRole = .customer
        error = nil
    }

    /// Switch between chef and customer roles
    func switchRole(to role: UserRole) async throws {
        guard isAuthenticated else { return }

        isLoading = true
        defer { isLoading = false }

        do {
            try await apiClient.switchRole(to: role.rawValue)
            currentRole = role

            // Refresh user profile to get updated role info
            try await fetchUserProfile()

        } catch let apiError as APIError {
            error = .apiError(apiError)
            throw error!
        }
    }

    /// Refresh the access token using refresh token
    func refreshAccessToken() async throws {
        guard let refreshToken = try? keychainService.load(forKey: TokenKey.refresh) else {
            throw AuthError.noRefreshToken
        }

        do {
            let response = try await apiClient.refreshToken(refreshToken: refreshToken)

            accessToken = response.access
            try keychainService.save(response.access, forKey: TokenKey.access)

        } catch {
            // Refresh failed - force logout
            logout()
            throw AuthError.sessionExpired
        }
    }

    /// Get current access token (refreshing if needed)
    func getAccessToken() async throws -> String {
        if let token = accessToken {
            return token
        }

        // Try to load from keychain
        if let token = try? keychainService.load(forKey: TokenKey.access) {
            accessToken = token
            return token
        }

        // Try to refresh
        try await refreshAccessToken()

        guard let token = accessToken else {
            throw AuthError.noAccessToken
        }

        return token
    }

    // MARK: - Private Methods

    /// Restore session from stored tokens
    private func restoreSession() async {
        guard let _ = try? keychainService.load(forKey: TokenKey.refresh) else {
            // No refresh token - not logged in
            return
        }

        do {
            // Try to refresh and fetch profile
            try await refreshAccessToken()
            try await fetchUserProfile()
            isAuthenticated = true
        } catch {
            // Session restoration failed - clear tokens
            logout()
        }
    }

    /// Fetch user profile from API
    private func fetchUserProfile() async throws {
        let user = try await apiClient.getUserProfile()
        currentUser = user
        currentRole = user.currentRole == "chef" ? .chef : .customer
    }
}

// MARK: - Auth Error

enum AuthError: LocalizedError {
    case noAccessToken
    case noRefreshToken
    case sessionExpired
    case invalidCredentials
    case emailNotVerified
    case apiError(APIError)
    case unknown(Error)

    var errorDescription: String? {
        switch self {
        case .noAccessToken:
            return "No access token available"
        case .noRefreshToken:
            return "No refresh token available"
        case .sessionExpired:
            return "Your session has expired. Please log in again."
        case .invalidCredentials:
            return "Invalid email or password"
        case .emailNotVerified:
            return "Please verify your email address"
        case .apiError(let error):
            return error.localizedDescription
        case .unknown(let error):
            return error.localizedDescription
        }
    }
}

// MARK: - Token Response

struct TokenResponse: Codable {
    let access: String
    let refresh: String
}

struct RefreshTokenResponse: Codable {
    let access: String
}

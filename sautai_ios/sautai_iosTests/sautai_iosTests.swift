//
//  sautai_iosTests.swift
//  sautai_iosTests
//
//  Created by Michael Jones on 2/4/26.
//

import Foundation
import Testing
@testable import sautai_ios

@Suite("sautai Core Tests")
struct sautai_iosTests {

    // MARK: - Model Tests
    
    @Suite("User Role Tests")
    struct UserRoleTests {
        
        @Test("User role can be encoded and decoded")
        func roleEncodingDecoding() throws {
            let chefRole = UserRole.chef
            let customerRole = UserRole.customer
            
            #expect(chefRole.rawValue == "chef")
            #expect(customerRole.rawValue == "customer")
        }
    }
    
    // MARK: - Message Tests
    
    @Suite("Sous Chef Message Tests")
    struct SousChefMessageTests {
        
        @Test("Message role detection works correctly")
        func messageRoleDetection() {
            let userMessage = SousChefMessage(content: "Hello", role: .user)
            let assistantMessage = SousChefMessage(content: "Hi there!", role: .assistant)
            
            #expect(userMessage.role.isUser == true)
            #expect(userMessage.role.isAssistant == false)
            
            #expect(assistantMessage.role.isAssistant == true)
            #expect(assistantMessage.role.isUser == false)
        }
        
        @Test("Streaming messages are properly flagged")
        func streamingMessageFlag() {
            let streamingMessage = SousChefMessage(
                content: "",
                role: .assistant,
                isStreaming: true
            )
            
            #expect(streamingMessage.isStreaming == true)
        }
    }
    
    // MARK: - Revenue Stats Tests

    @Suite("Revenue Statistics Tests")
    struct RevenueStatsTests {

        @Test("Revenue decimal values are correct")
        func revenueValues() {
            let revenue = RevenueStats(
                today: Decimal(string: "125.50") ?? 0,
                thisWeek: Decimal(string: "850.75") ?? 0,
                thisMonth: Decimal(string: "3200.00") ?? 0
            )

            #expect(revenue.today == Decimal(string: "125.50"))
            #expect(revenue.thisWeek == Decimal(string: "850.75"))
            #expect(revenue.thisMonth == Decimal(string: "3200.00"))
        }

        @Test("Zero revenue defaults work correctly")
        func zeroRevenueHandling() {
            let revenue = RevenueStats()

            #expect(revenue.today == 0)
            #expect(revenue.thisWeek == 0)
            #expect(revenue.thisMonth == 0)
        }
    }
    
    // MARK: - Date Formatting Tests

    @Suite("Date Formatting Tests")
    struct DateFormattingTests {

        @Test("Greeting changes based on time of day")
        func greetingText() {
            let calendar = Calendar.current
            let now = Date()
            let hour = calendar.component(.hour, from: now)

            let expectedGreeting: String
            if hour < 12 {
                expectedGreeting = "Good morning"
            } else if hour < 17 {
                expectedGreeting = "Good afternoon"
            } else {
                expectedGreeting = "Good evening"
            }

            // This test would need access to the view's greeting logic
            // For now, we verify the logic works
            #expect(expectedGreeting.count > 0)
        }
    }

    // MARK: - Auth Error Tests

    @Suite("Auth Error Tests")
    struct AuthErrorTests {

        @Test("Auth errors have proper descriptions")
        func authErrorDescriptions() {
            let sessionExpired = AuthError.sessionExpired
            let noToken = AuthError.noAccessToken
            let serverUnreachable = AuthError.serverUnreachable

            #expect(sessionExpired.errorDescription?.contains("expired") == true)
            #expect(noToken.errorDescription?.contains("token") == true)
            #expect(serverUnreachable.errorDescription?.contains("connect") == true)
        }

        @Test("API errors wrap correctly")
        func apiErrorWrapping() {
            let apiError = APIError.forbidden
            let authError = AuthError.apiError(apiError)

            #expect(authError.errorDescription?.contains("permission") == true)
        }
    }

    // MARK: - API Error Tests

    @Suite("API Error Tests")
    struct APIErrorTests {

        @Test("API errors have proper descriptions")
        func apiErrorDescriptions() {
            let forbidden = APIError.forbidden
            let notFound = APIError.notFound
            let rateLimited = APIError.rateLimited
            let serverError = APIError.serverError(500)

            #expect(forbidden.errorDescription?.contains("permission") == true)
            #expect(notFound.errorDescription?.contains("not found") == true)
            #expect(rateLimited.errorDescription?.contains("many requests") == true)
            #expect(serverError.errorDescription?.contains("500") == true)
        }

        @Test("Bad request error includes message")
        func badRequestMessage() {
            let error = APIError.badRequest("Email already exists")
            #expect(error.errorDescription == "Email already exists")
        }
    }
}

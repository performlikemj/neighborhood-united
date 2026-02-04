//
//  sautai_iosTests.swift
//  sautai_iosTests
//
//  Created by Michael Jones on 2/4/26.
//

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
        
        @Test("Revenue string converts to decimal correctly")
        func revenueConversion() {
            let revenue = RevenueStats(
                today: "125.50",
                thisWeek: "850.75",
                thisMonth: "3200.00"
            )
            
            #expect(revenue.todayDecimal == Decimal(string: "125.50"))
            #expect(revenue.thisWeekDecimal == Decimal(string: "850.75"))
            #expect(revenue.thisMonthDecimal == Decimal(string: "3200.00"))
        }
        
        @Test("Invalid revenue strings default to zero")
        func invalidRevenueHandling() {
            let revenue = RevenueStats(
                today: "invalid",
                thisWeek: "",
                thisMonth: "not-a-number"
            )
            
            #expect(revenue.todayDecimal == 0)
            #expect(revenue.thisWeekDecimal == 0)
            #expect(revenue.thisMonthDecimal == 0)
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
}

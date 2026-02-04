//
//  LoginUITests.swift
//  sautai_iosUITests
//
//  Comprehensive UI tests for the login and authentication flows.
//

import XCTest

final class LoginUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        
        app = XCUIApplication()
        app.launchArguments = ["UI-Testing"]
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Login Screen Tests

    @MainActor
    func testLoginScreenAppears() throws {
        app.launch()
        
        // Verify login screen elements exist
        XCTAssertTrue(app.staticTexts["sautai"].exists, "App logo should be visible")
        XCTAssertTrue(app.staticTexts["\"Artful kitchens. Shared hearts.\""].exists, "Tagline should be visible")
        
        // Check for form fields
        XCTAssertTrue(app.textFields["Email"].exists, "Email field should exist")
        XCTAssertTrue(app.secureTextFields.element(boundBy: 0).exists, "Password field should exist")
        
        // Check for buttons
        XCTAssertTrue(app.buttons["Log In"].exists, "Login button should exist")
        XCTAssertTrue(app.buttons["Create Account"].exists, "Create Account button should exist")
    }
    
    @MainActor
    func testNavigateToRegistration() throws {
        app.launch()
        
        // Tap create account button
        app.buttons["Create Account"].tap()
        
        // Verify registration screen appears
        XCTAssertTrue(app.staticTexts["Join sautai"].exists, "Registration screen should appear")
        XCTAssertTrue(app.textFields["Full Name"].exists, "Name field should exist on registration")
    }
    
    @MainActor
    func testEmailValidation() throws {
        app.launch()
        
        let emailField = app.textFields["Email"]
        let passwordField = app.secureTextFields.element(boundBy: 0)
        let loginButton = app.buttons["Log In"]
        
        // Login button should be disabled when fields are empty
        XCTAssertFalse(loginButton.isEnabled, "Login button should be disabled when fields are empty")
        
        // Enter email only
        emailField.tap()
        emailField.typeText("test@example.com")
        
        // Button should still be disabled (no password)
        XCTAssertFalse(loginButton.isEnabled, "Login button should be disabled when password is empty")
        
        // Enter password
        passwordField.tap()
        passwordField.typeText("password123")
        
        // Now button should be enabled
        XCTAssertTrue(loginButton.isEnabled, "Login button should be enabled when both fields are filled")
    }
}

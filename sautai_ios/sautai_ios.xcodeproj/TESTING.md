# Testing Guide for sautai iOS App

This guide covers all the ways to test the sautai application, from manual testing to automated tests.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Manual Testing](#manual-testing)
3. [Unit Tests](#unit-tests)
4. [UI Tests](#ui-tests)
5. [Testing Strategies](#testing-strategies)
6. [Mock Data Setup](#mock-data-setup)

---

## Prerequisites

### Backend Setup

Your app requires a backend API to function. Before testing:

1. **Local Development**: Start your backend server at `http://localhost:8000`
2. **Production**: Update the API URL in `APIClient.swift`

### Test Accounts

Create test accounts for both user roles:
- **Chef Account**: For testing chef-specific features
- **Customer Account**: For testing customer features

---

## Manual Testing

### Running the App

1. Open the project in Xcode
2. Select a simulator (e.g., iPhone 15 Pro)
3. Press `Cmd + R` or click the Play button
4. The app will launch in the simulator

### Test Scenarios

#### 1. Authentication Flow
- [ ] Launch app (should show login screen)
- [ ] Tap "Create Account" (should navigate to registration)
- [ ] Fill in registration form
- [ ] Toggle password visibility
- [ ] Submit registration
- [ ] Login with created account
- [ ] Logout from Settings

#### 2. Chef Experience
- [ ] Login as chef
- [ ] View dashboard (revenue, stats)
- [ ] Navigate to Clients tab
- [ ] Access Sous Chef AI
- [ ] Send message to AI
- [ ] Watch streaming response
- [ ] View meal plans
- [ ] Access settings

#### 3. Customer Experience
- [ ] Login as customer
- [ ] View home dashboard
- [ ] Browse "Find Chefs" tab
- [ ] View chef profiles
- [ ] Send message to chef
- [ ] View conversations
- [ ] Access settings

#### 4. AI Sous Chef
- [ ] Open Sous Chef tab
- [ ] Send a message (e.g., "Help me plan a vegetarian meal")
- [ ] Observe streaming response
- [ ] Send follow-up questions
- [ ] Start new conversation
- [ ] Verify conversation history

#### 5. Messaging
- [ ] Send message to chef/customer
- [ ] Receive response
- [ ] View conversation history
- [ ] Check unread indicators

---

## Unit Tests

### Running Unit Tests

**Via Xcode:**
1. Press `Cmd + U` to run all tests
2. Or click the diamond icon next to individual tests

**Via Command Line:**
```bash
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

### Test Structure

We use the **Swift Testing framework** (not XCTest) for unit tests:

```swift
import Testing
@testable import sautai_ios

@Suite("Feature Tests")
struct MyTests {
    
    @Test("Test description")
    func testSomething() {
        #expect(value == expectedValue)
    }
}
```

### Current Unit Tests

Located in `sautai_iosTests.swift`:

- **User Role Tests**: Role encoding/decoding
- **Message Tests**: Message role detection, streaming flags
- **Revenue Stats Tests**: String to Decimal conversion
- **Date Formatting Tests**: Greeting text logic

### Adding New Unit Tests

Example test for a new feature:

```swift
@Suite("Meal Plan Tests")
struct MealPlanTests {
    
    @Test("Meal plan can be created")
    func createMealPlan() throws {
        let mealPlan = MealPlan(
            id: 1,
            name: "Weekly Vegan Plan",
            clientId: 10
        )
        
        #expect(mealPlan.name == "Weekly Vegan Plan")
        #expect(mealPlan.clientId == 10)
    }
}
```

---

## UI Tests

### Running UI Tests

**Via Xcode:**
1. Press `Cmd + U` to run all tests
2. Select only UI test target to run UI tests separately

**Via Command Line:**
```bash
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15 Pro' -only-testing:sautai_iosUITests
```

### Current UI Tests

Located in `sautai_iosUITests.swift` and `LoginUITests.swift`:

- **Login Screen Tests**: Verify UI elements exist
- **Navigation Tests**: Registration flow, tab navigation
- **Form Validation Tests**: Email/password validation
- **Performance Tests**: Launch time, scroll performance

### Adding New UI Tests

Example UI test:

```swift
@MainActor
func testSousChefChat() throws {
    // Launch and login (you'll need to implement login helper)
    app.launch()
    loginAsChef()
    
    // Navigate to Sous Chef
    app.tabBars.buttons["Sous Chef"].tap()
    
    // Verify chat interface
    XCTAssertTrue(app.navigationBars["Sous Chef"].exists)
    
    // Type message
    let inputField = app.textFields["Ask Sous Chef anything..."]
    inputField.tap()
    inputField.typeText("Hello, Sous Chef!")
    
    // Send message
    app.buttons["arrow.up.circle.fill"].tap()
    
    // Verify message appears
    XCTAssertTrue(app.staticTexts["Hello, Sous Chef!"].exists)
}
```

---

## Testing Strategies

### Test Pyramid

Follow the testing pyramid approach:

```
        /\
       /UI\      (Few - Slow - Expensive)
      /____\
     /      \
    / Integ- \   (Some - Medium Speed)
   / ration  \
  /___________\
 /             \
/  Unit Tests  \  (Many - Fast - Cheap)
/_______________\
```

### Test Coverage Goals

- **Unit Tests**: 70%+ code coverage
- **Integration Tests**: Critical user flows
- **UI Tests**: Main user journeys

### What to Test

#### ✅ Do Test:
- Business logic (revenue calculations, validations)
- Data transformations (JSON decoding, date formatting)
- User flows (login → dashboard → feature)
- Error handling
- Edge cases (empty states, network failures)

#### ❌ Don't Test:
- SwiftUI framework internals
- Third-party libraries
- Simple getters/setters
- Trivial code

---

## Mock Data Setup

### Creating Mock API Responses

For testing without a backend, create mock responses:

```swift
// In your test file
extension APIClient {
    static var mock: APIClient {
        let client = APIClient()
        // Configure with mock data
        return client
    }
}
```

### Using SwiftUI Previews

Leverage Xcode Previews for visual testing:

```swift
#Preview {
    ChefDashboardView()
        .environmentObject(AuthManager.shared)
}

#Preview("Dark Mode") {
    ChefDashboardView()
        .preferredColorScheme(.dark)
}

#Preview("With Data") {
    let mockDashboard = ChefDashboard(
        revenue: RevenueStats(
            today: "125.50",
            thisWeek: "850.00",
            thisMonth: "3200.00"
        ),
        clients: ClientStats(total: 15, active: 12, newThisMonth: 3),
        orders: OrderStats(upcoming: 8, completedThisMonth: 24),
        topServices: []
    )
    
    // Pass mock data to view
    ChefDashboardView()
}
```

### Test Data Builders

Create helper functions for test data:

```swift
extension User {
    static func mockChef() -> User {
        User(
            id: 1,
            email: "chef@test.com",
            displayName: "Test Chef",
            role: .chef,
            isVerified: true
        )
    }
    
    static func mockCustomer() -> User {
        User(
            id: 2,
            email: "customer@test.com",
            displayName: "Test Customer",
            role: .customer,
            isVerified: true
        )
    }
}
```

---

## Continuous Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Run Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: macos-14
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Select Xcode
      run: sudo xcode-select -s /Applications/Xcode_15.2.app
    
    - name: Run Unit Tests
      run: |
        xcodebuild test \
          -scheme sautai_ios \
          -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
          -only-testing:sautai_iosTests
    
    - name: Run UI Tests
      run: |
        xcodebuild test \
          -scheme sautai_ios \
          -destination 'platform=iOS Simulator,name=iPhone 15 Pro' \
          -only-testing:sautai_iosUITests
```

---

## Debugging Tests

### Test Debugging Tips

1. **Set Breakpoints**: Click line numbers in test methods
2. **Print Statements**: Use `print()` for debugging
3. **View Hierarchy**: Use Xcode's View Hierarchy Debugger during UI tests
4. **Slow Animations**: Enable slow animations in Simulator for UI tests

### Common Issues

**Issue**: Tests fail because backend is not running
- **Solution**: Start backend or use mock data

**Issue**: UI tests can't find elements
- **Solution**: Add accessibility identifiers to views

```swift
TextField("Email", text: $email)
    .accessibilityIdentifier("emailField")
```

**Issue**: Tests are flaky
- **Solution**: Add explicit waits for async operations

```swift
app.waitForElement(app.buttons["Continue"], timeout: 5)
```

---

## Test Reports

### Viewing Test Results

After running tests:
1. Open the **Report Navigator** (`Cmd + 9`)
2. Select the latest test run
3. View passed/failed tests
4. See code coverage (Enable in Scheme → Test → Options → Code Coverage)

### Code Coverage

Enable code coverage to track which code is tested:

1. Edit scheme (`Cmd + <`)
2. Select **Test** action
3. Check "Gather coverage for targets"
4. Run tests
5. View coverage in Report Navigator

---

## Best Practices

1. **Keep Tests Fast**: Unit tests should run in milliseconds
2. **Test Behavior, Not Implementation**: Focus on what, not how
3. **One Assertion Per Test**: Makes failures easier to diagnose
4. **Use Descriptive Names**: `testLoginSucceedsWithValidCredentials` not `testLogin`
5. **Clean Up After Tests**: Reset state in `tearDown`
6. **Don't Test Private Methods**: Only test public API
7. **Mock External Dependencies**: Network, location, etc.

---

## Running Tests from Command Line

### All Tests
```bash
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15 Pro'
```

### Only Unit Tests
```bash
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15 Pro' -only-testing:sautai_iosTests
```

### Specific Test
```bash
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15 Pro' -only-testing:sautai_iosTests/UserRoleTests
```

### Generate Coverage Report
```bash
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15 Pro' -enableCodeCoverage YES
```

---

## Additional Resources

- [Swift Testing Documentation](https://developer.apple.com/documentation/testing)
- [XCTest Documentation](https://developer.apple.com/documentation/xctest)
- [UI Testing in Xcode](https://developer.apple.com/library/archive/documentation/DeveloperTools/Conceptual/testing_with_xcode/chapters/09-ui_testing.html)
- [Test-Driven Development](https://developer.apple.com/videos/play/wwdc2019/413/)

---

## Questions or Issues?

If you encounter testing issues:
1. Check test logs in Report Navigator
2. Verify backend is running (for integration tests)
3. Clean build folder (`Cmd + Shift + K`)
4. Reset simulator (`Device → Erase All Content and Settings`)
5. Restart Xcode if tests behave unexpectedly

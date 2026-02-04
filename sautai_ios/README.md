# sautAI iOS

Chef-first iOS application for the sautAI platform.

## Requirements

- iOS 17.0+
- Xcode 15.0+
- Swift 5.9+

## Project Structure

```
sautai_ios/
├── SautaiApp.swift              # App entry point
├── Core/                        # Core infrastructure
│   ├── Network/                 # API client, streaming
│   ├── Auth/                    # Authentication, Keychain
│   ├── Models/                  # Data models
│   ├── Design/                  # Design system
│   └── Persistence/             # SwiftData
├── Features/                    # Feature modules
│   ├── Auth/                    # Login, Register
│   ├── Chef/                    # Chef-specific features
│   │   ├── Dashboard/
│   │   ├── Clients/
│   │   ├── SousChef/           # AI assistant
│   │   └── MealPlanning/
│   ├── Customer/               # Customer features (Phase 2)
│   └── Settings/
├── Components/                  # Reusable UI components
└── Resources/                   # Assets, fonts
```

## Design System

Based on the **sautAI Brand Guide 2025**:

### Colors

| Name | Hex | Usage |
|------|-----|-------|
| Earthen Clay | `#C96F45` | Primary |
| Herb Green | `#7B9E72` | Secondary |
| Soft Cream | `#F8F5EF` | Background |
| Slate Tile | `#5A5D61` | Text |
| Sunlit Apricot | `#E9B882` | Accent |
| Clay Pot Brown | `#8B5E3C` | Deep accent |

### Typography

- **Primary:** Poppins
- **Accent:** Kalam (handwritten)
- **Fallback:** System fonts with rounded design

### Design Tokens

- Corner radius: 16pt (default)
- Animation duration: 0.25s
- Spacing: 8pt base unit

## Features

### Phase 1 (Current)

- [x] Authentication (JWT)
- [x] Chef Dashboard
- [x] Client Management
- [x] Sous Chef AI (streaming)
- [x] Meal Plans
- [x] Settings

### Phase 2 (Planned)

- [ ] Customer role screens
- [ ] Push notifications
- [ ] Offline support
- [ ] Real-time messaging (WebSocket)

## API Integration

Connects to the Django backend at:
- **Development:** `http://localhost:8000`
- **Production:** `https://api.sautai.com`

### Key Endpoints

- `/auth/api/login/` - Authentication
- `/chefs/api/me/dashboard/` - Chef dashboard
- `/chefs/api/me/sous-chef/stream/` - AI streaming
- `/chefs/api/me/clients/` - Client management

## Development

### Setup

1. Open `sautai_ios` in Xcode
2. Add custom fonts to Resources/Fonts (Poppins, Kalam)
3. Update the API base URL in `APIClient.swift`
4. Build and run

### Testing

```bash
# Run tests
xcodebuild test -scheme sautai_ios -destination 'platform=iOS Simulator,name=iPhone 15'
```

## Brand

> *"Cook together. Eat together. Be together."*
>
> — sautAI Brand Essence

---

*Built with SwiftUI, SwiftData, and native iOS frameworks.*

//
//  Typography.swift
//  sautai_ios
//
//  sautai Typography System (2025 Brand Guide)
//  Primary: Poppins (modern rounded sans-serif)
//  Accent: Kalam (handwritten for quotes)
//

import SwiftUI

// MARK: - Sautai Font

enum SautaiFont {

    // MARK: - Poppins (Primary)

    /// Poppins font with specified size and weight
    static func poppins(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        let fontName: String
        switch weight {
        case .ultraLight, .thin, .light:
            fontName = "Poppins-Light"
        case .regular:
            fontName = "Poppins-Regular"
        case .medium:
            fontName = "Poppins-Medium"
        case .semibold:
            fontName = "Poppins-SemiBold"
        case .bold, .heavy, .black:
            fontName = "Poppins-Bold"
        default:
            fontName = "Poppins-Regular"
        }

        // Fallback to system font if custom font not loaded
        if UIFont(name: fontName, size: size) != nil {
            return .custom(fontName, size: size)
        } else {
            return .system(size: size, weight: weight, design: .rounded)
        }
    }

    // MARK: - Kalam (Handwritten Accent)

    /// Kalam handwritten font for quotes and personal touches
    static func kalam(_ size: CGFloat) -> Font {
        if UIFont(name: "Kalam-Regular", size: size) != nil {
            return .custom("Kalam-Regular", size: size)
        } else {
            // Fallback to system serif italic for handwritten feel
            return .system(size: size, design: .serif).italic()
        }
    }

    // MARK: - Semantic Text Styles

    /// Large title - 34pt bold
    static let largeTitle = poppins(34, weight: .bold)

    /// Title - 28pt semibold
    static let title = poppins(28, weight: .semibold)

    /// Title 2 - 22pt semibold
    static let title2 = poppins(22, weight: .semibold)

    /// Title 3 - 20pt semibold
    static let title3 = poppins(20, weight: .semibold)

    /// Headline - 17pt semibold
    static let headline = poppins(17, weight: .semibold)

    /// Body - 17pt regular
    static let body = poppins(17, weight: .regular)

    /// Callout - 16pt regular
    static let callout = poppins(16, weight: .regular)

    /// Subheadline - 15pt regular
    static let subheadline = poppins(15, weight: .regular)

    /// Footnote - 13pt regular
    static let footnote = poppins(13, weight: .regular)

    /// Caption - 12pt regular
    static let caption = poppins(12, weight: .regular)

    /// Caption 2 - 11pt regular
    static let caption2 = poppins(11, weight: .regular)

    // MARK: - Special Styles

    /// Handwritten style for quotes and personal touches
    static let handwritten = kalam(18)

    /// Handwritten large for featured quotes
    static let handwrittenLarge = kalam(24)

    /// Button text - 17pt semibold
    static let button = poppins(17, weight: .semibold)

    /// Small button text - 15pt medium
    static let buttonSmall = poppins(15, weight: .medium)

    /// Tab bar label - 10pt medium
    static let tabLabel = poppins(10, weight: .medium)

    /// Navigation title - 17pt semibold
    static let navTitle = poppins(17, weight: .semibold)

    /// Large navigation title - 34pt bold
    static let navTitleLarge = poppins(34, weight: .bold)

    /// Stats/numbers display - 32pt bold
    static let stats = poppins(32, weight: .bold)

    /// Money/currency display - 28pt semibold
    static let money = poppins(28, weight: .semibold)
}

// MARK: - UIFont Extension for Font Registration

extension UIFont {

    /// Register custom fonts from bundle
    static func registerCustomFonts() {
        let fontNames = [
            "Poppins-Light",
            "Poppins-Regular",
            "Poppins-Medium",
            "Poppins-SemiBold",
            "Poppins-Bold",
            "Kalam-Regular"
        ]

        for fontName in fontNames {
            registerFont(named: fontName)
        }
    }

    private static func registerFont(named fontName: String) {
        guard let fontURL = Bundle.main.url(forResource: fontName, withExtension: "ttf") else {
            print("Warning: Could not find font \(fontName)")
            return
        }

        var error: Unmanaged<CFError>?
        if !CTFontManagerRegisterFontsForURL(fontURL as CFURL, .process, &error) {
            print("Warning: Could not register font \(fontName): \(error.debugDescription)")
        }
    }
}

// MARK: - Text Style View Modifier

struct SautaiTextStyle: ViewModifier {
    let font: Font
    let color: Color

    func body(content: Content) -> some View {
        content
            .font(font)
            .foregroundColor(color)
    }
}

extension View {
    func sautaiStyle(_ font: Font, color: Color = .sautai.slateTile) -> some View {
        modifier(SautaiTextStyle(font: font, color: color))
    }
}

// MARK: - Preview

#Preview("Typography") {
    ScrollView {
        VStack(alignment: .leading, spacing: 16) {
            Text("Large Title")
                .font(SautaiFont.largeTitle)

            Text("Title")
                .font(SautaiFont.title)

            Text("Title 2")
                .font(SautaiFont.title2)

            Text("Headline")
                .font(SautaiFont.headline)

            Text("Body text for regular content")
                .font(SautaiFont.body)

            Text("Callout text")
                .font(SautaiFont.callout)

            Text("Caption text")
                .font(SautaiFont.caption)

            Divider()

            Text("\"Artful kitchens. Shared hearts.\"")
                .font(SautaiFont.handwritten)
                .foregroundColor(.sautai.earthenClay)

            Text("$1,234.56")
                .font(SautaiFont.money)
                .foregroundColor(.sautai.herbGreen)
        }
        .padding()
    }
}

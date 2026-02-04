//
//  Colors.swift
//  sautai_ios
//
//  sautAI Brand Colors (2025 Brand Guide)
//  "Cook together. Eat together. Be together."
//

import SwiftUI

// MARK: - Color Extension

extension Color {
    static let sautai = SautaiColors()

    /// Initialize Color from hex string
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3: // RGB (12-bit)
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6: // RGB (24-bit)
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8: // ARGB (32-bit)
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Sautai Color Palette

struct SautaiColors {

    // MARK: Primary Palette (2025 Brand Guide)

    /// Primary color - Warmth and handcrafted care
    let earthenClay = Color(hex: "C96F45")

    /// Secondary color - Fresh herbs, renewal, health
    let herbGreen = Color(hex: "7B9E72")

    /// Background - Airy and comforting
    let softCream = Color(hex: "F8F5EF")

    /// Neutral - Grounded and stable (text, icons)
    let slateTile = Color(hex: "5A5D61")

    /// Accent - Glow and positivity
    let sunlitApricot = Color(hex: "E9B882")

    /// Deep Accent - Grounded richness
    let clayPotBrown = Color(hex: "8B5E3C")

    // MARK: Logo Colors

    /// Logo flames - Always this warm red-orange
    let logoFlames = Color(hex: "D54930")

    /// Logo pan (light mode)
    let logoPanLight = Color(hex: "131D1F")

    /// Logo pan (dark mode)
    let logoPanDark = Color.white

    // MARK: Semantic Colors

    let success = Color(hex: "168516")
    let successBackground = Color(hex: "168516").opacity(0.12)

    let warning = Color(hex: "B45309")
    let warningBackground = Color(hex: "F59E0B").opacity(0.12)

    let danger = Color(hex: "DC2626")
    let dangerBackground = Color(hex: "DC2626").opacity(0.12)

    let info = Color(hex: "1D4ED8")
    let infoBackground = Color(hex: "3B82F6").opacity(0.12)

    let pending = Color(hex: "7C3AED")
    let pendingBackground = Color(hex: "7C3AED").opacity(0.12)

    // MARK: Dark Mode Surfaces

    let darkBackground = Color(hex: "1A1410")
    let darkSurface = Color(hex: "2D2520")
    let darkSurface2 = Color(hex: "3D3530")
    let darkBorder = Color(hex: "4D4540")

    // MARK: Light Mode Surfaces

    let lightBackground = Color(hex: "F8F5EF")  // Same as softCream
    let lightSurface = Color.white
    let lightSurface2 = Color(hex: "FAF8F5")
    let lightBorder = Color(hex: "E8E4DD")
}

// MARK: - Adaptive Colors

extension SautaiColors {

    /// Adaptive background that responds to color scheme
    func background(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? darkBackground : lightBackground
    }

    /// Adaptive surface that responds to color scheme
    func surface(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? darkSurface : lightSurface
    }

    /// Adaptive text color
    func text(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Color(hex: "F5F0E8") : slateTile
    }

    /// Adaptive muted text color
    func mutedText(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Color(hex: "A09890") : Color(hex: "7A7570")
    }

    /// Adaptive border color
    func border(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? darkBorder : lightBorder
    }
}

// MARK: - Preview

#Preview("Color Palette") {
    ScrollView {
        VStack(spacing: 16) {
            Group {
                ColorSwatch(name: "Earthen Clay", color: .sautai.earthenClay)
                ColorSwatch(name: "Herb Green", color: .sautai.herbGreen)
                ColorSwatch(name: "Soft Cream", color: .sautai.softCream)
                ColorSwatch(name: "Slate Tile", color: .sautai.slateTile)
                ColorSwatch(name: "Sunlit Apricot", color: .sautai.sunlitApricot)
                ColorSwatch(name: "Clay Pot Brown", color: .sautai.clayPotBrown)
            }

            Divider()

            Group {
                ColorSwatch(name: "Logo Flames", color: .sautai.logoFlames)
                ColorSwatch(name: "Success", color: .sautai.success)
                ColorSwatch(name: "Warning", color: .sautai.warning)
                ColorSwatch(name: "Danger", color: .sautai.danger)
            }
        }
        .padding()
    }
}

private struct ColorSwatch: View {
    let name: String
    let color: Color

    var body: some View {
        HStack {
            RoundedRectangle(cornerRadius: 8)
                .fill(color)
                .frame(width: 60, height: 40)

            Text(name)
                .font(.body)

            Spacer()
        }
    }
}

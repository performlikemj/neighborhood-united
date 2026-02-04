//
//  DesignTokens.swift
//  sautai_ios
//
//  sautAI Design Tokens (2025 Brand Guide)
//  Spacing, corners, shadows, and animations
//

import SwiftUI

// MARK: - Design Tokens

enum SautaiDesign {

    // MARK: - Corner Radius

    /// Extra small corners - 4pt
    static let cornerRadiusXS: CGFloat = 4

    /// Small corners - 8pt
    static let cornerRadiusS: CGFloat = 8

    /// Medium corners - 12pt
    static let cornerRadiusM: CGFloat = 12

    /// Standard corners - 16pt (Brand Guide default)
    static let cornerRadius: CGFloat = 16

    /// Large corners - 20pt
    static let cornerRadiusL: CGFloat = 20

    /// Extra large corners - 24pt
    static let cornerRadiusXL: CGFloat = 24

    /// Full/pill corners - 9999pt
    static let cornerRadiusFull: CGFloat = 9999

    // MARK: - Spacing (Padding/Margins)

    /// Extra extra small - 2pt
    static let spacingXXS: CGFloat = 2

    /// Extra small - 4pt
    static let spacingXS: CGFloat = 4

    /// Small - 8pt
    static let spacingS: CGFloat = 8

    /// Medium - 12pt
    static let spacingM: CGFloat = 12

    /// Standard - 16pt
    static let spacing: CGFloat = 16

    /// Large - 24pt
    static let spacingL: CGFloat = 24

    /// Extra large - 32pt
    static let spacingXL: CGFloat = 32

    /// Section spacing - 48pt (Brand Guide minimum)
    static let spacingSection: CGFloat = 48

    // MARK: - Icon Sizes

    /// Small icon - 16pt
    static let iconSizeS: CGFloat = 16

    /// Medium icon - 20pt
    static let iconSizeM: CGFloat = 20

    /// Standard icon - 24pt
    static let iconSize: CGFloat = 24

    /// Large icon - 32pt
    static let iconSizeL: CGFloat = 32

    /// Extra large icon - 48pt
    static let iconSizeXL: CGFloat = 48

    // MARK: - Button Heights

    /// Small button - 36pt
    static let buttonHeightS: CGFloat = 36

    /// Standard button - 48pt
    static let buttonHeight: CGFloat = 48

    /// Large button - 56pt
    static let buttonHeightL: CGFloat = 56

    // MARK: - Animation

    /// Quick animation - 0.15s
    static let animationQuick: Double = 0.15

    /// Standard animation - 0.25s (Brand Guide: 0.2-0.3s)
    static let animationDuration: Double = 0.25

    /// Slow animation - 0.4s
    static let animationSlow: Double = 0.4

    /// Spring animation response
    static let springResponse: Double = 0.5

    /// Spring animation damping
    static let springDamping: Double = 0.7

    // MARK: - Shadows

    /// Subtle shadow
    static let shadowSubtle = SautaiShadow(
        color: .black.opacity(0.05),
        radius: 4,
        x: 0,
        y: 2
    )

    /// Standard shadow
    static let shadow = SautaiShadow(
        color: .black.opacity(0.1),
        radius: 8,
        x: 0,
        y: 4
    )

    /// Elevated shadow
    static let shadowElevated = SautaiShadow(
        color: .black.opacity(0.15),
        radius: 16,
        x: 0,
        y: 8
    )

    // MARK: - Layout

    /// Maximum content width - 1200pt (Brand Guide)
    static let maxContentWidth: CGFloat = 600  // Mobile-adjusted

    /// Card minimum height
    static let cardMinHeight: CGFloat = 80

    /// List row height
    static let listRowHeight: CGFloat = 56

    /// Avatar sizes
    static let avatarSizeS: CGFloat = 32
    static let avatarSize: CGFloat = 40
    static let avatarSizeL: CGFloat = 56
    static let avatarSizeXL: CGFloat = 80
}

// MARK: - Shadow Model

struct SautaiShadow {
    let color: Color
    let radius: CGFloat
    let x: CGFloat
    let y: CGFloat
}

// MARK: - Shadow View Modifier

extension View {
    func sautaiShadow(_ shadow: SautaiShadow = SautaiDesign.shadow) -> some View {
        self.shadow(
            color: shadow.color,
            radius: shadow.radius,
            x: shadow.x,
            y: shadow.y
        )
    }
}

// MARK: - Animation Extensions

extension Animation {
    /// Standard sautAI ease animation
    static var sautaiEase: Animation {
        .easeInOut(duration: SautaiDesign.animationDuration)
    }

    /// Quick sautAI animation
    static var sautaiQuick: Animation {
        .easeInOut(duration: SautaiDesign.animationQuick)
    }

    /// sautAI spring animation
    static var sautaiSpring: Animation {
        .spring(
            response: SautaiDesign.springResponse,
            dampingFraction: SautaiDesign.springDamping
        )
    }
}

// MARK: - Preview

#Preview("Design Tokens") {
    ScrollView {
        VStack(spacing: SautaiDesign.spacingL) {
            // Corner radius examples
            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Corner Radius")
                    .font(SautaiFont.headline)

                HStack(spacing: SautaiDesign.spacingM) {
                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadiusS)
                        .fill(Color.sautai.earthenClay)
                        .frame(width: 50, height: 50)

                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                        .fill(Color.sautai.herbGreen)
                        .frame(width: 50, height: 50)

                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadiusXL)
                        .fill(Color.sautai.sunlitApricot)
                        .frame(width: 50, height: 50)
                }
            }

            // Shadow examples
            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Shadows")
                    .font(SautaiFont.headline)

                HStack(spacing: SautaiDesign.spacingL) {
                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                        .fill(Color.white)
                        .frame(width: 80, height: 60)
                        .sautaiShadow(SautaiDesign.shadowSubtle)

                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                        .fill(Color.white)
                        .frame(width: 80, height: 60)
                        .sautaiShadow(SautaiDesign.shadow)

                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                        .fill(Color.white)
                        .frame(width: 80, height: 60)
                        .sautaiShadow(SautaiDesign.shadowElevated)
                }
            }

            // Button heights
            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Button Heights")
                    .font(SautaiFont.headline)

                VStack(spacing: SautaiDesign.spacingS) {
                    buttonExample(height: SautaiDesign.buttonHeightS, label: "Small")
                    buttonExample(height: SautaiDesign.buttonHeight, label: "Standard")
                    buttonExample(height: SautaiDesign.buttonHeightL, label: "Large")
                }
            }
        }
        .padding(SautaiDesign.spacingL)
    }
    .background(Color.sautai.softCream)
}

private func buttonExample(height: CGFloat, label: String) -> some View {
    Text(label)
        .font(SautaiFont.button)
        .foregroundColor(.white)
        .frame(maxWidth: .infinity)
        .frame(height: height)
        .background(Color.sautai.earthenClay)
        .cornerRadius(SautaiDesign.cornerRadius)
}

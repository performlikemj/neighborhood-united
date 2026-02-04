//
//  SautaiButton.swift
//  sautai_ios
//
//  Reusable button component following sautAI brand guidelines.
//

import SwiftUI

// MARK: - Button Style

enum SautaiButtonStyle {
    case primary
    case secondary
    case outline
    case ghost
    case destructive
}

// MARK: - Button Size

enum SautaiButtonSize {
    case small
    case medium
    case large

    var height: CGFloat {
        switch self {
        case .small: return SautaiDesign.buttonHeightS
        case .medium: return SautaiDesign.buttonHeight
        case .large: return SautaiDesign.buttonHeightL
        }
    }

    var font: Font {
        switch self {
        case .small: return SautaiFont.buttonSmall
        case .medium, .large: return SautaiFont.button
        }
    }

    var padding: CGFloat {
        switch self {
        case .small: return SautaiDesign.spacingM
        case .medium: return SautaiDesign.spacingL
        case .large: return SautaiDesign.spacingXL
        }
    }
}

// MARK: - Sautai Button

struct SautaiButton: View {
    let title: String
    let style: SautaiButtonStyle
    let size: SautaiButtonSize
    let icon: String?
    let isLoading: Bool
    let isDisabled: Bool
    let action: () -> Void

    init(
        _ title: String,
        style: SautaiButtonStyle = .primary,
        size: SautaiButtonSize = .medium,
        icon: String? = nil,
        isLoading: Bool = false,
        isDisabled: Bool = false,
        action: @escaping () -> Void
    ) {
        self.title = title
        self.style = style
        self.size = size
        self.icon = icon
        self.isLoading = isLoading
        self.isDisabled = isDisabled
        self.action = action
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: SautaiDesign.spacingS) {
                if isLoading {
                    ProgressView()
                        .tint(foregroundColor)
                } else {
                    if let icon = icon {
                        Image(systemName: icon)
                    }
                    Text(title)
                }
            }
            .font(size.font)
            .foregroundColor(foregroundColor)
            .frame(maxWidth: .infinity)
            .frame(height: size.height)
            .background(backgroundColor)
            .cornerRadius(SautaiDesign.cornerRadius)
            .overlay(
                RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                    .stroke(borderColor, lineWidth: style == .outline ? 2 : 0)
            )
        }
        .disabled(isDisabled || isLoading)
        .opacity(isDisabled ? 0.6 : 1)
    }

    // MARK: - Computed Colors

    private var foregroundColor: Color {
        switch style {
        case .primary:
            return .white
        case .secondary:
            return .white
        case .outline:
            return .sautai.earthenClay
        case .ghost:
            return .sautai.earthenClay
        case .destructive:
            return .white
        }
    }

    private var backgroundColor: Color {
        switch style {
        case .primary:
            return .sautai.earthenClay
        case .secondary:
            return .sautai.herbGreen
        case .outline:
            return .clear
        case .ghost:
            return .sautai.earthenClay.opacity(0.1)
        case .destructive:
            return .sautai.danger
        }
    }

    private var borderColor: Color {
        switch style {
        case .outline:
            return .sautai.earthenClay
        default:
            return .clear
        }
    }
}

// MARK: - Preview

#Preview("Button Styles") {
    VStack(spacing: SautaiDesign.spacingM) {
        SautaiButton("Primary Button", style: .primary) {}
        SautaiButton("Secondary Button", style: .secondary) {}
        SautaiButton("Outline Button", style: .outline) {}
        SautaiButton("Ghost Button", style: .ghost) {}
        SautaiButton("Destructive", style: .destructive) {}
        SautaiButton("With Icon", icon: "plus") {}
        SautaiButton("Loading", isLoading: true) {}
        SautaiButton("Disabled", isDisabled: true) {}
    }
    .padding()
    .background(Color.sautai.softCream)
}

#Preview("Button Sizes") {
    VStack(spacing: SautaiDesign.spacingM) {
        SautaiButton("Small", size: .small) {}
        SautaiButton("Medium", size: .medium) {}
        SautaiButton("Large", size: .large) {}
    }
    .padding()
    .background(Color.sautai.softCream)
}

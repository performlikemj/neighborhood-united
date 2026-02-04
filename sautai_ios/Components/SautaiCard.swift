//
//  SautaiCard.swift
//  sautai_ios
//
//  Reusable card component with sautAI styling.
//

import SwiftUI

// MARK: - Sautai Card

struct SautaiCard<Content: View>: View {
    let content: Content
    let padding: CGFloat
    let showShadow: Bool

    init(
        padding: CGFloat = SautaiDesign.spacing,
        showShadow: Bool = true,
        @ViewBuilder content: () -> Content
    ) {
        self.padding = padding
        self.showShadow = showShadow
        self.content = content()
    }

    var body: some View {
        content
            .padding(padding)
            .background(Color.white)
            .cornerRadius(SautaiDesign.cornerRadius)
            .if(showShadow) { view in
                view.sautaiShadow(SautaiDesign.shadowSubtle)
            }
    }
}

// MARK: - Conditional Modifier

extension View {
    @ViewBuilder
    func `if`<Transform: View>(_ condition: Bool, transform: (Self) -> Transform) -> some View {
        if condition {
            transform(self)
        } else {
            self
        }
    }
}

// MARK: - Stat Card

struct StatCard: View {
    let title: String
    let value: String
    let icon: String?
    let color: Color
    let trend: Double?

    init(
        title: String,
        value: String,
        icon: String? = nil,
        color: Color = .sautai.earthenClay,
        trend: Double? = nil
    ) {
        self.title = title
        self.value = value
        self.icon = icon
        self.color = color
        self.trend = trend
    }

    var body: some View {
        SautaiCard {
            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                HStack {
                    if let icon = icon {
                        Image(systemName: icon)
                            .foregroundColor(color)
                    }
                    Text(title)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))

                    Spacer()

                    if let trend = trend {
                        trendIndicator(trend)
                    }
                }

                Text(value)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)
            }
        }
    }

    @ViewBuilder
    private func trendIndicator(_ trend: Double) -> some View {
        let isPositive = trend >= 0
        HStack(spacing: 2) {
            Image(systemName: isPositive ? "arrow.up.right" : "arrow.down.right")
                .font(.system(size: 10, weight: .bold))
            Text(String(format: "%.1f%%", abs(trend)))
                .font(SautaiFont.caption2)
        }
        .foregroundColor(isPositive ? .sautai.success : .sautai.danger)
    }
}

// MARK: - Info Card

struct InfoCard: View {
    let title: String
    let message: String
    let icon: String
    let color: Color

    init(
        title: String,
        message: String,
        icon: String = "info.circle.fill",
        color: Color = .sautai.info
    ) {
        self.title = title
        self.message = message
        self.icon = icon
        self.color = color
    }

    var body: some View {
        HStack(alignment: .top, spacing: SautaiDesign.spacingM) {
            Image(systemName: icon)
                .font(.system(size: 24))
                .foregroundColor(color)

            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                Text(title)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Text(message)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
            }
        }
        .padding(SautaiDesign.spacing)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(color.opacity(0.1))
        .cornerRadius(SautaiDesign.cornerRadius)
    }
}

// MARK: - Preview

#Preview("Cards") {
    ScrollView {
        VStack(spacing: SautaiDesign.spacingM) {
            SautaiCard {
                Text("Basic Card Content")
                    .font(SautaiFont.body)
            }

            StatCard(
                title: "Revenue",
                value: "$1,234",
                icon: "dollarsign.circle.fill",
                color: .sautai.herbGreen,
                trend: 12.5
            )

            StatCard(
                title: "Orders",
                value: "47",
                icon: "bag.fill",
                color: .sautai.sunlitApricot,
                trend: -3.2
            )

            InfoCard(
                title: "Tip",
                message: "Complete your profile to attract more clients."
            )

            InfoCard(
                title: "Warning",
                message: "Your subscription expires in 3 days.",
                icon: "exclamationmark.triangle.fill",
                color: .sautai.warning
            )
        }
        .padding()
    }
    .background(Color.sautai.softCream)
}

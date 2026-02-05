//
//  OrderRowView.swift
//  sautai_ios
//
//  Reusable row component for displaying order summary.
//

import SwiftUI

struct OrderRowView: View {
    let order: Order

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Status icon
            Circle()
                .fill(statusColor.opacity(0.15))
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: order.status.icon)
                        .font(.system(size: 18))
                        .foregroundColor(statusColor)
                )

            // Order info
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                HStack {
                    Text(order.customerName ?? "Customer")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    Spacer()

                    Text(order.displayTotal)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.earthenClay)
                }

                HStack {
                    Text(order.status.displayName)
                        .font(SautaiFont.caption)
                        .foregroundColor(statusColor)

                    if let date = order.deliveryDate {
                        Text("•")
                            .foregroundColor(.sautai.slateTile.opacity(0.3))
                        Text(formatDeliveryDate(date))
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }

                    if let time = order.deliveryTime {
                        Text("at \(time)")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let itemCount = order.items?.count, itemCount > 0 {
                    Text("\(itemCount) item\(itemCount == 1 ? "" : "s")")
                        .font(SautaiFont.caption2)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var statusColor: Color {
        switch order.status.colorName {
        case "warning": return .sautai.warning
        case "info": return .sautai.info
        case "primary": return .sautai.earthenClay
        case "success": return .sautai.success
        case "danger": return .sautai.danger
        default: return .sautai.slateTile
        }
    }

    private func formatDeliveryDate(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return "Today"
        } else if calendar.isDateInTomorrow(date) {
            return "Tomorrow"
        } else {
            return date.formatted(date: .abbreviated, time: .omitted)
        }
    }
}

#Preview {
    VStack(spacing: 16) {
        OrderRowView(order: Order(
            id: 1,
            customerId: 1,
            customerName: "John Doe",
            chefId: 1,
            chefName: nil,
            status: .pending,
            totalAmount: "125.00",
            currency: "USD",
            items: nil,
            specialRequests: nil,
            deliveryDate: Date(),
            deliveryTime: "6:00 PM",
            deliveryAddress: nil,
            createdAt: nil,
            updatedAt: nil,
            paidAt: nil
        ))

        OrderRowView(order: Order(
            id: 2,
            customerId: 2,
            customerName: "Jane Smith",
            chefId: 1,
            chefName: nil,
            status: .confirmed,
            totalAmount: "85.50",
            currency: "USD",
            items: nil,
            specialRequests: nil,
            deliveryDate: Date().addingTimeInterval(86400),
            deliveryTime: "12:00 PM",
            deliveryAddress: nil,
            createdAt: nil,
            updatedAt: nil,
            paidAt: nil
        ))
    }
    .padding()
    .background(Color.sautai.softCream)
}

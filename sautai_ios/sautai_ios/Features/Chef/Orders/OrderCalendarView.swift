//
//  OrderCalendarView.swift
//  sautai_ios
//
//  Calendar view showing orders and meal events by date.
//

import SwiftUI

struct OrderCalendarView: View {
    @Environment(\.dismiss) var dismiss
    @State private var selectedDate = Date()
    @State private var calendarItems: [OrderCalendarItem] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var displayedMonth = Date()

    private var itemsForSelectedDate: [OrderCalendarItem] {
        let calendar = Calendar.current
        return calendarItems.filter { item in
            calendar.isDate(item.date, inSameDayAs: selectedDate)
        }
    }

    private var datesWithItems: Set<DateComponents> {
        let calendar = Calendar.current
        return Set(calendarItems.map { item in
            calendar.dateComponents([.year, .month, .day], from: item.date)
        })
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Calendar
                calendarSection

                Divider()

                // Items for selected date
                selectedDateItems
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Calendar")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        withAnimation(.sautaiSpring) {
                            selectedDate = Date()
                            displayedMonth = Date()
                        }
                    } label: {
                        Text("Today")
                            .font(SautaiFont.buttonSmall)
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }
        }
        .task {
            await loadCalendarItems()
        }
        .onChange(of: displayedMonth) { _, newMonth in
            Task { await loadCalendarItems(for: newMonth) }
        }
    }

    // MARK: - Calendar Section

    private var calendarSection: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Month navigation
            HStack {
                Button {
                    withAnimation(.sautaiSpring) {
                        displayedMonth = Calendar.current.date(byAdding: .month, value: -1, to: displayedMonth) ?? displayedMonth
                    }
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.sautai.earthenClay)
                }

                Spacer()

                Text(displayedMonth.formatted(.dateTime.month(.wide).year()))
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                Button {
                    withAnimation(.sautaiSpring) {
                        displayedMonth = Calendar.current.date(byAdding: .month, value: 1, to: displayedMonth) ?? displayedMonth
                    }
                } label: {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.sautai.earthenClay)
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)

            // Day headers
            HStack(spacing: 0) {
                ForEach(["S", "M", "T", "W", "T", "F", "S"], id: \.self) { day in
                    Text(day)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                        .frame(maxWidth: .infinity)
                }
            }
            .padding(.horizontal, SautaiDesign.spacingS)

            // Calendar grid
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 0), count: 7), spacing: SautaiDesign.spacingXS) {
                ForEach(daysInMonth(), id: \.self) { date in
                    if let date = date {
                        dayCell(date)
                    } else {
                        Color.clear
                            .frame(height: 44)
                    }
                }
            }
            .padding(.horizontal, SautaiDesign.spacingS)
        }
        .padding(.vertical, SautaiDesign.spacing)
        .background(Color.white)
    }

    private func dayCell(_ date: Date) -> some View {
        let calendar = Calendar.current
        let isSelected = calendar.isDate(date, inSameDayAs: selectedDate)
        let isToday = calendar.isDateInToday(date)
        let hasItems = datesWithItems.contains(calendar.dateComponents([.year, .month, .day], from: date))
        let isCurrentMonth = calendar.isDate(date, equalTo: displayedMonth, toGranularity: .month)

        return Button {
            withAnimation(.sautaiQuick) {
                selectedDate = date
            }
        } label: {
            VStack(spacing: 2) {
                Text("\(calendar.component(.day, from: date))")
                    .font(SautaiFont.body)
                    .foregroundColor(
                        isSelected ? .white :
                        isToday ? .sautai.earthenClay :
                        isCurrentMonth ? .sautai.slateTile : .sautai.slateTile.opacity(0.3)
                    )

                // Indicator dot for items
                if hasItems {
                    Circle()
                        .fill(isSelected ? Color.white : Color.sautai.earthenClay)
                        .frame(width: 6, height: 6)
                } else {
                    Circle()
                        .fill(Color.clear)
                        .frame(width: 6, height: 6)
                }
            }
            .frame(width: 44, height: 44)
            .background(
                Circle()
                    .fill(isSelected ? Color.sautai.earthenClay : isToday ? Color.sautai.earthenClay.opacity(0.1) : Color.clear)
            )
        }
    }

    // MARK: - Selected Date Items

    private var selectedDateItems: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text(selectedDate.formatted(date: .complete, time: .omitted))
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)
                .padding(.horizontal, SautaiDesign.spacing)
                .padding(.top, SautaiDesign.spacing)

            if isLoading {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if itemsForSelectedDate.isEmpty {
                VStack(spacing: SautaiDesign.spacingM) {
                    Image(systemName: "calendar.badge.clock")
                        .font(.system(size: 32))
                        .foregroundColor(.sautai.slateTile.opacity(0.4))

                    Text("No items scheduled")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    VStack(spacing: SautaiDesign.spacingS) {
                        ForEach(itemsForSelectedDate) { item in
                            calendarItemRow(item)
                        }
                    }
                    .padding(.horizontal, SautaiDesign.spacing)
                }
            }
        }
        .frame(maxHeight: .infinity)
    }

    private func calendarItemRow(_ item: OrderCalendarItem) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Type icon
            Image(systemName: item.type.icon)
                .font(.system(size: 18))
                .foregroundColor(itemColor(item))
                .frame(width: 36, height: 36)
                .background(itemColor(item).opacity(0.15))
                .cornerRadius(SautaiDesign.cornerRadiusS)

            // Info
            VStack(alignment: .leading, spacing: 2) {
                Text(item.title)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                HStack(spacing: SautaiDesign.spacingS) {
                    Text(item.displayTime)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))

                    if let customer = item.customerName {
                        Text("•")
                            .foregroundColor(.sautai.slateTile.opacity(0.3))
                        Text(customer)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }
            }

            Spacer()

            // Status badge
            Text(item.status.capitalized)
                .font(SautaiFont.caption2)
                .foregroundColor(itemColor(item))
                .padding(.horizontal, SautaiDesign.spacingS)
                .padding(.vertical, 4)
                .background(itemColor(item).opacity(0.1))
                .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func itemColor(_ item: OrderCalendarItem) -> Color {
        switch item.statusColor {
        case "warning": return .sautai.warning
        case "info": return .sautai.info
        case "primary": return .sautai.earthenClay
        case "success": return .sautai.herbGreen
        case "danger": return .sautai.danger
        default: return .sautai.slateTile
        }
    }

    // MARK: - Helpers

    private func daysInMonth() -> [Date?] {
        let calendar = Calendar.current

        // Get first day of month
        let components = calendar.dateComponents([.year, .month], from: displayedMonth)
        guard let firstOfMonth = calendar.date(from: components) else { return [] }

        // Get range of days
        guard let range = calendar.range(of: .day, in: .month, for: firstOfMonth) else { return [] }

        // Get weekday of first day (0 = Sunday)
        let firstWeekday = calendar.component(.weekday, from: firstOfMonth) - 1

        // Build array with leading nils for offset
        var days: [Date?] = Array(repeating: nil, count: firstWeekday)

        // Add all days
        for day in range {
            if let date = calendar.date(byAdding: .day, value: day - 1, to: firstOfMonth) {
                days.append(date)
            }
        }

        // Pad to complete final week
        while days.count % 7 != 0 {
            days.append(nil)
        }

        return days
    }

    // MARK: - Data Loading

    private func loadCalendarItems(for month: Date? = nil) async {
        isLoading = true
        error = nil

        let calendar = Calendar.current
        let targetMonth = month ?? displayedMonth

        // Get start and end of month (with some buffer)
        guard let startOfMonth = calendar.date(from: calendar.dateComponents([.year, .month], from: targetMonth)),
              let endOfMonth = calendar.date(byAdding: .month, value: 1, to: startOfMonth) else {
            isLoading = false
            return
        }

        do {
            calendarItems = try await APIClient.shared.getChefCalendar(startDate: startOfMonth, endDate: endOfMonth)
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

#Preview {
    OrderCalendarView()
}

//
//  KitchenView.swift
//  sautai_ios
//
//  Hub view for kitchen management: meals, dishes, ingredients, events, services.
//

import SwiftUI

struct KitchenView: View {
    @State private var selectedSection: KitchenSection = .dishes

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Section picker
                sectionPicker

                // Content
                TabView(selection: $selectedSection) {
                    DishesListView()
                        .tag(KitchenSection.dishes)

                    MealsListView()
                        .tag(KitchenSection.meals)

                    MealEventsListView()
                        .tag(KitchenSection.events)

                    IngredientsListView()
                        .tag(KitchenSection.ingredients)

                    ServicesListView()
                        .tag(KitchenSection.services)
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Kitchen")
        }
    }

    // MARK: - Section Picker

    private var sectionPicker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                ForEach(KitchenSection.allCases, id: \.self) { section in
                    sectionTab(section)
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.vertical, SautaiDesign.spacingM)
        }
        .background(Color.white)
    }

    private func sectionTab(_ section: KitchenSection) -> some View {
        let isSelected = selectedSection == section

        return Button {
            withAnimation(.sautaiQuick) {
                selectedSection = section
            }
        } label: {
            HStack(spacing: SautaiDesign.spacingXS) {
                Image(systemName: section.icon)
                    .font(.system(size: 14))
                Text(section.displayName)
                    .font(SautaiFont.buttonSmall)
            }
            .foregroundColor(isSelected ? .white : .sautai.slateTile)
            .padding(.horizontal, SautaiDesign.spacingM)
            .padding(.vertical, SautaiDesign.spacingS)
            .background(isSelected ? Color.sautai.earthenClay : Color.sautai.softCream)
            .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }
}

// MARK: - Kitchen Section

enum KitchenSection: String, CaseIterable {
    case dishes
    case meals
    case events
    case ingredients
    case services

    var displayName: String {
        switch self {
        case .dishes: return "Dishes"
        case .meals: return "Meals"
        case .events: return "Events"
        case .ingredients: return "Ingredients"
        case .services: return "Services"
        }
    }

    var icon: String {
        switch self {
        case .dishes: return "fork.knife"
        case .meals: return "takeoutbag.and.cup.and.straw"
        case .events: return "calendar.badge.clock"
        case .ingredients: return "carrot"
        case .services: return "briefcase"
        }
    }
}

#Preview {
    KitchenView()
}

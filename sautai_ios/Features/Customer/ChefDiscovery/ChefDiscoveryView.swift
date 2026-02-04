//
//  ChefDiscoveryView.swift
//  sautai_ios
//
//  Browse and search for chefs in the customer's area.
//

import SwiftUI

struct ChefDiscoveryView: View {
    @State private var chefs: [PublicChef] = []
    @State private var searchText = ""
    @State private var selectedCuisine: String?
    @State private var isLoading = true
    @State private var error: Error?

    private let cuisineFilters = ["All", "Italian", "Mexican", "Asian", "American", "Mediterranean", "Indian", "French"]

    var filteredChefs: [PublicChef] {
        var result = chefs

        if !searchText.isEmpty {
            result = result.filter { chef in
                chef.displayName.localizedCaseInsensitiveContains(searchText) ||
                (chef.bio?.localizedCaseInsensitiveContains(searchText) ?? false) ||
                (chef.cuisines?.contains { $0.localizedCaseInsensitiveContains(searchText) } ?? false)
            }
        }

        if let cuisine = selectedCuisine, cuisine != "All" {
            result = result.filter { chef in
                chef.cuisines?.contains { $0.localizedCaseInsensitiveContains(cuisine) } ?? false
            }
        }

        return result
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Cuisine filter
                cuisineFilterBar

                // Content
                if isLoading {
                    loadingView
                } else if chefs.isEmpty {
                    emptyView
                } else if filteredChefs.isEmpty {
                    noResultsView
                } else {
                    chefGrid
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Find a Chef")
            .searchable(text: $searchText, prompt: "Search chefs, cuisines...")
            .refreshable {
                await loadChefs()
            }
        }
        .task {
            await loadChefs()
        }
    }

    // MARK: - Cuisine Filter Bar

    private var cuisineFilterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: SautaiDesign.spacingS) {
                ForEach(cuisineFilters, id: \.self) { cuisine in
                    cuisineChip(cuisine)
                }
            }
            .padding(.horizontal, SautaiDesign.spacing)
            .padding(.vertical, SautaiDesign.spacingS)
        }
        .background(Color.white)
    }

    private func cuisineChip(_ cuisine: String) -> some View {
        let isSelected = (selectedCuisine == cuisine) || (cuisine == "All" && selectedCuisine == nil)

        return Button {
            withAnimation(.sautaiQuick) {
                selectedCuisine = cuisine == "All" ? nil : cuisine
            }
        } label: {
            Text(cuisine)
                .font(SautaiFont.buttonSmall)
                .foregroundColor(isSelected ? .white : .sautai.slateTile)
                .padding(.horizontal, SautaiDesign.spacingM)
                .padding(.vertical, SautaiDesign.spacingS)
                .background(isSelected ? Color.sautai.earthenClay : Color.sautai.softCream)
                .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }

    // MARK: - Chef Grid

    private var chefGrid: some View {
        ScrollView {
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: SautaiDesign.spacing),
                GridItem(.flexible(), spacing: SautaiDesign.spacing)
            ], spacing: SautaiDesign.spacing) {
                ForEach(filteredChefs) { chef in
                    NavigationLink {
                        ChefProfileView(chefId: chef.id)
                    } label: {
                        ChefCardView(chef: chef)
                    }
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Finding chefs near you...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "fork.knife.circle")
                .font(.system(size: 60))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No chefs in your area yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("We're expanding! Join the waitlist to be notified when chefs are available near you.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)
                .padding(.horizontal, SautaiDesign.spacingXL)

            Button {
                // TODO: Join waitlist
            } label: {
                Text("Join Waitlist")
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingXL)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
            }
        }
        .frame(maxHeight: .infinity)
        .padding()
    }

    // MARK: - No Results View

    private var noResultsView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No chefs found")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Try adjusting your search or filters")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Data Loading

    private func loadChefs() async {
        isLoading = true
        do {
            chefs = try await APIClient.shared.getPublicChefs()
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

// MARK: - Chef Card View

struct ChefCardView: View {
    let chef: PublicChef

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            // Photo
            ZStack {
                Rectangle()
                    .fill(Color.sautai.herbGreen.opacity(0.2))
                    .aspectRatio(1, contentMode: .fit)

                if let imageUrl = chef.profileImageUrl {
                    AsyncImage(url: URL(string: imageUrl)) { image in
                        image
                            .resizable()
                            .scaledToFill()
                    } placeholder: {
                        chefPlaceholder
                    }
                } else {
                    chefPlaceholder
                }
            }
            .cornerRadius(SautaiDesign.cornerRadius)
            .clipped()

            // Info
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                Text(chef.displayName)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)
                    .lineLimit(1)

                if let cuisines = chef.cuisines, !cuisines.isEmpty {
                    Text(cuisines.prefix(2).joined(separator: " • "))
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                        .lineLimit(1)
                }

                // Rating
                if let rating = chef.rating {
                    HStack(spacing: 4) {
                        Image(systemName: "star.fill")
                            .font(.system(size: 12))
                            .foregroundColor(.sautai.sunlitApricot)

                        Text(String(format: "%.1f", rating))
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile)

                        if let count = chef.reviewCount, count > 0 {
                            Text("(\(count))")
                                .font(SautaiFont.caption2)
                                .foregroundColor(.sautai.slateTile.opacity(0.5))
                        }
                    }
                }
            }
            .padding(.horizontal, SautaiDesign.spacingXS)
            .padding(.bottom, SautaiDesign.spacingS)
        }
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var chefPlaceholder: some View {
        Image(systemName: "person.crop.circle.fill")
            .font(.system(size: 40))
            .foregroundColor(.sautai.herbGreen)
    }
}

// MARK: - Public Chef Model

struct PublicChef: Codable, Identifiable {
    let id: Int
    let username: String?
    let displayName: String
    let bio: String?
    let cuisines: [String]?
    let specialties: [String]?
    let profileImageUrl: String?
    let rating: Double?
    let reviewCount: Int?
    let isVerified: Bool?
    let isLive: Bool?

    enum CodingKeys: String, CodingKey {
        case id, username, bio, cuisines, specialties, rating, isVerified, isLive
        case displayName = "display_name"
        case profileImageUrl = "profile_image_url"
        case reviewCount = "review_count"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        username = try container.decodeIfPresent(String.self, forKey: .username)
        displayName = try container.decodeIfPresent(String.self, forKey: .displayName) ?? "Chef"
        bio = try container.decodeIfPresent(String.self, forKey: .bio)
        cuisines = try container.decodeIfPresent([String].self, forKey: .cuisines)
        specialties = try container.decodeIfPresent([String].self, forKey: .specialties)
        profileImageUrl = try container.decodeIfPresent(String.self, forKey: .profileImageUrl)
        rating = try container.decodeIfPresent(Double.self, forKey: .rating)
        reviewCount = try container.decodeIfPresent(Int.self, forKey: .reviewCount)
        isVerified = try container.decodeIfPresent(Bool.self, forKey: .isVerified)
        isLive = try container.decodeIfPresent(Bool.self, forKey: .isLive)
    }
}

// MARK: - Preview

#Preview {
    ChefDiscoveryView()
}

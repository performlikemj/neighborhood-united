//
//  ChefProfileView.swift
//  sautai_ios
//
//  Detailed chef profile view for customers.
//  Allows viewing chef info, gallery, and initiating connection.
//

import SwiftUI

struct ChefProfileView: View {
    let chefId: Int

    @State private var chef: ChefProfileDetail?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showMessageSheet = false
    @State private var servesMyArea: Bool?
    @State private var checkingArea = false

    var body: some View {
        ScrollView {
            if isLoading {
                loadingView
            } else if let chef = chef {
                profileContent(chef)
            } else {
                errorView
            }
        }
        .background(Color.sautai.softCream)
        .navigationBarTitleDisplayMode(.inline)
        .sheet(isPresented: $showMessageSheet) {
            if let chef = chef {
                NewMessageSheet(chef: chef)
            }
        }
        .task {
            await loadChefProfile()
        }
    }

    // MARK: - Profile Content

    @ViewBuilder
    private func profileContent(_ chef: ChefProfileDetail) -> some View {
        VStack(spacing: 0) {
            // Header with photo
            headerSection(chef)

            // Main content
            VStack(spacing: SautaiDesign.spacingL) {
                // Quick stats
                statsSection(chef)

                // About
                if let bio = chef.bio, !bio.isEmpty {
                    aboutSection(bio)
                }

                // Cuisines & Specialties
                if let cuisines = chef.cuisines, !cuisines.isEmpty {
                    tagsSection(title: "Cuisines", tags: cuisines, color: .sautai.earthenClay)
                }

                if let specialties = chef.specialties, !specialties.isEmpty {
                    tagsSection(title: "Specialties", tags: specialties, color: .sautai.herbGreen)
                }

                // Service area check
                serviceAreaSection

                // Gallery
                if let photos = chef.photos, !photos.isEmpty {
                    gallerySection(photos)
                }

                // Action buttons
                actionButtons(chef)
            }
            .padding(SautaiDesign.spacing)
        }
    }

    // MARK: - Header Section

    private func headerSection(_ chef: ChefProfileDetail) -> some View {
        ZStack(alignment: .bottom) {
            // Cover image or gradient
            LinearGradient(
                colors: [.sautai.earthenClay, .sautai.clayPotBrown],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .frame(height: 200)

            // Profile photo
            VStack {
                ZStack {
                    Circle()
                        .fill(Color.white)
                        .frame(width: 110, height: 110)

                    if let imageUrl = chef.profileImageUrl {
                        AsyncImage(url: URL(string: imageUrl)) { image in
                            image
                                .resizable()
                                .scaledToFill()
                        } placeholder: {
                            profilePlaceholder
                        }
                        .frame(width: 100, height: 100)
                        .clipShape(Circle())
                    } else {
                        profilePlaceholder
                    }

                    // Verified badge
                    if chef.isVerified == true {
                        Image(systemName: "checkmark.seal.fill")
                            .font(.system(size: 24))
                            .foregroundColor(.sautai.herbGreen)
                            .background(Circle().fill(.white).padding(-2))
                            .offset(x: 35, y: 35)
                    }
                }

                Text(chef.displayName)
                    .font(SautaiFont.title)
                    .foregroundColor(.sautai.slateTile)

                if let username = chef.username {
                    Text("@\(username)")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }
            }
            .offset(y: 60)
        }
        .padding(.bottom, 70)
    }

    private var profilePlaceholder: some View {
        Circle()
            .fill(Color.sautai.herbGreen.opacity(0.2))
            .frame(width: 100, height: 100)
            .overlay(
                Image(systemName: "person.fill")
                    .font(.system(size: 40))
                    .foregroundColor(.sautai.herbGreen)
            )
    }

    // MARK: - Stats Section

    private func statsSection(_ chef: ChefProfileDetail) -> some View {
        HStack(spacing: SautaiDesign.spacingL) {
            if let rating = chef.rating {
                statItem(
                    value: String(format: "%.1f", rating),
                    label: "Rating",
                    icon: "star.fill",
                    color: .sautai.sunlitApricot
                )
            }

            if let reviewCount = chef.reviewCount, reviewCount > 0 {
                statItem(
                    value: "\(reviewCount)",
                    label: "Reviews",
                    icon: "message.fill",
                    color: .sautai.herbGreen
                )
            }

            if let years = chef.yearsExperience, years > 0 {
                statItem(
                    value: "\(years)",
                    label: "Years Exp.",
                    icon: "clock.fill",
                    color: .sautai.earthenClay
                )
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func statItem(value: String, label: String, icon: String, color: Color) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundColor(color)
                Text(value)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)
            }
            Text(label)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.6))
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - About Section

    private func aboutSection(_ bio: String) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text("About")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text(bio)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.8))
                .lineSpacing(4)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Tags Section

    private func tagsSection(title: String, tags: [String], color: Color) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text(title)
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            FlowLayout(spacing: SautaiDesign.spacingS) {
                ForEach(tags, id: \.self) { tag in
                    Text(tag)
                        .font(SautaiFont.caption)
                        .foregroundColor(color)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingXS)
                        .background(color.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusFull)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Service Area Section

    private var serviceAreaSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            HStack {
                Text("Service Area")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if checkingArea {
                    ProgressView()
                        .scaleEffect(0.8)
                }
            }

            if let serves = servesMyArea {
                HStack(spacing: SautaiDesign.spacingS) {
                    Image(systemName: serves ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundColor(serves ? .sautai.success : .sautai.warning)

                    Text(serves
                        ? "This chef delivers to your area!"
                        : "This chef doesn't serve your area yet")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.8))
                }
            } else {
                Button {
                    Task { await checkServiceArea() }
                } label: {
                    Text("Check if they serve my area")
                        .font(SautaiFont.buttonSmall)
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Gallery Section

    private func gallerySection(_ photos: [ChefPhotoItem]) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
            Text("Gallery")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: SautaiDesign.spacingS) {
                    ForEach(photos) { photo in
                        AsyncImage(url: URL(string: photo.imageUrl)) { image in
                            image
                                .resizable()
                                .scaledToFill()
                        } placeholder: {
                            Rectangle()
                                .fill(Color.sautai.softCream)
                        }
                        .frame(width: 150, height: 150)
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                        .clipped()
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Action Buttons

    private func actionButtons(_ chef: ChefProfileDetail) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Message button
            Button {
                showMessageSheet = true
            } label: {
                HStack {
                    Image(systemName: "bubble.left.fill")
                    Text("Message Chef")
                }
                .font(SautaiFont.button)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .frame(height: SautaiDesign.buttonHeight)
                .background(Color.sautai.earthenClay)
                .cornerRadius(SautaiDesign.cornerRadius)
            }

            // View services button
            Button {
                // TODO: Navigate to services
            } label: {
                HStack {
                    Image(systemName: "list.bullet.rectangle")
                    Text("View Services")
                }
                .font(SautaiFont.button)
                .foregroundColor(.sautai.earthenClay)
                .frame(maxWidth: .infinity)
                .frame(height: SautaiDesign.buttonHeight)
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadius)
                .overlay(
                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                        .stroke(Color.sautai.earthenClay, lineWidth: 2)
                )
            }
        }
        .padding(.top, SautaiDesign.spacingM)
    }

    // MARK: - Loading & Error Views

    private var loadingView: some View {
        VStack {
            ProgressView()
            Text("Loading profile...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxHeight: .infinity)
    }

    private var errorView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 40))
                .foregroundColor(.sautai.warning)

            Text("Could not load profile")
                .font(SautaiFont.headline)

            Button("Try Again") {
                Task { await loadChefProfile() }
            }
            .foregroundColor(.sautai.earthenClay)
        }
        .frame(maxHeight: .infinity)
    }

    // MARK: - Data Loading

    private func loadChefProfile() async {
        isLoading = true
        do {
            chef = try await APIClient.shared.getChefProfile(id: chefId)
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func checkServiceArea() async {
        checkingArea = true
        do {
            servesMyArea = try await APIClient.shared.checkChefServesArea(chefId: chefId)
        } catch {
            servesMyArea = false
        }
        checkingArea = false
    }
}

// MARK: - Chef Profile Detail Model

struct ChefProfileDetail: Codable, Identifiable {
    let id: Int
    let username: String?
    let displayName: String
    let bio: String?
    let cuisines: [String]?
    let specialties: [String]?
    let profileImageUrl: String?
    let coverImageUrl: String?
    let rating: Double?
    let reviewCount: Int?
    let yearsExperience: Int?
    let isVerified: Bool?
    let isLive: Bool?
    let photos: [ChefPhotoItem]?
}

struct ChefPhotoItem: Codable, Identifiable {
    let id: Int
    let imageUrl: String
    let caption: String?
}

// MARK: - Flow Layout

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrangeSubviews(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrangeSubviews(proposal: proposal, subviews: subviews)
        for (index, frame) in result.frames.enumerated() {
            subviews[index].place(at: CGPoint(x: bounds.minX + frame.minX, y: bounds.minY + frame.minY), proposal: .unspecified)
        }
    }

    private func arrangeSubviews(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, frames: [CGRect]) {
        let maxWidth = proposal.width ?? .infinity
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0
        var frames: [CGRect] = []

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)

            if currentX + size.width > maxWidth && currentX > 0 {
                currentX = 0
                currentY += lineHeight + spacing
                lineHeight = 0
            }

            frames.append(CGRect(x: currentX, y: currentY, width: size.width, height: size.height))
            lineHeight = max(lineHeight, size.height)
            currentX += size.width + spacing
        }

        return (CGSize(width: maxWidth, height: currentY + lineHeight), frames)
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ChefProfileView(chefId: 1)
    }
}

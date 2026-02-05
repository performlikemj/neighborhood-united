//
//  ChefProfileManagementView.swift
//  sautai_ios
//
//  Chef's own profile management and editing.
//

import SwiftUI

struct ChefProfileManagementView: View {
    @State private var profile: ChefProfile?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingEditSheet = false
    @State private var showingBreakSheet = false
    @State private var showingPhotosSheet = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    if isLoading {
                        loadingView
                    } else if let error = error {
                        errorView(error)
                    } else if let profile = profile {
                        // Profile Header
                        profileHeader(profile)

                        // Status Controls
                        statusSection(profile)

                        // Quick Stats
                        statsSection(profile)

                        // Profile Sections
                        profileSections(profile)
                    }
                }
                .padding(SautaiDesign.spacing)
            }
            .background(Color.sautai.softCream)
            .navigationTitle("My Profile")
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        showingEditSheet = true
                    } label: {
                        Image(systemName: "pencil")
                    }
                }
            }
            .sheet(isPresented: $showingEditSheet) {
                if let profile = profile {
                    EditChefProfileView(profile: profile) { updated in
                        self.profile = updated
                    }
                }
            }
            .sheet(isPresented: $showingBreakSheet) {
                if let profile = profile {
                    SetBreakStatusView(profile: profile) { updated in
                        self.profile = updated
                    }
                }
            }
            .sheet(isPresented: $showingPhotosSheet) {
                PhotosManagementView()
            }
            .refreshable {
                await loadProfile()
            }
        }
        .task {
            await loadProfile()
        }
    }

    // MARK: - Profile Header

    private func profileHeader(_ profile: ChefProfile) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Avatar
            ZStack(alignment: .bottomTrailing) {
                Circle()
                    .fill(Color.sautai.earthenClay.opacity(0.2))
                    .frame(width: 100, height: 100)
                    .overlay(
                        Text(String(profile.displayName.prefix(1)).uppercased())
                            .font(.system(size: 40, weight: .bold))
                            .foregroundColor(.sautai.earthenClay)
                    )

                Circle()
                    .fill(profile.isLive ? Color.sautai.success : Color.sautai.slateTile.opacity(0.5))
                    .frame(width: 24, height: 24)
                    .overlay(
                        Circle()
                            .stroke(Color.white, lineWidth: 3)
                    )
            }

            // Name & Badge
            VStack(spacing: SautaiDesign.spacingXS) {
                Text(profile.displayName)
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)

                if profile.isVerified {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark.seal.fill")
                            .foregroundColor(.sautai.herbGreen)
                        Text("Verified Chef")
                            .foregroundColor(.sautai.herbGreen)
                    }
                    .font(SautaiFont.caption)
                }
            }

            // Location
            if let location = profile.location {
                HStack(spacing: 4) {
                    Image(systemName: "location.fill")
                    Text(location)
                }
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
            }
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Status Section

    private func statusSection(_ profile: ChefProfile) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Live Status Toggle
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Accepting Orders")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    Text(profile.isLive ? "Your profile is visible to customers" : "Your profile is hidden from search")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                Spacer()

                Toggle("", isOn: Binding(
                    get: { profile.isLive },
                    set: { newValue in toggleLiveStatus(newValue) }
                ))
                .tint(.sautai.herbGreen)
            }

            Divider()

            // Break Status
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("On Break")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if profile.isOnBreak, let returnDate = profile.breakReturnDate {
                        Text("Returning \(returnDate.formatted(date: .abbreviated, time: .omitted))")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.warning)
                    } else {
                        Text("Not currently on break")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                Spacer()

                Button {
                    showingBreakSheet = true
                } label: {
                    Text(profile.isOnBreak ? "Edit" : "Set Break")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.earthenClay)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingS)
                        .background(Color.sautai.earthenClay.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Stats Section

    private func statsSection(_ profile: ChefProfile) -> some View {
        HStack(spacing: SautaiDesign.spacingM) {
            statCard(value: "\(profile.totalClients ?? 0)", label: "Clients", color: .sautai.earthenClay)
            statCard(value: String(format: "%.1f", profile.averageRating ?? 0), label: "Rating", color: .sautai.sunlitApricot)
            statCard(value: "\(profile.totalOrders ?? 0)", label: "Orders", color: .sautai.herbGreen)
        }
    }

    private func statCard(value: String, label: String, color: Color) -> some View {
        VStack(spacing: SautaiDesign.spacingXS) {
            Text(value)
                .font(SautaiFont.title2)
                .foregroundColor(color)
            Text(label)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Profile Sections

    private func profileSections(_ profile: ChefProfile) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Bio
            if let bio = profile.bio, !bio.isEmpty {
                profileSection(title: "About", icon: "person.text.rectangle") {
                    Text(bio)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)
                }
            }

            // Specialties
            if let specialties = profile.specialties, !specialties.isEmpty {
                profileSection(title: "Specialties", icon: "star") {
                    FlowLayout(spacing: SautaiDesign.spacingS) {
                        ForEach(specialties, id: \.self) { specialty in
                            Text(specialty)
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.earthenClay)
                                .padding(.horizontal, SautaiDesign.spacingM)
                                .padding(.vertical, SautaiDesign.spacingS)
                                .background(Color.sautai.earthenClay.opacity(0.1))
                                .cornerRadius(SautaiDesign.cornerRadiusFull)
                        }
                    }
                }
            }

            // Cuisines
            if let cuisines = profile.cuisines, !cuisines.isEmpty {
                profileSection(title: "Cuisines", icon: "fork.knife") {
                    FlowLayout(spacing: SautaiDesign.spacingS) {
                        ForEach(cuisines, id: \.self) { cuisine in
                            Text(cuisine)
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.herbGreen)
                                .padding(.horizontal, SautaiDesign.spacingM)
                                .padding(.vertical, SautaiDesign.spacingS)
                                .background(Color.sautai.herbGreen.opacity(0.1))
                                .cornerRadius(SautaiDesign.cornerRadiusFull)
                        }
                    }
                }
            }

            // Photos
            Button {
                showingPhotosSheet = true
            } label: {
                HStack {
                    Image(systemName: "photo.on.rectangle.angled")
                        .foregroundColor(.sautai.earthenClay)
                    Text("Manage Photos")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.3))
                }
                .padding(SautaiDesign.spacing)
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadius)
            }
            .buttonStyle(.plain)

            // Social Links
            if let socials = profile.socialLinks {
                profileSection(title: "Social Links", icon: "link") {
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                        if let website = socials.website {
                            socialLinkRow(icon: "globe", label: "Website", value: website)
                        }
                        if let instagram = socials.instagram {
                            socialLinkRow(icon: "camera", label: "Instagram", value: "@\(instagram)")
                        }
                        if let facebook = socials.facebook {
                            socialLinkRow(icon: "person.2", label: "Facebook", value: facebook)
                        }
                    }
                }
            }
        }
    }

    private func profileSection<Content: View>(title: String, icon: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(.sautai.earthenClay)
                Text(title)
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)
            }

            content()
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func socialLinkRow(icon: String, label: String, value: String) -> some View {
        HStack {
            Image(systemName: icon)
                .frame(width: 24)
                .foregroundColor(.sautai.slateTile.opacity(0.5))
            Text(label)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
            Spacer()
            Text(value)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.earthenClay)
        }
    }

    // MARK: - Loading & Error Views

    private var loadingView: some View {
        VStack {
            ProgressView()
                .scaleEffect(1.5)
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load profile")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadProfile() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .padding()
    }

    // MARK: - Actions

    private func loadProfile() async {
        isLoading = true
        error = nil

        do {
            profile = try await APIClient.shared.getChefProfile()
        } catch {
            self.error = error
        }

        isLoading = false
    }

    private func toggleLiveStatus(_ isLive: Bool) {
        Task {
            do {
                profile = try await APIClient.shared.setLiveStatus(isLive: isLive)
            } catch {
                // Revert on error - handled by @State
            }
        }
    }
}

// MARK: - Edit Chef Profile View

struct EditChefProfileView: View {
    @Environment(\.dismiss) var dismiss
    let profile: ChefProfile
    let onSaved: (ChefProfile) -> Void

    @State private var displayName: String
    @State private var bio: String
    @State private var location: String
    @State private var specialties: [String]
    @State private var cuisines: [String]
    @State private var website: String
    @State private var instagram: String
    @State private var facebook: String
    @State private var isSaving = false
    @State private var errorMessage: String?

    @State private var newSpecialty = ""
    @State private var newCuisine = ""

    init(profile: ChefProfile, onSaved: @escaping (ChefProfile) -> Void) {
        self.profile = profile
        self.onSaved = onSaved
        _displayName = State(initialValue: profile.displayName)
        _bio = State(initialValue: profile.bio ?? "")
        _location = State(initialValue: profile.location ?? "")
        _specialties = State(initialValue: profile.specialties ?? [])
        _cuisines = State(initialValue: profile.cuisines ?? [])
        _website = State(initialValue: profile.socialLinks?.website ?? "")
        _instagram = State(initialValue: profile.socialLinks?.instagram ?? "")
        _facebook = State(initialValue: profile.socialLinks?.facebook ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Basic Info") {
                    TextField("Display Name", text: $displayName)
                    TextField("Location", text: $location)
                }

                Section("About") {
                    TextField("Bio", text: $bio, axis: .vertical)
                        .lineLimit(3...6)
                }

                Section("Specialties") {
                    ForEach(specialties, id: \.self) { specialty in
                        HStack {
                            Text(specialty)
                            Spacer()
                            Button {
                                specialties.removeAll { $0 == specialty }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(.sautai.slateTile.opacity(0.3))
                            }
                        }
                    }

                    HStack {
                        TextField("Add specialty", text: $newSpecialty)
                        Button {
                            if !newSpecialty.isEmpty {
                                specialties.append(newSpecialty)
                                newSpecialty = ""
                            }
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(.sautai.earthenClay)
                        }
                        .disabled(newSpecialty.isEmpty)
                    }
                }

                Section("Cuisines") {
                    ForEach(cuisines, id: \.self) { cuisine in
                        HStack {
                            Text(cuisine)
                            Spacer()
                            Button {
                                cuisines.removeAll { $0 == cuisine }
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundColor(.sautai.slateTile.opacity(0.3))
                            }
                        }
                    }

                    HStack {
                        TextField("Add cuisine", text: $newCuisine)
                        Button {
                            if !newCuisine.isEmpty {
                                cuisines.append(newCuisine)
                                newCuisine = ""
                            }
                        } label: {
                            Image(systemName: "plus.circle.fill")
                                .foregroundColor(.sautai.earthenClay)
                        }
                        .disabled(newCuisine.isEmpty)
                    }
                }

                Section("Social Links") {
                    TextField("Website URL", text: $website)
                        .keyboardType(.URL)
                        .autocapitalization(.none)
                    TextField("Instagram username", text: $instagram)
                        .autocapitalization(.none)
                    TextField("Facebook", text: $facebook)
                        .autocapitalization(.none)
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Edit Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveProfile()
                    }
                    .disabled(displayName.isEmpty || isSaving)
                }
            }
        }
    }

    private func saveProfile() {
        isSaving = true
        errorMessage = nil

        let socialLinks = SocialLinks(
            website: website.isEmpty ? nil : website,
            instagram: instagram.isEmpty ? nil : instagram,
            facebook: facebook.isEmpty ? nil : facebook,
            twitter: profile.socialLinks?.twitter,
            youtube: profile.socialLinks?.youtube
        )

        let request = ChefProfileUpdateRequest(
            displayName: displayName,
            bio: bio.isEmpty ? nil : bio,
            location: location.isEmpty ? nil : location,
            specialties: specialties.isEmpty ? nil : specialties,
            cuisines: cuisines.isEmpty ? nil : cuisines,
            socialLinks: socialLinks
        )

        Task {
            do {
                let updated = try await APIClient.shared.updateChefProfile(data: request)
                await MainActor.run {
                    onSaved(updated)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isSaving = false
                }
            }
        }
    }
}

// MARK: - Set Break Status View

struct SetBreakStatusView: View {
    @Environment(\.dismiss) var dismiss
    let profile: ChefProfile
    let onSaved: (ChefProfile) -> Void

    @State private var isOnBreak: Bool
    @State private var returnDate: Date
    @State private var isSaving = false
    @State private var errorMessage: String?

    init(profile: ChefProfile, onSaved: @escaping (ChefProfile) -> Void) {
        self.profile = profile
        self.onSaved = onSaved
        _isOnBreak = State(initialValue: profile.isOnBreak)
        _returnDate = State(initialValue: profile.breakReturnDate ?? Calendar.current.date(byAdding: .day, value: 7, to: Date())!)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Toggle("On Break", isOn: $isOnBreak)
                }

                if isOnBreak {
                    Section("Return Date") {
                        DatePicker("Return on", selection: $returnDate, in: Date()..., displayedComponents: .date)
                    }

                    Section {
                        Text("While on break, your profile will show as unavailable and customers won't be able to place new orders.")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Break Status")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        saveBreakStatus()
                    }
                    .disabled(isSaving)
                }
            }
        }
    }

    private func saveBreakStatus() {
        isSaving = true
        errorMessage = nil

        Task {
            do {
                let updated = try await APIClient.shared.setBreakStatus(
                    onBreak: isOnBreak,
                    returnDate: isOnBreak ? returnDate : nil
                )
                await MainActor.run {
                    onSaved(updated)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isSaving = false
                }
            }
        }
    }
}

// MARK: - Photos Management View

struct PhotosManagementView: View {
    @Environment(\.dismiss) var dismiss
    @State private var photos: [ChefPhoto] = []
    @State private var isLoading = true
    @State private var error: Error?

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView()
                } else if photos.isEmpty {
                    emptyView
                } else {
                    photosList
                }
            }
            .navigationTitle("Photos")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Done") { dismiss() }
                }
            }
        }
        .task {
            await loadPhotos()
        }
    }

    private var photosList: some View {
        ScrollView {
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: SautaiDesign.spacingM) {
                ForEach(photos) { photo in
                    PhotoCard(photo: photo) {
                        deletePhoto(photo)
                    }
                }
            }
            .padding(SautaiDesign.spacing)
        }
    }

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "photo.on.rectangle.angled")
                .font(.system(size: 48))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No photos yet")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
    }

    private func loadPhotos() async {
        isLoading = true
        do {
            photos = try await APIClient.shared.getChefPhotos()
        } catch {
            self.error = error
        }
        isLoading = false
    }

    private func deletePhoto(_ photo: ChefPhoto) {
        Task {
            do {
                try await APIClient.shared.deleteChefPhoto(id: photo.id)
                photos.removeAll { $0.id == photo.id }
            } catch {
                self.error = error
            }
        }
    }
}

struct PhotoCard: View {
    let photo: ChefPhoto
    let onDelete: () -> Void

    var body: some View {
        ZStack(alignment: .topTrailing) {
            RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                .fill(Color.sautai.slateTile.opacity(0.1))
                .aspectRatio(1, contentMode: .fit)
                .overlay(
                    Image(systemName: "photo")
                        .font(.system(size: 32))
                        .foregroundColor(.sautai.slateTile.opacity(0.3))
                )

            Button {
                onDelete()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.title2)
                    .foregroundColor(.sautai.danger)
                    .background(Color.white)
                    .clipShape(Circle())
            }
            .padding(SautaiDesign.spacingS)
        }
    }
}

#Preview {
    ChefProfileManagementView()
}

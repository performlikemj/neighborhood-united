//
//  SettingsView.swift
//  sautai_ios
//
//  User settings and preferences.
//

import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var authManager: AuthManager
    @State private var showLogoutConfirmation = false
    @State private var showChangePassword = false
    @State private var showDeleteAccount = false

    var body: some View {
        NavigationStack {
            List {
                // Profile Section
                Section {
                    profileRow

                    Button {
                        showChangePassword = true
                    } label: {
                        HStack {
                            Image(systemName: "key.fill")
                                .foregroundColor(.sautai.earthenClay)
                                .frame(width: 28)

                            Text("Change Password")
                                .font(SautaiFont.body)
                                .foregroundColor(.sautai.slateTile)

                            Spacer()

                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.3))
                        }
                    }

                    Button {
                        showDeleteAccount = true
                    } label: {
                        HStack {
                            Image(systemName: "trash.fill")
                                .foregroundColor(.sautai.danger)
                                .frame(width: 28)

                            Text("Delete Account")
                                .font(SautaiFont.body)
                                .foregroundColor(.sautai.danger)

                            Spacer()

                            Image(systemName: "chevron.right")
                                .font(.caption)
                                .foregroundColor(.sautai.slateTile.opacity(0.3))
                        }
                    }
                } header: {
                    Text("Account")
                }

                // Role Switch Section
                if authManager.currentUser?.isChef == true {
                    Section {
                        roleSwitchRow
                    } header: {
                        Text("Current Role")
                    }
                }

                // Chef Tools Section (only visible for chefs)
                if authManager.currentRole == .chef {
                    Section {
                        NavigationLink {
                            LeadsListView()
                        } label: {
                            HStack {
                                Image(systemName: "person.badge.plus")
                                    .foregroundColor(.sautai.herbGreen)
                                    .frame(width: 28)

                                Text("Leads")
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)
                            }
                        }

                        NavigationLink {
                            SousChefView()
                        } label: {
                            HStack {
                                Image(systemName: "bubble.left.and.bubble.right.fill")
                                    .foregroundColor(.sautai.sunlitApricot)
                                    .frame(width: 28)

                                Text("Sous Chef AI")
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)
                            }
                        }
                    } header: {
                        Text("Chef Tools")
                    }

                    // Integrations Section (chef-only)
                    Section {
                        NavigationLink {
                            TelegramLinkingView()
                        } label: {
                            HStack {
                                Image(systemName: "paperplane.fill")
                                    .foregroundColor(Color(red: 0.0, green: 0.54, blue: 0.89)) // Telegram blue
                                    .frame(width: 28)

                                Text("Telegram")
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)

                                Spacer()

                                Text("Notifications")
                                    .font(SautaiFont.caption)
                                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                            }
                        }

                        NavigationLink {
                            WorkspaceSettingsView()
                        } label: {
                            HStack {
                                Image(systemName: "gearshape.2.fill")
                                    .foregroundColor(.sautai.herbGreen)
                                    .frame(width: 28)

                                Text("Sous Chef Settings")
                                    .font(SautaiFont.body)
                                    .foregroundColor(.sautai.slateTile)

                                Spacer()

                                Text("AI Customization")
                                    .font(SautaiFont.caption)
                                    .foregroundColor(.sautai.slateTile.opacity(0.5))
                            }
                        }
                    } header: {
                        Text("Integrations")
                    }
                }

                // Preferences Section
                Section {
                    settingsRow(icon: "bell.fill", title: "Notifications", color: .sautai.sunlitApricot)
                    settingsRow(icon: "globe", title: "Language", value: "English", color: .sautai.herbGreen)
                    settingsRow(icon: "ruler", title: "Measurement", value: authManager.currentUser?.measurementSystem.displayName ?? "US", color: .sautai.clayPotBrown)
                } header: {
                    Text("Preferences")
                }

                // Support Section
                Section {
                    settingsRow(icon: "questionmark.circle.fill", title: "Help & Support", color: .sautai.info)
                    settingsRow(icon: "doc.text.fill", title: "Terms of Service", color: .sautai.slateTile)
                    settingsRow(icon: "hand.raised.fill", title: "Privacy Policy", color: .sautai.slateTile)
                } header: {
                    Text("Support")
                }

                // Logout Section
                Section {
                    Button(role: .destructive) {
                        showLogoutConfirmation = true
                    } label: {
                        HStack {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                            Text("Sign Out")
                        }
                        .foregroundColor(.sautai.danger)
                    }
                }

                // App Version
                Section {
                    HStack {
                        Text("Version")
                            .foregroundColor(.sautai.slateTile)
                        Spacer()
                        Text("1.0.0 (1)")
                            .foregroundColor(.sautai.slateTile.opacity(0.5))
                    }
                }
            }
            .listStyle(.insetGrouped)
            .scrollContentBackground(.hidden)
            .background(Color.sautai.softCream)
            .navigationTitle("Settings")
            .confirmationDialog(
                "Sign Out",
                isPresented: $showLogoutConfirmation,
                titleVisibility: .visible
            ) {
                Button("Sign Out", role: .destructive) {
                    Task {
                        await authManager.logout()
                    }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("Are you sure you want to sign out?")
            }
            .sheet(isPresented: $showChangePassword) {
                ChangePasswordView()
            }
            .sheet(isPresented: $showDeleteAccount) {
                DeleteAccountView()
                    .environmentObject(authManager)
            }
        }
    }

    // MARK: - Profile Row

    private var profileRow: some View {
        NavigationLink {
            ProfileSettingsView()
        } label: {
            HStack(spacing: SautaiDesign.spacingM) {
                // Avatar
                Circle()
                    .fill(Color.sautai.earthenClay.opacity(0.2))
                    .frame(width: SautaiDesign.avatarSizeL, height: SautaiDesign.avatarSizeL)
                    .overlay(
                        Text(authManager.currentUser?.username.prefix(2).uppercased() ?? "??")
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.earthenClay)
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text(authManager.currentUser?.username ?? "User")
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    Text(authManager.currentUser?.email ?? "")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }
            .padding(.vertical, SautaiDesign.spacingS)
        }
    }

    // MARK: - Role Switch Row

    private var roleSwitchRow: some View {
        HStack {
            Image(systemName: authManager.currentRole == .chef ? "flame.fill" : "person.fill")
                .foregroundColor(.sautai.earthenClay)
                .frame(width: 28)

            Text(authManager.currentRole == .chef ? "Chef Mode" : "Customer Mode")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)

            Spacer()

            Button {
                Task {
                    let newRole: UserRole = authManager.currentRole == .chef ? .customer : .chef
                    try? await authManager.switchRole(to: newRole)
                }
            } label: {
                Text("Switch")
                    .font(SautaiFont.buttonSmall)
                    .foregroundColor(.sautai.earthenClay)
            }
        }
    }

    // MARK: - Settings Row

    private func settingsRow(icon: String, title: String, value: String? = nil, color: Color) -> some View {
        NavigationLink {
            Text(title) // Placeholder destination
        } label: {
            HStack {
                Image(systemName: icon)
                    .foregroundColor(color)
                    .frame(width: 28)

                Text(title)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if let value = value {
                    Text(value)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }
        }
    }
}

// MARK: - Profile Settings View (Placeholder)

struct ProfileSettingsView: View {
    @EnvironmentObject var authManager: AuthManager

    var body: some View {
        Form {
            Section("Personal Information") {
                TextField("Username", text: .constant(authManager.currentUser?.username ?? ""))
                TextField("Email", text: .constant(authManager.currentUser?.email ?? ""))
                TextField("Phone", text: .constant(authManager.currentUser?.phoneNumber ?? ""))
            }

            Section("Address") {
                TextField("Street", text: .constant(authManager.currentUser?.address?.street ?? ""))
                TextField("City", text: .constant(authManager.currentUser?.address?.city ?? ""))
                TextField("State", text: .constant(authManager.currentUser?.address?.state ?? ""))
                TextField("Postal Code", text: .constant(authManager.currentUser?.address?.displayPostalCode ?? ""))
            }
        }
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.inline)
    }
}

// MARK: - Preview

#Preview {
    SettingsView()
        .environmentObject(AuthManager.shared)
}

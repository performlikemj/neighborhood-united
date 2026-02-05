//
//  ChangePasswordView.swift
//  sautai_ios
//
//  Change password screen for authenticated users.
//

import SwiftUI

struct ChangePasswordView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var currentPassword = ""
    @State private var newPassword = ""
    @State private var confirmPassword = ""
    @State private var showCurrentPassword = false
    @State private var showNewPassword = false
    @State private var isLoading = false
    @State private var showSuccess = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                // Current Password
                Section {
                    HStack {
                        if showCurrentPassword {
                            TextField("Current Password", text: $currentPassword)
                        } else {
                            SecureField("Current Password", text: $currentPassword)
                        }

                        Button {
                            showCurrentPassword.toggle()
                        } label: {
                            Image(systemName: showCurrentPassword ? "eye.slash" : "eye")
                                .foregroundColor(.sautai.slateTile)
                        }
                    }
                } header: {
                    Text("Current Password")
                }

                // New Password
                Section {
                    HStack {
                        if showNewPassword {
                            TextField("New Password", text: $newPassword)
                        } else {
                            SecureField("New Password", text: $newPassword)
                        }

                        Button {
                            showNewPassword.toggle()
                        } label: {
                            Image(systemName: showNewPassword ? "eye.slash" : "eye")
                                .foregroundColor(.sautai.slateTile)
                        }
                    }

                    SecureField("Confirm New Password", text: $confirmPassword)

                    // Password strength indicator
                    if !newPassword.isEmpty {
                        HStack(spacing: SautaiDesign.spacingXS) {
                            ForEach(0..<3, id: \.self) { index in
                                RoundedRectangle(cornerRadius: 2)
                                    .fill(strengthBarColor(for: index))
                                    .frame(height: 4)
                            }
                            Text(passwordStrength.label)
                                .font(SautaiFont.caption2)
                                .foregroundColor(passwordStrength.color)
                        }
                    }
                } header: {
                    Text("New Password")
                } footer: {
                    VStack(alignment: .leading, spacing: 4) {
                        if !newPassword.isEmpty && newPassword.count < 8 {
                            Text("Password must be at least 8 characters")
                                .foregroundColor(.sautai.danger)
                        }
                        if !confirmPassword.isEmpty && !passwordsMatch {
                            Text("Passwords don't match")
                                .foregroundColor(.sautai.danger)
                        }
                    }
                    .font(SautaiFont.caption2)
                }

                // Error Message
                if let error = errorMessage {
                    Section {
                        Text(error)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.danger)
                    }
                }

                // Submit Button
                Section {
                    Button {
                        changePassword()
                    } label: {
                        HStack {
                            Spacer()
                            if isLoading {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Text("Change Password")
                            }
                            Spacer()
                        }
                    }
                    .listRowBackground(Color.sautai.earthenClay.opacity(isFormValid ? 1 : 0.5))
                    .foregroundColor(.white)
                    .disabled(!isFormValid || isLoading)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Color.sautai.softCream)
            .navigationTitle("Change Password")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button("Cancel") {
                        dismiss()
                    }
                    .foregroundColor(.sautai.earthenClay)
                }
            }
            .alert("Password Changed", isPresented: $showSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("Your password has been updated successfully.")
            }
        }
    }

    // MARK: - Validation

    private var passwordsMatch: Bool {
        newPassword == confirmPassword
    }

    private var isFormValid: Bool {
        !currentPassword.isEmpty &&
        newPassword.count >= 8 &&
        passwordsMatch
    }

    private var passwordStrength: PasswordStrength {
        if newPassword.count < 8 { return .weak }
        var score = 0
        if newPassword.contains(where: { $0.isLowercase }) { score += 1 }
        if newPassword.contains(where: { $0.isUppercase }) { score += 1 }
        if newPassword.contains(where: { $0.isNumber }) { score += 1 }
        if newPassword.contains(where: { "!@#$%^&*()_+-=[]{}|;:,.<>?".contains($0) }) { score += 1 }
        if newPassword.count >= 12 { score += 1 }

        switch score {
        case 0...2: return .weak
        case 3: return .medium
        default: return .strong
        }
    }

    private func strengthBarColor(for index: Int) -> Color {
        switch passwordStrength {
        case .weak:
            return index == 0 ? .sautai.danger : Color.sautai.lightBorder
        case .medium:
            return index < 2 ? .sautai.warning : Color.sautai.lightBorder
        case .strong:
            return .sautai.success
        }
    }

    // MARK: - Actions

    private func changePassword() {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await APIClient.shared.changePassword(
                    currentPassword: currentPassword,
                    newPassword: newPassword
                )
                await MainActor.run {
                    isLoading = false
                    showSuccess = true
                }
            } catch let error as APIError {
                await MainActor.run {
                    isLoading = false
                    switch error {
                    case .badRequest(let message):
                        errorMessage = message.isEmpty ? "Invalid current password" : message
                    case .forbidden:
                        errorMessage = "Session expired. Please log in again."
                    default:
                        errorMessage = error.localizedDescription
                    }
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = "Failed to change password. Please try again."
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    ChangePasswordView()
}

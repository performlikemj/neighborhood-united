//
//  DeleteAccountView.swift
//  sautai_ios
//
//  Account deletion confirmation screen.
//

import SwiftUI

struct DeleteAccountView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var authManager: AuthManager

    @State private var password = ""
    @State private var confirmText = ""
    @State private var isLoading = false
    @State private var showFinalConfirmation = false
    @State private var errorMessage: String?

    private let confirmationPhrase = "DELETE"

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    // Warning Icon
                    Image(systemName: "exclamationmark.triangle.fill")
                        .font(.system(size: 60))
                        .foregroundColor(.sautai.danger)
                        .padding(.top, SautaiDesign.spacingL)

                    // Warning Text
                    VStack(spacing: SautaiDesign.spacingM) {
                        Text("Delete Account")
                            .font(SautaiFont.title)
                            .foregroundColor(.sautai.slateTile)

                        Text("This action cannot be undone. All your data will be permanently deleted, including:")
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                            .multilineTextAlignment(.center)
                    }

                    // What will be deleted
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                        deletionItem("Your profile and account information")
                        deletionItem("All your orders and order history")
                        deletionItem("Saved preferences and settings")
                        deletionItem("Chat history with Sous Chef")
                        if authManager.currentUser?.isChef == true {
                            deletionItem("Your chef profile and services")
                            deletionItem("Client relationships and notes")
                            deletionItem("Meal plans and recipes")
                        }
                    }
                    .padding(SautaiDesign.spacing)
                    .background(Color.sautai.danger.opacity(0.1))
                    .cornerRadius(SautaiDesign.cornerRadius)

                    // Confirmation Form
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
                        // Password
                        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                            Text("Enter your password")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile)

                            SecureField("Password", text: $password)
                                .padding()
                                .background(Color.white)
                                .cornerRadius(SautaiDesign.cornerRadius)
                                .overlay(
                                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                                        .stroke(Color.sautai.lightBorder, lineWidth: 1)
                                )
                        }

                        // Confirmation Text
                        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                            Text("Type \"\(confirmationPhrase)\" to confirm")
                                .font(SautaiFont.caption)
                                .foregroundColor(.sautai.slateTile)

                            TextField(confirmationPhrase, text: $confirmText)
                                .autocapitalization(.allCharacters)
                                .autocorrectionDisabled()
                                .padding()
                                .background(Color.white)
                                .cornerRadius(SautaiDesign.cornerRadius)
                                .overlay(
                                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                                        .stroke(Color.sautai.lightBorder, lineWidth: 1)
                                )
                        }
                    }
                    .padding(.top, SautaiDesign.spacingM)

                    // Error Message
                    if let error = errorMessage {
                        Text(error)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.danger)
                            .multilineTextAlignment(.center)
                    }

                    // Delete Button
                    Button {
                        showFinalConfirmation = true
                    } label: {
                        HStack {
                            if isLoading {
                                ProgressView()
                                    .tint(.white)
                            } else {
                                Image(systemName: "trash.fill")
                                Text("Delete My Account")
                            }
                        }
                        .font(SautaiFont.button)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: SautaiDesign.buttonHeight)
                        .background(Color.sautai.danger.opacity(isFormValid ? 1 : 0.5))
                        .cornerRadius(SautaiDesign.cornerRadius)
                    }
                    .disabled(!isFormValid || isLoading)

                    // Cancel Link
                    Button("Cancel") {
                        dismiss()
                    }
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)
                    .padding(.bottom, SautaiDesign.spacingL)
                }
                .padding(SautaiDesign.spacingL)
            }
            .background(Color.sautai.softCream)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "xmark")
                            .foregroundColor(.sautai.slateTile)
                    }
                }
            }
            .alert("Final Confirmation", isPresented: $showFinalConfirmation) {
                Button("Cancel", role: .cancel) {}
                Button("Delete Forever", role: .destructive) {
                    deleteAccount()
                }
            } message: {
                Text("Are you absolutely sure? This will permanently delete your account and all associated data. This cannot be undone.")
            }
        }
    }

    // MARK: - Components

    private func deletionItem(_ text: String) -> some View {
        HStack(alignment: .top, spacing: SautaiDesign.spacingS) {
            Image(systemName: "xmark.circle.fill")
                .foregroundColor(.sautai.danger)
                .font(.system(size: 16))

            Text(text)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)
        }
    }

    // MARK: - Validation

    private var isFormValid: Bool {
        !password.isEmpty && confirmText == confirmationPhrase
    }

    // MARK: - Actions

    private func deleteAccount() {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await APIClient.shared.deleteAccount(password: password)
                await MainActor.run {
                    // Clear local session and navigate to login
                    authManager.clearLocalSession()
                }
            } catch let error as APIError {
                await MainActor.run {
                    isLoading = false
                    switch error {
                    case .badRequest(let message):
                        errorMessage = message.isEmpty ? "Incorrect password" : message
                    case .forbidden:
                        errorMessage = "Session expired. Please log in and try again."
                    default:
                        errorMessage = error.localizedDescription
                    }
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    errorMessage = "Failed to delete account. Please try again."
                }
            }
        }
    }
}

// MARK: - Preview

#Preview {
    DeleteAccountView()
        .environmentObject(AuthManager.shared)
}

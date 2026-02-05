//
//  ForgotPasswordView.swift
//  sautai_ios
//
//  Password reset request screen.
//

import SwiftUI

struct ForgotPasswordView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var email = ""
    @State private var isLoading = false
    @State private var showSuccess = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: SautaiDesign.spacingXL) {
                Spacer()

                // Icon
                Image(systemName: "key.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.sautai.earthenClay)

                // Header
                VStack(spacing: SautaiDesign.spacingS) {
                    Text("Reset Password")
                        .font(SautaiFont.title)
                        .foregroundColor(.sautai.slateTile)

                    Text("Enter your email and we'll send you a link to reset your password.")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                        .multilineTextAlignment(.center)
                }

                // Email Field
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    Text("Email")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile)

                    TextField("your@email.com", text: $email)
                        .textContentType(.emailAddress)
                        .keyboardType(.emailAddress)
                        .autocapitalization(.none)
                        .autocorrectionDisabled()
                        .padding()
                        .background(Color.white)
                        .cornerRadius(SautaiDesign.cornerRadius)
                        .overlay(
                            RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                                .stroke(Color.sautai.lightBorder, lineWidth: 1)
                        )
                }

                // Error Message
                if let error = errorMessage {
                    Text(error)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.danger)
                }

                // Submit Button
                Button {
                    sendResetLink()
                } label: {
                    HStack {
                        if isLoading {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Send Reset Link")
                        }
                    }
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: SautaiDesign.buttonHeight)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
                }
                .disabled(email.isEmpty || isLoading)
                .opacity(email.isEmpty ? 0.6 : 1)

                Spacer()
                Spacer()
            }
            .padding(SautaiDesign.spacingL)
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
            .alert("Check Your Email", isPresented: $showSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("If an account exists with that email, you'll receive a password reset link shortly.")
            }
        }
    }

    private func sendResetLink() {
        isLoading = true
        errorMessage = nil

        Task {
            do {
                try await APIClient.shared.requestPasswordReset(email: email)
                await MainActor.run {
                    isLoading = false
                    showSuccess = true
                }
            } catch {
                await MainActor.run {
                    isLoading = false
                    // Always show success to prevent email enumeration
                    showSuccess = true
                }
            }
        }
    }

    private var isValidEmail: Bool {
        let emailRegex = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/
        return email.wholeMatch(of: emailRegex) != nil
    }
}

// MARK: - Preview

#Preview {
    ForgotPasswordView()
}

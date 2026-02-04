//
//  RegisterView.swift
//  sautai_ios
//
//  Registration screen for new users.
//

import SwiftUI

struct RegisterView: View {
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var authManager: AuthManager

    @State private var email = ""
    @State private var username = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var phoneNumber = ""
    @State private var showPassword = false
    @State private var agreeToTerms = false
    @State private var showSuccess = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    // Header
                    VStack(spacing: SautaiDesign.spacingS) {
                        Text("Join sautAI")
                            .font(SautaiFont.title)
                            .foregroundColor(.sautai.slateTile)

                        Text("Cook together. Eat together. Be together.")
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                            .multilineTextAlignment(.center)
                    }
                    .padding(.top, SautaiDesign.spacingL)

                    // Form
                    VStack(spacing: SautaiDesign.spacing) {
                        formField(title: "Email", text: $email, placeholder: "your@email.com", keyboardType: .emailAddress)
                        formField(title: "Username", text: $username, placeholder: "Choose a username")
                        formField(title: "Phone (optional)", text: $phoneNumber, placeholder: "+1 (555) 123-4567", keyboardType: .phonePad)
                        passwordFields
                    }

                    // Terms
                    termsCheckbox

                    // Register Button
                    registerButton

                    // Login Link
                    loginLink
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
            .alert("Account Created!", isPresented: $showSuccess) {
                Button("OK") { dismiss() }
            } message: {
                Text("Please check your email to verify your account.")
            }
        }
    }

    // MARK: - Form Field

    private func formField(
        title: String,
        text: Binding<String>,
        placeholder: String,
        keyboardType: UIKeyboardType = .default
    ) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
            Text(title)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)

            TextField(placeholder, text: text)
                .keyboardType(keyboardType)
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
    }

    // MARK: - Password Fields

    private var passwordFields: some View {
        VStack(spacing: SautaiDesign.spacing) {
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                Text("Password")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile)

                HStack {
                    if showPassword {
                        TextField("Create a password", text: $password)
                    } else {
                        SecureField("Create a password", text: $password)
                    }

                    Button {
                        showPassword.toggle()
                    } label: {
                        Image(systemName: showPassword ? "eye.slash" : "eye")
                            .foregroundColor(.sautai.slateTile)
                    }
                }
                .padding()
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadius)
                .overlay(
                    RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                        .stroke(Color.sautai.lightBorder, lineWidth: 1)
                )
            }

            VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                Text("Confirm Password")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile)

                SecureField("Confirm your password", text: $confirmPassword)
                    .padding()
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadius)
                    .overlay(
                        RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                            .stroke(passwordsMatch ? Color.sautai.lightBorder : Color.sautai.danger, lineWidth: 1)
                    )

                if !confirmPassword.isEmpty && !passwordsMatch {
                    Text("Passwords don't match")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.danger)
                }
            }
        }
    }

    // MARK: - Terms Checkbox

    private var termsCheckbox: some View {
        Button {
            agreeToTerms.toggle()
        } label: {
            HStack(alignment: .top, spacing: SautaiDesign.spacingS) {
                Image(systemName: agreeToTerms ? "checkmark.square.fill" : "square")
                    .foregroundColor(agreeToTerms ? .sautai.earthenClay : .sautai.slateTile)

                Text("I agree to the Terms of Service and Privacy Policy")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile)
                    .multilineTextAlignment(.leading)
            }
        }
    }

    // MARK: - Register Button

    private var registerButton: some View {
        Button {
            Task {
                do {
                    try await authManager.register(
                        email: email,
                        password: password,
                        username: username,
                        phoneNumber: phoneNumber.isEmpty ? nil : phoneNumber
                    )
                    showSuccess = true
                } catch {
                    // Error handled by authManager
                }
            }
        } label: {
            HStack {
                if authManager.isLoading {
                    ProgressView()
                        .tint(.white)
                } else {
                    Text("Create Account")
                }
            }
            .font(SautaiFont.button)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .frame(height: SautaiDesign.buttonHeight)
            .background(Color.sautai.earthenClay)
            .cornerRadius(SautaiDesign.cornerRadius)
        }
        .disabled(!isFormValid || authManager.isLoading)
        .opacity(isFormValid ? 1 : 0.6)
    }

    // MARK: - Login Link

    private var loginLink: some View {
        HStack {
            Text("Already have an account?")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile)

            Button("Sign In") {
                dismiss()
            }
            .font(SautaiFont.button)
            .foregroundColor(.sautai.earthenClay)
        }
    }

    // MARK: - Validation

    private var passwordsMatch: Bool {
        password == confirmPassword || confirmPassword.isEmpty
    }

    private var isFormValid: Bool {
        !email.isEmpty &&
        !username.isEmpty &&
        !password.isEmpty &&
        password == confirmPassword &&
        password.count >= 8 &&
        agreeToTerms
    }
}

// MARK: - Preview

#Preview {
    RegisterView()
        .environmentObject(AuthManager.shared)
}

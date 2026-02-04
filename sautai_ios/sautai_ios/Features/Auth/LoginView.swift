//
//  LoginView.swift
//  sautai_ios
//
//  Login screen with username and password authentication.
//

import SwiftUI

struct LoginView: View {
    @EnvironmentObject var authManager: AuthManager

    @State private var username = ""
    @State private var password = ""
    @State private var showPassword = false
    @State private var showRegister = false
    @State private var showForgotPassword = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingXL) {
                    // Logo
                    logoSection

                    // Tagline
                    Text("\"Artful kitchens. Shared hearts.\"")
                        .font(SautaiFont.handwritten)
                        .foregroundColor(.sautai.earthenClay)
                        .padding(.bottom, SautaiDesign.spacingM)

                    // Form
                    VStack(spacing: SautaiDesign.spacing) {
                        usernameField
                        passwordField
                        forgotPasswordButton
                        loginButton
                    }

                    // Divider
                    dividerSection

                    // Register
                    registerButton
                }
                .padding(SautaiDesign.spacingL)
            }
            .background(Color.sautai.softCream)
            .navigationBarHidden(true)
            .sheet(isPresented: $showRegister) {
                RegisterView()
            }
            .sheet(isPresented: $showForgotPassword) {
                ForgotPasswordView()
            }
            .alert("Login Error", isPresented: .constant(authManager.error != nil)) {
                Button("OK") { authManager.error = nil }
            } message: {
                Text(authManager.error?.localizedDescription ?? "")
            }
        }
    }

    // MARK: - Logo Section

    private var logoSection: some View {
        VStack(spacing: SautaiDesign.spacingS) {
            // Logo placeholder - replace with actual logo
            ZStack {
                Circle()
                    .fill(Color.sautai.earthenClay.opacity(0.1))
                    .frame(width: 100, height: 100)

                Image(systemName: "flame.fill")
                    .font(.system(size: 44))
                    .foregroundColor(.sautai.logoFlames)
            }

            Text("sautai")
                .font(SautaiFont.largeTitle)
                .foregroundColor(.sautai.slateTile)
        }
        .padding(.top, SautaiDesign.spacingSection)
    }

    // MARK: - Username Field

    private var usernameField: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
            Text("Username")
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)

            TextField("Enter username", text: $username)
                .textContentType(.username)
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

    // MARK: - Password Field

    private var passwordField: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
            Text("Password")
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)

            HStack {
                if showPassword {
                    TextField("Password", text: $password)
                } else {
                    SecureField("Password", text: $password)
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
    }

    // MARK: - Forgot Password Button

    private var forgotPasswordButton: some View {
        HStack {
            Spacer()
            Button("Forgot password?") {
                showForgotPassword = true
            }
            .font(SautaiFont.caption)
            .foregroundColor(.sautai.earthenClay)
        }
    }

    // MARK: - Login Button

    private var loginButton: some View {
        Button {
            Task {
                try? await authManager.login(username: username, password: password)
            }
        } label: {
            HStack {
                if authManager.isLoading {
                    ProgressView()
                        .tint(.white)
                } else {
                    Text("Sign In")
                }
            }
            .font(SautaiFont.button)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .frame(height: SautaiDesign.buttonHeight)
            .background(Color.sautai.earthenClay)
            .cornerRadius(SautaiDesign.cornerRadius)
        }
        .disabled(username.isEmpty || password.isEmpty || authManager.isLoading)
        .opacity(username.isEmpty || password.isEmpty ? 0.6 : 1)
    }

    // MARK: - Divider Section

    private var dividerSection: some View {
        HStack {
            Rectangle()
                .fill(Color.sautai.lightBorder)
                .frame(height: 1)

            Text("or")
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)
                .padding(.horizontal, SautaiDesign.spacingS)

            Rectangle()
                .fill(Color.sautai.lightBorder)
                .frame(height: 1)
        }
        .padding(.vertical, SautaiDesign.spacingM)
    }

    // MARK: - Register Button

    private var registerButton: some View {
        Button {
            showRegister = true
        } label: {
            Text("Create Account")
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
}

// MARK: - Preview

#Preview {
    LoginView()
        .environmentObject(AuthManager.shared)
}

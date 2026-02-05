//
//  WorkspaceSettingsView.swift
//  sautai_ios
//
//  Sous Chef AI workspace customization settings.
//

import SwiftUI

struct WorkspaceSettingsView: View {
    @State private var settings = WorkspaceSettings()
    @State private var isLoading = true
    @State private var isSaving = false
    @State private var error: Error?
    @State private var showError = false
    @State private var showSaveSuccess = false

    // Editable fields
    @State private var soulPrompt = ""
    @State private var businessRules = ""
    @State private var chefNickname = ""
    @State private var sousChefName = ""
    @State private var includeAnalytics = true
    @State private var includeSeasonal = true
    @State private var autoMemorySave = true

    var body: some View {
        List {
            if isLoading {
                Section {
                    HStack {
                        Spacer()
                        ProgressView()
                            .padding()
                        Spacer()
                    }
                }
            } else {
                personalitySection
                behaviorSection
                dataSection
            }
        }
        .listStyle(.insetGrouped)
        .scrollContentBackground(.hidden)
        .background(Color.sautai.softCream)
        .navigationTitle("Sous Chef Settings")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .confirmationAction) {
                if hasChanges {
                    Button {
                        Task { await saveSettings() }
                    } label: {
                        if isSaving {
                            ProgressView()
                        } else {
                            Text("Save")
                                .font(SautaiFont.button)
                        }
                    }
                    .disabled(isSaving)
                }
            }
        }
        .task {
            await loadSettings()
        }
        .alert("Error", isPresented: $showError) {
            Button("OK") {}
        } message: {
            Text(error?.localizedDescription ?? "An error occurred")
        }
        .overlay {
            if showSaveSuccess {
                SaveSuccessToast()
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
    }

    // MARK: - Personality Section

    private var personalitySection: some View {
        Section {
            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Chef Nickname")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))

                TextField("How should Sous Chef call you?", text: $chefNickname)
                    .font(SautaiFont.body)
                    .textFieldStyle(.roundedBorder)
            }
            .padding(.vertical, SautaiDesign.spacingXS)

            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Sous Chef Name")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))

                TextField("Name your AI assistant", text: $sousChefName)
                    .font(SautaiFont.body)
                    .textFieldStyle(.roundedBorder)
            }
            .padding(.vertical, SautaiDesign.spacingXS)

            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Personality Prompt")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))

                TextEditor(text: $soulPrompt)
                    .font(SautaiFont.body)
                    .frame(minHeight: 100)
                    .scrollContentBackground(.hidden)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadiusS)
                    .overlay(
                        RoundedRectangle(cornerRadius: SautaiDesign.cornerRadiusS)
                            .stroke(Color.sautai.lightBorder, lineWidth: 1)
                    )
            }
            .padding(.vertical, SautaiDesign.spacingXS)
        } header: {
            Text("Personality")
        } footer: {
            Text("Customize how your Sous Chef communicates with you. Leave blank for default behavior.")
        }
    }

    // MARK: - Behavior Section

    private var behaviorSection: some View {
        Section {
            VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                Text("Business Rules")
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))

                TextEditor(text: $businessRules)
                    .font(SautaiFont.body)
                    .frame(minHeight: 100)
                    .scrollContentBackground(.hidden)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadiusS)
                    .overlay(
                        RoundedRectangle(cornerRadius: SautaiDesign.cornerRadiusS)
                            .stroke(Color.sautai.lightBorder, lineWidth: 1)
                    )
            }
            .padding(.vertical, SautaiDesign.spacingXS)
        } header: {
            Text("Business Context")
        } footer: {
            Text("Add any business rules, pricing guidelines, or constraints that Sous Chef should know about.")
        }
    }

    // MARK: - Data Section

    private var dataSection: some View {
        Section {
            Toggle(isOn: $includeAnalytics) {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                    Text("Include Analytics")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)

                    Text("Share order stats and trends with Sous Chef")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }

            Toggle(isOn: $includeSeasonal) {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                    Text("Seasonal Awareness")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)

                    Text("Consider seasonal ingredients and holidays")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }

            Toggle(isOn: $autoMemorySave) {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                    Text("Auto-save Memories")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile)

                    Text("Let Sous Chef remember important details")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }
        } header: {
            Text("Data & Learning")
        } footer: {
            Text("Control what data Sous Chef can access and remember.")
        }
        .tint(.sautai.herbGreen)
    }

    // MARK: - Computed Properties

    private var hasChanges: Bool {
        soulPrompt != (settings.soulPrompt ?? "") ||
        businessRules != (settings.businessRules ?? "") ||
        chefNickname != (settings.chefNickname ?? "") ||
        sousChefName != (settings.sousChefName ?? "") ||
        includeAnalytics != (settings.includeAnalytics ?? true) ||
        includeSeasonal != (settings.includeSeasonal ?? true) ||
        autoMemorySave != (settings.autoMemorySave ?? true)
    }

    // MARK: - Actions

    private func loadSettings() async {
        isLoading = true
        do {
            settings = try await APIClient.shared.getWorkspaceSettings()
            // Update local state
            soulPrompt = settings.soulPrompt ?? ""
            businessRules = settings.businessRules ?? ""
            chefNickname = settings.chefNickname ?? ""
            sousChefName = settings.sousChefName ?? ""
            includeAnalytics = settings.includeAnalytics ?? true
            includeSeasonal = settings.includeSeasonal ?? true
            autoMemorySave = settings.autoMemorySave ?? true
        } catch {
            self.error = error
            showError = true
        }
        isLoading = false
    }

    private func saveSettings() async {
        isSaving = true
        do {
            let updatedSettings = WorkspaceSettings(
                soulPrompt: soulPrompt.isEmpty ? nil : soulPrompt,
                businessRules: businessRules.isEmpty ? nil : businessRules,
                includeAnalytics: includeAnalytics,
                includeSeasonal: includeSeasonal,
                autoMemorySave: autoMemorySave,
                chefNickname: chefNickname.isEmpty ? nil : chefNickname,
                sousChefName: sousChefName.isEmpty ? nil : sousChefName
            )
            settings = try await APIClient.shared.updateWorkspaceSettings(data: updatedSettings)

            // Show success toast
            withAnimation {
                showSaveSuccess = true
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                withAnimation {
                    showSaveSuccess = false
                }
            }
        } catch {
            self.error = error
            showError = true
        }
        isSaving = false
    }
}

// MARK: - Save Success Toast

struct SaveSuccessToast: View {
    var body: some View {
        VStack {
            HStack(spacing: SautaiDesign.spacingS) {
                Image(systemName: "checkmark.circle.fill")
                    .foregroundColor(.sautai.success)

                Text("Settings saved")
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)
            }
            .padding(SautaiDesign.spacing)
            .background(
                RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                    .fill(Color.white)
                    .shadow(color: .black.opacity(0.1), radius: 10, y: 5)
            )
            .padding(.top, SautaiDesign.spacingL)

            Spacer()
        }
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        WorkspaceSettingsView()
    }
}

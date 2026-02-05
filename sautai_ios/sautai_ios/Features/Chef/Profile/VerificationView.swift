//
//  VerificationView.swift
//  sautai_ios
//
//  Chef verification status and document management.
//

import SwiftUI

struct VerificationView: View {
    @State private var verificationStatus: VerificationStatus?
    @State private var documents: [VerificationDocument] = []
    @State private var isLoading = true
    @State private var error: Error?
    @State private var showingScheduleMeeting = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    if isLoading {
                        loadingView
                    } else if let error = error {
                        errorView(error)
                    } else {
                        // Verification Status Card
                        if let status = verificationStatus {
                            statusCard(status)
                        }

                        // Documents Section
                        documentsSection

                        // Meeting Section
                        if let status = verificationStatus {
                            meetingSection(status)
                        }
                    }
                }
                .padding(SautaiDesign.spacing)
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Verification")
            .sheet(isPresented: $showingScheduleMeeting) {
                ScheduleMeetingView { meeting in
                    verificationStatus?.upcomingMeeting = meeting
                }
            }
            .refreshable {
                await loadData()
            }
        }
        .task {
            await loadData()
        }
    }

    // MARK: - Status Card

    private func statusCard(_ status: VerificationStatus) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            // Status Icon
            ZStack {
                Circle()
                    .fill(statusColor(status).opacity(0.15))
                    .frame(width: 80, height: 80)

                Image(systemName: statusIcon(status))
                    .font(.system(size: 36))
                    .foregroundColor(statusColor(status))
            }

            // Status Text
            VStack(spacing: SautaiDesign.spacingXS) {
                Text(statusTitle(status))
                    .font(SautaiFont.title2)
                    .foregroundColor(.sautai.slateTile)

                Text(statusSubtitle(status))
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
                    .multilineTextAlignment(.center)
            }

            // Progress Bar
            if !status.isVerified {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    HStack {
                        Text("Verification Progress")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                        Spacer()
                        Text("\(completedSteps(status))/\(totalSteps)")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }

                    GeometryReader { geometry in
                        ZStack(alignment: .leading) {
                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.sautai.slateTile.opacity(0.1))

                            RoundedRectangle(cornerRadius: 4)
                                .fill(Color.sautai.herbGreen)
                                .frame(width: geometry.size.width * progress(status))
                        }
                    }
                    .frame(height: 8)
                }
                .padding(.top, SautaiDesign.spacingM)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private var totalSteps: Int { 3 }

    private func completedSteps(_ status: VerificationStatus) -> Int {
        var count = 0
        if status.documentsSubmitted { count += 1 }
        if status.documentsApproved { count += 1 }
        if status.meetingCompleted { count += 1 }
        return count
    }

    private func progress(_ status: VerificationStatus) -> Double {
        Double(completedSteps(status)) / Double(totalSteps)
    }

    private func statusColor(_ status: VerificationStatus) -> Color {
        if status.isVerified {
            return .sautai.success
        } else if status.isPending {
            return .sautai.warning
        } else {
            return .sautai.slateTile
        }
    }

    private func statusIcon(_ status: VerificationStatus) -> String {
        if status.isVerified {
            return "checkmark.seal.fill"
        } else if status.isPending {
            return "clock.fill"
        } else {
            return "doc.text.magnifyingglass"
        }
    }

    private func statusTitle(_ status: VerificationStatus) -> String {
        if status.isVerified {
            return "Verified Chef"
        } else if status.isPending {
            return "Verification Pending"
        } else {
            return "Not Yet Verified"
        }
    }

    private func statusSubtitle(_ status: VerificationStatus) -> String {
        if status.isVerified {
            return "Your profile is verified and trusted by customers."
        } else if status.isPending {
            return "Your verification is being reviewed. We'll notify you when complete."
        } else {
            return "Complete the steps below to become a verified chef."
        }
    }

    // MARK: - Documents Section

    private var documentsSection: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("Required Documents")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(DocumentType.allCases, id: \.self) { docType in
                let doc = documents.first { $0.documentType == docType }
                DocumentRow(documentType: docType, document: doc)
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    // MARK: - Meeting Section

    private func meetingSection(_ status: VerificationStatus) -> some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            HStack {
                Text("Verification Meeting")
                    .font(SautaiFont.headline)
                    .foregroundColor(.sautai.slateTile)

                Spacer()

                if status.meetingCompleted {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.sautai.success)
                }
            }

            if let meeting = status.upcomingMeeting {
                // Show scheduled meeting
                VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                    HStack {
                        Image(systemName: "calendar")
                            .foregroundColor(.sautai.earthenClay)

                        Text(meeting.scheduledDate.formatted(date: .abbreviated, time: .shortened))
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile)
                    }

                    HStack(spacing: 4) {
                        Circle()
                            .fill(meetingStatusColor(meeting.status))
                            .frame(width: 8, height: 8)

                        Text(meeting.status.displayName)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                    }

                    if let notes = meeting.notes, !notes.isEmpty {
                        Text(notes)
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.7))
                            .padding(SautaiDesign.spacingS)
                            .background(Color.sautai.softCream)
                            .cornerRadius(SautaiDesign.cornerRadiusS)
                    }
                }
                .padding(SautaiDesign.spacingM)
                .background(Color.sautai.herbGreen.opacity(0.05))
                .cornerRadius(SautaiDesign.cornerRadiusS)
            } else if status.meetingCompleted {
                // Meeting completed
                HStack {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.sautai.success)
                    Text("Meeting completed")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            } else if status.documentsApproved {
                // Ready to schedule
                VStack(spacing: SautaiDesign.spacingM) {
                    Text("Your documents have been approved! Schedule a brief video meeting to complete verification.")
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.8))

                    Button {
                        showingScheduleMeeting = true
                    } label: {
                        Label("Schedule Meeting", systemImage: "calendar.badge.plus")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.sautai.earthenClay)
                }
            } else {
                // Not ready yet
                HStack {
                    Image(systemName: "lock.fill")
                        .foregroundColor(.sautai.slateTile.opacity(0.3))
                    Text("Submit and get documents approved first")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func meetingStatusColor(_ status: MeetingStatus) -> Color {
        switch status {
        case .scheduled: return .sautai.info
        case .confirmed: return .sautai.herbGreen
        case .completed: return .sautai.success
        case .cancelled: return .sautai.danger
        case .noShow: return .sautai.warning
        }
    }

    // MARK: - Loading & Error

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

            Text("Failed to load verification status")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))

            Button("Try Again") {
                Task { await loadData() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .padding()
    }

    // MARK: - Load Data

    private func loadData() async {
        isLoading = true
        error = nil

        do {
            async let statusTask = APIClient.shared.getVerificationStatus()
            async let docsTask = APIClient.shared.getVerificationDocuments()

            let (statusResult, docsResult) = try await (statusTask, docsTask)
            verificationStatus = statusResult
            documents = docsResult
        } catch {
            self.error = error
        }

        isLoading = false
    }
}

// MARK: - Document Row

struct DocumentRow: View {
    let documentType: DocumentType
    let document: VerificationDocument?

    var body: some View {
        HStack {
            // Icon
            ZStack {
                RoundedRectangle(cornerRadius: SautaiDesign.cornerRadiusS)
                    .fill(statusColor.opacity(0.1))
                    .frame(width: 44, height: 44)

                Image(systemName: statusIcon)
                    .foregroundColor(statusColor)
            }

            // Info
            VStack(alignment: .leading, spacing: 2) {
                Text(documentType.displayName)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)

                Text(statusText)
                    .font(SautaiFont.caption)
                    .foregroundColor(statusColor)
            }

            Spacer()

            // Action
            if document == nil {
                Button {
                    // TODO: Upload document
                } label: {
                    Text("Upload")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.earthenClay)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingS)
                        .background(Color.sautai.earthenClay.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                }
            } else if document?.status == .rejected {
                Button {
                    // TODO: Re-upload document
                } label: {
                    Text("Re-upload")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.danger)
                        .padding(.horizontal, SautaiDesign.spacingM)
                        .padding(.vertical, SautaiDesign.spacingS)
                        .background(Color.sautai.danger.opacity(0.1))
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                }
            }
        }
        .padding(SautaiDesign.spacingM)
        .background(Color.sautai.softCream)
        .cornerRadius(SautaiDesign.cornerRadiusS)
    }

    private var statusColor: Color {
        guard let doc = document else { return .sautai.slateTile.opacity(0.5) }
        switch doc.status {
        case .pending: return .sautai.warning
        case .approved: return .sautai.success
        case .rejected: return .sautai.danger
        case .expired: return .sautai.warning
        }
    }

    private var statusIcon: String {
        guard let doc = document else { return "doc.badge.plus" }
        switch doc.status {
        case .pending: return "clock"
        case .approved: return "checkmark.circle.fill"
        case .rejected: return "xmark.circle.fill"
        case .expired: return "exclamationmark.triangle.fill"
        }
    }

    private var statusText: String {
        guard let doc = document else { return "Not uploaded" }
        switch doc.status {
        case .pending: return "Under review"
        case .approved:
            if let expiry = doc.expiryDate {
                let days = Calendar.current.dateComponents([.day], from: Date(), to: expiry).day ?? 0
                if days <= 30 {
                    return "Expires in \(days) days"
                }
            }
            return "Approved"
        case .rejected: return doc.rejectionReason ?? "Rejected"
        case .expired: return "Expired - please re-upload"
        }
    }
}

// MARK: - Schedule Meeting View

struct ScheduleMeetingView: View {
    @Environment(\.dismiss) var dismiss
    let onScheduled: (VerificationMeeting) -> Void

    @State private var selectedDate = Date()
    @State private var notes = ""
    @State private var isScheduling = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("Select Date & Time") {
                    DatePicker(
                        "Meeting Time",
                        selection: $selectedDate,
                        in: Date()...,
                        displayedComponents: [.date, .hourAndMinute]
                    )
                }

                Section("Notes (Optional)") {
                    TextField("Any notes for the meeting...", text: $notes, axis: .vertical)
                        .lineLimit(2...4)
                }

                Section {
                    VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                        Label("Video call via Zoom", systemImage: "video")
                        Label("Takes about 15-20 minutes", systemImage: "clock")
                        Label("Have your documents ready", systemImage: "doc.text")
                    }
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                if let error = errorMessage {
                    Section {
                        Text(error)
                            .foregroundColor(.sautai.danger)
                    }
                }
            }
            .navigationTitle("Schedule Meeting")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Schedule") {
                        scheduleMeeting()
                    }
                    .disabled(isScheduling)
                }
            }
        }
    }

    private func scheduleMeeting() {
        isScheduling = true
        errorMessage = nil

        Task {
            do {
                let meeting = try await APIClient.shared.scheduleVerificationMeeting(
                    date: selectedDate,
                    notes: notes.isEmpty ? nil : notes
                )
                await MainActor.run {
                    onScheduled(meeting)
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isScheduling = false
                }
            }
        }
    }
}

#Preview {
    VerificationView()
}

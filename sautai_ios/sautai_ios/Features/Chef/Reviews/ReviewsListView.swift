//
//  ReviewsListView.swift
//  sautai_ios
//
//  Chef reviews list with summary and reply functionality.
//

import SwiftUI

struct ReviewsListView: View {
    @State private var reviews: [Review] = []
    @State private var summary: ReviewSummary?
    @State private var isLoading = true
    @State private var error: Error?
    @State private var selectedReview: Review?
    @State private var showingReplySheet = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: SautaiDesign.spacingL) {
                    if isLoading {
                        loadingView
                    } else if let error = error {
                        errorView(error)
                    } else {
                        // Summary Card
                        if let summary = summary {
                            summaryCard(summary)
                        }

                        // Reviews List
                        if reviews.isEmpty {
                            emptyStateView
                        } else {
                            reviewsList
                        }
                    }
                }
                .padding(SautaiDesign.spacing)
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Reviews")
            .refreshable {
                await loadData()
            }
            .sheet(isPresented: $showingReplySheet) {
                if let review = selectedReview {
                    ReplyToReviewSheet(review: review) {
                        Task { await loadData() }
                    }
                }
            }
        }
        .task {
            await loadData()
        }
    }

    // MARK: - Summary Card

    private func summaryCard(_ summary: ReviewSummary) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            HStack(spacing: SautaiDesign.spacingL) {
                // Average Rating
                VStack(spacing: SautaiDesign.spacingXS) {
                    Text(String(format: "%.1f", summary.averageRating))
                        .font(.system(size: 48, weight: .bold))
                        .foregroundColor(.sautai.slateTile)

                    HStack(spacing: 2) {
                        ForEach(0..<5, id: \.self) { index in
                            Image(systemName: starImage(for: index, rating: summary.averageRating))
                                .font(.system(size: 14))
                                .foregroundColor(.sautai.sunlitApricot)
                        }
                    }

                    Text("\(summary.totalReviews) review\(summary.totalReviews == 1 ? "" : "s")")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }

                Divider()
                    .frame(height: 80)

                // Rating Breakdown
                VStack(alignment: .leading, spacing: SautaiDesign.spacingXS) {
                    ratingBar(label: "5", count: summary.fiveStarCount, total: summary.totalReviews)
                    ratingBar(label: "4", count: summary.fourStarCount, total: summary.totalReviews)
                    ratingBar(label: "3", count: summary.threeStarCount, total: summary.totalReviews)
                    ratingBar(label: "2", count: summary.twoStarCount, total: summary.totalReviews)
                    ratingBar(label: "1", count: summary.oneStarCount, total: summary.totalReviews)
                }
            }

            if summary.pendingResponseCount > 0 {
                Divider()

                HStack {
                    Image(systemName: "exclamationmark.bubble")
                        .foregroundColor(.sautai.warning)
                    Text("\(summary.pendingResponseCount) review\(summary.pendingResponseCount == 1 ? "" : "s") awaiting response")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.warning)
                    Spacer()
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }

    private func ratingBar(label: String, count: Int, total: Int) -> some View {
        HStack(spacing: SautaiDesign.spacingS) {
            HStack(spacing: 2) {
                Text(label)
                    .font(SautaiFont.caption)
                    .foregroundColor(.sautai.slateTile)
                Image(systemName: "star.fill")
                    .font(.system(size: 10))
                    .foregroundColor(.sautai.sunlitApricot)
            }
            .frame(width: 30, alignment: .trailing)

            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.sautai.slateTile.opacity(0.1))

                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.sautai.sunlitApricot)
                        .frame(width: total > 0 ? geometry.size.width * CGFloat(count) / CGFloat(total) : 0)
                }
            }
            .frame(height: 8)

            Text("\(count)")
                .font(SautaiFont.caption2)
                .foregroundColor(.sautai.slateTile.opacity(0.6))
                .frame(width: 24, alignment: .trailing)
        }
    }

    private func starImage(for index: Int, rating: Double) -> String {
        let threshold = Double(index) + 0.5
        if rating >= Double(index + 1) {
            return "star.fill"
        } else if rating >= threshold {
            return "star.leadinghalf.filled"
        } else {
            return "star"
        }
    }

    // MARK: - Reviews List

    private var reviewsList: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            Text("All Reviews")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            ForEach(reviews) { review in
                ReviewRowView(review: review) {
                    selectedReview = review
                    showingReplySheet = true
                }
            }
        }
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack {
            Spacer()
            ProgressView()
                .scaleEffect(1.5)
            Spacer()
        }
        .frame(maxWidth: .infinity, minHeight: 300)
    }

    // MARK: - Error View

    private func errorView(_ error: Error) -> some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundColor(.sautai.warning)

            Text("Failed to load reviews")
                .font(SautaiFont.headline)

            Text(error.localizedDescription)
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)

            Button("Try Again") {
                Task { await loadData() }
            }
            .buttonStyle(.borderedProminent)
            .tint(.sautai.earthenClay)
        }
        .padding()
    }

    // MARK: - Empty State

    private var emptyStateView: some View {
        VStack(spacing: SautaiDesign.spacingM) {
            Image(systemName: "star.bubble")
                .font(.system(size: 64))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No Reviews Yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Reviews will appear here once customers rate your services.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(SautaiDesign.spacingXL)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    // MARK: - Load Data

    private func loadData() async {
        isLoading = true
        error = nil

        do {
            async let reviewsTask = APIClient.shared.getMyReviews()
            async let summaryTask = APIClient.shared.getReviewSummary()

            let (reviewsResponse, summaryResult) = try await (reviewsTask, summaryTask)
            reviews = reviewsResponse.results
            summary = summaryResult
        } catch {
            self.error = error
        }

        isLoading = false
    }
}

// MARK: - Review Row View

struct ReviewRowView: View {
    let review: Review
    let onReply: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
            // Header
            HStack {
                // Customer Avatar
                Circle()
                    .fill(Color.sautai.earthenClay.opacity(0.15))
                    .frame(width: 40, height: 40)
                    .overlay(
                        Text(String(review.customerName.prefix(1)).uppercased())
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.earthenClay)
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text(review.customerName)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    Text(review.timeAgo)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.6))
                }

                Spacer()

                // Rating Stars
                HStack(spacing: 2) {
                    ForEach(0..<5, id: \.self) { index in
                        Image(systemName: index < review.rating ? "star.fill" : "star")
                            .font(.system(size: 12))
                            .foregroundColor(.sautai.sunlitApricot)
                    }
                }
            }

            // Review Text
            if let comment = review.comment, !comment.isEmpty {
                Text(comment)
                    .font(SautaiFont.body)
                    .foregroundColor(.sautai.slateTile)
                    .lineLimit(4)
            }

            // Service Info
            if let serviceName = review.serviceName {
                HStack {
                    Image(systemName: "fork.knife")
                        .font(.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.5))
                    Text(serviceName)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                }
            }

            // Response or Reply Button
            if let response = review.response {
                VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                    Text("Your Response")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.herbGreen)

                    Text(response.content)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.8))
                        .padding(SautaiDesign.spacingM)
                        .background(Color.sautai.herbGreen.opacity(0.05))
                        .cornerRadius(SautaiDesign.cornerRadiusS)
                }
            } else {
                Button {
                    onReply()
                } label: {
                    Label("Reply to Review", systemImage: "arrowshape.turn.up.left")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.earthenClay)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
        .sautaiShadow(SautaiDesign.shadowSubtle)
    }
}

// MARK: - Reply to Review Sheet

struct ReplyToReviewSheet: View {
    @Environment(\.dismiss) var dismiss
    let review: Review
    let onReplied: () -> Void

    @State private var replyText = ""
    @State private var isSending = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: SautaiDesign.spacingL) {
                // Original Review
                VStack(alignment: .leading, spacing: SautaiDesign.spacingM) {
                    HStack {
                        Text(review.customerName)
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.slateTile)

                        Spacer()

                        HStack(spacing: 2) {
                            ForEach(0..<5, id: \.self) { index in
                                Image(systemName: index < review.rating ? "star.fill" : "star")
                                    .font(.system(size: 12))
                                    .foregroundColor(.sautai.sunlitApricot)
                            }
                        }
                    }

                    if let comment = review.comment, !comment.isEmpty {
                        Text(comment)
                            .font(SautaiFont.body)
                            .foregroundColor(.sautai.slateTile.opacity(0.8))
                    }
                }
                .padding(SautaiDesign.spacing)
                .background(Color.sautai.softCream)
                .cornerRadius(SautaiDesign.cornerRadius)

                // Reply Input
                VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                    Text("Your Response")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile)

                    TextEditor(text: $replyText)
                        .font(SautaiFont.body)
                        .frame(minHeight: 150)
                        .padding(SautaiDesign.spacingS)
                        .background(Color.white)
                        .cornerRadius(SautaiDesign.cornerRadius)
                        .overlay(
                            RoundedRectangle(cornerRadius: SautaiDesign.cornerRadius)
                                .stroke(Color.sautai.lightBorder, lineWidth: 1)
                        )
                }

                if let error = errorMessage {
                    Text(error)
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.danger)
                }

                Spacer()
            }
            .padding(SautaiDesign.spacing)
            .navigationTitle("Reply to Review")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Send") {
                        sendReply()
                    }
                    .disabled(replyText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isSending)
                }
            }
        }
    }

    private func sendReply() {
        isSending = true
        errorMessage = nil

        Task {
            do {
                _ = try await APIClient.shared.replyToReview(
                    reviewId: review.id,
                    content: replyText.trimmingCharacters(in: .whitespacesAndNewlines)
                )
                await MainActor.run {
                    onReplied()
                    dismiss()
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isSending = false
                }
            }
        }
    }
}

#Preview {
    ReviewsListView()
}

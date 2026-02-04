//
//  ConversationsListView.swift
//  sautai_ios
//
//  List of all conversations for messaging.
//

import SwiftUI

struct ConversationsListView: View {
    @State private var conversations: [Conversation] = []
    @State private var isLoading = true
    @State private var error: Error?

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    loadingView
                } else if conversations.isEmpty {
                    emptyView
                } else {
                    conversationsList
                }
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Messages")
            .refreshable {
                await loadConversations()
            }
        }
        .task {
            await loadConversations()
        }
    }

    // MARK: - Conversations List

    private var conversationsList: some View {
        List {
            ForEach(conversations) { conversation in
                NavigationLink {
                    ChatView(conversation: conversation)
                } label: {
                    ConversationRowView(conversation: conversation)
                }
                .listRowBackground(Color.white)
                .listRowSeparator(.hidden)
                .listRowInsets(EdgeInsets(
                    top: SautaiDesign.spacingXS,
                    leading: SautaiDesign.spacing,
                    bottom: SautaiDesign.spacingXS,
                    trailing: SautaiDesign.spacing
                ))
            }
        }
        .listStyle(.plain)
    }

    // MARK: - Loading View

    private var loadingView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            ProgressView()
            Text("Loading messages...")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
        }
    }

    // MARK: - Empty View

    private var emptyView: some View {
        VStack(spacing: SautaiDesign.spacingL) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 60))
                .foregroundColor(.sautai.slateTile.opacity(0.3))

            Text("No messages yet")
                .font(SautaiFont.headline)
                .foregroundColor(.sautai.slateTile)

            Text("Start a conversation with a chef to discuss meal plans, dietary needs, and more.")
                .font(SautaiFont.body)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .multilineTextAlignment(.center)
                .padding(.horizontal, SautaiDesign.spacingXL)

            NavigationLink {
                ChefDiscoveryView()
            } label: {
                Text("Find a Chef")
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .padding(.horizontal, SautaiDesign.spacingXL)
                    .padding(.vertical, SautaiDesign.spacingM)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
            }
        }
        .padding()
    }

    // MARK: - Data Loading

    private func loadConversations() async {
        isLoading = true
        do {
            conversations = try await APIClient.shared.getConversations()
        } catch {
            self.error = error
        }
        isLoading = false
    }
}

// MARK: - Conversation Row View

struct ConversationRowView: View {
    let conversation: Conversation

    var body: some View {
        HStack(spacing: SautaiDesign.spacingM) {
            // Avatar
            ZStack(alignment: .topTrailing) {
                Circle()
                    .fill(Color.sautai.earthenClay.opacity(0.2))
                    .frame(width: SautaiDesign.avatarSizeL, height: SautaiDesign.avatarSizeL)
                    .overlay(
                        Text(String(conversation.otherUserName.prefix(1)).uppercased())
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.earthenClay)
                    )

                // Unread badge
                if conversation.hasUnread {
                    Circle()
                        .fill(Color.sautai.danger)
                        .frame(width: 18, height: 18)
                        .overlay(
                            Text("\(min(conversation.unreadCount, 99))")
                                .font(SautaiFont.caption2)
                                .foregroundColor(.white)
                        )
                        .offset(x: 4, y: -4)
                }
            }

            // Content
            VStack(alignment: .leading, spacing: SautaiDesign.spacingXXS) {
                HStack {
                    Text(conversation.otherUserName)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)
                        .lineLimit(1)

                    Spacer()

                    if let date = conversation.lastMessageAt {
                        Text(formatDate(date))
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.slateTile.opacity(0.5))
                    }
                }

                if let lastMessage = conversation.lastMessage {
                    Text(lastMessage)
                        .font(SautaiFont.body)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))
                        .lineLimit(2)
                }
            }
        }
        .padding(SautaiDesign.spacing)
        .background(Color.white)
        .cornerRadius(SautaiDesign.cornerRadius)
    }

    private func formatDate(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            let formatter = DateFormatter()
            formatter.dateFormat = "h:mm a"
            return formatter.string(from: date)
        } else if calendar.isDateInYesterday(date) {
            return "Yesterday"
        } else {
            let formatter = DateFormatter()
            formatter.dateFormat = "MMM d"
            return formatter.string(from: date)
        }
    }
}

// MARK: - Preview

#Preview {
    ConversationsListView()
}

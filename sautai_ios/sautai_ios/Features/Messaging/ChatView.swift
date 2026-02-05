//
//  ChatView.swift
//  sautai_ios
//
//  Real-time chat interface between customer and chef.
//

import SwiftUI

struct ChatView: View {
    let conversation: Conversation

    @State private var messages: [Message] = []
    @State private var inputText = ""
    @State private var isLoading = true
    @State private var isSending = false
    @FocusState private var isInputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Messages
            messagesView

            // Input
            inputView
        }
        .background(Color.sautai.softCream)
        .navigationTitle(conversation.otherUserName)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .principal) {
                VStack(spacing: 0) {
                    Text(conversation.otherUserName)
                        .font(SautaiFont.headline)
                        .foregroundColor(.sautai.slateTile)

                    if conversation.isChefConversation == true {
                        Text("Chef")
                            .font(SautaiFont.caption2)
                            .foregroundColor(.sautai.herbGreen)
                    }
                }
            }
        }
        .task {
            await loadMessages()
            await markAsRead()
        }
    }

    // MARK: - Messages View

    private var messagesView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: SautaiDesign.spacingS) {
                    if isLoading {
                        ProgressView()
                            .padding()
                    }

                    ForEach(messages) { message in
                        ChatMessageBubble(message: message)
                            .id(message.id)
                    }
                }
                .padding(SautaiDesign.spacing)
            }
            .onChange(of: messages.count) { _, _ in
                if let lastMessage = messages.last {
                    withAnimation {
                        proxy.scrollTo(lastMessage.id, anchor: .bottom)
                    }
                }
            }
        }
    }

    // MARK: - Input View

    private var inputView: some View {
        VStack(spacing: 0) {
            Divider()

            HStack(spacing: SautaiDesign.spacingM) {
                // Text field
                TextField("Type a message...", text: $inputText, axis: .vertical)
                    .font(SautaiFont.body)
                    .lineLimit(1...5)
                    .padding(SautaiDesign.spacingM)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadius)
                    .focused($isInputFocused)

                // Send button
                Button {
                    Task { await sendMessage() }
                } label: {
                    if isSending {
                        ProgressView()
                            .frame(width: 32, height: 32)
                    } else {
                        Image(systemName: "arrow.up.circle.fill")
                            .font(.system(size: 32))
                            .foregroundColor(canSend ? .sautai.earthenClay : .sautai.slateTile.opacity(0.3))
                    }
                }
                .disabled(!canSend || isSending)
            }
            .padding(SautaiDesign.spacing)
            .background(Color.sautai.softCream)
        }
    }

    private var canSend: Bool {
        !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    // MARK: - Actions

    private func loadMessages() async {
        isLoading = true
        do {
            let response = try await APIClient.shared.getConversationMessages(conversationId: conversation.id)
            messages = response.results
        } catch {
            // Handle error
        }
        isLoading = false
    }

    private func markAsRead() async {
        try? await APIClient.shared.markConversationRead(conversationId: conversation.id)
    }

    private func sendMessage() async {
        guard canSend else { return }

        let content = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        inputText = ""
        isSending = true

        // Optimistically add message
        let tempMessage = Message(
            id: Int.random(in: 100000...999999),
            conversationId: conversation.id,
            senderId: 0,
            senderName: "You",
            content: content,
            createdAt: Date(),
            readAt: nil,
            isFromCurrentUser: true
        )
        messages.append(tempMessage)

        do {
            let sentMessage = try await APIClient.shared.sendMessage(
                conversationId: conversation.id,
                content: content
            )
            // Replace temp message with real one
            if let index = messages.firstIndex(where: { $0.id == tempMessage.id }) {
                messages[index] = sentMessage
            }
        } catch {
            // Remove temp message on error
            messages.removeAll { $0.id == tempMessage.id }
        }

        isSending = false
    }
}

// MARK: - Chat Message Bubble

struct ChatMessageBubble: View {
    let message: Message

    var isFromMe: Bool {
        message.isFromCurrentUser ?? false
    }

    var body: some View {
        HStack {
            if isFromMe { Spacer(minLength: 60) }

            VStack(alignment: isFromMe ? .trailing : .leading, spacing: SautaiDesign.spacingXXS) {
                Text(message.content)
                    .font(SautaiFont.body)
                    .foregroundColor(isFromMe ? .white : .sautai.slateTile)
                    .padding(SautaiDesign.spacingM)
                    .background(isFromMe ? Color.sautai.earthenClay : Color.white)
                    .cornerRadius(SautaiDesign.cornerRadius)

                // Timestamp
                Text(formatTime(message.createdAt))
                    .font(SautaiFont.caption2)
                    .foregroundColor(.sautai.slateTile.opacity(0.5))
            }

            if !isFromMe { Spacer(minLength: 60) }
        }
    }

    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h:mm a"
        return formatter.string(from: date)
    }
}

// MARK: - New Message Sheet

struct NewMessageSheet: View {
    @Environment(\.dismiss) private var dismiss
    let chef: ChefProfileDetail

    @State private var messageText = ""
    @State private var isSending = false
    @State private var error: Error?

    var body: some View {
        NavigationStack {
            VStack(spacing: SautaiDesign.spacingL) {
                // Chef info
                HStack(spacing: SautaiDesign.spacingM) {
                    Circle()
                        .fill(Color.sautai.earthenClay.opacity(0.2))
                        .frame(width: 50, height: 50)
                        .overlay(
                            Text(String(chef.displayName.prefix(1)).uppercased())
                                .font(SautaiFont.headline)
                                .foregroundColor(.sautai.earthenClay)
                        )

                    VStack(alignment: .leading) {
                        Text(chef.displayName)
                            .font(SautaiFont.headline)
                            .foregroundColor(.sautai.slateTile)

                        Text("Chef")
                            .font(SautaiFont.caption)
                            .foregroundColor(.sautai.herbGreen)
                    }

                    Spacer()
                }
                .padding(SautaiDesign.spacing)
                .background(Color.white)
                .cornerRadius(SautaiDesign.cornerRadius)

                // Message input
                VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                    Text("Your message")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile)

                    TextEditor(text: $messageText)
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

                // Suggestions
                VStack(alignment: .leading, spacing: SautaiDesign.spacingS) {
                    Text("Quick starts")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile.opacity(0.7))

                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(spacing: SautaiDesign.spacingS) {
                            quickStartChip("I'm interested in meal prep services")
                            quickStartChip("What's your availability like?")
                            quickStartChip("Do you accommodate dietary restrictions?")
                        }
                    }
                }

                Spacer()

                // Send button
                Button {
                    Task { await startConversation() }
                } label: {
                    HStack {
                        if isSending {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Image(systemName: "paperplane.fill")
                            Text("Send Message")
                        }
                    }
                    .font(SautaiFont.button)
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: SautaiDesign.buttonHeight)
                    .background(Color.sautai.earthenClay)
                    .cornerRadius(SautaiDesign.cornerRadius)
                }
                .disabled(messageText.isEmpty || isSending)
                .opacity(messageText.isEmpty ? 0.6 : 1)
            }
            .padding(SautaiDesign.spacing)
            .background(Color.sautai.softCream)
            .navigationTitle("New Message")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
            }
        }
    }

    private func quickStartChip(_ text: String) -> some View {
        Button {
            messageText = text
        } label: {
            Text(text)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.earthenClay)
                .padding(.horizontal, SautaiDesign.spacingM)
                .padding(.vertical, SautaiDesign.spacingS)
                .background(Color.sautai.earthenClay.opacity(0.1))
                .cornerRadius(SautaiDesign.cornerRadiusFull)
        }
    }

    private func startConversation() async {
        isSending = true
        do {
            _ = try await APIClient.shared.startConversation(
                userId: chef.id,
                message: messageText
            )
            dismiss()
        } catch {
            self.error = error
        }
        isSending = false
    }
}

// MARK: - Preview

#Preview {
    NavigationStack {
        ChatView(conversation: Conversation(
            id: 1,
            otherUserId: 2,
            otherUserName: "Chef Maria",
            otherUserAvatar: nil,
            lastMessage: "Looking forward to our session!",
            lastMessageAt: Date(),
            unreadCount: 0,
            isChefConversation: true
        ))
    }
}

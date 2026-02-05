//
//  ChatView.swift
//  sautai_ios
//
//  Real-time chat interface between customer and chef.
//  Uses WebSocket for real-time message delivery and typing indicators.
//

import SwiftUI

struct ChatView: View {
    let conversation: Conversation

    @StateObject private var webSocket = WebSocketClient.shared
    @State private var messages: [Message] = []
    @State private var inputText = ""
    @State private var isLoading = true
    @State private var isSending = false
    @State private var otherUserTyping = false
    @State private var typingDebounceTask: Task<Void, Never>?
    @FocusState private var isInputFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            // Connection status (if not connected)
            if !webSocket.connectionState.isConnected && webSocket.connectionState != .disconnected {
                connectionStatusBar
            }

            // Messages
            messagesView

            // Typing indicator
            if otherUserTyping {
                typingIndicatorView
            }

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
            await connectWebSocket()
        }
        .onDisappear {
            webSocket.disconnect()
        }
    }

    // MARK: - Connection Status Bar

    private var connectionStatusBar: some View {
        HStack(spacing: SautaiDesign.spacingS) {
            ProgressView()
                .scaleEffect(0.8)

            Text(webSocket.connectionState.description)
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile)
        }
        .padding(.vertical, SautaiDesign.spacingXS)
        .frame(maxWidth: .infinity)
        .background(Color.sautai.warning.opacity(0.2))
    }

    // MARK: - Typing Indicator

    private var typingIndicatorView: some View {
        HStack {
            Text("\(conversation.otherUserName) is typing...")
                .font(SautaiFont.caption)
                .foregroundColor(.sautai.slateTile.opacity(0.7))
                .italic()

            TypingDotsAnimation()
        }
        .padding(.horizontal, SautaiDesign.spacing)
        .padding(.vertical, SautaiDesign.spacingXS)
        .frame(maxWidth: .infinity, alignment: .leading)
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
                    .onChange(of: inputText) { _, newValue in
                        handleTypingChange(newValue)
                    }

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

    private func connectWebSocket() async {
        // Set up callbacks before connecting
        webSocket.onMessage = { [self] message in
            // Only add if not from current user (we already added optimistically)
            if message.isFromCurrentUser != true {
                // Check if message already exists (avoid duplicates)
                if !messages.contains(where: { $0.id == message.id }) {
                    withAnimation {
                        messages.append(message)
                    }
                }
            }
        }

        webSocket.onTypingIndicator = { userId, isTyping in
            // Only show typing if it's the other user
            if userId == conversation.otherUserId {
                withAnimation {
                    otherUserTyping = isTyping
                }
            }
        }

        webSocket.onMessagesRead = { _ in
            // Could update read receipts UI here if needed
        }

        webSocket.onError = { error in
            #if DEBUG
            print("WebSocket error in ChatView: \(error.localizedDescription)")
            #endif
        }

        // Connect to the conversation
        await webSocket.connect(conversationId: conversation.id)
    }

    private func sendMessage() async {
        guard canSend else { return }

        let content = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        inputText = ""
        isSending = true

        // Stop typing indicator
        try? await webSocket.sendTyping(false)

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

        // Try WebSocket first, fall back to HTTP
        if webSocket.connectionState.isConnected {
            do {
                try await webSocket.sendMessage(content)
                // Message will be confirmed via WebSocket callback
                // For now, just mark as sent
                isSending = false
                return
            } catch {
                #if DEBUG
                print("WebSocket send failed, falling back to HTTP: \(error)")
                #endif
            }
        }

        // HTTP fallback
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

    private func handleTypingChange(_ newValue: String) {
        // Debounce typing indicator
        typingDebounceTask?.cancel()
        typingDebounceTask = Task {
            // Send typing indicator if text is not empty
            let isTyping = !newValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty

            if webSocket.connectionState.isConnected {
                try? await webSocket.sendTyping(isTyping)
            }

            // Auto-stop typing after 3 seconds of no changes
            if isTyping {
                try? await Task.sleep(nanoseconds: 3_000_000_000)
                if !Task.isCancelled && webSocket.connectionState.isConnected {
                    try? await webSocket.sendTyping(false)
                }
            }
        }
    }
}

// MARK: - Typing Dots Animation

struct TypingDotsAnimation: View {
    @State private var animationOffset = 0

    var body: some View {
        HStack(spacing: 2) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.sautai.slateTile.opacity(0.5))
                    .frame(width: 6, height: 6)
                    .offset(y: animationOffset == index ? -3 : 0)
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.4).repeatForever()) {
                animationOffset = (animationOffset + 1) % 3
            }
        }
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

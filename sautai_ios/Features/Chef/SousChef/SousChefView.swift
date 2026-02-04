//
//  SousChefView.swift
//  sautai_ios
//
//  AI assistant chat interface with real-time streaming responses.
//

import SwiftUI

struct SousChefView: View {
    @State private var messages: [SousChefMessage] = []
    @State private var inputText = ""
    @State private var isStreaming = false
    @State private var currentStreamingMessage: SousChefMessage?
    @FocusState private var isInputFocused: Bool

    // Default context for standalone conversations
    private let familyType = "chef"
    private let familyId = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Messages
                messagesView

                // Input
                inputView
            }
            .background(Color.sautai.softCream)
            .navigationTitle("Sous Chef")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .primaryAction) {
                    Button {
                        startNewConversation()
                    } label: {
                        Image(systemName: "square.and.pencil")
                            .foregroundColor(.sautai.earthenClay)
                    }
                }
            }
        }
        .onAppear {
            if messages.isEmpty {
                addWelcomeMessage()
            }
        }
    }

    // MARK: - Messages View

    private var messagesView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: SautaiDesign.spacingM) {
                    ForEach(messages) { message in
                        MessageBubbleView(message: message)
                            .id(message.id)
                    }

                    if let streaming = currentStreamingMessage {
                        MessageBubbleView(message: streaming)
                            .id(streaming.id)
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
            .onChange(of: currentStreamingMessage?.content) { _, _ in
                if let streaming = currentStreamingMessage {
                    withAnimation {
                        proxy.scrollTo(streaming.id, anchor: .bottom)
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
                TextField("Ask Sous Chef anything...", text: $inputText, axis: .vertical)
                    .font(SautaiFont.body)
                    .lineLimit(1...5)
                    .padding(SautaiDesign.spacingM)
                    .background(Color.white)
                    .cornerRadius(SautaiDesign.cornerRadius)
                    .focused($isInputFocused)

                // Send button
                Button {
                    sendMessage()
                } label: {
                    Image(systemName: isStreaming ? "stop.fill" : "arrow.up.circle.fill")
                        .font(.system(size: 32))
                        .foregroundColor(canSend ? .sautai.earthenClay : .sautai.slateTile.opacity(0.3))
                }
                .disabled(!canSend && !isStreaming)
            }
            .padding(SautaiDesign.spacing)
            .background(Color.sautai.softCream)
        }
    }

    private var canSend: Bool {
        !inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !isStreaming
    }

    // MARK: - Actions

    private func addWelcomeMessage() {
        let welcome = SousChefMessage(
            content: "Hello! I'm your Sous Chef AI assistant. I can help you with meal planning, recipe ideas, client management, and more. What would you like to work on today?",
            role: .assistant
        )
        messages.append(welcome)
    }

    private func startNewConversation() {
        messages.removeAll()
        currentStreamingMessage = nil
        isStreaming = false
        inputText = ""
        addWelcomeMessage()
    }

    private func sendMessage() {
        guard canSend else { return }

        let userMessage = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        inputText = ""
        isInputFocused = false

        // Add user message
        let userMsg = SousChefMessage(content: userMessage, role: .user)
        messages.append(userMsg)

        // Start streaming response
        isStreaming = true
        currentStreamingMessage = SousChefMessage(
            content: "",
            role: .assistant,
            isStreaming: true
        )

        Task {
            await StreamingClient.shared.streamMessage(
                message: userMessage,
                familyType: familyType,
                familyId: familyId,
                onChunk: { chunk in
                    currentStreamingMessage?.content += chunk
                },
                onComplete: {
                    if let streaming = currentStreamingMessage {
                        var finalMessage = streaming
                        finalMessage.isStreaming = false
                        messages.append(finalMessage)
                    }
                    currentStreamingMessage = nil
                    isStreaming = false
                },
                onError: { error in
                    let errorMessage = SousChefMessage(
                        content: "Sorry, I encountered an error: \(error.localizedDescription). Please try again.",
                        role: .assistant
                    )
                    messages.append(errorMessage)
                    currentStreamingMessage = nil
                    isStreaming = false
                }
            )
        }
    }
}

// MARK: - Message Bubble View

struct MessageBubbleView: View {
    let message: SousChefMessage

    var body: some View {
        HStack(alignment: .top, spacing: SautaiDesign.spacingS) {
            if message.role.isUser {
                Spacer(minLength: 60)
            }

            if message.role.isAssistant {
                // AI Avatar
                Circle()
                    .fill(Color.sautai.earthenClay.opacity(0.2))
                    .frame(width: 32, height: 32)
                    .overlay(
                        Image(systemName: "brain.head.profile")
                            .font(.system(size: 16))
                            .foregroundColor(.sautai.earthenClay)
                    )
            }

            VStack(alignment: message.role.isUser ? .trailing : .leading, spacing: SautaiDesign.spacingXS) {
                // Message content
                Text(message.content.isEmpty ? " " : message.content)
                    .font(SautaiFont.body)
                    .foregroundColor(message.role.isUser ? .white : .sautai.slateTile)
                    .padding(SautaiDesign.spacingM)
                    .background(
                        message.role.isUser
                            ? Color.sautai.earthenClay
                            : Color.white
                    )
                    .cornerRadius(SautaiDesign.cornerRadius)
                    .cornerRadius(message.role.isUser ? SautaiDesign.cornerRadius : SautaiDesign.cornerRadiusS, corners: message.role.isUser ? [.topLeft, .bottomLeft, .bottomRight] : [.topRight, .bottomLeft, .bottomRight])

                // Streaming indicator
                if message.isStreaming {
                    HStack(spacing: 4) {
                        ForEach(0..<3) { index in
                            Circle()
                                .fill(Color.sautai.earthenClay)
                                .frame(width: 6, height: 6)
                                .opacity(0.6)
                        }
                    }
                    .padding(.leading, SautaiDesign.spacingS)
                }
            }

            if message.role.isAssistant {
                Spacer(minLength: 60)
            }
        }
    }
}

// MARK: - Corner Radius Extension

extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(
            roundedRect: rect,
            byRoundingCorners: corners,
            cornerRadii: CGSize(width: radius, height: radius)
        )
        return Path(path.cgPath)
    }
}

// MARK: - Preview

#Preview {
    SousChefView()
}

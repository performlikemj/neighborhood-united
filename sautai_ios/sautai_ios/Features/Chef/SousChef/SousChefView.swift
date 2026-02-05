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
    @State private var lastError: Error?
    @State private var lastUserMessage: String?
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
                            .onAppear {
                                #if DEBUG
                                print("🔵 Message appeared in UI: \(message.role.rawValue) - \(message.content.prefix(50))...")
                                #endif
                            }
                    }

                    if let streaming = currentStreamingMessage {
                        MessageBubbleView(message: streaming)
                            .id("streaming-\(streaming.content.count)") // Use content length as part of ID to force updates
                            .onAppear {
                                #if DEBUG
                                print("🟡 Streaming message appeared in UI: \(streaming.content.prefix(50))...")
                                #endif
                            }
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
            // Retry banner when there's an error
            if lastError != nil && !isStreaming {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.sautai.warning)

                    Text("Message failed to send")
                        .font(SautaiFont.caption)
                        .foregroundColor(.sautai.slateTile)

                    Spacer()

                    Button("Retry") {
                        retryLastMessage()
                    }
                    .font(SautaiFont.caption)
                    .fontWeight(.semibold)
                    .foregroundColor(.sautai.earthenClay)
                }
                .padding(SautaiDesign.spacingS)
                .background(Color.sautai.warning.opacity(0.1))
            }

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
                    if isStreaming {
                        StreamingClient.shared.cancel()
                        isStreaming = false
                        currentStreamingMessage = nil
                    } else {
                        sendMessage()
                    }
                } label: {
                    Image(systemName: isStreaming ? "stop.fill" : "arrow.up.circle.fill")
                        .font(.system(size: 32))
                        .foregroundColor(canSend || isStreaming ? .sautai.earthenClay : .sautai.slateTile.opacity(0.3))
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
            content: """
            # Hello! 👩‍🍳
            
            I'm your **Sous Chef AI** assistant. I can help you with:
            
            • **Meal planning** - Create custom plans for your clients
            • **Recipe ideas** - Get suggestions based on dietary needs
            • **Client management** - Track preferences and allergies
            • **Order tracking** - View and manage orders
            
            What would you like to work on today?
            """,
            role: .assistant
        )
        messages.append(welcome)
    }

    private func startNewConversation() {
        // Call API to start new conversation on server
        Task {
            do {
                _ = try await APIClient.shared.startSousChefConversation()
            } catch {
                #if DEBUG
                print("⚠️ Failed to start new conversation on server: \(error.localizedDescription)")
                #endif
                // Continue with local reset even if API fails
            }
        }

        // Clear local state
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
        lastError = nil
        lastUserMessage = userMessage

        // Add user message
        let userMsg = SousChefMessage(content: userMessage, role: .user)
        messages.append(userMsg)

        streamResponse(for: userMessage)
    }

    private func streamResponse(for message: String) {
        // Start streaming response
        isStreaming = true
        currentStreamingMessage = SousChefMessage(
            content: "",
            role: .assistant,
            isStreaming: true
        )

        Task {
            await StreamingClient.shared.streamMessage(
                message: message,
                familyType: familyType,
                familyId: familyId,
                onChunk: { chunk in
                    #if DEBUG
                    print("📬 SousChefView: Received chunk - \(chunk.count) chars: \(chunk.prefix(50))...")
                    #endif
                    // Update content while preserving the message ID
                    if var streaming = currentStreamingMessage {
                        let oldContent = streaming.content
                        streaming.content += chunk
                        currentStreamingMessage = streaming
                        #if DEBUG
                        print("📝 SousChefView: Updated streaming message")
                        print("   Old length: \(oldContent.count), New length: \(streaming.content.count)")
                        print("   currentStreamingMessage is now: \(currentStreamingMessage?.content.prefix(50) ?? "")")
                        #endif
                    } else {
                        #if DEBUG
                        print("⚠️ currentStreamingMessage is nil when chunk arrived!")
                        #endif
                    }
                },
                onComplete: {
                    #if DEBUG
                    print("✅ SousChefView: Stream complete")
                    if let streaming = currentStreamingMessage {
                        print("   Final message length: \(streaming.content.count) chars")
                    }
                    #endif
                    if let streaming = currentStreamingMessage {
                        var finalMessage = streaming
                        finalMessage.isStreaming = false
                        messages.append(finalMessage)
                        #if DEBUG
                        print("   Added to messages array, total messages: \(messages.count)")
                        #endif
                    }
                    currentStreamingMessage = nil
                    isStreaming = false
                    lastError = nil
                },
                onError: { error in
                    lastError = error
                    currentStreamingMessage = nil
                    isStreaming = false

                    // Show error as a message with retry option
                    let errorMessage = SousChefMessage(
                        content: "⚠️ \(error.localizedDescription)",
                        role: .assistant
                    )
                    messages.append(errorMessage)
                }
            )
        }
    }

    private func retryLastMessage() {
        guard let message = lastUserMessage else { return }
        // Remove the last error message
        if let lastMessage = messages.last, lastMessage.content.hasPrefix("⚠️") {
            messages.removeLast()
        }
        streamResponse(for: message)
    }
}

// MARK: - Message Bubble View

struct MessageBubbleView: View {
    let message: SousChefMessage

    var body: some View {
        #if DEBUG
        let _ = print("🎨 MessageBubbleView rendering: role=\(message.role.rawValue), streaming=\(message.isStreaming), contentLength=\(message.content.count), isEmpty=\(message.content.isEmpty)")
        #endif
        
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
                Group {
                    if message.content.isEmpty && message.isStreaming {
                        HStack(spacing: SautaiDesign.spacingS) {
                            Text("Thinking")
                                .font(SautaiFont.body)
                                .foregroundColor(.sautai.slateTile.opacity(0.6))
                                .italic()
                            TypingIndicator()
                        }
                    } else {
                        // Render Markdown with proper formatting
                        if let attributedString = try? AttributedString(markdown: message.content) {
                            Text(attributedString)
                                .font(SautaiFont.body)
                                .foregroundColor(message.role.isUser ? .white : .sautai.slateTile)
                                .multilineTextAlignment(message.role.isUser ? .trailing : .leading)
                        } else {
                            // Fallback to plain text
                            Text(message.content)
                                .font(SautaiFont.body)
                                .foregroundColor(message.role.isUser ? .white : .sautai.slateTile)
                                .multilineTextAlignment(message.role.isUser ? .trailing : .leading)
                        }
                    }
                }
                .padding(SautaiDesign.spacingM)
                .background(
                    message.role.isUser
                        ? Color.sautai.earthenClay
                        : Color.white
                )
                .cornerRadius(SautaiDesign.cornerRadius)
                .cornerRadius(message.role.isUser ? SautaiDesign.cornerRadius : SautaiDesign.cornerRadiusS, corners: message.role.isUser ? [.topLeft, .bottomLeft, .bottomRight] : [.topRight, .bottomLeft, .bottomRight])
            }

            if message.role.isAssistant {
                Spacer(minLength: 60)
            }
        }
    }
}

// MARK: - Typing Indicator

struct TypingIndicator: View {
    @State private var animatingDot = 0

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<3) { index in
                Circle()
                    .fill(Color.sautai.earthenClay)
                    .frame(width: 8, height: 8)
                    .scaleEffect(animatingDot == index ? 1.2 : 0.8)
                    .opacity(animatingDot == index ? 1.0 : 0.4)
            }
        }
        .onAppear {
            startAnimation()
        }
    }

    private func startAnimation() {
        Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { timer in
            withAnimation(.easeInOut(duration: 0.3)) {
                animatingDot = (animatingDot + 1) % 3
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

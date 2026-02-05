//
//  StreamingClient.swift
//  sautai_ios
//
//  Server-Sent Events (SSE) client for real-time AI streaming.
//  Used for Sous Chef token-by-token responses.
//

import Foundation

// MARK: - Streaming Client

class StreamingClient {

    // MARK: - Singleton

    static let shared = StreamingClient()

    // MARK: - Configuration

    private let baseURL: URL
    private var currentTask: URLSessionDataTask?

    // MARK: - Initialization

    private init() {
        #if DEBUG
        // Use 127.0.0.1 instead of localhost to avoid IPv6 issues
        self.baseURL = URL(string: "http://127.0.0.1:8000")!
        #else
        self.baseURL = URL(string: "https://api.sautai.com")!
        #endif
    }

    // MARK: - Stream Message

    /// Stream a message from Sous Chef AI
    func streamMessage(
        message: String,
        familyType: String,
        familyId: Int,
        onChunk: @escaping (String) -> Void,
        onComplete: @escaping () -> Void,
        onError: @escaping (Error) -> Void
    ) async {
        // Cancel any existing stream
        cancel()

        // Use URL(string:relativeTo:) to properly construct the URL
        guard let url = URL(string: "/chefs/api/me/sous-chef/stream/", relativeTo: baseURL) else {
            #if DEBUG
            print("🔴 StreamingClient: Invalid URL construction")
            #endif
            await MainActor.run { onError(StreamingError.invalidResponse) }
            return
        }

        #if DEBUG
        print("🎙️ StreamingClient: Starting stream to \(url.absoluteString)")
        print("   Message: \(message.prefix(50))...")
        print("   Family: \(familyType)/\(familyId)")
        #endif

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.timeoutInterval = 120  // 2 minute timeout for streaming

        // Add auth token
        do {
            let token = try await AuthManager.shared.getAccessToken()
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
            #if DEBUG
            print("🔑 StreamingClient: Auth token added (length: \(token.count))")
            #endif
        } catch {
            #if DEBUG
            print("🔴 StreamingClient: Auth error - \(error.localizedDescription)")
            #endif
            await MainActor.run { onError(StreamingError.authenticationFailed(error.localizedDescription)) }
            return
        }

        // Build request body - include client_type for iOS-specific response formatting
        let body: [String: Any] = [
            "message": message,
            "family_type": familyType,
            "family_id": familyId,
            "client_type": "ios"  // Tells Django to return plain markdown, not JSON blocks
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            #if DEBUG
            print("🔴 StreamingClient: JSON encode error - \(error.localizedDescription)")
            #endif
            await MainActor.run { onError(error) }
            return
        }

        // Use bytes for streaming
        do {
            let (bytes, response) = try await URLSession.shared.bytes(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                #if DEBUG
                print("🔴 StreamingClient: Non-HTTP response")
                #endif
                await MainActor.run { onError(StreamingError.invalidResponse) }
                return
            }

            #if DEBUG
            print("📥 StreamingClient: Response status \(httpResponse.statusCode)")
            #endif

            // Handle specific error codes
            guard (200...299).contains(httpResponse.statusCode) else {
                let errorMessage: String
                switch httpResponse.statusCode {
                case 401:
                    errorMessage = "Authentication expired. Please log in again."
                case 403:
                    errorMessage = "You don't have access to Sous Chef."
                case 404:
                    errorMessage = "Sous Chef service not found."
                case 429:
                    errorMessage = "Too many requests. Please wait a moment."
                case 500...599:
                    errorMessage = "Server error. Please try again later."
                default:
                    errorMessage = "Request failed with status \(httpResponse.statusCode)"
                }
                #if DEBUG
                print("🔴 StreamingClient: HTTP \(httpResponse.statusCode) - \(errorMessage)")
                #endif
                await MainActor.run { onError(StreamingError.httpError(httpResponse.statusCode, errorMessage)) }
                return
            }

            #if DEBUG
            print("🟢 StreamingClient: Connected, receiving chunks...")
            var chunkCount = 0
            #endif

            // Process SSE stream
            for try await line in bytes.lines {
                #if DEBUG
                if !line.isEmpty {
                    print("   📦 Line: \(line.prefix(80))")
                }
                #endif

                // SSE format: "data: <content>"
                if line.hasPrefix("data: ") {
                    let chunk = String(line.dropFirst(6))

                    // Check for end signal
                    if chunk == "[DONE]" {
                        #if DEBUG
                        print("✅ StreamingClient: Stream complete (\(chunkCount) chunks)")
                        #endif
                        await MainActor.run { onComplete() }
                        return
                    }

                    #if DEBUG
                    chunkCount += 1
                    #endif

                    // Parse JSON chunk from Django Sous Chef API
                    // With client_type: "ios", Django returns plain markdown text in "content"
                    if let data = chunk.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {

                        // Check message type
                        let messageType = json["type"] as? String

                        if messageType == "done" {
                            // Stream complete signal from Django
                            #if DEBUG
                            print("✅ StreamingClient: Received done signal")
                            #endif
                            await MainActor.run { onComplete() }
                            return
                        }

                        if messageType == "error" {
                            let errorMsg = json["message"] as? String ?? "Unknown error"
                            #if DEBUG
                            print("🔴 StreamingClient: Stream error - \(errorMsg)")
                            #endif
                            await MainActor.run { onError(StreamingError.serverError(errorMsg)) }
                            return
                        }

                        // Handle text content - with client_type: "ios", Django sends plain markdown
                        if let contentStr = json["content"] as? String, !contentStr.isEmpty {
                            #if DEBUG
                            print("   📝 Content: \(contentStr.prefix(50))...")
                            print("   🚀 Calling onChunk with \(contentStr.count) characters")
                            #endif
                            await MainActor.run {
                                #if DEBUG
                                print("   ✅ onChunk called on MainActor")
                                #endif
                                onChunk(contentStr)
                            }
                        }
                    } else {
                        // Plain text chunk (fallback)
                        #if DEBUG
                        print("   📝 Raw chunk: \(chunk.prefix(50))...")
                        #endif
                        await MainActor.run { onChunk(chunk) }
                    }
                }
            }

            #if DEBUG
            print("✅ StreamingClient: Stream ended naturally (\(chunkCount) chunks)")
            #endif
            await MainActor.run { onComplete() }

        } catch {
            if (error as NSError).code == NSURLErrorCancelled {
                #if DEBUG
                print("⚠️ StreamingClient: Cancelled by user")
                #endif
                return
            }

            #if DEBUG
            print("🔴 StreamingClient: Error - \(error.localizedDescription)")
            print("   NSError code: \((error as NSError).code)")
            #endif

            // Provide more user-friendly error messages
            let friendlyError: StreamingError
            let nsError = error as NSError

            switch nsError.code {
            case NSURLErrorNotConnectedToInternet:
                friendlyError = .noInternet
            case NSURLErrorTimedOut:
                friendlyError = .timeout
            case NSURLErrorCannotConnectToHost, NSURLErrorCannotFindHost:
                friendlyError = .serverUnreachable
            default:
                friendlyError = .connectionLost
            }

            await MainActor.run { onError(friendlyError) }
        }
    }

    /// Cancel the current stream
    func cancel() {
        currentTask?.cancel()
        currentTask = nil
    }
}

// MARK: - Streaming Error

enum StreamingError: LocalizedError {
    case invalidResponse
    case connectionLost
    case parsingFailed
    case authenticationFailed(String)
    case httpError(Int, String)
    case serverError(String)
    case noInternet
    case timeout
    case serverUnreachable

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid streaming response"
        case .connectionLost:
            return "Connection to server was lost"
        case .parsingFailed:
            return "Failed to parse streaming data"
        case .authenticationFailed(let reason):
            return "Authentication failed: \(reason)"
        case .httpError(_, let message):
            return message
        case .serverError(let message):
            return message
        case .noInternet:
            return "No internet connection. Please check your network."
        case .timeout:
            return "Request timed out. Please try again."
        case .serverUnreachable:
            return "Cannot reach the server. Please try again later."
        }
    }
}

// MARK: - Streaming Message Model

struct StreamingChunk: Codable {
    let content: String?
    let done: Bool?
    let error: String?
}

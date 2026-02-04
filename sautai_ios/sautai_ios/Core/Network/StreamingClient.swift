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
            await MainActor.run { onError(StreamingError.invalidResponse) }
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")

        // Add auth token
        do {
            let token = try await AuthManager.shared.getAccessToken()
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        } catch {
            await MainActor.run { onError(error) }
            return
        }

        // Build request body
        let body: [String: Any] = [
            "message": message,
            "family_type": familyType,
            "family_id": familyId
        ]

        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            await MainActor.run { onError(error) }
            return
        }

        // Use bytes for streaming
        do {
            let (bytes, response) = try await URLSession.shared.bytes(for: request)

            guard let httpResponse = response as? HTTPURLResponse,
                  (200...299).contains(httpResponse.statusCode) else {
                await MainActor.run { onError(StreamingError.invalidResponse) }
                return
            }

            // Process SSE stream
            for try await line in bytes.lines {
                // SSE format: "data: <content>"
                if line.hasPrefix("data: ") {
                    let chunk = String(line.dropFirst(6))

                    // Check for end signal
                    if chunk == "[DONE]" {
                        await MainActor.run { onComplete() }
                        return
                    }

                    // Parse JSON chunk if needed
                    if let data = chunk.data(using: .utf8),
                       let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                       let content = json["content"] as? String {
                        await MainActor.run { onChunk(content) }
                    } else {
                        // Plain text chunk
                        await MainActor.run { onChunk(chunk) }
                    }
                }
            }

            await MainActor.run { onComplete() }

        } catch {
            if (error as NSError).code == NSURLErrorCancelled {
                // Cancelled - don't report as error
                return
            }
            await MainActor.run { onError(error) }
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

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "Invalid streaming response"
        case .connectionLost:
            return "Connection to server was lost"
        case .parsingFailed:
            return "Failed to parse streaming data"
        }
    }
}

// MARK: - Streaming Message Model

struct StreamingChunk: Codable {
    let content: String?
    let done: Bool?
    let error: String?
}

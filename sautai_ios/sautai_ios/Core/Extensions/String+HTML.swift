//
//  String+HTML.swift
//  sautai_ios
//
//  HTML to NSAttributedString conversion with Sautai styling.
//  Used by SousChefView to render HTML responses from the backend.
//

import SwiftUI

#if canImport(UIKit)
import UIKit
#endif

extension String {
    /// Convert HTML string to NSAttributedString with Sautai styling.
    ///
    /// - Parameters:
    ///   - font: The base font to use
    ///   - textColor: The text color
    /// - Returns: An NSAttributedString suitable for display, or nil if parsing fails
    func htmlToAttributedString(
        font: UIFont = UIFont.systemFont(ofSize: 16),
        textColor: UIColor = UIColor(Color.sautai.slateTile)
    ) -> NSAttributedString? {
        // Build styled HTML with CSS that matches Sautai design
        let styledHTML = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
                font-size: \(font.pointSize)px;
                color: \(textColor.hexString);
                line-height: 1.5;
                margin: 0;
                padding: 0;
            }
            strong, b {
                font-weight: 600;
            }
            em, i {
                font-style: italic;
            }
            code {
                font-family: 'SF Mono', Menlo, monospace;
                font-size: 0.9em;
                background-color: rgba(0, 0, 0, 0.05);
                padding: 2px 5px;
                border-radius: 4px;
            }
            pre {
                font-family: 'SF Mono', Menlo, monospace;
                font-size: 0.9em;
                background-color: rgba(0, 0, 0, 0.05);
                padding: 10px;
                border-radius: 6px;
                overflow-x: auto;
                white-space: pre-wrap;
            }
            pre code {
                background-color: transparent;
                padding: 0;
            }
            a {
                color: #C96F45;
                text-decoration: none;
            }
            ul, ol {
                padding-left: 20px;
                margin: 8px 0;
            }
            li {
                margin: 4px 0;
            }
            table {
                border-collapse: collapse;
                margin: 8px 0;
                font-size: 0.9em;
            }
            th {
                background-color: rgba(0, 0, 0, 0.05);
                border: 1px solid rgba(0, 0, 0, 0.1);
                padding: 8px;
                text-align: left;
                font-weight: 600;
            }
            td {
                border: 1px solid rgba(0, 0, 0, 0.1);
                padding: 8px;
            }
            hr {
                border: none;
                border-top: 1px solid rgba(0, 0, 0, 0.1);
                margin: 12px 0;
            }
            br {
                line-height: 1.5;
            }
        </style>
        </head>
        <body>
        \(self)
        </body>
        </html>
        """

        guard let data = styledHTML.data(using: .utf8) else {
            return nil
        }

        // Parse HTML on main thread (required by iOS)
        let options: [NSAttributedString.DocumentReadingOptionKey: Any] = [
            .documentType: NSAttributedString.DocumentType.html,
            .characterEncoding: String.Encoding.utf8.rawValue
        ]

        // Note: NSAttributedString HTML parsing must be done on main thread
        // but SwiftUI may call this from background. For production, consider
        // caching or async processing.
        do {
            let attributed = try NSAttributedString(
                data: data,
                options: options,
                documentAttributes: nil
            )
            return attributed
        } catch {
            #if DEBUG
            print("⚠️ HTML parsing failed: \(error.localizedDescription)")
            #endif
            return nil
        }
    }

    /// Convert HTML string to SwiftUI AttributedString with Sautai styling.
    ///
    /// - Parameters:
    ///   - font: The SwiftUI Font to base styling on
    ///   - textColor: The SwiftUI Color for text
    /// - Returns: An AttributedString suitable for Text views, or nil if parsing fails
    func htmlToAttributedString(
        font: Font = SautaiFont.body,
        textColor: Color = .sautai.slateTile
    ) -> AttributedString? {
        // Convert SwiftUI types to UIKit types
        let uiFont = UIFont.systemFont(ofSize: 16) // Base size, CSS overrides
        let uiColor = UIColor(textColor)

        guard let nsAttributed = htmlToAttributedString(font: uiFont, textColor: uiColor) else {
            return nil
        }

        // Convert NSAttributedString to SwiftUI AttributedString
        return AttributedString(nsAttributed)
    }
}

// MARK: - UIColor Hex Extension

extension UIColor {
    /// Returns the hex string representation of the color (e.g., "#RRGGBB")
    var hexString: String {
        var r: CGFloat = 0
        var g: CGFloat = 0
        var b: CGFloat = 0
        var a: CGFloat = 0

        getRed(&r, green: &g, blue: &b, alpha: &a)

        let rgb = (Int)(r * 255) << 16 | (Int)(g * 255) << 8 | (Int)(b * 255) << 0

        return String(format: "#%06x", rgb)
    }
}

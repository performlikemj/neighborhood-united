/**
 * StructuredContent - Renders structured JSON content blocks.
 * 
 * This component receives content from the Sous Chef AI assistant
 * and renders it as properly formatted HTML. It handles:
 * - Text blocks (paragraphs)
 * - Table blocks (with headers and rows)
 * - List blocks (ordered and unordered)
 * - Legacy markdown text (backwards compatibility with ReactMarkdown)
 */

import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Check if content looks like markdown (has markdown syntax).
 */
function looksLikeMarkdown(content) {
  if (!content) return false
  // Check for common markdown patterns
  const markdownPatterns = [
    /\*\*[^*]+\*\*/,      // **bold**
    /\*[^*]+\*/,          // *italic*
    /^#{1,6}\s/m,         // # headers
    /^\s*[-*+]\s/m,       // - list items
    /^\s*\d+\.\s/m,       // 1. numbered lists
    /\[.+\]\(.+\)/,       // [links](url)
    /`[^`]+`/,            // `code`
    /^\|.+\|$/m,          // | tables |
  ]
  return markdownPatterns.some(pattern => pattern.test(content))
}

/**
 * Parse content and extract blocks.
 * Handles both structured JSON and legacy plain text/markdown.
 */
function parseContent(content) {
  if (!content) return { blocks: [], isLegacyMarkdown: false }
  
  // Try to parse as JSON
  try {
    const parsed = JSON.parse(content)
    if (parsed && Array.isArray(parsed.blocks)) {
      return { blocks: parsed.blocks, isLegacyMarkdown: false }
    }
    // If it's JSON but not our format, treat as legacy
    return { blocks: [], isLegacyMarkdown: true, rawContent: content }
  } catch {
    // Not JSON - this is legacy content
    return { blocks: [], isLegacyMarkdown: true, rawContent: content }
  }
}

/**
 * Render a text block as a paragraph.
 */
function TextBlock({ content }) {
  if (!content) return null
  
  // Split on double newlines for paragraphs
  const paragraphs = content.split(/\n\n+/).filter(Boolean)
  
  return (
    <>
      {paragraphs.map((para, i) => (
        <p key={i} className="structured-text">
          {para.split('\n').map((line, j) => (
            <span key={j}>
              {j > 0 && <br />}
              {line}
            </span>
          ))}
        </p>
      ))}
    </>
  )
}

/**
 * Render a table block.
 */
function TableBlock({ headers, rows }) {
  if (!headers || !rows) return null
  
  return (
    <div className="structured-table-wrapper">
      <table className="structured-table">
        <thead>
          <tr>
            {headers.map((header, i) => (
              <th key={i}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * Render a list block (ordered or unordered).
 */
function ListBlock({ items, ordered }) {
  if (!items || !Array.isArray(items)) return null
  
  const ListTag = ordered ? 'ol' : 'ul'
  
  return (
    <ListTag className={`structured-list ${ordered ? 'ordered' : 'unordered'}`}>
      {items.map((item, i) => (
        <li key={i}>{item}</li>
      ))}
    </ListTag>
  )
}

/**
 * Main StructuredContent component.
 * 
 * @param {Object} props
 * @param {string} props.content - The content string (JSON or plain text)
 * @param {string} props.className - Optional additional CSS class
 */
export default function StructuredContent({ content, className = '' }) {
  // Parse content to blocks or detect legacy markdown
  const parsed = useMemo(() => parseContent(content), [content])
  
  // Handle legacy markdown content with ReactMarkdown
  if (parsed.isLegacyMarkdown) {
    return (
      <div className={`structured-content legacy-markdown ${className}`}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {parsed.rawContent || ''}
        </ReactMarkdown>
        <style>{legacyMarkdownStyles}</style>
      </div>
    )
  }
  
  const { blocks } = parsed
  if (!blocks.length) return null
  
  return (
    <div className={`structured-content ${className}`}>
      {blocks.map((block, index) => {
        switch (block.type) {
          case 'table':
            return (
              <TableBlock
                key={index}
                headers={block.headers}
                rows={block.rows}
              />
            )
          
          case 'list':
            return (
              <ListBlock
                key={index}
                items={block.items}
                ordered={block.ordered}
              />
            )
          
          case 'text':
          default:
            return <TextBlock key={index} content={block.content} />
        }
      })}
      
      <style>{`
        .structured-content {
          line-height: 1.6;
          color: var(--text);
          font-size: 0.9rem;
          word-break: break-word;
        }
        
        .structured-text {
          margin: 0.75em 0;
          color: var(--text);
        }
        
        .structured-text:first-child { margin-top: 0; }
        .structured-text:last-child { margin-bottom: 0; }
        
        /* Table Styles */
        .structured-table-wrapper {
          overflow-x: auto;
          margin: 0.75em 0;
        }
        
        .structured-table {
          border-collapse: collapse;
          font-size: 0.85em;
          width: 100%;
          min-width: 300px;
        }
        
        .structured-table th {
          background: var(--surface-2, #f3f4f6);
          border: 1px solid var(--border, #e5e7eb);
          padding: 0.5em 0.75em;
          color: var(--text);
          font-weight: 600;
          text-align: left;
          white-space: nowrap;
        }
        
        .structured-table td {
          border: 1px solid var(--border, #e5e7eb);
          padding: 0.5em 0.75em;
          color: var(--text);
          vertical-align: top;
        }
        
        .structured-table tbody tr:nth-child(even) {
          background: rgba(128, 128, 128, 0.05);
        }
        
        .structured-table tbody tr:hover {
          background: rgba(92, 184, 92, 0.08);
        }
        
        /* List Styles */
        .structured-list {
          margin: 0.75em 0;
          padding-left: 1.5em;
          color: var(--text);
        }
        
        .structured-list li {
          margin: 0.35em 0;
          line-height: 1.5;
        }
        
        .structured-list.unordered { list-style-type: disc; }
        .structured-list.ordered { list-style-type: decimal; }
        
        /* First/last element spacing */
        .structured-content > *:first-child { margin-top: 0 !important; }
        .structured-content > *:last-child { margin-bottom: 0 !important; }
      `}</style>
    </div>
  )
}

/**
 * Styles for legacy markdown content rendered with ReactMarkdown.
 */
const legacyMarkdownStyles = `
  .legacy-markdown {
    line-height: 1.6;
    color: var(--text);
    font-size: 0.9rem;
    word-break: break-word;
  }
  
  .legacy-markdown p {
    margin: 0.75em 0;
    color: var(--text);
  }
  
  .legacy-markdown p:first-child { margin-top: 0; }
  .legacy-markdown p:last-child { margin-bottom: 0; }
  
  .legacy-markdown h1,
  .legacy-markdown h2,
  .legacy-markdown h3,
  .legacy-markdown h4 {
    color: var(--text);
    font-weight: 600;
    line-height: 1.3;
    margin-top: 1.25em;
    margin-bottom: 0.5em;
  }
  
  .legacy-markdown h1 { font-size: 1.3em; }
  .legacy-markdown h2 { font-size: 1.15em; }
  .legacy-markdown h3 { font-size: 1.05em; }
  .legacy-markdown h4 { font-size: 1em; }
  
  .legacy-markdown h1:first-child,
  .legacy-markdown h2:first-child,
  .legacy-markdown h3:first-child { margin-top: 0; }
  
  .legacy-markdown ul,
  .legacy-markdown ol {
    margin: 0.75em 0;
    padding-left: 1.5em;
    color: var(--text);
  }
  
  .legacy-markdown li {
    margin: 0.35em 0;
    line-height: 1.5;
    color: var(--text);
  }
  
  .legacy-markdown ul { list-style-type: disc; }
  .legacy-markdown ol { list-style-type: decimal; }
  
  .legacy-markdown strong { font-weight: 700; color: var(--text); }
  .legacy-markdown em { font-style: italic; }
  
  .legacy-markdown code {
    background: var(--surface-2, #f3f4f6);
    border: 1px solid var(--border, #e5e7eb);
    padding: 0.15em 0.4em;
    border-radius: 4px;
    font-size: 0.85em;
  }
  
  .legacy-markdown pre {
    background: var(--surface-2, #f3f4f6);
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 6px;
    padding: 0.75em 1em;
    margin: 0.75em 0;
    overflow-x: auto;
  }
  
  .legacy-markdown pre code {
    background: transparent;
    border: none;
    padding: 0;
  }
  
  .legacy-markdown table {
    border-collapse: collapse;
    margin: 0.75em 0;
    font-size: 0.85em;
    width: 100%;
    display: block;
    overflow-x: auto;
  }
  
  .legacy-markdown th {
    background: var(--surface-2, #f3f4f6);
    border: 1px solid var(--border, #e5e7eb);
    padding: 0.5em 0.75em;
    color: var(--text);
    font-weight: 600;
    text-align: left;
  }
  
  .legacy-markdown td {
    border: 1px solid var(--border, #e5e7eb);
    padding: 0.5em 0.75em;
    color: var(--text);
  }
  
  .legacy-markdown tbody tr:nth-child(even) {
    background: rgba(128, 128, 128, 0.05);
  }
  
  .legacy-markdown > *:first-child { margin-top: 0 !important; }
  .legacy-markdown > *:last-child { margin-bottom: 0 !important; }
`

/**
 * Export parsing utility for use in other components.
 */
export { parseContent }

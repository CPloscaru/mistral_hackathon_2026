/**
 * TypingIndicator - Three animated dots in an assistant bubble
 *
 * Displayed when isStreaming=true AND assistant message content is empty
 * (i.e., before the first token arrives).
 *
 * Dots bounce with staggered delays: 0s, 0.2s, 0.4s
 */

function TypingIndicator() {
  return (
    <div className="typing-indicator-row" aria-label="L'assistant écrit…" role="status">
      <div className="typing-indicator">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  )
}

export default TypingIndicator

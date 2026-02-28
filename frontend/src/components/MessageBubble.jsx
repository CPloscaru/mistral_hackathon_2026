/**
 * MessageBubble - iMessage-style chat bubble
 *
 * Props:
 *   message: { role: 'user'|'assistant', content: string, id: number, streaming?: boolean }
 *
 * - User: blue background, right-aligned, flat bottom-right corner
 * - Assistant: grey background, left-aligned, flat bottom-left corner
 * - Streaming: cursor blink at end of text
 * - Fade-in animation on appearance
 * - Lightweight markdown: **bold**, *italic*, newlines
 */

function parseMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>')
}

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const isStreaming = message.streaming === true

  const rowClass = `message-row ${isUser ? 'message-row--user' : 'message-row--assistant'}`

  const bubbleClass = [
    'message-bubble',
    isUser ? 'message-bubble--user' : 'message-bubble--assistant',
    isStreaming ? 'message-bubble--streaming' : '',
  ]
    .filter(Boolean)
    .join(' ')

  return (
    <div className={rowClass}>
      <div
        className={bubbleClass}
        dangerouslySetInnerHTML={{ __html: parseMarkdown(message.content) }}
      />
    </div>
  )
}

export default MessageBubble

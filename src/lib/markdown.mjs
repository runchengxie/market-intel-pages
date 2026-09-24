import { marked } from 'marked';
import sanitizeHtml from 'sanitize-html';

marked.setOptions({ gfm: true, breaks: false });

export function renderMarkdown(markdown) {
  const parsed = marked.parse(markdown);
  return sanitizeHtml(parsed, {
    allowedTags: [
      'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'br', 'hr', 'blockquote',
      'ul', 'ol', 'li', 'strong', 'em', 'code', 'pre', 'a',
      'table', 'thead', 'tbody', 'tr', 'th', 'td', 'del',
    ],
    allowedAttributes: { a: ['href', 'title', 'rel', 'target'], th: ['align'], td: ['align'] },
    allowedSchemes: ['http', 'https', 'mailto'],
    allowProtocolRelative: false,
    transformTags: {
      a: (_tag, attributes) => ({ tagName: 'a', attribs: {
        ...attributes,
        ...(attributes.href?.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {}),
      } }),
    },
  });
}

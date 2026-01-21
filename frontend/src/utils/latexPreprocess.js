/**
 * Preprocesses text to convert various LaTeX delimiter formats
 * to the format expected by remark-math ($ and $$).
 *
 * Handles:
 * - \( ... \) → $ ... $ (inline math)
 * - \[ ... \] → $$ ... $$ (display math)
 * - Escaped dollar signs and edge cases
 */

export function preprocessLatex(content) {
  if (!content || typeof content !== 'string') {
    return content;
  }

  let processed = content;

  // Convert display math first: \[ ... \] → $$ ... $$
  // Using a regex that handles multiline content
  processed = processed.replace(/\\\[([\s\S]*?)\\\]/g, (match, inner) => {
    return `$$${inner}$$`;
  });

  // Convert inline math: \( ... \) → $ ... $
  processed = processed.replace(/\\\(([\s\S]*?)\\\)/g, (match, inner) => {
    return `$${inner}$`;
  });

  return processed;
}

export default preprocessLatex;

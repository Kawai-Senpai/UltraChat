/**
 * UltraChat - Markdown Renderer
 * Handles Markdown parsing and code highlighting.
 */

// Configure marked
marked.setOptions({
    gfm: true,
    breaks: true,
    highlight: function(code, lang) {
        if (lang && hljs.getLanguage(lang)) {
            try {
                return hljs.highlight(code, { language: lang }).value;
            } catch (e) {
                console.error('Highlight error:', e);
            }
        }
        return hljs.highlightAuto(code).value;
    }
});

// Custom renderer for code blocks with copy button
const renderer = new marked.Renderer();

renderer.code = function(code, language) {
    const lang = language || 'plaintext';
    const highlighted = lang && hljs.getLanguage(lang)
        ? hljs.highlight(code, { language: lang }).value
        : hljs.highlightAuto(code).value;
    
    const id = `code-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    
    return `
        <div class="code-block">
            <div class="code-header">
                <span class="code-lang">${lang}</span>
                <button class="code-copy" data-code-id="${id}" onclick="window.copyCode('${id}')">
                    Copy
                </button>
            </div>
            <pre><code id="${id}" class="hljs language-${lang}">${highlighted}</code></pre>
        </div>
    `;
};

marked.use({ renderer });

// Global copy function
window.copyCode = async function(id) {
    const codeElement = document.getElementById(id);
    if (!codeElement) return;
    
    const text = codeElement.textContent;
    
    try {
        await navigator.clipboard.writeText(text);
        
        // Update button text
        const button = document.querySelector(`[data-code-id="${id}"]`);
        if (button) {
            const originalText = button.textContent;
            button.textContent = 'Copied!';
            setTimeout(() => {
                button.textContent = originalText;
            }, 2000);
        }
    } catch (err) {
        console.error('Failed to copy:', err);
    }
};

// Render markdown to HTML
export function renderMarkdown(text) {
    if (!text) return '';
    
    try {
        return marked.parse(text);
    } catch (e) {
        console.error('Markdown parse error:', e);
        return escapeHtml(text);
    }
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Render inline markdown (no block elements)
export function renderInlineMarkdown(text) {
    if (!text) return '';
    
    try {
        return marked.parseInline(text);
    } catch (e) {
        console.error('Markdown inline parse error:', e);
        return escapeHtml(text);
    }
}

// Highlight all code blocks in an element
export function highlightCode(container) {
    const blocks = container.querySelectorAll('pre code:not(.hljs)');
    blocks.forEach((block) => {
        hljs.highlightElement(block);
    });
}

export default { renderMarkdown, renderInlineMarkdown, highlightCode };

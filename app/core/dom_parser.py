import re
from bs4 import BeautifulSoup, Comment

def compress_dom(html_source: str) -> str:
    """
    Takes raw HTML and compresses it into a clean, text-based representation
    of only the interactive and meaningful elements (buttons, links, inputs, labels).
    This prevents blowing out the LLM's context window.
    """
    soup = BeautifulSoup(html_source, 'html.parser')
    
    # 1. Remove all script, style, meta, and svg tags
    for tag in soup(["script", "style", "meta", "noscript", "svg", "path", "header", "footer"]):
        tag.decompose()
        
    # 2. Remove comments
    comments = soup.findAll(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()
        
    # 3. Target specifically interactive/important elements
    interactive_tags = ['a', 'button', 'input', 'select', 'textarea', 'label', 'h1', 'h2', 'h3']
    
    compressed_lines = []
    
    for element in soup.find_all(interactive_tags):
        # Skip hidden elements
        style = element.get('style', '').lower()
        if 'display: none' in style or 'visibility: hidden' in style:
            continue
        if element.get('type') == 'hidden':
            continue
            
        el_type = element.name.upper()
        
        # Build a representation like: [BUTTON id="submit-btn"] Submit Application [/BUTTON]
        attrs_str = ""
        
        # We only care about id, name, type, and placeholder to give the agent targets
        for attr in ['id', 'name', 'type', 'placeholder', 'aria-label', 'value']:
            val = element.get(attr)
            if val:
                # Keep it clean
                val_str = str(val) if not isinstance(val, list) else " ".join(val)
                attrs_str += f' {attr}="{val_str}"'
                
        text_content = element.get_text(strip=True)
        
        # If it's an input with no text, it might just have a placeholder or value
        if not text_content and element.name == 'input':
            text_content = element.get('value', '')
            
        # Only add elements that actually have some identifying text or attributes
        if text_content or attrs_str:
            line = f"<{el_type}{attrs_str}>{text_content}</{el_type}>"
            compressed_lines.append(line)

    # 4. Join and deduplicate excessive newlines
    clean_dom = "\n".join(compressed_lines)
    return clean_dom

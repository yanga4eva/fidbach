import re
from bs4 import BeautifulSoup, Comment

def get_xpath(element) -> str:
    """Generates an absolute XPath for a given BeautifulSoup element."""
    components = []
    child = element if element.name else element.parent
    for parent in child.parents:
        siblings = parent.find_all(child.name, recursive=False)
        components.append(
            child.name if len(siblings) == 1 else '%s[%d]' % (
                child.name,
                next(i for i, s in enumerate(siblings, 1) if s is child)
            )
        )
        child = parent
    components.reverse()
    return '/%s' % '/'.join(components)

def compress_dom(html_source: str) -> str:
    """
    Takes raw HTML and compresses it into a clean, text-based representation
    of only the interactive and meaningful elements.
    Crucially, it embeds the EXACT XPath for every element so the LLM doesn't guess.
    """
    soup = BeautifulSoup(html_source, 'html.parser')
    
    # 1. Remove noise
    for tag in soup(["script", "style", "meta", "noscript", "svg", "path", "nav", "footer", "iframe"]):
        tag.decompose()
        
    comments = soup.findAll(string=lambda text: isinstance(text, Comment))
    for comment in comments:
        comment.extract()
        
    # 2. Target specifically interactive/important elements
    interactive_tags = ['a', 'button', 'input', 'select', 'textarea', 'label']
    
    compressed_lines = []
    
    for element in soup.find_all(interactive_tags):
        style = element.get('style', '').lower()
        if 'display: none' in style or 'visibility: hidden' in style:
            continue
        if element.get('type') == 'hidden':
            continue
            
        el_type = element.name.upper()
        exact_xpath = get_xpath(element)
        
        attrs_str = f' xpath="{exact_xpath}"'
        
        for attr in ['id', 'name', 'type', 'placeholder', 'value']:
            val = element.get(attr)
            if val:
                val_str = str(val) if not isinstance(val, list) else " ".join(val)
                attrs_str += f' {attr}="{val_str}"'
                
        text_content = element.get_text(strip=True)
        if not text_content and element.name == 'input':
            text_content = element.get('value', '')
            
        if text_content or 'type' in attrs_str or 'placeholder' in attrs_str:
            line = f"<{el_type}{attrs_str}>{text_content}</{el_type}>"
            compressed_lines.append(line)

    clean_dom = "\n".join(compressed_lines)
    return clean_dom

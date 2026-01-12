import html

def hide_sensitive_info(paragraph, words_array):
    import re

    # PII regex patterns
    patterns = [
        # Full Name (Assuming two capitalized words)
        r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b',
        # Phone numbers (Indian format)
        r'\+91[-\s]?\d{10}',
        r'\b\d{10}\b',
        # Email addresses
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b',
        # Aadhaar number
        r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        # PAN card
        r'\b[A-Z]{5}\d{4}[A-Z]\b',
        # Passport
        r'\b([A-Z][0-9]{7})\b',
        # Driving License (example: DL-09-2020-123456)
        r'\bDL-\d{2}-\d{4}-\d{6}\b',
        # Bank account number (12+ digits)
        r'\b\d{9,18}\b',
        # IFSC code
        r'\b[A-Z]{4}0\d{6}\b',
        # Social media handles (@username)
        r'@\w+',
        # LinkedIn/GitHub usernames (assuming after linkedin.com/in/ or github.com/)
        r'(linkedin\.com/in/|github\.com/)[A-Za-z0-9_-]+',
        # Addresses (very basic, looking for Flat/No/Street/Sector etc.)
        r'Flat No\.? \d+[A-Za-z]?,? [A-Za-z ]+,? Sector \d+,? [A-Za-z]+',
    ]

    # Hide PII
    for pat in patterns:
        paragraph = re.sub(pat, '**********', paragraph)

    # Hide words from words_array (case-insensitive, whole words)
    for word in words_array:
        word_pat = r'\b' + re.escape(word) + r'\b'
        paragraph = re.sub(word_pat, '**********', paragraph, flags=re.IGNORECASE)

    return paragraph

if __name__ == "__main__":
    ""
    with open("output.pdf", "rb") as f:
        input_data = f.read()
    
    data = hide_sensitive_info(paragraph=input_data, words_array=["assignment", "capstone"])
    unescaped = html.unescape(data)

    pdf_bytes = unescaped.encode("latin-1", errors="strict")

    with open("output2.pdf", "wb") as f:
        f.write(pdf_bytes)
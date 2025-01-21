import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extractor import extract_from_pdf

def main():
    pdf_path = "docs/test.pdf"
    try:
        pages = extract_from_pdf(pdf_path)
        print(f"Extracted {len(pages)} pages:")
        for page in pages:
            print(f"Page {page['page']}: {page['text'][:100]}...")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 

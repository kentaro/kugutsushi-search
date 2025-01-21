import pdfplumber
from pathlib import Path
from typing import List, Dict, Union
import io
import re

class PDFExtractor:
    def __init__(self, pdf_data: Union[str, bytes, Path]):
        if isinstance(pdf_data, (str, Path)):
            self.pdf_data = Path(pdf_data)
            if not self.pdf_data.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_data}")
        else:
            self.pdf_data = io.BytesIO(pdf_data)

    def clean_text(self, text: str) -> str:
        """テキストを整形"""
        # 連続する空白を1つに
        text = re.sub(r'\s+', ' ', text)
        # 文末の句点で改行を入れる
        text = re.sub(r'。', '。\n', text)
        # 先頭と末尾の空白を削除
        return text.strip()

    def extract(self) -> List[Dict[str, any]]:
        """PDFからテキストを抽出し、ページ単位でリストを返す"""
        pages = []
        with pdfplumber.open(self.pdf_data) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text and text.strip():
                    pages.append({
                        "page": i,
                        "text": self.clean_text(text),
                        "file": str(self.pdf_data) if isinstance(self.pdf_data, Path) else "memory"
                    })
        return pages

def extract_from_pdf(pdf_data: Union[str, bytes, Path]) -> List[Dict[str, any]]:
    """PDFExtractorのヘルパー関数"""
    extractor = PDFExtractor(pdf_data)
    return extractor.extract() 
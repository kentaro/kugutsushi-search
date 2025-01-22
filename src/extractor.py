import fitz
from pathlib import Path
from typing import List, Dict, Union
import io
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

class PDFExtractor:
    def __init__(self, pdf_data: Union[str, bytes, Path], max_workers: int = 8):
        if isinstance(pdf_data, (str, Path)):
            self.pdf_data = Path(pdf_data)
            if not self.pdf_data.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_data}")
        else:
            self.pdf_data = io.BytesIO(pdf_data)
        self.max_workers = max_workers

    def clean_text(self, text: str) -> str:
        """テキストを整形"""
        # 連続する空白を1つに
        text = re.sub(r'\s+', ' ', text)
        # 文末の句点で改行を入れる
        text = re.sub(r'。', '。\n', text)
        # 先頭と末尾の空白を削除
        return text.strip()

    def process_page(self, page_info: tuple) -> Dict[str, any]:
        """1ページを処理"""
        page, i, file_name = page_info
        text = page.get_text()
        if text and text.strip():
            return {
                "page": i,
                "text": self.clean_text(text),
                "file": file_name
            }
        return None

    def extract(self) -> List[Dict[str, any]]:
        """PDFからテキストを抽出し、ページ単位でリストを返す"""
        pages = []
        with fitz.open(stream=self.pdf_data if isinstance(self.pdf_data, io.BytesIO) else str(self.pdf_data)) as doc:
            file_name = str(self.pdf_data) if isinstance(self.pdf_data, Path) else self.pdf_data.name if hasattr(self.pdf_data, 'name') else "memory"
            
            # ページ情報をリストにまとめる
            page_infos = [(page, i, file_name) for i, page in enumerate(doc, 1)]
            
            # マルチスレッドで処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 進捗バーを表示しながら処理
                futures = [executor.submit(self.process_page, page_info) for page_info in page_infos]
                for future in tqdm(as_completed(futures), total=len(futures), desc="Processing PDF"):
                    result = future.result()
                    if result:
                        pages.append(result)

        return pages

def extract_from_pdf(pdf_data: Union[str, bytes, Path], max_workers: int = 8) -> List[Dict[str, any]]:
    """PDFExtractorのヘルパー関数"""
    extractor = PDFExtractor(pdf_data, max_workers=max_workers)
    return extractor.extract() 
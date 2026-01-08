"""PDF抽出 - PyMuPDFによるテキスト抽出"""

import fitz
from pathlib import Path
from typing import List, Dict, Union
import io
import re
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500  # 文字数
CHUNK_OVERLAP = 50  # オーバーラップ


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """テキストをチャンクに分割

    句点・改行で区切りつつ、chunk_size文字程度のチャンクを作成。
    句点がない長いテキストは強制分割。
    """
    if len(text) <= chunk_size:
        return [text]

    # 句点・改行で分割
    sentences = re.split(r'(?<=[。．！？\n])', text)

    chunks = []
    current = ""

    for sent in sentences:
        # 文自体がchunk_sizeより長い場合は強制分割
        while len(sent) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.append(sent[:chunk_size].strip())
            sent = sent[chunk_size - overlap:]

        if len(current) + len(sent) <= chunk_size:
            current += sent
        else:
            if current:
                chunks.append(current.strip())
            current = sent

    if current.strip():
        chunks.append(current.strip())

    return chunks


def extract_from_pdf(pdf_data: Union[str, bytes, Path]) -> List[Dict]:
    """PDFからテキストを抽出

    Args:
        pdf_data: ファイルパス、バイトデータ、またはPathオブジェクト

    Returns:
        [{"page": ページ番号(1-indexed), "text": テキスト}, ...]
    """
    if isinstance(pdf_data, (str, Path)):
        pdf_path = Path(pdf_data)
        if not pdf_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {pdf_data}")
        doc = fitz.open(str(pdf_path))
    else:
        doc = fitz.open(stream=io.BytesIO(pdf_data), filetype="pdf")

    pages = []
    with doc:
        for i, page in enumerate(doc, 1):
            text = page.get_text()
            if text and text.strip():
                # テキスト整形: 連続空白を1つに、句点で改行
                text = re.sub(r'\s+', ' ', text)
                text = re.sub(r'。', '。\n', text)
                pages.append({"page": i, "text": text.strip()})

    return pages

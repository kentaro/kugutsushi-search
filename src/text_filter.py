"""テキストフィルタ - 低品質ページの除外"""

import re

MIN_TEXT_LENGTH = 100
MIN_UNIQUE_CHARS = 20

SKIP_PATTERNS = [
    r'^目\s*次\s*$',
    r'^索\s*引\s*$',
    r'^contents?\s*$',
    r'^index\s*$',
    r'^第\s*\d+\s*[章節部編]\s*$',
    r'^chapter\s+\d+\s*$',
]


def is_content_page(text: str) -> bool:
    """コンテンツページかどうか判定

    Returns:
        True: インデックスに含める
        False: 目次・索引・章扉など（スキップ）
    """
    text = text.strip()

    # 文字数不足
    if len(text) < MIN_TEXT_LENGTH:
        return False

    # ユニーク文字不足（記号・数字だけのページ除外）
    unique = set(re.sub(r'[\s\d\W]', '', text))
    if len(unique) < MIN_UNIQUE_CHARS:
        return False

    # ページ番号だけ
    if re.match(r'^[\d\s\-\.]+$', text):
        return False

    # 除外パターン（短いページのみ）
    first_line = text.split('\n')[0].strip()
    for pattern in SKIP_PATTERNS:
        if re.match(pattern, first_line, re.IGNORECASE):
            if len(text) < 500:
                return False

    return True

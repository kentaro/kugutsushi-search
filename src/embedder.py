from sentence_transformers import SentenceTransformer
from typing import List, Dict

class Embedder:
    def __init__(self):
        self.model = SentenceTransformer("hotchpotch/static-embedding-japanese")

    def generate_embedding(self, text: str) -> List[float]:
        """テキストをベクトル化"""
        return self.model.encode(text)

    def generate_embeddings(self, texts: List[Dict[str, any]]) -> List[List[float]]:
        """複数のテキストをベクトル化"""
        # テキストのみを抽出してベクトル化
        text_list = [text["text"] for text in texts]
        return self.model.encode(text_list) 
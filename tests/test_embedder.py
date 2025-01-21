import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.embedder import Embedder

def main():
    try:
        # テスト用のテキスト
        texts = [
            "これは日本語のテストテキストです。",
            "文ベクトルの生成をテストします。",
            "複数の文章を一度に処理できます。"
        ]

        # Embedderの初期化
        embedder = Embedder()
        
        # 単一のテキストでテスト
        print("単一テキストのベクトル生成テスト:")
        vector = embedder.generate_embedding(texts[0])
        print(f"Shape: {vector.shape}")
        print(f"Vector: {vector[:5]}...")  # 最初の5要素だけ表示
        
        # 複数テキストでテスト
        print("\n複数テキストのベクトル生成テスト:")
        vectors = embedder.generate_embeddings(texts)
        print(f"Shape: {vectors.shape}")
        print(f"First vector: {vectors[0][:5]}...")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 
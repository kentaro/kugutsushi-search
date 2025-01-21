import os
import sys
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.indexer import Indexer
from src.embedder import Embedder

def main():
    try:
        # テストデータ
        texts = [
            "美味しいラーメン屋に行きたい",
            "素敵なカフェが近所にあるよ。落ち着いた雰囲気でゆっくりできるし、窓際の席からは公園の景色も見えるんだ。",
            "新鮮な魚介を提供する店です。地元の漁師から直接仕入れているので鮮度は抜群ですし、料理人の腕も確かです。",
            "あそこは行きにくいけど、隠れた豚骨の名店だよ。スープが最高だし、麺の硬さも好み。",
            "おすすめの中華そばの店を教えてあげる。とりわけチャーシューが手作りで柔らかくてジューシーなんだ。",
        ]
        
        # メタデータ
        metadata_list = [
            {"id": i, "text": text} for i, text in enumerate(texts)
        ]
        
        # ベクトル生成
        print("ベクトル生成中...")
        embedder = Embedder()
        vectors = embedder.generate_embeddings(texts)
        print(f"生成されたベクトル: shape={vectors.shape}")
        
        # インデックス作成
        print("\nインデックス作成中...")
        indexer = Indexer()
        indexer.add(vectors, metadata_list)
        
        # 検索テスト
        print("\n検索テスト:")
        query = "ラーメンが食べたい"
        query_vector = embedder.generate_embedding(query)
        results = indexer.search(query_vector, top_k=3)
        
        print(f"クエリ: {query}")
        print("\n検索結果:")
        for metadata, score in results:
            print(f"スコア: {score:.4f}")
            print(f"テキスト: {metadata['text']}\n")
        
        # インデックスの保存と読み込みテスト
        print("インデックスの保存テスト...")
        indexer.save("test_index")
        
        print("インデックスの読み込みテスト...")
        new_indexer = Indexer()
        new_indexer.load("test_index")
        
        # 読み込んだインデックスで検索
        print("\n読み込んだインデックスでの検索テスト:")
        results = new_indexer.search(query_vector, top_k=3)
        for metadata, score in results:
            print(f"スコア: {score:.4f}")
            print(f"テキスト: {metadata['text']}\n")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 
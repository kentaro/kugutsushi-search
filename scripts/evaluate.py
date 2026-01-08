#!/usr/bin/env python3
"""網羅的評価スクリプト - ハイブリッド検索システムの性能評価"""

import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import sys
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Tuple
import statistics

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.embedder import Embedder
from src.indexer import Indexer
from src.bm25_indexer import BM25Indexer
from src.hybrid_searcher import HybridSearcher, SearchConfig

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 評価用クエリセット（多様なカテゴリ）
EVAL_QUERIES = {
    "技術・プログラミング": [
        "機械学習の基本的なアルゴリズム",
        "Pythonでのデータ処理",
        "関数型プログラミングの特徴",
        "ニューラルネットワークの構造",
        "アルゴリズムの計算量",
    ],
    "哲学・思想": [
        "存在とは何か",
        "認識論の歴史",
        "倫理学の基本概念",
        "現象学の方法",
        "言語と意味の関係",
    ],
    "歴史・社会": [
        "明治維新の影響",
        "戦後日本の経済成長",
        "民主主義の発展",
        "グローバリゼーションの課題",
        "日本の近代化過程",
    ],
    "科学・自然": [
        "量子力学の基礎",
        "進化論の証拠",
        "脳と意識の関係",
        "気候変動のメカニズム",
        "生態系のバランス",
    ],
    "文学・芸術": [
        "小説の語りの技法",
        "詩の韻律",
        "現代アートの特徴",
        "日本文学の伝統",
        "美の概念",
    ],
    "経済・ビジネス": [
        "マクロ経済政策",
        "ファイナンスの基礎",
        "起業のリスク",
        "マーケティング戦略",
        "組織のマネジメント",
    ],
    "心理・教育": [
        "認知心理学の知見",
        "学習の動機づけ",
        "発達心理学",
        "教育方法論",
        "記憶のメカニズム",
    ],
    "キーワード検索（固有名詞）": [
        "アドラー心理学",
        "ヴィトゲンシュタイン",
        "レヴィ＝ストロース",
        "マルクス経済学",
        "フーコー権力論",
    ],
}


@dataclass
class QueryResult:
    """クエリごとの評価結果"""
    query: str
    category: str
    latency_ms: float
    num_results: int
    top_files: List[str]
    top_scores: List[float]


@dataclass
class AblationResult:
    """アブレーション評価結果"""
    config_name: str
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_results: float


@dataclass
class EvaluationReport:
    """評価レポート"""
    timestamp: str
    index_stats: Dict[str, Any]
    performance: Dict[str, Any]
    ablation: List[Dict[str, Any]]
    query_results: List[Dict[str, Any]]


class Evaluator:
    """評価実行クラス"""

    def __init__(self):
        logger.info("評価システム初期化中...")

        # コンポーネント初期化
        self.embedder = Embedder()
        self.indexer = Indexer()
        self.indexer.load()

        self.bm25 = BM25Indexer()
        self.bm25.load()

        self.searcher = HybridSearcher(self.embedder, self.indexer, self.bm25)

        logger.info("評価システム初期化完了")

    def get_index_stats(self) -> Dict[str, Any]:
        """インデックス統計"""
        return {
            "vector_count": self.indexer.get_vector_count(),
            "metadata_count": self.indexer.db.get_metadata_count(),
            "bm25_doc_count": self.bm25.corpus_size,
            "file_count": len(self.indexer.db.get_file_list()),
            "is_trained": self.indexer.is_trained,
        }

    def warmup(self, n: int = 3) -> None:
        """ウォームアップ（モデルキャッシュ）"""
        logger.info(f"ウォームアップ中（{n}回）...")
        for _ in range(n):
            self.searcher.search("テスト", top_k=5)
        logger.info("ウォームアップ完了")

    def benchmark_latency(self, queries: List[str], config: SearchConfig, n_runs: int = 3) -> Dict[str, float]:
        """レイテンシベンチマーク"""
        latencies = []

        for query in queries:
            for _ in range(n_runs):
                start = time.perf_counter()
                self.searcher.search(query, top_k=10, config=config)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)

        latencies.sort()
        return {
            "avg_ms": statistics.mean(latencies),
            "p50_ms": latencies[len(latencies) // 2],
            "p95_ms": latencies[int(len(latencies) * 0.95)],
            "p99_ms": latencies[int(len(latencies) * 0.99)],
            "min_ms": min(latencies),
            "max_ms": max(latencies),
        }

    def evaluate_queries(self, config: SearchConfig) -> List[QueryResult]:
        """クエリ評価"""
        results = []

        for category, queries in EVAL_QUERIES.items():
            for query in queries:
                start = time.perf_counter()
                search_results = self.searcher.search(query, top_k=10, config=config)
                elapsed = (time.perf_counter() - start) * 1000

                result = QueryResult(
                    query=query,
                    category=category,
                    latency_ms=elapsed,
                    num_results=len(search_results),
                    top_files=[r[0].get("file", "")[:50] for r in search_results[:5]],
                    top_scores=[round(r[1], 4) for r in search_results[:5]],
                )
                results.append(result)

        return results

    def ablation_study(self) -> List[AblationResult]:
        """アブレーション評価"""
        configs = [
            ("Vector Only", SearchConfig(use_bm25=False, use_rerank=False)),
            ("BM25 Only (via hybrid)", SearchConfig(use_bm25=True, use_rerank=False)),
            ("Hybrid (Vector+BM25)", SearchConfig(use_bm25=True, use_rerank=False)),
            ("Hybrid + Rerank", SearchConfig(use_bm25=True, use_rerank=True)),
        ]

        # フラットなクエリリスト
        all_queries = [q for queries in EVAL_QUERIES.values() for q in queries]

        results = []
        for name, config in configs:
            logger.info(f"評価中: {name}")

            latencies = []
            result_counts = []

            for query in all_queries:
                start = time.perf_counter()
                search_results = self.searcher.search(query, top_k=10, config=config)
                elapsed = (time.perf_counter() - start) * 1000
                latencies.append(elapsed)
                result_counts.append(len(search_results))

            latencies.sort()
            results.append(AblationResult(
                config_name=name,
                avg_latency_ms=round(statistics.mean(latencies), 2),
                p50_latency_ms=round(latencies[len(latencies) // 2], 2),
                p95_latency_ms=round(latencies[int(len(latencies) * 0.95)], 2),
                avg_results=round(statistics.mean(result_counts), 2),
            ))

        return results

    def run_full_evaluation(self) -> EvaluationReport:
        """完全評価実行"""
        import datetime

        # 1. インデックス統計
        logger.info("=" * 60)
        logger.info("インデックス統計取得中...")
        index_stats = self.get_index_stats()
        logger.info(f"ベクトル: {index_stats['vector_count']:,}件")
        logger.info(f"BM25: {index_stats['bm25_doc_count']:,}件")

        # 2. ウォームアップ
        self.warmup()

        # 3. アブレーション評価
        logger.info("=" * 60)
        logger.info("アブレーション評価中...")
        ablation_results = self.ablation_study()

        for r in ablation_results:
            logger.info(f"  {r.config_name}: avg={r.avg_latency_ms}ms, p95={r.p95_latency_ms}ms")

        # 4. 詳細クエリ評価（フル構成）
        logger.info("=" * 60)
        logger.info("詳細クエリ評価中...")
        config = SearchConfig(use_bm25=True, use_rerank=True)
        query_results = self.evaluate_queries(config)

        # カテゴリ別集計
        category_stats = {}
        for r in query_results:
            if r.category not in category_stats:
                category_stats[r.category] = []
            category_stats[r.category].append(r.latency_ms)

        for cat, latencies in category_stats.items():
            avg = statistics.mean(latencies)
            logger.info(f"  {cat}: avg={avg:.1f}ms")

        # 5. 全体パフォーマンス
        all_latencies = [r.latency_ms for r in query_results]
        performance = {
            "total_queries": len(query_results),
            "avg_latency_ms": round(statistics.mean(all_latencies), 2),
            "p50_latency_ms": round(sorted(all_latencies)[len(all_latencies) // 2], 2),
            "p95_latency_ms": round(sorted(all_latencies)[int(len(all_latencies) * 0.95)], 2),
            "min_latency_ms": round(min(all_latencies), 2),
            "max_latency_ms": round(max(all_latencies), 2),
            "category_stats": {k: round(statistics.mean(v), 2) for k, v in category_stats.items()},
        }

        logger.info("=" * 60)
        logger.info("評価完了")
        logger.info(f"全クエリ: avg={performance['avg_latency_ms']}ms, p95={performance['p95_latency_ms']}ms")

        return EvaluationReport(
            timestamp=datetime.datetime.now().isoformat(),
            index_stats=index_stats,
            performance=performance,
            ablation=[asdict(r) for r in ablation_results],
            query_results=[asdict(r) for r in query_results],
        )


def print_report(report: EvaluationReport) -> None:
    """レポート出力"""
    print("\n" + "=" * 70)
    print("           ハイブリッド検索システム 評価レポート")
    print("=" * 70)

    print("\n【インデックス統計】")
    stats = report.index_stats
    print(f"  ベクトル数:     {stats['vector_count']:>12,} 件")
    print(f"  メタデータ数:   {stats['metadata_count']:>12,} 件")
    print(f"  BM25文書数:     {stats['bm25_doc_count']:>12,} 件")
    print(f"  ファイル数:     {stats['file_count']:>12,} 件")
    print(f"  IVF-PQ訓練済み: {str(stats['is_trained']):>12}")

    print("\n【アブレーション評価】")
    print("-" * 70)
    print(f"{'構成':<30} {'平均(ms)':>10} {'P50(ms)':>10} {'P95(ms)':>10}")
    print("-" * 70)
    for r in report.ablation:
        print(f"{r['config_name']:<30} {r['avg_latency_ms']:>10.1f} {r['p50_latency_ms']:>10.1f} {r['p95_latency_ms']:>10.1f}")

    print("\n【カテゴリ別レイテンシ】")
    print("-" * 70)
    for cat, avg in report.performance['category_stats'].items():
        print(f"  {cat:<35} {avg:>8.1f} ms")

    print("\n【全体パフォーマンス】")
    perf = report.performance
    print(f"  総クエリ数: {perf['total_queries']}")
    print(f"  平均:  {perf['avg_latency_ms']:>8.1f} ms")
    print(f"  P50:   {perf['p50_latency_ms']:>8.1f} ms")
    print(f"  P95:   {perf['p95_latency_ms']:>8.1f} ms")
    print(f"  Min:   {perf['min_latency_ms']:>8.1f} ms")
    print(f"  Max:   {perf['max_latency_ms']:>8.1f} ms")

    print("\n【サンプル検索結果】")
    print("-" * 70)
    # 各カテゴリから1つずつ
    shown_categories = set()
    for r in report.query_results:
        if r['category'] not in shown_categories and len(shown_categories) < 5:
            shown_categories.add(r['category'])
            print(f"\n  クエリ: 「{r['query']}」 ({r['category']})")
            print(f"  レイテンシ: {r['latency_ms']:.1f}ms, 結果数: {r['num_results']}")
            print("  上位3件:")
            for i, (f, s) in enumerate(zip(r['top_files'][:3], r['top_scores'][:3])):
                print(f"    {i+1}. [{s:.3f}] {f}...")

    print("\n" + "=" * 70)


def main():
    evaluator = Evaluator()
    report = evaluator.run_full_evaluation()

    # レポート出力
    print_report(report)

    # JSON保存
    output_path = Path("embeddings/evaluation_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    logger.info(f"レポート保存: {output_path}")


if __name__ == "__main__":
    main()

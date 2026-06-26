"""
触发 knowledge_indexer.rebuild_index() 把 multihop-news 下文章建进向量+BM25 索引。

用法:
    cd backend
    python scripts/build_multihop_index.py
"""
from __future__ import annotations

import io
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_retrieval.indexer import knowledge_indexer  # noqa: E402


def main() -> None:
    print("=" * 60)
    print("建立向量+BM25 索引")
    print("=" * 60)

    print(f"\n[1/3] 配置 indexer ...")
    knowledge_indexer.configure(PROJECT_ROOT)

    print(f"\n[2/3] 触发全量重建 ...")
    print(f"  • 知识库目录: {PROJECT_ROOT / 'knowledge'}")
    md_count = sum(1 for _ in (PROJECT_ROOT / "knowledge").rglob("*.md"))
    json_count = sum(1 for _ in (PROJECT_ROOT / "knowledge").rglob("*.json"))
    print(f"  • 待索引文件: {md_count} 个 .md, {json_count} 个 .json")
    print(f"  • 这一步会调 embedding API,可能花 5~15 分钟,请等待 ...")

    t0 = time.time()
    knowledge_indexer.rebuild_index()
    elapsed = time.time() - t0

    print(f"\n[3/3] 完成! 耗时 {elapsed:.1f} 秒")
    status = knowledge_indexer.status()
    print(f"  • indexed_files: {status.indexed_files}")
    print(f"  • vector_ready: {status.vector_ready}")
    print(f"  • bm25_ready: {status.bm25_ready}")

    # 快速 smoke test
    print(f"\n[smoke test] 测试一条检索 ...")
    test_q = "Sam Bankman-Fried FTX trial"
    vector_evidences = knowledge_indexer.retrieve_vector(test_q, top_k=3)
    bm25_evidences = knowledge_indexer.retrieve_bm25(test_q, top_k=3)
    print(f"  • vector hits: {len(vector_evidences)}")
    for ev in vector_evidences[:3]:
        print(f"      - {ev.source_path} ({ev.locator})")
    print(f"  • bm25 hits: {len(bm25_evidences)}")
    for ev in bm25_evidences[:3]:
        print(f"      - {ev.source_path} ({ev.locator})")

    print("\n" + "=" * 60)
    print("✅ 索引建立完成,可以运行评估脚本")
    print("=" * 60)


if __name__ == "__main__":
    main()

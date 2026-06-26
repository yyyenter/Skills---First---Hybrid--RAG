"""
对比纯 RAG vs Skill+RAG 的检索准确率（MultiHop-RAG 数据集）

两种配置：
  A) pure_rag: 关掉 Skill，直接走 hybrid_retriever（向量 + BM25）
  B) with_skill: 走完整 orchestrator（Skill -> 不够 -> hybrid -> RRF 融合）

指标:
  - Hit@5 / Hit@10  : 前 K 条至少命中一篇标注文章
  - Recall@K        : 前 K 条覆盖标注文章的比例
  - MRR             : Mean Reciprocal Rank

用法:
    cd backend
    python scripts/evaluate_skill_vs_rag.py [--limit N] [--config A|B|both]
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import sys
import time
import traceback
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_retrieval.hybrid_retriever import hybrid_retriever  # noqa: E402
from knowledge_retrieval.indexer import knowledge_indexer  # noqa: E402
from knowledge_retrieval.orchestrator import knowledge_orchestrator  # noqa: E402
from knowledge_retrieval.skill_retriever_agent import skill_retriever_agent  # noqa: E402
from graph.agent import AgentManager  # noqa: E402

SAMPLE_PATH = Path(__file__).resolve().parent / "multihop_sample.json"
RESULT_PATH = Path(__file__).resolve().parent / "multihop_eval_result.json"


# ---------- 评估指标 ----------

def hit_at_k(retrieved_paths: list[str], gt_paths: set[str], k: int) -> int:
    return int(any(p in gt_paths for p in retrieved_paths[:k]))


def recall_at_k(retrieved_paths: list[str], gt_paths: set[str], k: int) -> float:
    if not gt_paths:
        return 1.0
    hits = sum(1 for gt in gt_paths if gt in retrieved_paths[:k])
    return hits / len(gt_paths)


def mrr(retrieved_paths: list[str], gt_paths: set[str]) -> float:
    for rank, p in enumerate(retrieved_paths, start=1):
        if p in gt_paths:
            return 1.0 / rank
    return 0.0


def dedupe_paths(evidences) -> list[str]:
    """从 Evidence 列表里去重得到文件路径序列(保持顺序)"""
    seen = set()
    out: list[str] = []
    for ev in evidences:
        path = ev.source_path if hasattr(ev, "source_path") else ev.get("source_path", "")
        if path and path not in seen:
            seen.add(path)
            out.append(path)
    return out


# ---------- 配置 A: 纯 RAG ----------

async def retrieve_pure_rag(query: str) -> dict:
    t0 = time.time()
    result = hybrid_retriever.retrieve(query, top_k=10)
    elapsed = time.time() - t0

    # 简单合并:vector + bm25 交叉去重得到 top 10
    seen = set()
    merged_paths: list[str] = []
    for ev in result.vector_evidences + result.bm25_evidences:
        if ev.source_path not in seen:
            seen.add(ev.source_path)
            merged_paths.append(ev.source_path)

    return {
        "retrieved_paths": merged_paths[:10],
        "vector_paths": dedupe_paths(result.vector_evidences),
        "bm25_paths": dedupe_paths(result.bm25_evidences),
        "elapsed": elapsed,
    }


# ---------- 配置 B: Skill + RAG ----------

async def retrieve_with_skill(query: str) -> dict:
    t0 = time.time()
    skill_paths: list[str] = []
    fused_paths: list[str] = []
    final_paths: list[str] = []
    fallback_used = False
    skill_status = "uncertain"
    skill_reason = ""
    error = None

    try:
        async for event in knowledge_orchestrator.astream(query):
            etype = event.get("type")
            if etype == "retrieval":
                stage = event.get("stage")
                results = event.get("results", []) or []
                if stage == "skill":
                    skill_paths = dedupe_paths(results)
                elif stage == "fused":
                    fused_paths = dedupe_paths(results)
            elif etype == "orchestrated_result":
                result = event["result"]
                final_paths = dedupe_paths(result.evidences)
                fallback_used = result.fallback_used
                skill_status = result.status
                skill_reason = result.reason
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        traceback.print_exc()

    elapsed = time.time() - t0
    return {
        "retrieved_paths": final_paths[:10],
        "skill_paths": skill_paths,
        "fused_paths": fused_paths,
        "fallback_used": fallback_used,
        "skill_status": skill_status,
        "skill_reason": skill_reason,
        "elapsed": elapsed,
        "error": error,
    }


# ---------- 主流程 ----------

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="只跑前 N 条(用于快速验证)，0 = 全部")
    parser.add_argument("--config", choices=["A", "B", "both"], default="both",
                        help="A=只跑纯 RAG, B=只跑 Skill+RAG, both=两个都跑")
    args = parser.parse_args()

    print("=" * 70)
    print("MultiHop-RAG 评估：纯 RAG vs Skill+RAG")
    print("=" * 70)

    # 加载采样集
    sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    queries = sample["queries"]
    title_to_path = sample["title_to_path"]
    if args.limit > 0:
        queries = queries[: args.limit]

    print(f"\n采样: {len(queries)} 条 query")
    print(f"标注文章: {len(title_to_path)} 篇")

    # 配置 indexer + orchestrator(Skill Agent 需要 model_builder)
    knowledge_indexer.configure(PROJECT_ROOT)
    am = AgentManager()
    am.initialize(PROJECT_ROOT)  # 这个会同时配置 orchestrator + skill agent

    print(f"\n索引状态: vector_ready={knowledge_indexer.status().vector_ready}, "
          f"bm25_ready={knowledge_indexer.status().bm25_ready}")

    # 跑评估
    results_a: list[dict] = []
    results_b: list[dict] = []

    for i, q in enumerate(queries):
        query = q["query"]
        gt_titles = q["ground_truth_titles"]
        gt_paths = {title_to_path[t] for t in gt_titles if t in title_to_path}

        print(f"\n[{i+1}/{len(queries)}] [{q['question_type']}] {query[:80]}", flush=True)
        print(f"  GT: {len(gt_paths)} 篇 - {[Path(p).stem[:30] for p in gt_paths]}", flush=True)

        # 配置 A
        if args.config in ("A", "both"):
            r_a = await retrieve_pure_rag(query)
            r_a.update({
                "id": q["id"],
                "query": query,
                "question_type": q["question_type"],
                "ground_truth_paths": list(gt_paths),
                "hit@5": hit_at_k(r_a["retrieved_paths"], gt_paths, 5),
                "hit@10": hit_at_k(r_a["retrieved_paths"], gt_paths, 10),
                "recall@5": recall_at_k(r_a["retrieved_paths"], gt_paths, 5),
                "recall@10": recall_at_k(r_a["retrieved_paths"], gt_paths, 10),
                "mrr": mrr(r_a["retrieved_paths"], gt_paths),
            })
            results_a.append(r_a)
            print(f"  A pure_rag : hit@5={r_a['hit@5']} recall@10={r_a['recall@10']:.2f} "
                  f"MRR={r_a['mrr']:.3f} ({r_a['elapsed']:.1f}s)", flush=True)

        # 配置 B
        if args.config in ("B", "both"):
            r_b = await retrieve_with_skill(query)
            r_b.update({
                "id": q["id"],
                "query": query,
                "question_type": q["question_type"],
                "ground_truth_paths": list(gt_paths),
                "hit@5": hit_at_k(r_b["retrieved_paths"], gt_paths, 5),
                "hit@10": hit_at_k(r_b["retrieved_paths"], gt_paths, 10),
                "recall@5": recall_at_k(r_b["retrieved_paths"], gt_paths, 5),
                "recall@10": recall_at_k(r_b["retrieved_paths"], gt_paths, 10),
                "mrr": mrr(r_b["retrieved_paths"], gt_paths),
            })
            results_b.append(r_b)
            print(f"  B skill+rag: hit@5={r_b['hit@5']} recall@10={r_b['recall@10']:.2f} "
                  f"MRR={r_b['mrr']:.3f} status={r_b['skill_status']} "
                  f"fallback={r_b['fallback_used']} ({r_b['elapsed']:.1f}s)", flush=True)

        # 每条都立即落盘 - 极端情况零数据丢失
        _save_results(results_a, results_b, sample)

    _print_summary(results_a, results_b)


def _save_results(results_a: list[dict], results_b: list[dict], sample: dict) -> None:
    payload = {
        "sample_meta": {
            "seed": sample.get("seed"),
            "sample_size": sample.get("sample_size"),
            "sample_per_type": sample.get("sample_per_type"),
        },
        "pure_rag": results_a,
        "with_skill": results_b,
    }
    RESULT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _avg(values: list[float]) -> float:
    return sum(values) / max(1, len(values))


def _print_summary(results_a: list[dict], results_b: list[dict]) -> None:
    print("\n" + "=" * 70)
    print("评估汇总")
    print("=" * 70)

    for label, results in (("A pure_rag   ", results_a), ("B skill+rag  ", results_b)):
        if not results:
            continue
        # 整体
        n = len(results)
        h5 = _avg([r["hit@5"] for r in results])
        h10 = _avg([r["hit@10"] for r in results])
        r5 = _avg([r["recall@5"] for r in results])
        r10 = _avg([r["recall@10"] for r in results])
        m = _avg([r["mrr"] for r in results])
        elapsed = _avg([r["elapsed"] for r in results])

        print(f"\n>> {label} (n={n})")
        print(f"   Hit@5    : {h5:.3f}")
        print(f"   Hit@10   : {h10:.3f}")
        print(f"   Recall@5 : {r5:.3f}")
        print(f"   Recall@10: {r10:.3f}")
        print(f"   MRR      : {m:.3f}")
        print(f"   平均耗时 : {elapsed:.2f}s")

    # 按类型拆解
    if results_a and results_b:
        print(f"\n>> 按 query 类型拆解 (Hit@5)")
        types = sorted(set(r["question_type"] for r in results_a))
        print(f"   {'类型':<22} {'pure_rag':>10} {'skill+rag':>11} {'增益':>10}")
        for qtype in types:
            ra = [r for r in results_a if r["question_type"] == qtype]
            rb = [r for r in results_b if r["question_type"] == qtype]
            ha = _avg([r["hit@5"] for r in ra])
            hb = _avg([r["hit@5"] for r in rb])
            delta = hb - ha
            print(f"   {qtype:<22} {ha:>10.3f} {hb:>11.3f} {delta:>+10.3f}")

    # Skill 自评校准
    if results_b:
        print(f"\n>> Skill 自评估校准")
        success_rows = [r for r in results_b if r.get("skill_status") == "success"]
        partial_rows = [r for r in results_b if r.get("skill_status") == "partial"]
        not_found_rows = [r for r in results_b if r.get("skill_status") == "not_found"]
        uncertain_rows = [r for r in results_b if r.get("skill_status") == "uncertain"]
        fallback_rows = [r for r in results_b if r.get("fallback_used")]

        print(f"   status=success : {len(success_rows)}/{len(results_b)} "
              f"-> hit@5 = {_avg([r['hit@5'] for r in success_rows]):.3f} (越接近 1 越好)")
        print(f"   status=partial : {len(partial_rows)}/{len(results_b)}")
        print(f"   status=not_found: {len(not_found_rows)}/{len(results_b)}")
        print(f"   status=uncertain: {len(uncertain_rows)}/{len(results_b)}")
        print(f"   fallback 触发率: {len(fallback_rows)}/{len(results_b)} "
              f"= {len(fallback_rows)/max(1,len(results_b)):.1%}")

    print(f"\n详细结果: {RESULT_PATH.relative_to(PROJECT_ROOT)}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

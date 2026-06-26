#!/usr/bin/env python3
"""
Legal RAG Evaluation: Baseline vs Skill-First

Compare retrieval quality between:
- Baseline: direct hybrid (vector + BM25) retrieval
- Skill-First: LLM reads SKILL.md, decides routing & tools, then retrieves

Usage:
    cd backend
    python scripts/eval_legal_skills.py

Rate-limiting: sleeps 15s between questions (~4 RPM safe for GLM-4.7-Flash free tier)
                     Internal tool chains add 2-4 extra calls per question.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from config import get_settings
from graph.agent import agent_manager
from knowledge_retrieval.hybrid_retriever import hybrid_retriever
from knowledge_retrieval.indexer import knowledge_indexer
from knowledge_retrieval.skill_retriever_agent import skill_retriever_agent

# ---------------------------------------------------------------------------
# 20 Legal questions with expected skill & ground-truth documents
# ---------------------------------------------------------------------------
EVAL_QUESTIONS: list[dict[str, Any]] = [
    # --- Statute Search (法条检索) ---
    {
        "id": 1,
        "question": "合同编中，当事人应当按照什么原则履行合同义务？",
        "expected_skill": "statute_search",
        "ground_truth_paths": ["knowledge/legal/statutes/contract_law_articles.md"],
        "key_answer": "全面履行、诚信原则",
    },
    {
        "id": 2,
        "question": "什么情况下当事人可以法定解除合同？",
        "expected_skill": "statute_search",
        "ground_truth_paths": ["knowledge/legal/statutes/contract_law_articles.md"],
        "key_answer": "不可抗力、预期违约、迟延履行",
    },
    {
        "id": 3,
        "question": "民法典对合同订立的形式有哪些规定？",
        "expected_skill": "statute_search",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "书面形式、口头形式、其他形式",
    },
    {
        "id": 4,
        "question": "依法成立的合同对谁具有法律约束力？",
        "expected_skill": "statute_search",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "仅对当事人具有法律约束力",
    },
    {
        "id": 5,
        "question": "民法典合同编调整什么范围的民事关系？",
        "expected_skill": "statute_search",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "因合同产生的民事关系",
    },
    # --- Case Search (判例检索) ---
    {
        "id": 6,
        "question": "指导案例1号中，法院认为什么情况下买方不构成跳单违约？",
        "expected_skill": "case_search",
        "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
        "key_answer": "通过其他公众可以获知的正当途径获得相同房源信息",
    },
    {
        "id": 7,
        "question": "上海中原物业顾问有限公司诉陶德华案的裁判结果是什么？",
        "expected_skill": "case_search",
        "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
        "key_answer": "驳回原告诉讼请求，维持原判",
    },
    {
        "id": 8,
        "question": "居间合同中的禁止跳单条款效力如何认定？",
        "expected_skill": "case_search",
        "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
        "key_answer": "合法有效",
    },
    {
        "id": 9,
        "question": "陶德华案的一审法院是哪个？",
        "expected_skill": "case_search",
        "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
        "key_answer": "上海市虹口区人民法院",
    },
    {
        "id": 10,
        "question": "陶德华案中的关键争议焦点是什么？",
        "expected_skill": "case_search",
        "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
        "key_answer": "是否利用中原公司信息绕开中介成交",
    },
    # --- Contract Clause (合同条款) ---
    {
        "id": 11,
        "question": "LIMEENERGYCO分销商协议的期限是多长？",
        "expected_skill": "contract_clause",
        "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
        "key_answer": "10年",
    },
    {
        "id": 12,
        "question": "分销商在哪个区域有独家分销权？",
        "expected_skill": "contract_clause",
        "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
        "key_answer": "伊利诺伊州",
    },
    {
        "id": 13,
        "question": "分销商协议中，公司授予分销商使用什么名称的权利？",
        "expected_skill": "contract_clause",
        "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
        "key_answer": "Electric City of Illinois",
    },
    {
        "id": 14,
        "question": "分销商是否有权将名称使用权再许可给第三方？",
        "expected_skill": "contract_clause",
        "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
        "key_answer": "无权",
    },
    {
        "id": 15,
        "question": "分销商协议的续期条件是什么？",
        "expected_skill": "contract_clause",
        "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
        "key_answer": "遵守所有条款，每年可续",
    },
    # --- Legal Definition (法律定义) ---
    {
        "id": 16,
        "question": "民法典中，什么是合同？",
        "expected_skill": "legal_definition",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "民事主体之间设立、变更、终止民事法律关系的协议",
    },
    {
        "id": 17,
        "question": "当事人对合同条款理解有争议时，应如何确定条款含义？",
        "expected_skill": "legal_definition",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "依据本法第一百四十二条第一款的规定确定",
    },
    {
        "id": 18,
        "question": "非因合同产生的债权债务关系适用什么规定？",
        "expected_skill": "legal_definition",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "适用有关法律规定；没有规定的适用本编通则",
    },
    {
        "id": 19,
        "question": "书面形式包括哪些具体类型？",
        "expected_skill": "legal_definition",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "合同书、信件、电报、电传、传真、数据电文",
    },
    {
        "id": 20,
        "question": "民法典合同编通则适用于什么情况？",
        "expected_skill": "legal_definition",
        "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
        "key_answer": "本法或者其他法律没有明文规定的合同",
    },
]


# ---------------------------------------------------------------------------
# Baseline retrieval (no skill, direct hybrid)
# ---------------------------------------------------------------------------
def baseline_retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Pure hybrid retrieval without any skill guidance."""
    result = hybrid_retriever.retrieve(
        query,
        top_k=top_k,
        path_filters=["knowledge/legal/"],
    )
    evidences = []
    for ev in result.vector_evidences + result.bm25_evidences:
        evidences.append({
            "source_path": ev.source_path,
            "snippet": ev.snippet[:200],
            "score": ev.score,
            "channel": ev.channel,
        })
    # Deduplicate by path
    seen = set()
    deduped = []
    for ev in evidences:
        if ev["source_path"] not in seen:
            seen.add(ev["source_path"])
            deduped.append(ev)
    return deduped[:top_k]


# ---------------------------------------------------------------------------
# Skill-First retrieval (LLM reads SKILL.md + decides tools)
# ---------------------------------------------------------------------------
async def skill_retrieve(query: str, top_k: int = 5, max_retries: int = 2) -> dict[str, Any]:
    """Skill-First retrieval: LLM reads SKILL.md, routes, then retrieves.
    Retries on 429 rate-limit or 1113 quota errors with exponential backoff."""
    for attempt in range(max_retries + 1):
        collected = []
        skill_result = None
        try:
            async for event in skill_retriever_agent.astream(query):
                if event.get("type") == "skill_result":
                    skill_result = event["result"]
                collected.append(event)
        except Exception as exc:
            msg = str(exc)
            # Zhipu rate-limit (1113=quota, 429=too many requests)
            if "1113" in msg or "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
                if attempt < max_retries:
                    wait = 20 + attempt * 10
                    print(f"    [RateLimit] attempt {attempt + 1}/{max_retries + 1}, sleep {wait}s...")
                    time.sleep(wait)
                    continue
            return {"error": msg, "evidences": [], "status": "error"}

        if skill_result is None:
            return {"error": "No skill_result", "evidences": [], "status": "no_result"}
        break

    evidences = []
    for ev in skill_result.get("evidences", [])[:top_k]:
        evidences.append({
            "source_path": ev.get("source_path", ""),
            "snippet": ev.get("snippet", "")[:200],
            "score": ev.get("score"),
            "channel": "skill",
        })
    return {
        "status": skill_result.get("status", "unknown"),
        "evidences": evidences,
        "narrowed_paths": skill_result.get("narrowed_paths", []),
        "rewritten_queries": skill_result.get("rewritten_queries", []),
        "reason": skill_result.get("reason", ""),
    }

    evidences = []
    for ev in skill_result.get("evidences", [])[:top_k]:
        evidences.append({
            "source_path": ev.get("source_path", ""),
            "snippet": ev.get("snippet", "")[:200],
            "score": ev.get("score"),
            "channel": "skill",
        })
    return {
        "status": skill_result.get("status", "unknown"),
        "evidences": evidences,
        "narrowed_paths": skill_result.get("narrowed_paths", []),
        "rewritten_queries": skill_result.get("rewritten_queries", []),
        "reason": skill_result.get("reason", ""),
    }


# ---------------------------------------------------------------------------
# Evaluation metrics
# ---------------------------------------------------------------------------
def check_recall(retrieved_paths: list[str], ground_truth_paths: list[str]) -> bool:
    """Return True if any ground-truth doc appears in retrieved docs."""
    normalized_gt = {p.replace("\\", "/") for p in ground_truth_paths}
    normalized_ret = {p.replace("\\", "/") for p in retrieved_paths}
    return bool(normalized_gt & normalized_ret)


def evaluate_answer(retrieved_snippets: str, key_answer: str) -> dict[str, Any]:
    """Simple keyword-based answer check (heuristic)."""
    # Heuristic: count how many key terms appear in retrieved text
    terms = [t.strip() for t in key_answer.replace("。", "").replace("、", "").split("，") if len(t.strip()) > 1]
    hits = sum(1 for t in terms if t in retrieved_snippets)
    return {
        "terms_total": len(terms),
        "terms_hit": hits,
        "partial_score": hits / max(1, len(terms)),
    }


# ---------------------------------------------------------------------------
# Main evaluation loop
# ---------------------------------------------------------------------------
async def main() -> None:
    settings = get_settings()
    print(f"[Config] LLM: {settings.llm_provider}/{settings.llm_model}")
    print(f"[Config] Embedding: {settings.embedding_provider}/{settings.embedding_model}")
    print()

    # Initialize backend (loads index, NO rebuild)
    agent_manager.initialize(settings.backend_dir)
    knowledge_indexer.configure(settings.backend_dir)
    knowledge_indexer._load_manifest()
    knowledge_indexer._load_vector_index()
    skill_retriever_agent.configure(settings.backend_dir, agent_manager._build_chat_model)

    status = knowledge_indexer.status()
    print(f"[Index] docs={len(knowledge_indexer._documents)}, "
          f"vector_ready={status.vector_ready}, bm25_ready={status.bm25_ready}")
    print(f"[Eval ] {len(EVAL_QUESTIONS)} questions, sleep=15s between queries")
    print("-" * 80)

    results = []
    for i, q in enumerate(EVAL_QUESTIONS, 1):
        qid = q["id"]
        question = q["question"]
        print(f"\n[{i}/{len(EVAL_QUESTIONS)}] Q{qid}: {question}")

        # --- Baseline ---
        baseline_evs = baseline_retrieve(question, top_k=5)
        baseline_paths = [e["source_path"] for e in baseline_evs]
        baseline_snippets = "\n".join(e["snippet"] for e in baseline_evs)
        baseline_recall = check_recall(baseline_paths, q["ground_truth_paths"])
        baseline_answer = evaluate_answer(baseline_snippets, q["key_answer"])
        print(f"  [Baseline] recall={baseline_recall}, "
              f"paths={len(baseline_paths)}, "
              f"answer_score={baseline_answer['partial_score']:.2f}")

        # --- Skill-First ---
        skill_res = await skill_retrieve(question, top_k=5)
        if "error" in skill_res:
            print(f"  [Skill] ERROR: {skill_res['error']}")
            skill_paths = []
            skill_snippets = ""
            skill_recall = False
            skill_answer = {"partial_score": 0.0}
            skill_status = "error"
        else:
            skill_paths = [e["source_path"] for e in skill_res["evidences"]]
            skill_snippets = "\n".join(e["snippet"] for e in skill_res["evidences"])
            skill_recall = check_recall(skill_paths, q["ground_truth_paths"])
            skill_answer = evaluate_answer(skill_snippets, q["key_answer"])
            skill_status = skill_res["status"]
            print(f"  [Skill] status={skill_status}, recall={skill_recall}, "
                  f"paths={len(skill_paths)}, "
                  f"answer_score={skill_answer['partial_score']:.2f}")
            if skill_res.get("rewritten_queries"):
                print(f"          rewritten={skill_res['rewritten_queries']}")

        results.append({
            "id": qid,
            "question": question,
            "expected_skill": q["expected_skill"],
            "baseline_recall": baseline_recall,
            "baseline_answer_score": baseline_answer["partial_score"],
            "skill_recall": skill_recall,
            "skill_answer_score": skill_answer["partial_score"],
            "skill_status": skill_status if "error" not in skill_res else "error",
            "baseline_paths": baseline_paths,
            "skill_paths": skill_paths,
        })

        # Rate limiting: sleep between questions (GLM-4.7-Flash free tier ~4 RPM)
        if i < len(EVAL_QUESTIONS):
            print("  [Sleep] 15s...")
            time.sleep(15)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)

    total = len(results)
    baseline_recalls = sum(1 for r in results if r["baseline_recall"])
    skill_recalls = sum(1 for r in results if r["skill_recall"])
    baseline_avg_score = sum(r["baseline_answer_score"] for r in results) / total
    skill_avg_score = sum(r["skill_answer_score"] for r in results) / total

    print(f"\nTotal Questions: {total}")
    print(f"\n[Retrieval Recall@5]")
    print(f"  Baseline : {baseline_recalls}/{total} = {baseline_recalls/total*100:.1f}%")
    print(f"  Skill    : {skill_recalls}/{total} = {skill_recalls/total*100:.1f}%")
    print(f"  Improvement: +{(skill_recalls - baseline_recalls)/total*100:.1f}pp")

    print(f"\n[Answer Keyword Score (heuristic)]")
    print(f"  Baseline : {baseline_avg_score:.3f}")
    print(f"  Skill    : {skill_avg_score:.3f}")
    print(f"  Improvement: +{(skill_avg_score - baseline_avg_score)*100:.1f}%")

    # Per-skill breakdown
    print(f"\n[Per-Skill Breakdown]")
    for skill_name in ["statute_search", "case_search", "contract_clause", "legal_definition"]:
        skill_qs = [r for r in results if r["expected_skill"] == skill_name]
        if not skill_qs:
            continue
        b_rec = sum(1 for r in skill_qs if r["baseline_recall"])
        s_rec = sum(1 for r in skill_qs if r["skill_recall"])
        print(f"  {skill_name:20s}: Baseline={b_rec}/{len(skill_qs)} Skill={s_rec}/{len(skill_qs)}")

    # Save results
    out_path = settings.backend_dir / "eval_legal_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Saved] {out_path}")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Quick test: first 5 questions only."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from config import get_settings
from graph.agent import agent_manager
from knowledge_retrieval.hybrid_retriever import hybrid_retriever
from knowledge_retrieval.indexer import knowledge_indexer
from knowledge_retrieval.skill_retriever_agent import skill_retriever_agent
from knowledge_retrieval.orchestrator import knowledge_orchestrator

QUESTIONS = [
    {"id": 1, "question": "合同编中，当事人应当按照什么原则履行合同义务？", "ground_truth_paths": ["knowledge/legal/statutes/contract_law_articles.md"], "key_answer": "全面履行、诚信原则"},
    {"id": 6, "question": "指导案例1号中，法院认为什么情况下买方不构成跳单违约？", "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"], "key_answer": "通过其他公众可以获知的正当途径获得相同房源信息"},
    {"id": 11, "question": "LIMEENERGYCO分销商协议的期限是多长？", "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"], "key_answer": "10年"},
    {"id": 16, "question": "民法典中，什么是合同？", "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"], "key_answer": "民事主体之间设立、变更、终止民事法律关系的协议"},
    {"id": 2, "question": "什么情况下当事人可以法定解除合同？", "ground_truth_paths": ["knowledge/legal/statutes/contract_law_articles.md"], "key_answer": "不可抗力、预期违约、迟延履行"},
]


def baseline_retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    result = hybrid_retriever.retrieve(query, top_k=top_k, path_filters=["knowledge/legal/"])
    evidences = []
    for ev in result.vector_evidences + result.bm25_evidences:
        evidences.append({"source_path": ev.source_path, "snippet": ev.snippet[:200], "score": ev.score, "channel": ev.channel})
    seen = set()
    deduped = []
    for ev in evidences:
        if ev["source_path"] not in seen:
            seen.add(ev["source_path"])
            deduped.append(ev)
    return deduped[:top_k]


async def skill_retrieve(query: str, top_k: int = 5, max_retries: int = 2) -> dict[str, Any]:
    """Full Skill-First + Fallback + RRF fusion via orchestrator."""
    for attempt in range(max_retries + 1):
        orchestrated = None
        try:
            async for event in knowledge_orchestrator.astream(query):
                if event.get("type") == "orchestrated_result":
                    orchestrated = event["result"]
        except Exception as exc:
            msg = str(exc)
            if "1113" in msg or "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
                if attempt < max_retries:
                    wait = 20 + attempt * 10
                    print(f"    [RateLimit] attempt {attempt + 1}/{max_retries + 1}, sleep {wait}s...")
                    time.sleep(wait)
                    continue
            return {"error": msg, "evidences": [], "status": "error"}

        if orchestrated is None:
            return {"error": "No orchestrated_result", "evidences": [], "status": "no_result"}
        break

    evidences = []
    for ev in orchestrated.evidences[:top_k]:
        evidences.append({
            "source_path": ev.source_path,
            "snippet": ev.snippet[:200],
            "score": ev.score,
            "channel": ev.channel,
        })
    return {
        "status": orchestrated.status,
        "evidences": evidences,
        "fallback_used": orchestrated.fallback_used,
        "reason": orchestrated.reason,
    }


def check_recall(retrieved_paths: list[str], ground_truth_paths: list[str]) -> bool:
    normalized_gt = {p.replace("\\", "/") for p in ground_truth_paths}
    normalized_ret = {p.replace("\\", "/") for p in retrieved_paths}
    return bool(normalized_gt & normalized_ret)


async def main() -> None:
    settings = get_settings()
    print(f"[Config] LLM: {settings.llm_provider}/{settings.llm_model}")
    agent_manager.initialize(settings.backend_dir)
    knowledge_indexer.configure(settings.backend_dir)
    knowledge_indexer._load_manifest()
    knowledge_indexer._load_vector_index()
    skill_retriever_agent.configure(settings.backend_dir, agent_manager._build_chat_model)
    print(f"[Index] {len(knowledge_indexer._documents)} docs, vector={knowledge_indexer._vector_ready}, bm25={knowledge_indexer._bm25_ready}")

    for i, q in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}] Q{q['id']}: {q['question']}")

        base = baseline_retrieve(q["question"], top_k=5)
        base_paths = [e["source_path"] for e in base]
        print(f"  [Baseline] recall={check_recall(base_paths, q['ground_truth_paths'])}, paths={base_paths}")

        skill = await skill_retrieve(q["question"], top_k=5)
        if "error" in skill:
            print(f"  [Skill+RRF] ERROR: {skill['error']}")
        else:
            skill_paths = [e["source_path"] for e in skill["evidences"]]
            fb = "(fallback+RRF)" if skill.get("fallback_used") else "(skill-only)"
            print(f"  [Skill+RRF] status={skill['status']} {fb}, recall={check_recall(skill_paths, q['ground_truth_paths'])}, paths={skill_paths}")

        if i < len(QUESTIONS):
            print("  [Sleep] 15s...")
            time.sleep(15)

    print("\n[Done]")


if __name__ == "__main__":
    asyncio.run(main())

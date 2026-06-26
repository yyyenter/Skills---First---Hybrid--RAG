"""
准备 MultiHop-RAG 评估数据：
  1. 从 MultiHopRAG.json 各类型均衡抽样 30 条 query
  2. 找出这些 query 涉及的所有标注文章
  3. 把这些文章从 corpus.json 写入 backend/knowledge/multihop-news/ 作为 .md
  4. 保存采样集到 backend/scripts/multihop_sample.json，供评估脚本读取

用法：
    cd backend
    python scripts/prepare_multihop_eval.py
"""
from __future__ import annotations

import io
import json
import random
import re
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows (zh-CN GBK by default)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


DATASET_DIR = Path("E:/Python/MultiHop-RAG/dataset")
QUERIES_PATH = DATASET_DIR / "MultiHopRAG.json"
CORPUS_PATH = DATASET_DIR / "corpus.json"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NEWS_DIR = PROJECT_ROOT / "knowledge" / "multihop-news"
SAMPLE_PATH = Path(__file__).resolve().parent / "multihop_sample.json"

# 各类型采样数量（合计 30）
SAMPLE_PER_TYPE = {
    "inference_query": 10,
    "comparison_query": 10,
    "temporal_query": 7,
    "null_query": 3,
}
SEED = 42


def _safe_filename(title: str, max_len: int = 80) -> str:
    """把新闻标题转成安全的文件名"""
    name = re.sub(r"[\\/:*?\"<>|]", "_", title)
    name = re.sub(r"\s+", "_", name).strip("._")
    if len(name) > max_len:
        name = name[:max_len].rstrip("._")
    if not name:
        name = "untitled"
    return name


def _build_markdown(doc: dict) -> str:
    """把新闻转成 Markdown，标题作为 H1，正文按段落"""
    title = str(doc.get("title", "")).strip()
    author = str(doc.get("author", "")).strip()
    source = str(doc.get("source", "")).strip()
    published = str(doc.get("published_at", "")).strip()
    category = str(doc.get("category", "")).strip()
    url = str(doc.get("url", "")).strip()
    body = str(doc.get("body", "")).strip()

    lines = [f"# {title}", ""]
    meta_lines = []
    if author:
        meta_lines.append(f"- author: {author}")
    if source:
        meta_lines.append(f"- source: {source}")
    if published:
        meta_lines.append(f"- published_at: {published}")
    if category:
        meta_lines.append(f"- category: {category}")
    if url:
        meta_lines.append(f"- url: {url}")
    if meta_lines:
        lines.append("## Metadata")
        lines.append("")
        lines.extend(meta_lines)
        lines.append("")

    lines.append("## Body")
    lines.append("")
    # 按双换行切段，避免一段过长
    paragraphs = re.split(r"\n\s*\n+", body)
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        lines.append(para)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    print("=" * 60)
    print("MultiHop-RAG 评估数据准备")
    print("=" * 60)

    # 1. 加载数据
    print(f"\n[1/4] 加载数据集 ...")
    queries = json.loads(QUERIES_PATH.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    print(f"  • 查询数: {len(queries)}")
    print(f"  • 文章数: {len(corpus)}")

    # 2. 各类型均衡抽样
    print(f"\n[2/4] 抽样 query ...")
    random.seed(SEED)
    sampled: list[dict] = []
    for qtype, n in SAMPLE_PER_TYPE.items():
        pool = [q for q in queries if q["question_type"] == qtype]
        chosen = random.sample(pool, n)
        sampled.extend(chosen)
        print(f"  • {qtype}: 抽 {n} 条 (总池 {len(pool)})")
    random.shuffle(sampled)
    print(f"  • 总采样: {len(sampled)} 条")

    # 3. 收集涉及的文章
    print(f"\n[3/4] 收集涉及的文章 ...")
    needed_titles: set[str] = set()
    for q in sampled:
        for ev in q.get("evidence_list", []):
            title = str(ev.get("title", "")).strip()
            if title:
                needed_titles.add(title)
    print(f"  • 涉及文章数: {len(needed_titles)}")

    # 建立 title -> doc 的索引
    corpus_by_title: dict[str, dict] = {}
    for doc in corpus:
        t = str(doc.get("title", "")).strip()
        if t:
            corpus_by_title[t] = doc

    # 检查覆盖情况
    missing = [t for t in needed_titles if t not in corpus_by_title]
    if missing:
        print(f"  ⚠️ 警告: corpus 中缺少 {len(missing)} 篇文章")
        for t in missing[:5]:
            print(f"      - {t}")

    # 4. 把文章写入 knowledge/multihop-news/
    print(f"\n[4/4] 写入文章到 {NEWS_DIR.relative_to(PROJECT_ROOT)} ...")
    NEWS_DIR.mkdir(parents=True, exist_ok=True)

    # 清理旧文件（避免上轮残留）
    for old in NEWS_DIR.glob("*.md"):
        old.unlink()

    # 写一个 data_structure.md 作为目录索引，给 Skill 用
    structure_lines = [
        "# Multi-Hop News 语料目录",
        "",
        "本目录是 MultiHop-RAG 评估用的英文新闻语料。每个 `.md` 文件对应一篇新闻文章。",
        "",
        "## 检索方法",
        "",
        "- **关键实体定位**：从问题中提取人名、公司名、产品名、时间，用 grep 在所有 .md 文件中搜索",
        "- **多跳推理**：对比/时序类问题需要分别检索每个实体后综合",
        "- **元信息位置**：每篇文章包含 `## Metadata` 段（作者、来源、发布时间）和 `## Body` 段（正文）",
        "",
        "## 文章列表（按 source 分组）",
        "",
    ]

    written: list[dict] = []
    used_filenames: set[str] = set()
    by_source: dict[str, list[str]] = {}

    for title in sorted(needed_titles):
        if title not in corpus_by_title:
            continue
        doc = corpus_by_title[title]

        base_name = _safe_filename(title)
        filename = f"{base_name}.md"
        suffix = 1
        while filename in used_filenames:
            suffix += 1
            filename = f"{base_name}_{suffix}.md"
        used_filenames.add(filename)

        target = NEWS_DIR / filename
        target.write_text(_build_markdown(doc), encoding="utf-8")

        rel_path = f"knowledge/multihop-news/{filename}"
        source = str(doc.get("source", "Unknown"))
        by_source.setdefault(source, []).append(f"- [{title}]({filename})")

        written.append({
            "title": title,
            "filename": filename,
            "rel_path": rel_path,
            "source": source,
        })

    # 完成 data_structure.md
    for source, items in sorted(by_source.items()):
        structure_lines.append(f"### {source}")
        structure_lines.append("")
        structure_lines.extend(items)
        structure_lines.append("")
    (NEWS_DIR / "data_structure.md").write_text(
        "\n".join(structure_lines), encoding="utf-8"
    )

    print(f"  • 写入 {len(written)} 篇文章")
    print(f"  • 写入目录索引: data_structure.md")

    # 5. 保存采样集（评估脚本要用）
    sample_payload = {
        "seed": SEED,
        "sample_size": len(sampled),
        "sample_per_type": SAMPLE_PER_TYPE,
        "queries": [
            {
                "id": idx,
                "query": q["query"],
                "answer": q.get("answer", ""),
                "question_type": q["question_type"],
                "ground_truth_titles": [
                    str(ev.get("title", "")).strip()
                    for ev in q.get("evidence_list", [])
                    if str(ev.get("title", "")).strip()
                ],
                "evidence_facts": [
                    str(ev.get("fact", "")).strip()
                    for ev in q.get("evidence_list", [])
                ],
            }
            for idx, q in enumerate(sampled)
        ],
        "title_to_path": {w["title"]: w["rel_path"] for w in written},
    }
    SAMPLE_PATH.write_text(
        json.dumps(sample_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n采样集保存到: {SAMPLE_PATH.relative_to(PROJECT_ROOT)}")

    print("\n" + "=" * 60)
    print(f"✅ 完成。下一步：")
    print(f"  1. 运行 python scripts/build_multihop_index.py 建索引")
    print(f"  2. 运行 python scripts/evaluate_skill_vs_rag.py 跑评估")
    print("=" * 60)


if __name__ == "__main__":
    main()

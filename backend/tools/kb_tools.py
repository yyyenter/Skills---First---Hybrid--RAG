from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Type

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from knowledge_retrieval.indexer import knowledge_indexer


# ── kb_search ─────────────────────────────────────────────────────────────

class KBSearchInput(BaseModel):
    query: str = Field(..., description="检索查询语句，用于混合向量 + BM25 检索")
    top_k: int = Field(5, description="返回结果数量（默认 5）")
    path_filter: str | None = Field(None, description="可选：限定检索目录，如 'knowledge/medical/literature/'")


class KBSearchTool(BaseTool):
    name: str = "kb_search"
    description: str = (
        "混合检索本地知识库，同时使用向量语义检索和 BM25 关键词检索，并通过 RRF 融合排序。"
        "适用于通用检索场景。返回包含 source_path、locator、snippet、score、parent_id 的结果列表。"
    )
    args_schema: Type[BaseModel] = KBSearchInput

    def _run(
        self,
        query: str,
        top_k: int = 5,
        path_filter: str | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        path_filters = [path_filter] if path_filter else None

        vector_results = knowledge_indexer.retrieve_vector(query, top_k=top_k, path_filters=path_filters)
        bm25_results = knowledge_indexer.retrieve_bm25(query, top_k=top_k, path_filters=path_filters)

        # RRF 简单融合
        seen = {}
        for rank, ev in enumerate(vector_results, start=1):
            key = (ev.source_path, ev.locator)
            seen[key] = {"evidence": ev, "rrf": 1.0 / (60 + rank)}
        for rank, ev in enumerate(bm25_results, start=1):
            key = (ev.source_path, ev.locator)
            if key in seen:
                seen[key]["rrf"] += 1.0 / (60 + rank)
            else:
                seen[key] = {"evidence": ev, "rrf": 1.0 / (60 + rank)}

        sorted_items = sorted(seen.values(), key=lambda x: x["rrf"], reverse=True)[:top_k]
        result_list = []
        for item in sorted_items:
            ev = item["evidence"]
            result_list.append({
                "source_path": ev.source_path,
                "source_type": ev.source_type,
                "locator": ev.locator,
                "snippet": ev.snippet,
                "score": round(item["rrf"], 4),
                "parent_id": ev.parent_id,
            })

        return json.dumps({"count": len(result_list), "results": result_list}, ensure_ascii=False, indent=2)

    async def _arun(
        self,
        query: str,
        top_k: int = 5,
        path_filter: str | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, top_k, path_filter, None)


# ── kb_metadata_filter ────────────────────────────────────────────────────

class KBMetadataFilterInput(BaseModel):
    query: str = Field(..., description="检索查询语句")
    filters: dict[str, Any] | None = Field(None, description="元数据过滤条件，如 {'year': 2020, 'study_type': 'systematic_review'}")
    top_k: int = Field(5, description="返回结果数量（默认 5）")
    path_filter: str | None = Field(None, description="可选：限定检索目录")


class KBMetadataFilterTool(BaseTool):
    name: str = "kb_metadata_filter"
    description: str = (
        "带元数据过滤的混合检索。先执行向量 + BM25 混合检索，再按 filters 中的字段值"
        "在结果中过滤（如年份、研究类型、条款类型等）。适用于需要精确限定条件的场景。"
    )
    args_schema: Type[BaseModel] = KBMetadataFilterInput

    def _run(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
        path_filter: str | None = None,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        path_filters = [path_filter] if path_filter else None
        filters = filters or {}

        # Step 1: 先做混合检索（扩大 top_k 以补偿过滤损失）
        search_top_k = max(top_k * 4, 20)
        vector_results = knowledge_indexer.retrieve_vector(query, top_k=search_top_k, path_filters=path_filters)
        bm25_results = knowledge_indexer.retrieve_bm25(query, top_k=search_top_k, path_filters=path_filters)

        # RRF 融合
        seen = {}
        for rank, ev in enumerate(vector_results, start=1):
            key = (ev.source_path, ev.locator)
            seen[key] = {"evidence": ev, "rrf": 1.0 / (60 + rank)}
        for rank, ev in enumerate(bm25_results, start=1):
            key = (ev.source_path, ev.locator)
            if key in seen:
                seen[key]["rrf"] += 1.0 / (60 + rank)
            else:
                seen[key] = {"evidence": ev, "rrf": 1.0 / (60 + rank)}

        all_results = sorted(seen.values(), key=lambda x: x["rrf"], reverse=True)

        # Step 2: 元数据后过滤
        filtered = []
        for item in all_results:
            ev = item["evidence"]
            if not self._matches_filters(ev, filters):
                continue
            filtered.append({
                "source_path": ev.source_path,
                "source_type": ev.source_type,
                "locator": ev.locator,
                "snippet": ev.snippet,
                "score": round(item["rrf"], 4),
                "parent_id": ev.parent_id,
            })
            if len(filtered) >= top_k:
                break

        return json.dumps(
            {"count": len(filtered), "applied_filters": filters, "results": filtered},
            ensure_ascii=False,
            indent=2,
        )

    def _matches_filters(self, evidence, filters: dict[str, Any]) -> bool:
        """检查 evidence 是否满足过滤条件。

        注意：当前 metadata 只存了基础字段（doc_id, parent_id, source_path, source_type, locator）。
        过滤是基于 source_path / source_type 和 snippet 内容做简单匹配。
        如果需要更精细的过滤，应在 Markdown frontmatter 或 JSON 元数据中添加对应字段，
        并在 indexer.py 切分时把元数据附加到 metadata 中。
        """
        for key, value in filters.items():
            # 简单过滤：在 source_path、locator、snippet 中查找
            text_to_search = f"{evidence.source_path} {evidence.locator} {evidence.snippet}"
            if str(value).lower() not in text_to_search.lower():
                return False
        return True

    async def _arun(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 5,
        path_filter: str | None = None,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, query, filters, top_k, path_filter, None)


# ── kb_list_files ─────────────────────────────────────────────────────────

class KBListFilesInput(BaseModel):
    path: str = Field("knowledge/", description="要列出的知识库目录，如 'knowledge/medical/literature/'")
    recursive: bool = Field(True, description="是否递归列出子目录内容")


class KBListFilesTool(BaseTool):
    name: str = "kb_list_files"
    description: str = (
        "列出指定知识库目录下的文件列表，用于浏览知识库结构或确认文件是否存在。"
        "返回文件路径、大小、类型信息。"
    )
    args_schema: Type[BaseModel] = KBListFilesInput

    def _run(
        self,
        path: str = "knowledge/",
        recursive: bool = True,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        base_dir = knowledge_indexer.base_dir
        if not base_dir:
            return json.dumps({"error": "KnowledgeIndexer not configured"}, ensure_ascii=False)

        target = (base_dir / path).resolve()
        knowledge_root = (base_dir / "knowledge").resolve()
        if knowledge_root not in target.parents and target != knowledge_root:
            return json.dumps({"error": "Path traversal detected"}, ensure_ascii=False)
        if not target.exists():
            return json.dumps({"error": "Path does not exist"}, ensure_ascii=False)

        files = []
        pattern = target.rglob("*") if recursive else target.iterdir()
        for item in sorted(pattern):
            if item.is_file():
                rel = str(item.relative_to(base_dir)).replace("\\", "/")
                files.append({
                    "path": rel,
                    "size": item.stat().st_size,
                    "type": item.suffix.lower().lstrip(".") or "unknown",
                })

        return json.dumps(
            {"directory": path, "count": len(files), "files": files},
            ensure_ascii=False,
            indent=2,
        )

    async def _arun(
        self,
        path: str = "knowledge/",
        recursive: bool = True,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, path, recursive, None)


# ── kb_open_chunk ─────────────────────────────────────────────────────────

class KBOpenChunkInput(BaseModel):
    parent_id: str = Field(..., description="chunk 的 parent_id，如 'knowledge/medical/literature/pubmed_xxx.md::背景'")


class KBOpenChunkTool(BaseTool):
    name: str = "kb_open_chunk"
    description: str = (
        "打开指定 chunk 的完整 section 内容（parent 级别），用于获取检索结果中 snippet 的上下文。"
        "传入 parent_id 即可获取该 section 的完整文本，不截断。"
    )
    args_schema: Type[BaseModel] = KBOpenChunkInput

    def _run(
        self,
        parent_id: str,
        run_manager: CallbackManagerForToolRun | None = None,
    ) -> str:
        # 从 manifest 中查找匹配的 parent_id
        for doc in knowledge_indexer._documents:
            if doc.get("parent_id") == parent_id:
                full_text = doc.get("parent_text", "") or doc.get("text", "")
                return json.dumps({
                    "parent_id": parent_id,
                    "source_path": doc.get("source_path", ""),
                    "source_type": doc.get("source_type", ""),
                    "locator": doc.get("locator", ""),
                    "full_text": full_text,
                }, ensure_ascii=False, indent=2)

        return json.dumps(
            {"error": "Parent ID not found", "parent_id": parent_id},
            ensure_ascii=False,
            indent=2,
        )

    async def _arun(
        self,
        parent_id: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        return await asyncio.to_thread(self._run, parent_id, None)

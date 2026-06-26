# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ragclaw** - A local-first, file-driven Agent workspace with hybrid RAG (Retrieval-Augmented Generation). The system features a "Skill-first, hybrid retrieval fallback" knowledge retrieval architecture.

### Key Architecture Patterns

1. **Skill-First Retrieval**: Skill agents (like `rag-skill`) are queried first for domain-specific knowledge. Only when skill results are `partial`/`not_found`/`uncertain` does the system fallback to vector + BM25 hybrid retrieval.

2. **File-as-Source-of-Truth**: All state (sessions, memory, skills) is persisted as local files:
   - `backend/sessions/*.json` - conversation history
   - `backend/memory/MEMORY.md` - long-term memory
   - `backend/skills/*/SKILL.md` - editable skill definitions

3. **Observable Retrieval**: Every retrieval step (skill, vector, bm25, fused) is streamed to the frontend for transparency.

## Common Commands

### Backend
```powershell
cd backend
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8004 --reload
```

### Frontend
```powershell
cd frontend
npm install
npm run dev
```

### Health Check
```
http://127.0.0.1:8004/health
```

## Tech Stack

**Backend**: Python 3.10+, FastAPI, LangChain 1.x, LlamaIndex, OpenAI-compatible APIs  
**Frontend**: Next.js 14, React 18, TypeScript, Tailwind CSS, Monaco Editor

## Supported LLM Providers

- `zhipu` (default): GLM-5
- `bailian`: Qwen3.5-Plus
- `deepseek`: DeepSeek-Chat
- `openai`: GPT-4.1-Mini

## Environment Variables

Minimum required (in `backend/.env`):

```env
LLM_PROVIDER=zhipu
LLM_MODEL=glm-5
ZHIPU_API_KEY=your_key

EMBEDDING_PROVIDER=zhipu
EMBEDDING_MODEL=embedding-3
EMBEDDING_API_KEY=your_key
```

## Code Architecture

### Core Modules

| Path | Purpose |
|------|---------|
| `backend/app.py` | FastAPI entry point, lifespan initialization |
| `backend/graph/agent.py` | Main Agent manager with astream() for chat |
| `backend/graph/session_manager.py` | Session CRUD, message persistence |
| `backend/graph/memory_indexer.py` | Memory RAG indexing |
| `backend/graph/prompt_builder.py` | Dynamic system prompt from components |
| `backend/knowledge_retrieval/orchestrator.py` | Skill-first + hybrid fallback orchestration |
| `backend/knowledge_retrieval/skill_retriever_agent.py` | Skill agent execution |
| `backend/knowledge_retrieval/indexer.py` | Vector + BM25 knowledge indexing |
| `backend/knowledge_retrieval/fusion.py` | Reciprocal Rank Fusion (RRF) |

### Knowledge Retrieval Flow

```
User Question
    ↓
Skill Retriever Agent (e.g., rag-skill)
    ↓
{status: success/partial/not_found/uncertain}
    ↓
If partial/not_found/uncertain → Vector + BM25 Fallback
    ↓
RRF Fusion of skill + vector + bm25 results
    ↓
Answer with citations
```

### Frontend Structure

- `src/app/page.tsx` - Main workspace with 3 columns (Sidebar, Chat, Inspector)
- `src/lib/store.tsx` - Zustand-like global state for sessions, messages, RAG mode
- `src/lib/api.ts` - TypeScript API client for all backend endpoints
- `src/components/chat/` - ChatPanel, ChatMessage, RetrievalCard, ThoughtChain

### RAG Mode

Toggle via `/api/config/rag-mode`:
- **Disabled**: Normal agent flow with tools
- **Enabled**: Memory检索 injected into context before model inference

## Key Design Principles

1. **No external dependencies** (MySQL/Redis) - all state is file-based
2. **Skimmable prompts** - system prompts built from Markdown components
3. **Transparent tool calls** - every tool invocation is streamed and persisted
4. **Skill = Document** - skills are editable `.md` files, not black-box functions

# Ragclaw — Skill-First Agentic RAG

一个面向本地运行、文件优先、可审计的 **Skill-First Hybrid RAG** 智能问答系统。

核心设计理念：**让 LLM Agent 先读领域 Skill（业务策略文档），再决定如何检索，而不是盲目做向量搜索。**

- **Skill 优先**：8 个领域 Skill（法律×4 + 医疗×4）指导检索策略
- **混合检索兜底**：Skill 结果不足时，自动 fallback 到向量 + BM25 + RRF 融合
- **文件即事实源**：所有状态（会话、记忆、Skill、知识库）都是本地文件
- **检索可观测**：前端实时展示 Skill 路由决策、工具调用链、检索证据来源

---

## 架构概览

```
用户问题
    ↓
Intent Router → Skill Router（legal / medical / generic）
    ↓
LLM 读取领域 SKILL.md（含强制路由决策 JSON）
    ↓
Method Router（statute / case / evidence / drug 等）
    ↓
LLM 调用 KB 工具（kb_search / kb_metadata_filter / kb_list_files / kb_open_chunk）
    ↓
{status: success / partial / not_found / uncertain}
    ↓
status ≠ success → 触发 Hybrid Fallback
    ↓
Vector 检索 + BM25 检索 → RRF 融合
    ↓
带引用的最终答案
```

### 两层路由

| 层级 | 职责 | 输出 |
|---|---|---|
| **业务路由** | 判断问题属于法律 / 医疗 / 通用 | `skills/legal/...` 或 `skills/medical/...` |
| **方法路由** | 在 SKILL.md 内按优先级表选择检索方法 | JSON：`{"method":"Comparison Hop","reason":"...","sub_queries":[...]}` |

---

## 项目特点

### 1. 领域 Skill 可编辑

8 个领域 Skill 全部以 `SKILL.md` 形式存在，不是黑盒代码：

**法律领域**（`skills/legal/`）
- `statute_search` — 法条原文检索
- `case_search` — 判例检索（含 One Good Case Method）
- `contract_clause` — 合同条款检索（基于 CUAD 41 类分类）
- `legal_definition` — 法律术语定义检索

**医疗领域**（`skills/medical/`）
- `evidence_search` — 循证医学文献检索（PICO 框架）
- `guideline_search` — 临床指南检索
- `drug_search` — 药品信息检索
- `diagnosis_search` — 诊断标准检索

每个 Skill 包含：
- **强制路由决策**：优先级表 P0-P4 + JSON 模板
- **术语规范化映射表**：口语化表达 → 专业术语
- **意图挖掘检查清单**：5 个自审问题
- **查询重写策略**：PICO 拆解、同义词扩展、证据等级限定
- **多跳检索判断**：Bridge Entity / Comparison / Temporal Chain / Special Population / Legal Element

### 2. Skill-First + Hybrid Fallback

- Skill Agent 优先执行：LLM 读取 SKILL.md → 做路由决策 → 调用 KB 工具检索
- 当 Skill 返回 `partial` / `not_found` / `uncertain` 时，自动 fallback 到向量 + BM25
- RRF（Reciprocal Rank Fusion）融合所有来源的证据，按融合得分排序输出

### 3. 零数据库本地索引

- **向量索引**：LlamaIndex SimpleVectorStore（内存）+ Ollama 本地 Embedding（nomic-embed-text，768 维）
- **BM25 索引**：自研内存 Counter 实现，支持中英文混合 tokenization
- **无外部依赖**：不需要 MySQL / Redis / Elasticsearch

### 4. 检索可观测

前端 Inspector 面板实时展示：
- Skill 路由决策（读了哪个 SKILL.md）
- 工具调用链（kb_search、kb_metadata_filter 等）
- 每跳检索的查询和结果数量
- 向量 / BM25 / 融合三个阶段的证据来源

---

## 知识库

真实数据集已导入 `backend/knowledge/`：

| 数据集 | 领域 | 数量 | 说明 |
|---|---|---|---|
| CUAD | 法律/合同 | 5 份 | The Atticus Project 合同理解数据集 |
| PubMedQA | 医疗/文献 | 10 份 | 医学问答数据集 |
| 民法典 | 法律/法条 | 5 份 | 合同编、总则、物权编等 |
| 指导案例 | 法律/判例 | 1 份 | 最高人民法院指导案例 1 号 |

> 原始数据集已做 Markdown 转换，YAML frontmatter 保留元数据（pmid、year、document_type 等）。

---

## 技术栈

**后端**
- Python 3.10+
- FastAPI + Uvicorn
- LangChain 1.x（Agent + Tool）
- LangGraph（流式工具调用链）
- LlamaIndex（向量索引）
- OpenAI-compatible API（支持智谱 / 通义千问 / DeepSeek / Ollama）

**前端**
- Next.js 14
- React 18 + TypeScript
- Tailwind CSS
- Monaco Editor

---

## 快速开始

### 1. 环境准备

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

配置环境变量 `backend/.env`：

```env
# LLM（示例：智谱 GLM-4.7-Flash）
LLM_PROVIDER=zhipu
LLM_MODEL=glm-4.7-flash
ZHIPU_API_KEY=your_key

# Embedding（示例：Ollama 本地）
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_API_KEY=ollama
EMBEDDING_BASE_URL=http://localhost:11434/v1
```

> 也支持 DeepSeek、通义千问、OpenAI 等。Embedding 推荐用 Ollama 本地（nomic-embed-text）避免 API 限流。

### 2. 启动 Ollama（用于本地 Embedding）

```powershell
ollama pull nomic-embed-text
ollama serve
```

### 3. 启动后端

```powershell
cd backend
python -m uvicorn app:app --host 127.0.0.1 --port 8004 --reload
```

> 首次启动会自动加载已有索引（2894 chunks）。如需重建索引，调用 `POST /api/knowledge/index/rebuild`。

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:3000`。

---

## 核心代码结构

```
backend/
├─ app.py                          # FastAPI 入口
├─ graph/
│  ├─ agent.py                     # Agent 管理器（工具列表、模型构建）
│  ├─ prompt_builder.py            # 系统提示词动态组装
│  └─ session_manager.py           # 会话持久化
├─ knowledge_retrieval/
│  ├─ orchestrator.py              # Skill-First + Hybrid Fallback + RRF 融合
│  ├─ skill_retriever_agent.py     # Skill Agent（读取 SKILL.md、路由决策）
│  ├─ indexer.py                   # 向量索引 + BM25 索引（零数据库）
│  ├─ hybrid_retriever.py          # Vector + BM25 并行检索
│  ├─ fusion.py                    # Reciprocal Rank Fusion
│  └─ types.py                     # 数据模型（Evidence、RetrievalStep 等）
├─ skills/                         # 8 个领域 Skill
│  ├─ legal/
│  │  ├─ statute_search/SKILL.md
│  │  ├─ case_search/SKILL.md
│  │  ├─ contract_clause/SKILL.md
│  │  └─ legal_definition/SKILL.md
│  └─ medical/
│     ├─ evidence_search/SKILL.md
│     ├─ guideline_search/SKILL.md
│     ├─ drug_search/SKILL.md
│     └─ diagnosis_search/SKILL.md
├─ tools/
│  ├─ kb_tools.py                  # 4 个 KB 检索工具
│  └─ ...                          # terminal / read_file / python_repl 等
├─ knowledge/                      # 知识库文件
│  ├─ legal/statutes/              # 民法典各编
│  ├─ legal/cases/                 # 指导案例
│  ├─ legal/contracts/             # CUAD 合同
│  └─ medical/                     # PubMedQA 文献 + 指南
└─ scripts/
   ├─ convert_cuad.py              # 数据集转换
   ├─ convert_pubmedqa.py
   ├─ rebuild_index.py
   └─ eval_legal_skills.py         # 法律 Skill 评测脚本
```

---

## 评测

仓库内置法律领域评测脚本，对比 **Baseline（纯 Hybrid 检索）** vs **Skill-First + RRF Fallback**：

```powershell
cd backend
python scripts/eval_legal_skills.py
```

评测维度：
- **Recall@5**：ground-truth 文档是否出现在 Top-5 结果中
- **Answer Keyword Score**：检索片段中关键术语的覆盖度
- **Fallback Rate**：Skill 未成功时 fallback 到 hybrid 的比例

---

## 当前边界

- 更适合本地开发、研究和原型验证，不是完整 SaaS
- LLM 执行多步工具调用的稳定性依赖模型能力（GLM-4.7-Flash 够用但偶有失败）
- Excel / PDF 的高级处理仍主要依赖 Skill 链路中的专门工具
- 混合检索当前主要覆盖 Markdown / JSON 类知识文件

---

## 致谢

- `skill` 设计思路参考了 [ConardLi/rag-skill](https://github.com/ConardLi/rag-skill)
- 法律检索方法参考 Harvard Law Library Legal Research Strategy
- 医疗循证检索参考 Duke University PICO Framework
- 多跳检索参考 HotpotQA (Yang et al., EMNLP 2018)
- 合同条款分类基于 CUAD (The Atticus Project, NeurIPS 2021)

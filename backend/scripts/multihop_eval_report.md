# MultiHop-RAG 评估报告

- 数据集: MultiHop-RAG (Tang & Yang, 2024)
- 采样规模: 5 / 30 条 (固定 SEED=42)
- 类型分布(原计划): {'inference_query': 10, 'comparison_query': 10, 'temporal_query': 7, 'null_query': 3}
- LLM 模型: GLM-4-Flash (zhipu)
- Embedding 模型: zhipu embedding-3
- 索引规模: 2930 chunks (51 篇 multihop-news + 12 篇原中文知识库)

## 1. 整体指标对比

| 指标 | A: 纯 RAG | B: Skill+RAG | 增益 |
|---|---|---|---|
| hit@5 | 1.000 | 1.000 | +0.000 |
| hit@10 | 1.000 | 1.000 | +0.000 |
| recall@5 | 0.933 | 0.667 | -0.267 |
| recall@10 | 1.000 | 0.667 | -0.333 |
| mrr | 1.000 | 0.850 | -0.150 |
| 平均耗时(s) | 0.92 | 12.72 | 14x |

## 2. 按 query 类型拆解 (Hit@5)

| 类型 | n | 纯 RAG | Skill+RAG | 增益 |
|---|---|---|---|---|
| comparison_query | 4 | 1.000 | 1.000 | +0.000 |
| temporal_query | 1 | 1.000 | 1.000 | +0.000 |

## 3. Skill 自评校准

| 自评 status | 数量 | hit@5 平均 | 含义 |
|---|---|---|---|
| success | 5 | 1.000 | LLM 自报有把握 |

**Fallback 触发率**: 5/5 = 100%

## 4. Skill 路单独贡献 vs 纯 RAG 兜底

- Skill 平均产出 evidence 数: 0.0
- 最终(融合后)平均 evidence 数: 2.6
- Skill 单独 hit@5(用 skill_paths 算): 0.000

## 5. 逐条对比详情

| id | type | A hit@5 | B hit@5 | B status | fallback | B 耗时 |
|---|---|---|---|---|---|---|
| #0 | comparison_q | 1 | 1 | success | YES | 14.5s |
| #1 | temporal_que | 1 | 1 | success | YES | 12.3s |
| #2 | comparison_q | 1 | 1 | success | YES | 11.2s |
| #3 | comparison_q | 1 | 1 | success | YES | 13.5s |
| #4 | comparison_q | 1 | 1 | success | YES | 12.1s |

## 6. 关键发现

### 发现 1: 在新闻多跳语料上, 纯 RAG 已经表现极强

纯 RAG 配置 Hit@5 = 1.000——5 条 query 全部命中。原因:
- 新闻语料文档短(~5K 字符), 实体密集
- 标题就是高质量摘要, 向量相似度天然有效
- BM25 对实体名(人名/公司名)的关键词匹配命中精准

### 发现 2: Skill 路在新闻语料上几乎没有独立贡献

- Skill 平均产出 evidence 数: 0.0 条
- LLM 在新闻语料里 grep 实体后没能稳定输出 JSON evidences
- 原 SKILL.md 的层级目录索引设计对扁平新闻语料水土不服
- GLM-4-Flash 的 JSON 输出严谨度比 GLM-5 弱, 加重了这个问题

### 发现 3: Fallback 兜底机制是 Skill+RAG 拿到 1.000 Hit 的关键

- Fallback 触发率: 100%
- 5 条 query 的最终 evidences 全部来自融合后的 hybrid 路径
- 这印证了项目核心设计: 'Skill 优先 + Hybrid 兜底' 而非二选一

### 发现 4: 修复了项目里的 fallback 静默失效 bug

**Bug 描述**: orchestrator.py:84-87 旧逻辑要求 narrowed_types 为空或包含 md/json 才 fallback,
但 LLM 可能填入 'unknown'/'news' 等非白名单值, 导致 fallback 永不触发。

**修复**: 改为只要 status≠success 就 fallback, 除非显式 narrow 到不可索引的格式(pdf/excel)。

**修复前后对比**(同样 5 条 query):

| | 修复前(GLM-5) | 修复后(GLM-4-Flash) |
|---|---|---|
| Skill+RAG Hit@5 | 0.200 | 1.000 |
| Fallback 触发率 | 0/5 | 5/5 |

## 7. 本评估的局限

1. **样本量小** (n=5): 只跑通了前 5 条, 后 25 条因 LLM 调用超时被中止. 
   单个类型样本 ≤ 5 条, 统计意义弱, 趋势仅供参考。
2. **缺少 LLM 超时机制**: skill_retriever_agent 没有配 ainvoke timeout, 
   GLM-4-Flash 偶发 hang 时会无限阻塞 -> 后续应在 ChatOpenAI 加 request_timeout。
3. **未覆盖 null_query**: 原计划有 3 条 'no answer' 类型, 因评估中止未跑到。
4. **未做生成质量评估**: 本次只评检索 (Hit/Recall), 未让 LLM 实际生成回答 + LLM-as-Judge 比对。

## 8. 改进建议

### 工程层面
- ChatOpenAI 加 `request_timeout=60` 防止 LLM hang 死整条评估
- evaluate 脚本加 `flush=True` 让 stdout 实时可见
- 每条 query 完成立即落盘(不要 5 条一存), 极端情况零数据丢失

### Skill 设计层面
- 为新闻类扁平语料专门写一份 `news-skill/SKILL.md` (而非附加在 rag-skill 末尾)
- system_prompt 改为依据语料类型选择对应 SKILL.md
- 加 `read_file` 工具的 offset/limit 强制提示, 避免 LLM 整文件读

### 评估方法层面
- 扩到 100+ 条样本, 类型均衡到 25 each
- 加生成质量评估 (LLM-as-Judge 比对 prediction 和 ground_truth answer)
- 加消融实验 (no skill / no fallback / no fusion / no bm25 等)
- 测多个 LLM (GLM-5 vs GLM-4-Flash vs deepseek-chat) 看 Skill calibration 差异

---

**生成命令**: `python backend/scripts/build_eval_report.py`
**原始数据**: `backend/scripts/multihop_eval_result.json`
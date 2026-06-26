---
name: legal-definition-search
description: 法律术语/概念定义检索技能。当用户询问"什么是X"、"X的定义"、"X的构成要件"、"X的法律含义"时使用。检索法律知识库中的法条定义、司法解释定义和权威学术定义。
---

## 目标

找到法律概念的准确定义、构成要件和适用范围。返回必须包含定义来源（哪部法律、哪一条）、定义原文、构成要件分解。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## 检索变量说明

| 变量 | 含义 | 默认值 | 可选值 |
|---|---|---|---|
| `definition_source` | 定义来源类型 | `"statute"` | `"statute"`, `"judicial_interpretation"`, `"academic"` |
| `jurisdiction` | 法域 | `"China"` | `"China"`, `"USA"`, `"EU"` |

## 推荐命令

### 法条中的定义条款检索

```
kb_search(
    query="不安抗辩权 定义 构成要件",
    path_filter="knowledge/legal/statutes/",
    top_k=5
)
```

### 司法解释中的定义

```
kb_metadata_filter(
    query="表见代理 构成要件",
    filters={
        "document_type": "judicial_interpretation",
        "jurisdiction": "China"
    },
    top_k=5
)
```

## 执行步骤

1. **标准化术语**
   - 将用户的口语化表述转换为标准法律术语
   - 例："担心对方不付钱" → "不安抗辩权"

2. **首次检索**
   - 用 `kb_search`，query 包含"术语 + 定义/概念/构成要件"
   - 优先在 `knowledge/legal/statutes/` 中检索

3. **判断结果**
   - ✅ 如果结果中有明确的定义条款 → 进入 Step 4
   - ❌ 如果只有原则性提及 → 执行【扩展检索】

4. **精确定位**
   - 用 `kb_open_chunk` 打开定义条款的完整内容
   - 提取：定义原文、构成要件、适用条件、法律后果

### 扩展检索策略

```
策略 A：上位概念检索
  kb_search(query="抗辩权 类型 定义", path_filter="knowledge/legal/statutes/", top_k=5)

策略 B：同领域概念对比
  kb_search(query="同时履行抗辩权 OR 先履行抗辩权 OR 不安抗辩权", path_filter="knowledge/legal/", top_k=5)

策略 C：如果仍找不到 → status 标记为 not_found
```

## 结果筛选规则

- 优先**法条中的定义条款**（如"本法所称X，是指..."）
- 其次**司法解释中的定义**
- 再次**权威学术著作**
- 同一术语在不同法律中定义可能不同，必须标注来源

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到定义 | `status = "not_found"`，说明"未找到该术语的权威法律定义" |
| 找到原则性提及但无定义 | `status = "partial"` |
| 不同来源定义冲突 | `status = "uncertain"`，列出差异并标注来源 |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/legal/statutes/contract_law_articles.md",
      "source_type": "statute",
      "locator": "第五百二十七条",
      "snippet": "应当先履行债务的当事人，有确切证据证明对方有下列情形之一的，可以中止履行...",
      "score": 0.95,
      "parent_id": "contract_law_articles::第五百二十七条"
    }
  ],
  "narrowed_paths": ["knowledge/legal/statutes/"],
  "narrowed_types": ["statute"],
  "rewritten_queries": ["不安抗辩权 定义 民法典", "不安抗辩权 构成要件"],
  "searched_paths": ["knowledge/legal/statutes/contract_law_articles.md"],
  "reason": "找到民法典第527条关于不安抗辩权的定义和适用条件。"
}
```

## 特别约束

- 定义引用必须精确到法条编号
- 构成要件必须分条列出
- 禁止用通俗解释替代法条定义

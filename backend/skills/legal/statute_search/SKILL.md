---
name: legal-statute-search
description: 法律成文法/法规检索技能。当用户询问法条原文、法律规定、法律条款内容、某类行为的法律后果、具体法律名称中的条文时使用。仅限法律知识库 knowledge/legal/statutes/ 目录下检索。
---

## 目标

用法条原文、法律条款的准确定义回答用户问题。返回必须包含法条编号、法律名称、具体条文内容，必要时给出相关司法解释。

## 可用工具

你作为法律检索代理，可以且仅可以调用以下工具：

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索（向量 + BM25） | `query` (检索关键词) | `top_k` (默认 5), `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` (字典) | `top_k` (默认 5) |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

> ⚠️ 不要直接 grep、不要直接 read 文件、不要使用 terminal 工具。

## 检索变量说明

| 变量 | 含义 | 默认值 | 可选值 |
|---|---|---|---|
| `jurisdiction` | 法域/管辖地 | `"China"` | `"China"`, `"USA"`, `"EU"`, `"California"`, `"Delaware"` |
| `law_name` | 法律名称 | 自动提取 | 如 `"Civil Code"`, `"Company Law"`, `"Contract Law"` |
| `article_number` | 法条编号 | 无 | 如 `"第563条"`, `"Article 563"` |
| `year` | 法律修订年份 | 无 | 如 `2020`, `2021` |

## 推荐命令

### 按法条编号检索（最精准）

```
kb_search(
    query="民法典 第563条 合同解除",
    path_filter="knowledge/legal/statutes/",
    top_k=3
)
```

### 按法律名称 + 主题检索

```
kb_metadata_filter(
    query="不安抗辩权 行使条件",
    filters={
        "document_type": "statute",
        "jurisdiction": "China",
        "law_name": "Civil Code"
    },
    top_k=5
)
```

### 跨法域对比检索（需要对比不同地区法律时）

```
kb_metadata_filter(
    query="竞业限制 期限",
    filters={"document_type": "statute", "jurisdiction": "California"},
    top_k=5
)

kb_metadata_filter(
    query="non-compete duration",
    filters={"document_type": "statute", "jurisdiction": "Delaware"},
    top_k=5
)
```

## 执行步骤

1. **提取检索要素**
   - 从用户问题中提取：法域（未明确则默认 China）、法律名称（如有）、法条编号（如有）、核心法律术语
   - 如果用户问了"X 的法律规定"，把 X 转换为标准法律术语

2. **首次检索**
   - 如果用户明确给出了法条编号 → 用 `kb_search`，query 包含"法律名称 + 法条编号 + 关键词"
   - 如果用户没有给法条编号 → 用 `kb_metadata_filter`，filters 包含 `document_type=statute` 和法域

3. **判断结果质量**
   - ✅ 如果结果中有明确的法条编号 + 完整条文 → 进入 Step 4
   - ❌ 如果结果只有原则性规定、缺少具体条款 → 执行【扩展检索】

4. **精确定位**
   - 用 `kb_open_chunk` 打开 Step 2 找到的 chunk，获取完整条文内容
   - 如果同一条款有多个修订版本，优先取最新生效版本

5. **补充检索（必要时）**
   - 如果法条内容需要司法解释辅助理解，用 `kb_search` 检索同名司法解释
   - 如果法条已被修订或废止，必须标注"该法条已被修订/废止，当前有效版本为..."

### 扩展检索策略

如果 Step 2-3 未找到明确法条：

```
策略 A：同义词扩展
  kb_search(query="解除合同 OR 终止合同 OR 撤销合同", path_filter="knowledge/legal/statutes/", top_k=5)

策略 B：上位概念检索
  kb_search(query="合同权利义务终止", path_filter="knowledge/legal/statutes/", top_k=5)

策略 C：如果仍找不到 → status 标记为 not_found
```

## 结果筛选规则

- 优先使用**法条原文**，不要用二次文献（教科书、论文）替代法条
- 同一条款多个版本时，优先**最新生效版本**
- 如果结果中有"已废止"、"已被修订"等字样，必须重新检索当前有效版本
- 法条编号必须精确到条、款、项（如"第563条第1款第2项"）
- 不要只用第一条结果下结论，至少核对 2-3 个来源的一致性

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到任何法条 | `status = "not_found"`，说明"在当前知识库中未找到直接对应的法条" |
| 找到原则性规定但无具体条款 | `status = "partial"`，说明"找到上位法规定，但缺少具体条款支撑" |
| 法条已修订/废止 | `status = "uncertain"`，标注新旧法差异，说明有效版本 |
| 不同法域规定冲突 | `status = "uncertain"`，列出各法域差异 |
| 检索结果不足以支持结论 | `status = "not_found"`，禁止编造法条 |

## 输出格式

必须以以下 JSON 结构输出：

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/legal/statutes/civil_code_contract.md",
      "source_type": "statute",
      "locator": "第五百六十三条",
      "snippet": "当事人一方迟延履行主要债务，经催告后在合理期限内仍未履行的，当事人可以解除合同...",
      "score": 0.95,
      "parent_id": "civil_code_contract::第五百六十三条"
    }
  ],
  "narrowed_paths": ["knowledge/legal/statutes/"],
  "narrowed_types": ["statute"],
  "rewritten_queries": ["民法典 合同解除 迟延履行", "合同法 解除权 催告"],
  "searched_paths": ["knowledge/legal/statutes/civil_code_contract.md"],
  "reason": "找到民法典第563条关于合同法定解除的直接法条依据，包含迟延履行和催告程序的具体规定。"
}
```

## 特别约束

- 禁止编造不存在的法条编号或条文内容
- 禁止使用知识库以外的法律知识回答问题
- 对法条引用必须精确到编号，不能只写"法律规定"
- 如果涉及新旧法冲突，必须明确标注"现行有效法"
- 对跨法域问题，必须标注"中国法"、"美国法"等来源

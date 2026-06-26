---
name: medical-drug-search
description: 药物信息检索技能。当用户询问药品适应症、禁忌症、用法用量、不良反应、药物相互作用、特殊人群用药时使用。仅限医学知识库 knowledge/medical/drugs/ 目录下检索。
---

## 目标

找到药品的法定信息（说明书、药典）和指南推荐。返回必须包含药品名称、适应症、用法用量、禁忌症、主要不良反应。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## 检索变量说明

| 变量 | 含义 | 默认值 | 可选值 |
|---|---|---|---|
| `drug_name` | 药品通用名 | 自动提取 | 如 `"metformin"`, `"二甲双胍"` |
| `drug_class` | 药物类别 | 无 | 如 `"biguanide"`, `"ACEI"`, `"ARB"` |
| `population` | 特殊人群 | 无 | `"pregnant"`, `"elderly"`, `"pediatric"`, `"renal_impairment"` |

## 推荐命令

### 按药品通用名检索

```
kb_metadata_filter(
    query="二甲双胍 肾功能不全 eGFR",
    filters={
        "document_type": "drug_label",
        "drug_name": "metformin"
    },
    top_k=5
)
```

### 按药物类别 + 适应症检索

```
kb_search(
    query="SGLT2抑制剂 心力衰竭 推荐",
    path_filter="knowledge/medical/drugs/",
    top_k=5
)
```

## 执行步骤

1. **标准化药名**
   - 优先使用通用名（如"二甲双胍"）
   - 同时检索商品名（如"格华止"）作为补充

2. **首次检索**
   - 用 `kb_metadata_filter`，filters 包含 `document_type=drug_label`
   - 加入药品名称过滤

3. **信息分层提取**
   - 第一层：药品说明书（法定信息，优先级最高）
   - 第二层：指南中的药物推荐
   - 第三层：药典/药物学专著

4. **特殊人群验证**
   - 如果问题涉及特殊人群，检索该人群的用药注意事项

## 结果筛选规则

- 优先**药品说明书**（法定信息）
- 注意**禁忌症**和**黑框警告**
- 注意**肾功能/肝功能调整**
- 药物相互作用必须列出具体机制

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到药品信息 | `status = "not_found"` |
| 找到药品但缺少特殊人群信息 | `status = "partial"` |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/medical/drugs/metformin_label.md",
      "source_type": "drug_label",
      "locator": "用法用量 / 肾功能不全患者",
      "snippet": "eGFR 45-59：剂量减半；eGFR < 30：禁用。",
      "score": 0.95,
      "parent_id": "metformin_label::用法用量"
    }
  ],
  "narrowed_paths": ["knowledge/medical/drugs/"],
  "narrowed_types": ["drug_label"],
  "rewritten_queries": ["二甲双胍 肾功能不全", "metformin renal dosing"],
  "searched_paths": ["knowledge/medical/drugs/metformin_label.md"],
  "reason": "找到二甲双胍说明书中关于肾功能不全患者的剂量调整方案。"
}
```

## 特别约束

- 必须标注药品通用名和商品名
- 剂量信息必须精确到 mg 和频次
- 禁忌症必须完整列出
- 禁止推荐超说明书用药

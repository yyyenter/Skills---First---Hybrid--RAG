---
name: medical-diagnosis-search
description: 疾病诊断标准检索技能。当用户询问诊断标准、分型分期、检查方法、鉴别诊断、正常值范围时使用。仅限医学知识库 knowledge/medical/diseases/ 和 knowledge/medical/guidelines/ 目录下检索。
---

## 目标

找到疾病的权威诊断标准、分型分期体系和检查方法。返回必须包含诊断标准来源、具体指标、排除标准。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## 检索变量说明

| 变量 | 含义 | 默认值 | 可选值 |
|---|---|---|---|
| `disease_name` | 疾病名称 | 自动提取 | 如 `"T2DM"`, `"hypertension"` |
| `diagnosis_standard` | 诊断标准版本 | 最新 | `"WHO_2024"`, `"ADA_2024"`, `"中国指南_2024"` |
| `classification` | 分型/分期 | 无 | `"type"`, `"stage"`, `"grade"` |

## 推荐命令

### 按疾病名称检索诊断标准

```
kb_metadata_filter(
    query="2型糖尿病 诊断标准 HbA1c",
    filters={
        "document_type": "guideline",
        "disease": "T2DM"
    },
    top_k=5
)
```

### 按检查项目检索正常值

```
kb_search(
    query="空腹血糖 正常值 诊断切点",
    path_filter="knowledge/medical/guidelines/",
    top_k=5
)
```

## 执行步骤

1. **确定疾病名称**
   - 将用户的口语化表述转换为标准疾病名称
   - 例："血糖高" → "2型糖尿病"或"糖尿病前期"

2. **首次检索**
   - 用 `kb_metadata_filter`，filters 包含 `document_type=guideline`
   - 加入疾病名称过滤

3. **诊断标准提取**
   - 从结果中提取：诊断指标、切点值、必要条件、排除标准
   - 注意诊断标准的**版本**和**适用范围**

4. **分型分期检索（如需要）**
   - 如果问题涉及分型或分期，进一步检索相关内容

## 结果筛选规则

- 优先**最新版本**的诊断标准
- 优先**WHO、中华医学会、ADA**等权威来源
- 注意诊断标准的**适用范围**（成人/儿童、妊娠/非妊娠）
- 注意新旧版标准的**差异**

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到诊断标准 | `status = "not_found"` |
| 找到标准但缺少具体切点 | `status = "partial"` |
| 新旧标准差异大 | `status = "uncertain"`，列出差异 |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/medical/guidelines/t2dm_2024_guideline.md",
      "source_type": "guideline",
      "locator": "一、诊断标准 / 1.1 糖尿病诊断标准",
      "snippet": "HbA1c ≥ 6.5%；空腹血糖 ≥ 7.0 mmol/L；OGTT 2h ≥ 11.1 mmol/L。",
      "score": 0.95,
      "parent_id": "t2dm_2024_guideline::诊断标准"
    }
  ],
  "narrowed_paths": ["knowledge/medical/guidelines/"],
  "narrowed_types": ["guideline"],
  "rewritten_queries": ["2型糖尿病 诊断标准", "糖尿病 HbA1c 切点"],
  "searched_paths": ["knowledge/medical/guidelines/t2dm_2024_guideline.md"],
  "reason": "找到2024版中国2型糖尿病防治指南中的诊断标准，包含HbA1c、空腹血糖和OGTT三个指标。"
}
```

## 特别约束

- 诊断标准必须标注版本和来源
- 必须区分主要诊断标准和次要诊断标准
- 必须列出排除标准
- 禁止用非权威来源的诊断标准

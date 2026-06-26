---
name: medical-guideline-search
description: 临床指南检索技能。当用户询问诊疗规范、专家共识、临床指南推荐、标准治疗方案、疾病管理策略时使用。仅限医学知识库 knowledge/medical/guidelines/ 目录下检索。
---

## 目标

找到最新临床指南中的诊疗建议和推荐等级，回答"应该怎么治"类问题。返回必须包含指南来源、推荐等级、具体建议内容。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## 检索变量说明

| 变量 | 含义 | 默认值 | 可选值 |
|---|---|---|---|
| `organization` | 发布机构 | 无 | `"中华医学会"`, `"NCCN"`, `"WHO"`, `"ADA"` |
| `year_min` | 最早年份 | 2020 | 任意整数 |
| `evidence_level` | 证据等级 | 无 | `"Level I"`, `"Level II"`, `"Level III"` |
| `disease` | 疾病名称 | 自动提取 | 如 `"T2DM"`, `"hypertension"` |

## 推荐命令

### 按疾病 + 指南类型检索

```
kb_metadata_filter(
    query="2型糖尿病 一线治疗 二甲双胍",
    filters={
        "document_type": "guideline",
        "organization": "中华医学会",
        "year_min": 2020
    },
    top_k=5
)
```

### 按治疗目标检索

```
kb_metadata_filter(
    query="高血压 血压控制目标 130/80",
    filters={
        "document_type": "guideline",
        "disease": "hypertension"
    },
    top_k=5
)
```

## 执行步骤

1. **PICO 拆解**
   - P：患者/疾病
   - I：干预措施（如有）
   - O：关注的结局

2. **首次检索**
   - 用 `kb_metadata_filter`，filters 包含 `document_type=guideline`
   - 优先过滤近 5 年指南（`year_min=2020`）
   - 优先权威来源（中华医学会、NCCN、WHO）

3. **推荐等级提取**
   - 从结果中提取推荐等级（Strong / Conditional）
   - 提取证据等级（Level I - IV）

4. **精确定位**
   - 用 `kb_open_chunk` 打开相关 chunk
   - 提取具体推荐内容和剂量

## 结果筛选规则

- 优先**近 5 年**的指南
- 优先**强推荐（Strong Recommendation）**
- 注意指南的**适用范围**（如"适用于成人"、"不适用于孕妇"）
- 不同指南推荐冲突时，优先**最新指南**

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到指南 | `status = "not_found"` |
| 找到指南但无具体推荐 | `status = "partial"` |
| 指南间推荐冲突 | `status = "uncertain"`，列出冲突并标注指南年份 |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/medical/guidelines/t2dm_2024_guideline.md",
      "source_type": "guideline",
      "locator": "三、药物治疗 / 3.1 一线治疗",
      "snippet": "二甲双胍为 T2DM 患者的首选、一线、全程用药。起始剂量 500 mg/d，最佳有效剂量 2000 mg/d。",
      "score": 0.95,
      "parent_id": "t2dm_2024_guideline::三、药物治疗"
    }
  ],
  "narrowed_paths": ["knowledge/medical/guidelines/"],
  "narrowed_types": ["guideline"],
  "rewritten_queries": ["2型糖尿病 一线治疗", "二甲双胍 指南推荐"],
  "searched_paths": ["knowledge/medical/guidelines/t2dm_2024_guideline.md"],
  "reason": "找到2024版中国2型糖尿病防治指南，明确二甲双胍为一线首选药物。"
}
```

## 特别约束

- 必须标注指南来源和年份
- 必须标注推荐等级和证据等级
- 禁止用个人经验替代指南推荐

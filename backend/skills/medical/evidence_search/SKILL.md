---
name: medical-evidence-search
description: 循证医学文献检索技能。当用户询问"有什么证据支持"、"循证医学证据"、"系统综述"、"RCT"、"Meta分析"时使用。基于PICO框架和Cochrane高度敏感检索策略。仅限医学知识库 knowledge/medical/literature/ 目录下检索。
---

## 目标

找到最高等级的循证医学证据回答临床问题。返回必须包含研究类型、证据等级、主要结论。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## PICO 框架

任何临床问题先拆解为 PICO：

| 字母 | 含义 | 示例 |
|---|---|---|
| P | Patient / Problem | 2型糖尿病患者 |
| I | Intervention | 二甲双胍 |
| C | Comparison | 磺脲类 |
| O | Outcome | HbA1c 下降 |

## 证据等级

| 等级 | 类型 | 优先级 |
|---|---|---|
| Level I | 系统综述 / Meta 分析 | 最高 |
| Level II | 随机对照试验（RCT） | 高 |
| Level III | 证据摘要 / 临床指南 | 中高 |
| Level IV | 队列研究 / 病例对照 | 中 |
| Level V | 病例系列 / 专家意见 | 低 |

## 推荐命令

### 按 PICO 检索系统综述

```
kb_metadata_filter(
    query="阿司匹林 心血管疾病 一级预防 系统综述",
    filters={
        "document_type": "literature",
        "study_type": "systematic_review",
        "year_min": 2020
    },
    top_k=5
)
```

### 按研究类型检索 RCT

```
kb_metadata_filter(
    query="二甲双胍 心血管 获益 RCT",
    filters={
        "document_type": "literature",
        "study_type": "RCT",
        "year_min": 2018
    },
    top_k=5
)
```

## 执行步骤

1. **PICO 拆解**
   - 从问题中提取 P、I、C、O
   - 确定问题类型（治疗/诊断/预后/病因）

2. **首次检索**
   - 用 `kb_metadata_filter`
   - 优先过滤 `study_type=systematic_review` 或 `RCT`
   - 优先近 5 年文献

3. **证据等级判断**
   - 从结果中提取研究类型
   - 按证据金字塔排序

4. **精确定位**
   - 用 `kb_open_chunk` 读取关键结论
   - 提取：样本量、主要终点、统计显著性、NNT/NNH

## 结果筛选规则

- 优先**系统综述和 Meta 分析**
- 其次**高质量 RCT**
- 注意**样本量**和**随访时间**
- 注意**发表偏倚**风险

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到系统综述 | 降级检索 RCT |
| 未找到 RCT | 降级检索队列研究 |
| 所有等级均无 | `status = "not_found"` |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/medical/literature/aspirin_cvd_prevention_meta.md",
      "source_type": "literature",
      "locator": "结果 / 主要结局",
      "snippet": "低剂量阿司匹林使 MACE 风险降低 10%（RR 0.90, 95% CI 0.83-0.98），但主要出血风险增加 47%（RR 1.47）。",
      "score": 0.95,
      "parent_id": "aspirin_cvd_prevention_meta::结果"
    }
  ],
  "narrowed_paths": ["knowledge/medical/literature/"],
  "narrowed_types": ["literature"],
  "rewritten_queries": ["阿司匹林 心血管 一级预防 Meta分析", "aspirin primary prevention systematic review"],
  "searched_paths": ["knowledge/medical/literature/aspirin_cvd_prevention_meta.md"],
  "reason": "找到2021年JACC系统综述，阿司匹林一级预防获益与风险并存。"
}
```

## 特别约束

- 必须标注研究类型和证据等级
- 必须包含统计指标（RR/OR/HR, 95% CI, p值）
- 禁止用个案报道支持一般性结论
- 必须说明研究局限性

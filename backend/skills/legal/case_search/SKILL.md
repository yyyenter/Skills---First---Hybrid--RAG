---
name: legal-case-search
description: 法律判例检索技能。当用户询问类似案例、判例、裁判规则、法院怎么判、指导性案例、司法实践时使用。仅限法律知识库 knowledge/legal/cases/ 目录下检索。
---

## 目标

找到与问题相关的判例、裁判规则和法院观点，回答"法院怎么判"类问题。返回必须包含案例名称、法院层级、裁判要点和适用法条。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索（向量 + BM25） | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## 检索变量说明

| 变量 | 含义 | 默认值 | 可选值 |
|---|---|---|---|
| `court_level` | 法院层级 | 无优先级 | `"supreme"`, `"high"`, `"intermediate"`, `"basic"` |
| `year_min` | 最早年份 | 2020 | 任意整数 |
| `case_type` | 案件类型 | 无 | `"civil"`, `"criminal"`, `"administrative"`, `"contract"` |
| `legal_domain` | 法律领域 | 无 | `"contract"`, `"tort"`, `"property"`, `"ip"`, `"labor"` |

## 推荐命令

### 按核心法律原则检索（One Good Case Method）

```
kb_metadata_filter(
    query="商品房预售合同 解除权 除斥期间",
    filters={
        "document_type": "case",
        "court_level": "supreme",
        "year_min": 2020
    },
    top_k=8
)
```

### 按案件类型 + 关键词检索

```
kb_metadata_filter(
    query="跳单 居间合同 违约",
    filters={
        "document_type": "case",
        "case_type": "civil",
        "legal_domain": "contract"
    },
    top_k=5
)
```

### 从已知法条找相关判例

```
kb_search(
    query="民法典第563条 合同解除 判例",
    path_filter="knowledge/legal/cases/",
    top_k=5
)
```

## 执行步骤

1. **提取检索要素**
   - 核心法律关系（如"居间合同"、"预售合同"）
   - 关键事实特征（如"跳单"、"除斥期间"）
   - 法院层级偏好（未指定则优先最高法）

2. **首次检索（One Good Case）**
   - 用 `kb_metadata_filter`，filters 包含 `document_type=case`
   - 优先过滤 `court_level=supreme`
   - 优先过滤 `year_min=2020`（近5年优先）

3. **从好案例向外扩展**
   - 从 Step 2 结果中选择最相关的 1 个判例
   - 用 `kb_open_chunk` 读取完整裁判要点
   - 提取该判例引用的法条编号
   - 用该法条编号再次检索，找其他引用同一条款的判例

4. **层级扩展（如最高法案例不足）**
   - 放宽 `court_level` 过滤，加入高院、中院案例
   - 注意标注法院层级差异（指导性案例 > 典型案例 > 一般判例）

### 扩展检索策略

如果 Step 2-3 未找到足够判例：

```
策略 A：同义词扩展
  kb_search(query="违约 OR 违反合同 OR 不履行", path_filter="knowledge/legal/cases/", top_k=5)

策略 B：上位概念检索
  kb_search(query="合同责任", path_filter="knowledge/legal/cases/", top_k=5)

策略 C：如果仍找不到 → status 标记为 not_found
```

## 结果筛选规则

- 优先**指导性案例**、**公报案例**、**最高法典型案例**
- 同一法律问题多个判例时，优先**最新判例**
- 注意判例是否被后续判例**推翻或限缩**
- 对比判例时要标注法院层级差异
- 不要只用一条判例下结论，至少引用 2-3 个判例

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到任何判例 | `status = "not_found"`，说明"未找到相关判例" |
| 仅找到原则性论述 | `status = "partial"`，说明"找到裁判思路，但缺少具体判例支撑" |
| 判例之间存在冲突 | `status = "uncertain"`，列出冲突判例并标注法院层级 |
| 判例已被推翻 | `status = "uncertain"`，标注最新裁判规则 |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/legal/cases/contract_termination_case.md",
      "source_type": "case",
      "locator": "指导案例 1 号",
      "snippet": "当卖方将同一房屋通过多个中介公司挂牌出售时，买方通过其他公众可以获知的正当途径获得相同房源信息的，不构成违约。",
      "score": 0.92,
      "parent_id": "contract_termination_case::指导案例 1 号"
    }
  ],
  "narrowed_paths": ["knowledge/legal/cases/"],
  "narrowed_types": ["case"],
  "rewritten_queries": ["跳单 居间合同 违约", "中介合同 跳单 裁判规则"],
  "searched_paths": ["knowledge/legal/cases/contract_termination_case.md"],
  "reason": "找到最高法指导案例1号关于跳单违约的裁判规则，明确不构成违约的条件。"
}
```

## 特别约束

- 禁止编造不存在的判例名称或案号
- 引用判例必须标注法院层级和案例编号
- 判例引用不能替代法条，必须同时标注适用法条

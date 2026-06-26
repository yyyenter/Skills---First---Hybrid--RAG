---
name: legal-contract-clause-search
description: 合同条款检索技能。当用户询问合同范本条款、CUAD 标准条款类型、合同中的具体条款内容（如竞业限制、保密条款、违约责任等）时使用。仅限法律知识库 knowledge/legal/contracts/ 目录下检索。
---

## 目标

找到合同范本中的具体条款内容，回答合同条款相关问题。返回必须包含条款原文、条款类型（CUAD 分类）、适用场景说明。

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

## CUAD 条款类型对照表

用户问题映射到 CUAD 标准条款类别：

| CUAD 类别 | 常见用户问法 | 中文术语 |
|---|---|---|
| Agreement Date | "合同什么时候签的" | 签订日期 |
| Effective Date | "合同什么时候生效" | 生效日期 |
| Expiration Date | "合同什么时候到期" | 到期日 |
| Renewal Term | "能不能续签" | 续租/续约条款 |
| Non-Compete | "竞业限制"、"离职后不能去竞争对手" | 竞业限制条款 |
| Exclusivity | "独家"、"排他" | 独家/排他条款 |
| No-Solicit of Customers | "不能挖客户" | 不招揽客户条款 |
| Change of Control | "公司被收购怎么办" | 控制权变更条款 |
| Anti-Assignment | "能不能把合同转给别人" | 禁止转让条款 |
| License Grant | "授权范围" | 许可授权条款 |
| Cap on Liability | "最多赔多少" | 责任限额条款 |
| Governing Law | "适用什么法律" | 准据法条款 |

## 推荐命令

### 按 CUAD 条款类型检索

```
kb_metadata_filter(
    query="竞业限制 期限 范围",
    filters={
        "document_type": "contract",
        "cuad_category": "Non-Compete"
    },
    top_k=5
)
```

### 按合同类型 + 条款关键词检索

```
kb_metadata_filter(
    query="违约责任 赔偿限额",
    filters={
        "document_type": "contract",
        "contract_type": "commercial_lease"
    },
    top_k=5
)
```

### 打开具体条款查看上下文

```
kb_open_chunk(parent_id="commercial_lease_template::第五条")
```

## 执行步骤

1. **映射 CUAD 类型**
   - 将用户问题映射到上表中最接近的 CUAD 条款类别
   - 同时考虑相关的 2-3 个邻近类别

2. **首次检索**
   - 用 `kb_metadata_filter`，filters 包含 `document_type=contract`
   - 如果知道合同类型，加入 `contract_type` 过滤
   - 如果知道 CUAD 类型，加入 `cuad_category` 过滤

3. **比对多个范本**
   - 找到多个合同范本中的相同条款
   - 提取差异点（如不同范本的责任限额不同）

4. **精确定位条款内容**
   - 用 `kb_open_chunk` 打开找到的 chunk
   - 提取完整条款文本

## 结果筛选规则

- 优先**标准合同范本**（如住建部范本、商务部范本）
- 同一条款多个范本时，列出差异供用户参考
- 注意条款的**生效条件**和**例外情形**
- 区分"标准条款"和"协商条款"

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到对应条款 | `status = "not_found"`，说明"未找到该条款类型的合同范本" |
| 找到条款但缺少上下文 | `status = "partial"`，说明"找到条款文本，但缺少适用条件说明" |
| 不同范本条款差异大 | `status = "uncertain"`，列出差异并标注范本来源 |

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [
    {
      "source_path": "knowledge/legal/contracts/commercial_lease_template.md",
      "source_type": "contract",
      "locator": "第五条 违约责任",
      "snippet": "任何一方的赔偿责任总额不得超过 3 个月租金。",
      "score": 0.95,
      "parent_id": "commercial_lease_template::第五条"
    }
  ],
  "narrowed_paths": ["knowledge/legal/contracts/"],
  "narrowed_types": ["contract"],
  "rewritten_queries": ["竞业限制 合同条款", "违约责任 赔偿限额"],
  "searched_paths": ["knowledge/legal/contracts/commercial_lease_template.md"],
  "reason": "找到商业租赁合同范本中关于责任限额的条款，明确赔偿上限为3个月租金。"
}
```

## 特别约束

- 必须标注条款所属的 CUAD 标准类别
- 引用合同条款必须标注合同类型和条款编号
- 禁止编造不存在的合同条款

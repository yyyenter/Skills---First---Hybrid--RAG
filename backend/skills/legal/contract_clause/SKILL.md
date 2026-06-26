---
name: legal-contract-clause-search
description: 合同条款检索技能。当用户询问合同范本条款、CUAD 标准条款类型、合同中的具体条款内容（如竞业限制、保密条款、违约责任等）时使用。仅限法律知识库 knowledge/legal/contracts/ 目录下检索。
---

## 目标

找到合同范本中的具体条款内容，回答合同条款相关问题。返回必须包含条款原文、条款类型（CUAD 分类）、适用场景说明。

## 路由决策（必须先执行）

**规则**：分析用户问题，先输出路由决策 JSON，再调用任何工具。

| 优先级 | 条件 | 方法 |
|---|---|---|
| P0 | 含"合不合理"、"有没有效"、"合法吗" | Bridge Entity Hop（条款→法律标准） |
| P1 | 含"有什么不同"、"A和B的区别"、"对比" | Comparison Hop（条款对比/范本对比） |
| P2 | 含"什么情况下"、"怎么触发"、"适用条件" | Legal Element Hop（触发条件分析） |
| P3 | 以上都不匹配 | 单跳 |

```json
{"method":"Bridge Entity Hop|Comparison Hop|Legal Element Hop|single","reason":"一句话说明","sub_queries":[{"step":1,"query":"...","tool":"kb_search|kb_metadata_filter"}]}
```

## 适用场景与触发条件

| 场景 | 示例 |
|---|---|
| 条款内容查询 | "竞业限制条款一般怎么写？" |
| 条款对比 | "技术许可合同和商品销售合同的违约责任条款有什么不同？" |
| 条款适用 | "什么情况下可以触发控制权变更条款？" |
| 条款缺失分析 | "这个合同缺了什么重要条款？" |

---

## 查询重写与意图挖掘

### 术语规范化映射表

| 口语化表达 | 专业术语 / CUAD 类别 | 映射原因 |
|---|---|---|
| "不能去竞争对手" | "Non-Compete / 竞业限制条款" | CUAD Group 2 |
| "独家代理" | "Exclusivity / 独家/排他条款" | CUAD Group 2 |
| "不能挖客户" | "No-Solicit of Customers / 不招揽客户条款" | CUAD Group 2 |
| "公司被收购怎么办" | "Change of Control / 控制权变更条款" | CUAD Group 3 |
| "能不能转给第三方" | "Anti-Assignment / 禁止转让条款" | CUAD Group 3 |
| "最多赔多少" | "Cap on Liability / 责任限额条款" | CUAD Group 6 |
| "适用什么法律" | "Governing Law / 准据法条款" | 独立 |
| "合同什么时候签的" | "Agreement Date / 签订日期" | CUAD Group 1 |
| "能不能续签" | "Renewal Term / 续约条款" | CUAD Group 1 |
| "授权范围" | "License Grant / 许可授权条款" | CUAD Group 4 |
| "源代码托管" | "Source Code Escrow / 源代码托管条款" | 独立 |
| "审计权利" | "Audit Rights / 审计权条款" | CUAD Group 5 |
| "保密" | "Confidentiality / 保密条款（注：非CUAD标准，但常见）" | 需补充检索 |
| "知识产权归属" | "IP Ownership Assignment / 知识产权归属条款" | 独立 |

### 合同类型识别

**用户问题中可能隐含合同类型，需要识别：**

| 用户表达 | 合同类型 | 说明 |
|---|---|---|
| "技术合作" | "技术许可协议 / 技术开发合同" | 知识产权密集型 |
| "买房" / "租房" | "商品房买卖合同 / 租赁合同" | 不动产相关 |
| "卖软件" | "软件许可协议 / SaaS协议" | 许可类 |
| "加盟" | "特许经营合同 / 加盟协议" | 连锁经营 |
| "雇佣" | "劳动合同 / 劳务合同" | 劳动关系 |
| "投资" | "股权投资协议 / 增资协议" | 投融资 |

### 意图挖掘检查清单

1. **用户要的是条款范本，还是条款分析？**
   - "竞业限制条款怎么写" → 要范本，单跳
   - "这个竞业限制条款合不合理" → **需要分析，可能需要多跳（条款→法律标准→合理性判断）**

2. **用户是否隐含了合同类型？**
   - "技术合作的保密条款" → 隐含合同类型 = 技术许可
   - 不知道合同类型时，需要先检索通用条款，再检索特定类型

3. **用户是否隐含了比较需求？**
   - "竞业限制和保密条款有什么区别" → **Comparison Hop**
   - "技术合同和劳动合同的竞业限制一样吗" → **Comparison Hop**

4. **用户是否问的是条款触发条件？**
   - "什么情况下可以解除合同" → 需要 Bridge Entity Hop（条款→触发条件→适用场景）

### 查询重写策略

**策略1：CUAD 类型映射**
```
原始："竞业限制"
重写："Non-Compete 竞业限制 条款范本"
```

**策略2：合同类型限定**
```
原始："技术合作的保密条款"
重写："技术许可协议 保密条款 范本"
```

**策略3：条款对比**
```
原始："竞业限制和保密条款有什么区别"
重写1："Non-Compete 条款 范围 期限"
重写2："Confidentiality 条款 范围 期限"
```

---

## 多跳检索判断

### 单跳即可的场景

- 用户明确给出了 CUAD 条款类型
- 用户只需要某个条款的范本内容
- **示例**："竞业限制条款一般怎么写？"

### 需要多跳的场景

#### 场景A：Bridge Entity Hop（条款→法律标准）
**适用**：用户需要判断条款的合法性/合理性

**示例**：
```
问题："竞业限制期限写5年有效吗？"
分析：需要条款范本 + 法律标准

多跳步骤：
  跳1：检索竞业限制条款范本
    kb_search(query="Non-Compete 竞业限制 条款范本", top_k=2)
    → 常见写法：1-2年
    
  跳2：检索法律对竞业限制期限的规定
    kb_search(query="竞业限制 期限 法律 劳动合同法", top_k=2)
    → 法律规定：最长2年
    
  融合：条款范本 + 法律标准 = 合法性判断（5年无效）
```

#### 场景B：Comparison Hop（条款对比）
**适用**：用户需要对比不同类型合同中的相同条款

**示例**：
```
问题："技术许可合同和商品销售合同的违约责任条款有什么不同？"
分析：需要分别检索两种合同的违约责任条款，再对比

多跳步骤：
  跳1：检索技术许可合同的违约责任
    kb_search(query="技术许可协议 违约责任 条款", top_k=2)
    → 条款A：知识产权侵权赔偿
    
  跳2：检索商品销售合同的违约责任
    kb_search(query="商品销售合同 违约责任 条款", top_k=2)
    → 条款B：质量瑕疵赔偿
    
  融合：对比条款A和条款B的差异
```

#### 场景C：Legal Element Hop（条款触发条件分析）
**适用**：用户需要了解条款的适用条件和触发机制

**示例**：
```
问题："什么情况下可以触发控制权变更条款？"
分析：需要拆解控制权变更条款的触发条件

多跳步骤：
  跳1：检索控制权变更条款的定义
    kb_search(query="Change of Control 定义 触发条件", top_k=2)
    → 触发条件1：股权变更50%以上
    → 触发条件2：合并、分立
    → 触发条件3：资产出售
    
  跳2：检索各触发条件的具体适用
    kb_search(query="股权变更 50% 控制权变更 适用", top_k=2)
    kb_search(query="合并分立 控制权变更 条款", top_k=2)
    
  融合：按触发条件组织答案
```

---

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索 | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

---

## CUAD 条款类型对照表

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

---

## 执行步骤

1. **映射 CUAD 类型**
   - 将用户问题映射到 CUAD 条款类别
   - 识别隐含合同类型

2. **查询重写**
   - 用术语映射表转换口语化表达
   - 识别 CUAD 类型和合同类型

3. **判断是否需要多跳**
   - 需要合法性判断 → Bridge Entity Hop
   - 需要对比 → Comparison Hop
   - 需要触发条件分析 → Legal Element Hop

4. **执行检索**

5. **比对多个范本**（如需要）

---

## 推荐命令

### 单跳：按 CUAD 类型检索

```python
kb_metadata_filter(
    query="竞业限制 期限 范围",
    filters={
        "document_type": "contract",
        "cuad_category": "Non-Compete"
    },
    top_k=5
)
```

### 多跳：条款→法律标准

```python
# 跳1：条款范本
clause = kb_search(query="Non-Compete 竞业限制 范本", top_k=2)

# 跳2：法律标准
law = kb_search(query="竞业限制 期限 法律 2年", top_k=2)
```

---

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到对应条款 | `status = "not_found"` |
| 找到条款但缺少上下文 | `status = "partial"` |
| 不同范本条款差异大 | `status = "uncertain"`，列出差异 |

---

## 输出格式

```json
{
  "status": "success | partial | not_found | uncertain",
  "evidences": [...],
  "multi_hop": {
    "used": false,
    "method": null,
    "steps": []
  },
  "reason": "找到竞业限制条款范本，符合CUAD Non-Compete类别。"
}
```

---

## 特别约束

- 必须标注条款所属的 CUAD 标准类别
- 引用合同条款必须标注合同类型和条款编号
- 禁止编造不存在的合同条款

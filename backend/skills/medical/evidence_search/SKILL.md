---
name: medical-evidence-search
description: 循证医学文献检索技能。当用户询问"有什么证据支持"、"循证医学证据"、"系统综述"、"RCT"、"Meta分析"、"A药和B药哪个更好"时使用。基于PICO框架和Cochrane高度敏感检索策略。
---

## 目标

找到最高等级的循证医学证据回答临床问题。返回必须包含研究类型、证据等级、主要结论。

## 路由决策（必须先执行）

**规则**：分析用户问题，先输出路由决策 JSON，再调用任何工具。

| 优先级 | 条件 | 方法 |
|---|---|---|
| P0 | 含"哪个更好"、"A和B"、"比较"、"vs" | Comparison Hop（分别检索A/B证据→对比） |
| P1 | 含"为什么"、"机制"、"通过什么" | Bridge Entity Hop（PICO→机制→临床证据） |
| P2 | 含"从...到..."、"进展"、"几年后" | Temporal Chain Hop（时序证据链） |
| P3 | 含多个独立问题（用逗号/句号分隔3个以上主题） | 拆分为多个单跳 |
| P4 | 以上都不匹配 | 单跳（PICO→kb_search） |

```json
{"method":"Comparison Hop|Bridge Entity Hop|Temporal Chain Hop|single","reason":"一句话说明","sub_queries":[{"step":1,"query":"...","tool":"kb_search|kb_metadata_filter"}]}
```

## 适用场景与触发条件

| 场景 | 示例 |
|---|---|
| 治疗证据 | "二甲双胍对心梗有没有保护作用？" |
| 比较证据 | "阿司匹林和氯吡格雷哪个更适合二级预防？" |
| 诊断证据 | "HbA1c 6.5%诊断糖尿病的敏感度是多少？" |
| 预后证据 | "T2DM患者10年心血管风险是多少？" |
| 病因证据 | "肥胖和2型糖尿病的因果关系有什么证据？" |

---

## 查询重写与意图挖掘

### 术语规范化映射表

| 口语化表达 | 专业术语 | 映射原因 |
|---|---|---|
| "血糖药" / "降糖药" | "二甲双胍 / SGLT2抑制剂 / DPP-4抑制剂 / GLP-1RA / 胰岛素" | 必须具体化到药物类别或通用名，否则检索结果太泛 |
| "伤肾" / "对肾不好" | "肾功能不全 / eGFR下降 / 肾毒性 / 急性肾损伤" | 医学术语需精确到指标或诊断标准 |
| "心脏病" | "心血管疾病 / 心肌梗死 / 心力衰竭 / 房颤" | 需具体化到疾病亚型 |
| "血压高" | "高血压 / 原发性高血压 / 血压控制目标" | 区分疾病 vs 症状 |
| "吃多少" | "剂量 / 用法用量 / 起始剂量 / 维持剂量" | 需对应到具体用药方案 |
| "有没有用" | "疗效 / 有效性 / 获益 / 风险降低" | 需对应到具体临床终点 |
| "哪个更好" | "比较 / 优效性 / 非劣效性 / 网络Meta分析" | 需识别比较型问题的证据等级 |
| "长期吃安全吗" | "安全性 / 不良反应 / 长期随访 / 耐受性" | 安全性问题需单独检索 |

### 意图挖掘检查清单

**执行每次检索前，先回答以下问题：**

1. **用户表面问的是定义/概念，还是证据？**
   - 如果问"什么是P值" → 这是定义问题，**不需要**循证检索，返回 `status="not_found"`，指引到 medical-diagnosis-search
   - 如果问"P<0.05的证据可靠吗" → 这是证据评价问题，需要循证文献

2. **用户是否隐含了比较需求？**
   - "二甲双胍怎么样" → 单药疗效，单跳检索
   - "二甲双胍和胰岛素哪个好" → **比较型问题，需要多跳**（分别检索A和B，再比较）

3. **用户是否隐含了因果推断？**
   - "肥胖会不会导致糖尿病" → 病因证据，需要流行病学研究
   - "糖尿病患者为什么容易得肾病" → 机制证据，需要基础研究+临床证据

4. **用户是否隐含了时间/进展维度？**
   - "刚开始吃药要注意什么" → 短期安全性
   - "吃了10年会不会有问题" → 长期随访证据，可能需要时序多跳

5. **用户是否把多个问题混在一起？**
   - "二甲双胍怎么吃，有什么副作用，对心脏好不好" → **三合一问题，必须拆成3个子查询**

### 查询重写策略

**策略1：PICO拆解重写**
```
原始："阿司匹林对心梗一级预防有用吗？"
  ↓ PICO拆解
P：无心血管病史的成年人
I：低剂量阿司匹林
C：安慰剂/不干预
O：主要心血管事件（MACE）
  ↓ 重写
"aspirin primary prevention cardiovascular disease systematic review"
"阿司匹林 一级预防 心血管事件 系统综述"
```

**策略2：同义词扩展**
```
原始："血糖药伤肾"
扩展："metformin renal impairment" OR "SGLT2 inhibitor kidney function" OR "hypoglycemic agent nephrotoxicity"
扩展："降糖药 肾功能不全" OR "口服降糖药 eGFR" OR "二甲双胍 肾毒性"
```

**策略3：证据等级限定**
```
原始："二甲双胍心血管保护"
重写："metformin cardiovascular benefit meta-analysis"（优先系统综述）
重写："metformin cardiovascular benefit RCT"（如系统综述不足，降级检索RCT）
```

**策略4：中英文混合**
```
原始："SGLT2 inhibitor heart failure"
重写："SGLT2抑制剂 心力衰竭 指南推荐"（中文指南可能包含更详细的推荐等级）
```

---

## 多跳检索判断

### 单跳即可的场景（直接执行 kb_search）

- 问题只有一个明确的 PICO 要素
- 用户只需要某个药物/干预的单一证据
- 问题不涉及比较、因果、时序
- **示例**："二甲双胍对T2DM的疗效有什么证据？"

### 需要多跳的场景（必须拆分执行）

#### 场景A：Bridge Entity Hop（桥接实体跳）
**适用**：问题需要先找到中间实体，再用中间实体找最终答案

**判断标准**：
- 问题形式："A对B的C有什么影响？"（A→C→B 或 A→B→C）
- 问题涉及机制推断："为什么A会导致B？"

**示例**：
```
问题："二甲双胍通过什么机制保护心血管？"
分析：
  实体A = 二甲双胍
  实体B = 心血管保护
  中间机制C = AMPK通路 / 抗炎 / 内皮功能
  
多跳步骤：
  跳1：检索"二甲双胍 作用机制 AMPK" → 找到机制C
  跳2：检索"AMPK 心血管保护 机制" → 验证C→B的因果关系
  跳3（可选）：检索"二甲双胍 心血管 临床试验" → 确认临床证据
```

**执行代码**：
```python
# 跳1：找机制
result1 = kb_search(query="metformin mechanism AMPK cardiovascular", top_k=3)
mechanism = extract_mechanism(result1)  # 如 "AMPK activation"

# 跳2：验证机制→结局
result2 = kb_search(query=f"{mechanism} cardiovascular protection clinical evidence", top_k=3)
```

#### 场景B：Comparison Hop（比较跳）
**适用**：问题涉及两个或多个实体的比较

**判断标准**：
- 问题含"哪个更好"、"A vs B"、"比较"、"优劣"、"选择"
- 问题隐含了决策需求

**示例**：
```
问题："二甲双胍和SGLT2抑制剂哪个对心衰更好？"
分析：这是比较型问题，必须分别检索A和B，再比较

多跳步骤：
  跳1：检索"二甲双胍 心力衰竭 证据" → 收集证据A
  跳2：检索"SGLT2抑制剂 心力衰竭 证据" → 收集证据B
  跳3：检索"二甲双胍 SGLT2抑制剂 心力衰竭 比较" → 直接比较研究（Head-to-head）
  融合：对比证据A和证据B的等级、样本量、效应值
```

**执行代码**：
```python
# 跳1：检索A
evidence_A = kb_search(query="metformin heart failure evidence", top_k=3)

# 跳2：检索B
evidence_B = kb_search(query="SGLT2 inhibitor heart failure evidence", top_k=3)

# 跳3：检索直接比较
comparison = kb_search(query="metformin vs SGLT2 heart failure head-to-head", top_k=3)
```

#### 场景C：Temporal Chain Hop（时序链跳）
**适用**：问题涉及时间进展、随访、长期安全性

**判断标准**：
- 问题含"长期"、"随访"、"进展"、"几年后"、"从...到..."
- 问题涉及疾病自然史或治疗时间线

**示例**：
```
问题："糖尿病肾病从微量白蛋白尿发展到肾衰竭需要多久？"
分析：这是时序问题，需要追踪疾病的自然进展

多跳步骤：
  跳1：检索"糖尿病肾病 微量白蛋白尿 定义 诊断标准"
  跳2：检索"糖尿病肾病 大量白蛋白尿 进展时间 队列研究"
  跳3：检索"糖尿病肾病 肾衰竭 ESRD 进展 预后"
  融合：串联时间线，给出从stage 1到stage 5的典型进展时间
```

### 多跳执行通用流程

```
Step 1: 判断是否需要多跳
  └─→ 如果单跳即可 → 直接执行 kb_search
  └─→ 如果需要多跳 → 继续

Step 2: 选择多跳方法
  └─→ 含"为什么/机制" → Bridge Entity Hop
  └─→ 含"比较/哪个更好" → Comparison Hop
  └─→ 含"时间/进展/长期" → Temporal Chain Hop
  └─→ 混合类型 → 组合使用

Step 3: 拆分子查询
  └─→ 每个子查询必须有明确的单一目标
  └─→ 子查询之间必须有逻辑依赖关系
  └─→ 每个子查询调用一次 kb_search 或 kb_metadata_filter

Step 4: 逐步执行
  └─→ 跳1：执行第一个子查询
  └─→ 提取关键实体/结论（从 snippet 中提取）
  └─→ 跳2：用提取的实体构建第二个查询
  └─→ ...
  └─→ 跳N：最终查询

Step 5: 融合所有跳的结果
  └─→ 按逻辑关系组织答案
  └─→ 标注每跳的查询和来源
  └─→ 如果某跳返回空，标注并降级结论
```

---

## 可用工具

| 工具名称 | 用途 | 必选参数 | 可选参数 |
|---|---|---|---|
| `kb_search` | 混合检索（向量 + BM25） | `query` | `top_k`, `path_filter` |
| `kb_metadata_filter` | 带元数据过滤的检索 | `query`, `filters` | `top_k` |
| `kb_open_chunk` | 打开指定 chunk 的完整内容 | `parent_id` | 无 |

---

## PICO 框架

任何临床问题先拆解为 PICO：

| 字母 | 含义 | 示例 |
|---|---|---|
| P | Patient / Problem | 2型糖尿病患者 |
| I | Intervention | 二甲双胍 |
| C | Comparison | 磺脲类 / 安慰剂 |
| O | Outcome | HbA1c 下降 / 心血管事件减少 |

**PICO 拆解是多跳判断的基础**：
- 如果用户只提供了 P 和 I → 单跳检索
- 如果用户提供了 P + I + C → 可能需要 Comparison Hop
- 如果用户提供了 P + I + O → 单跳，但需限定结局类型
- 如果用户问的是机制（为什么 I 导致 O）→ Bridge Entity Hop

---

## 证据等级

| 等级 | 类型 | 优先级 |
|---|---|---|
| Level I | 系统综述 / Meta 分析 | 最高 |
| Level II | 随机对照试验（RCT） | 高 |
| Level III | 证据摘要 / 临床指南 | 中高 |
| Level IV | 队列研究 / 病例对照 | 中 |
| Level V | 病例系列 / 专家意见 | 低 |

---

## 执行步骤

### 单跳执行流程

1. **PICO 拆解**
   - 从问题中提取 P、I、C、O
   - 确定问题类型（治疗/诊断/预后/病因）

2. **查询重写**
   - 用"术语规范化映射表"把口语化表达转成专业术语
   - 用"查询重写策略"扩展同义词和限定证据等级

3. **首次检索**
   - 用 `kb_metadata_filter`
   - 优先过滤 `study_type=systematic_review` 或 `RCT`
   - 优先近 5 年文献

4. **证据等级判断**
   - 从结果中提取研究类型
   - 按证据金字塔排序

5. **精确定位**
   - 用 `kb_open_chunk` 读取关键结论
   - 提取：样本量、主要终点、统计显著性、NNT/NNH

### 多跳执行流程

1. **判断多跳类型**（见"多跳检索判断"章节）
2. **拆分子查询**，每个子查询对应一次工具调用
3. **逐跳执行**，每跳后提取关键实体
4. **融合结果**，按逻辑关系组织

---

## 推荐命令

### 单跳：按 PICO 检索系统综述

```python
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

### 多跳：Bridge Entity（机制推断）

```python
# 跳1：找机制
result1 = kb_search(query="metformin AMPK mechanism cardiovascular", top_k=3)
# 从 result1 提取机制关键词，如 "AMPK activation"

# 跳2：验证机制→临床结局
result2 = kb_search(query="AMPK activation cardiovascular protection clinical trial", top_k=3)
```

### 多跳：Comparison（药物比较）

```python
# 跳1：检索药物A
evidence_A = kb_search(query="metformin heart failure evidence", top_k=3)

# 跳2：检索药物B
evidence_B = kb_search(query="SGLT2 inhibitor heart failure evidence", top_k=3)

# 跳3：检索直接比较
comparison = kb_search(query="metformin vs SGLT2 heart failure head-to-head", top_k=3)
```

### 多跳：Temporal Chain（疾病进展）

```python
# 跳1：诊断标准
stage1 = kb_search(query="diabetic nephropathy microalbuminuria definition", top_k=2)

# 跳2：进展时间
progression = kb_search(query="diabetic nephropathy progression time ESRD cohort", top_k=3)

# 跳3：预后因素
prognosis = kb_search(query="diabetic nephropathy risk factors rapid progression", top_k=2)
```

---

## 结果筛选规则

- 优先**系统综述和 Meta 分析**
- 其次**高质量 RCT**
- 注意**样本量**和**随访时间**
- 注意**发表偏倚**风险
- 比较型问题必须有**直接比较研究**或**网络Meta分析**

---

## 失败处理

| 场景 | 处理方式 |
|---|---|
| 未找到系统综述 | 降级检索 RCT |
| 未找到 RCT | 降级检索队列研究 |
| 所有等级均无 | `status = "not_found"` |
| 多跳中某跳为空 | 标注该跳缺失，用其他跳的结果补充，`status = "partial"` |
| 多跳结果矛盾 | `status = "uncertain"`，列出矛盾并分析原因 |

---

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
      "parent_id": "aspirin_cvd_prevention_meta::结果",
      "hop": 1
    }
  ],
  "narrowed_paths": ["knowledge/medical/literature/"],
  "narrowed_types": ["literature"],
  "rewritten_queries": ["阿司匹林 心血管 一级预防 Meta分析", "aspirin primary prevention systematic review"],
  "searched_paths": ["knowledge/medical/literature/aspirin_cvd_prevention_meta.md"],
  "multi_hop": {
    "used": true,
    "method": "Comparison Hop",
    "steps": [
      {"hop": 1, "query": "metformin heart failure evidence", "result_count": 3},
      {"hop": 2, "query": "SGLT2 inhibitor heart failure evidence", "result_count": 3},
      {"hop": 3, "query": "metformin vs SGLT2 heart failure head-to-head", "result_count": 1}
    ]
  },
  "reason": "通过Comparison Hop分别检索二甲双胍和SGLT2抑制剂的心衰证据，再查找直接比较研究。"
}
```

---

## 特别约束

- 必须标注研究类型和证据等级
- 必须包含统计指标（RR/OR/HR, 95% CI, p值）
- 禁止用个案报道支持一般性结论
- 必须说明研究局限性
- 多跳检索必须在输出中标注每跳的查询和结果数量

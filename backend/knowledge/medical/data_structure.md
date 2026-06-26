# 医学知识库目录结构

## 目录说明

| 子目录 | 说明 | 文档数 | 证据等级 |
|---|---|---|---|
| `guidelines/` | 临床指南、专家共识 | 8 | Level IV |
| `drugs/` | 药品说明书、药物相互作用 | 12 | Level V |
| `diseases/` | 疾病诊疗规范、诊断标准 | 10 | Level IV |
| `literature/` | 系统综述、RCT 文献 | 15 | Level I-III |

## PICO 框架覆盖

本知识库遵循循证医学 PICO 框架：
- **P**: Patient / Problem（患者/问题）
- **I**: Intervention（干预措施）
- **C**: Comparison（对照）
- **O**: Outcome（结局指标）

## 循证医学证据金字塔

| 证据等级 | 类型 | 本库覆盖情况 |
|---|---|---|
| Level I | 系统综述、Meta 分析 | ✅ literature/ |
| Level II | 随机对照试验（RCT） | ✅ literature/ |
| Level III | 证据摘要 | ✅ literature/ |
| Level IV | 临床指南 | ✅ guidelines/ |
| Level V-VII | 队列研究、病例系列 | ✅ literature/ |
| Level VIII | 专家意见、机制研究 | ✅ diseases/ |

## 检索提示

- 临床指南检索优先使用 `guidelines/` 目录
- 药物信息检索优先使用 `drugs/` 目录
- 循证文献检索使用 `literature/` 目录
- 疾病诊断标准使用 `diseases/` 目录

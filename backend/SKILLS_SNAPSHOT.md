<skills>
  <summary>Available local skills that the agent can inspect with read_file.</summary>
  <skill name="天气查询" path="skills/get_weather/SKILL.md">
    <description>查询指定城市的天气情况，并整理成适合直接回复用户的简洁结果。</description>
  </skill>
  <skill name="kb-retriever" path="skills/rag-skill/SKILL.md">
    <description>面向本地知识库目录的通用检索和问答助手。核心流程：(1)分层索引导航 (2)遇到PDF/Excel时必须先读取references学习处理方法 (3)处理文件后再检索。按文件类型组合使用 grep、Read、pdfplumber、pandas 进行渐进式检索，避免整文件加载。用户问题涉及"从知识库目录回答问题/检索信息/查资料"时使用。</description>
  </skill>
  <skill name="legal-statute-search" path="skills/legal/statute_search/SKILL.md">
    <description>法律成文法/法规检索技能。当用户询问法条原文、法律规定、法律条款内容、某类行为的法律后果、具体法律名称中的条文时使用。仅限法律知识库 knowledge/legal/statutes/ 目录下检索。</description>
  </skill>
  <skill name="legal-case-search" path="skills/legal/case_search/SKILL.md">
    <description>法律判例检索技能。当用户询问类似案例、判例、裁判规则、法院怎么判、指导性案例、司法实践时使用。仅限法律知识库 knowledge/legal/cases/ 目录下检索。</description>
  </skill>
  <skill name="legal-contract-clause" path="skills/legal/contract_clause/SKILL.md">
    <description>合同条款检索技能。当用户询问合同范本条款、CUAD 标准条款类型、合同中的具体条款内容（如竞业限制、保密条款、违约责任等）时使用。仅限法律知识库 knowledge/legal/contracts/ 目录下检索。</description>
  </skill>
  <skill name="legal-definition-search" path="skills/legal/legal_definition/SKILL.md">
    <description>法律术语/概念定义检索技能。当用户询问"什么是X"、"X的定义"、"X的构成要件"、"X的法律含义"时使用。检索法律知识库中的法条定义、司法解释定义和权威学术定义。</description>
  </skill>
  <skill name="medical-guideline-search" path="skills/medical/guideline_search/SKILL.md">
    <description>临床指南检索技能。当用户询问诊疗规范、专家共识、临床指南推荐、标准治疗方案、疾病管理策略时使用。仅限医学知识库 knowledge/medical/guidelines/ 目录下检索。</description>
  </skill>
  <skill name="medical-drug-search" path="skills/medical/drug_search/SKILL.md">
    <description>药物信息检索技能。当用户询问药品适应症、禁忌症、用法用量、不良反应、药物相互作用、特殊人群用药时使用。仅限医学知识库 knowledge/medical/drugs/ 目录下检索。</description>
  </skill>
  <skill name="medical-evidence-search" path="skills/medical/evidence_search/SKILL.md">
    <description>循证医学文献检索技能。当用户询问"有什么证据支持"、"循证医学证据"、"系统综述"、"RCT"、"Meta分析"时使用。基于PICO框架和Cochrane高度敏感检索策略。仅限医学知识库 knowledge/medical/literature/ 目录下检索。</description>
  </skill>
  <skill name="medical-diagnosis-search" path="skills/medical/diagnosis_search/SKILL.md">
    <description>疾病诊断标准检索技能。当用户询问诊断标准、分型分期、检查方法、鉴别诊断、正常值范围时使用。仅限医学知识库 knowledge/medical/diseases/ 和 knowledge/medical/guidelines/ 目录下检索。</description>
  </skill>
  <skill name="失败恢复经验沉淀" path="skills/retry-lesson-capture/SKILL.md">
    <description>当一个任务首次执行失败，但在重试其他工具、接口、参数或流程后成功时，使用此技能总结可复用经验，并将经验同时写入当前正在使用的 SKILL.md 与 memory/MEMORY.md。适用于 API 失败后切换备用 API、命令失败后改用其他命令、抓取失败后改用其他数据源、解析失败后改用其他流程等场景。</description>
  </skill>
  <skill name="联网搜索" path="skills/web-search/SKILL.md">
    <description>使用 Tavily 联网搜索最新信息、官方文档、新闻动态、实时行情和外部事实来源。适用于用户明确要求搜索、联网、查官网、给链接、核验事实，或任务明显依赖实时外部信息的场景。优先调用本技能目录下的 Tavily 脚本，不要退回抓搜索结果页。</description>
  </skill>
</skills>

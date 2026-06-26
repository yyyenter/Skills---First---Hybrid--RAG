#!/usr/bin/env python3
"""
Legal RAG Evaluation (50 questions): Baseline vs Skill-First + Fallback + RRF

Metrics:
  - Baseline Recall@5: pure hybrid retrieval
  - Skill Hit Rate: Skill status=success AND recall=true (no fallback needed)
  - Fallback Success Rate: Skill failed but fallback+RRF recovered
  - Final Recall@5: Skill-First + Fallback combined
  - Improvement: Final - Baseline (percentage points)

Rate-limiting: sleeps 15s between questions (~4 RPM for GLM-4.7-Flash)
Estimated runtime: 50q x ~60s = ~50 minutes (with retries)
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from config import get_settings
from graph.agent import agent_manager
from knowledge_retrieval.hybrid_retriever import hybrid_retriever
from knowledge_retrieval.indexer import knowledge_indexer
from knowledge_retrieval.orchestrator import knowledge_orchestrator

# ---------------------------------------------------------------------------
# 50 Legal questions: 30 single-hop + 20 multi-hop
# Multi-hop types: Bridge Entity / Comparison / Temporal Chain
# ---------------------------------------------------------------------------
EVAL_QUESTIONS: list[dict[str, Any]] = [
    # ========== SINGLE-HOP (30) ==========

    # --- Statute Search (10) ---
    {"id": 1,  "question": "合同编中，当事人应当按照什么原则履行合同义务？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/contract_law_articles.md"],
     "key_answer": "当事人应当按照约定全面履行自己的义务，并遵循诚信原则，根据合同的性质、目的和交易习惯履行通知、协助、保密等义务。"},
    {"id": 2,  "question": "什么情况下当事人可以法定解除合同？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/contract_law_articles.md"],
     "key_answer": "（一）因不可抗力致使不能实现合同目的；（二）在履行期限届满前明确表示或以行为表明不履行主要债务；（三）迟延履行主要债务，经催告后在合理期限内仍未履行；（四）迟延履行债务或有其他违约行为致使不能实现合同目的。"},
    {"id": 3,  "question": "民法典对合同订立的形式有哪些规定？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "当事人订立合同可以采用书面形式、口头形式或者其他形式。书面形式包括合同书、信件、电报、电传、传真等可以有形地表现所载内容的形式；以电子数据交换、电子邮件等方式能够有形地表现所载内容并可以随时调取查用的数据电文，视为书面形式。"},
    {"id": 4,  "question": "依法成立的合同对谁具有法律约束力？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "依法成立的合同，仅对当事人具有法律约束力，但是法律另有规定的除外。"},
    {"id": 5,  "question": "民法典总则中，限制民事行为能力人是指几岁以上的未成年人？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_总则.md"],
     "key_answer": "八周岁以上的未成年人为限制民事行为能力人，实施民事法律行为由其法定代理人代理或者经其法定代理人同意、追认。"},
    {"id": 6,  "question": "民法典物权编中，不动产物权的设立以什么为生效要件？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_物权编.md"],
     "key_answer": "不动产物权的设立、变更、转让和消灭，经依法登记，发生效力；未经登记，不发生效力，但是法律另有规定的除外。"},
    {"id": 7,  "question": "民法典侵权责任编中，产品责任由谁承担？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_侵权责任编.md"],
     "key_answer": "因产品存在缺陷造成他人损害的，生产者应当承担侵权责任。因产品存在缺陷造成他人损害的，被侵权人可以向产品的生产者请求赔偿，也可以向产品的销售者请求赔偿。"},
    {"id": 8,  "question": "民法典总则中，民事法律行为有效的条件有哪些？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_总则.md"],
     "key_answer": "具备下列条件的民事法律行为有效：（一）行为人具有相应的民事行为能力；（二）意思表示真实；（三）不违反法律、行政法规的强制性规定，不违背公序良俗。"},
    {"id": 9,  "question": "民法典侵权责任编中，饲养动物造成他人损害由谁承担责任？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_侵权责任编.md"],
     "key_answer": "饲养的动物造成他人损害的，动物饲养人或者管理人应当承担侵权责任；但是，能够证明损害是因被侵权人故意或者重大过失造成的，可以不承担或者减轻责任。"},
    {"id": 10, "question": "民法典物权编中，业主对建筑物专有部分享有什么权利？",
     "expected_skill": "statute_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_物权编.md"],
     "key_answer": "业主对建筑物内的住宅、经营性用房等专有部分享有所有权，对专有部分以外的共有部分享有共有和共同管理的权利。"},

    # --- Case Search (5) ---
    {"id": 11, "question": "指导案例1号中，法院认为什么情况下买方不构成跳单违约？",
     "expected_skill": "case_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
     "key_answer": "当卖方将同一房屋通过多个中介公司挂牌出售时，买方通过其他公众可以获知的正当途径获得相同房源信息的，买方有权选择报价低、服务好的中介公司促成房屋买卖合同成立，其行为并没有利用先前与之签约中介公司的房源信息，故不构成违约。"},
    {"id": 12, "question": "上海中原物业顾问有限公司诉陶德华案的裁判结果是什么？",
     "expected_skill": "case_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
     "key_answer": "一审上海市虹口区人民法院驳回原告诉讼请求；二审上海市第二中级人民法院于2009年9月4日作出（2009）沪二中民二（民）终字第1508号民事判决，驳回上诉，维持原判。"},
    {"id": 13, "question": "居间合同中的禁止跳单条款效力如何认定？",
     "expected_skill": "case_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
     "key_answer": "确认书系中介公司提供的格式合同，其中关于禁止买方利用中介公司提供的房源信息却绕开该中介公司与卖方签订房屋买卖合同的约定合法有效。"},
    {"id": 14, "question": "陶德华案的一审法院是哪个？",
     "expected_skill": "case_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
     "key_answer": "上海市虹口区人民法院。"},
    {"id": 15, "question": "陶德华案中的关键争议焦点是什么？",
     "expected_skill": "case_search", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/cases/contract_termination_case.md"],
     "key_answer": "陶德华是否利用中原公司提供的房源信息却绕开中原公司私下与出卖人签订买卖合同，构成跳单违约。"},

    # --- Contract Clause - CUAD 0000 (5) ---
    {"id": 16, "question": "LIMEENERGYCO分销商协议的期限是多长？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
     "key_answer": "协议期限为十年（10 years），自公司向分销商交付最后一个样品之日起算。如果分销商遵守所有条款，协议可按年度续期，每次续期一年，最多再续十年。"},
    {"id": 17, "question": "分销商在哪个区域有独家分销权？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
     "key_answer": "伊利诺伊州（the State of Illinois），包括该州内的公共和私人实体、机构、公司、公立学校、公园区、惩教设施、机场、政府住房管理局和其他政府机构及设施。"},
    {"id": 18, "question": "分销商是否有权将名称使用权再许可给第三方？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
     "key_answer": "无权。分销商无权将名称（Names）再许可给任何第三方，也无权在公司事先书面批准的情况下以任何其他名称开展业务。"},
    {"id": 19, "question": "分销商协议的续期条件是什么？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
     "key_answer": "如果分销商遵守本协议的所有条款，协议可按年度续期，每次续期一年，最多再续十年。所有续期均按本协议规定的相同条款和条件进行。"},
    {"id": 20, "question": "分销商协议中，公司授予分销商使用什么名称的权利？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md"],
     "key_answer": "公司授予分销商使用名称'Electric City of Illinois'或类似变体（collectively the Names）的权利，用于本协议项下的业务。协议终止后，分销商不再享有该名称的任何权利。"},

    # --- Contract Clause - CUAD 0001 WHITESMOKE (5) ---
    {"id": 21, "question": "WHITESMOKE推广分销协议的生效日期是什么时候？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"],
     "key_answer": "2011年8月1日（the Effective Date）。"},
    {"id": 22, "question": "WHITESMOKE协议中，Distributor App指的是什么软件？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"],
     "key_answer": "WhiteSmoke Writer的试用版（the trial version of the WhiteSmoke Writer, currently called WhiteSmoke 2011），在全球范围内可用。明确不包括WhiteSmoke Writer的完整付费版本或任何版本的WhiteSmoke Translator软件。"},
    {"id": 23, "question": "WHITESMOKE协议中，Bundle的定义是什么？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"],
     "key_answer": "Bundle是指Distribution Products与Distributor App(s)捆绑在一起的产品组合。"},
    {"id": 24, "question": "WHITESMOKE协议的签约双方是谁？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"],
     "key_answer": "Whitesmoke Inc.（分销商，注册地址：501 Silverside Road, Suite 105, Wilmington DE 19809, USA）和Google Inc.（主要营业地：1600 Amphitheatre Parkway, Mountain View, CA 94043, USA）。"},
    {"id": 25, "question": "WHITESMOKE协议中，Chrome Browser Criteria Checker的作用是什么？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"],
     "key_answer": "Chrome Browser Criteria Checker是一套软件例程，用于检查某些标准（由Google确定并可不时修改），以确定Chrome Browser是否可以在终端用户的操作系统上安装。"},

    # --- Contract Clause - CUAD 0002 LOHA (3) ---
    {"id": 26, "question": "LOHA供应合同中，买方委托的采购代理是谁？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md"],
     "key_answer": "买方委托SHENZHEN YICHANGTAI IMPORT AND EXPORT TRADE CO., LTD或SHENZHEN LEHEYUAN TRADING CO, LTD（统称'受托方'或'YICHANGTAI'或'LEHEYUAN'）以订单形式从卖方采购本协议规定的产品。"},
    {"id": 27, "question": "LOHA供应合同中，卖方应在几个工作日内确认订单？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md"],
     "key_answer": "卖方应在收到订单后三个工作日内予以确认。如果卖方发现订单不可接受或需要修改，应在收到订单后两个工作日内通知受托方。"},
    {"id": 28, "question": "LOHA供应合同中，保险由谁负责投保？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md"],
     "key_answer": "由卖方按发票金额的110%投保一切险和战争险（All Risks and War Risk）。"},

    # --- Contract Clause - CUAD 0003 Centrack (3) ---
    {"id": 29, "question": "Centrack网站托管协议中，i-on提供哪些基本服务？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md"],
     "key_answer": "（1）通过T1线路连接到互联网的连通性；（2）托管计算机的使用及维护；（3）托管计算机所在物理空间及环境控制；（4）托管计算机的应急电力备份系统；（5）最多150 MB的镜像计算机存储空间。"},
    {"id": 30, "question": "Centrack协议中，托管计算机的存储空间上限是多少？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md"],
     "key_answer": "最多150 MB的镜像计算机存储空间（up to 150 MB of mirrored computer storage on the Hosting Computer）。"},
    {"id": 31, "question": "Centrack协议中，i-on应在什么时间进行维护？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md"],
     "key_answer": "i-on将尽最大努力在工作日晚上8点至早上8点（Eastern Standard Time）或周末安排和执行维护。"},

    # --- Contract Clause - CUAD 0004 NELNET (3) ---
    {"id": 32, "question": "NELNET联合申报协议的签署日期是什么时候？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0004_NELNETINC_04_08_2020-EX-1-JOINT_FILING_AGREEMENT.md"],
     "key_answer": "2020年3月27日（Dated: March 27, 2020）。"},
    {"id": 33, "question": "NELNET协议依据什么法律规则提交？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0004_NELNETINC_04_08_2020-EX-1-JOINT_FILING_AGREEMENT.md"],
     "key_answer": "依据1934年《证券交易法》下的Rule 13d-1(k)提交Schedule 13G或Schedule 13D。"},
    {"id": 34, "question": "NELNET协议中，各方对什么信息负责？",
     "expected_skill": "contract_clause", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/contracts/cuad_0004_NELNETINC_04_08_2020-EX-1-JOINT_FILING_AGREEMENT.md"],
     "key_answer": "各方对其自身信息的完整性和准确性负责，但不对其他方的信息负责，除非其知道或有理由相信该信息不准确。"},

    # --- Legal Definition (6) ---
    {"id": 35, "question": "民法典中，什么是合同？",
     "expected_skill": "legal_definition", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "合同是民事主体之间设立、变更、终止民事法律关系的协议。婚姻、收养、监护等有关身份关系的协议，适用有关该身份关系的法律规定；没有规定的，可以根据其性质参照适用本编规定。"},
    {"id": 36, "question": "当事人对合同条款理解有争议时，应如何确定条款含义？",
     "expected_skill": "legal_definition", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "应当依据本法第一百四十二条第一款的规定，确定争议条款的含义。合同文本采用两种以上文字订立并约定具有同等效力的，对各文本使用的词句推定具有相同含义。各文本使用的词句不一致的，应当根据合同的相关条款、性质、目的以及诚信原则等予以解释。"},
    {"id": 37, "question": "非因合同产生的债权债务关系适用什么规定？",
     "expected_skill": "legal_definition", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "非因合同产生的债权债务关系，适用有关该债权债务关系的法律规定；没有规定的，适用本编通则的有关规定，但是根据其性质不能适用的除外。"},
    {"id": 38, "question": "书面形式包括哪些具体类型？",
     "expected_skill": "legal_definition", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "书面形式是合同书、信件、电报、电传、传真等可以有形地表现所载内容的形式。以电子数据交换、电子邮件等方式能够有形地表现所载内容，并可以随时调取查用的数据电文，视为书面形式。"},
    {"id": 39, "question": "民法典合同编通则适用于什么情况？",
     "expected_skill": "legal_definition", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_合同编.md"],
     "key_answer": "本法或者其他法律没有明文规定的合同，适用本编通则的规定，并可以参照适用本编或者其他法律最相类似合同的规定。"},
    {"id": 40, "question": "民法典总则中，自然人的民事权利能力从什么时候开始？",
     "expected_skill": "legal_definition", "multi_hop": False,
     "ground_truth_paths": ["knowledge/legal/statutes/民法典_总则.md"],
     "key_answer": "自然人从出生时起到死亡时止，具有民事权利能力，依法享有民事权利，承担民事义务。"},

    # ========== MULTI-HOP (20) ==========

    # --- Bridge Entity Hop: Case → Statute (4) ---
    {"id": 41, "question": "陶德华案中提到的居间合同，在民法典中是怎么定义的？",
     "expected_skill": "case_search", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/cases/contract_termination_case.md",
         "knowledge/legal/statutes/民法典_合同编.md"
     ],
     "key_answer": "【跳1-案例】陶德华案中，中原公司与陶德华签订的是《房地产求购确认书》，属于居间合同，约定禁止跳单条款。【跳2-法条】民法典中，居间合同（现称'中介合同'）是中介人向委托人报告订立合同的机会或者提供订立合同的媒介服务，委托人支付报酬的合同。"},
    {"id": 42, "question": "指导案例1号中法院引用的民法典条文，关于违约责任的原文是什么？",
     "expected_skill": "case_search", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/cases/contract_termination_case.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-案例】陶德华案中，法院引用了《合同法》第四百二十四条、第四百二十六条（现《民法典》第九百六十一条、第九百六十三条）。【跳2-法条】民法典第九百六十一条：中介合同是中介人向委托人报告订立合同的机会或者提供订立合同的媒介服务，委托人支付报酬的合同。第九百六十三条：中介人促成合同成立的，委托人应当按照约定支付报酬。"},
    {"id": 43, "question": "陶德华案中的跳单行为，在民法典合同编中对应什么规定？",
     "expected_skill": "case_search", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/cases/contract_termination_case.md",
         "knowledge/legal/statutes/民法典_合同编.md"
     ],
     "key_answer": "【跳1-案例】陶德华案中的'跳单'是指买方利用中介公司提供的房源信息却绕开该中介公司与卖方签订房屋买卖合同。【跳2-法条】民法典第九百六十五条规定：委托人在接受中介人的服务后，利用中介人提供的交易机会或者媒介服务，绕开中介人直接订立合同的，应当向中介人支付报酬。"},
    {"id": 44, "question": "陶德华案中，法院认定不构成跳单的理由与民法典合同编的哪条诚信原则相呼应？",
     "expected_skill": "case_search", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/cases/contract_termination_case.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-案例】法院认为陶德华通过其他公众可以获知的正当途径获得相同房源信息，有权选择报价低、服务好的中介，不属于利用中原公司信息跳单。【跳2-法条】民法典第七条规定：民事主体从事民事活动，应当遵循诚信原则，秉持诚实，恪守承诺。第五百零九条规定：当事人应当遵循诚信原则，根据合同的性质、目的和交易习惯履行通知、协助、保密等义务。"},

    # --- Bridge Entity Hop: Contract → Statute (4) ---
    {"id": 45, "question": "LOHA供应合同中的不可抗力条款，在民法典合同编中如何规定？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-合同】LOHA供应合同涉及国际贸易，其中的不可抗力条款关系到合同履行障碍。【跳2-法条】民法典第五百六十三条第一款规定：因不可抗力致使不能实现合同目的，当事人可以解除合同。第五百九十条规定：当事人一方因不可抗力不能履行合同的，根据不可抗力的影响，部分或者全部免除责任，但是法律另有规定的除外。"},
    {"id": 46, "question": "WHITESMOKE协议中的Distributor App涉及民法典中的什么合同类型？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md",
         "knowledge/legal/statutes/民法典_合同编.md"
     ],
     "key_answer": "【跳1-合同】WHITESMOKE协议中的Distributor App是WhiteSmoke Writer试用版，属于软件分发。【跳2-法条】民法典合同编中的技术合同包括技术开发、技术转让、技术许可、技术咨询和技术服务合同。Distributor App的分发可涉及技术许可合同或买卖合同。"},
    {"id": 47, "question": "LIMEENERGYCO分销商协议中的独家分销权，对应民法典中的什么概念？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md",
         "knowledge/legal/statutes/民法典_合同编.md"
     ],
     "key_answer": "【跳1-合同】LIMEENERGYCO协议中，公司授予分销商在伊利诺伊州的独家分销权（exclusive distributor），有权销售Energy Saver等产品。【跳2-法条】民法典合同编中的委托合同（第九百一十九条）和中介合同（第九百六十一条）与独家分销权最为接近。独家分销协议本质上是一种特殊的委托销售合同。"},
    {"id": 48, "question": "Centrack网站托管协议中的服务维护义务，在民法典合同编中对应什么类型的合同义务？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-合同】Centrack协议中，i-on承诺7x24小时维护Hosted Site的运行，提供T1互联网连接、托管计算机、物理空间、备用电源和存储空间。【跳2-法条】民法典第五百零九条规定：当事人应当按照约定全面履行自己的义务。i-on的维护义务属于技术服务合同中的主给付义务，违反该义务构成违约，应承担违约责任。"},

    # --- Comparison Hop: Contract vs Contract (4) ---
    {"id": 49, "question": "LIMEENERGYCO和WHITESMOKE的分销协议分别由哪些公司签署？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md",
         "knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"
     ],
     "key_answer": "【跳1-LIMEENERGYCO】由Electric City Corp.（公司）和Electric City of Illinois LLC（分销商）签署。【跳2-WHITESMOKE】由Whitesmoke Inc.（分销商）和Google Inc.签署。【对比】前者是母子公司关系，后者是独立公司之间的合作关系。"},
    {"id": 50, "question": "比较LIMEENERGYCO和WHITESMOKE协议中分销商的分销产品范围有什么不同？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md",
         "knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md"
     ],
     "key_answer": "【跳1-LIMEENERGYCO】分销产品是Energy Saver（节能设备），可在伊利诺伊州内销售给公共和私人实体、学校、机场、政府住房管理局等。【跳2-WHITESMOKE】分销产品是Chrome Browser、Google Toolbar和WhiteSmoke Writer试用版，通过Distributor App向终端用户分发。【对比】前者是实体硬件产品，后者是软件/互联网产品。"},
    {"id": 51, "question": "LOHA供应合同和Centrack托管合同在服务提供方的责任范围上有什么不同？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md",
         "knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md"
     ],
     "key_answer": "【跳1-LOHA】卖方责任包括：按订单供货、负责包装、投保一切险和战争险、承担质量保证责任、在72小时内发出装船通知。【跳2-Centrack】i-on责任包括：7x24小时维护网站运行、提供互联网连接、托管计算机维护、物理空间环境控制、备用电源。【对比】LOHA卖方责任侧重实物交付和质量保证；Centrack i-on责任侧重技术维护和服务连续性。"},
    {"id": 52, "question": "比较民法典总则中的民事法律行为效力和合同编中的合同效力条件有什么联系？",
     "expected_skill": "statute_search", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/statutes/民法典_总则.md",
         "knowledge/legal/statutes/民法典_合同编.md"
     ],
     "key_answer": "【跳1-总则】民事法律行为有效的条件：行为人具有相应民事行为能力、意思表示真实、不违反法律和公序良俗。【跳2-合同编】合同成立的基本条件与总则一致，但合同编进一步规定了合同订立的形式要求（书面/口头/其他）、要约与承诺规则、格式条款解释规则等。【联系】合同是民事法律行为的一种特殊类型，合同效力判断首先要满足总则中民事法律行为有效的一般条件，再适用合同编的特殊规定。"},

    # --- Comparison Hop: Statute vs Statute (2) ---
    {"id": 53, "question": "民法典合同编中的违约责任与侵权责任编中的产品责任在归责原则上有何不同？",
     "expected_skill": "statute_search", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/statutes/contract_law_articles.md",
         "knowledge/legal/statutes/民法典_侵权责任编.md"
     ],
     "key_answer": "【跳1-合同编】违约责任一般适用严格责任原则（无过错责任），即当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任，不以过错为要件。【跳2-侵权责任编】产品责任也适用无过错责任（严格责任），但机动车交通事故责任适用过错责任原则。【对比】合同违约责任和侵权责任中的产品责任都趋向严格责任，但违约责任基于合同关系，侵权责任基于法定义务，两者在举证责任、赔偿范围和免责事由上存在差异。"},
    {"id": 54, "question": "民法典总则中的宣告失踪制度与合同编中的法定解除制度有什么联系？",
     "expected_skill": "statute_search", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/statutes/民法典_总则.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-总则】自然人下落不明满二年的，利害关系人可以向人民法院申请宣告该自然人为失踪人。失踪人的财产由其配偶、成年子女、父母或者其他愿意担任财产代管人的人代管。【跳2-合同编】法定解除的情形包括因不可抗力致使不能实现合同目的、预期违约、迟延履行等。【联系】当合同一方当事人被宣告失踪时，其财产代管人可能需要决定是否继续履行合同；如果失踪导致合同目的无法实现（如具有人身专属性的合同），可能触发法定解除。"},

    # --- Temporal Chain Hop (2) ---
    {"id": 55, "question": "从合同订立到因不可抗力法定解除，民法典合同编规定了哪些必经阶段和法律后果？",
     "expected_skill": "statute_search", "multi_hop": True, "hop_type": "Temporal Chain",
     "ground_truth_paths": [
         "knowledge/legal/statutes/民法典_合同编.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-订立阶段】当事人采用要约、承诺方式或其他方式订立合同，合同自成立时生效（第469条、第502条）。【跳2-履行阶段】当事人应当按照约定全面履行义务，遵循诚信原则（第509条）。【跳3-解除阶段】因不可抗力致使不能实现合同目的，当事人可以解除合同（第563条）。【跳4-法律后果】合同解除后，尚未履行的终止履行；已经履行的，根据履行情况和合同性质，当事人可以请求恢复原状或采取其他补救措施，并有权请求赔偿损失（第566条）。"},
    {"id": 56, "question": "从陶德华验看房源到最终二审判决维持原判，经历了哪些关键时间节点和程序？",
     "expected_skill": "case_search", "multi_hop": True, "hop_type": "Temporal Chain",
     "ground_truth_paths": [
         "knowledge/legal/cases/contract_termination_case.md"
     ],
     "key_answer": "【跳1-2008年】陶德华通过中原公司获得房源信息，双方签订《房地产求购确认书》，约定禁止跳单条款（验看后6个月内不得绕开中介成交）。【跳2-验看后】陶德华发现该房屋在多个中介同时挂牌，通过另一中介汉宇公司以更低佣金和更低价格成交。【跳3-一审】上海市虹口区人民法院审理，判决驳回中原公司的诉讼请求（认定不构成跳单）。【跳4-2009年9月4日】上海市第二中级人民法院作出（2009）沪二中民二（民）终字第1508号民事判决，驳回上诉，维持原判。"},

    # --- Bridge Entity: Contract → Case (2) ---
    {"id": 57, "question": "LIMEENERGYCO分销商协议中的续约条款，如果发生争议，类似纠纷在中国法律下会如何处理？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md",
         "knowledge/legal/cases/contract_termination_case.md"
     ],
     "key_answer": "【跳1-合同】LIMEENERGYCO协议约定：遵守所有条款即可按年度续期，每次一年，最多再续十年；所有续期均按相同条款进行。【跳2-判例参考】陶德华案确立了格式合同条款的解释原则：当卖方通过多个渠道提供相同信息时，买方有权选择更优服务。若续约条款属于格式条款且存在争议，法院将依据民法典第四百九十六条（格式条款提示说明义务）和第一百四十二条（合同解释规则）进行解释，倾向于保护弱势方的合理预期。"},
    {"id": 58, "question": "Centrack协议中i-on承诺的7x24小时服务，如果服务中断造成损失，在中国法律框架下如何认定责任？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Bridge Entity",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md",
         "knowledge/legal/statutes/contract_law_articles.md"
     ],
     "key_answer": "【跳1-合同】Centrack协议约定i-on将7x24小时维护Hosted Site运行，仅在晚上8点至早上8点或周末进行合理维护。【跳2-法条】民法典第五百七十七条规定：当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。若i-on非因合理维护中断服务，构成违约，应承担赔偿责任；赔偿范围包括直接损失和合同履行后可以获得的利益，但不得超过违约一方订立合同时预见到或应当预见到的因违约可能造成的损失（第584条）。"},

    # --- Comparison: Multiple Contracts (2) ---
    {"id": 59, "question": "比较LOHA供应合同、Centrack托管合同和NELNET联合申报协议在签约主体数量上有什么不同？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md",
         "knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md",
         "knowledge/legal/contracts/cuad_0004_NELNETINC_04_08_2020-EX-1-JOINT_FILING_AGREEMENT.md"
     ],
     "key_answer": "【跳1-LOHA】两方主体：买方（Shenzhen LOHAS Supply Chain Management Co., Ltd.）和卖方（未具名），买方委托YICHANGTAI或LEHEYUAN作为采购代理。【跳2-Centrack】两方主体：Centrack International（客户）和i-on interactive（托管方）。【跳3-NELNET】多方主体：Shelby J. Butterfield和Butterfield Family Trust（由Shelby J. Butterfield作为共同受托人签署）。【对比】LOHA和Centrack是典型的两方合同；NELNET是多方联合申报协议，涉及信托结构和共同责任。"},
    {"id": 60, "question": "比较五个CUAD合同（LIMEENERGYCO、WHITESMOKE、LOHA、Centrack、NELNET）在合同期限方面的规定有什么不同？",
     "expected_skill": "contract_clause", "multi_hop": True, "hop_type": "Comparison",
     "ground_truth_paths": [
         "knowledge/legal/contracts/cuad_0000_LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR_AGREEMENT.md",
         "knowledge/legal/contracts/cuad_0001_WHITESMOKE_INC_11_08_2011-EX-10_26-PROMOTION_AND_DISTRIBUTIO.md",
         "knowledge/legal/contracts/cuad_0002_LohaCompanyltd_20191209_F-1_EX-10_16_11917878_EX-10_16_Suppl.md",
         "knowledge/legal/contracts/cuad_0003_CENTRACKINTERNATIONALINC_10_29_1999-EX-10_3-WEB_SITE_HOSTING.md",
         "knowledge/legal/contracts/cuad_0004_NELNETINC_04_08_2020-EX-1-JOINT_FILING_AGREEMENT.md"
     ],
     "key_answer": "【跳1-LIMEENERGYCO】明确期限：10年，可续期最多再10年（按年度续期）。【跳2-WHITESMOKE】未明确总期限，协议生效日为2011年8月1日，属于持续性推广分销协议。【跳3-LOHA】框架性供应协议，以订单为执行单位，无固定总期限，以具体订单的有效期为准。【跳4-Centrack】未明确固定期限，属于持续性网站托管服务协议，按服务提供持续有效。【跳5-NELNET】联合申报协议，签署日期为2020年3月27日，用于联合提交Schedule 13G/13D，随申报义务持续有效。【对比】只有LIMEENERGYCO明确规定了固定期限和续期机制；其余四个合同或属于框架/持续性协议，或未明确期限，体现了不同商业场景下的合同期限设计差异。"},
]


# ---------------------------------------------------------------------------
# Baseline retrieval
# ---------------------------------------------------------------------------
def baseline_retrieve(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    result = hybrid_retriever.retrieve(query, top_k=top_k, path_filters=["knowledge/legal/"])
    evidences = []
    for ev in result.vector_evidences + result.bm25_evidences:
        evidences.append({"source_path": ev.source_path, "snippet": ev.snippet[:200], "score": ev.score, "channel": ev.channel})
    seen = set()
    deduped = []
    for ev in evidences:
        if ev["source_path"] not in seen:
            seen.add(ev["source_path"])
            deduped.append(ev)
    return deduped[:top_k]


# ---------------------------------------------------------------------------
# Skill-First + Fallback + RRF via orchestrator
# ---------------------------------------------------------------------------
async def skill_first_retrieve(query: str, max_retries: int = 2) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        orchestrated = None
        try:
            async for event in knowledge_orchestrator.astream(query):
                if event.get("type") == "orchestrated_result":
                    orchestrated = event["result"]
        except Exception as exc:
            msg = str(exc)
            if "1113" in msg or "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
                if attempt < max_retries:
                    wait = 20 + attempt * 10
                    print(f"    [RateLimit] retry {attempt + 1}/{max_retries + 1}, sleep {wait}s...")
                    time.sleep(wait)
                    continue
            return {"error": msg, "evidences": [], "status": "error", "fallback_used": False}

        if orchestrated is None:
            return {"error": "No result", "evidences": [], "status": "no_result", "fallback_used": False}
        break

    evidences = []
    for ev in orchestrated.evidences[:5]:
        evidences.append({"source_path": ev.source_path, "snippet": ev.snippet[:200], "score": ev.score, "channel": ev.channel})
    return {
        "status": orchestrated.status,
        "evidences": evidences,
        "fallback_used": orchestrated.fallback_used,
        "reason": orchestrated.reason,
    }


def check_recall(retrieved_paths: list[str], ground_truth_paths: list[str]) -> bool:
    normalized_gt = {p.replace("\\", "/") for p in ground_truth_paths}
    normalized_ret = {p.replace("\\", "/") for p in retrieved_paths}
    return bool(normalized_gt & normalized_ret)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    settings = get_settings()
    print(f"[Config] LLM: {settings.llm_provider}/{settings.llm_model}")
    print(f"[Config] Embedding: {settings.embedding_provider}/{settings.embedding_model}")

    agent_manager.initialize(settings.backend_dir)
    knowledge_indexer.configure(settings.backend_dir)
    knowledge_indexer._load_manifest()
    knowledge_indexer._load_vector_index()
    knowledge_orchestrator.configure(settings.backend_dir, agent_manager._build_chat_model)

    print(f"[Index] {len(knowledge_indexer._documents)} docs, vector={knowledge_indexer._vector_ready}, bm25={knowledge_indexer._bm25_ready}")
    print(f"[Eval ] {len(EVAL_QUESTIONS)} questions, sleep=15s between queries")
    print(f"[Note ] Estimated runtime: ~{len(EVAL_QUESTIONS)} min (with rate-limit retries)")
    print("=" * 80)

    results = []
    for i, q in enumerate(EVAL_QUESTIONS, 1):
        qid = q["id"]
        question = q["question"]
        print(f"\n[{i:2d}/{len(EVAL_QUESTIONS)}] Q{qid}: {question}")

        # Baseline
        base_evs = baseline_retrieve(question, top_k=5)
        base_paths = [e["source_path"] for e in base_evs]
        base_recall = check_recall(base_paths, q["ground_truth_paths"])
        print(f"  [Baseline] recall={base_recall}, paths={len(base_paths)}")

        # Skill-First + Fallback + RRF
        skill = await skill_first_retrieve(question)
        if "error" in skill:
            print(f"  [Skill+RRF] ERROR: {skill['error']}")
            skill_recall = False
            skill_hit = False
            fallback_recovered = False
            skill_status = "error"
        else:
            skill_paths = [e["source_path"] for e in skill["evidences"]]
            skill_recall = check_recall(skill_paths, q["ground_truth_paths"])
            skill_hit = (skill["status"] == "success" and skill_recall)
            fallback_recovered = (skill["fallback_used"] and skill_recall)
            skill_status = skill["status"]
            fb_tag = "(fallback+RRF)" if skill["fallback_used"] else "(skill-only)"
            print(f"  [Skill+RRF] status={skill_status} {fb_tag}, recall={skill_recall}")

        results.append({
            "id": qid,
            "question": question,
            "expected_skill": q["expected_skill"],
            "multi_hop": q.get("multi_hop", False),
            "hop_type": q.get("hop_type", "single"),
            "baseline_recall": base_recall,
            "skill_status": skill_status,
            "skill_hit": skill_hit,
            "skill_recall": skill_recall,
            "fallback_recovered": fallback_recovered,
            "fallback_used": skill.get("fallback_used", False) if "error" not in skill else False,
            "baseline_paths": base_paths,
            "skill_paths": [e["source_path"] for e in skill.get("evidences", [])] if "error" not in skill else [],
        })

        if i < len(EVAL_QUESTIONS):
            print("  [Sleep] 15s...")
            time.sleep(15)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("EVALUATION SUMMARY")
    print("=" * 80)

    total = len(results)

    baseline_recalls = sum(1 for r in results if r["baseline_recall"])
    skill_hits = sum(1 for r in results if r["skill_hit"])
    skill_attempts = sum(1 for r in results if r["skill_status"] not in {"error", "no_result"})
    skill_failures = sum(1 for r in results if not r["skill_hit"] and r["skill_status"] not in {"error", "no_result"})
    fallback_recoveries = sum(1 for r in results if r["fallback_recovered"])
    final_recalls = sum(1 for r in results if r["skill_recall"])

    print(f"\nTotal Questions:        {total}")
    print(f"\n[Retrieval Recall@5]")
    print(f"  Baseline (pure hybrid): {baseline_recalls}/{total} = {baseline_recalls/total*100:.1f}%")
    print(f"  Final (Skill+Fallback): {final_recalls}/{total} = {final_recalls/total*100:.1f}%")
    print(f"  Improvement:            +{(final_recalls - baseline_recalls)/total*100:.1f}pp")

    print(f"\n[Skill Performance]")
    print(f"  Skill Hit Rate:        {skill_hits}/{skill_attempts} = {skill_hits/max(1,skill_attempts)*100:.1f}%")
    print(f"  Skill Failures:        {skill_failures}")

    print(f"\n[Fallback Performance]")
    print(f"  Fallback Used:         {sum(1 for r in results if r['fallback_used'])}")
    print(f"  Fallback Recovered:    {fallback_recoveries}/{max(1, skill_failures)} = {fallback_recoveries/max(1,skill_failures)*100:.1f}%")

    print(f"\n[Per-Skill Breakdown]")
    for skill_name in ["statute_search", "case_search", "contract_clause", "legal_definition"]:
        skill_qs = [r for r in results if r["expected_skill"] == skill_name]
        if not skill_qs:
            continue
        b_rec = sum(1 for r in skill_qs if r["baseline_recall"])
        s_hit = sum(1 for r in skill_qs if r["skill_hit"])
        f_rec = sum(1 for r in skill_qs if r["fallback_recovered"])
        fn_rec = sum(1 for r in skill_qs if r["skill_recall"])
        print(f"  {skill_name:20s}: Baseline={b_rec}/{len(skill_qs)}  SkillHit={s_hit}/{len(skill_qs)}  FallbackRec={f_rec}  Final={fn_rec}/{len(skill_qs)}")

    # --- Single-hop vs Multi-hop breakdown ---
    print(f"\n[Single-Hop vs Multi-Hop]")
    single_qs = [r for r in results if not r["multi_hop"]]
    multi_qs  = [r for r in results if r["multi_hop"]]

    b_rec_s = sum(1 for r in single_qs if r["baseline_recall"])
    fn_rec_s = sum(1 for r in single_qs if r["skill_recall"])
    s_hit_s = sum(1 for r in single_qs if r["skill_hit"])
    fb_rec_s = sum(1 for r in single_qs if r["fallback_recovered"])
    print(f"  Single-Hop ({len(single_qs)}q): Baseline={b_rec_s}/{len(single_qs)}  SkillHit={s_hit_s}/{len(single_qs)}  FallbackRec={fb_rec_s}  Final={fn_rec_s}/{len(single_qs)}")

    b_rec_m = sum(1 for r in multi_qs if r["baseline_recall"])
    fn_rec_m = sum(1 for r in multi_qs if r["skill_recall"])
    s_hit_m = sum(1 for r in multi_qs if r["skill_hit"])
    fb_rec_m = sum(1 for r in multi_qs if r["fallback_recovered"])
    print(f"  Multi-Hop  ({len(multi_qs)}q):  Baseline={b_rec_m}/{len(multi_qs)}  SkillHit={s_hit_m}/{len(multi_qs)}  FallbackRec={fb_rec_m}  Final={fn_rec_m}/{len(multi_qs)}")

    # Per-hop-type breakdown
    hop_types = {}
    for r in multi_qs:
        ht = r.get("hop_type", "unknown")
        hop_types.setdefault(ht, []).append(r)
    if hop_types:
        print(f"\n[Multi-Hop Type Breakdown]")
        for ht, qs in hop_types.items():
            b_rec = sum(1 for r in qs if r["baseline_recall"])
            fn_rec = sum(1 for r in qs if r["skill_recall"])
            s_hit = sum(1 for r in qs if r["skill_hit"])
            fb_rec = sum(1 for r in qs if r["fallback_recovered"])
            print(f"  {ht:20s}: Baseline={b_rec}/{len(qs)}  SkillHit={s_hit}/{len(qs)}  FallbackRec={fb_rec}  Final={fn_rec}/{len(qs)}")

    # Save
    out_path = settings.backend_dir / "eval_legal_50_results.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Saved] {out_path}")

    # One-liner for resume
    print("\n" + "=" * 80)
    print("RESUME ONE-LINER:")
    print(f"  Skill-First Agentic RAG: Skill 直接命中 {skill_hits}/{total} ({skill_hits/total*100:.1f}%), "
          f"兜底机制挽回 {fallback_recoveries}/{max(1,skill_failures)} ({fallback_recoveries/max(1,skill_failures)*100:.1f}%) 失败案例，"
          f"最终召回率 {final_recalls}/{total} ({final_recalls/total*100:.1f}%)，"
          f"相比纯 RAG 基线 {baseline_recalls}/{total} ({baseline_recalls/total*100:.1f}%) 提升 {(final_recalls-baseline_recalls)/total*100:.1f} 个百分点。")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

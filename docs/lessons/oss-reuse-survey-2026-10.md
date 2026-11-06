# 开源可复用项目调研报告（七个功能模块）

**调研日期**：2026-10-06
**范围**：本仓库全部功能模块 —— `infra/`（ETL 与图谱）、`rca/`、`chaos/`、`dr-plan-generator/`、`graph_mcp/`、`compliance_export/`
**方法**：7 个方向并行检索 GitHub，**逐项实地核实最近提交日期**（commits/releases Atom feed、`gh api`、仓库页面）。
**判据**：超过 12 个月（即早于 2025-10）无提交或无发布 → 标注「疑似停更」。核不实的一律写「未能核实」，不以推测充当事实。

> ⚠️ **核实方法的局限（必须随结论一起读）**：GitHub REST API 对未认证请求限流 60/h，多数方向改用 Atom feed 或 `gh` CLI 取日期。
> 因此「**最近提交日期可信**」，但「**近 6 个月精确 commit 计数**」多数未能取得，活跃度以发布节奏与近期提交频率定性描述。

---

## 零、一句话结论

**七个模块里，六个的「底座」都有活跃的开源项目可直接用或二次开发；而贯穿全平台的「以依赖图驱动决策」这一层，开源生态完全空白。**

具体说，下面四项能力在全部 7 个方向的检索中**没有找到任何现成实现**：

| 我们的能力 | 开源现状 |
|---|---|
| 依赖图 → 自动生成混沌实验假设 | ❌ 无。仅 ChaosBlade Blade AI、AWS `ai-chaos` MCP server 可参考「AI 生成实验」的工程思路 |
| 依赖图 → 自动生成切换顺序（7 阶段） | ❌ 无。所有编排引擎只对**已声明的** DAG 排序，不会读依赖图反推阶段 |
| 依赖图作为 Graph-RAG 推理输入 | ❌ 无。RCA 类项目都是「证据收集 + LLM」，不含图推理 |
| 业务能力 → 控制项穿透映射（含证据分级） | ❌ 无。合规类项目全是「云资源配置姿态扫描」，回答的是另一个问题 |

**这决定了改造策略：换底座，不换内核。** 可以大幅削减自研 ETL、探针框架、编排脚手架的维护量，但图驱动决策这一层必须自研——它既是差异点，也无从复用。

---

## 一、按模块的结论与推荐

### 1.1 `infra/` 服务拓扑采集（eBPF）

**推荐：不换采集器，改用 DeepFlow 自带的拓扑 API 取代那 4 条自研 Lambda ETL。**

| 项目 | 最近提交 | 最新发布 | 维护方 | 部署 | 关键可复用点 |
|---|---|---|---|---|---|
| **DeepFlow**（现用） | 2026-09-21 | v7.2.2（~2026-09-10） | 云杉网络（公司） | Helm，特权 DaemonSet，需自建 ClickHouse+MySQL，**ARM64 ✓** | **Universal Map 直接给出带方向/协议/QPS 的调用边**，有 SQL/HTTP API |
| Cilium Hubble | 2026-10-05 | v1.21 预发布 | CNCF 毕业 | **需以 Cilium 作 CNI**（最大门槛），ARM64 ✓ | Relay gRPC flow API，可派生边（QPS 需自行聚合） |
| Kiali | 2026-10-05 | v2.33.1（2026-10-05） | Red Hat | **强依赖 Istio** | Graph API 直接返回含 QPS 的拓扑 JSON（最开箱即用） |
| Coroot | 2026-10-03 | 1.27.0（2026-09-29） | Coroot Inc. | Helm 可一并装 ClickHouse+Prom，ARM64 ✓ | eBPF Service Map 100% 覆盖；导出 API 文档化程度一般（**未充分核实**） |
| Odigos | 2026-10-05 | v1.39.0-pre1 | CNCF Sandbox | **无需自建存储**，ARM64 ✓，最易 | 无侵入生成分布式 trace，**可补 X-Ray 采样缺口**；但不直接产出边 |
| Grafana Beyla → OBI | 2026-10-05 | v3.38.0（2026-10-05） | **2025 年已捐赠 OpenTelemetry**，核心迁入 `opentelemetry-ebpf-instrumentation` | 单二进制，ARM64 ✓ | service graph 指标（可派生边与 QPS） |
| Pixie | 2026-09-24 | v0.14.16-pre（2026-07-13） | CNCF Sandbox | 需 Pixie Cloud 或自建（较重），**ARM64 支持未能核实** | PxL 查 service graph；数据保留短 |
| Kubeshark | 2026-09-30 | v53.4.0（2026-08-13） | 公司 | CLI/Helm | L7 全流量取证，长期聚合非其强项 |
| Netdata | 2026-10-06 | v2.12.0（2026-09-30） | 公司 | 极易 | ⚠️ 聚焦单节点指标，**不满足服务依赖边需求** |
| **Caretta** | **2025-03-17** | v0.0.17 | groundcover | Helm 轻量 | ⚠️ **疑似停更（约 19 个月）**。讽刺的是它的边模型（`caretta_links` 指标直出源/目的/方向）与我们需求最契合 |

**关键共性：没有一个自带图数据库。** 写入 Neptune 这一步无法外包,但可以从「4 条自研管道」收敛成「一次拓扑 API 查询」。

### 1.2 `infra/` 云资产图谱（CMDB）

**推荐：Cartography 作为二次开发基座。**

| 项目 | 最近提交 | 最新发布 | 能否写 Neptune | 评价 |
|---|---|---|---|---|
| **Cartography**（原 Lyft，现 **CNCF**） | **2026-10-05** | 0.141.0（2026-09-01） | ❌ 无官方后端（原生 Neo4j）。Neptune 支持 Bolt+openCypher 理论可接，但其 Cypher 含 Neo4j 特性，**需改写并验证兼容性** | **51 个 AWS intel 模块**；**边建模最强**（IAM 权限链、网络路径、跨账号信任）；schema 声明式可扩展 → 直接解决「新增资源类型要改代码」 |
| CloudQuery | 2026-10-05 | cli-v6.43.0（2026-09-22） | ❌（有 Neo4j destination，源码级确认） | 数据源 70+，覆盖面极广；但模型是**关系表**，Neo4j 目标只是把表映射成节点，**非原生图** |
| Steampipe | 2026-10-05 | v2.4.7（2026-09-16） | ❌（Zero-ETL 不持久化） | SQL 实时查，无持久图、无边建模 |
| **Fix Inventory**（原 Resoto） | **2025-03-28** | 4.2.0（2024-12-05） | ❌（绑 ArangoDB） | ⚠️ **疑似停更（约 18 个月）**。图模型最接近我们，但停更 + 绑 ArangoDB |
| **CloudGraph** | **2023-05-20** | 2022-12 | ❌ | ❌ **已停更 3 年+** |
| **awspx** | **2021-08-25** | v1.3.4（2021-08） | ❌ | ❌ **已停更 5 年**，且范围窄（只做 IAM 攻击路径） |
| Cloud Custodian | 2026-10-01 | 0.9.53.0（2026-10-01） | 不适用 | YAML 策略治理引擎，非清单/图 |
| NetBox | 2026-10-06 | v4.7.2（2026-09-29） | ❌ | DCIM/IPAM，**手工录入非云自动发现** |
| Backstage catalog | 2026-10-05 | v1.55.3（2026-09-29） | ❌ | 服务/所有权目录，非基础设施自动发现 |
| Komiser | 2026-09-10 | **v3.1.22（2024-12-02）** | ❌ | 代码活跃但**发布停滞近 1 年**；无边建模 |

**硬约束(已核实)：无一候选能原生写入 Amazon Neptune。** Cartography 的 Neptune 适配器需自写,但工作量远小于维护全套自研 ETL。

### 1.3 `rca/` 智能根因分析

**推荐：HolmesGPT 作为基座（原生支持 Bedrock）；告警关联层参考 Keep；统计因果用 PyRCA 作库补充。**

| 项目 | 最近提交 | Bedrock 支持 | 关键可复用点 |
|---|---|---|---|
| **HolmesGPT** | **2026-10-05** | **✅ 原生**（README 明列 Bedrock） | **证据收集 toolset 框架**（≈我们 6 个 Layer2 探针）、agentic 调查循环、告警双向写回、Slack 推送、报告模板。CNCF Sandbox，Robusta+Microsoft |
| k8sgpt | 2026-10-04 | **✅ 原生**（`amazonbedrock`、`amazonbedrockconverse`，支持 inference-profile ARN） | 自定义 analyzer 框架、脱敏、Bedrock Converse 接入范式、MCP server。但分析器以 K8s 资源为主 |
| **Keep** | 2026-09-28 | ❌ **未在 AI 后端列表中**（仅 Anthropic/OpenAI/DeepSeek/Ollama/Grok/Gemini） | 告警**去重 + 规则关联 + 富化 + workflow + 单一视图 UI**，内置 CloudWatch provider（双向）。⚠️ **全自动 AI 关联属 Cloud/企业版，开源版仅规则关联** |
| Robusta | 2026-10-05 | 经 HolmesGPT 间接 | 告警路由/聚合、变更追踪。K8s 中心化，与我们 CloudWatch/Neptune 架构契合度低 |
| **PyRCA**（Salesforce） | 2026-06-02（此前大量提交停在 2023） | N/A（统计/因果，非 LLM） | **纯 Python 库**（`pip install sfr-pyrca`），贝叶斯网络/随机游走/ε-diagnosis/假设检验 → 补足纯图查询之外的统计因果推断 |
| OpenRCA（Microsoft） | 2026-04-14（23 commits，研究性质） | 可自接 | **RCA-agent 范式**（LLM 写 Python 按需检索 telemetry，避免长上下文）+ **RCA 评测基准**（可评估我们流水线准确率）。需 80GB 盘/32GB 内存 |
| kagent | 2026-10-05 | 非一等公民（可经 AI gateway 间接） | 声明式 Agent 运行时、MCP 工具接入、OTel 可观测。CNCF |
| SigNoz | 2026-10-05 | N/A | 与现有 CloudWatch 栈重叠，复用价值有限 |
| kubectl-ai | 2026-07-15 | 未能核实 | 交互式 kubectl 助手，非流水线组件 |
| incident.io 开源部分 | **未能核实**存在可用于 RCA 的开源组件（核心闭源） | — | — |
| Grafana Sift / Asserts | **未能核实开源版本存在**（`grafana/sift` 不存在，属 Cloud 闭源） | — | — |

### 1.4 `chaos/` 混沌工程

**推荐：沿用 Chaos Mesh + 直接复用 `aws-samples/fis-template-library`；最该补的新能力是「稳态假设判定」。**

| 项目 | 最新发布 | ARM64 | 稳态假设判定 | 关键可复用点 |
|---|---|---|---|---|
| **Chaos Mesh**（现用，CNCF 孵化） | v2.8.4（2026-08-18） | ✓（PR #3088 已合并） | ❌ **官方明确不打算加** | 30+ 故障类型、Workflow DAG 编排、CRD 可编程、自带 Dashboard |
| **LitmusChaos**（CNCF 孵化） | 3.32.0（2026-09-17，严格月度） | ✓（2020 起） | **✅ Probes**（HTTP/cmd/k8s/prometheus 前后置校验与裁决） | ChaosHub、Argo 编排、GraphQL API、完整控制台。**发布节奏最稳** |
| **Chaos Toolkit** | 1.21.4（2026-10-05） | ✓（纯 Python 无特权） | **✅ 原生 `steady-state-hypothesis` 块** | **自动 rollback**、Python SDK（**最适合 AI Agent 以代码生成实验**）、`chaostoolkit-aws` 可驱动 FIS。⚠️ 1.19→1.20 曾**沉寂约 2.5 年**（2024-02 → 2026-08） |
| **ChaosBlade**（阿里） | v1.8.1（2026-09-29）+ Blade AI v0.7.2 | **未能核实** | 较弱 | 故障面极广（OS/JVM/容器/K8s）；CLI+HTTP 易 AI 调用；**Blade AI 的会话式编排/安全审计/自动恢复思路与我们方向高度相关** |
| **Krkn**（Red Hat，CNCF Sandbox） | v5.2.12（2026-10-02，极频繁） | ✓ multiarch | **✅ health checks + Prometheus 告警裁决** | 场景插件、事件驱动触发器、**Python 原生（krkn-lib）易 AI 调用**、health check 中止做护栏 |
| Pumba | 1.2.1（2026-08-23） | ✓ | ❌ | 容器 kill/netem/stress，轻量补充 |
| kube-monkey | v0.7.0（2026-09-20） | ✓ | ❌ | 仅随机杀 Pod。曾停滞近 3 年后恢复 |
| **Netflix Chaos Monkey** | **v2.1.3（2024-10-03）** | — | ❌ | ⚠️ **疑似停更约 2 年**；强绑 Spinnaker；仅实例终止。**不推荐** |
| Steadybit 开源部分 | Kit/extensions 2026 活跃 | — | extension-prometheus 的 check 可借鉴 | ⚠️ **平台核心（编排引擎+UI）闭源商业**，开源仅扩展协议 |
| `aws-samples/fis-template-library` | 2026-04-14（143 commits） | 随 FIS | — | **大量 FIS 实验模板**（Aurora/DynamoDB/ElastiCache/EC2/SQS/CloudFront 区域级故障）→ 直接补齐我们 FIS 侧覆盖面 |
| `aws-samples/sample-aws-genai-ops-demos` (ai-chaos) | — | — | — | **FIS 的 MCP server，用自然语言生成 FIS 实验模板** → 与我们「AI 生成实验」方向直接相关 |

### 1.5 `dr-plan-generator/` 灾备编排

**推荐：继续以 Temporal 为执行底座，不要替换。借鉴 AWX 与 StackStorm 的人工审批/演练实现。**

| 项目 | 最近提交 | 部署复杂度（Temporal 为基准） | 人工审批 | 演练/真执行区分 | 图→顺序 |
|---|---|---|---|---|---|
| **Temporal**（现用 1.32） | 2026-10-05 | 基准 | Signal/Update（UI 自建） | ❌ | ❌ |
| Cadence（Uber） | 2026-10-04 | ≈Temporal | Signal | ❌ | ❌ |
| Argo Workflows（CNCF 毕业） | 2026-10-05 | **需 K8s** | `suspend/resume` ✅ | ❌ | ❌ |
| Rundeck（PagerDuty） | 2026-10-05 | **更轻**（单容器+DB） | 企业版/插件 | ❌ | ❌ |
| StackStorm | 2026-09-02（发布慢，3.9.0 为 2025-10） | **更重**（Mongo+MQ+Redis） | **Inquiries ✅ 最成熟** | ❌ | ❌ |
| Apache Airflow | 2026-10-05 | 中 | 弱 | ❌ | ❌ |
| **Ansible AWX / Runner** | 2026-10-02 / 2026-09-10 | 需 K8s，较重 | **审批节点 ✅** | **`--check` 天然 dry-run ✅** | ❌ |
| AWS multi-region resilience guidance | 2026-10-05 | 样例非产品 | 门 ✅ | ❌ | ❌ |
| aws-resilience-hub-tools | 2026-01-26 | 评估工具非引擎 | — | — | ❌ |
| **aws-samples/drs-tools** | **2025-02-06** | — | — | — | ⚠️ **疑似停更** |
| zph/runbook | 2026-03-07（单维护者） | 轻 CLI | 手动 | ❌ | ❌ |
| Eldergenix/runbook-guard | 2026-05-05 | **成熟度未能核实** | ✅ | **默认 dry-run ✅** | ❌ |
| **unskript/Awesome-CloudOps** | **2025-05-28** | — | — | — | ⚠️ **疑似停更** |
| **openark/orchestrator** | **2025-02-01** | — | — | — | ⚠️ **疑似停更**，且仅 MySQL 复制层 |

**另一项无人提供的能力**：「演练版本 == 批准版本 == 当前版本」这种三等版本门禁,**没有任何项目原生提供**。

### 1.6 `graph_mcp/` 图查询 MCP 与 NL2Cypher

**推荐：坚持自建受控查询目录；只吸收 AST 只读校验与审计日志作为第二道护栏。**

| 项目 | 最近提交 | 支持 openCypher/Neptune | 结论 |
|---|---|---|---|
| **awslabs/mcp · amazon-neptune-mcp-server** | 2026-09-08（功能性提交 2026-04-01） | **✅ openCypher + Gremlin，Neptune DB + Analytics** | 唯一原生对准 Neptune 的图 MCP。但走的正是我们**刻意否定**的「Agent 自由生成查询」路线,无目录无 provenance。⚠️ README 称该套件将逐步被新的 "Agent Toolkit for AWS" 取代 |
| **langchain-aws** `NeptuneOpenCypherQAChain` | **未能核实** | **✅ openCypher + SPARQL，Neptune** | 可复用 openCypher 生成链与 schema 注入 prompt；护栏仅「只读 + 正则抽取」,弱 |
| neo4j-contrib/mcp-neo4j | 2026-09-09 | ❌ 仅 Neo4j Cypher | 成熟 NL→Cypher 参考；绑 Neo4j |
| neo4j/neo4j-graphrag-python | **2026-10-05**（v1.22.0 於 2026-10-01） | ❌ 仅 Neo4j | **图+向量混合检索接口设计**值得借鉴（对应我们 rca 的图+语义检索） |
| **microsoft/graphrag** | 仅修 CVE（**日期未精确核实**） | ❌ | ⚠️ **已进入维护模式,明确不接新功能**；且场景错位（从文本建图,非查既有图）。**不建议作基座** |
| neo4j-labs/text2cypher | **未能核实** | ❌ | 微调数据集/基准,方向与「固定目录」相反 |
| LlamaIndex PropertyGraphIndex | 未核实（主仓活跃） | 有 Neptune 集成 | PropertyGraph + 向量抽象可借鉴 |
| **LanceDB** | 2026 活跃（未逐一核实） | — | **基于对象存储的 serverless 架构,与 S3 Vectors 最接近** → S3 Vectors 最贴切的开源替代 |
| Qdrant / pgvector | 2026 活跃（未逐一核实） | — | 成熟向量检索；pgvector 运维最简 |
| SQL 治理型 MCP（mcp-sql-guard / mcp-bigquery-server / safedb-mcp） | 多数活跃（未核实） | — | **AST 级只读校验 + allowlist + PII 掩码 + 防篡改审计日志** —— 理念与我们最接近,但在 SQL 侧 |

**一个值得记下的生态事实**：图数据库领域**几乎没有「受控查询目录」的 MCP 实现**,全部走自由生成 + 只读校验。
我们这个设计在图侧属空白,但 **awslabs 自家的 `lambda-tool-mcp-server`（把预定义 Lambda 暴露为 MCP 工具）本质就是同一模式**,是生态内对该设计的最强背书。

### 1.7 `compliance_export/` 合规映射导出

**推荐：维持自研内核，导出层可选挂接 OSCAL（经 compliance-trestle）。**

| 项目 | 最近发布 | 结论 |
|---|---|---|
| **compliance-trestle**（oscal-compass，原 IBM，CNCF Sandbox） | **v5.2.0（2026-10-05）**，约月更 | 自带 NIST 800-53/CSF catalog；OSCAL 文档创建/校验/转换；v5.2.0 新增「AWS Config 结果 → OSCAL 评估结果」。**但不做能力→控制项的图映射,也不认识 DORA/BCBS/SS1&21** |
| prowler | 5.44.0（2026-09-29，约双周更） | **50 个合规框架**自带。但它是**配置姿态扫描器**（「桶是否加密 → CIS 2.1.1」）,不是把业务能力映射到控制项 |
| steampipe-mod-aws-compliance | README 含 CIS v6.0.0，**精确日期未能核实** | 540+ 检查,框架齐全。同为资源姿态检查 |
| cloud-custodian | 2026-10-01 | 策略/治理引擎,**不提供控制项框架库也不做映射导出**,偏离最远 |
| OpenCRE（OWASP） | 2026-10-01 | 做**标准之间**互映射,不是把平台能力映射到控制项 |
| **regula**（fugue） | **已归档,2024-09-03 起只读** | ⚠️ **停更**,不建议 |
| OPA/Conftest、MapOSCAL、C2P、Audit Manager 周边 | **未逐一核实** | 均非「业务能力 → 控制项追溯」工具 |

**判断题的答案：不换。** 三个理由:

1. **没有开源项目做这件事。** 它们回答「这个资源是否满足某控制项」,我们回答「哪些业务功能依赖这条 ICT 服务、证据等级如何」。后者是 DORA Art.8/29/31、SS1&21 要的**映射**而非清单,依赖图遍历 + 证据分级 + 集中度分析。
2. **规模小恰恰是维持自研的理由。** 8 个文件、逻辑清晰、单一真源。引入 OSCAL 要承担模型学习曲线与格式阻抗,而 DORA/BCBS/等保本身都不是 OSCAL-native（OSCAL 以 NIST/FedRAMP 为中心）。
3. **值得借力的只有导出层。** 可让 `report.py` 增加一个 OSCAL Assessment-Results 导出分支,让结果被第三方审计工具消费。锦上添花,非替换。

---

## 二、避坑清单（已核实停更或有陷阱）

把这些单独列出来,因为它们在搜索结果里排名都不低,容易误选:

| 项目 | 问题 | 备注 |
|---|---|---|
| Caretta | 2025-03-17 起无提交（约 19 个月） | 边模型**最贴合我们**,可惜停更 |
| Fix Inventory（原 Resoto） | 2025-03-28 起无提交（约 18 个月） | 图模型最接近,但绑 ArangoDB |
| CloudGraph | 2023-05-20 起无提交（3 年+） | — |
| awspx | 2021-08-25 起无提交（5 年） | 范围也窄 |
| Netflix Chaos Monkey | v2.1.3（2024-10-03）后无发布 | Simian Army 早已归档 |
| regula | 已归档只读（2024-09-03） | — |
| unskript/Awesome-CloudOps | 2025-05-28 起无提交 | — |
| aws-samples/drs-tools | 2025-02-06 起无提交 | — |
| openark/orchestrator | 2025-02-01 起无提交 | — |
| microsoft/graphrag | **维护模式,明确不接新功能** | 36.2k star 容易误导 |
| **Keep** | **全自动 AI 关联是 Cloud/企业版**,开源版只有规则关联 | 文档不显眼,容易误判 |
| **Steadybit** | **编排引擎与 UI 闭源**,开源只有扩展协议 | — |
| **Chaos Toolkit** | 1.19→1.20 **沉寂约 2.5 年**,2026 才恢复 | 目前活跃,但历史有断档 |
| Komiser | 代码活跃但**发布停滞近 1 年**（v3.1.22 於 2024-12） | 「有提交」不等于「有发布」 |
| Grafana Sift / Asserts | **未能核实存在开源版本**（`grafana/sift` 不存在） | 属 Grafana Cloud 闭源 |
| incident.io | 核心闭源,开源仓库多为周边 | — |

---

## 三、建议的动作顺序

按「收益 ÷ 风险」排序,前两项收益最大:

**① 用 DeepFlow 拓扑 API 取代 4 条自研 Lambda ETL（拓扑侧）。**
改为周期性作业直接查 DeepFlow 已聚合的带方向/协议/QPS 的调用边并写 Neptune。一步消除自研 ETL,同时 eBPF 全量采集天然填补 X-Ray 采样空洞。**不引入任何新组件**（DeepFlow 已在跑）。

**② 评估 Cartography 作为 AWS 资产 ETL 基座（资产侧）。**
需自写 Neptune 适配器并验证 openCypher 兼容性,但换来 51 个声明式 intel 模块与最强的边建模。保留现有 EventBridge 实时管道补其增量短板。

**③ 给 `chaos/` 补「稳态假设判定」。**
Chaos Mesh 官方明确不做这块。借鉴 LitmusChaos 的 Probes,或引入 Chaos Toolkit 的原生 `steady-state-hypothesis` + Python SDK（后者天然适合 Bedrock Agent 以代码生成实验并自动回滚）。同时直接取用 `aws-samples/fis-template-library` 补 FIS 侧覆盖面。

**④ 把 `rca/` 的 6 个 Layer2 探针改写成 HolmesGPT 的自定义 toolset。**
HolmesGPT 原生支持 Bedrock,可复用其 agentic 调查循环、告警双向接入、报告模板。Neptune Graph-RAG 与 S3 Vectors 历史检索仍自研——这两块无可复用。

**⑤ `dr-plan-generator/` 保持 Temporal,精读 AWX 与 StackStorm 的审批/演练实现。**
拓扑排序用通用图库即可,没必要为此引入整套 K8s 原生引擎。

**⑥ `graph_mcp/` 保持受控目录,加一道 AST 只读校验与防篡改审计日志。**
参考 SQL 侧治理型 MCP 的做法。

**⑦ `compliance_export/` 维持自研,可选加 OSCAL 导出分支。**

---

## 四、本报告的可信边界

- **最近提交日期**:均实地取自 GitHub,可信。
- **近 6 个月精确 commit 数**:多数**未能取得**（API 限流）,活跃度为定性判断。
- 明确标注「未能核实」的条目:langchain-aws 最近提交、ChaosBlade 的 ARM64 支持、Pixie 的 ARM64 支持、Coroot 的拓扑导出 API 细节、steampipe-mod 的精确日期、microsoft/graphrag 的精确日期、text2cypher 的日期、Eldergenix/runbook-guard 的成熟度、LanceDB/Qdrant/pgvector 与 SQL 治理型 MCP 的逐项日期、incident.io 与 Grafana Sift 的开源组件是否存在。
- **未做的事**:没有实际部署或试跑任何候选项目。所有「部署难度」判断来自文档与仓库结构,**不是实测**。决定采用前应当先在非生产环境起一遍。

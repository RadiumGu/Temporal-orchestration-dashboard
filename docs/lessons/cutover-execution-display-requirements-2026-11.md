# 割接 / 容灾切换执行环节：大屏到底要展示什么（调研，2026-11）

> 调研时间 2026-11-05。代码基线 `origin/main` `359302a`（#83）。
> 本文回答「要展示哪些信息」；怎么做见 `docs/runbooks/dr-cutover-dashboard-design.md`。

## 1. 先定观众：同一场切换有四类人在看，问的问题不同

| 观众 | 在哪看 | 他要在 5 秒内得到答案的问题 |
|---|---|---|
| **指挥者**（切换负责人） | 指挥台大屏 / 自己电脑 | 我们会不会超 RTO？卡在哪一步、在等谁、等了多久？离不可逆点还有几步？有没有人 override 过闸门？ |
| **执行人**（做某一步的工程师 / agent） | 自己电脑 | 现在轮到我了吗？要执行的命令原文是什么？做完怎么确认？上一步的探针结论是什么？ |
| **观察者**（管理层、客户、业务方） | 会议室大屏 | 进行到哪个阶段了？顺利吗？大概什么时候结束？ |
| **审计 / 复盘** | 事后 | 每一步谁在什么时候做的、通过什么通道、有没有被核实？计划时长和实际差多少，时间花在机器上还是在等人？ |

这四组问题决定了信息分层：**态势（观察者）→ 阻塞与风险（指挥者）→ 当前动作（执行人）→ 证据（审计）**。一个页面同时满足四类人会变成什么都看不清，设计上要拆成视图（见设计文档 §3）。

## 2. 行业做法：专门做割接执行的产品展示什么

Cutover（专做割接 / DR runbook 执行的商业平台）的执行态界面是目前最成熟的参照，其帮助中心对单 runbook 大屏的组件描述如下（[Single Runbook Dashboard](https://help.cutover.com/en/articles/9353643-single-runbook-dashboard)、[Execute a Runbook](https://help.cutover.com/en/articles/3850249-execute-a-runbook)，以下为转述）：

- **RAG 状态 + 一句状态说明**，并显示由哪位管理员在何时更新。
- **可开始任务列表**（依赖已满足、等人认领）与**进行中任务列表**，各带预测开始 / 结束时间和已耗时。
- **里程碑任务**单独成区：已完成、可开始、未就绪三种图标，用来一眼看出「走到哪了、比计划快还是慢」。
- **按阶段完成度**、**按工作流（stream）汇总**：每个 stream 的计划 vs 实际开始/结束，用 ± 偏差表示早晚。
- **完成数随时间的燃尽/燃起图**。
- **迟到提示**：任务晚于计划 5 分钟开始出现警示，越晚越醒目，到 1 小时最强。
- **跳过任务必须写备注**，备注显示在任务旁。
- **演练（Rehearsal）与正式（Live）两种运行**，界面和通知都区分；正式运行中已完成任务的内容被锁定不可改。
- **开跑前校验**：绿 / 橙 / 红三档，红档（关键问题）阻止开始。
- **复盘（PIR）大屏**：计划 vs 实际的偏差着色，早于计划绿色、晚于计划橙色。

Cutover 在 DR 场景的文章里把执行期大屏要回答的核心问题归结为一句：**会不会达到 RTO**，并强调需要自动计算实际恢复时间（RTA）、人工任务和自动任务在同一张 runbook 里排序、自动生成不可篡改的审计记录（[Dynamic runbook execution for enterprise DR](https://cutover.com/blog/dynamic-runbook-execution-enterprise-disaster-recovery)，转述）。

AWS ARC Region switch 的执行详情页（2026-10 调研已核实，见 `docs/lessons/oss-reuse-survey-2026-10.md`）提供：每步状态、人工审批步骤、**RTO 目标与实际恢复时间对比**、每次执行生成 PDF 报告投递到 S3。

通用割接实践（ERP / 迁移 runbook 文章的共同点）补充三条：**命名的 go/no-go 检查点**、**可度量的回滚触发条件**（错误率、健康检查，而不是临场判断）、**按小时排的时间表 + 每步负责人**。例如 [enov8 的割接计划指南](https://www.enov8.com/blog/mastering-the-art-of-cutover-planning-a-step-by-step-guide/) 把割接计划定义为带负责人和检查点、含 go/no-go 与回滚步骤的时间序列任务表（转述）。

*以上 Cutover / enov8 内容均为转述，非原文引用。Content was rephrased for compliance with licensing restrictions.*

## 3. 信息清单（按层级）

标 ★ 的是容灾切换特有、通用 runbook 工具常常没有的。

### 3.1 全局态势（观察者 + 指挥者，页面顶部一条）

| 信息 | 说明 |
|---|---|
| 计划身份 | 计划 id、方向（东京 → 首尔）、**模式（演练 / 正式）**——演练与正式必须在视觉上不可能混淆（颜色 + 文字双编码） |
| 版本锚点 ★ | 执行的是哪一版（v 号 + sha256 前 8 位）、谁批准的、演练是否覆盖这一版 |
| 总体状态 | 进行中 / 等人 / 闸门未过 / 已完成 / 已中止 / 停滞（超时） / 被取消 |
| 时钟 | 切换已用时；**RTO 目标与预测完成时间**；与计划的偏差 |
| 进度 | 第 k / N 步；按阶段（A–F）的完成度 |
| 阻塞点 | 当前在等什么（确认 / 裁决 / 闸门）、**在等谁**、已等多久、**距离「等人超时自动停住」还剩多久** |
| 不可逆点 ★ | 第一个 `reversible: false` 步骤在哪；是否已越过。越过之前「回滚路径可用」，越过之后只能向前或另起回切计划 |
| 数据丢失裁决 ★ | Aurora 切换方式裁决（switchover / failover-allow-data-loss）的结果——这是唯一会丢数据的分叉，结论必须常驻显示 |
| 未核实标记 ★ | 有没有人 override 过闸门。有 override 时整次执行的结论只能是「无法判断」，大屏要明说 |

### 3.2 步骤列表（指挥者 + 执行人）

每一步：

- 序号、id、标题、**所属阶段**
- 类型：核查（只读）/ 人工变更 / 裁决
- **执行者类型**：机器（worker 探针）/ 人 / agent（经 MCP）/ ARC（托管服务执行）——一步里常常不止一个，见 3.4
- 状态（细分到「机器在跑前置探针」「等人执行命令」「机器在跑后置探针」，而不是笼统的「进行中」）
- 可逆性 + 回滚命令；不可逆时显示「为什么接受不可逆」
- 计划时长、实际开始 / 结束、实际时长、偏差
- 条件步骤：被跳过时显示「因为裁决 X 选了 Y」
- 探针结论：**observed 与 expected 并排**，不是只给 PASS/FAIL

### 3.3 当前等待点（执行人，最醒目的卡片）

- 等待类型：确认结果 / 执行命令并确认 / 裁决 / 闸门（探针未全过）
- 命令原文（可复制）、裁决选项、闸门失败的探针与原因
- 允许的动作：retry / override（必须写理由）/ abort
- 已等时长与超时倒计时
- 推进方式：现在只有 `probe_cli.py update ...`（经 SSM）和 temporal-mcp `update_workflow` 两条通道；大屏要给出可复制的完整命令

### 3.4 执行者与证据 ★（审计 + 指挥者）

一个人工步骤实际包含四个动作，执行者各不相同：

```
机器：前置探针  →  人：在 Temporal 之外执行命令  →  人或 agent：回报「已执行」  →  机器：后置探针核实
```

Temporal **看不到**第二个动作本身，只看到第三个动作「有人声称执行了」。所以大屏对每个人工动作要分开显示三件事：

| 字段 | 来源 | 可信度 |
|---|---|---|
| 署名 | Update 参数里的 `operator` | 自报 |
| 通道 | Update 请求的 `meta.identity`（服务端写进 history 的 `WorkflowExecutionUpdateAcceptedEvent`） | 客户端声明，但能区分 CLI / MCP / 控制台 |
| 认证身份 | CloudTrail（SSM StartSession、ARC `ApprovePlanExecutionStep`）或控制台登录 | 已认证 |

把这三者混成一个「执行人：alice」会让审计误以为身份已被核实。目前全系统唯一被认证过的人工身份是 ARC 审批人（`arc_state.approvers` 从 CloudTrail 读出，带 MFA 标记）。

### 3.5 时间

- 每步拆成**机器耗时**（探针）和**等人耗时**（从开始等到收到回复）。演练复盘最有用的结论通常是「时间花在等人上」，而这只有拆开才看得见。
- 计划时长来源：runbook 声明的 `expected_minutes`，或历次执行记录的中位数。
- 预测完成时间 = 已用时 + 当前步剩余 + 后续步计划时长之和。

### 3.6 平台自身健康 ★

容灾时编排平台本身也在压力下，大屏不能只展示业务：

- **数据新鲜度**：「状态更新于 N 秒前」。陈旧的状态在切换中是危险的，必须显性。
- **worker 是否在线**：worker 不在，query 失败、update 被拒，计划推进不了。注意 Temporal 在没有 poller 时会**省略** pollers 字段，要显示「未报告」而不是「0」（见 temporal-mcp `describe_task_queue` 的修复）。
- **`TemporalReportedProblems`**：workflow task 在激活阶段失败时，列表页仍显示 Running，只有这个系统 search attribute 会暴露问题（项目已踩过）。
- Temporal 自身所在区域：当前 Temporal 只在首尔一台 EC2 上，是已接受的单点。

### 3.7 计划治理（多计划总览）

- 计划生命周期：draft → approved → drilling → drilled → executing → executed → closed
- 当前版本、批准版本、演练版本是否一致（`plan_state` 里三个布尔就是硬闸门的分解）
- **演练新鲜度**：最近一次演练的时间和结论；超过一定天数要提示（对应 Cutover 的「过期管理」）
- 同一人修订并批准（`same_person_revised_and_approved`）：记录不阻止，但要显示

### 3.8 事后复盘

- 计划 vs 实际（每步、每阶段）
- override、超时、重试闸门的次数和位置
- 执行记录 S3 链接。**Temporal 保留期 720h**，30 天后 history 消失，复盘与长期历史只能读 `plans/<plan_id>/executions/*.json`

## 4. 对照：现有数据能撑起多少

| 信息 | 现有来源 | 缺口 |
|---|---|---|
| 计划列表、生命周期、版本闸门 | `DrPlanWorkflow.plan_state` + SA `DRPlanId` 等 | 无 |
| 当前步骤、等待点、命令原文 | `DrRunbookWorkflow.runbook_state` | 只返回**当前一步**，没有全量步骤状态 |
| 全部步骤定义 | `current_body` 查询 → `runbook.extract_runbook()` | 无（纯 Python，可复用） |
| 每步开始 / 结束时间 | **无**（step 记录里只有回复时刻 `at`） | 需要补，或从 history 推导 |
| 计划时长、RTO 目标 | **无**（`dr-runbook/v1` 没有这两个字段） | 需要加可选字段 |
| 执行者署名 | 回复里的 `operator` | 自报 |
| 执行通道 | Update 的 `meta.identity` | probe_cli 不设，默认 `pid@hostname`；MCP 由调用方自填 |
| ARC 步骤、审批人 | `arc_state`（含 CloudTrail 审批人与 MFA） | 无 |
| 探针 observed / expected | `runbook_state.last_probes`（最后 8 条）| 只有最后 8 条；全量在 step 记录里但不在 query 里 |
| worker 在线 | DescribeTaskQueue | 字段缺省语义要处理 |
| 30 天后的历史 | S3 执行记录 | 记录里也没有时间戳 |

结论：**展示层要的东西，七成已经在 query 和 SA 里；真正缺的是时间（开始/结束/计划时长/RTO）和全量步骤视图。** 这两项都是展示元数据，不改变 workflow 发出的 command。

## 5. 几条容灾大屏特有的原则

1. **未知不显示成 0，也不显示成绿色。** 测不到（UNKNOWN）、未报告、数据陈旧，都要有独立的视觉状态。
2. **人和机器分开显示**，自报身份和已认证身份分开显示。
3. **演练和正式不可能看错。**
4. **不可逆点是一等元素**，不是表格里的一个布尔列。
5. **大屏只读是默认。** 操作入口要单独设计并保持现有审计链（设计文档 §6）。
6. **Temporal UI 仍然是调试器**：大屏解决「看懂」，排查问题还是回到 Temporal UI 和 history。

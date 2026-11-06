# 切换执行大屏（DR Cutover Dashboard）设计

> 2026-11-05 初稿。代码基线 `origin/main` `359302a`。
> 信息需求的调研依据：`docs/lessons/cutover-execution-display-requirements-2026-11.md`。
> 上位设计：`docs/runbooks/dr-arc-temporal-hybrid-design.md` §7（入口缺口）、§10（大屏定位）。

## 1. 目标与非目标

**目标**：一个页面看清已定义的计划和正在进行的切换：每一步是什么、谁在做（机器 / 人 / agent / ARC）、状态、时间、离 RTO 和不可逆点还有多远；人和 agent 推进步骤时，大屏实时反映，并如实区分自报身份与已认证身份。

**非目标**：

- 不替代 Temporal UI 做排查。
- 不新增任何「推进步骤」的权威逻辑。validator 仍是唯一权威，大屏和 probe_cli、MCP 一样只是一个客户端。
- 不在 v1 提供写操作（理由见 §6）。
- 不做多活、不做全自动切换（与上位设计一致）。

## 2. 为什么不是 Temporal UI、Grafana 或 iframe 扩展

| 方案 | 结论 | 原因 |
|---|---|---|
| 继续打磨 Temporal UI（PR #78 已做） | 保留作调试器 | 它按 event 展示，不按「步骤」展示；Timeline 按真实时间缩放，30 天等待会压扁所有步骤；没有 RTO、不可逆点、执行者区分 |
| Grafana State timeline | 不选 | 画不出 RTO 预测、等待点卡片、执行者三元组；Volkov Labs 交互插件已归档（2026-10 调研） |
| Temporal UI `customUi.iframeExtensions` 嵌入 | 可选的入口位，不是方案 | 只是一个 iframe 槽位，内容仍然要自己做；后期可把本大屏挂进 Temporal UI 顶栏 |
| **自建 BFF + 单页前端** | **选这个** | 数据 70% 已在 query / SA 里（调研 §4），缺的只是时间字段；前端可以按「步骤」而不是「事件」建模 |

## 3. 视图

一个应用，三个视图，同一份数据：

| 视图 | 给谁 | 内容 | 交互 |
|---|---|---|---|
| **总览**（Plans） | 指挥者、审计 | 所有计划：生命周期、当前 / 批准 / 演练版本是否一致、最近演练时间与结论、有无在途执行 | 点进单次执行 |
| **执行**（Run） | 指挥者、执行人 | 顶部态势条 + 阶段泳道 + 步骤表 + 当前等待卡片 + 证据时间线 | 展开步骤看探针、复制命令 |
| **大屏**（Wall） | 观察者 | 态势条放大 + 阶段进度 + 当前步骤一行 + RTO 时钟 | 无，只读，大字号，自动刷新 |

### 3.1 执行视图线框

```
┌ 演练 REHEARSAL ▌plan-20261006-tokyo-to-seoul · v7 (sha 3fa9c21e) · 批准 bob · 演练覆盖 v7 ✓ ┐
│ 已用 01:42:10   RTO 目标 04:00   预测完成 03:25 (提前 35m)   第 14/27 步   数据 3 秒前 ● worker 在线 │
│ ⚠ 不可逆点：第 19 步 promote-aurora（还差 5 步）   Aurora 裁决：switchover   override：0      │
└──────────────────────────────────────────────────────────────────────────────────────────┘
┌ 阶段泳道 ───────────────────────────────────────────────────────────────────────────────┐
│ A 前置核查 ██████████ 9/9  B 计算 ████ 1/1  C 工作负载 ███░░ 3/5  D 数据层 ░░░░ 0/4 ◆ ...   │
└──────────────────────────────────────────────────────────────────────────────────────────┘
┌ 现在等你 ────────────────────────────────┐ ┌ 步骤 ─────────────────────────────────────────┐
│ 🙋 执行并确认 · 14 apply-workload-search │ │ #  步骤                 执行者    状态     计划/实际 │
│ 已等 6m12s · 超时停住还剩 23h53m         │ │ 12 部署 petsite       🤖→👤→🤖 ✓已核实   8m/7m   │
│ $ kubectl --context ... apply -f ...    │ │ 13 部署 payforadoption 🤖→👤→🤖 ✓已核实  8m/11m ▲│
│ [复制 probe_cli 确认命令]                │ │ 14 部署 search-service 🤖✓→👤…        等人执行 │
│ 前置探针：deploy_ready … PASS            │ │ 15 部署 petfood       —         未开始   8m/–  │
└──────────────────────────────────────────┘ └──────────────────────────────────────────────┘
┌ 证据时间线 ──────────────────────────────────────────────────────────────────────────────┐
│ 10:41:03 🤖 worker  pre  deploy_ready(search-service) PASS  observed ready=0 expected≥0  │
│ 10:34:51 👤 alice   confirm_step apply-workload-payforadoption  通道 cli@ip-10-20-1-10 (SSM) │
│ 10:22:10 🤖 agent   confirm_step check-ecr-images  通道 agent:devops-agent  身份自报          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

视觉规则：

- **模式双编码**：演练用中性色条 + 「演练」字样；正式用警示色条 + 「正式」字样。只靠颜色会在投影仪上看错。
- **状态不只靠颜色**：每个状态有图标 + 文字，色盲和黑白投影都能读。
- **时间轴按步骤等宽，不按真实时间缩放**。等人的时长画成步骤内的斜线段并标数字。这正是 Temporal Timeline 被 30 天计时器压扁的反面。
- **不可逆点**：泳道上的 ◆ 标记 + 态势条常驻一行；越过之后整条态势条加一道边框并改文案为「已越过不可逆点」。
- **未知 / 陈旧**：UNKNOWN 探针用独立的灰色带问号，不是红也不是绿；数据超过 30 秒未更新，态势条变为「数据陈旧」并停止显示预测完成时间。

## 4. 数据模型

### 4.1 步骤视图 `StepView`（BFF 产出，前端只消费这一种）

```ts
type Actor = 'machine' | 'human' | 'agent' | 'arc';
type Trust = 'authenticated' | 'channel-only' | 'self-asserted';

interface ActionRecord {
  actor: Actor;
  what: 'probe' | 'confirm' | 'decide' | 'resolve_gate' | 'arc_step' | 'arc_approval';
  at: string;                 // 服务端事件时间
  operator?: string;          // Update 参数里的署名（自报）
  channel?: string;           // Update meta.identity / activity 的 worker identity
  trust: Trust;
  detail?: Record<string, unknown>;   // 探针 observed/expected、裁决选项、override 理由
}

interface StepView {
  index: number; id: string; phase: string; title: string;
  kind: 'check' | 'manual' | 'decision';
  status: StepStatus;              // 见 4.2
  reversible: boolean | null; rollback?: string; irreversibleNote?: string;
  command?: string; options?: string[];
  skippedBecause?: { step: string; chosen: string; needed: string[] };
  plannedMinutes?: number;          // runbook expected_minutes 或历次中位数
  startedAt?: string; finishedAt?: string;
  machineSeconds?: number; humanWaitSeconds?: number;
  actions: ActionRecord[];
}
```

### 4.2 状态推导

全部由 `runbook_state` 的 `awaiting` + 光标 + step 记录推出，不靠前端猜：

| 条件 | 状态 | 显示 |
|---|---|---|
| index > cursor 且未跳过 | `pending` | 未开始 |
| 在 `skipped` 里 | `skipped` | 跳过（附裁决原因） |
| index == cursor，`awaiting == null` | `probing` | 机器核查中（pre / check / post） |
| `awaiting.type == confirm` 且 `check == true` | `await_ack` | 等人确认核查结果 |
| `awaiting.type == confirm` 且 有 `command` | `await_exec` | 等人执行命令 |
| `awaiting.type == decision` | `await_decision` | 等人裁决 |
| `awaiting.type == gate` | `gate_blocked` | 闸门未过（列出失败探针） |
| 已完成且该步有 override | `done_overridden` | 完成·未核实 |
| 已完成 | `done` | 完成·已核实 |
| run 状态 `stalled` 且是光标步 | `stalled` | 等人超时，已停住 |
| run 状态 `aborted` 且是光标步 | `aborted` | 已中止 |

### 4.3 执行者与可信度判定

| 证据 | actor | trust |
|---|---|---|
| 探针 activity（`ActivityTaskStarted.identity` = worker） | machine | channel-only |
| Update，`meta.identity` 以 `agent:` 开头 | agent | self-asserted（CloudTrail 只见 AgentCore 角色） |
| Update，`meta.identity` 以 `cli:` 开头或为默认 `pid@host` | human | channel-only（真实 IAM 身份在 CloudTrail `StartSession`） |
| Update，`meta.identity` 以 `console:` 开头（v3 才有） | human | authenticated（BFF 从已验签的 JWT 写入） |
| `arc_state.timeline` 里的 ARC 步骤 | arc | channel-only |
| `arc_state.approvers`（CloudTrail，带 MFA） | human | authenticated |

前提是 §7 的 G3：身份前缀由**通道服务端**强制加上，调用方填不掉。

### 4.4 时间与 RTO

- 切换时钟 T0 = 正式执行子 workflow 的开始时间（`authorize_execution` 之后）。演练有自己的时钟，不与正式混算。
- 预测完成 = 已用时 + 当前步剩余（`plannedMinutes − 当前步已用`，不小于 0）+ 后续未跳过步骤的 `plannedMinutes` 之和。
- 有步骤缺 `plannedMinutes` 时，预测显示为「≥ x」并注明缺几步，不把缺失当 0。
- 迟到提示：当前步超出计划 5 分钟起提示，越晚越醒目（沿用 Cutover 的做法）。
- RTO 目标来自 runbook 新增的 `rto_minutes`；没有就不显示 RTO 行，不编一个。

## 5. 架构

### 5.1 数据通路

```
                                   首尔 ap-northeast-2
 ┌────────────┐  SSM 端口转发   ┌─────────────────────── Temporal EC2 10.20.1.10 ───────────────────────┐
 │ 运维人员浏览器 │──────────────▶│  dashboard-bff (容器, :8090)                                          │
 └────────────┘ (v1 唯一入口)   │   ├─ Temporal HTTP API localhost:7243                                │
 ┌────────────┐  CloudFront     │   │    ListWorkflowExecutions（SA 过滤）· Describe · Query            │
 │ 会议室大屏    │──(v2, 首尔入口)─▶│   │    GetWorkflowExecutionHistory(waitNewEvent=true) 长轮询        │
 └────────────┘  + Cognito      │   │    DescribeTaskQueue（worker 在线）                              │
                                │   ├─ runbook.py / ui_text.py（直接 import，同一套解析）                │
                                │   └─ S3 plans/*/executions/*.json（30 天后的历史）                    │
                                │  temporal server 1.32 · DR worker（已在同机）                          │
                                └─────────────────────────────────────────────────────────────────────┘
 agent ── temporal-mcp（AgentCore, 首尔）── Temporal HTTP API（不经 BFF；BFF 从 history 看到它的 Update）
```

选型理由：

- **BFF 放在 Temporal 同机**：与 2026-09-24「DR worker 跑在 Temporal EC2 上」的决定一致，不引入新的故障域；切换时 EKS 可能正是被操作对象，不放 EKS。代价是同一个单点，上位设计已接受。
- **BFF 用 Python**：直接 import `runbook.py`（纯 Python）解析步骤定义，与 worker 同一份代码，不写第二套解析。
- **不用 Lambda**：要为每个在途执行维持一个 history 长轮询并向多个浏览器推 SSE，常驻进程更直接。

### 5.2 实时性与对 Temporal 的负载

- 每个**在途执行**一条 `GetWorkflowExecutionHistory(waitNewEvent=true)` 长轮询。有新事件才重新 `query runbook_state`，再把差量经 SSE 推给浏览器。N 个浏览器只产生 1 条长轮询和每事件 1 次 query。
- Query 是在 **worker** 上执行的：worker 不在线时 query 失败。BFF 因此有两条读路径：
  - **主路径**：query（字段全，含命令原文、探针 observed）
  - **降级路径**：只用 history + describe 推导步骤边界（正式执行每步开始时有一次 `UpsertWorkflowSearchAttributes` 写 `DRStepName`；探针是 activity 事件；人的动作是 Update 事件；等待是 timer 事件）。演练模式不写 `DRStepName`，只能按探针 activity 的顺序对齐到步骤。降级时态势条明示「worker 不在线，状态由 history 推导，无法推进」。
- 列表视图每 10 秒一次 `ListWorkflowExecutions`。visibility 是最终一致的，列表与详情短暂不一致时以详情为准。
- 关闭的执行：Temporal 保留期内读 history；超过 30 天只读 S3 执行记录。

### 5.3 BFF 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/plans` | 计划列表 + 每个计划的 `plan_state`（缓存 10 秒） |
| GET | `/api/runs/{workflowId}` | 一次执行的完整快照：`StepView[]` + 态势 + 健康 |
| GET | `/api/runs/{workflowId}/stream` | SSE：`snapshot` / `step` / `action` / `health` 四种事件 |
| GET | `/api/health` | worker pollers（缺省 = 未报告）、`TemporalReportedProblems`、数据年龄 |
| GET | `/api/runs/{workflowId}/record` | 已结束执行的 S3 记录（复盘视图） |
| POST | `/api/runs/{workflowId}/actions/{confirm_step\|decide\|resolve_gate}` | **v3 才开**，见 §6 |

## 6. 人工控制：放在哪、怎么保住审计链

现状（上位设计 §6）：人推进经 `probe_cli.py` + SSM，CloudTrail 有真实 IAM 身份；agent 经 temporal-mcp `update_workflow`（#83 放开），署名自报。2026-10-07 我们已经否决了「在 Temporal UI 里发 Update」，原因是 UI 发出的 Update 不带可审计身份。

大屏加写操作会遇到同一个问题，所以分三档：

| 档 | 大屏能做什么 | 审计链 | 建议 |
|---|---|---|---|
| **v1 只读 + 复制命令** | 等待卡片给出完整的 `probe_cli.py update <wid> confirm_step '{...}'`，人粘贴到 SSM 会话执行 | 不变 | **先做这个** |
| v2 只读大屏对外 | 会议室 / 客户经首尔 CloudFront + Cognito 只读访问 | 不涉及写 | 跟 §5 前门方案一起做 |
| v3 控制台写操作 | 按钮直接发 Update，BFF 从已验签的登录令牌取身份，强制写 `meta.identity = console:<email>`，带 `update_id` 幂等键，并把请求本身另记一份到 S3 | 新增一条**已认证**通道 | **需要你决定**；不可逆步骤建议同时要求第二人确认 |

v3 的硬约束：BFF 不做任何校验逻辑，validator 拒绝什么就原样显示什么；BFF 的 IAM 权限与 worker 一样只读 AWS，它写的只有 Temporal Update 和 S3 审计记录。

## 7. 需要的代码改动（全部是展示元数据，不改变 command 序列）

| # | 改动 | 位置 | 风险 / 验证 |
|---|---|---|---|
| **G1** | step 记录加 `started_at` / `awaiting_since` / `replied_at` / `finished_at`（`workflow.now()`）；新增 query `runbook_progress` 返回全部步骤的记录、光标、跳过与裁决 | `runbook_workflow.py` | 只加 query 与字典字段，不新增 command。仍按 `auto/verify-temporal-workflow-code-change-by-replaying-live-history` 用新代码回放服务端全部 DR history（PR #78 的做法） |
| **G2** | `dr-runbook/v1` 增加可选字段：计划级 `rto_minutes`，步骤级 `expected_minutes`、`owner`（负责团队） | `runbook.py` validator + `runbook_draft.py` | 可选字段，旧正文不受影响；但改了正文就是新版本，要重新走批准 + 演练 |
| **G3** | 通道身份前缀由通道服务端强制：temporal-mcp 写 `agent:<claimed>`；probe_cli 连接时设 `identity="cli:" + 默认值` | `temporal-mcp/src/tools/workflows.ts`、`probe_cli.py` | 调用方改不掉前缀，agent 就无法伪装成 CLI。temporal-mcp 要重新部署 AgentCore runtime |
| **G4** | 导出的 S3 执行记录带 G1 的时间戳 | `runbook_workflow._export` | 复盘与「计划时长取历次中位数」靠它 |

G1 不做也能出 v1：BFF 走 §5.2 的降级路径从 history 推导时间。但那样每次快照都要读全量 history，长执行会慢，所以 G1 排在 BFF 之前。

## 8. 部署（首尔）

| 项 | 做法 |
|---|---|
| 运行 | Temporal EC2 上 `docker run`，与 server、worker 同一 compose 网络；监听 `127.0.0.1:8090`，不开安全组 |
| 访问（v1） | `aws ssm start-session --target <首尔 Temporal 实例> --document-name AWS-StartPortForwardingSession --parameters portNumber=8090,localPortNumber=8090`，浏览器开 `http://127.0.0.1:8090` |
| 权限 | 复用 worker 实例角色的只读权限 + 对执行记录桶的 `s3:GetObject`/`ListBucket`；v3 才需要 `s3:PutObject` 到单独的审计前缀 |
| 入口（v2） | 首尔 CloudFront + Cognito（上位设计 §5/§7 已规划），源站经 CloudFront VPC origin 到内网 ALB 或实例。Cognito 在首尔建 user pool；若用 IAM Identity Center，要确认已复制到首尔（Identity Center 2026 起支持多区域复制，但需要客户托管的多区域 KMS 密钥），否则东京故障时登录不了 |
| 前端 | React + Vite + TypeScript，`EventSource` 收 SSE；构建产物由 BFF 直接托管，不另起 S3 站点 |

## 9. 故障模式

| 故障 | 大屏表现 | 处理 |
|---|---|---|
| worker 不在线 | query 失败 | 切到 history 降级路径；红条「无法推进」；pollers 缺省显示「未报告」 |
| workflow task 激活失败 | 列表仍 Running | 读 `TemporalReportedProblems`，显示问题类别 |
| BFF 自己挂了 | 浏览器 SSE 断开 | 前端显示「连接断开 N 秒」，不保留最后一帧当作当前状态 |
| Temporal EC2 不可用 | 全部不可用 | 与编排器同命运（已接受的单点）；切换按纸面 runbook + S3 最近执行记录继续 |
| 东京区域故障 | 不受影响 | 全部组件在首尔；入口不再经东京 ALB |
| visibility 滞后 | 列表与详情短暂不一致 | 以详情（describe / query）为准 |

## 10. 验证计划

1. G1：新 query 在本地 `temporal server start-dev` 上读回；用新代码回放首尔全部 DR history，结果与现网代码一致。
2. BFF 降级路径：停 worker，确认快照仍能给出光标与时间、并显示「无法推进」。
3. 实时性：在一次演练里用 probe_cli 发 `confirm_step`，测从 Update 被接受到浏览器出现的延迟（目标 < 2 秒）。
4. 身份：分别经 probe_cli、temporal-mcp 发 Update，确认大屏的 actor / trust 判定与 §4.3 一致，且 MCP 无法写出 `cli:` 前缀（G3 之后）。
5. 演练 / 正式双编码：黑白打印一张截图，确认模式仍可辨认。

## 11. 路线图

| 阶段 | 内容 | 前置 |
|---|---|---|
| 1 | G1 + G4（时间戳与全量进度 query） | 回放验证 |
| 2 | BFF + 执行视图 + 总览视图，SSM 端口转发访问，只读 + 复制命令（v1） | 1 |
| 3 | G2 计划时长与 RTO；预测完成时间上线 | 一次真实演练取基线 |
| 4 | G3 通道身份前缀 | 无 |
| 5 | 大屏视图 + 首尔 CloudFront/Cognito 只读入口（v2） | 上位设计 §5 前门 |
| 6 | 控制台写操作（v3） | **你的决定** |

## 12. 待你决定

1. **v3 是否要做**：大屏上直接点按钮推进步骤。做的话，不可逆步骤要不要强制两人确认。
2. **RTO 时钟从哪一刻起算**：`authorize_execution` 之后的执行开始（本文默认），还是「宣布灾难」的时刻（需要人工录入）。
3. **计划时长的来源**：在 runbook 里手填 `expected_minutes`，还是只用历次演练中位数。

## 13. 未核实

- CloudFront VPC origin 与内网 ALB + Cognito 认证动作组合是否可行（ALB 认证动作需要能访问 IdP 端点），v2 动手前要实测；备选是在 CloudFront 侧用 Lambda@Edge 验证令牌。
- 首尔 Temporal UI 的版本（Timeline 渲染 activity summary 需要 ≥ v2.34.6）与本设计无关，未查。
- 本机到首尔 Temporal（`10.20.1.10:7243`）不通，本文没有读取在途执行的实时数据；状态推导表是按 `origin/main` 源码写的，G1 落地时要用真实 history 对一遍。
- 本机 AWS 凭证当前无效（`InvalidClientTokenId`），没有核对首尔的 IAM、安全组和 Identity Center 配置。

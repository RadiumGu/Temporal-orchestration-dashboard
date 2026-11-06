# Temporal-orchestration-dashboard

东京 → 首尔灾备切换的 Temporal 编排：计划评审链（`DrPlanWorkflow`）、人执行 + Temporal 核实的执行链（`DrRunbookWorkflow`）、ARC Region switch 桥接、只读探针，以及正在设计的切换执行大屏。

2026-11-06 从 [graph-dependency-platform](https://github.com/RadiumGu/graph-dependency-platform)（`origin/main` `359302a`，#83）拆出，用 `git filter-repo` 保留了这些路径的提交历史（81 个提交）。相对路径保持不变，所以测试、部署脚本、文档里的路径引用都不用改。

## 目录

| 路径 | 内容 |
|---|---|
| `dr-plan-generator/worker/` | worker：工作流、activity、探针目录与实现、ARC 桥接、`probe_cli.py`、UI 文本渲染 |
| `dr-plan-generator/draft_runbook.py` | 从实测事实生成 `dr-runbook/v1` 计划初稿 |
| `infra/dr-korea/temporal-1.32/` | 首尔 Temporal 1.32 服务端（compose）、`deploy-worker.sh`、IAM 授权脚本 |
| `infra/dr-korea/0{2,5,6,7,8}-*.yaml`、`20-*.yaml`、`arc-approve.sh` | Temporal 主机、temporal-mcp AgentCore 运行时、worker 权限、ARC 计划 |
| `infra/dr-korea/workloads/`、`15-korea-workloads.yaml`、`petsite-korea-drill.yaml`、`scripts/*korea_workloads.py` | 计划初稿引用的首尔工作负载清单（见下「与原仓库的重叠」） |
| `tests/` | 17 个 DR 测试 + 辅助模块 |
| `docs/` | 编排交接文档、ARC 混合方案设计、切换大屏设计与调研 |

## 测试

```bash
python3.11 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
DR_REQUIRE_TEMPORAL=1 DR_MIN_PASSED=245 .venv/bin/python -m pytest -q
```

test_129 / test_132 / test_136 会起本地 Temporal 测试服务器（`WorkflowEnvironment.start_local`，首次运行会下载 CLI）。拆分时实测 248 passed。

## 部署 worker

`infra/dr-korea/temporal-1.32/deploy-worker.sh --publish` 从**本仓库的 git 对象库**取 `dr-plan-generator/worker/` 发布到 S3，路径与原仓库相同，所以在本仓库里运行即可。本仓库还没有 remote，`--ref` 只能用本地分支或 SHA。

## 运行时仍依赖原仓库的地方

- `snapshot_workflow.py` 的 `DR_GENERATOR_DIR` 默认 `/opt/graph-dependency-platform/dr-plan-generator`：快照导出要调用原仓库的计划生成器（读 Neptune 依赖图）。这是首尔主机上的运行时路径，不是代码依赖。
- worker 通过 graph MCP（网络）读依赖图，`graph_mcp_client.py` 不 import 原仓库代码。
- `deploy-worker.sh` 里的 `REPO=RadiumGu/graph-dependency-platform` 只赋给了一个未被使用的 `RAW_BASE` 变量，发布不走 GitHub。

## 与原仓库的重叠（待决定）

原仓库里这些路径**还没有删除**，现在两边各有一份：

- 上表全部路径
- `tests/cfn_yaml.py`、`tests/zh_text.py`（原仓库其他测试也在用，删除时要留在那边）
- `docs/runbooks/deployment-record.md`（全平台的部署记录，test_130 读其中 §4.54；这里是整份拷贝）

留在原仓库、**不**搬过来的：`dr-plan-generator/executor_temporal.py`（旧执行器骨架，和 `executor_base` / `models` 绑在一起）以及守它的用例（test_80，test_81 的 `TestMutualExclusionViaWorkflowId`，test_128 的 `test_measured_value_recorded`）。

## 拆分时对测试做的改动

| 测试 | 改动 | 原因 |
|---|---|---|
| test_81 | 去掉 `TestMutualExclusionViaWorkflowId` | 守的是 `executor_temporal.py`，留在原仓库 |
| test_128 | 去掉 `test_measured_value_recorded`；保留期注释检查只扫 worker | 同上 |
| test_130 | CI 文件改为 `.github/workflows/dr-checks.yml`；通过数下限改为 `DR_MIN_PASSED ≥ 245` | 原仓库的 `GDP_OFFLINE_MIN_PASSED` 是全平台的通过数（1820） |
| `tests/conftest.py` | 新写：只注入 `tests/` 与 `dr-plan-generator/`，加 `DR_MIN_PASSED` 下限 | 原 conftest 还注入 rca、chaos，并带离线云访问跳过机制，这里都用不到 |

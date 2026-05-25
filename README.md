# TeamCollab

Git-native asynchronous multi-agent collaboration plugin for Claude Code.

**仓库即黑板。Commit 即事件。Push/Pull 即同步。**

TeamCollab 让多个 Claude Code 实例（代表不同团队成员）通过一个 Git 仓库异步协作完成文档类作业。无需中央服务器——离线工作、在线推送、DAG 调度自动收敛。

---

## 特性

- **14 个 MCP 工具** — 覆盖项目初始化、任务管理、产物提交、评审、搜索、同步
- **10 个 Slash 命令** — `/team-init`、`/team-tasks`、`/team-join`、`/team-claim`...
- **DAG 任务调度** — 拓扑依赖校验，防自环、防悬空、过载预警
- **自动评审** — 5 维度 × 20 分制（contract / brief / glossary / continuity / evidence）
- **自动整合** — 术语归一、风格统一、冲突标注
- **GitHub Actions 兜底** — 组长离线时 Action 自动评审 + 生成草稿
- **离线容错** — push 失败自动排队，联网后透明重试
- **冲突自愈** — pull-rebase-retry 循环，JSON 文件 deep-merge

---

## 快速开始

### 前提条件

| 软件 | 版本 | 用途 |
|------|------|------|
| Python | ≥ 3.11 | 运行 MCP Server |
| Git | ≥ 2.30 | 版本控制 |
| Claude Code | 最新 | AI 交互界面 |
| gh CLI | ≥ 2.0 | 可选，用于 GitHub 操作 |

### 安装

三种安装路径，选其一：

#### 路径 A：Plugin 安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/your-org/team-collab.git
cd team-collab

# 运行安装脚本
# macOS / Linux:
bash scripts/install.sh

# Windows (以管理员身份运行 PowerShell):
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

安装脚本会：
1. `pip install -e .` 安装 Python 包
2. 创建 `~/.claude/plugins/team-collab` 符号链接指向此仓库

#### 路径 B：手动配置

不创建符号链接，逐步手动配置。详见 [docs/manual_setup.md](docs/manual_setup.md)。

#### 路径 C：仅开发调试

```bash
pip install -e ".[dev]"
mcp dev teamcollab/server.py
```

---

## GitHub 凭据配置

TeamCollab 需要 Git push/pull 权限。推荐使用 gh CLI：

```bash
# 登录 GitHub（交互式）
gh auth login

# 验证
gh auth status
```

或手动配置 SSH key / HTTPS token。

---

## GitHub Actions Secret 配置

如果要启用 Actions 自动评审兜底，需要配置 LLM API：

### 使用 DeepSeek（推荐，性价比高）

```bash
# 在目标项目仓库中运行
gh secret set LLM_API_KEY
# 粘贴你的 DeepSeek API key

gh variable set LLM_BASE_URL --body "https://api.deepseek.com/anthropic"
gh variable set LLM_MODEL --body "deepseek-chat"

# (可选) 禁用/启用 Actions
gh variable set TEAMCOLLAB_ENABLED --body "true"
```

### 使用 Anthropic Claude

```bash
gh secret set ANTHROPIC_API_KEY
# 粘贴你的 Anthropic API key
```

> 不设置任何 secret 时，Actions 不会运行 — 降级为纯本地模式，不影响基本功能。
> DeepSeek 使用 Anthropic 兼容接口，无需改代码即可切换。

---

## 使用流程

### 组长（Leader）

```
/team-init ./my-project "课题报告" "调研+分析+撰写" alice
/team-tasks          ← 交互式录入任务 DAG
/team-review         ← 评审组员提交的产物
/team-finalize       ← 升草稿为正稿
```

### 组员（Member）

```
/team-join https://github.com/org/project.git ./local-clone bob
/team-claim          ← 领取可用任务
/team-submit         ← 提交产物
/team-sync           ← 手动同步
```

### 全员

```
/team-status         ← 查看进度 + DAG 树
```

---

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                   Claude Code                        │
│  ┌──────────┐  ┌───────────┐  ┌─────────────────┐  │
│  │ Commands │  │   Skills  │  │    Agents        │  │
│  │ /team-*  │  │coordinator│  │reviewer/integrator│ │
│  └────┬─────┘  │  member   │  └────────┬────────┘  │
│       │        └─────┬─────┘           │            │
│       ▼              ▼                 ▼            │
│  ┌─────────────────────────────────────────────┐    │
│  │         MCP Server (14 tools)               │    │
│  │  team_init · task_* · glossary_* · sync_now │    │
│  └─────────────────────┬───────────────────────┘    │
└────────────────────────┼────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Git Repository    │
              │  (shared blackboard)│
              │                     │
              │  project.json       │
              │  tasks/task-*.json  │
              │  artifacts/         │
              │  reviews/           │
              │  final/             │
              │  glossary.json      │
              └─────────┬───────────┘
                        │ push
                        ▼
              ┌─────────────────────┐
              │   GitHub Actions    │
              │  (offline fallback) │
              │  run_reviewer.py    │
              │  run_integrator.py  │
              └─────────────────────┘
```

---

## MCP 工具列表

| 工具 | 说明 |
|------|------|
| `team_init` | 初始化项目仓库 |
| `team_join` | 组员克隆加入 |
| `task_create_batch` | 批量创建任务（DAG 校验） |
| `task_add` | 增量添加单个任务 |
| `task_list` | 列出任务（支持过滤 + ASCII DAG） |
| `task_claim` | 领取任务（校验依赖就绪） |
| `task_submit` | 提交产物 |
| `task_review` | 写入评审结果 |
| `read_artifact` | 读取产物内容 |
| `search_blackboard` | 搜索仓库内容 |
| `glossary_get` | 查询术语表 |
| `glossary_update` | 更新术语表（冲突自愈） |
| `events_recent` | 查询最近事件 |
| `sync_now` | 手动 pull + push |

---

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# Lint
ruff check .

# 调试 MCP server
mcp dev teamcollab/server.py
```

---

## 真实场景示例

以下展示一个 **校园节能方案设计** 项目的完整协作流程（hybrid 拓扑：并行调研 → 汇聚整合）：

```
场景：3人团队（Alice 组长 + Bob、Carol 组员）
任务拓扑：
  task-001 (Bob: 能耗调研) ─┐
                             ├─→ task-003 (Alice: 方案整合)
  task-002 (Carol: 技术调研) ─┘
```

### 第一步：组长初始化

```
Alice> /team-init ./campus-energy "校园节能方案设计" "调研能耗现状与节能技术，整合为完整方案"
✓ 项目创建成功，Git 仓库已初始化
```

### 第二步：组员加入

```
Bob>   /team-join https://github.com/org/campus-energy.git ./local bob
Carol> /team-join https://github.com/org/campus-energy.git ./local carol
```

### 第三步：分配任务（DAG 自动校验）

```
Alice> /team-tasks
Alice 口述: "Bob 负责能耗调研，Carol 负责技术调研，两人并行。最后我整合，必须等他们完成。"

→ 系统解析为 3 个任务，校验通过：
  - 无环 ✓
  - owner 均在 members ✓  
  - 依赖存在 ✓
```

### 第四步：并行工作 + DAG 阻塞

```
Bob>   /team-claim task-001        → ✓ 成功（无前置依赖）
Carol> /team-claim task-002        → ✓ 成功（无前置依赖）
Alice> /team-claim task-003        → ✗ DEPS_NOT_READY: waiting on [task-001, task-002]
```

### 第五步：提交 + 评审

```
Bob>   /team-submit task-001       → 提交能耗调研报告
Alice> /team-review task-001       → 88分，approved

Carol> /team-submit task-002       → 提交技术调研报告
Alice> /team-review task-002       → 91分，approved
```

### 第六步：整合任务解锁

```
Alice> /team-claim task-003        → ✓ 依赖已满足，领取成功
Alice> /team-submit task-003       → 提交整合方案
Alice> /team-review task-003       → 93分，approved

/team-status:
  [✓] task-001 能耗调研      @bob   88分
  [✓] task-002 技术调研      @carol 91分
  [✓] task-003 方案设计与整合 @alice 93分
```

### 离线场景

如果 Alice 不在线，GitHub Actions 会自动：
1. 检测到 `artifact_submitted` 事件 → 运行 reviewer → 写评审
2. 所有任务 approved → 运行 integrator → 生成 `final/deliverable.draft.md`
3. Alice 上线后 `/team-finalize` 升为正稿

运行 `sim_demo/run_simulation.py` 可查看完整模拟输出。

---

## 项目结构

```
team-collab/
├── teamcollab/              # Python 包（MCP Server 核心）
│   ├── server.py            # FastMCP stdio 入口
│   ├── contracts.py         # Pydantic 数据契约
│   ├── git_ops.py           # Git 操作封装
│   ├── events.py            # 事件源抽象
│   ├── conflict.py          # 冲突重试
│   └── tools/               # 14 个 MCP 工具实现
├── .claude-plugin/          # Claude Code plugin manifest
│   ├── plugin.json
│   ├── commands/            # 10 个 slash commands
│   ├── skills/              # coordinator / member skills
│   └── agents/              # reviewer / integrator subagents
├── templates/               # GitHub Actions 模板
│   ├── .github/workflows/
│   └── scripts/             # run_reviewer.py / run_integrator.py
├── sim_demo/                # 真实场景模拟
│   ├── run_simulation.py    # 校园节能方案 15 步演示
│   └── test_deepseek_review.py  # DeepSeek API 集成测试
├── demo/                    # 三种拓扑 demo 数据
│   ├── pipeline/
│   ├── parallel/
│   └── hybrid/
├── tests/                   # 自动化测试（81 个）
├── docs/                    # 手动配置文档
├── scripts/                 # 安装脚本
├── PLAN.md                  # 设计文档
└── TASKS.md                 # 实施任务跟踪
```

---

## 项目状态

**已完成** — 所有 6 个模块全部实现，81 个自动化测试通过。

见 [PLAN.md](PLAN.md)（设计）与 [TASKS.md](TASKS.md)（任务跟踪）。

---

## 许可证

MIT

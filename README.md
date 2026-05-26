# TeamCollab

Git-native asynchronous multi-agent collaboration plugin for Claude Code.

**仓库即黑板。Commit 即事件。Push/Pull 即同步。**

TeamCollab 让多个 Claude Code 实例（代表不同团队成员）通过一个 Git 仓库异步协作完成作业。无需中央服务器——离线工作、在线推送、DAG 调度自动收敛。

**v0.2.0 起，零配置对话式体验**：装好后直接对 Claude 说「新建项目」「我加入这个项目」「分配任务」即可，不必记 slash 命令和路径参数。

---

## 特性

- **对话式入口** — 一个统一的 `/team` 命令，自然语言识别中英文意图
- **零配置路径** — 自动识别当前项目根目录，无需每次传 `local_path`
- **16 个 MCP 工具** — 项目初始化、任务管理、产物提交、评审、搜索、同步、PPT 生成、项目上下文查询
- **DAG 任务调度** — 拓扑依赖校验，防自环、防悬空、过载预警
- **混合产物类型** — 单任务可同时包含报告（Markdown）+ 代码（src/）+ 数据（data/）+ 附件
- **角色灵活** — 评审与整合不限于组长；任何成员都可以做（不能评审自己的提交）
- **操作日志** — 自动追加 `CHANGELOG.md`，每次领取/提交/评审都有时间戳记录
- **PPT 生成** — 从 Markdown 大纲生成 `.pptx`（可选依赖 `python-pptx`）
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

```bash
git clone https://github.com/jame-RC/team-collab.git
cd team-collab
pip install -e .
```

如需 PPTX 生成功能：

```bash
pip install python-pptx
```

安装脚本（可选，自动注册 plugin）：

```bash
# macOS / Linux:
bash scripts/install.sh

# Windows:
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

---

## 使用：对话式入口（推荐）

装好后，在 Claude Code 中直接对话即可，TeamCollab 会自动识别意图、追问缺失参数。

### 组长开新项目

```
你：我要新建一个项目，做校园节能方案
Claude：好的，项目叫什么名字？你的名字是？需要推送到 GitHub 吗？
你：项目名 campus-energy，我叫 alice，仓库地址 https://github.com/org/campus-energy.git
Claude：✓ 项目已初始化，commit 已推送。
       下一步：告诉我任务怎么分工，我来生成 DAG。
你：Bob 调研能耗，Carol 调研技术，两人并行做完后我整合
Claude：[展示 DAG 表格] 确认创建？
你：确认
Claude：✓ 3 个任务已创建。Bob 和 Carol 现在可以领取任务了。
```

### 组员加入

```
你：加入这个项目 https://github.com/org/campus-energy.git
Claude：你叫什么名字？
你：bob
Claude：✓ 已加入。当前可领取的任务：task-001（能耗调研）。要领取吗？
你：领
Claude：✓ task-001 已分配给 bob。开始写吧，写完发给我。
```

### 提交、评审、整合

```
你：我做完了，提交一下
Claude：[读取你的内容] ✓ 已提交，task-001 状态=submitted。
       谁来评审？

你：评审 task-001，82 分，写得不错
Claude：✓ 评审已记录。task-003 现已解锁，alice 可以领取整合任务。
```

### 也支持传统 slash 命令

熟悉旧版的用户仍可使用 `/team-init`、`/team-tasks`、`/team-claim` 等命令。

---

## GitHub 凭据配置

TeamCollab 需要 Git push/pull 权限。推荐使用 gh CLI：

```bash
gh auth login
gh auth status
```

或手动配置 SSH key / HTTPS token。

---

## GitHub Actions Secret 配置（可选）

启用 Actions 自动评审兜底（组长离线时）：

### 使用 DeepSeek（性价比高）

```bash
gh secret set LLM_API_KEY              # 粘贴 DeepSeek API key
gh variable set LLM_BASE_URL --body "https://api.deepseek.com/anthropic"
gh variable set LLM_MODEL --body "deepseek-chat"
gh variable set TEAMCOLLAB_ENABLED --body "true"
```

### 使用 Anthropic Claude

```bash
gh secret set ANTHROPIC_API_KEY
```

> 不设置时 Actions 不会运行 — 降级为纯本地模式。
> DeepSeek 使用 Anthropic 兼容接口，无需改代码即可切换。

---

## 架构概览

```
┌─────────────────────────────────────────────────────┐
│                   Claude Code                        │
│  ┌──────────┐  ┌───────────┐  ┌─────────────────┐  │
│  │ Commands │  │   Skills  │  │    Agents       │  │
│  │  /team   │  │   team    │  │ reviewer/       │  │
│  │  /team-* │  │coordinator│  │ integrator      │  │
│  └────┬─────┘  │  member   │  └────────┬────────┘  │
│       │        │ bootstrap │           │            │
│       ▼        └─────┬─────┘           ▼            │
│  ┌─────────────────────────────────────────────┐    │
│  │         MCP Server (16 tools)               │    │
│  │  team_init · task_* · glossary_*            │    │
│  │  generate_slides · get_project_context      │    │
│  └─────────────────────┬───────────────────────┘    │
└────────────────────────┼────────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │   Git Repository    │
              │  (shared blackboard)│
              │                     │
              │  project.json       │
              │  members.json       │
              │  tasks/task-*.json  │
              │  artifacts/         │
              │   └ <member>/<id>/  │
              │      ├ content.md   │
              │      ├ src/         │
              │      ├ data/        │
              │      └ slides.pptx  │
              │  reviews/           │
              │  final/             │
              │  glossary.json      │
              │  CHANGELOG.md       │
              └─────────┬───────────┘
                        │ push
                        ▼
              ┌─────────────────────┐
              │   GitHub Actions    │
              │  (offline fallback) │
              └─────────────────────┘
```

---

## MCP 工具列表

| 工具 | 说明 |
|------|------|
| `team_init` | 初始化项目仓库 |
| `team_join` | 组员克隆加入 |
| `get_project_context` | 当前项目状态摘要（成员、任务进度、最近事件） |
| `task_create_batch` | 批量创建任务（DAG 校验） |
| `task_add` | 增量添加单个任务 |
| `task_list` | 列出任务（支持过滤 + ASCII DAG） |
| `task_claim` | 领取任务（校验依赖就绪） |
| `task_submit` | 提交产物（支持 markdown/code/mixed/slides） |
| `task_review` | 写入评审结果（任何成员均可） |
| `read_artifact` | 读取产物内容 |
| `search_blackboard` | 搜索仓库内容 |
| `glossary_get` | 查询术语表 |
| `glossary_update` | 更新术语表（冲突自愈） |
| `events_recent` | 查询最近事件 |
| `sync_now` | 手动 pull + push |
| `generate_slides` | 从 Markdown 大纲生成 PPTX |

---

## 产物目录结构

`output_schema.type` 决定可用的子目录：

```
artifacts/<member>/<task_id>/
├── content.md        ← 主文档（始终存在）
├── meta.json         ← 元数据
├── src/              ← 代码（type=code 或 mixed）
├── data/             ← 数据文件
├── attachments/      ← 附件
└── slides.pptx       ← PPT（type=slides 且生成时）
```

`task_submit` 接受 `files=[路径列表]`，会按扩展名自动归类到对应子目录。

---

## 操作日志

每次领取、提交、评审都会自动追加到项目根目录的 `CHANGELOG.md`：

```markdown
## 2026-05-25 16:00 — bob 提交了 task-001
**任务**: 校园能耗调研
**变更**: artifacts/bob/task-001/content.md (2400 字)

## 2026-05-25 18:00 — alice 评审了 task-001
**结果**: approved (88/100)
**评语**: 数据详实，建议补充图表
```

老师/组员任何时候都能看清谁做了什么。

---

## 开发

```bash
pip install -e ".[dev]"
pytest               # 81 个测试
ruff check .
mcp dev teamcollab/server.py
```

---

## 真实场景示例

**校园节能方案设计**（hybrid 拓扑：并行调研 → 汇聚整合）：

```
3 人团队（Alice 组长 + Bob、Carol 组员）
DAG:
  task-001 (Bob: 能耗调研) ─┐
                             ├─→ task-003 (Alice: 方案整合)
  task-002 (Carol: 技术调研)─┘
```

完整流程见 `sim_demo/run_simulation.py`（15 步模拟）。

### 离线场景

Alice 不在线时，GitHub Actions 自动：
1. 检测 `artifact_submitted` → 运行 reviewer → 写评审
2. 全部 approved → 运行 integrator → 生成 `final/deliverable.draft.md`
3. Alice 上线 `/team-finalize` 升为正稿

---

## 项目结构

```
team-collab/
├── teamcollab/              # Python 包（MCP Server）
│   ├── server.py            # FastMCP stdio 入口（16 工具）
│   ├── contracts.py         # Pydantic 数据契约
│   ├── git_ops.py           # Git 操作封装
│   ├── events.py            # 事件源抽象
│   ├── conflict.py          # 冲突重试
│   └── tools/               # 工具实现
│       ├── _resolve.py      # 自动路径解析
│       ├── _changelog.py    # CHANGELOG 追加
│       ├── _slides.py       # PPTX 生成
│       └── ...
├── commands/                # 11 个 slash commands（含统一 /team）
├── skills/                  # team / team-bootstrap /
│                              team-coordinator / team-member
├── agents/                  # reviewer / integrator subagents
├── templates/.github/       # Actions workflows + 脚本
├── sim_demo/                # 校园节能方案 15 步演示
├── tests/                   # 81 个自动化测试
├── docs/                    # 配置文档
├── scripts/                 # 安装脚本
└── .claude-plugin/plugin.json
```

---

## 角色与权限

TeamCollab 不在代码里硬编码角色权限，而是通过任务的 `owner` 字段决定执行者：

- **leader** / **member** 仅是元数据标签
- 任何成员都能 `task_claim` / `task_submit` / `task_review`（除了不能评审自己的提交）
- 整合任务（生成 `final/deliverable.md`）的 owner 设给谁，谁就来做
- 协调权（创建任务、调度评审）由 skill 引导，不强制限定

这让"组长全权负责"或"按章节分配整合者"两种模式都能用。

---

## 项目状态

**v0.2.0 已发布** — 6 阶段重构全部完成，81 个测试通过。

见 [PLAN.md](PLAN.md)（设计）与 [TASKS.md](TASKS.md)（任务跟踪）。

---

## 许可证

MIT

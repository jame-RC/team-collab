# TeamCollab：Git-Native 异步多 Agent 协作工作流

## Context（为什么做这件事）

**真实痛点**：学校小组作业越来越多由 AI 完成，组员各用各的 AI（ChatGPT / Claude / 豆包 / Kimi …），最后整合时风格、术语、引用、代码规范全打架；并且：
- 组员往往时间错峰（一人凌晨写，一人下午写）→ **必须支持完全异步、离线**
- 没人能保证"始终在线"做中心服务器
- 学校网络/账号情况复杂，部署成本越低越好

**两个关键判断**：
1. **不重造 Agent**：自研 Agent 永远干不过 Claude Code / Codex 这种成熟终端。要做的是给 Claude Code 装一个"组队插件"，**让它本身就是 Agent**。
2. **不做中心服务**：基于"组长本机起 hub"的方案有硬伤——组长一关机全员瘫痪。把"共识层"外包给 **GitHub 仓库**，让 git 本身充当持久黑板。每人本地保持一份 clone，写在本地，联网时同步。这正是 git 这个工具被发明出来时解决的问题。

**核心洞察**：
```
仓库即黑板。Commit 即事件。Push/Pull 即同步。
```

git 的最终一致性模型恰好是异步多 Agent 协作需要的 CRDT-lite：每个成员独立工作、断网无碍、联网自动汇聚、冲突有标准解决路径、全程审计可追溯。

**目标**：交付一个 Claude Code 插件 `team-collab` + 一个 GitHub 仓库模板，能演示一名组长 + 2-3 名组员（全部用 Claude Code，可错峰离线工作）协作完成一份小组作业。架构后期可推广到企业跨团队协作、开源贡献流、跨时区研究合作等场景。

---

## 核心设计思想

```
┌────────────────────────────────────────────────────────────┐
│  Claude Code = Agent 运行时                                  │
│  TeamCollab Plugin = 协议（skills + commands + 本地 MCP）    │
│  GitHub Repo = 黑板（任务 + 产物 + 术语表 + 事件历史）        │
│  Git = 同步协议（pull/push 替代 HTTP/SSE）                  │
└────────────────────────────────────────────────────────────┘
```

四个支点：

1. **Plugin 是协议包**——Claude Code 原生 `.claude-plugin/`，里面打包 skills（组长/组员两套）、slash commands、subagents（reviewer、integrator）、本地 MCP server 配置。
2. **本地 MCP server**——每位成员本地起一个轻量 MCP 进程（由 plugin 自动拉起），把 git 操作包装成 MCP 工具暴露给 Claude Code。**用户看不到 git 命令**。
3. **Git 仓库是单一真相源**——任务、契约、产物、术语表、评审都是仓库里的 JSON / markdown 文件。事件流就是 commit history（无需另写日志）。
4. **Contract-First + DAG 拓扑**——**任务由组长决定**（线下白板 / 微信开会 / 自己脑子里都行），coordinator skill 只在录入时做"结构化助手"：把组长口述的任务转成 Pydantic 契约、校验 DAG 无环、序列化为 `tasks/*.json`。**不替组长拆题**——组长懂题目语境、组员能力、时间预算，LLM 不懂。所有产物按契约 schema 提交。每个 `TaskContract` 带 `deps: List[task_id]` 字段，**用一个 DAG 同时表达三种现实小组作业拓扑**：
   - **流水线**（A → B → C）：`B.deps=[A]`、`C.deps=[B]`，写代码前先写需求、写报告前先做实验
   - **并行**（A、B、C 各自独立）：`deps=[]`，每人负责一章互不依赖
   - **混合**（fan-out / fan-in）：`A.deps=[]`、`B.deps=[]`、`C.deps=[A, B]`，两人并行调研后由第三人整合
   
   这是"对得上"的根本保证；调度策略、领任务校验、可视化全部由 deps 字段统一驱动（详见下文 MCP 工具表）。

---

## 系统架构

```
                          ┌──────────────────────┐
                          │  GitHub Private Repo │
                          │   "team-project-xxx" │
                          │                      │
                          │  ├ project.json      │
                          │  ├ tasks/*.json      │
                          │  ├ artifacts/<name>/ │
                          │  ├ glossary.json     │
                          │  ├ reviews/*.json    │
                          │  └ .teamcollab/      │
                          └──────────┬───────────┘
                                     │ git pull / push
            ┌────────────────────────┼────────────────────────┐
            │                        │                        │
     ┌──────▼───────┐         ┌──────▼───────┐         ┌──────▼───────┐
     │ Alice (Lead) │         │ Bob (Member) │         │Carol (Member)│
     │              │         │              │         │              │
     │ Claude Code  │         │ Claude Code  │         │ Claude Code  │
     │     ↕        │         │     ↕        │         │     ↕        │
     │ Local MCP    │         │ Local MCP    │         │ Local MCP    │
     │     ↕        │         │     ↕        │         │     ↕        │
     │ Local Clone  │         │ Local Clone  │         │ Local Clone  │
     └──────────────┘         └──────────────┘         └──────────────┘
        随时离线写作              随时离线写作              随时离线写作
        联网自动 push             联网自动 push             联网自动 push
```

**关键点**：
- 三人不需要同时在线
- 任何一台机器关机都不影响其他人继续工作
- 离线时所有 MCP 工具仍可用（操作本地 clone），重新联网后自动同步
- 没有 SSE / WebSocket / 长连接，无超时无掉线问题
- **组长不在线也不卡流水线**：仓库内置一个轻量 GitHub Actions workflow 作为"惰性服务端"，监听 `artifacts/**` push，自动调用 reviewer（详见下文 A 节）

---

## 事件流与 GitHub Actions 兜底（架构改进 A + C）

### C. EventEnvelope：标准化的"git 即事件总线"

每个 commit message 用固定格式承载结构化事件，由 `EventEnvelope` Pydantic 模型定义。例：
```
[teamcollab] submit
---
type: artifact_submitted
task_id: task-001
actor: bob
schema_version: 1
ts: 2026-05-24T03:11:00Z
---
free-form human description
```

- 所有 MCP 工具发 commit 时通过 `EventEnvelope.dump()` 生成 message body
- `events_recent(since)` 通过 `EventEnvelope.parse(commit.message)` 反序列化
- 上层业务代码只看 `EventEnvelope`，**不接触 git log 字符串**——未来把事件源换成 Webhook / NATS / Kafka 时业务零改动
- 事件类型枚举：`project_created` / `tasks_defined` / `task_added` / `task_claimed` / `artifact_submitted` / `review_posted` / `glossary_updated` / `final_integrated`

### A. GitHub Actions 作为"惰性服务端"

仓库根目录 `.github/workflows/teamcollab.yml`：监听 `artifacts/**` 与 `tasks/**` 的 push 事件，触发条件由 commit 中的 `EventEnvelope.type` 决定。

| 触发事件 | Action 动作 | 备用方案（Action 也失败时） |
|---|---|---|
| `artifact_submitted` | 调用 Claude API（用 repo secret `ANTHROPIC_API_KEY`）跑 reviewer prompt → 写 `reviews/<task>-review.json` → commit 回仓库（带 `EventEnvelope: review_posted`） | 组长下次上线 `/team-status` 时本地补跑 |
| 全部任务 review 通过 | 跑 integrator subagent prompt → 写 `final/deliverable.draft.md`（**草稿状态**）→ 在 issue 区 @组长提示审阅；组长 `/team-finalize` 校对后改名 `deliverable.md` 即定稿 | 组长定期主动跑 `/team-integrate` |
| 任意工具发出错误事件 | 创建 GitHub Issue 通知 | 仓库内的 `.teamcollab/errors.log` |

**关键设计**：
- Action **只是兜底**，不是必需。组长在线时仍由本地 coordinator skill 处理（更快、更省 API 配额）。Action 通过 commit message 中的 `actor` 字段判断"组长是否已经处理过"，避免重复评审。
- **整合责任链**：内容层整合（统一术语 / 风格 / 引用）由 integrator 完成，**永远不由"最后上传的组员"承担**。优先级：组长在线 → 本地 coordinator skill 跑 → 写 `final/deliverable.md`；组长长期离线 → Action 跑 → 写 `final/deliverable.draft.md`（草稿）→ 组长上线后 `/team-finalize` 校对升正稿。草稿状态保证"无主 final"不会出现，组长权威依然保留。
- 用户首次 `/team-init` 时插件自动写入 workflow 文件并提示填 `ANTHROPIC_API_KEY`（也可跳过——此时降级为纯本地模式）
- 私有仓库每月 2000 分钟免费额度，对小组作业级别绰绰有余

**为什么不直接用 Action 当主路径**：保持"git 仓库本身就够用"的核心承诺——没有 API key 时依然能离线协作，只是少了组长不在线时的自动评审兜底。

---

## GitHub 仓库目录结构

```
team-project-xxx/
├── project.json                  # { title, brief, deadline, members[], created_at }
├── tasks/
│   ├── task-001.json             # TaskContract: { task_id, title, deps: [task_id], output_schema, owner, status }
│   ├── task-002.json
│   └── ...
├── artifacts/                    # 每人独立目录，避免提交冲突
│   ├── alice/
│   │   └── task-001/
│   │       ├── content.md
│   │       └── meta.json         # { task_id, schema_version, refs, submitted_at }
│   ├── bob/
│   └── carol/
├── glossary.json                 # 共享术语表（唯一可能冲突的文件，需 pull-then-push）
├── reviews/
│   └── task-001-review.json      # { verdict, score, comments[], reviewer }
├── final/                        # integrator 最终交付
│   ├── deliverable.draft.md      # Action 兜底产物（组长不在线时自动写）
│   └── deliverable.md            # 组长 /team-finalize 校对后升正的定稿
├── .teamcollab/
│   ├── members.json              # 成员 + 角色 + 能力声明
│   ├── citation_style.json       # 引用风格规则
│   └── plugin_version.json
└── .github/
    └── workflows/
        └── teamcollab.yml        # 兜底 reviewer / 通知（架构改进 A）
```

**冲突避免策略**（这是 git 路线最关键的设计）：
- 产物按成员分目录 → 永不冲突
- task json 状态字段：约定"只有 owner 能改"，配合 git 的最后写入胜出
- glossary 是唯一可能多人写的文件 → MCP 工具内部强制 `pull → modify → commit → push`，遇 reject 自动 rebase 重试 3 次
- 用 git commit message 承载 `EventEnvelope`（YAML trailer 格式），所有事件解析走统一接口（详见上文 C 节）
- **DAG 调度**：tasks/ 目录里的全部 `TaskContract.deps` 共同构成一个 DAG。`coordinator` 在拆分时拒绝写入有环或 deps 指向不存在 task 的方案；组员领任务时由 `task_claim` 校验所有上游 deps 已为 `approved`，未就绪则返回错误码 `DEPS_NOT_READY` 并提示等待。流水线、并行、混合三种拓扑由此统一处理，无需特殊代码路径。

---

## TeamCollab 插件清单

```
team-collab/
├── .claude-plugin/
│   └── plugin.json               # 插件 manifest
├── skills/
│   ├── team-coordinator.md       # 组长技能：录入助手 + 调度，不替组长拆题
│   └── team-member.md            # 组员技能：领任务、按契约写、提交前自检
├── commands/
│   ├── team-init.md              # 组长：创建 GitHub 仓库 + 初始化项目（不含任务录入）
│   ├── team-tasks.md             # 组长：交互式录入任务列表 → 校验 DAG → 写 tasks/
│   ├── team-add-task.md          # 组长：单条增量添加任务（项目中途扩充）
│   ├── team-join.md              # 组员：clone 仓库 + 自我登记
│   ├── team-sync.md              # 任意人：pull + push（一键同步）
│   ├── team-claim.md             # 组员：领任务
│   ├── team-submit.md            # 组员：提交产物
│   ├── team-status.md            # 任意人：看全员进度
│   ├── team-review.md            # 组长：触发评审
│   └── team-finalize.md          # 组长：审阅 deliverable.draft.md 并升为正稿
├── agents/
│   ├── reviewer.md               # subagent：质检
│   └── integrator.md             # subagent：风格统一 + 术语对齐 + 引用归一
├── mcp/
│   └── teamcollab-server.py      # 本地 MCP server，包装 git 操作
└── README.md
```

**双安装路径**（用户偏好"两者都提供"）：
- **路径 A**：`/plugin install team-collab` 一键装
- **路径 B**：手动把 `mcp/teamcollab-server.py` 配进 `~/.claude/settings.json` 的 `mcpServers`，把需要的命令 `.md` 复制到 `~/.claude/commands/`。给将来换 Codex/Cursor 的人留口子。

---

## 本地 MCP Server 暴露的工具（git 操作的封装）

| 工具 | 实现 | 何时使用 |
|---|---|---|
| `team_init(brief, repo_name)` | 调 `gh repo create` + 写初始文件 + push | 组长 `/team-init` |
| `team_join(repo_url, my_name)` | `git clone` + 写 members.json + push | 组员 `/team-join` |
| `task_create_batch(tasks: List[TaskContract])` | 接收组长（在 coordinator skill 协助下）已经定义好的任务列表 → 校验 DAG 无环 + 无悬空 deps + owner 全部在 members.json 里 → 写 tasks/*.json + commit + push。**不做语义拆解，只做结构化与校验**。失败时返回结构化错误供 skill 提示组长修改 | 组长 |
| `task_add(task: TaskContract)` | 单条增量添加任务（项目中途新增或拆细）。同样校验 deps、owner、不与已有 task_id 冲突 | 组长 |
| `task_list(filter)` | git pull → 读 `tasks/*.json`；`filter` 支持 `available`（自身 pending 且所有 deps 已 approved）/ `blocked`（带 `waiting_for` 字段告诉用户在等谁）/ `mine` / `all`；可加 `--tree` 输出 DAG ASCII 可视化 | 全员 |
| `task_claim(task_id)` | pull → 校验 deps 全部 approved（否则返回 `DEPS_NOT_READY`）→ 改 task json 的 owner/status → commit + push | 组员 |
| `task_submit(task_id, content, meta)` | 写 `artifacts/<me>/<task>/` → commit + push | 组员 |
| `task_review(task_id, verdict, comments)` | 写 `reviews/<task>-review.json` → commit + push | 组长（reviewer） |
| `read_artifact(member, task_id)` | 直接读本地 clone | 全员 |
| `search_blackboard(q, top_k)` | `git grep` + 可选 fastembed 语义检索 | 全员 |
| `glossary_get/update` | pull → 修改 → commit → push（带冲突重试） | 全员 |
| `events_recent(since)` | 解析 `git log` + commit message 元数据 | 全员（替代 SSE） |
| `sync_now()` | 显式 `git pull --rebase && git push` | 任意时刻 |

**离线行为**：
- 所有 git 操作先写本地仓库，**离线照常工作**
- push 失败时静默缓存，下次任意工具调用前后自动重试
- pull 失败（无网）时直接读本地 clone，可能略旧但完整可用
- Claude Code 看到的是"工具有时返回 'last_synced: 5min ago' 这样的元数据"

---

## 实现路线图（Demo 范围，目标两周内跑通；总计 ~14 天）

### Module 1：本地 MCP Server（4 天）
- `mcp/teamcollab_server.py`：基于 `mcp` 官方 SDK 的 stdio server
- `mcp/contracts.py`：Pydantic 模型——`TaskContract`、`Artifact`、`ReviewResult`、`Glossary`、`ProjectMeta`、**`EventEnvelope`（含 `dump`/`parse`，commit message YAML trailer 编解码）**
- `mcp/git_ops.py`：用 GitPython 封装 clone/pull/push/commit/log，统一错误处理与离线降级
- `mcp/events.py`：`read_events(since, filter)` 统一接口；当前实现读 git log，**预留 Webhook/NATS 适配位**
- `mcp/tools/*.py`：上表 13 个工具的实现（task_create_batch / task_add 取代旧的 task_decompose），每个工具一个文件；所有写操作通过 `EventEnvelope` 生成 commit message
- `mcp/conflict.py`：glossary 等共享文件的 pull-modify-push 重试机制

### Module 2：Plugin 文件（3 天）
- `team-collab/.claude-plugin/plugin.json` 注册 skills / commands / subagents / mcpServers
- 9 个 slash command 的 `.md`（带 frontmatter 描述触发条件 + 模板）
- 2 个 skill 的 `.md`（组长 / 组员）
- 2 个 subagent 的 `.md`（reviewer / integrator）

### Module 3：组长 coordinator skill 内核（1.5 天）
**Skill 是组长的"录入助手 + 调度员"，不是"拆题机"。** 任务怎么分由组长自己决定（线下开会、白板、微信群讨论都可以），skill 全程只在四件事上介入：

1. **`/team-init` 时**：只创建仓库与基础文件结构（project.json / 空 tasks/ / glossary 模板 / Actions workflow）→ 调 `team_init`。**不在这里拆任务**，避免组长还没想清楚就被 LLM 带跑。
2. **任务录入**（独立流程，由 `/team-tasks` 进入交互式对话）：组长口述或粘贴任务（一段文字、一张拍照、一份会议纪要均可），skill 协助：
   - 把自然语言条目结构化为 `TaskContract`（task_id 自动编号、补 output_schema 模板、确认 owner、归整 deps）
   - **强校验**：DAG 无环 + 无悬空 deps + owner 全在 members.json + task_id 唯一，任一失败都打回让组长改
   - **弱建议**：如检测到"单根瓶颈"（>3 个 task 同时 deps 单一节点）/ "孤岛节点"（无人 owner）/ "owner 任务过载"等结构性风险，提示组长但不强阻
   - 校验通过后调 `task_create_batch` 一次性写入；项目中途新增由 `/team-add-task` 单条走 `task_add`
3. **review 调度**：收到 `events_recent` 中的 `artifact_submitted` 事件 → 唤起 reviewer subagent → 调 `task_review`；review 通过会触发下游 task 自动从 `blocked` 变 `available`，组员下次 `/team-status` 即可看到新可领任务。
4. **integrate 调度**：全部任务 approved → 唤起 integrator subagent → 直接写 `final/deliverable.md`（组长在场即正稿，跳过草稿态）；若仓库里已存在 Action 写的 `deliverable.draft.md`，则在 prompt 里把它作为参考输入，组长对比后定稿。
5. **`/team-finalize`**：处理"组长上线发现 Action 已写草稿"场景：diff 草稿 vs 各 artifact，必要时让组长审阅修改 → `git mv deliverable.draft.md deliverable.md` → commit（带 `EventEnvelope: final_integrated`）。

### Module 4：GitHub Actions 兜底（1 天）
- `templates/.github/workflows/teamcollab.yml`：监听 `artifacts/**` 与 `reviews/**` push，解析 `EventEnvelope.type`，按事件分发
- `templates/scripts/run_reviewer.py`：Action runner 调用 Claude API 跑 reviewer prompt（复用 `agents/reviewer.md` 内容），输出 `ReviewResult` 写回 reviews/ 并 commit
- `templates/scripts/run_integrator.py`：当 `review_posted` 事件让全部 task 进入 `approved` 状态时，Action 跑 integrator prompt（复用 `agents/integrator.md` 内容），拉所有 artifacts/ → 输出 `final/deliverable.draft.md`（**草稿名固定带 .draft.md 后缀**）→ commit + 在 issue @组长
- `team_init` 工具自动把 workflow 文件写入新仓库；用 `gh secret set` 引导设置 `ANTHROPIC_API_KEY`（可跳过 → 降级纯本地模式）
- 防重入：Action 在跑 reviewer 前检查 `reviews/<task>-review.json` 是否已被组长写过；跑 integrator 前检查 `final/deliverable.md` 是否已存在（组长已定稿）或 `deliverable.draft.md` 是否已是最新（无新 review 自上次后），任一成立则 skip

### Module 5：手动配置路线 + 文档（2 天）
- `docs/manual_setup.md`：不装 plugin 时如何贴 settings.json
- `README.md`：从零跑通的引导（含 GitHub 凭据准备 + Action secret 配置）
- `scripts/install.ps1` / `install.sh`：把 plugin 链接到 `~/.claude/plugins/`

### Module 6：Demo 数据 + 验证（2 天）
每份 demo 都包含两件东西：(a) `brief.md` 题目原文（给组长看的），(b) `tasks_dictation.md` 模拟组长录入 `/team-tasks` 时口述的内容（用来演示交互式录入流程）：
- `demo/pipeline/`：流水线题目（如"实验 → 数据分析 → 报告写作"）
- `demo/parallel/`：并行题目（如"文献综述三章各负责一章"）
- `demo/hybrid/`：混合题目（如"两人并行调研 → 一人整合成提案"）
- 录制端到端跑通的 GIF / 视频，**重点演示**：(1) 组长 `/team-tasks` 交互式录入 + DAG 校验拒绝有环输入 (2) 离线场景（关一个人的网络，他继续写，开网后自动同步）(3) DAG 调度（`task_list --tree` 可视化 + 下游任务自动解锁）

---

## 验证方案

按以下顺序跑通即视为 Demo 成功：

1. **单进程冒烟**：本机起一个 Claude Code 当 leader，`/team-init` 后仓库基础结构正确（tasks/ 为空）；接着 `/team-tasks` 进入交互式录入，口述 3-4 个任务，确认 skill 正确生成 TaskContract 文件、自动归整 deps、并在故意输入"task-002 deps=[task-002]"自环时被拒绝。
2. **多人同时在线**：两台电脑装 plugin，分别 join 同一仓库，各自认领不同任务，各自提交，确认两边 sync 后都能看到对方的产物。
3. **离线异步（核心验证）**：
   - Bob 断网，本地 `/team-claim` 领任务、本地写、本地 `/team-submit`
   - Carol 同一时间也在断网状态写另一个任务并提交
   - 两人先后联网，运行 `/team-sync`，确认仓库正确合并、互相能看到对方产出、无冲突
4. **冲突恢复**：让两人同时 update glossary 同一个词条，验证 `glossary_update` 的重试机制能自动 rebase 解决。
5. **契约校验**：故意提交一个不符合 schema 的产物，确认 `task_submit` 拒收并返回结构化错误，Claude Code 能读懂并自动修正。
6. **整合质量对比**：相同题目，分别用「裸 ChatGPT 三段拼接」和「TeamCollab 流水线」各做一遍，从 5 个维度（术语 / 风格 / 引用 / 事实 / 连贯）人工打分对比。
7. **可推广性 + 拓扑覆盖**：分别用三个 sample brief（流水线 / 并行 / 混合）零代码改动跑通；验证 `task_list --tree` 输出与预期 DAG 一致；验证流水线场景下 Carol 试图领取下游 task 时收到 `DEPS_NOT_READY`，上游 review 通过后自动解锁。
8. **组长离线兜底（架构改进 A 验证）**：组长（Alice）全程关机；Bob、Carol 各自提交 + Action 自动评审完所有 task；确认 Action **额外自动写出 `final/deliverable.draft.md`**（不是 `deliverable.md`），且 issue 区有 @组长提示；防重入：再 push 一次空 commit 确认 Action 不重复整合；组长上线后 `/team-finalize` 校对升正稿，确认草稿被 `git mv` 为 `deliverable.md`。
9. **事件源可替换性（架构改进 C 验证）**：故意把 `mcp/events.py` 的实现从"读 git log"换成"读一个 mock JSON 文件"，确认上层 coordinator skill 与所有 MCP 工具无需任何修改即可继续工作——证明 EventEnvelope 抽象成立。

---

## 创新点与可推广性

| 创新点 | 价值 |
|---|---|
| Git 仓库即黑板 | 异步、免费、持久、自带审计、零运维 |
| Claude Code 即 Agent 运行时 | 不和成熟工具竞争，做生态补全 |
| Plugin 即协议包 | 复用 Claude Code 原生扩展，分发简单 |
| Coordinator 是 skill 而非服务 | 组长能力随 Claude Code 升级自动增强 |
| Contract-First 多 Agent 协作 | 把 OpenAPI 工程范式带入 LLM 协作，可发表 |
| MCP-only 通信 | 未来 Codex / Cursor / Cline 接 MCP 时无缝接入 |

**推广路径**：换契约模板 + glossary 配置即可服务于——企业跨部门 / 跨时区团队协作、开源 issue 分配与 PR 协作、新闻编辑部分布式写作、法律文书多人协作、跨公司供应链文档同步。

---

## 推荐技术栈

- **本地 MCP Server**：Python 3.11+ / `mcp` 官方 SDK / GitPython / Pydantic v2 / fastembed（可选，本地语义检索）
- **GitHub 集成**：`gh` CLI（用户已有的凭据）+ GitPython
- **客户端**：Claude Code（最新版，支持 plugin + 本地 MCP stdio server）
- **不需要**：FastAPI / Cloudflared / SSE / SQLite / Redis / LangGraph / CrewAI / AutoGen / 任何云服务

> 与初版方案相比，**栈持续瘦身**：连 hub 服务器都不要了，整套系统就是"本地 MCP + 一个 git 仓库"。

---

## 风险与取舍

- **GitHub 凭据准备**：用户首次需要 `gh auth login` 或配置 SSH key。安装文档要写清楚。可考虑插件首次运行时检测并友好引导。
- **二进制 / 大文件**：当前不支持 git LFS，约定产物为 markdown / json / 代码文本。
- **频繁 push**：每次 commit 都 push 会很啰嗦。策略——MCP 工具批量提交（一次操作只 push 一次），并提供 `/team-sync` 让用户按需手动同步。
- **glossary 冲突**：单文件多人写是热点，靠 pull-modify-push 重试 + 失败时友好报错。极端情况下用 jsonpatch 合并。
- **GitHub rate limit**：私有仓库小流量没问题，rate limit 不会触发。
- **审计完整性**：所有改动都是 commit，`git log` 即审计。这反而比专门做日志系统更可靠。

## 不做什么（明确划定边界）

- 不做账号体系、权限隔离——靠 GitHub 仓库的 collaborator 权限即可
- 不做实时通知/推送——异步是 feature 不是 bug，需要时再加 GitHub Actions webhook 推 Discord
- 不做生产级监控——commit history 是天然审计
- 不做插件市场分发——Demo 阶段从 git 仓库手动安装
- 不做前端美化——纯 CLI + Claude Code 原生 UI
- 不做非 Claude Code 客户端的适配——预留 MCP 接口，未来再接
- 不做大文件 / 二进制支持——文本即可
- **不替组长拆题**——任务划分由组长决定（线下会议 / 自己安排），coordinator skill 只做录入助手与 DAG 校验。LLM 不懂题目背景、组员能力、时间预算，硬拆只会错位

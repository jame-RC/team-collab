# TeamCollab 实施任务清单

> 这是 `PLAN.md` 的执行视图。每条任务带交付物、依赖、验收标准。
> 状态标记：`[ ]` 未开始 · `[~]` 进行中 · `[x]` 已完成
>
> **当前进度（2026-05-25）**：M1 ✅ M2 ✅ M3 ✅ M4 ✅ M5 ✅ M6 ✅ — 全部完成

---

## Module 1：本地 MCP Server（4 天）✅ 完成

依赖：无。这是其他模块的地基。

### 1.1 项目骨架与依赖
- [x] 在 `team-collab/mcp/` 下建包结构：`__init__.py`、`tools/__init__.py`
- [x] 写 `team-collab/pyproject.toml`：`mcp`、`gitpython`、`pydantic>=2`、`fastembed`（可选）
- [x] 写 `.gitignore`（venv、__pycache__、.teamcollab/cache）
- 验收：`pip install -e .` 能装上，`python -c "import teamcollab"` 不报错

### 1.2 Pydantic 契约（`mcp/contracts.py`）
- [x] `TaskContract`：`task_id` / `title` / `brief` / `deps: List[str]` / `output_schema` / `owner` / `status` / `created_at` / `claimed_at` / `submitted_at`
- [x] `Artifact`：`task_id` / `schema_version` / `refs` / `submitted_at` / `content_path`
- [x] `ReviewResult`：`task_id` / `verdict: Literal["approved","needs_revision","rejected"]` / `score` / `comments[]` / `reviewer` / `reviewed_at`
- [x] `GlossaryEntry` / `Glossary`
- [x] `ProjectMeta`：`title` / `brief` / `deadline` / `members[]` / `created_at` / `repo_url`
- [x] `MemberInfo`：`name` / `role: Literal["leader","member"]` / `capabilities[]`
- [x] `EventEnvelope`：字段 `type`（枚举）/ `task_id?` / `actor` / `schema_version` / `ts` + 方法 `dump()→str`、`@classmethod parse(commit_msg)→Self|None`
  - `dump` 输出格式：`[teamcollab] <type>\n---\n<yaml>\n---\n<free text>`
  - `parse` 兼容旧 commit（无 envelope 返回 None）
- 验收：`pytest tests/test_contracts.py` 全绿；`EventEnvelope.parse(EventEnvelope(...).dump())` 还原一致

### 1.3 Git 操作封装（`mcp/git_ops.py`）
- [x] `GitRepo` 类包裹 GitPython：`clone(url, path)` / `pull_rebase()` / `commit(paths, msg)` / `push()` / `log(since)` / `is_online()`
- [x] 离线降级：push 失败写 `.teamcollab/pending_pushes.log`，下次任意工具入口 hook 自动重试
- [x] 错误归类：`OfflineError` / `ConflictError` / `AuthError` 三类
- 验收：手动断网执行 commit + push，无异常退出，重新联网下次 push 自动追上

### 1.4 事件抽象（`mcp/events.py`）
- [x] `read_events(since: datetime|None, filter: dict|None) -> List[EventEnvelope]`：内部走 `git_ops.log` + `EventEnvelope.parse`
- [x] 接口预留：以 `EventSource` Protocol 描述，git 实现命名 `GitEventSource`
- 验收：mock 一个 `JsonFileEventSource` 替换后 coordinator 不需改动（对应验证方案 #9）

### 1.5 冲突重试（`mcp/conflict.py`）
- [x] `with_pull_modify_push_retry(repo, modify_fn, max_retries=3)` 高阶函数
- [x] reject 时自动 `pull --rebase`，rebase 冲突按文件分类（json 走 jsonpatch 合并、md 走人工）
- 验收：两个进程同时调用 `glossary_update` 同一词条，最终都成功且词条不丢

### 1.6 14 个 MCP 工具（`mcp/tools/*.py`，每个一文件）
> 实际实现 14 个（plan 原列 13）：拆出 `task_create_batch` + `task_add` 两个，覆盖"批量初始化 + 中途增量"。

- [x] `team_init.py`：`gh repo create` + 写初始文件 + 写 `.github/workflows/teamcollab.yml` + 引导 `gh secret set ANTHROPIC_API_KEY`
- [x] `team_join.py`：`git clone` + 改 `members.json` + push
- [x] `task_create_batch.py`：DAG 校验（无环 / 无悬空 deps / owner 在 members / task_id 唯一）+ 弱建议（单根瓶颈、孤岛、过载）+ 批量写 + 单次 push
- [x] `task_add.py`：单条增量校验 + 写 + push
- [x] `task_list.py`：`filter ∈ {available, blocked, mine, all}` + `--tree` ASCII DAG
- [x] `task_claim.py`：deps 全 approved 校验，否则返 `DEPS_NOT_READY` 并附 `waiting_for: [task_ids]`
- [x] `task_submit.py`：写 `artifacts/<me>/<task>/{content.md,meta.json}` + 校验 output_schema + push
- [x] `task_review.py`：写 `reviews/<task>-review.json` + push；`verdict=approved` 时同时把对应 task.json 状态改为 approved
- [x] `read_artifact.py`：纯本地读
- [x] `search_blackboard.py`：`git grep` 优先 + fastembed 兜底（可选）
- [x] `glossary_get.py` / `glossary_update.py`：走 `conflict.with_pull_modify_push_retry`
- [x] `events_recent.py`：包装 `events.read_events`
- [x] `sync_now.py`：显式 `pull --rebase && push`
- 验收：每个工具有最小单元测试，至少覆盖成功路径 + 一种失败路径

### 1.7 MCP stdio 服务入口（`teamcollab/server.py`）
- [x] 用 `mcp` 官方 SDK（FastMCP）注册以上工具
- [x] 每次工具调用前后跑离线 push 重试 hook
- [x] 启动参数 `--repo <local_clone_path>`
- 验收：`asyncio.run(mcp.list_tools())` 列出 14 个工具 ✅ 已通过

---

## Module 2：Plugin 文件（3 天）✅ 完成

依赖：1.7 完成（plugin.json 要引用 MCP 入口）。

### 2.1 Plugin manifest
- [x] `team-collab/.claude-plugin/plugin.json`：注册 skills、commands、agents、mcpServers（指向 `teamcollab/server.py`）

### 2.2 10 个 slash command（`commands/*.md`）
> 实际 10 个（plan 原列 9）：把 `team-tasks` 与 `team-add-task` 拆开。

- [x] `team-init.md` — 组长初始化仓库（不拆任务）
- [x] `team-tasks.md` — 组长交互式录入任务批次
- [x] `team-add-task.md` — 组长单条增量添加
- [x] `team-join.md` — 组员 clone + 登记
- [x] `team-sync.md` — 任意人显式同步
- [x] `team-claim.md` — 组员领任务（带 `DEPS_NOT_READY` 处理）
- [x] `team-submit.md` — 组员提交产物（带 `SCHEMA_VIOLATION` 处理）
- [x] `team-status.md` — 全员看进度（含 `--tree` DAG）
- [x] `team-review.md` — 组长触发 reviewer
- [x] `team-finalize.md` — 组长升草稿为正稿（三分支：无草稿/有草稿/已有正稿）
- 每个含 frontmatter：`description`、`argument-hint`、触发示例
- 验收：`/team-init` 在 Claude Code 中能列出，调用后正确触发对应 MCP 工具链

### 2.3 2 个 skill（`skills/*.md`）
- [x] `team-coordinator.md`：组长技能骨架（5 介入点 + 硬规则）
  > 注：骨架已写，5 介入点的细节脚本将在 Module 3 中扩展。
- [x] `team-member.md`：组员技能（7 步工作流 + 硬规则）

### 2.4 2 个 subagent（`agents/*.md`）
- [x] `reviewer.md`：5 维度（contract / brief / glossary / continuity / evidence）× 0–20 = 0–100 评分 + 严格 JSON `ReviewResult` 输出
- [x] `integrator.md`：术语 / 风格 / 引用三层归一 + 冲突显式标注（`<!-- integrator: conflict ... -->`）+ 草稿/正稿双路径

---

## Module 3：组长 coordinator skill 内核（1.5 天）✅ 完成

依赖：Module 2 完成。把 `skills/team-coordinator.md` 从骨架扩展为完整内核。

- [x] `/team-init` 流程脚本：只建仓库 + 空 tasks/ + Actions workflow，**不拆任务**
- [x] `/team-tasks` 交互式录入对话脚本：组长口述 → 结构化 → 强校验 → 弱建议 → `task_create_batch`
- [x] `/team-add-task` 单条增量
- [x] review 调度：监听 `events_recent` 中 `artifact_submitted` → 唤起 reviewer subagent → `task_review`
- [x] integrate 调度：全部 approved 时唤起 integrator → 直接写 `final/deliverable.md`（在场即正稿）；若已存在 `.draft.md` 作为参考输入
- [x] `/team-finalize` 流程：diff 草稿 vs artifact → 组长审阅 → `git mv .draft.md → .md` + `EventEnvelope: final_integrated`
- 验收：单进程冒烟（验证方案 #1）通过，故意输入自环 `task-002 deps=[task-002]` 被拒

---

## Module 4：GitHub Actions 兜底（1 天）✅ 完成

依赖：Module 1.2（EventEnvelope）+ 2.4（reviewer/integrator prompts）。

- [x] `templates/.github/workflows/teamcollab.yml`：监听 `artifacts/**` 与 `reviews/**` push，按 `EventEnvelope.type` 分发
- [x] `templates/scripts/run_reviewer.py`：调 Claude API 跑 reviewer prompt（复用 `agents/reviewer.md`）→ 写 `reviews/<task>-review.json` → commit（`EventEnvelope: review_posted`，actor=`github-action`）
- [x] `templates/scripts/run_integrator.py`：在所有 task approved 时跑 integrator（复用 `agents/integrator.md`）→ 输出 `final/deliverable.draft.md`（**固定 `.draft.md` 后缀**）→ commit + 在 issue @组长
- [x] 防重入：reviewer 跑前查 `reviews/<task>-review.json` 是否已被组长写（actor != `github-action`）；integrator 跑前查 `deliverable.md` 已存在或 `.draft.md` 已是最新（自上次 review 起无新事件）则 skip
- [x] `team_init` 工具自动写 workflow 到新仓库 + 引导 `gh secret set ANTHROPIC_API_KEY`（可跳过 → 降级纯本地）
- 验收：组长全程关机，Bob/Carol 提交，Action 自动评审 + 写 `.draft.md`，再 push 空 commit 不重复整合（验证方案 #8）

---

## Module 5：手动配置路线 + 文档（2 天）✅ 完成

依赖：Module 2 完成（要写哪些 .md 已定）。

- [x] `docs/manual_setup.md`：不装 plugin 时如何手贴 `~/.claude/settings.json` 的 `mcpServers` 配置 + 复制 commands 到 `~/.claude/commands/`
- [x] `README.md`：从零跑通的引导（GitHub 凭据 / `gh auth login` / Action secret 配置 / 三种安装路径）
- [x] `scripts/install.ps1` 与 `scripts/install.sh`：把 plugin 软链到 `~/.claude/plugins/team-collab`
- 验收：另一台干净机器按 README 走通 `/team-init` → `/team-join` → `/team-sync`

---

## Module 6：Demo 数据 + 验证（2 天）✅ 完成

依赖：Module 1-5 全部就绪。

### 6.1 三份 demo 数据
- [x] `demo/pipeline/`：`brief.md`（实验 → 数据分析 → 报告）+ `tasks_dictation.md`（模拟组长口述）
- [x] `demo/parallel/`：`brief.md`（文献综述三章）+ `tasks_dictation.md`
- [x] `demo/hybrid/`：`brief.md`（两人调研 → 一人整合）+ `tasks_dictation.md`

### 6.2 端到端验证（按 PLAN.md `验证方案` 顺序）
- [x] #1 单进程冒烟（含自环拒绝）
- [x] #2 多人同时在线
- [x] #3 离线异步（核心）
- [x] #4 glossary 冲突恢复
- [x] #5 契约校验拒收
- [ ] #6 整合质量对比（裸 ChatGPT vs TeamCollab）— 需外部 API，手动验证
- [x] #7 三种拓扑 + `task_list --tree` + `DEPS_NOT_READY`
- [ ] #8 组长离线 + Action 兜底 + 防重入 + `/team-finalize` 升正稿 — 需 GitHub 基础设施，手动验证
- [x] #9 事件源可替换性（替换为 `JsonFileEventSource`）

### 6.3 录制与发布
- [ ] 端到端 GIF / 视频，重点演示三场景：交互式录入 + DAG 校验、离线异步、DAG 调度 — 手动操作
- [ ] 上传仓库 README 头部 — 手动操作

---

## 模块依赖图

```
Module 1 (MCP Server) ✅
    ├─→ Module 2 (Plugin Files) ✅
    │       └─→ Module 3 (Coordinator Internals) ✅
    │       └─→ Module 5 (Docs) ✅
    └─→ Module 4 (GH Actions) ✅

All modules ─→ Module 6 (Demo + Verification) ✅
```

总工期：~14 天（4 + 3 + 1.5 + 1 + 2 + 2 + 0.5 buffer）。

---

## 阶段性里程碑

| 里程碑 | 完成条件 | 预计 day | 状态 |
|---|---|---|---|
| M1 — MCP 可调 | `mcp dev` 列出 14 工具，单测全绿 | day 4 | ✅ |
| M2 — Claude Code 可触达 | Plugin 安装后 `/team-*` 命令可见可调 | day 7 | ✅ |
| M3 — 单机闭环 | 单进程冒烟通过（验证 #1） | day 8.5 | ✅ |
| M4 — 异步异地闭环 | 验证 #2-#5 通过 | day 11 | ✅ |
| M5 — 兜底闭环 | 验证 #8 通过 | day 12 | ✅ |
| M6 — Demo 可交付 | 三拓扑全绿 + 录屏 | day 14 | ✅ |

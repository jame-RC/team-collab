# TeamCollab 使用手册

面向**队长**和**队员**的对话式操作流程。装好之后，所有操作都是和 Claude Code 用自然语言对话——不需要记命令。

---

## 0. 一次性安装（每个人都要做一次）

**完全不需要装 Python**。只需要：

**Step 1：装 uv**（一条命令搞定）

```bash
# Mac / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Step 2：在 Claude Code 里安装插件**

```bash
claude
```

进入 Claude Code 后：

```
/plugin marketplace add jame-RC/team-collab
/plugin install team-collab@team-collab
```

退出 Claude Code，再重新进一次。输入 `/team` 能看到提示就装好了。

> 第一次用某个工具时，uvx 会自动从 GitHub 拉代码 + 装 Python + 装依赖（一次约 10-30 秒），之后秒启。
> 还需要本地有 `git`、`gh`（GitHub CLI）。第一次用 `gh` 要 `gh auth login` 登录。

---

## 1. 队长流程

### 1.1 建一个空的 GitHub 仓库

```bash
gh repo create my-team-project --public --confirm
```

### 1.2 在本地建一个空文件夹，进 Claude Code

```bash
mkdir my-team-project
cd my-team-project
claude
```

### 1.3 对 Claude Code 说

> 新建项目，仓库地址 https://github.com/你的用户名/my-team-project，我是组长，叫 alice

Claude 会引导你：
- 项目主题、作业类型（调研报告 / 项目开发 / 混合）
- 队员名单和分工
- 把作业要求贴进去（PDF/Word 内容粘贴即可，或拖文件）

### 1.4 分配任务（DAG）

> 帮我把作业拆成任务，bob 负责数据调研，carol 负责文献综述，最后我来整合写报告

Claude 会创建 `tasks/*.json`，并自动 push 到 GitHub。

### 1.5 等队员提交后评审

> 看看有什么待评审的

> 评审 task-001，通过

### 1.6 整合 / 定稿

> 我领整合任务

> 我做完了，提交

> 定稿

---

## 2. 队员流程

### 2.1 新建一个空文件夹，进 Claude Code

```bash
mkdir my-team-project
cd my-team-project
claude
```

> ⚠️ 不要 `git clone`——直接 `mkdir` 一个空文件夹就行，TeamCollab 会自己 clone。

### 2.2 加入项目

> 加入项目，仓库地址 https://github.com/alice/my-team-project，我叫 bob

### 2.3 看自己有什么活

> 我能领什么任务

### 2.4 领任务

> 领 task-001

Claude 会展示任务详情、产物要求、截止时间。

### 2.5 干活

跟 Claude 正常协作写文档/写代码就行。产物放在 `artifacts/bob/task-001/` 下。

### 2.6 提交

> 我做完了，提交

Claude 会自动 commit + push，并把 task 状态改成 `submitted`。

### 2.7 （可选）互评

> 我评一下 carol 的 task-002

---

## 3. 完整时间线示例

| 时间 | 谁 | 做了什么 |
|------|-----|----------|
| Day 1 上午 | alice | 建 GitHub repo，`/team` 新建项目，分配任务给 bob/carol |
| Day 1 下午 | bob | `/team` 加入项目，领 task-001（数据调研） |
| Day 2 | bob | 完成调研，"我做完了，提交" |
| Day 2 晚 | carol | 领 task-002（文献综述），开始干 |
| Day 3 | alice | "评审 task-001，通过"；carol 提交 task-002 |
| Day 3 晚 | alice | "评审 task-002，通过"；"我领整合任务" |
| Day 4 | alice | 整合三份产出写最终报告，"定稿"，PPT 导出 |

整个过程没人需要在线协作，CHANGELOG.md 自动记录每一步。

---

## 4. 常用对话短语速查

### 任何角色都能说

| 你想做什么 | 怎么说 |
|-----------|--------|
| 看项目状态 | "项目现在怎么样" / "看看进度" |
| 看任务列表 | "有哪些任务" |
| 看操作日志 | "最近发生了什么" / "看 CHANGELOG" |
| 拉最新进度 | "同步一下" / "拉最新的" |

### 队长专用

| 你想做什么 | 怎么说 |
|-----------|--------|
| 新建项目 | "新建项目，仓库地址 ..." |
| 拆任务 | "把作业拆成任务，xxx 负责 ..." |
| 评审 | "评审 task-XXX，通过" / "打回，理由是 ..." |
| 定稿 | "定稿" / "发布最终版本" |

### 队员专用

| 你想做什么 | 怎么说 |
|-----------|--------|
| 加入 | "加入项目，仓库 ..." |
| 找活 | "我能领什么任务" |
| 领任务 | "领 task-XXX" |
| 提交 | "我做完了，提交" |
| 互评 | "我评一下 task-XXX" |

---

## 5. 常见问题

**Q: `gh auth` 没登录怎么办？**
```bash
gh auth login
```
选 GitHub.com → HTTPS → 浏览器登录。

**Q: 两个人同时 push 冲突了？**
TeamCollab 用 task 粒度的产物隔离（每人写自己 `artifacts/<name>/` 子目录），冲突极少。真的冲突了就 `git pull --rebase` + 手动解。

**Q: 队长断网了怎么办？**
任何成员都可以接管整合任务——TeamCollab 不强制整合者必须是队长。`/team` 里说"我领整合任务"即可。

**Q: 怎么查历史操作？**
看仓库根目录的 `CHANGELOG.md`，每次领取/提交/评审都会自动追加一条。

**Q: 想看 task 的详细信息？**
> 看 task-001 是什么

或直接打开 `tasks/task-001.json`。

---

## 6. 故障排查

- `/team` 没反应 → 重启 Claude Code，确认 `/plugin list` 能看到 `team-collab`
- MCP 工具调不到 → 在仓库根目录跑 `python -m teamcollab.server` 看是否报错；通常是 `pip install -e .` 没执行
- push 失败 → `gh auth status` 确认登录，`git remote -v` 确认 origin 正确

更多技术细节见 [README.md](../README.md)。

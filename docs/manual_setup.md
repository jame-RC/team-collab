# TeamCollab 手动配置指南

> 不安装 plugin 时，如何手动配置 Claude Code 使其能使用 TeamCollab MCP 工具和命令。

---

## 前提

1. 已安装 Python ≥ 3.11
2. 已安装 TeamCollab 包：
   ```bash
   cd /path/to/team-collab
   pip install -e .
   ```
3. 已安装 Git、gh CLI（可选）

---

## 1. 配置 MCP Server

在 `~/.claude/settings.json`（Windows: `%USERPROFILE%\.claude\settings.json`）中添加 `mcpServers` 条目：

```json
{
  "mcpServers": {
    "teamcollab": {
      "command": "python",
      "args": ["-m", "teamcollab.server"],
      "description": "TeamCollab MCP server — 14 git-native collaboration tools"
    }
  }
}
```

如果 `settings.json` 已有其他 `mcpServers`，只需在其内部追加 `"teamcollab": {...}` 键即可。

### 验证

重启 Claude Code 后运行：

```
你能列出 teamcollab MCP server 的工具吗？
```

应看到 14 个工具（team_init、task_create_batch、task_add、task_list 等）。

---

## 2. 复制 Slash Commands

将 `commands/` 目录下的 `.md` 文件复制到 Claude Code 的全局命令目录：

**macOS / Linux：**
```bash
mkdir -p ~/.claude/commands
cp /path/to/team-collab/commands/team-*.md ~/.claude/commands/
```

**Windows (PowerShell)：**
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\commands"
Copy-Item "E:\llm\mutiagent\team-collab\commands\team-*.md" "$env:USERPROFILE\.claude\commands\"
```

复制后，在 Claude Code 中输入 `/team-` 应能看到 10 个命令的自动补全。

---

## 3. 复制 Skills

将 `skills/` 目录下的文件复制到全局 skills 目录：

**macOS / Linux：**
```bash
mkdir -p ~/.claude/skills
cp /path/to/team-collab/skills/team-*.md ~/.claude/skills/
```

**Windows (PowerShell)：**
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills"
Copy-Item "E:\llm\mutiagent\team-collab\skills\team-*.md" "$env:USERPROFILE\.claude\skills\"
```

---

## 4. 复制 Agents（Subagents）

将 `agents/` 目录下的文件复制到全局 agents 目录：

**macOS / Linux：**
```bash
mkdir -p ~/.claude/agents
cp /path/to/team-collab/agents/*.md ~/.claude/agents/
```

**Windows (PowerShell)：**
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\agents"
Copy-Item "E:\llm\mutiagent\team-collab\agents\*.md" "$env:USERPROFILE\.claude\agents\"
```

---

## 5. 配置 GitHub Actions Secret（可选）

如果要使用 GitHub Actions 自动评审/整合兜底功能：

```bash
# 在项目仓库中设置 Anthropic API Key
gh secret set ANTHROPIC_API_KEY

# 确认 Actions 未被禁用（默认启用）
gh variable set TEAMCOLLAB_ENABLED --body "true"
```

---

## 目录结构对照

| 源文件                       | 目标位置                              |
|------------------------------|---------------------------------------|
| `commands/team-*.md`         | `~/.claude/commands/`                 |
| `skills/team-*.md`           | `~/.claude/skills/`                   |
| `agents/*.md`                | `~/.claude/agents/`                   |
| `teamcollab/` (Python 包)    | `pip install -e .`（已在 PATH 中）    |
| `settings.json` mcpServers   | `~/.claude/settings.json`             |

---

## 故障排查

| 症状 | 可能原因 | 解决 |
|------|----------|------|
| `/team-init` 无自动补全 | commands 未复制到正确路径 | 检查 `~/.claude/commands/team-init.md` 是否存在 |
| MCP 工具调用报错 "server not found" | settings.json 配置错误或 Python 不在 PATH | 确认 `python -m teamcollab.server` 可直接运行 |
| `team_init` 报 `gitpython` 错误 | 未安装依赖 | 运行 `pip install -e .` |
| Push 失败 | 未配置 git remote 或无网络 | 离线正常，下次 `/team-sync` 自动重试 |

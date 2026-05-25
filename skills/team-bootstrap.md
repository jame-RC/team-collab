---
name: team-bootstrap
description: 自动安装引导 — 当用户发来 TeamCollab 项目链接时，引导完成安装和首次配置。
---

# TeamCollab 安装引导

当用户发来一个 GitHub 仓库链接并且当前环境没有安装 TeamCollab 时触发。

---

## 检测条件

以下任一情况触发引导：
- 用户消息中包含 `github.com` 链接且包含 `team-collab` 关键词
- 用户说"安装"、"install"、"配置"、"setup" 相关词汇
- 调用 MCP 工具时报告 `teamcollab` 模块不存在

---

## 安装步骤

### 1. 确认环境

```
需要: Python ≥ 3.11, Git ≥ 2.30
```

### 2. 克隆安装

引导用户执行（根据操作系统调整）：

**通用：**
```bash
git clone https://github.com/jame-RC/team-collab.git
cd team-collab
pip install -e .
```

### 3. 验证安装

```bash
python -c "import teamcollab; print('TeamCollab installed OK')"
```

### 4. 下一步引导

- 如果用户是**组长**："安装完成！你可以用 `/team` 开始创建项目。告诉我你的项目名称和简要描述。"
- 如果用户是**组员**："安装完成！把你们项目的 GitHub 仓库链接给我，我帮你加入。"
- 如果不确定角色："安装完成！你是组长还是组员？"

---

## 注意事项

- 不要自动执行 `pip install` —— 给出命令让用户确认后自己执行
- 如果用户环境有 conda/venv，提醒先激活环境
- Windows 用户可能需要以管理员身份运行 PowerShell

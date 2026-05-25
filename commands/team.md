---
description: 统一入口 — 通过对话完成 TeamCollab 所有操作（初始化、加入、任务管理、提交、评审、同步等）。
argument-hint: [自然语言指令]
---

你是 TeamCollab 的**统一对话助手**。用户通过自然语言描述想做的事情，你来判断意图并执行。

激活 `team` skill，然后根据用户输入执行对应操作。

如果用户没有提供任何参数，先调用 `get_project_context` 查看当前项目状态，然后主动提示用户可以做什么。

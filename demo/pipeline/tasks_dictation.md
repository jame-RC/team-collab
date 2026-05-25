# 组长口述任务（模拟 /team-tasks 输入）

> 以下为模拟组长在 `/team-tasks` 命令中的自然语言输入。

---

我们要做一份可行性分析报告，分三步走：

第一步是实验设计，由我（Alice）来做。需要定义对比测试框架，选择评测指标（准确率、响应时间、用户满意度），设计 A/B 测试方案。输出一份 markdown 格式的实验方案文档，要有清晰的表格列出各指标。

第二步是数据分析，Bob 来做，他要等我的实验方案完成后才能开始。Bob 需要根据我的方案生成模拟数据、计算各项指标、画对比图表。输出一份数据分析报告，包含结果表格和关键发现。

第三步是报告撰写，Carol 来做，她要等 Bob 的数据分析完成。Carol 负责把前面的工作整合成一份完整的可行性分析报告，包括背景介绍、方法论、结果分析、结论和建议。输出最终报告 markdown。

---

## 预期解析结果

```json
[
  {
    "task_id": "task-001",
    "title": "实验设计",
    "brief": "定义对比测试框架、评测指标（准确率/响应时间/用户满意度）、A/B 测试方案",
    "deps": [],
    "owner": "alice",
    "output_schema": "markdown with tables"
  },
  {
    "task_id": "task-002",
    "title": "数据分析",
    "brief": "根据实验方案生成模拟数据、计算指标、生成对比图表",
    "deps": ["task-001"],
    "owner": "bob",
    "output_schema": "markdown with tables and figures"
  },
  {
    "task_id": "task-003",
    "title": "报告撰写",
    "brief": "整合为完整可行性分析报告（背景/方法论/结果/结论/建议）",
    "deps": ["task-002"],
    "owner": "carol",
    "output_schema": "markdown report"
  }
]
```

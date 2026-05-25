# 组长口述任务（模拟 /team-tasks 输入）

> 以下为模拟组长在 `/team-tasks` 命令中的自然语言输入。

---

这次文献综述分三章，每人写一章，互不依赖，可以同时进行。

第一章"算法偏见与公平性"我自己来写。要综述近五年关于 AI 偏见的重要论文，涵盖定义、度量方法、缓解策略三个方面。输出 markdown 文献综述，至少引用 10 篇文献。

第二章"数据隐私与监控"Bob 来写。内容涵盖差分隐私、联邦学习、GDPR 合规三个方向。同样要有文献引用和对比分析表格。

第三章"自主武器系统伦理"Carol 来写。聚焦国际人道法、人类控制原则、各国政策对比。输出要有明确的立场论证。

三章之间没有前后依赖，谁先写完都行。术语要统一——如果对"AI bias"有不同翻译，以 glossary 为准。

---

## 预期解析结果

```json
[
  {
    "task_id": "task-001",
    "title": "算法偏见与公平性",
    "brief": "综述近五年 AI 偏见论文：定义、度量方法、缓解策略，至少引用 10 篇",
    "deps": [],
    "owner": "alice",
    "output_schema": "markdown literature review with citations"
  },
  {
    "task_id": "task-002",
    "title": "数据隐私与监控",
    "brief": "差分隐私/联邦学习/GDPR 合规综述，含对比分析表格",
    "deps": [],
    "owner": "bob",
    "output_schema": "markdown literature review with tables"
  },
  {
    "task_id": "task-003",
    "title": "自主武器系统伦理",
    "brief": "国际人道法/人类控制原则/各国政策对比，含立场论证",
    "deps": [],
    "owner": "carol",
    "output_schema": "markdown literature review with argumentation"
  }
]
```

# 组长口述任务（模拟 /team-tasks 输入）

> 以下为模拟组长在 `/team-tasks` 命令中的自然语言输入。

---

我们要做一份校园节能方案。分两阶段：先调研，再整合设计。

第一阶段两个任务可以同时做：

Bob 负责能耗调研——统计过去三年的电力、暖通、照明数据，找出峰值时段和浪费环节。输出一份能耗审计报告，要有数据表格和趋势图描述。

Carol 负责技术调研——调研太阳能光伏、智能楼宇控制、建筑节能改造三类技术的成本效益。输出技术对比报告，含可行性评分矩阵。

第二阶段是方案设计，由我（Alice）来做，必须等 Bob 和 Carol 都完成后才能开始。我会综合两份调研结果，设计具体的节能方案，包括目标设定（节能 20%）、实施路径（分三期）、预算估算。输出完整方案文档。

---

## 预期解析结果

```json
[
  {
    "task_id": "task-001",
    "title": "能耗调研",
    "brief": "统计三年电力/暖通/照明数据，识别峰值时段和浪费环节",
    "deps": [],
    "owner": "bob",
    "output_schema": "markdown with data tables"
  },
  {
    "task_id": "task-002",
    "title": "技术调研",
    "brief": "调研太阳能/智能控制/建筑改造的成本效益，含可行性评分矩阵",
    "deps": [],
    "owner": "carol",
    "output_schema": "markdown with comparison matrix"
  },
  {
    "task_id": "task-003",
    "title": "方案设计",
    "brief": "综合两份调研，设计节能方案（目标20%/三期实施/预算估算）",
    "deps": ["task-001", "task-002"],
    "owner": "alice",
    "output_schema": "markdown proposal document"
  }
]
```

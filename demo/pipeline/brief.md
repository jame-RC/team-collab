# Demo: Pipeline（流水线拓扑）

## 项目简介

**课题**：《基于大模型的智能客服系统可行性分析报告》

三人团队完成一份可行性分析报告，任务呈严格流水线依赖：

```
实验设计(Alice) → 数据分析(Bob) → 报告撰写(Carol)
```

- Alice 设计实验方案（对比测试框架、评测指标定义）
- Bob 基于 Alice 的方案执行数据分析（结果表格、图表描述）
- Carol 基于 Bob 的分析撰写最终报告（结论、建议）

## 团队

| 成员 | 角色 | 擅长 |
|------|------|------|
| Alice | Leader | 系统设计、项目管理 |
| Bob | Member | 数据分析、Python |
| Carol | Member | 学术写作、文献综述 |

## 截止日期

2026-06-15

## 验证重点

- DAG 线性依赖：Bob 无法在 Alice 完成前 claim
- `DEPS_NOT_READY` 正确返回 waiting_for
- 流水线中间产物正确传递给下游 reviewer

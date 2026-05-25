# Demo: Hybrid（混合拓扑）

## 项目简介

**课题**：《校园节能方案设计》

三人团队完成一份节能方案设计报告，拓扑为"两人并行调研 → 一人整合"：

```
能耗调研(Bob)   ─┐
                 ├─→ 方案设计(Alice)
技术调研(Carol) ─┘
```

- Bob 调研校园当前能耗数据（电力、暖通、照明）
- Carol 调研可用节能技术（太阳能、智能控制、建筑改造）
- Alice 基于两份调研整合为完整节能方案（目标设定、实施路径、预算估算）

## 团队

| 成员 | 角色 | 擅长 |
|------|------|------|
| Alice | Leader | 系统工程、方案整合 |
| Bob | Member | 数据采集、能源审计 |
| Carol | Member | 新能源技术、工程设计 |

## 截止日期

2026-06-20

## 验证重点

- Bob 和 Carol 可并行 claim（deps 为空）
- Alice 的 task-003 blocked by [task-001, task-002]，两者都 approved 后才能 claim
- `task_list --tree` 正确显示扇入结构
- integrator 需要处理两份不同格式的输入

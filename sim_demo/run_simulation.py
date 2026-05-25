"""
真实场景模拟：校园节能方案设计
=================================
团队：Alice(组长) + Bob(能耗调研) + Carol(技术调研)
拓扑：Bob 和 Carol 并行 → Alice 整合（扇入）

这个脚本模拟完整的协作流程，展示每一步的输入和输出。
"""
import sys
import json
from pathlib import Path

# 确保能 import teamcollab
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from teamcollab.contracts import (
    MemberInfo, ProjectMeta, Role, TaskContract, Verdict,
)
from teamcollab.tools._io import read_json, read_model, write_json, write_model
from teamcollab.tools._paths import members_json, project_json, task_json, tasks_dir
from teamcollab.tools.glossary import glossary_get, glossary_update
from teamcollab.tools.task_create_batch import task_create_batch
from teamcollab.tools.task_list import task_list
from teamcollab.tools.task_claim import task_claim, TaskClaimError
from teamcollab.tools.task_submit import task_submit
from teamcollab.tools.task_review import task_review
from teamcollab.tools.team_init import team_init
from teamcollab.events import GitEventSource
from teamcollab.git_ops import GitRepo


ROOT = Path(__file__).resolve().parent / "campus_energy_project"


def banner(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def step(msg: str):
    print(f"  → {msg}")


def show_json(data, indent=4):
    print(json.dumps(data, ensure_ascii=False, indent=indent))


# ============================================================
# STEP 1: 组长 Alice 初始化项目
# ============================================================
banner("STEP 1: 组长 Alice 初始化项目")

step("Alice 执行 /team-init，创建「校园节能方案设计」项目")
result = team_init(
    local_path=ROOT,
    title="校园节能方案设计",
    brief="三人团队完成校园节能方案：能耗调研 + 技术调研 → 方案整合",
    leader="alice",
)
print(f"  ✓ 项目创建成功")
print(f"    路径: {ROOT}")
print(f"    返回: {json.dumps(result, ensure_ascii=False)}")

# 配置 git user（模拟环境需要）
from git import Repo as GitPyRepo
g = GitPyRepo(ROOT)
g.git.config("user.email", "alice@campus.edu")
g.git.config("user.name", "Alice")

# 添加团队成员
step("添加团队成员 Bob 和 Carol")
extra = [
    MemberInfo(name="bob", role=Role.MEMBER),
    MemberInfo(name="carol", role=Role.MEMBER),
]
members_raw = read_json(members_json(ROOT))
members_raw.extend(m.model_dump(mode="json") for m in extra)
write_json(members_json(ROOT), members_raw)

project = read_model(project_json(ROOT), ProjectMeta)
project = project.model_copy(update={"members": project.members + extra})
write_model(project_json(ROOT), project)

print(f"  ✓ 团队成员: alice(leader), bob(member), carol(member)")


# ============================================================
# STEP 2: 组长 Alice 分配任务（模拟 /team-tasks）
# ============================================================
banner("STEP 2: 组长 Alice 分配任务")

step("Alice 口述任务需求，系统解析为结构化任务：")
print("""
    Alice 说：
    "我们要做一份校园节能方案。分两阶段：先调研，再整合设计。
     Bob 负责能耗调研，Carol 负责技术调研，两人可以同时做。
     最后我来整合，必须等他们都完成。"
""")

tasks = [
    TaskContract(
        task_id="task-001",
        title="能耗调研",
        brief="统计三年电力/暖通/照明数据，识别峰值时段和浪费环节，输出能耗审计报告",
        deps=[],
        owner="bob",
    ),
    TaskContract(
        task_id="task-002",
        title="技术调研",
        brief="调研太阳能/智能控制/建筑改造的成本效益，输出技术对比报告含可行性评分矩阵",
        deps=[],
        owner="carol",
    ),
    TaskContract(
        task_id="task-003",
        title="方案设计与整合",
        brief="综合两份调研，设计节能方案（目标20%节能/三期实施/预算估算），输出完整方案文档",
        deps=["task-001", "task-002"],
        owner="alice",
    ),
]

step("执行 task_create_batch 创建任务...")
result = task_create_batch(local_path=ROOT, tasks=tasks, actor="alice")
print(f"  ✓ 任务创建成功")
show_json(result)


# ============================================================
# STEP 3: 查看任务看板
# ============================================================
banner("STEP 3: 查看任务看板（task_list）")

step("查看所有任务状态：")
result = task_list(local_path=ROOT, filter="all", tree=True)
print(f"\n  任务列表:")
for t in result["tasks"]:
    print(f"    [{t['status']:12s}] {t['task_id']} - {t['title']} (owner: {t['owner']})")

print(f"\n  DAG 树形图:")
print(f"    {result['tree']}")


# ============================================================
# STEP 4: Bob 领取任务
# ============================================================
banner("STEP 4: Bob 领取「能耗调研」任务")

step("Bob 执行 /team-claim task-001")
result = task_claim(local_path=ROOT, task_id="task-001", me="bob")
print(f"  ✓ Bob 成功领取 task-001")
show_json(result)


# ============================================================
# STEP 5: Carol 领取任务
# ============================================================
banner("STEP 5: Carol 领取「技术调研」任务")

step("Carol 执行 /team-claim task-002")
result = task_claim(local_path=ROOT, task_id="task-002", me="carol")
print(f"  ✓ Carol 成功领取 task-002")
show_json(result)


# ============================================================
# STEP 6: Alice 尝试领取整合任务（应被阻塞）
# ============================================================
banner("STEP 6: Alice 尝试领取「方案整合」（应被阻塞）")

step("Alice 执行 /team-claim task-003")
try:
    task_claim(local_path=ROOT, task_id="task-003", me="alice")
    print("  ✗ 不应该到这里")
except TaskClaimError as e:
    print(f"  ✓ 正确阻塞！错误信息: {e}")
    print(f"    原因：task-001 和 task-002 尚未完成")


# ============================================================
# STEP 7: 统一术语（glossary）
# ============================================================
banner("STEP 7: 统一术语表")

step("Alice 定义术语 'HVAC'")
glossary_update(local_path=ROOT, term="HVAC", definition="暖通空调系统（Heating, Ventilation, and Air Conditioning）", actor="alice")

step("Bob 定义术语 'kWh'")
glossary_update(local_path=ROOT, term="kWh", definition="千瓦时，电能计量单位", actor="bob")

step("Carol 定义术语 'PV'")
glossary_update(local_path=ROOT, term="PV", definition="光伏（Photovoltaic），太阳能电池板技术", actor="carol")

result = glossary_get(local_path=ROOT)
print(f"  ✓ 当前术语表:")
for term, info in result["entries"].items():
    print(f"    • {term}: {info['definition']}")


# ============================================================
# STEP 8: Bob 提交能耗调研报告
# ============================================================
banner("STEP 8: Bob 提交能耗调研报告")

bob_report = """# 校园能耗审计报告

## 1. 数据概述

统计周期：2023-2025 年度

| 年度 | 电力(万kWh) | HVAC(万kWh) | 照明(万kWh) | 总计 |
|------|------------|-------------|-------------|------|
| 2023 | 856 | 423 | 198 | 1477 |
| 2024 | 892 | 451 | 205 | 1548 |
| 2025 | 934 | 478 | 212 | 1624 |

## 2. 峰值时段分析

- **电力峰值**：工作日 9:00-11:00 和 14:00-17:00，占日总耗电 62%
- **HVAC 峰值**：夏季（6-8月）占全年 HVAC 能耗的 45%
- **照明浪费**：非教学时段（21:00-6:00）仍有 23% 教室亮灯

## 3. 主要浪费环节

1. **空调过度制冷**：夏季设定温度普遍 22°C，低于推荐 26°C
2. **照明无人值守**：约 35% 教室在空置时未关灯
3. **老旧设备效率低**：2015 年前安装的 HVAC 设备 COP 仅 2.8（新设备可达 5.0+）
4. **待机功耗**：实验室设备 24h 待机，年耗约 12 万 kWh

## 4. 节能潜力评估

保守估计，通过行为管理 + 设备升级可节能 18-25%，年减排约 280-390 万 kWh。
"""

step("Bob 执行 /team-submit task-001")
result = task_submit(local_path=ROOT, task_id="task-001", me="bob", content=bob_report)
print(f"  ✓ Bob 提交成功")
print(f"    产物路径: artifacts/bob/task-001/content.md")
print(f"    字数: ~{len(bob_report)}字")


# ============================================================
# STEP 9: Carol 提交技术调研报告
# ============================================================
banner("STEP 9: Carol 提交技术调研报告")

carol_report = """# 校园节能技术对比报告

## 1. 技术方案概览

| 技术方向 | 初始投资(万元) | 年节能(万kWh) | 回收期(年) | 可行性评分 |
|----------|---------------|---------------|-----------|-----------|
| 屋顶 PV 系统 | 800 | 120 | 6.5 | ★★★★☆ |
| 智能楼宇控制 | 350 | 95 | 3.7 | ★★★★★ |
| 建筑围护改造 | 1200 | 85 | 14.1 | ★★★☆☆ |

## 2. 太阳能 PV 系统

- **规模**：可利用屋顶面积约 12,000㎡，装机容量 1.8MWp
- **年发电量**：约 180 万 kWh（考虑遮挡和衰减后实际 120 万 kWh）
- **优势**：零碳排、政策补贴、可视化教育价值
- **风险**：屋顶承重需评估、清洁维护成本

## 3. 智能楼宇控制系统

- **核心模块**：
  - 人员感知照明（PIR + 光照传感器）
  - HVAC 智能调度（基于课表 + 天气预测）
  - 能耗实时监测大屏
- **预期效果**：照明节能 40%，HVAC 节能 25%
- **优势**：投资回收快、可分期部署、数据驱动决策
- **风险**：系统集成复杂度、师生使用习惯适应

## 4. 建筑围护结构改造

- **措施**：外墙保温层升级、Low-E 玻璃更换、屋顶绿化
- **优势**：一次性改造持续受益 20+ 年
- **风险**：投资大、施工周期长、需分栋实施

## 5. 综合建议

推荐优先级：智能楼宇控制 > PV 系统 > 建筑改造（按投资回收期排序）
"""

step("Carol 执行 /team-submit task-002")
result = task_submit(local_path=ROOT, task_id="task-002", me="carol", content=carol_report)
print(f"  ✓ Carol 提交成功")
print(f"    产物路径: artifacts/carol/task-002/content.md")
print(f"    字数: ~{len(carol_report)}字")


# ============================================================
# STEP 10: 组长 Alice 评审 Bob 的报告
# ============================================================
banner("STEP 10: 组长评审 Bob 的能耗调研报告")

step("Alice（或 reviewer subagent）评审 task-001")
result = task_review(
    local_path=ROOT,
    task_id="task-001",
    reviewer="alice",
    verdict=Verdict.APPROVED,
    score=88,
    comments=[
        {"message": "数据详实，峰值分析有价值", "severity": "info"},
        {"message": "建议补充对标院校数据作为参照", "severity": "minor"},
    ],
)
print(f"  ✓ task-001 评审完成: APPROVED (88分)")
show_json(result)


# ============================================================
# STEP 11: 组长 Alice 评审 Carol 的报告
# ============================================================
banner("STEP 11: 组长评审 Carol 的技术调研报告")

step("Alice（或 reviewer subagent）评审 task-002")
result = task_review(
    local_path=ROOT,
    task_id="task-002",
    reviewer="alice",
    verdict=Verdict.APPROVED,
    score=91,
    comments=[
        {"message": "可行性评分矩阵清晰实用", "severity": "info"},
        {"message": "智能控制方案的供应商调研可进一步细化", "severity": "minor"},
    ],
)
print(f"  ✓ task-002 评审完成: APPROVED (91分)")
show_json(result)


# ============================================================
# STEP 12: Alice 现在可以领取整合任务了
# ============================================================
banner("STEP 12: Alice 领取整合任务（前置任务已全部通过）")

step("再次查看任务状态：")
result = task_list(local_path=ROOT, filter="all", tree=True)
for t in result["tasks"]:
    status_icon = "✓" if t["status"] == "approved" else "○"
    print(f"    [{status_icon}] {t['task_id']} - {t['title']} ({t['status']})")

step("\nAlice 执行 /team-claim task-003")
result = task_claim(local_path=ROOT, task_id="task-003", me="alice")
print(f"  ✓ Alice 成功领取 task-003（依赖已满足）")


# ============================================================
# STEP 13: Alice 提交最终方案
# ============================================================
banner("STEP 13: Alice 提交整合方案")

alice_proposal = """# 校园节能方案设计

## 项目概述

基于能耗审计（Bob）和技术调研（Carol）结果，制定校园三年节能 20% 的实施方案。

## 1. 节能目标

| 指标 | 当前(2025) | 目标(2028) | 降幅 |
|------|-----------|-----------|------|
| 年总能耗 | 1624 万kWh | 1299 万kWh | -20% |
| 碳排放 | 9744 tCO₂ | 7795 tCO₂ | -20% |
| 生均能耗 | 812 kWh/人 | 650 kWh/人 | -20% |

## 2. 三期实施路径

### 第一期（2025.9 - 2026.6）— 行为管理 + 智能控制
- 部署智能楼宇控制系统（投资 350 万元）
- 推行空调 26°C 制度 + 照明分时管控
- 预期节能：95 万 kWh（占总目标 29%）

### 第二期（2026.9 - 2027.6）— PV 系统建设
- 分三批完成屋顶 PV 安装（投资 800 万元）
- 配套储能系统用于削峰填谷
- 预期节能：120 万 kWh（占总目标 37%）

### 第三期（2027.9 - 2028.6）— 设备更新 + 围护改造
- 替换 COP<3.0 的老旧 HVAC 设备
- 重点建筑外墙保温升级（投资 600 万元）
- 预期节能：110 万 kWh（占总目标 34%）

## 3. 预算总览

| 项目 | 投资(万元) | 年节省(万元) | 回收期 |
|------|-----------|-------------|--------|
| 智能控制 | 350 | 95 | 3.7年 |
| PV 系统 | 800 | 120 | 6.5年 |
| 设备+围护 | 600 | 88 | 6.8年 |
| **合计** | **1750** | **303** | **5.8年** |

## 4. 风险与应对

1. **资金风险**：申请教育部节能专项补贴 + 合同能源管理模式
2. **施工影响**：安排在寒暑假施工，最小化教学干扰
3. **技术风险**：智能系统选择成熟供应商，预留 10% 冗余容量

## 5. 预期成果

- 年节能 325 万 kWh，年减碳 1950 tCO₂
- 获评"绿色校园"示范单位
- 能耗监测平台可作为教学实践基地
"""

step("Alice 执行 /team-submit task-003")
result = task_submit(local_path=ROOT, task_id="task-003", me="alice", content=alice_proposal)
print(f"  ✓ Alice 提交整合方案成功")
print(f"    字数: ~{len(alice_proposal)}字")


# ============================================================
# STEP 14: 最终评审（组长自审或外部评审）
# ============================================================
banner("STEP 14: 最终评审")

step("对整合方案进行评审")
result = task_review(
    local_path=ROOT,
    task_id="task-003",
    reviewer="alice",
    verdict=Verdict.APPROVED,
    score=93,
    comments=[
        {"message": "方案完整，三期路径清晰可执行", "severity": "info"},
        {"message": "数据来源引用充分，与调研报告衔接良好", "severity": "info"},
    ],
)
print(f"  ✓ task-003 评审完成: APPROVED (93分)")


# ============================================================
# STEP 15: 最终看板 + 事件回放
# ============================================================
banner("STEP 15: 最终项目状态")

step("任务看板：")
result = task_list(local_path=ROOT, filter="all", tree=True)
for t in result["tasks"]:
    print(f"    [✓ APPROVED] {t['task_id']} - {t['title']} (owner: {t['owner']}, score: -)")

print(f"\n  DAG 结构:")
print(f"    {result['tree']}")

step("\n术语表最终状态：")
glossary = glossary_get(local_path=ROOT)
for term, info in glossary["entries"].items():
    print(f"    • {term}: {info['definition']}")

step("\n事件回放（git log 中的 EventEnvelope）：")
git_repo = GitRepo(ROOT)
source = GitEventSource(git_repo)
events = source.read()
for ev in events:
    actor = ev.envelope.actor
    etype = ev.envelope.type.value
    task = ev.envelope.task_id or ""
    print(f"    [{etype:20s}] actor={actor:6s} {task}")


# ============================================================
# 总结
# ============================================================
banner("模拟完成 ✓")
print("""
  项目「校园节能方案设计」协作流程：

  1. Alice(组长) 初始化项目、分配 3 个任务
  2. Bob 和 Carol 并行领取各自任务（无依赖）
  3. Alice 尝试领取整合任务 → 被 DAG 阻塞
  4. 三人协同维护术语表
  5. Bob 提交能耗调研 → Alice 评审通过 (88分)
  6. Carol 提交技术调研 → Alice 评审通过 (91分)
  7. Alice 整合任务解锁 → 领取 → 提交完整方案 → 通过 (93分)

  所有产物保存在: sim_demo/campus_energy_project/artifacts/
  事件历史保存在: git log (每个操作一个 commit + EventEnvelope)
""")

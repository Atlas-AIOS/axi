# 第十五轮交付报告：Multi-Round Deliberation Gate

**日期**: 2026-03-11  
**状态**: ✅ 已完成  
**目标**: 在现有 19 席串行议政基础上，升级成多轮协商—审验—执行门控闭环

---

## 1. 本轮交付清单

### 15A: Goal Alignment Phase ✅

**实现**: `GoalAlignmentPhase` 类

**功能**:
- Round 0 议题对齐层
- 在正式开会前确认：
  - 问题定义 (`problem_definition`)
  - 成功标准 (`success_criteria`)
  - 硬约束/禁区 (`hard_constraints`)
  - 已知分歧点 (`known_divergences`)

**输出工件**: `alignment_brief.json`

```json
{
  "topic": "议题主题",
  "problem_definition": "问题定义",
  "success_criteria": ["标准1", "标准2", ...],
  "hard_constraints": ["约束1", "约束2", ...],
  "known_divergences": ["分歧1", "分歧2", ...],
  "created_at": "2026-03-11T..."
}
```

---

### 15B: Round-based Deliberation ✅

**实现**: `RoundBasedDeliberation` 类

**功能**:
- 显式 `round_id` 多轮机制
- 回合最小结构：
  - Round 0: 需求对齐
  - Round 1: 初提案
  - Round 2+: 反驳/修正/收敛
  - Round N: 直到评分达标

**MeetingState 扩展字段**:
```python
alignment_brief: Optional[AlignmentBrief]  # 对齐简报
alignment_status: str                      # pending / completed
current_round: int                         # 当前轮次
max_rounds: int                            # 最大轮数限制
round_summaries: List[RoundSummary]        # 每轮结构化总结
```

**每轮总结包含**:
- `proposals`: 提案要点
- `counter_arguments`: 反驳/质疑
- `unresolved_issues`: 未决问题
- `blocking_demands`: 阻断性要求
- `conditions`: 条件性支持
- `score`: 主持人评分

---

### 15C: Review Scoring Gate ✅

**实现**: `HostScoringGate` 类 + `ThirdPartyReview` 类

**主持人评分** (5 个维度，各 0-20 分):
1. **目标对齐度** (`goal_alignment`): 与议题目标的一致性
2. **风险闭环度** (`risk_closure`): 风险识别与处理
3. **可执行性** (`executability`): 方案可落地性
4. **反驳吸收度** (`counter_absorption`): 对质疑的回应
5. **审计完备性** (`audit_completeness`): 记录与审计

**评分门控规则**:
```
>= 95:  ✓ 允许进入执行态
70-94:  → 继续讨论
< 70:   ✗ 考虑拒绝
```

**第三方审验机构** (规则版):
- 审验员: 杨戬 / 包拯 / 钟馗 / 丰都大帝
- 基于 `pending_questions` / `blocking_demands` / `conditions` 生成评分
- 输出: `review_report.json`
  - 五个维度评分
  - 总分
  - 缺陷列表
  - 要求修改项
  - 通过/拒绝判定

---

### 15D: Agent Message Bus v1 ✅

**实现**: `AgentMessageBus` 类

**三类消息**:
1. **`clarification`**: 澄清请求
2. **`challenge`**: 反驳/质疑
3. **`dependency_request`**: 依赖协作请求

**约束**:
- 只做记录，不参与最终计票
- 所有消息可追踪、可审计、可回放
- 支持 `broadcast` 和点对点通信

**消息结构**:
```json
{
  "message_id": "msg_0001",
  "timestamp": "2026-03-11T...",
  "sender_id": "LOGOS",
  "receiver_id": "Casey",
  "message_type": "challenge",
  "content": "...",
  "related_round": 1,
  "context": {}
}
```

---

## 2. 通过标准验证

| 标准 | 状态 | 说明 |
|------|------|------|
| 同一议题可进入多轮 | ✅ | Round 0 → Round 1 → Round 2 → ... |
| 每轮都有结构化总结 | ✅ | `RoundSummary` 包含提案/反驳/未决项 |
| <95 自动继续讨论 | ✅ | `continue_deliberation = True` 自动推进 |
| 审验报告独立生成 | ✅ | `ReviewReport` 独立输出 |
| Agent 消息可追踪 | ✅ | `message_log` 完整记录，可审计 |

---

## 3. 核心组件关系

```
MultiRoundDeliberationGate (主控器)
├── GoalAlignmentPhase (15A)
│   └── alignment_brief.json
├── RoundBasedDeliberation (15B)
│   └── round_summaries[]
├── HostScoringGate (15C)
│   └── dimension_scores → total_score
├── ThirdPartyReview (15C)
│   └── review_reports[]
└── AgentMessageBus (15D)
    └── message_log[]
```

---

## 4. 使用示例

```python
from multi_round_deliberation_gate import MultiRoundDeliberationGate

# 创建门控
gate = MultiRoundDeliberationGate(
    meeting_id="demo_001",
    topic="是否集成 ConsensusPredictor",
    max_rounds=5
)

# Round 0: Goal Alignment
gate.start_meeting(
    problem_definition="评估模型集成标准",
    success_criteria=["ECE < 0.22", ...],
    hard_constraints=["不影响主逻辑", ...],
    known_divergences=["校准问题", ...]
)

# Round 1: 协商 + 评分
summary, score = gate.run_deliberation_round(
    proposals=["建议集成"],
    counter_arguments=["ECE 超标"],
    unresolved_issues=["如何修复"],
    blocking_demands=["必须解决校准"],
    conditions=["修复后可考虑"],
    dimension_scores={
        "goal_alignment": 18.0,
        "risk_closure": 12.0,
        ...
    }
)

# 发送消息
gate.message_bus.send_message(
    sender_id="LOGOS",
    receiver_id="Casey",
    message_type="challenge",
    content="数据是否准确？"
)

# 最终审验
report = gate.conduct_final_review()
```

---

## 5. 本轮不做的事（明确边界）

| 不做的事 | 原因 |
|----------|------|
| 19 席全并发自由聊天 | 保持可控性，避免失控 |
| 几百个 agent | 先验证机制，再扩展规模 |
| 第三方审验替代议政流程 | 审验是门控，不是替代 |
| 重 UI 平台 | 先做核心机制，UI 后续 |
| 无限轮讨论 | 设置 max_rounds 上限 |

---

## 6. 与现有系统的关系

**现有基础** (已验证):
- ✅ 19 席串行议政
- ✅ 阶段总结机制
- ✅ 冲突处理 / 二轮修正
- ✅ 五态决议状态机

**第十五轮新增**:
- ➕ Goal Alignment Phase
- ➕ 显式 round_id
- ➕ 主持人评分门控
- ➕ 第三方审验机构
- ➕ Agent 消息总线

**关系**: 不是推翻重建，是在现有 v2 基础上升级到 v2.5 / v3.5

---

## 7. 文件清单

```
rounds/round15/
├── multi_round_deliberation_gate.py    # 核心实现
├── ROUND15_DELIVERABLE.md               # 本交付报告
└── meeting_state_demo.json              # 演示输出示例
```

---

## 8. 下一步建议

第十五轮已验证基础机制，后续可扩展：

1. **与 Matrix Bridge 集成**: 将 `!council start` 扩展为支持 Goal Alignment Phase
2. **审验规则细化**: 基于真实会议数据优化评分算法
3. **消息总线 UI**: 添加简单的消息查看界面
4. **回放到现有会议**: 用第十五轮机制重新分析历史会议

---

**结论**: 第十五轮 Multi-Round Deliberation Gate 已完成，具备完整的议题对齐—多轮协商—审验评分—执行门控闭环能力。

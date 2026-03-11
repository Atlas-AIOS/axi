# Round 16.1: Historical Replay Acceptance Criteria

## 文档目的

定义历史会议回放验证的验收标准，确保新系统的多轮门控层在改变决策边界的同时，保持可接受的误杀率和风险拦截率。

---

## 核心指标

### 指标 1: False-Block Rate (误拦率)

**定义**: 历史上后来证明没问题的提案，被新 gate 错拦的比例

**计算公式**:
```
False-Block Rate = (历史上 Approved 且执行成功，但被新系统 Blocked 的数量) 
                   / (历史上 Approved 的总数量)
```

**验收门槛**:
- 🟢 **PASS**: ≤ 15%
- 🟡 **CONDITIONAL**: 15% - 25% (需要人工复核)
- 🔴 **FAIL**: > 25%

**为什么**: 误拦率过高意味着系统过于保守，会阻碍正常决策流程。

---

### 指标 2: Risk-Intercept Rate (风险拦截率)

**定义**: 历史上后来暴露问题的提案，被新 gate 提前拦下的比例

**计算公式**:
```
Risk-Intercept Rate = (历史上后来出问题且被新系统 Blocked 的数量)
                      / (历史上后来出问题的总数量)
```

**验收门槛**:
- 🟢 **PASS**: ≥ 70%
- 🟡 **CONDITIONAL**: 50% - 70% (需要增强检测)
- 🔴 **FAIL**: < 50%

**为什么**: 拦截率过低说明门控层没有起到应有的风控作用。

---

### 指标 3: Deliberation Overhead (协商开销)

**定义**: 额外增加的轮次 / 时间 / 消息量是否可接受

**三个子指标**:

#### 3a. 额外轮次比例
```
Extra Rounds Ratio = (需要 >1 轮协商的案例数) / (总案例数)
```
- 🟢 **PASS**: ≤ 40%
- 🟡 **CONDITIONAL**: 40% - 60%
- 🔴 **FAIL**: > 60%

#### 3b. 平均轮次增长
```
Avg Rounds Increase = 新系统平均轮次 - 历史平均轮次
```
- 🟢 **PASS**: ≤ 1.0 轮
- 🟡 **CONDITIONAL**: 1.0 - 2.0 轮
- 🔴 **FAIL**: > 2.0 轮

#### 3c. Goal Alignment 耗时
- 🟢 **PASS**: 平均 ≤ 2 分钟
- 🟡 **CONDITIONAL**: 2 - 5 分钟
- 🔴 **FAIL**: > 5 分钟

---

## 分层验证要求

### 分层 1: 按原决策结果分层

必须分别报告以下三类的一致性率:

| 原决策 | 需要验证的问题 | 最低一致率要求 |
|--------|---------------|---------------|
| **Approved** | 新系统是否会过度拦截? | ≥ 75% 保持 Approved |
| **Blocked/Rejected** | 新系统是否漏掉风险? | ≥ 80% 保持 Blocked |
| **Conditional/Pending** | 新系统是否更趋向明确决策? | ≥ 60% 给出明确结论 |

### 分层 2: 按场景类型分层

| 场景类型 | 样本数量 | 特殊要求 |
|---------|---------|---------|
| strong_support | ≥ 5 | 不应被误拦 |
| strong_opposition | ≥ 5 | 应被拦截 |
| conditional_heavy | ≥ 5 | 需要更多轮次 |
| balanced | ≥ 5 | 可能产生分歧 |
| opposition_with_veto | ≥ 3 | 必须被拦截 |

### 分层 3: 按 Gate 检查点分层

对每个被拦截的案例，必须记录拦截点:

| 拦截点 | 可接受比例 | 说明 |
|--------|-----------|------|
| Goal Alignment Phase | ≤ 20% | 议题对齐问题 |
| Deliberation Round (Score < 95) | ≤ 40% | 协商评分不足 |
| Third-Party Review | ≤ 25% | 审验不通过 |
| Decision Gate | ≤ 15% | 最终门控拦截 |

---

## 验证流程

### Phase 1: 数据准备

1. **扩充样本集**: 从 50 个案例扩展到至少 200 个
2. **标注历史结果**: 对每个历史案例标注:
   - 原决策结果 (Approved/Blocked/Conditional)
   - 后续执行情况 (成功/失败/未知)
   - 风险等级 (高/中/低)

### Phase 2: 分层回放

```python
# 伪代码
for case in historical_cases:
    result = replay(case)
    
    # 按原决策分类统计
    if case.original_status == 'approved':
        stats['approved'].total += 1
        if result.replay_status == 'approved':
            stats['approved'].retained += 1
        else:
            stats['approved'].blocked += 1
            
    # 记录拦截点
    if result.replay_status == 'blocked':
        intercept_point = result.blocked_at
        stats['intercept_points'][intercept_point] += 1
```

### Phase 3: 指标计算

运行 `historical_replay_verifier.py` 的增强版，输出:

```json
{
  "false_block_rate": 0.12,
  "risk_intercept_rate": 0.75,
  "deliberation_overhead": {
    "extra_rounds_ratio": 0.35,
    "avg_rounds_increase": 0.8,
    "alignment_time_avg": 90
  },
  "layered_analysis": {
    "approved": {"retained": 45, "blocked": 5, "rate": 0.90},
    "blocked": {"retained": 38, "unblocked": 2, "rate": 0.95}
  },
  "verdict": "PASS"
}
```

---

## 通过标准汇总

### 强制通过条件 (必须全部满足)

| 指标 | 门槛 |
|------|------|
| False-Block Rate | ≤ 15% |
| Risk-Intercept Rate | ≥ 70% |
| Extra Rounds Ratio | ≤ 40% |
| Approved Retention Rate | ≥ 75% |
| Blocked Retention Rate | ≥ 80% |

### 一票否决条件 (满足任意一条即 FAIL)

- False-Block Rate > 30%
- Risk-Intercept Rate < 40%
- 超过 30% 的 Approved 案例需要 >2 轮协商
- Goal Alignment 平均耗时 > 10 分钟

---

## Shadow 模式部署标准

在满足以下条件后，可进入 Shadow 模式:

1. ✅ 通过所有强制通过条件
2. ✅ 运行 200+ 案例验证
3. ✅ 人工复核所有被拦截的 Approved 案例
4. ✅ 确认无重大系统缺陷

Shadow 模式要求:
- 并行运行新旧系统
- 新系统只记录，不拦截
- 对比观察期: 至少 30 天或 50 个真实会议
- 定期输出对比报告

---

## 下一步行动清单

### Round 16.1 (当前)

- [ ] 扩充历史案例库至 200+
- [ ] 实现分层回放分析器
- [ ] 标注历史案例后续结果
- [ ] 生成分层验证报告

### Round 16.2

- [ ] 分析未通过指标
- [ ] 调整门控阈值
- [ ] 优化 Goal Alignment 提取逻辑
- [ ] 重新验证直至通过

### Round 17 (通过验收后)

- [ ] 部署 Shadow 模式
- [ ] 接入真实 Matrix 生命周期
- [ ] 建立持续监控 dashboard
- [ ] 制定正式切换计划

---

## 附录: 与现有系统的关联

### 与 Round 15.1 的关系

本验收标准验证的是 Round 15.1 的决策质量，通过后方可进入生产环境。

### 与 Round 16 的关系

Round 16 证明了"门控会改变决策边界"，Round 16.1 证明"改变是向好的"。

### 与现有 Matrix Bridge 的集成

验收通过后，新系统将通过 `bridge/gateway_layer.py` 接入 Matrix Bridge，原有 `!council` 命令保持不变，但增加:
- 显式 Goal Alignment 阶段
- 轮次提示
- 审验状态展示

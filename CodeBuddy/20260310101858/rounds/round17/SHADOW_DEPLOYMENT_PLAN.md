# Shadow Deployment Plan (Round 17)
# 影子部署计划

## 状态
- **前提条件**: ✅ Round 16.2 已完成，门控配置通过历史回放验收
- **当前阶段**: 准备进入 Shadow 部署
- **目标**: 30天 / 50个真实会议验证

## 核心原则

### Shadow 期间规则
1. **新系统并行运行** - 影子系统实时处理所有会议
2. **新系统只给建议，不拦截** - 建议记录但不影响实际决策
3. **旧系统仍是唯一执行链** - 所有执行仍由旧系统控制
4. **所有差异必须落审计日志** - 完整记录新旧系统差异

### 30天后三选一判定
- **Promote to default** - 影子系统晋升为主系统
- **Keep shadow longer** - 延长观察期
- **Retune and rerun** - 重新调参后再验证

---

## 部署配置

### 影子系统配置 (最佳配置来自 Round 16.2)
```python
{
    "deliberation_threshold": 75.0,   # 协商门槛
    "review_threshold": 80.0,          # 审验门槛
    "max_defects": 1,                  # 最大容忍缺陷数
    "support_weight": 1.0,             # 支持票权重
    "oppose_penalty": 1.5,             # 反对票惩罚
    "veto_penalty": 3.0                # 否决票惩罚
}
```

### 验收标准 (来自 HISTORICAL_REPLAY_ACCEPTANCE_CRITERIA)
| 指标 | 门槛 | 说明 |
|------|------|------|
| False-Block Rate | ≤ 15% | 误拦率，衡量是否过度严格 |
| Risk-Intercept Rate | ≥ 70% | 风险拦截率，衡量是否有效 |
| Extra Rounds Ratio | ≤ 40% | 额外轮次比例，衡量效率 |
| Decision Alignment | ≥ 75% | 决策一致率，衡量稳定性 |

---

## 5个核心观察指标

### 1. False-Block Rate in Real Meetings
**定义**: 旧系统批准但影子系统拦截的提案比例

**门槛**: ≤ 15%

**记录方式**:
```python
false_block_detected = (
    legacy_decision in ["approved", "conditional_approved"] and
    shadow_decision in ["rejected", "requires_deliberation"]
)
```

**分析重点**:
- 哪些类型的提案容易被误拦
- 误拦是否集中在特定场景
- 人工覆盖后是否证明是误拦

### 2. Review Disagreement Rate
**定义**: 协商评分与审验评分差异 > 20 分的会议比例

**观察目标**: 趋势稳定下降

**记录方式**:
```python
review_disagreement = abs(deliberation_score - review_score) > 20
```

**分析重点**:
- 审验与协商的不一致模式
- 哪种类型的提案容易分歧
- 分歧时的最终正确方是谁

### 3. Extra Round Overhead in Real Usage
**定义**: 影子系统建议的额外协商轮次的平均值

**门槛**: ≤ 0.4 (40%会议建议额外轮次)

**记录方式**:
```python
extra_rounds_suggested = 1 if needs_more_deliberation else 0
```

**分析重点**:
- 额外轮次建议的分布
- 接受额外轮次后的改善情况
- 额外轮次的时间成本

### 4. Human Acceptance / Override Rate
**定义**: 人工覆盖影子系统建议的比例

**观察目标**: 低且无集中抱怨

**记录方式**:
```python
human_override = True
override_reason = "业务确认：..."
```

**分析重点**:
- 哪些场景需要人工介入
- 人工覆盖的合理性
- 影子系统建议的采纳率

### 5. Accepted-Risk Miss Rate ⭐ NEW
**定义**: 旧系统放行、影子系统高置信拦截的案例中，后续验证确实暴露问题的比例

**作用**: 区分"误拦"与"提前发现风险"

**记录方式**:
```python
# 检测高置信风险拦截
accepted_risk_detected = (
    legacy_decision in ["approved", "conditional_approved"] and
    shadow_decision in ["rejected", "requires_deliberation"] and
    shadow_confidence > 0.8
)

# 30天后验证
manager.validate_risk(meeting_id, risk_confirmed=True/False, notes="...")
```

**分析重点**:
- 高置信拦截的准确性
- 真正的风险拦截 vs 误拦
- 影子系统的风险识别能力

---

## 部署检查清单

### 部署前检查
- [ ] Round 16.2 调参报告已归档
- [ ] 影子部署配置已确认
- [ ] 审计日志存储路径已配置
- [ ] 旧系统备份已完成
- [ ] 回滚方案已准备

### 部署日检查
- [ ] 影子系统服务已启动
- [ ] 审计日志正常写入
- [ ] 旧系统运行不受影响
- [ ] 监控告警已配置
- [ ] 值班人员已通知

### 运行期检查 (每日)
- [ ] 影子系统运行状态正常
- [ ] 审计日志无异常
- [ ] 新旧系统差异在可接受范围
- [ ] 无性能问题

### 30天评估检查
- [ ] 50个会议数据已收集
- [ ] 5个核心指标已计算 (含 Accepted-risk 验证)
- [ ] 验收标准评估完成
- [ ] 晋升/延长/重调建议已输出

---

## 决策矩阵

### 晋升条件 (Promote to Default)
必须同时满足:
- False-Block Rate ≤ 15%
- Decision Alignment ≥ 75%
- Extra Rounds Ratio ≤ 40%
- 总会议数 ≥ 50
- 运行天数 ≥ 30

### 延长条件 (Keep Shadow Longer)
满足以下任一:
- 会议数或天数不足
- 指标在门槛附近波动
- 需要更多数据确认稳定性

### 重调条件 (Retune and Rerun)
满足以下任一:
- False-Block Rate > 15%
- Decision Alignment < 75%
- 有明显系统性偏差

---

## 风险与应对

| 风险 | 可能性 | 影响 | 应对措施 |
|------|--------|------|----------|
| 影子系统影响旧系统性能 | 低 | 高 | 资源隔离，独立部署 |
| 误拦率过高导致业务不满 | 中 | 高 | 实时监控，人工覆盖机制 |
| 审计日志过大 | 中 | 中 | 定期归档，压缩存储 |
| 30天后指标不达标 | 中 | 中 | 准备重调方案 |

---

## 附录

### 相关文件
- `bridge/shadow_deployment.py` - 影子部署框架
- `rounds/round16/HISTORICAL_REPLAY_ACCEPTANCE_CRITERIA.md` - 验收标准
- `ROUND16_2_TUNING_REPORT.md` - 调参报告
- `data/shadow/` - 审计日志存储目录

### 关键命令
```bash
# 启动影子部署
python3 bridge/shadow_deployment.py

# 查看当前状态
python3 -c "from bridge.shadow_deployment import ShadowDeploymentManager; \
            m = ShadowDeploymentManager(shadow_id='SHADOW-XXXX'); \
            m.print_status()"

# 生成报告
python3 -c "from bridge.shadow_deployment import ShadowDeploymentManager; \
            m = ShadowDeploymentManager(shadow_id='SHADOW-XXXX'); \
            m.generate_report()"
```

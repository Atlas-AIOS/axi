# Round 17.3: Shadow Deployment Launch
# 新一轮影子部署启动文档

**日期**: 2026-03-11  
**配置版本**: deliberation=70, review=80  
**观察期**: 30天 / 50个真实会议  

---

## 部署决策

### 采用配置
```python
{
    "deliberation_threshold": 70.0,  # Round 17.2 验证的推荐值
    "review_threshold": 80.0,        # 保持不动
    "max_defects": 1,
    "support_weight": 1.0,
    "oppose_penalty": 1.5,
    "veto_penalty": 3.0
}
```

### 决策依据 (Round 17.2 结论)

| 配置 | FB Rate | Alignment | Accepted-Risk | 判定 |
|------|---------|-----------|---------------|------|
| 75/80 (旧) | 38% | 24% | 17 | ❌ 过严 |
| **70/80 (新)** | **16%** | **38%** | **7** | ✅ **采用** |
| 70/75 | 16% | 42% | 7 | ⚠️ 多改一个变量，归因弱 |
| 65/80 | 4% | 48% | 1 | ⚠️ 过松，漏检风险 |

**选择 70/80 的理由**:
1. **最小有效改动**: 只改 deliberation 一个参数
2. **不过度放松**: FB 16% 接近 15% 门槛，非 4% 过松
3. **问题主因匹配**: deliberation 是主要瓶颈，review 不是
4. **风险可控**: Accepted-Risk 7个处于合理水平

---

## 验收口径

### 🔍 阶段性观察目标 (中期检查参考)

用于 15 天中期检查，判断趋势方向：

| 指标 | 当前值 | 观察目标 | 说明 |
|------|--------|----------|------|
| False-Block Rate | 16% | **≤ 15%** | 接近门槛即可 |
| Decision Alignment | 38% | **≥ 60%** | 确认改善趋势 |
| Accepted-Risk Cases | 7 | 5-12 | 不过度漏检即可 |
| Extra Rounds | - | ≤ 0.5 | 中期可略宽松 |

### ⭐ Promote 正式门槛 (30天后判定)

**必须同时满足**，缺一不可：

| 门槛 | 数值 | 来源 |
|------|------|------|
| False-Block Rate | **≤ 15%** | Round 17 原始标准 |
| Decision Alignment | **≥ 75%** | Round 17 原始标准 |
| Extra Rounds Ratio | **≤ 40%** | Round 17 原始标准 |
| 样本数 | **≥ 50** | Round 17 原始标准 |
| 运行天数 | **≥ 30** | Round 17 原始标准 |
| Accepted-Risk 验证 | **完成** | 30天后验证

### 30天判定标准

**Promote (晋升生产默认)**: 全部正式门槛达标

**Extend (延长观察)**: 
- FB Rate ≤ 15% 达标，但 Alignment 60-75% (接近但未达 75%)
- 或总样本/天数达标，但 Accepted-Risk 验证未完成

**Retune (再次调参)**: 
- FB Rate > 20% (改善不足)
- Alignment < 60% (方向错误)
- 或特定 source/topic 误差仍显著集中

## Source/Topic 细分监控 (重点盯防)

> ⚠️ **关键提醒**: 即使总 FB Rate 达标，若误差集中在特定来源或议题类型，仍可能导致结构性偏差。

### Source 分桶观察

Round 17.1 归因显示 live_manual 是主要误拦来源 (40% FB Rate)。本轮需确认是否改善：

| Source | Round 17 FB Rate | 本轮目标 | 告警线 |
|--------|------------------|----------|--------|
| live_manual | 40% | ≤ 20% | > 30% 🔴 |
| live_auto | 40% | ≤ 20% | > 25% 🟡 |
| replay_real | 20% | ≤ 15% | > 20% 🟡 |

**判定规则**:
- live_manual 仍 > 30% → 需下调至 65 或启用 source-aware 校准
- live_auto 恶化 > 25% → 回滚 deliberation 调整

### Topic 分桶观察

Round 17.1 归因显示 strategic_initiative / technical_decision 分歧率异常高：

| Topic Type | 分歧率 (R17) | 本轮目标 | 告警线 |
|------------|--------------|----------|--------|
| strategic_initiative | 100% (6/6) | ≤ 50% | > 70% 🔴 |
| technical_decision | 83% (5/6) | ≤ 50% | > 70% 🔴 |
| compliance_check | 78% (7/9) | ≤ 50% | > 60% 🟡 |
| resource_allocation | - | ≤ 30% | > 40% 🟡 |

**判定规则**:
- 任何 topic 分歧率仍 > 70% → 需启用 topic-aware margin 调整
- strategic_initiative 持续 100% → P2 措施强制启动

### 细分监控检查清单

- [ ] 每 10 个样本检查一次 source 分桶 FB Rate
- [ ] 每 10 个样本检查一次 topic 分桶分歧率
- [ ] 若 live_manual 连续 3 个样本误拦 → 标记告警
- [ ] 若 strategic_initiative 连续 2 个分歧 → 标记告警

---

## 启动检查清单

- [x] 配置更新: deliberation_threshold = 70
- [x] 配置保持: review_threshold = 80
- [x] 其他参数: 与 Round 17 保持一致
- [x] 数据目录: `data/shadow/` 已就绪
- [x] 日志格式: 与上一轮保持一致 (确保可比性)

---

## 三条纪律 (重申)

1. **新系统只记录，不拦截**
2. **旧系统仍是唯一执行链**
3. **所有分歧都落日志，不人工挑样本**

---

## 时间线

| 阶段 | 时间 | 动作 |
|------|------|------|
| 启动 | 2026-03-11 | 切换配置，开始收集样本 |
| 中期 | 2026-03-26 (15天) | 可选：检查初步趋势 |
| 验收 | 2026-04-10 (30天) | 收集满50样本，生成报告 |
| 判定 | 2026-04-10 | Promote / Extend / Retune |

---

## 验收口径速查

```
┌─────────────────────────────────────────────────────────────┐
│  阶段性观察目标 (15天检查)                                   │
│  - FB Rate ≤ 15%                                            │
│  - Alignment ≥ 60% (趋势确认)                                │
├─────────────────────────────────────────────────────────────┤
│  Promote 正式门槛 (30天判定)                                 │
│  - FB Rate ≤ 15%                                            │
│  - Alignment ≥ 75% ⭐ 关键差距                               │
│  - Extra Rounds ≤ 40%                                       │
│  - 样本 ≥ 50, 天数 ≥ 30                                     │
│  - Accepted-Risk 验证完成                                    │
├─────────────────────────────────────────────────────────────┤
│  细分盯防                                                   │
│  - live_manual FB Rate ≤ 20% (原 40%)                       │
│  - strategic_initiative 分歧 ≤ 50% (原 100%)                │
└─────────────────────────────────────────────────────────────┘
```

## 一句话

> **Round 17.3 已启动：deliberation=70/review=80 进入新一轮 Shadow。正式 Promote 门槛是 Alignment≥75% (不是 60%)。同步盯防 live_manual 和 strategic_initiative 细分指标，30天后三选一。**

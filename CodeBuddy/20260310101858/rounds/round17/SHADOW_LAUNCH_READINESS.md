# Shadow Launch Readiness
# 影子部署启动就绪确认

**日期**: 2026-03-11  
**状态**: 🟢 **Ready for Shadow Deployment**  
**前提**: Round 16.2 门控调参已通过验收

---

## 核心判定

### 当前状态
```
Ready for shadow deployment, not ready for promotion.
```

### 判定依据

| 指标 | 演示结果 | 门槛 | 状态 |
|------|----------|------|------|
| False-Block Rate | 20% | ≤ 15% | ⚠️ 超标 |
| Decision Alignment | 60% | ≥ 75% | ⚠️ 不足 |
| Extra Rounds | 0.4 | ≤ 0.4 | ✅ 达标 |

**结论**: 演示数据显示系统尚未达到正式切换标准，但已具备进入影子观察的条件。

---

## 三条纪律 (强制执行)

### 1. 新系统只记录，不拦截
- 影子系统的建议仅用于观察
- 不影响实际决策流程
- 所有建议落审计日志

### 2. 旧系统仍是唯一执行链
- 所有执行仍由旧系统控制
- 影子系统无执行权
- 无并行干预能力

### 3. 所有分歧都落日志，不人工挑样本
- 100% 记录，无选择性过滤
- 无人工干预采样
- 完整审计追踪

---

## 5个核心观察指标

### 1. False-Block Rate
- **定义**: 旧批准但影子拦截的比例
- **门槛**: ≤ 15%
- **30天目标**: 降至 15% 以下

### 2. Review Disagreement Rate
- **定义**: 协商与审验评分差异 > 20 的比例
- **30天目标**: 趋势稳定下降

### 3. Extra Round Overhead
- **定义**: 影子建议的额外轮次平均值
- **门槛**: ≤ 0.4
- **30天目标**: 保持达标

### 4. Human Override Rate
- **定义**: 人工覆盖影子建议的比例
- **30天目标**: 低且无集中抱怨

### 5. Accepted-Risk Miss Rate ⭐
- **定义**: 旧放行+新高置信拦截案例中，后续验证确实有风险的比例
- **作用**: 区分"误拦"与"提前发现风险"
- **30天动作**: 对 Accepted-risk 案例进行后续验证

---

## 30天后判定标准

### 🟢 PROMOTE (晋升为主系统)
必须同时满足:
- False-Block ≤ 15%
- Decision Alignment ≥ 75%
- Extra Round ≤ 40%
- Review Disagreement 稳定下降
- Human Override 低且无集中抱怨

### 🟡 EXTEND (延长观察)
满足以下任一:
- 指标接近门槛
- 趋势改善但样本不够稳
- 需要更多数据确认

### 🔴 RETUNE (重新调参)
满足以下任一:
- False-Block 持续 > 15%
- Decision Alignment 持续 < 75%
- 人工覆盖频繁且有规律

---

## 启动检查清单

### 部署前
- [x] Round 16.2 调参报告已归档
- [x] 影子部署框架已更新 (含 Accepted-risk)
- [x] 三条纪律文档化
- [x] 5个指标记录机制就绪
- [ ] 部署时间窗口确认
- [ ] Matrix Bridge 集成点确认

### 部署日
- [ ] `python3 bridge/launch_shadow.py` 执行
- [ ] Shadow ID 确认
- [ ] 审计日志路径确认
- [ ] 监控告警配置
- [ ] 值班人员通知

### 运行期 (30天)
- [ ] 每日指标检查
- [ ] 每周趋势分析
- [ ] Accepted-risk 案例标记
- [ ] 人工覆盖记录

### 30天后
- [ ] Accepted-risk 案例验证
- [ ] 5个指标最终计算
- [ ] 判定 (Promote/Extend/Retune)
- [ ] 报告输出

---

## 关键文件

| 文件 | 作用 |
|------|------|
| `bridge/shadow_deployment.py` | 影子部署管理器 |
| `bridge/launch_shadow.py` | 启动脚本 |
| `rounds/round17/SHADOW_DEPLOYMENT_PLAN.md` | 详细部署计划 |
| `data/shadow/` | 审计日志存储 |

---

## 启动命令

```bash
# 启动影子部署
python3 bridge/launch_shadow.py

# 查看实时状态
python3 -c "from bridge.shadow_deployment import ShadowDeploymentManager; \
            m = ShadowDeploymentManager(shadow_id='SHADOW-YYYYMMDD-PROD'); \
            m.print_status()"

# 验证 Accepted-risk 案例 (30天后)
python3 -c "from bridge.shadow_deployment import ShadowDeploymentManager; \
            m = ShadowDeploymentManager(shadow_id='SHADOW-YYYYMMDD-PROD'); \
            m.validate_risk('MTG-XXX', risk_confirmed=True, notes='...')"
```

---

## 样本来源分类与判定规则

### 来源类型定义

| 来源类型 | 说明 | 判定优先级 |
|----------|------|------------|
| `live_manual` | 手动发起的真实会议 | ⭐⭐⭐ 高 |
| `live_auto` | 自动进入的真实会议 | ⭐⭐⭐ 高 |
| `replay_real` | 历史真实会议回放 | ⭐⭐ 辅助 |
| `staged` | 受控演练 | ⭐ 盲区覆盖 |

### 判定规则

**主结论依据**: `live_manual` + `live_auto`  
**辅助证据**: `replay_real`  
**盲区覆盖**: `staged` (不作为主结论)

### 使用示例

```python
# 手动发起的真实会议
manager.process_meeting(
    meeting_id="MTG-001",
    legacy_decision="approved",
    shadow_decision="rejected",
    source_type="live_manual",      # 手动真实会议
    issue_type="budget_allocation", # 议题类型
    risk_level="high",              # 风险等级
    ...
)
```

---

## 最终确认

**当前结论**: 系统已就绪，可进入 30 天影子观察期。

**不是**: "系统已完美，立即切换"  
**而是**: "系统值得在真实环境中验证，用 30 天数据决定下一步"

**下一步动作**: 等待部署窗口，执行 `launch_shadow.py`

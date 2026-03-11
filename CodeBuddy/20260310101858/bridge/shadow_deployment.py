#!/usr/bin/env python3
"""
Shadow Deployment Framework
影子部署框架 (Round 17)

作用: 新系统并行运行，只记录建议不拦截，与旧系统对比验证
验证周期: 30天 / 50个真实会议

Shadow 期间规则:
1. 新系统并行运行
2. 新系统只给建议，不拦截
3. 旧系统仍是唯一执行链
4. 所有差异必须落审计日志

30天后三选一判定:
- Promote to default (正式切换)
- Keep shadow longer (延长观察)
- Retune and rerun (重新调参)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid


class ShadowStatus(Enum):
    """影子部署状态"""
    ACTIVE = "active"           # 运行中
    PAUSED = "paused"           # 暂停
    COMPLETED = "completed"     # 完成
    PROMOTED = "promoted"       # 已晋升
    RETUNED = "retuned"         # 已重调


class RecommendationAction(Enum):
    """建议动作"""
    APPROVE = "approve"         # 建议批准
    REJECT = "reject"           # 建议拒绝
    CONTINUE = "continue"       # 建议继续讨论
    ESCALATE = "escalate"       # 建议升级
    NO_OP = "no_op"             # 无操作


@dataclass
class ShadowObservation:
    """影子观察记录"""
    # 基础信息
    observation_id: str
    meeting_id: str
    timestamp: str
    
    # 样本来源 (live_manual/live_auto/replay_real/staged)
    source_type: str              # 样本来源类型
    
    # 议题特征
    issue_type: str               # 议题类型
    risk_level: str               # 风险等级 (low/medium/high/critical)
    
    # 新旧系统决策对比
    legacy_decision: str          # 旧系统决策
    shadow_decision: str          # 影子系统决策
    decision_aligned: bool        # 是否一致
    
    # 5个核心观察指标 (4个原指标 + Accepted-risk miss rate)
    false_block_detected: bool    # 是否发现误拦
    review_disagreement: bool     # 审验分歧
    extra_rounds_suggested: int   # 建议额外轮次
    human_override: bool          # 是否有人工覆盖
    accepted_risk_detected: bool  # 新系统高置信拦截旧放行案例 (Accepted-risk miss)
    
    # 详细评分
    deliberation_score: float
    review_score: float
    shadow_confidence: float      # 影子系统置信度
    gate_checks: List[Dict]
    
    # 后续验证 (用于 Accepted-risk miss rate)
    risk_validated: Optional[bool] = None   # 后续是否暴露问题
    validated_at: Optional[str] = None      # 验证时间
    
    # 元数据
    notes: str = ""
    logged_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "observation_id": self.observation_id,
            "meeting_id": self.meeting_id,
            "timestamp": self.timestamp,
            "source_type": self.source_type,
            "issue_type": self.issue_type,
            "risk_level": self.risk_level,
            "legacy_decision": self.legacy_decision,
            "shadow_decision": self.shadow_decision,
            "decision_aligned": self.decision_aligned,
            "false_block_detected": self.false_block_detected,
            "review_disagreement": self.review_disagreement,
            "extra_rounds_suggested": self.extra_rounds_suggested,
            "human_override": self.human_override,
            "accepted_risk_detected": self.accepted_risk_detected,
            "deliberation_score": self.deliberation_score,
            "review_score": self.review_score,
            "shadow_confidence": self.shadow_confidence,
            "gate_checks": self.gate_checks,
            "risk_validated": self.risk_validated,
            "validated_at": self.validated_at,
            "notes": self.notes,
            "logged_at": self.logged_at
        }


@dataclass
class ShadowMetrics:
    """影子部署指标汇总"""
    # 时间范围
    start_date: str
    end_date: str
    total_days: int
    
    # 会议统计
    total_meetings: int
    completed_meetings: int
    
    # 5个核心观察指标 (4个原指标 + Accepted-risk miss rate)
    false_block_rate: float       # 误拦率 (目标: ≤ 15%)
    review_disagreement_rate: float  # 审验分歧率
    avg_extra_rounds: float       # 平均额外轮次 (目标: ≤ 0.4)
    human_override_rate: float    # 人工覆盖率
    accepted_risk_miss_rate: float  # 已接受风险漏检率 (新指标)
    
    # 一致性
    decision_alignment_rate: float  # 决策一致率
    
    # 细分统计
    legacy_approved_shadow_blocked: int   # 旧批新拦 (潜在误拦)
    legacy_blocked_shadow_approved: int   # 旧拦新批 (潜在漏拦)
    both_approved: int
    both_blocked: int
    
    # Accepted-risk miss 细分
    accepted_risk_cases: int           # 旧放行新高置信拦截案例数
    validated_risk_cases: int          # 已验证的案例数
    confirmed_risk_cases: int          # 验证后确认有问题的案例数
    false_positive_risk_cases: int     # 验证后确认无问题的案例数 (误拦)
    
    # 样本来源统计 (live_manual/live_auto/replay_real/staged)
    live_manual_count: int         # 手动发起的真实会议
    live_auto_count: int           # 自动进入的真实会议
    replay_real_count: int         # 历史真实会议回放
    staged_count: int              # 受控演练
    
    # 议题类型分布
    issue_type_distribution: Dict[str, int]   # 各议题类型数量
    risk_level_distribution: Dict[str, int]   # 各风险等级数量
    
    # 状态
    evaluation_status: str        # pending / ready_for_decision
    recommendation: str           # promote / extend / retune
    
    def to_dict(self) -> Dict:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "total_days": self.total_days,
            "total_meetings": self.total_meetings,
            "completed_meetings": self.completed_meetings,
            "false_block_rate": self.false_block_rate,
            "review_disagreement_rate": self.review_disagreement_rate,
            "avg_extra_rounds": self.avg_extra_rounds,
            "human_override_rate": self.human_override_rate,
            "accepted_risk_miss_rate": self.accepted_risk_miss_rate,
            "decision_alignment_rate": self.decision_alignment_rate,
            "legacy_approved_shadow_blocked": self.legacy_approved_shadow_blocked,
            "legacy_blocked_shadow_approved": self.legacy_blocked_shadow_approved,
            "both_approved": self.both_approved,
            "both_blocked": self.both_blocked,
            "accepted_risk_cases": self.accepted_risk_cases,
            "validated_risk_cases": self.validated_risk_cases,
            "confirmed_risk_cases": self.confirmed_risk_cases,
            "false_positive_risk_cases": self.false_positive_risk_cases,
            "live_manual_count": self.live_manual_count,
            "live_auto_count": self.live_auto_count,
            "replay_real_count": self.replay_real_count,
            "staged_count": self.staged_count,
            "issue_type_distribution": self.issue_type_distribution,
            "risk_level_distribution": self.risk_level_distribution,
            "evaluation_status": self.evaluation_status,
            "recommendation": self.recommendation
        }


class ShadowDeploymentManager:
    """影子部署管理器"""
    
    # 最佳配置 (来自 Round 16.2)
    DEFAULT_CONFIG = {
        "deliberation_threshold": 75.0,
        "review_threshold": 80.0,
        "max_defects": 1,
        "support_weight": 1.0,
        "oppose_penalty": 1.5,
        "veto_penalty": 3.0
    }
    
    # 验收门槛
    ACCEPTANCE_CRITERIA = {
        "max_false_block_rate": 0.15,
        "min_decision_alignment": 0.75,
        "max_avg_extra_rounds": 0.4,
        "min_meetings": 50,
        "min_days": 30
    }
    
    def __init__(self, 
                 shadow_id: Optional[str] = None,
                 config: Optional[Dict] = None,
                 storage_dir: str = "/home/admin/CodeBuddy/20260310101858/data/shadow"):
        self.shadow_id = shadow_id or f"SHADOW-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
        self.config = config or self.DEFAULT_CONFIG
        self.storage_dir = storage_dir
        self.observations: List[ShadowObservation] = []
        self.status = ShadowStatus.ACTIVE
        self.start_time = datetime.now()
        
        # 确保存储目录存在
        os.makedirs(storage_dir, exist_ok=True)
        
        print(f"[ShadowDeployment] 初始化影子部署: {self.shadow_id}")
        print(f"  - 配置: deliberation_threshold={self.config['deliberation_threshold']}")
        print(f"  - 目标: 30天 / 50个会议")
        print(f"  - 模式: 只观察不拦截")
    
    def process_meeting(self, 
                       meeting_id: str,
                       legacy_decision: str,      # 旧系统决策
                       shadow_decision: str,      # 影子系统决策
                       deliberation_score: float,
                       review_score: float,
                       gate_checks: List[Dict],
                       shadow_confidence: float = 0.0,  # 影子系统置信度
                       source_type: str = "live_manual",  # 样本来源
                       issue_type: str = "general",       # 议题类型
                       risk_level: str = "medium",         # 风险等级
                       notes: str = "") -> ShadowObservation:
        """
        处理一个会议的对比观察
        
        Args:
            meeting_id: 会议ID
            legacy_decision: 旧系统决策 (approved/rejected/conditional)
            shadow_decision: 影子系统决策
            deliberation_score: 协商评分
            review_score: 审验评分
            gate_checks: 门控检查详情
            shadow_confidence: 影子系统置信度 (0-1)
            source_type: 样本来源 (live_manual/live_auto/replay_real/staged)
            issue_type: 议题类型
            risk_level: 风险等级 (low/medium/high/critical)
            notes: 备注
        """
        # 判断是否一致
        decision_aligned = legacy_decision == shadow_decision
        
        # 判断是否可能误拦 (旧批新拦)
        false_block_detected = (
            legacy_decision in ["approved", "conditional_approved"] and
            shadow_decision in ["rejected", "requires_deliberation"]
        )
        
        # 审验分歧 (审验评分与协商评分差异大)
        review_disagreement = abs(deliberation_score - review_score) > 20
        
        # 估计额外轮次
        extra_rounds_suggested = self._estimate_extra_rounds(
            deliberation_score, review_score, gate_checks
        )
        
        # Accepted-risk miss: 旧放行 + 新高置信拦截 (置信度 > 0.8 视为高置信)
        accepted_risk_detected = (
            legacy_decision in ["approved", "conditional_approved"] and
            shadow_decision in ["rejected", "requires_deliberation"] and
            shadow_confidence > 0.8
        )
        
        observation = ShadowObservation(
            observation_id=f"OBS-{uuid.uuid4().hex[:12]}",
            meeting_id=meeting_id,
            timestamp=datetime.now().isoformat(),
            source_type=source_type,
            issue_type=issue_type,
            risk_level=risk_level,
            legacy_decision=legacy_decision,
            shadow_decision=shadow_decision,
            decision_aligned=decision_aligned,
            false_block_detected=false_block_detected,
            review_disagreement=review_disagreement,
            extra_rounds_suggested=extra_rounds_suggested,
            human_override=False,  # 初始为False，人工覆盖时更新
            accepted_risk_detected=accepted_risk_detected,
            deliberation_score=deliberation_score,
            review_score=review_score,
            shadow_confidence=shadow_confidence,
            gate_checks=gate_checks,
            notes=notes,
            logged_at=datetime.now().isoformat()
        )
        
        self.observations.append(observation)
        
        # 实时保存
        self._save_observation(observation)
        
        # 打印关键差异
        if not decision_aligned:
            print(f"  ⚠️  决策差异: {meeting_id} [{source_type}]")
            print(f"     议题: {issue_type} | 风险: {risk_level}")
            print(f"     旧系统: {legacy_decision} | 影子系统: {shadow_decision}")
            if false_block_detected:
                print(f"     🔴 潜在误拦!")
            if accepted_risk_detected:
                print(f"     🚨 高置信风险拦截 (Accepted-risk detected)")
        
        return observation
    
    def _estimate_extra_rounds(self, 
                               deliberation_score: float, 
                               review_score: float,
                               gate_checks: List[Dict]) -> int:
        """估计建议的额外轮次"""
        # 简化逻辑：如果需要继续讨论，建议1轮
        for check in gate_checks:
            if check.get("status") == "pending":
                return 1
            if check.get("check_name") == "deliberation_minimum" and check.get("status") == "fail":
                return 1
        return 0
    
    def _save_observation(self, observation: ShadowObservation):
        """保存观察记录"""
        filename = f"{self.storage_dir}/{self.shadow_id}_observations.jsonl"
        with open(filename, "a") as f:
            f.write(json.dumps(observation.to_dict(), ensure_ascii=False) + "\n")
    
    def record_human_override(self, 
                             meeting_id: str, 
                             override_decision: str,
                             reason: str):
        """记录人工覆盖"""
        for obs in self.observations:
            if obs.meeting_id == meeting_id:
                obs.human_override = True
                obs.notes += f"\n[人工覆盖] {override_decision}: {reason}"
                print(f"  👤 人工覆盖记录: {meeting_id} -> {override_decision}")
                break
    
    def calculate_metrics(self) -> ShadowMetrics:
        """计算当前指标"""
        if not self.observations:
            return ShadowMetrics(
                start_date=self.start_time.isoformat(),
                end_date=datetime.now().isoformat(),
                total_days=(datetime.now() - self.start_time).days,
                total_meetings=0,
                completed_meetings=0,
                false_block_rate=0.0,
                review_disagreement_rate=0.0,
                avg_extra_rounds=0.0,
                human_override_rate=0.0,
                accepted_risk_miss_rate=0.0,
                decision_alignment_rate=0.0,
                legacy_approved_shadow_blocked=0,
                legacy_blocked_shadow_approved=0,
                both_approved=0,
                both_blocked=0,
                accepted_risk_cases=0,
                validated_risk_cases=0,
                confirmed_risk_cases=0,
                false_positive_risk_cases=0,
                live_manual_count=0,
                live_auto_count=0,
                replay_real_count=0,
                staged_count=0,
                issue_type_distribution={},
                risk_level_distribution={},
                evaluation_status="pending",
                recommendation="pending"
            )
        
        total = len(self.observations)
        
        # 基础计数
        aligned = sum(1 for o in self.observations if o.decision_aligned)
        false_blocks = sum(1 for o in self.observations if o.false_block_detected)
        review_disagreements = sum(1 for o in self.observations if o.review_disagreement)
        overrides = sum(1 for o in self.observations if o.human_override)
        extra_rounds_total = sum(o.extra_rounds_suggested for o in self.observations)
        
        # 细分统计
        la_sb = sum(1 for o in self.observations 
                    if o.legacy_decision in ["approved", "conditional_approved"]
                    and o.shadow_decision in ["rejected", "requires_deliberation"])
        lb_sa = sum(1 for o in self.observations
                    if o.legacy_decision in ["rejected", "blocked"]
                    and o.shadow_decision in ["approved", "conditional_approved"])
        both_a = sum(1 for o in self.observations
                     if o.legacy_decision in ["approved", "conditional_approved"]
                     and o.shadow_decision in ["approved", "conditional_approved"])
        both_b = sum(1 for o in self.observations
                     if o.legacy_decision in ["rejected", "blocked"]
                     and o.shadow_decision in ["rejected", "blocked"])
        
        # Accepted-risk miss 统计
        accepted_risk_cases = sum(1 for o in self.observations if o.accepted_risk_detected)
        validated_risk_cases = sum(1 for o in self.observations 
                                   if o.accepted_risk_detected and o.risk_validated is not None)
        confirmed_risk_cases = sum(1 for o in self.observations 
                                   if o.accepted_risk_detected and o.risk_validated == True)
        false_positive_risk_cases = sum(1 for o in self.observations 
                                        if o.accepted_risk_detected and o.risk_validated == False)
        
        # Accepted-risk miss rate: 已验证案例中确认有风险的比例
        if validated_risk_cases > 0:
            accepted_risk_miss_rate = confirmed_risk_cases / validated_risk_cases
        elif accepted_risk_cases > 0:
            accepted_risk_miss_rate = -1.0  # 用负数表示待验证
        else:
            accepted_risk_miss_rate = 0.0
        
        # 样本来源统计
        live_manual_count = sum(1 for o in self.observations if o.source_type == "live_manual")
        live_auto_count = sum(1 for o in self.observations if o.source_type == "live_auto")
        replay_real_count = sum(1 for o in self.observations if o.source_type == "replay_real")
        staged_count = sum(1 for o in self.observations if o.source_type == "staged")
        
        # 议题类型分布
        issue_type_distribution = {}
        for o in self.observations:
            issue_type_distribution[o.issue_type] = issue_type_distribution.get(o.issue_type, 0) + 1
        
        # 风险等级分布
        risk_level_distribution = {}
        for o in self.observations:
            risk_level_distribution[o.risk_level] = risk_level_distribution.get(o.risk_level, 0) + 1
        
        # 计算指标
        days_elapsed = (datetime.now() - self.start_time).days
        
        metrics = ShadowMetrics(
            start_date=self.start_time.isoformat(),
            end_date=datetime.now().isoformat(),
            total_days=days_elapsed,
            total_meetings=total,
            completed_meetings=total,
            false_block_rate=false_blocks / total if total > 0 else 0.0,
            review_disagreement_rate=review_disagreements / total if total > 0 else 0.0,
            avg_extra_rounds=extra_rounds_total / total if total > 0 else 0.0,
            human_override_rate=overrides / total if total > 0 else 0.0,
            accepted_risk_miss_rate=accepted_risk_miss_rate,
            decision_alignment_rate=aligned / total if total > 0 else 0.0,
            legacy_approved_shadow_blocked=la_sb,
            legacy_blocked_shadow_approved=lb_sa,
            both_approved=both_a,
            both_blocked=both_b,
            accepted_risk_cases=accepted_risk_cases,
            validated_risk_cases=validated_risk_cases,
            confirmed_risk_cases=confirmed_risk_cases,
            false_positive_risk_cases=false_positive_risk_cases,
            live_manual_count=live_manual_count,
            live_auto_count=live_auto_count,
            replay_real_count=replay_real_count,
            staged_count=staged_count,
            issue_type_distribution=issue_type_distribution,
            risk_level_distribution=risk_level_distribution,
            evaluation_status="pending",
            recommendation="pending"
        )
        
        # 判断是否满足验收条件
        self._evaluate_readiness(metrics)
        
        return metrics
    
    def _evaluate_readiness(self, metrics: ShadowMetrics):
        """评估是否满足正式切换条件"""
        criteria = self.ACCEPTANCE_CRITERIA
        
        checks = [
            metrics.false_block_rate <= criteria["max_false_block_rate"],
            metrics.decision_alignment_rate >= criteria["min_decision_alignment"],
            metrics.avg_extra_rounds <= criteria["max_avg_extra_rounds"],
            metrics.total_meetings >= criteria["min_meetings"],
            metrics.total_days >= criteria["min_days"]
        ]
        
        if all(checks):
            metrics.evaluation_status = "ready_for_decision"
            metrics.recommendation = "promote"
        elif metrics.total_meetings >= criteria["min_meetings"] and metrics.total_days >= criteria["min_days"]:
            metrics.evaluation_status = "ready_for_decision"
            # 根据具体问题给出建议
            if metrics.false_block_rate > criteria["max_false_block_rate"]:
                metrics.recommendation = "retune"
            else:
                metrics.recommendation = "extend"
        else:
            metrics.evaluation_status = "pending"
            metrics.recommendation = "pending"
    
    def generate_report(self) -> Dict:
        """生成影子部署报告"""
        metrics = self.calculate_metrics()
        
        report = {
            "shadow_id": self.shadow_id,
            "status": self.status.value,
            "config": self.config,
            "metrics": metrics.to_dict(),
            "acceptance_criteria": self.ACCEPTANCE_CRITERIA,
            "recent_observations": [o.to_dict() for o in self.observations[-10:]]
        }
        
        # 保存报告
        report_path = f"{self.storage_dir}/{self.shadow_id}_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return report
    
    def print_status(self):
        """打印当前状态"""
        metrics = self.calculate_metrics()
        criteria = self.ACCEPTANCE_CRITERIA
        
        print("\n" + "="*60)
        print(f"📊 Shadow Deployment Status: {self.shadow_id}")
        print("="*60)
        print(f"运行时间: {metrics.total_days}天")
        print(f"观察会议: {metrics.total_meetings}/{criteria['min_meetings']}")
        print()
        print("5个核心观察指标:")
        print(f"  1. False-Block Rate:       {metrics.false_block_rate:.1%} "
              f"(门槛: ≤{criteria['max_false_block_rate']:.0%}) "
              f"{'✅' if metrics.false_block_rate <= criteria['max_false_block_rate'] else '⚠️'}")
        print(f"  2. Review Disagreement:    {metrics.review_disagreement_rate:.1%}")
        print(f"  3. Avg Extra Rounds:       {metrics.avg_extra_rounds:.2f} "
              f"(门槛: ≤{criteria['max_avg_extra_rounds']:.1f}) "
              f"{'✅' if metrics.avg_extra_rounds <= criteria['max_avg_extra_rounds'] else '⚠️'}")
        print(f"  4. Human Override Rate:    {metrics.human_override_rate:.1%}")
        # Accepted-risk miss rate
        if metrics.accepted_risk_miss_rate < 0:
            print(f"  5. Accepted-Risk Miss:     待验证 ({metrics.accepted_risk_cases} 案例待追踪)")
        else:
            print(f"  5. Accepted-Risk Miss:     {metrics.accepted_risk_miss_rate:.1%} "
                  f"({metrics.validated_risk_cases}/{metrics.accepted_risk_cases} 已验证)")
        print()
        print(f"决策一致率: {metrics.decision_alignment_rate:.1%} "
              f"(门槛: ≥{criteria['min_decision_alignment']:.0%}) "
              f"{'✅' if metrics.decision_alignment_rate >= criteria['min_decision_alignment'] else '⚠️'}")
        print()
        print("决策矩阵:")
        print(f"  旧批新批: {metrics.both_approved}")
        print(f"  旧拦新拦: {metrics.both_blocked}")
        print(f"  🔴 旧批新拦 (误拦): {metrics.legacy_approved_shadow_blocked}")
        print(f"  🟡 旧拦新批 (漏拦): {metrics.legacy_blocked_shadow_approved}")
        if metrics.accepted_risk_cases > 0:
            print(f"  🚨 高置信风险拦截: {metrics.accepted_risk_cases}")
        print()
        print("样本来源分布:")
        live_total = metrics.live_manual_count + metrics.live_auto_count
        print(f"  真实会议: {live_total} (手动:{metrics.live_manual_count} 自动:{metrics.live_auto_count})")
        if metrics.replay_real_count > 0:
            print(f"  历史回放: {metrics.replay_real_count}")
        if metrics.staged_count > 0:
            print(f"  受控演练: {metrics.staged_count}")
        print()
        if metrics.issue_type_distribution:
            print("议题类型分布:")
            for issue_type, count in sorted(metrics.issue_type_distribution.items()):
                print(f"  - {issue_type}: {count}")
            print()
        if metrics.risk_level_distribution:
            print("风险等级分布:")
            for level, count in sorted(metrics.risk_level_distribution.items()):
                print(f"  - {level}: {count}")
            print()
        print(f"评估状态: {metrics.evaluation_status}")
        print(f"建议动作: {metrics.recommendation}")
        print("="*60)
    
    def validate_risk(self, meeting_id: str, risk_confirmed: bool, notes: str = ""):
        """
        验证 Accepted-risk 案例是否真的暴露问题
        
        Args:
            meeting_id: 会议ID
            risk_confirmed: True=确认有风险, False=误拦
            notes: 验证备注
        """
        for obs in self.observations:
            if obs.meeting_id == meeting_id and obs.accepted_risk_detected:
                obs.risk_validated = risk_confirmed
                obs.validated_at = datetime.now().isoformat()
                obs.notes += f"\n[风险验证] {'确认有风险' if risk_confirmed else '误拦'}: {notes}"
                status = "✅ 确认" if risk_confirmed else "❌ 误拦"
                print(f"  🔍 风险验证记录: {meeting_id} -> {status}")
                self._save_validation_update(obs)
                break
    
    def _save_validation_update(self, observation: ShadowObservation):
        """保存验证更新到日志"""
        filename = f"{self.storage_dir}/{self.shadow_id}_validations.jsonl"
        validation_record = {
            "observation_id": observation.observation_id,
            "meeting_id": observation.meeting_id,
            "risk_validated": observation.risk_validated,
            "validated_at": observation.validated_at,
            "notes": observation.notes
        }
        with open(filename, "a") as f:
            f.write(json.dumps(validation_record, ensure_ascii=False) + "\n")


def demo():
    """演示影子部署框架 - 含 Accepted-risk miss rate"""
    print("="*70)
    print("Shadow Deployment Framework Demo")
    print("影子部署框架演示 (Round 17) - 含 Accepted-risk miss rate")
    print("="*70)
    print("\n⚠️  三条纪律:")
    print("  1. 新系统只记录，不拦截")
    print("  2. 旧系统仍是唯一执行链")
    print("  3. 所有分歧都落日志，不人工挑样本")
    
    # 创建影子部署管理器
    manager = ShadowDeploymentManager(
        shadow_id="SHADOW-20260311-DEMO",
        config=ShadowDeploymentManager.DEFAULT_CONFIG
    )
    
    print("\n--- 模拟 10 个会议的观察 ---\n")
    
    # 模拟会议数据 (添加 shadow_confidence)
    # (meeting_id, legacy, shadow, delib_score, review_score, confidence)
    test_cases = [
        ("MTG-001", "approved", "approved", 85, 88, 0.9),
        ("MTG-002", "approved", "approved", 78, 82, 0.85),
        ("MTG-003", "rejected", "rejected", 45, 42, 0.95),
        ("MTG-004", "approved", "rejected", 72, 68, 0.85),  # 潜在误拦 (高置信)
        ("MTG-005", "approved", "approved", 90, 92, 0.92),
        ("MTG-006", "conditional_approved", "approved", 80, 85, 0.88),
        ("MTG-007", "rejected", "rejected", 30, 35, 0.90),
        ("MTG-008", "approved", "requires_deliberation", 70, 65, 0.88),  # 潜在误拦 (高置信)
        ("MTG-009", "approved", "approved", 88, 90, 0.91),
        ("MTG-010", "rejected", "approved", 75, 80, 0.75),  # 潜在漏拦 (低置信)
    ]
    
    for meeting_id, legacy, shadow, delib_score, review_score, confidence in test_cases:
        gate_checks = [
            {"check_name": "deliberation_minimum", "status": "pass" if delib_score >= 75 else "fail", "score": delib_score},
            {"check_name": "review_minimum", "status": "pass" if review_score >= 80 else "fail", "score": review_score}
        ]
        
        manager.process_meeting(
            meeting_id=meeting_id,
            legacy_decision=legacy,
            shadow_decision=shadow,
            deliberation_score=delib_score,
            review_score=review_score,
            gate_checks=gate_checks,
            shadow_confidence=confidence,
            notes=f"Demo observation for {meeting_id}"
        )
    
    # 记录人工覆盖
    manager.record_human_override(
        meeting_id="MTG-004",
        override_decision="approved",
        reason="业务确认：此提案已通过法务审核，建议批准"
    )
    
    # 打印状态 (此时 accepted-risk 还未验证)
    print("\n--- 初始状态 (待验证 Accepted-risk) ---")
    manager.print_status()
    
    # 模拟后续验证 Accepted-risk 案例
    print("\n--- 30天后验证 Accepted-risk 案例 ---\n")
    
    # MTG-004: 验证为误拦 (实际没问题)
    manager.validate_risk(
        meeting_id="MTG-004",
        risk_confirmed=False,
        notes="30天后复盘：该提案运行正常，无风险暴露"
    )
    
    # MTG-008: 验证为真风险 (实际暴露问题)
    manager.validate_risk(
        meeting_id="MTG-008",
        risk_confirmed=True,
        notes="30天后复盘：该提案执行后出现争议，确认有风险"
    )
    
    # 打印最终状态
    print("\n--- 验证后状态 ---")
    manager.print_status()
    
    # 生成报告
    report = manager.generate_report()
    print(f"\n📄 报告已保存: data/shadow/SHADOW-20260311-DEMO_report.json")
    
    print("\n" + "="*70)
    print("演示完成。真实部署时将：")
    print("  1. 并行运行新旧系统")
    print("  2. 影子系统只记录建议")
    print("  3. 旧系统保持唯一执行权")
    print("  4. 30天后根据指标决定下一步")
    print("="*70)


if __name__ == "__main__":
    demo()

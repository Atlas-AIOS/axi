#!/usr/bin/env python3
"""
Layered Historical Replay Analyzer
分层历史回放分析器 (Round 16.1)

实现验收标准的三个核心指标:
1. False-Block Rate (误拦率)
2. Risk-Intercept Rate (风险拦截率)
3. Deliberation Overhead (协商开销)

并支持按原决策结果、场景类型、拦截点分层分析。
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/rounds/round16')

from historical_replay_verifier import HistoricalMeetingReplayVerifier, ReplayResult, ReplayVerdict


class AcceptanceStatus(Enum):
    """验收状态"""
    PASS = "pass"
    CONDITIONAL = "conditional"
    FAIL = "fail"


@dataclass
class LayeredMetrics:
    """分层指标"""
    # 基础统计
    total_cases: int = 0
    
    # 按原决策分层
    original_approved: int = 0
    original_blocked: int = 0
    original_conditional: int = 0
    original_pending: int = 0
    
    approved_retained: int = 0      # 原approved，回放仍approved
    approved_blocked: int = 0       # 原approved，回放被blocked (误拦)
    blocked_retained: int = 0       # 原blocked，回放仍blocked
    blocked_unblocked: int = 0      # 原blocked，回放通过 (可能漏风险)
    
    # 指标1: False-Block Rate
    false_block_count: int = 0
    false_block_rate: float = 0.0
    false_block_status: str = "unknown"
    
    # 指标2: Risk-Intercept Rate (需要历史风险标注)
    high_risk_cases: int = 0
    high_risk_intercepted: int = 0
    risk_intercept_rate: float = 0.0
    risk_intercept_status: str = "unknown"
    
    # 指标3: Deliberation Overhead
    extra_rounds_cases: int = 0
    extra_rounds_ratio: float = 0.0
    avg_historical_rounds: float = 1.0  # 假设历史平均1轮
    avg_replay_rounds: float = 0.0
    avg_rounds_increase: float = 0.0
    overhead_status: str = "unknown"
    
    # 按场景分层
    by_scenario: Dict[str, Dict] = field(default_factory=dict)
    
    # 按拦截点分层
    intercept_points: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "total_cases": self.total_cases,
            "by_original_decision": {
                "approved": {
                    "total": self.original_approved,
                    "retained": self.approved_retained,
                    "blocked": self.approved_blocked,
                    "retention_rate": self.approved_retained / self.original_approved if self.original_approved > 0 else 0
                },
                "blocked": {
                    "total": self.original_blocked,
                    "retained": self.blocked_retained,
                    "unblocked": self.blocked_unblocked,
                    "retention_rate": self.blocked_retained / self.original_blocked if self.original_blocked > 0 else 0
                }
            },
            "metrics": {
                "false_block_rate": {
                    "value": self.false_block_rate,
                    "status": self.false_block_status,
                    "threshold": "≤ 15%"
                },
                "risk_intercept_rate": {
                    "value": self.risk_intercept_rate,
                    "status": self.risk_intercept_status,
                    "threshold": "≥ 70%"
                },
                "deliberation_overhead": {
                    "extra_rounds_ratio": {
                        "value": self.extra_rounds_ratio,
                        "threshold": "≤ 40%"
                    },
                    "avg_rounds_increase": {
                        "value": self.avg_rounds_increase,
                        "threshold": "≤ 1.0"
                    },
                    "status": self.overhead_status
                }
            },
            "by_scenario": self.by_scenario,
            "intercept_points": self.intercept_points
        }


@dataclass
class AcceptanceReport:
    """验收报告"""
    report_id: str
    timestamp: str
    
    # 指标
    metrics: LayeredMetrics
    
    # 综合判定
    overall_status: AcceptanceStatus = AcceptanceStatus.FAIL
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[str] = field(default_factory=list)
    conditional_checks: List[str] = field(default_factory=list)
    
    # 详细发现
    key_findings: List[str] = field(default_factory=list)
    risk_cases: List[str] = field(default_factory=list)  # 可能漏掉的风险
    
    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "metrics": self.metrics.to_dict(),
            "checks": {
                "passed": self.passed_checks,
                "failed": self.failed_checks,
                "conditional": self.conditional_checks
            },
            "key_findings": self.key_findings,
            "risk_cases": self.risk_cases
        }


class LayeredReplayAnalyzer:
    """
    分层回放分析器
    
    实现验收标准的完整分析逻辑
    """
    
    # 验收门槛
    THRESHOLDS = {
        'false_block_rate_max': 0.15,           # 15%
        'false_block_rate_conditional': 0.25,   # 25%
        'risk_intercept_rate_min': 0.70,        # 70%
        'risk_intercept_rate_conditional': 0.50, # 50%
        'extra_rounds_ratio_max': 0.40,         # 40%
        'extra_rounds_ratio_conditional': 0.60, # 60%
        'avg_rounds_increase_max': 1.0,
        'avg_rounds_increase_conditional': 2.0,
        'approved_retention_min': 0.75,         # 75%
        'blocked_retention_min': 0.80           # 80%
    }
    
    # 场景风险等级 (基于经验)
    SCENARIO_RISK = {
        'strong_opposition': 'high',
        'opposition_with_veto': 'high',
        'strong_support': 'low',
        'overwhelming_support': 'low',
        'moderate_support': 'medium',
        'balanced': 'medium',
        'conditional_heavy': 'medium'
    }
    
    def __init__(self, verifier: HistoricalMeetingReplayVerifier = None):
        self.verifier = verifier or HistoricalMeetingReplayVerifier()
        self.results: List[ReplayResult] = []
        self.metrics: Optional[LayeredMetrics] = None
        self.report: Optional[AcceptanceReport] = None
    
    def load_and_replay(self, max_cases: int = 200) -> List[ReplayResult]:
        """加载并回放案例"""
        # 使用基础 verifier 进行回放
        self.verifier.run_full_replay(max_cases=max_cases)
        self.results = self.verifier.report.results if self.verifier.report else []
        return self.results
    
    def load_existing_results(self, results: List[ReplayResult]):
        """加载已有的回放结果"""
        self.results = results
    
    def analyze(self) -> LayeredMetrics:
        """
        执行完整分析
        
        Returns:
            LayeredMetrics
        """
        metrics = LayeredMetrics()
        metrics.total_cases = len(self.results)
        
        if metrics.total_cases == 0:
            return metrics
        
        # 1. 按原决策分层统计
        self._analyze_by_original_decision(metrics)
        
        # 2. 计算 False-Block Rate
        self._calculate_false_block_rate(metrics)
        
        # 3. 计算 Risk-Intercept Rate
        self._calculate_risk_intercept_rate(metrics)
        
        # 4. 计算 Deliberation Overhead
        self._calculate_deliberation_overhead(metrics)
        
        # 5. 按场景分层
        self._analyze_by_scenario(metrics)
        
        # 6. 按拦截点分层
        self._analyze_intercept_points(metrics)
        
        self.metrics = metrics
        return metrics
    
    def _analyze_by_original_decision(self, metrics: LayeredMetrics):
        """按原决策结果分析"""
        for result in self.results:
            original = result.original_status
            replay = result.replay_status
            
            if original == 'approved':
                metrics.original_approved += 1
                if replay == 'approved':
                    metrics.approved_retained += 1
                else:
                    metrics.approved_blocked += 1
                    metrics.false_block_count += 1
                    
            elif original in ['blocked', 'rejected']:
                metrics.original_blocked += 1
                if replay in ['blocked', 'rejected']:
                    metrics.blocked_retained += 1
                else:
                    metrics.blocked_unblocked += 1
                    
            elif original == 'conditional':
                metrics.original_conditional += 1
                
            elif original == 'pending':
                metrics.original_pending += 1
    
    def _calculate_false_block_rate(self, metrics: LayeredMetrics):
        """计算误拦率"""
        if metrics.original_approved > 0:
            metrics.false_block_rate = metrics.false_block_count / metrics.original_approved
        else:
            metrics.false_block_rate = 0.0
        
        # 判定状态
        if metrics.false_block_rate <= self.THRESHOLDS['false_block_rate_max']:
            metrics.false_block_status = 'pass'
        elif metrics.false_block_rate <= self.THRESHOLDS['false_block_rate_conditional']:
            metrics.false_block_status = 'conditional'
        else:
            metrics.false_block_status = 'fail'
    
    def _calculate_risk_intercept_rate(self, metrics: LayeredMetrics):
        """计算风险拦截率"""
        # 基于场景类型推断风险等级
        for result in self.results:
            # 从历史案例中提取场景
            scenario = self._get_scenario(result.case_id)
            risk_level = self.SCENARIO_RISK.get(scenario, 'medium')
            
            if risk_level in ['high', 'medium']:
                metrics.high_risk_cases += 1
                if result.replay_status in ['blocked', 'rejected']:
                    metrics.high_risk_intercepted += 1
        
        if metrics.high_risk_cases > 0:
            metrics.risk_intercept_rate = metrics.high_risk_intercepted / metrics.high_risk_cases
        else:
            metrics.risk_intercept_rate = 0.0
        
        # 判定状态
        if metrics.risk_intercept_rate >= self.THRESHOLDS['risk_intercept_rate_min']:
            metrics.risk_intercept_status = 'pass'
        elif metrics.risk_intercept_rate >= self.THRESHOLDS['risk_intercept_rate_conditional']:
            metrics.risk_intercept_status = 'conditional'
        else:
            metrics.risk_intercept_status = 'fail'
    
    def _calculate_deliberation_overhead(self, metrics: LayeredMetrics):
        """计算协商开销"""
        total_rounds = 0
        
        for result in self.results:
            total_rounds += result.deliberation_rounds
            if result.deliberation_rounds > 1:
                metrics.extra_rounds_cases += 1
        
        metrics.avg_replay_rounds = total_rounds / len(self.results) if self.results else 0
        metrics.avg_rounds_increase = metrics.avg_replay_rounds - metrics.avg_historical_rounds
        metrics.extra_rounds_ratio = metrics.extra_rounds_cases / len(self.results) if self.results else 0
        
        # 判定状态 (综合三个子指标)
        extra_rounds_pass = metrics.extra_rounds_ratio <= self.THRESHOLDS['extra_rounds_ratio_max']
        avg_increase_pass = metrics.avg_rounds_increase <= self.THRESHOLDS['avg_rounds_increase_max']
        
        if extra_rounds_pass and avg_increase_pass:
            metrics.overhead_status = 'pass'
        elif (metrics.extra_rounds_ratio <= self.THRESHOLDS['extra_rounds_ratio_conditional'] and
              metrics.avg_rounds_increase <= self.THRESHOLDS['avg_rounds_increase_conditional']):
            metrics.overhead_status = 'conditional'
        else:
            metrics.overhead_status = 'fail'
    
    def _analyze_by_scenario(self, metrics: LayeredMetrics):
        """按场景类型分析"""
        scenario_stats: Dict[str, Dict] = {}
        
        for result in self.results:
            scenario = self._get_scenario(result.case_id)
            
            if scenario not in scenario_stats:
                scenario_stats[scenario] = {
                    'total': 0,
                    'unchanged': 0,
                    'blocked': 0,
                    'approved': 0
                }
            
            scenario_stats[scenario]['total'] += 1
            
            if result.verdict == ReplayVerdict.UNCHANGED:
                scenario_stats[scenario]['unchanged'] += 1
            
            if result.replay_status == 'blocked':
                scenario_stats[scenario]['blocked'] += 1
            elif result.replay_status == 'approved':
                scenario_stats[scenario]['approved'] += 1
        
        metrics.by_scenario = scenario_stats
    
    def _analyze_intercept_points(self, metrics: LayeredMetrics):
        """分析拦截点分布"""
        points = {
            'goal_alignment': 0,
            'deliberation_low_score': 0,
            'third_party_review': 0,
            'decision_gate': 0
        }
        
        for result in self.results:
            if result.replay_status != 'blocked':
                continue
            
            # 根据特征推断拦截点
            if not result.alignment_passed:
                points['goal_alignment'] += 1
            elif result.review_score < 95 and not result.review_passed:
                points['third_party_review'] += 1
            elif result.deliberation_rounds >= 2:
                points['deliberation_low_score'] += 1
            else:
                points['decision_gate'] += 1
        
        metrics.intercept_points = points
    
    def _get_scenario(self, case_id: str) -> str:
        """从案例ID获取场景类型"""
        # 尝试从 verifier 的 cases 中查找
        for case in self.verifier.cases:
            if case.get('case_id') == case_id:
                return case.get('scenario', 'unknown')
        return 'unknown'
    
    def generate_acceptance_report(self) -> AcceptanceReport:
        """生成验收报告"""
        if self.metrics is None:
            self.analyze()
        
        metrics = self.metrics
        report = AcceptanceReport(
            report_id=f"acceptance_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            metrics=metrics
        )
        
        # 评估各项检查
        self._evaluate_checks(report)
        
        # 生成关键发现
        self._generate_findings(report)
        
        # 识别风险案例
        self._identify_risk_cases(report)
        
        # 综合判定
        self._determine_overall_status(report)
        
        self.report = report
        return report
    
    def _evaluate_checks(self, report: AcceptanceReport):
        """评估各项检查"""
        m = self.metrics
        t = self.THRESHOLDS
        
        # False-Block Rate
        if m.false_block_status == 'pass':
            report.passed_checks.append(f"False-Block Rate: {m.false_block_rate:.1%} ≤ {t['false_block_rate_max']:.0%}")
        elif m.false_block_status == 'conditional':
            report.conditional_checks.append(f"False-Block Rate: {m.false_block_rate:.1%} (threshold: {t['false_block_rate_max']:.0%})")
        else:
            report.failed_checks.append(f"False-Block Rate: {m.false_block_rate:.1%} > {t['false_block_rate_max']:.0%}")
        
        # Risk-Intercept Rate
        if m.risk_intercept_status == 'pass':
            report.passed_checks.append(f"Risk-Intercept Rate: {m.risk_intercept_rate:.1%} ≥ {t['risk_intercept_rate_min']:.0%}")
        elif m.risk_intercept_status == 'conditional':
            report.conditional_checks.append(f"Risk-Intercept Rate: {m.risk_intercept_rate:.1%} (threshold: {t['risk_intercept_rate_min']:.0%})")
        else:
            report.failed_checks.append(f"Risk-Intercept Rate: {m.risk_intercept_rate:.1%} < {t['risk_intercept_rate_min']:.0%}")
        
        # Approved Retention
        retention_rate = m.approved_retained / m.original_approved if m.original_approved > 0 else 0
        if retention_rate >= t['approved_retention_min']:
            report.passed_checks.append(f"Approved Retention: {retention_rate:.1%} ≥ {t['approved_retention_min']:.0%}")
        else:
            report.failed_checks.append(f"Approved Retention: {retention_rate:.1%} < {t['approved_retention_min']:.0%}")
        
        # Blocked Retention
        blocked_retention = m.blocked_retained / m.original_blocked if m.original_blocked > 0 else 0
        if blocked_retention >= t['blocked_retention_min']:
            report.passed_checks.append(f"Blocked Retention: {blocked_retention:.1%} ≥ {t['blocked_retention_min']:.0%}")
        else:
            report.conditional_checks.append(f"Blocked Retention: {blocked_retention:.1%} (threshold: {t['blocked_retention_min']:.0%})")
        
        # Deliberation Overhead
        if m.overhead_status == 'pass':
            report.passed_checks.append(f"Deliberation Overhead: Extra rounds {m.extra_rounds_ratio:.1%}, Avg increase {m.avg_rounds_increase:.1f}")
        else:
            report.failed_checks.append(f"Deliberation Overhead: Extra rounds {m.extra_rounds_ratio:.1%}, Avg increase {m.avg_rounds_increase:.1f}")
    
    def _generate_findings(self, report: AcceptanceReport):
        """生成关键发现"""
        m = self.metrics
        
        # 一致性分析
        unchanged = len([r for r in self.results if r.verdict == ReplayVerdict.UNCHANGED])
        consistency = unchanged / len(self.results) if self.results else 0
        report.key_findings.append(f"Overall consistency: {consistency:.1%} ({unchanged}/{len(self.results)})")
        
        # 误拦分析
        if m.false_block_count > 0:
            report.key_findings.append(f"False blocks: {m.false_block_count} approved cases were blocked")
        
        # 风险拦截分析
        report.key_findings.append(f"High-risk intercept: {m.high_risk_intercepted}/{m.high_risk_cases} ({m.risk_intercept_rate:.1%})")
        
        # 场景分析
        for scenario, stats in m.by_scenario.items():
            if stats['total'] >= 5:
                block_rate = stats['blocked'] / stats['total']
                report.key_findings.append(f"Scenario '{scenario}': {block_rate:.1%} blocked ({stats['blocked']}/{stats['total']})")
        
        # 拦截点分析
        total_blocked = sum(m.intercept_points.values())
        if total_blocked > 0:
            for point, count in m.intercept_points.items():
                ratio = count / total_blocked
                report.key_findings.append(f"Intercept at {point}: {ratio:.1%} ({count}/{total_blocked})")
    
    def _identify_risk_cases(self, report: AcceptanceReport):
        """识别风险案例"""
        # 识别可能被漏掉的风险 (原blocked，回放通过)
        for result in self.results:
            if result.original_status in ['blocked', 'rejected'] and result.replay_status == 'approved':
                report.risk_cases.append(f"{result.case_id}: Originally blocked but approved in replay")
    
    def _determine_overall_status(self, report: AcceptanceReport):
        """确定综合状态"""
        # 一票否决条件
        if self.metrics.false_block_rate > 0.30:
            report.overall_status = AcceptanceStatus.FAIL
            return
        
        if self.metrics.risk_intercept_rate < 0.40:
            report.overall_status = AcceptanceStatus.FAIL
            return
        
        # 强制通过条件
        must_pass = [
            self.metrics.false_block_status == 'pass',
            self.metrics.risk_intercept_status == 'pass',
            self.metrics.overhead_status == 'pass',
            len(report.failed_checks) == 0
        ]
        
        if all(must_pass):
            report.overall_status = AcceptanceStatus.PASS
        elif len(report.failed_checks) > 0:
            report.overall_status = AcceptanceStatus.FAIL
        else:
            report.overall_status = AcceptanceStatus.CONDITIONAL
    
    def print_report(self):
        """打印报告"""
        if self.report is None:
            print("No report available. Run generate_acceptance_report() first.")
            return
        
        r = self.report
        m = r.metrics
        
        print("\n" + "=" * 80)
        print("Layered Replay Acceptance Report")
        print("=" * 80)
        print(f"Report ID: {r.report_id}")
        print(f"Timestamp: {r.timestamp}")
        print(f"Total Cases: {m.total_cases}")
        print(f"\n{'🟢' if r.overall_status == AcceptanceStatus.PASS else '🟡' if r.overall_status == AcceptanceStatus.CONDITIONAL else '🔴'} Overall Status: {r.overall_status.value.upper()}")
        
        print("\n" + "-" * 80)
        print("Metrics Summary")
        print("-" * 80)
        
        print(f"\n1. False-Block Rate: {m.false_block_rate:.1%}")
        print(f"   Status: {m.false_block_status.upper()}")
        print(f"   Detail: {m.false_block_count}/{m.original_approved} approved cases blocked")
        
        print(f"\n2. Risk-Intercept Rate: {m.risk_intercept_rate:.1%}")
        print(f"   Status: {m.risk_intercept_status.upper()}")
        print(f"   Detail: {m.high_risk_intercepted}/{m.high_risk_cases} high-risk cases intercepted")
        
        print(f"\n3. Deliberation Overhead:")
        print(f"   Status: {m.overhead_status.upper()}")
        print(f"   Extra Rounds Ratio: {m.extra_rounds_ratio:.1%}")
        print(f"   Avg Rounds Increase: {m.avg_rounds_increase:.1f}")
        
        print("\n" + "-" * 80)
        print("Layered Analysis")
        print("-" * 80)
        
        print(f"\nBy Original Decision:")
        if m.original_approved > 0:
            retention = m.approved_retained / m.original_approved
            print(f"  Approved -> Approved: {retention:.1%} ({m.approved_retained}/{m.original_approved})")
            print(f"  Approved -> Blocked:  {m.false_block_rate:.1%} ({m.approved_blocked}/{m.original_approved})")
        if m.original_blocked > 0:
            retention = m.blocked_retained / m.original_blocked
            print(f"  Blocked -> Blocked:   {retention:.1%} ({m.blocked_retained}/{m.original_blocked})")
            print(f"  Blocked -> Approved:  {m.blocked_unblocked} cases (potential risk)")
        
        print("\n" + "-" * 80)
        print("Checks")
        print("-" * 80)
        
        if r.passed_checks:
            print("\n✅ Passed:")
            for check in r.passed_checks:
                print(f"  • {check}")
        
        if r.conditional_checks:
            print("\n⚠️  Conditional:")
            for check in r.conditional_checks:
                print(f"  • {check}")
        
        if r.failed_checks:
            print("\n❌ Failed:")
            for check in r.failed_checks:
                print(f"  • {check}")
        
        print("\n" + "-" * 80)
        print("Key Findings")
        print("-" * 80)
        for finding in r.key_findings:
            print(f"  • {finding}")
        
        if r.risk_cases:
            print("\n⚠️  Risk Cases (potential misses):")
            for case in r.risk_cases[:5]:  # 最多显示5个
                print(f"  • {case}")
            if len(r.risk_cases) > 5:
                print(f"  ... and {len(r.risk_cases) - 5} more")
        
        print("\n" + "=" * 80)
    
    def export_report(self, filepath: str = None) -> str:
        """导出报告"""
        if self.report is None:
            raise ValueError("No report available.")
        
        if filepath is None:
            filepath = f"/home/admin/CodeBuddy/20260310101858/data/acceptance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.report.to_dict(), f, indent=2, ensure_ascii=False)
        
        return filepath


# 演示
if __name__ == "__main__":
    print("=" * 80)
    print("Layered Replay Analyzer - Demo")
    print("=" * 80)
    
    # 创建分析器
    analyzer = LayeredReplayAnalyzer()
    
    # 加载并回放
    print("\n📚 Loading and replaying cases...")
    analyzer.load_and_replay(max_cases=50)
    
    # 执行分析
    print("\n🔍 Analyzing metrics...")
    metrics = analyzer.analyze()
    
    # 生成验收报告
    print("\n📋 Generating acceptance report...")
    report = analyzer.generate_acceptance_report()
    
    # 打印报告
    analyzer.print_report()
    
    # 导出
    filepath = analyzer.export_report()
    print(f"\n📄 Report exported to: {filepath}")

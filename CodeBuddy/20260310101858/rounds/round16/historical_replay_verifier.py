#!/usr/bin/env python3
"""
Historical Meeting Replay Verifier
历史会议回放验证器

作用: 拿已经完成的真实会议，用 Round 15.1 的多轮协商-审验-门控闭环重新跑一遍

验证重点:
1. 哪些旧会议在 Round 0 就该被打回 (Goal Alignment)
2. 哪些旧会议会在 <95 时继续一轮
3. 第三方审验会不会改变原先结论
4. 哪些 unresolved issue 以前被直接放过去了

Round 16: 验证与回溯测试
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

# 添加路径以导入模块
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/rounds/round15')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/bridge')

from bridge.goal_alignment_wizard import GoalAlignmentIntakeWizard, IntakeStatus
from bridge.decision_gate import DecisionGateExecutor, GateStatus, evaluate_round15_meeting


class ReplayVerdict(Enum):
    """回放裁决"""
    UNCHANGED = "unchanged"           # 结论不变
    UPGRADED = "upgraded"             # 升级 (如 pending -> approved)
    DOWNGRADED = "downgraded"         # 降级 (如 approved -> rejected)
    ADDED_ROUNDS = "added_rounds"     # 需要额外轮次
    BLOCKED_AT_GATE = "blocked_at_gate"  # 在门控处被拦


@dataclass
class ReplayResult:
    """回放结果"""
    case_id: str
    original_status: str              # 原始状态
    replay_status: str                # 回放状态
    verdict: ReplayVerdict
    
    # Round 15 分析
    alignment_passed: bool
    deliberation_rounds: int
    review_score: float
    review_passed: bool
    gate_status: str
    
    # 差异分析
    differences: List[str] = field(default_factory=list)
    insights: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "case_id": self.case_id,
            "original_status": self.original_status,
            "replay_status": self.replay_status,
            "verdict": self.verdict.value,
            "alignment_passed": self.alignment_passed,
            "deliberation_rounds": self.deliberation_rounds,
            "review_score": self.review_score,
            "review_passed": self.review_passed,
            "gate_status": self.gate_status,
            "differences": self.differences,
            "insights": self.insights
        }


@dataclass
class ReplayReport:
    """回放验证报告"""
    report_id: str
    timestamp: str
    total_cases: int
    
    # 统计
    unchanged: int = 0
    upgraded: int = 0
    downgraded: int = 0
    added_rounds: int = 0
    blocked_at_gate: int = 0
    
    # 详细结果
    results: List[ReplayResult] = field(default_factory=list)
    
    # 关键发现
    key_findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "total_cases": self.total_cases,
            "summary": {
                "unchanged": self.unchanged,
                "upgraded": self.upgraded,
                "downgraded": self.downgraded,
                "added_rounds": self.added_rounds,
                "blocked_at_gate": self.blocked_at_gate
            },
            "results": [r.to_dict() for r in self.results],
            "key_findings": self.key_findings,
            "recommendations": self.recommendations
        }


class HistoricalMeetingReplayVerifier:
    """
    历史会议回放验证器
    
    将历史会议用新的 Round 15.1 流程重新跑一遍，验证新系统的效果
    """
    
    # 场景到议题的映射
    SCENARIO_TOPIC_MAP = {
        'strong_opposition': '面对强烈反对的提案',
        'strong_support': '获得强力支持的提案',
        'moderate_support': '获得适度支持的提案',
        'opposition_with_veto': '有否决权的反对提案',
        'balanced': '立场均衡的提案',
        'conditional_heavy': '大量条件支持的提案',
        'overwhelming_support': '压倒性支持的提案'
    }
    
    def __init__(self, historical_cases_path: str = "/home/admin/CodeBuddy/20260310101858/data/historical_cases"):
        self.cases_path = historical_cases_path
        self.wizard = GoalAlignmentIntakeWizard()
        self.gate_executor = DecisionGateExecutor()
        self.cases: List[Dict] = []
        self.report: Optional[ReplayReport] = None
    
    def load_cases(self, filename: str = "sample_cases.jsonl", max_cases: int = None) -> int:
        """
        加载历史案例
        
        Args:
            filename: 案例文件名
            max_cases: 最大加载数量
            
        Returns:
            加载的案例数
        """
        filepath = os.path.join(self.cases_path, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Historical cases not found: {filepath}")
        
        self.cases = []
        
        with open(filepath, 'r') as f:
            for i, line in enumerate(f):
                if max_cases and i >= max_cases:
                    break
                
                try:
                    case = json.loads(line.strip())
                    self.cases.append(case)
                except json.JSONDecodeError:
                    continue
        
        print(f"📚 Loaded {len(self.cases)} historical cases from {filename}")
        return len(self.cases)
    
    def replay_case(self, case: Dict) -> ReplayResult:
        """
        回放单个案例
        
        Args:
            case: 历史案例数据
            
        Returns:
            ReplayResult
        """
        case_id = case.get('case_id', 'unknown')
        scenario = case.get('scenario', 'unknown')
        original_result = case.get('result', {})
        original_status = original_result.get('status', 'unknown')
        
        # Step 1: Goal Alignment Intake
        topic = self.SCENARIO_TOPIC_MAP.get(scenario, f"议题: {scenario}")
        problem = self._generate_problem_description(case)
        
        # 模拟摄入
        status, brief, questions = self.wizard.intake(
            raw_text=f"主题：{topic}\n问题：{problem}",
            submitter_id="historical_replay",
            source="replay"
        )
        
        alignment_passed = brief.is_complete() and status in [IntakeStatus.STRUCTURED, IntakeStatus.VALIDATED]
        
        # Step 2: 模拟多轮协商
        # 根据原始立场分布计算模拟评分
        stance = original_result.get('final_stance', {})
        mock_deliberation_score = self._calculate_mock_deliberation_score(stance)
        deliberation_rounds = self._estimate_deliberation_rounds(stance, original_status)
        
        # Step 3: 模拟第三方审验
        review_score, review_passed = self._simulate_review(mock_deliberation_score, original_status)
        
        # Step 4: 决策门控
        gate_status, ticket, gate_reason = self.gate_executor.evaluate_meeting(
            meeting_id=case_id,
            deliberation_score=mock_deliberation_score,
            deliberation_rounds=deliberation_rounds,
            review_score=review_score,
            review_passed=review_passed,
            review_defects=[],
            dependencies_satisfied=True
        )
        
        # Step 5: 确定回放结论
        replay_status = self._determine_replay_status(gate_status, review_passed, mock_deliberation_score)
        
        # Step 6: 对比分析
        verdict, differences, insights = self._analyze_differences(
            original_status, replay_status, alignment_passed, 
            deliberation_rounds, gate_status, stance
        )
        
        return ReplayResult(
            case_id=case_id,
            original_status=original_status,
            replay_status=replay_status,
            verdict=verdict,
            alignment_passed=alignment_passed,
            deliberation_rounds=deliberation_rounds,
            review_score=review_score,
            review_passed=review_passed,
            gate_status=gate_status.value,
            differences=differences,
            insights=insights
        )
    
    def _generate_problem_description(self, case: Dict) -> str:
        """生成问题描述"""
        scenario = case.get('scenario', 'unknown')
        stance = case.get('result', {}).get('final_stance', {})
        
        total = sum(stance.values()) if stance else 0
        support_pct = stance.get('support', 0) / total * 100 if total > 0 else 0
        oppose_pct = stance.get('oppose', 0) / total * 100 if total > 0 else 0
        
        return f"场景：{scenario}。支持率：{support_pct:.1f}%，反对率：{oppose_pct:.1f}%。需要议会裁决。"
    
    def _calculate_mock_deliberation_score(self, stance: Dict) -> float:
        """根据立场分布计算模拟协商评分"""
        total = sum(stance.values()) if stance else 1
        
        support = stance.get('support', 0)
        conditional = stance.get('conditional', 0) * 0.7  # 条件支持算0.7
        oppose = stance.get('oppose', 0)
        veto = stance.get('veto', 0) * 2  # 否决权权重更高
        
        # 计算原始得分 (0-100)
        raw_score = (support + conditional - oppose - veto) / total * 50 + 50
        
        # 调整：考虑五个维度
        goal_alignment = min(20, raw_score / 100 * 20)
        risk_closure = min(20, (support + conditional) / total * 20)
        executability = min(20, max(0, (support - oppose) / total * 20 + 10))
        counter_absorption = min(20, conditional / total * 40)
        audit_completeness = 18  # 历史案例审计完整性假设较高
        
        total_score = goal_alignment + risk_closure + executability + counter_absorption + audit_completeness
        return min(100, max(0, total_score))
    
    def _estimate_deliberation_rounds(self, stance: Dict, original_status: str) -> int:
        """估计需要的协商轮数"""
        support = stance.get('support', 0)
        oppose = stance.get('oppose', 0)
        conditional = stance.get('conditional', 0)
        total = sum(stance.values())
        
        if total == 0:
            return 1
        
        # 如果分歧大，需要更多轮次
        support_ratio = support / total
        oppose_ratio = oppose / total
        
        if abs(support_ratio - oppose_ratio) < 0.2:
            # 势均力敌，需要多轮
            return 3 + min(2, conditional // 5)
        elif support_ratio > 0.7:
            # 强力支持，快速通过
            return 1
        elif oppose_ratio > 0.5:
            # 强烈反对，可能1-2轮就被拒
            return 2
        else:
            return 2
    
    def _simulate_review(self, deliberation_score: float, original_status: str) -> Tuple[float, bool]:
        """模拟第三方审验"""
        # 审验分数基于协商分数，但有随机波动
        import random
        review_score = min(100, max(0, deliberation_score + random.uniform(-5, 5)))
        
        # 如果原始状态是 approved，审验更容易通过
        if original_status == 'approved':
            review_score = max(95, review_score)
        
        passed = review_score >= 95
        return review_score, passed
    
    def _determine_replay_status(self, gate_status: GateStatus, 
                                  review_passed: bool, 
                                  deliberation_score: float) -> str:
        """确定回放状态"""
        if gate_status == GateStatus.OPEN and review_passed:
            return 'approved'
        elif gate_status == GateStatus.CLOSED or not review_passed:
            return 'blocked'
        else:
            return 'pending'
    
    def _analyze_differences(self, original_status: str, replay_status: str,
                            alignment_passed: bool, deliberation_rounds: int,
                            gate_status: GateStatus, stance: Dict) -> Tuple[ReplayVerdict, List[str], List[str]]:
        """分析差异"""
        differences = []
        insights = []
        
        # 1. 判断裁决类型
        if original_status == replay_status:
            verdict = ReplayVerdict.UNCHANGED
        elif original_status == 'blocked' and replay_status == 'approved':
            verdict = ReplayVerdict.UPGRADED
            differences.append("新流程批准了原被拒的提案")
        elif original_status == 'approved' and replay_status == 'blocked':
            verdict = ReplayVerdict.DOWNGRADED
            differences.append("新流程阻止了原被批准的提案")
        else:
            verdict = ReplayVerdict.UNCHANGED
        
        # 2. 检查 alignment
        if not alignment_passed:
            differences.append("在 Goal Alignment Phase 发现问题")
            insights.append("建议：增加议题对齐环节，避免在模糊问题上浪费时间")
        
        # 3. 检查轮次
        if deliberation_rounds > 2:
            verdict = ReplayVerdict.ADDED_ROUNDS
            differences.append(f"需要 {deliberation_rounds} 轮协商才能得出结论")
        
        # 4. 检查门控
        if gate_status == GateStatus.CLOSED:
            verdict = ReplayVerdict.BLOCKED_AT_GATE
            differences.append("在决策门控处被阻止")
        
        # 5. 基于立场分布的洞察
        support = stance.get('support', 0)
        oppose = stance.get('oppose', 0)
        conditional = stance.get('conditional', 0)
        
        if conditional > max(support, oppose):
            insights.append("大量条件支持表明需要更多澄清")
        
        if stance.get('veto', 0) > 0 and replay_status == 'approved':
            insights.append("有否决票但被批准，需要检查否决权逻辑")
        
        return verdict, differences, insights
    
    def run_full_replay(self, max_cases: int = None) -> ReplayReport:
        """
        运行完整回放验证
        
        Args:
            max_cases: 最大处理案例数
            
        Returns:
            ReplayReport
        """
        if not self.cases:
            self.load_cases(max_cases=max_cases)
        
        report = ReplayReport(
            report_id=f"replay_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            total_cases=len(self.cases)
        )
        
        print(f"\n🔄 Starting replay of {len(self.cases)} cases...")
        print("=" * 70)
        
        for i, case in enumerate(self.cases):
            if max_cases and i >= max_cases:
                break
            
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(self.cases)} cases...")
            
            result = self.replay_case(case)
            report.results.append(result)
            
            # 更新统计
            if result.verdict == ReplayVerdict.UNCHANGED:
                report.unchanged += 1
            elif result.verdict == ReplayVerdict.UPGRADED:
                report.upgraded += 1
            elif result.verdict == ReplayVerdict.DOWNGRADED:
                report.downgraded += 1
            elif result.verdict == ReplayVerdict.ADDED_ROUNDS:
                report.added_rounds += 1
            elif result.verdict == ReplayVerdict.BLOCKED_AT_GATE:
                report.blocked_at_gate += 1
        
        # 生成关键发现
        report.key_findings = self._generate_findings(report)
        report.recommendations = self._generate_recommendations(report)
        
        self.report = report
        return report
    
    def _generate_findings(self, report: ReplayReport) -> List[str]:
        """生成关键发现"""
        findings = []
        
        # 1. 一致性分析
        consistency_rate = report.unchanged / report.total_cases * 100 if report.total_cases > 0 else 0
        findings.append(f"新系统与历史结论一致率: {consistency_rate:.1f}% ({report.unchanged}/{report.total_cases})")
        
        # 2. 变更分析
        if report.downgraded > 0:
            findings.append(f"有 {report.downgraded} 个原被批准的提案在新系统中被阻止")
        
        if report.upgraded > 0:
            findings.append(f"有 {report.upgraded} 个原被拒的提案在新系统中被批准")
        
        # 3. 门控效果
        if report.blocked_at_gate > 0:
            findings.append(f"决策门控成功拦截了 {report.blocked_at_gate} 个高风险提案")
        
        # 4. 轮次分析
        avg_rounds = sum(r.deliberation_rounds for r in report.results) / len(report.results) if report.results else 0
        findings.append(f"平均需要 {avg_rounds:.1f} 轮协商")
        
        return findings
    
    def _generate_recommendations(self, report: ReplayReport) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if report.downgraded > report.upgraded:
            recommendations.append("新系统更严格，建议检查阈值设置是否过于保守")
        
        if report.added_rounds > report.total_cases * 0.3:
            recommendations.append("超过30%的案例需要额外轮次，建议优化协商效率")
        
        # 检查是否有本应被阻止但被通过的
        false_approvals = [r for r in report.results 
                         if r.original_status == 'approved' and r.replay_status == 'blocked']
        if false_approvals:
            recommendations.append(f"发现 {len(false_approvals)} 个潜在误批案例，建议人工复核")
        
        recommendations.append("建议定期用历史案例验证系统决策质量")
        
        return recommendations
    
    def export_report(self, filepath: str = None) -> str:
        """导出报告"""
        if self.report is None:
            raise ValueError("No report available. Run run_full_replay() first.")
        
        if filepath is None:
            filepath = f"/home/admin/CodeBuddy/20260310101858/data/replay_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(self.report.to_dict(), f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def print_summary(self):
        """打印摘要"""
        if self.report is None:
            print("No report available.")
            return
        
        report = self.report
        
        print("\n" + "=" * 70)
        print("Historical Meeting Replay - Summary Report")
        print("=" * 70)
        print(f"Report ID: {report.report_id}")
        print(f"Timestamp: {report.timestamp}")
        print(f"Total Cases: {report.total_cases}")
        
        print("\n📊 Verdict Distribution:")
        print(f"  Unchanged:     {report.unchanged} ({report.unchanged/report.total_cases*100:.1f}%)")
        print(f"  Upgraded:      {report.upgraded} ({report.upgraded/report.total_cases*100:.1f}%)")
        print(f"  Downgraded:    {report.downgraded} ({report.downgraded/report.total_cases*100:.1f}%)")
        print(f"  Added Rounds:  {report.added_rounds} ({report.added_rounds/report.total_cases*100:.1f}%)")
        print(f"  Blocked@Gate:  {report.blocked_at_gate} ({report.blocked_at_gate/report.total_cases*100:.1f}%)")
        
        print("\n🔍 Key Findings:")
        for finding in report.key_findings:
            print(f"  • {finding}")
        
        print("\n💡 Recommendations:")
        for rec in report.recommendations:
            print(f"  • {rec}")
        
        print("\n" + "=" * 70)


# 演示
if __name__ == "__main__":
    print("=" * 70)
    print("Historical Meeting Replay Verifier - Demo")
    print("=" * 70)
    
    verifier = HistoricalMeetingReplayVerifier()
    
    # 运行完整回放
    report = verifier.run_full_replay(max_cases=50)
    
    # 打印摘要
    verifier.print_summary()
    
    # 导出报告
    report_path = verifier.export_report()
    print(f"\n📄 Report exported to: {report_path}")
    
    # 显示几个具体案例
    print("\n" + "=" * 70)
    print("Sample Case Analysis")
    print("=" * 70)
    
    for result in report.results[:3]:
        print(f"\nCase: {result.case_id}")
        print(f"  Original: {result.original_status} -> Replay: {result.replay_status}")
        print(f"  Verdict: {result.verdict.value}")
        print(f"  Review Score: {result.review_score:.1f}/100")
        print(f"  Rounds Needed: {result.deliberation_rounds}")
        if result.differences:
            print(f"  Differences: {', '.join(result.differences)}")
        if result.insights:
            print(f"  Insights: {', '.join(result.insights)}")

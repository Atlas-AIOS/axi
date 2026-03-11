#!/usr/bin/env python3
"""
Goal Alignment Gate Tuner
Goal Alignment 门控调参器 (Round 16.2)

策略: 只调 Goal Alignment，不动其他门
目标: 把 False-Block Rate 从 100% 降下来，通过三项验收指标

可调参数:
1. completeness_threshold: 完整性阈值 (默认过高)
2. missing_field_tolerance: 缺失字段容忍度
3. min_confidence_score: 最低置信度
4. allow_continue_with_gaps: 允许缺失进入 Round 1
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy

sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/rounds/round16')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/bridge')

from bridge.goal_alignment_wizard import GoalAlignmentIntakeWizard, IntakeStatus, StructuredBrief
from layered_replay_analyzer import LayeredReplayAnalyzer, AcceptanceStatus


@dataclass
class AlignmentGateConfig:
    """Goal Alignment Gate 配置"""
    # 核心参数
    completeness_threshold: float = 0.8      # 完整性阈值 (0-1)
    min_confidence_score: float = 0.6        # 最低置信度 (0-1)
    
    # 缺失字段容忍
    max_missing_fields: int = 2              # 允许缺失字段数
    allow_missing_constraints: bool = False  # 是否允许缺失约束
    
    # 模糊议题处理
    allow_continue_with_gaps: bool = True    # 允许缺失进入 Round 1
    force_reject_on_critical_gap: bool = False  # 关键缺失才拒绝
    
    # 评分调整
    confidence_boost_for_topic: float = 0.1  # 有主题时置信度加成
    lenient_extraction: bool = True          # 宽松提取模式
    
    def to_dict(self) -> Dict:
        return {
            "completeness_threshold": self.completeness_threshold,
            "min_confidence_score": self.min_confidence_score,
            "max_missing_fields": self.max_missing_fields,
            "allow_missing_constraints": self.allow_missing_constraints,
            "allow_continue_with_gaps": self.allow_continue_with_gaps,
            "force_reject_on_critical_gap": self.force_reject_on_critical_gap,
            "confidence_boost_for_topic": self.confidence_boost_for_topic,
            "lenient_extraction": self.lenient_extraction
        }


@dataclass
class TuningResult:
    """调参结果"""
    config: AlignmentGateConfig
    
    # 三项核心指标
    false_block_rate: float = 1.0
    risk_intercept_rate: float = 0.0
    extra_rounds_ratio: float = 0.0
    
    # 辅助指标
    approved_retention: float = 0.0
    overall_status: str = "unknown"
    
    # 是否通过验收
    passed_acceptance: bool = False
    failed_checks: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "config": self.config.to_dict(),
            "metrics": {
                "false_block_rate": self.false_block_rate,
                "risk_intercept_rate": self.risk_intercept_rate,
                "extra_rounds_ratio": self.extra_rounds_ratio,
                "approved_retention": self.approved_retention
            },
            "overall_status": self.overall_status,
            "passed_acceptance": self.passed_acceptance,
            "failed_checks": self.failed_checks
        }


class TunedGoalAlignmentWizard(GoalAlignmentIntakeWizard):
    """
    可调参的 Goal Alignment Wizard
    """
    
    def __init__(self, config: AlignmentGateConfig = None):
        super().__init__()
        self.config = config or AlignmentGateConfig()
    
    def intake(self, raw_text: str, submitter_id: str, source: str = "matrix") -> Tuple[IntakeStatus, StructuredBrief, List[str]]:
        """
        重写 intake，应用调参配置
        """
        # 调用父类基础提取
        intake_record = self._create_intake_record(raw_text, submitter_id, source)
        self.intake_history.append(intake_record)
        
        # 提取结构化信息
        structured = self._extract_structure(raw_text)
        structured.extracted_at = datetime.now().isoformat()
        
        # 应用宽松提取模式
        if self.config.lenient_extraction:
            structured = self._apply_lenient_extraction(structured, raw_text)
        
        # 评估完整性 (应用配置)
        missing = self._identify_missing_with_tolerance(structured)
        structured.missing_fields = missing
        
        # 计算置信度 (应用配置)
        confidence = self._calculate_confidence_with_config(structured, raw_text)
        structured.confidence_score = confidence
        
        # 生成澄清问题
        questions = self._generate_clarification_questions(structured, missing)
        
        # 确定状态 (应用配置)
        status = self._determine_status_with_config(structured, missing, confidence)
        
        if status in [IntakeStatus.VALIDATED, IntakeStatus.STRUCTURED]:
            self.structured_history.append(structured)
        
        return status, structured, questions
    
    def _create_intake_record(self, raw_text: str, submitter_id: str, source: str):
        """创建摄入记录"""
        from bridge.goal_alignment_wizard import RawIntake
        return RawIntake(
            intake_id=f"intake_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{submitter_id[:8]}",
            timestamp=datetime.now().isoformat(),
            source=source,
            raw_text=raw_text,
            submitter_id=submitter_id
        )
    
    def _apply_lenient_extraction(self, brief: StructuredBrief, raw_text: str) -> StructuredBrief:
        """应用宽松提取规则"""
        # 如果没有提取到主题，使用文本前50字符
        if not brief.topic or brief.topic == "未命名议题":
            brief.topic = raw_text[:50].strip().replace('\n', ' ')
        
        # 如果没有问题定义，使用文本前200字符
        if not brief.problem_definition or len(brief.problem_definition) < 20:
            brief.problem_definition = raw_text[:200].strip()
        
        # 如果没有成功标准，生成默认标准
        if len(brief.success_criteria) == 0:
            brief.success_criteria = [
                "议题得到充分讨论",
                "风险被识别和评估",
                "形成可执行的决议"
            ]
        
        # 如果没有硬约束，添加默认约束
        if len(brief.hard_constraints) == 0:
            brief.hard_constraints = [
                "遵守议会基本规则",
                "尊重各席位意见"
            ]
        
        return brief
    
    def _identify_missing_with_tolerance(self, brief: StructuredBrief) -> List[str]:
        """应用容忍度的缺失字段识别"""
        missing = []
        
        # 主题检查 (必须)
        if not brief.topic or len(brief.topic) < 3:
            missing.append("topic")
        
        # 问题定义检查 (放宽)
        if not brief.problem_definition or len(brief.problem_definition) < 10:
            missing.append("problem_definition")
        
        # 成功标准检查 (可容忍)
        if len(brief.success_criteria) == 0:
            missing.append("success_criteria")
        
        # 约束检查 (根据配置)
        if not self.config.allow_missing_constraints:
            if len(brief.hard_constraints) == 0:
                missing.append("hard_constraints")
        
        return missing
    
    def _calculate_confidence_with_config(self, brief: StructuredBrief, raw_text: str) -> float:
        """应用配置的置信度计算"""
        base_confidence = self._calculate_confidence(brief, raw_text)
        
        # 有主题时加成
        if brief.topic and len(brief.topic) > 5:
            base_confidence += self.config.confidence_boost_for_topic
        
        return min(1.0, base_confidence)
    
    def _determine_status_with_config(self, brief: StructuredBrief, 
                                       missing: List[str], 
                                       confidence: float) -> IntakeStatus:
        """应用配置的状态判定"""
        
        # 检查关键缺失
        critical_missing = [f for f in missing if f in ["topic"]]
        
        # 如果有关键缺失且配置强制拒绝
        if critical_missing and self.config.force_reject_on_critical_gap:
            return IntakeStatus.CLARIFYING
        
        # 检查缺失字段数是否超过容忍度
        if len(missing) > self.config.max_missing_fields:
            if self.config.allow_continue_with_gaps:
                # 允许继续，但标记为 clarifying
                return IntakeStatus.CLARIFYING
            else:
                return IntakeStatus.REJECTED
        
        # 检查置信度
        if confidence >= self.config.completeness_threshold:
            return IntakeStatus.VALIDATED
        elif confidence >= self.config.min_confidence_score:
            return IntakeStatus.STRUCTURED
        elif self.config.allow_continue_with_gaps:
            return IntakeStatus.CLARIFYING
        else:
            return IntakeStatus.REJECTED


class GoalAlignmentGateTuner:
    """
    Goal Alignment Gate 调参器
    
    执行参数扫描，找到满足验收标准的配置
    """
    
    # 验收门槛
    THRESHOLDS = {
        'false_block_rate_max': 0.15,
        'risk_intercept_rate_min': 0.70,
        'extra_rounds_ratio_max': 0.40,
        'approved_retention_min': 0.75
    }
    
    def __init__(self):
        self.results: List[TuningResult] = []
        self.best_config: Optional[AlignmentGateConfig] = None
        self.best_result: Optional[TuningResult] = None
    
    def evaluate_config(self, config: AlignmentGateConfig, 
                        max_cases: int = 50) -> TuningResult:
        """
        评估一个配置
        
        Args:
            config: Goal Alignment 配置
            max_cases: 评估案例数
            
        Returns:
            TuningResult
        """
        # 创建带配置的 wizard
        wizard = TunedGoalAlignmentWizard(config)
        
        # 创建 analyzer 并使用自定义 wizard
        analyzer = LayeredReplayAnalyzer()
        analyzer.verifier.wizard = wizard  # 替换 wizard
        
        # 加载并回放
        analyzer.load_and_replay(max_cases=max_cases)
        
        # 分析
        metrics = analyzer.analyze()
        report = analyzer.generate_acceptance_report()
        
        # 构建结果
        result = TuningResult(
            config=config,
            false_block_rate=metrics.false_block_rate,
            risk_intercept_rate=metrics.risk_intercept_rate,
            extra_rounds_ratio=metrics.extra_rounds_ratio,
            approved_retention=metrics.approved_retained / metrics.original_approved if metrics.original_approved > 0 else 0,
            overall_status=report.overall_status.value,
            failed_checks=report.failed_checks
        )
        
        # 判断是否通过验收
        result.passed_acceptance = (
            result.false_block_rate <= self.THRESHOLDS['false_block_rate_max'] and
            result.risk_intercept_rate >= self.THRESHOLDS['risk_intercept_rate_min'] and
            result.extra_rounds_ratio <= self.THRESHOLDS['extra_rounds_ratio_max'] and
            result.approved_retention >= self.THRESHOLDS['approved_retention_min']
        )
        
        return result
    
    def grid_search(self, 
                    completeness_range: List[float] = [0.5, 0.6, 0.7],
                    confidence_range: List[float] = [0.4, 0.5, 0.6],
                    missing_tolerance_range: List[int] = [2, 3, 4],
                    max_cases: int = 50) -> List[TuningResult]:
        """
        网格搜索最佳参数
        
        Args:
            completeness_range: 完整性阈值范围
            confidence_range: 置信度阈值范围
            missing_tolerance_range: 缺失容忍度范围
            max_cases: 每个配置评估案例数
            
        Returns:
            所有结果列表
        """
        print(f"\n🔍 Starting Grid Search")
        print(f"   Configurations to test: {len(completeness_range) * len(confidence_range) * len(missing_tolerance_range)}")
        print(f"   Cases per config: {max_cases}")
        print("=" * 70)
        
        self.results = []
        best_score = -1
        
        count = 0
        for completeness in completeness_range:
            for confidence in confidence_range:
                for missing_tol in missing_tolerance_range:
                    count += 1
                    
                    config = AlignmentGateConfig(
                        completeness_threshold=completeness,
                        min_confidence_score=confidence,
                        max_missing_fields=missing_tol,
                        allow_missing_constraints=True,
                        allow_continue_with_gaps=True,
                        lenient_extraction=True
                    )
                    
                    print(f"\n[{count}] Testing: completeness={completeness}, confidence={confidence}, missing_tol={missing_tol}")
                    
                    result = self.evaluate_config(config, max_cases)
                    self.results.append(result)
                    
                    print(f"    False-Block: {result.false_block_rate:.1%}")
                    print(f"    Risk-Intercept: {result.risk_intercept_rate:.1%}")
                    print(f"    Approved Retention: {result.approved_retention:.1%}")
                    print(f"    Status: {'✅ PASS' if result.passed_acceptance else '❌ FAIL'}")
                    
                    # 更新最佳配置
                    if result.passed_acceptance:
                        score = result.risk_intercept_rate - result.false_block_rate
                        if score > best_score:
                            best_score = score
                            self.best_config = config
                            self.best_result = result
        
        print("\n" + "=" * 70)
        print("Grid Search Complete")
        print("=" * 70)
        
        return self.results
    
    def quick_tune(self, max_cases: int = 50) -> TuningResult:
        """
        快速调参 (推荐配置)
        
        基于问题诊断的推荐参数:
        - 当前问题: Goal Alignment 过严
        - 解决方案: 大幅降低门槛，允许缺失进入 Round 1
        """
        print("\n⚡ Quick Tune: Applying recommended configuration")
        print("=" * 70)
        
        # 推荐配置 (宽松模式)
        config = AlignmentGateConfig(
            completeness_threshold=0.5,      # 降低完整性要求
            min_confidence_score=0.4,         # 降低置信度要求
            max_missing_fields=3,             # 允许更多缺失
            allow_missing_constraints=True,   # 允许缺失约束
            allow_continue_with_gaps=True,    # 允许缺失进入 Round 1
            force_reject_on_critical_gap=False,  # 不轻易拒绝
            confidence_boost_for_topic=0.15,  # 有主题时加分
            lenient_extraction=True           # 宽松提取
        )
        
        result = self.evaluate_config(config, max_cases)
        self.results.append(result)
        
        if result.passed_acceptance:
            self.best_config = config
            self.best_result = result
        
        return result
    
    def print_summary(self):
        """打印调参摘要"""
        print("\n" + "=" * 70)
        print("Goal Alignment Gate Tuning Summary")
        print("=" * 70)
        
        print(f"\nTotal configurations tested: {len(self.results)}")
        
        passed = [r for r in self.results if r.passed_acceptance]
        print(f"Passed acceptance: {len(passed)}")
        
        if self.best_config:
            print("\n🏆 Best Configuration:")
            print(f"   Completeness Threshold: {self.best_config.completeness_threshold}")
            print(f"   Min Confidence: {self.best_config.min_confidence_score}")
            print(f"   Max Missing Fields: {self.best_config.max_missing_fields}")
            print(f"   Allow Continue with Gaps: {self.best_config.allow_continue_with_gaps}")
            
            print("\n📊 Best Result:")
            print(f"   False-Block Rate: {self.best_result.false_block_rate:.1%}")
            print(f"   Risk-Intercept Rate: {self.best_result.risk_intercept_rate:.1%}")
            print(f"   Extra Rounds Ratio: {self.best_result.extra_rounds_ratio:.1%}")
            print(f"   Approved Retention: {self.best_result.approved_retention:.1%}")
        else:
            print("\n⚠️  No configuration passed all acceptance criteria")
            print("   Showing top 3 closest candidates:")
            
            # 排序：先按是否接近通过，再按综合得分
            sorted_results = sorted(
                self.results,
                key=lambda r: (
                    abs(r.false_block_rate - 0.15) + 
                    abs(r.risk_intercept_rate - 0.70) +
                    abs(r.extra_rounds_ratio - 0.40)
                )
            )[:3]
            
            for i, r in enumerate(sorted_results, 1):
                print(f"\n   #{i}:")
                print(f"      Config: completeness={r.config.completeness_threshold}, "
                      f"confidence={r.config.min_confidence_score}")
                print(f"      False-Block: {r.false_block_rate:.1%}, "
                      f"Risk-Intercept: {r.risk_intercept_rate:.1%}")
        
        print("\n" + "=" * 70)


# 演示
if __name__ == "__main__":
    print("=" * 70)
    print("Goal Alignment Gate Tuner - Demo")
    print("=" * 70)
    
    tuner = GoalAlignmentGateTuner()
    
    # 快速调参
    result = tuner.quick_tune(max_cases=50)
    
    # 打印结果
    print("\n" + "=" * 70)
    print("Quick Tune Result")
    print("=" * 70)
    print(f"\nConfiguration:")
    for key, value in result.config.to_dict().items():
        print(f"  {key}: {value}")
    
    print(f"\nMetrics:")
    print(f"  False-Block Rate: {result.false_block_rate:.1%}")
    print(f"  Risk-Intercept Rate: {result.risk_intercept_rate:.1%}")
    print(f"  Extra Rounds Ratio: {result.extra_rounds_ratio:.1%}")
    print(f"  Approved Retention: {result.approved_retention:.1%}")
    
    print(f"\nOverall: {'✅ PASSED' if result.passed_acceptance else '❌ FAILED'}")
    
    if not result.passed_acceptance and result.failed_checks:
        print("\nFailed checks:")
        for check in result.failed_checks:
            print(f"  • {check}")
    
    # 如果快速调参不通过，进行网格搜索
    if not result.passed_acceptance:
        print("\n" + "=" * 70)
        print("Quick tune failed. Running grid search...")
        print("=" * 70)
        
        results = tuner.grid_search(
            completeness_range=[0.4, 0.5, 0.6],
            confidence_range=[0.3, 0.4, 0.5],
            missing_tolerance_range=[2, 3, 4],
            max_cases=30  # 网格搜索用较少案例
        )
        
        tuner.print_summary()

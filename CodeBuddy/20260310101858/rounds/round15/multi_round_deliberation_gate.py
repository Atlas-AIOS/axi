#!/usr/bin/env python3
"""
第十五轮：Multi-Round Deliberation Gate

在现有天心议会 v2.0 基础上升级：
- Goal Alignment Phase（议题对齐层）
- 显式 round_id 多轮机制
- 主持人阶段评分
- 第三方审验机构（规则版）
- 最小 agent 消息总线

目标：把单轮串行议政升级成多轮协商—审验—执行门控闭环
"""

import json
import random
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class MessageType(Enum):
    """Agent 消息总线支持的三种消息类型"""
    CLARIFICATION = "clarification"      # 澄清请求
    CHALLENGE = "challenge"              # 反驳/质疑
    DEPENDENCY_REQUEST = "dependency_request"  # 依赖协作请求


class RoundStatus(Enum):
    """回合状态"""
    ALIGNMENT = "alignment"              # Round 0: 议题对齐
    DELIBERATION = "deliberation"        # Round 1+: 协商讨论
    REVIEW = "review"                    # 审验评分
    COMPLETED = "completed"              # 完成
    REJECTED = "rejected"                # 被拒绝


@dataclass
class AgentMessage:
    """Agent 间消息（可审计）"""
    message_id: str
    timestamp: str
    sender_id: str
    receiver_id: str  # 可以是 "broadcast" 或特定 agent
    message_type: str  # clarification / challenge / dependency_request
    content: str
    related_round: int
    context: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "timestamp": self.timestamp,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type,
            "content": self.content,
            "related_round": self.related_round,
            "context": self.context
        }


@dataclass
class AlignmentBrief:
    """Round 0: 议题对齐简报"""
    topic: str                           # 议题主题
    problem_definition: str              # 问题定义
    success_criteria: List[str]          # 成功标准
    hard_constraints: List[str]          # 硬约束/禁区
    known_divergences: List[str]         # 已知分歧点
    created_at: str
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "problem_definition": self.problem_definition,
            "success_criteria": self.success_criteria,
            "hard_constraints": self.hard_constraints,
            "known_divergences": self.known_divergences,
            "created_at": self.created_at
        }


@dataclass
class RoundSummary:
    """每轮结构化总结"""
    round_id: int
    status: str                          # deliberation / review / completed
    proposals: List[str]                 # 本轮提案要点
    counter_arguments: List[str]         # 反驳/质疑
    unresolved_issues: List[str]         # 未决问题
    blocking_demands: List[str]          # 阻断性要求
    conditions: List[str]                # 条件性支持
    score: Optional[float] = None        # 主持人评分
    
    def to_dict(self) -> Dict:
        return {
            "round_id": self.round_id,
            "status": self.status,
            "proposals": self.proposals,
            "counter_arguments": self.counter_arguments,
            "unresolved_issues": self.unresolved_issues,
            "blocking_demands": self.blocking_demands,
            "conditions": self.conditions,
            "score": self.score
        }


@dataclass
class ReviewReport:
    """第三方审验报告"""
    reviewer_id: str                     # 审验机构（杨戬/包拯/钟馗/丰都大帝）
    timestamp: str
    scores: Dict[str, float]             # 五个维度评分
    total_score: float                   # 总分
    defects: List[str]                   # 缺陷列表
    required_revisions: List[str]        # 要求修改项
    passed: bool                         # 是否通过（>=95）
    
    def to_dict(self) -> Dict:
        return {
            "reviewer_id": self.reviewer_id,
            "timestamp": self.timestamp,
            "scores": self.scores,
            "total_score": self.total_score,
            "defects": self.defects,
            "required_revisions": self.required_revisions,
            "passed": self.passed
        }


@dataclass
class MeetingState:
    """扩展的会议状态"""
    meeting_id: str
    topic: str
    
    # 议题对齐
    alignment_brief: Optional[AlignmentBrief] = None
    alignment_status: str = "pending"    # pending / completed
    
    # 多轮协商
    current_round: int = 0               # Round 0 = alignment, Round 1+ = deliberation
    max_rounds: int = 5                  # 最大轮数限制
    round_summaries: List[RoundSummary] = field(default_factory=list)
    
    # 审验评分
    review_score: Optional[float] = None
    review_passed: bool = False
    review_reports: List[ReviewReport] = field(default_factory=list)
    continue_deliberation: bool = True   # 是否继续讨论
    
    # Agent 消息总线
    message_log: List[AgentMessage] = field(default_factory=list)
    
    # 决议状态
    final_status: str = "pending"        # pending / approved / rejected
    execution_gate_passed: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "meeting_id": self.meeting_id,
            "topic": self.topic,
            "alignment_brief": self.alignment_brief.to_dict() if self.alignment_brief else None,
            "alignment_status": self.alignment_status,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds,
            "round_summaries": [s.to_dict() for s in self.round_summaries],
            "review_score": self.review_score,
            "review_passed": self.review_passed,
            "review_reports": [r.to_dict() for r in self.review_reports],
            "continue_deliberation": self.continue_deliberation,
            "message_log": [m.to_dict() for m in self.message_log],
            "final_status": self.final_status,
            "execution_gate_passed": self.execution_gate_passed
        }


class GoalAlignmentPhase:
    """Round 0: 议题对齐层"""
    
    def __init__(self, meeting_state: MeetingState):
        self.meeting_state = meeting_state
    
    def conduct_alignment(self, 
                         topic: str,
                         problem_definition: str,
                         success_criteria: List[str],
                         hard_constraints: List[str],
                         known_divergences: List[str]) -> AlignmentBrief:
        """
        执行议题对齐
        
        在正式开会前，先确认：
        1. 我们到底要解决什么问题
        2. 什么算成功
        3. 有哪些硬约束
        4. 目前已知的分歧点
        """
        print(f"\n{'='*60}")
        print(f"Round 0: Goal Alignment Phase")
        print(f"{'='*60}")
        print(f"Topic: {topic}")
        
        brief = AlignmentBrief(
            topic=topic,
            problem_definition=problem_definition,
            success_criteria=success_criteria,
            hard_constraints=hard_constraints,
            known_divergences=known_divergences,
            created_at=datetime.now().isoformat()
        )
        
        self.meeting_state.alignment_brief = brief
        self.meeting_state.alignment_status = "completed"
        self.meeting_state.current_round = 1  # 进入 Round 1
        
        print(f"\n✓ Alignment brief created")
        print(f"  Success criteria: {len(success_criteria)} items")
        print(f"  Hard constraints: {len(hard_constraints)} items")
        print(f"  Known divergences: {len(known_divergences)} items")
        
        return brief


class RoundBasedDeliberation:
    """多轮协商层"""
    
    def __init__(self, meeting_state: MeetingState):
        self.meeting_state = meeting_state
    
    def conduct_round(self,
                     proposals: List[str],
                     counter_arguments: List[str],
                     unresolved_issues: List[str],
                     blocking_demands: List[str],
                     conditions: List[str]) -> RoundSummary:
        """
        执行一轮协商
        
        每轮结构：
        - 提案要点
        - 反驳/质疑
        - 未决问题
        - 阻断性要求
        - 条件性支持
        """
        round_id = self.meeting_state.current_round
        
        print(f"\n{'='*60}")
        print(f"Round {round_id}: Deliberation")
        print(f"{'='*60}")
        
        summary = RoundSummary(
            round_id=round_id,
            status="deliberation",
            proposals=proposals,
            counter_arguments=counter_arguments,
            unresolved_issues=unresolved_issues,
            blocking_demands=blocking_demands,
            conditions=conditions
        )
        
        self.meeting_state.round_summaries.append(summary)
        
        print(f"  Proposals: {len(proposals)}")
        print(f"  Counter-arguments: {len(counter_arguments)}")
        print(f"  Unresolved issues: {len(unresolved_issues)}")
        print(f"  Blocking demands: {len(blocking_demands)}")
        print(f"  Conditions: {len(conditions)}")
        
        return summary
    
    def advance_to_next_round(self) -> bool:
        """推进到下一轮"""
        if self.meeting_state.current_round >= self.meeting_state.max_rounds:
            print(f"\n⚠️ Max rounds ({self.meeting_state.max_rounds}) reached")
            return False
        
        self.meeting_state.current_round += 1
        print(f"\n→ Advancing to Round {self.meeting_state.current_round}")
        return True


class HostScoringGate:
    """主持人阶段评分"""
    
    SCORE_DIMENSIONS = [
        "goal_alignment",      # 目标对齐度
        "risk_closure",        # 风险闭环度
        "executability",       # 可执行性
        "counter_absorption",  # 反驳吸收度
        "audit_completeness"   # 审计完备性
    ]
    
    def __init__(self, meeting_state: MeetingState):
        self.meeting_state = meeting_state
    
    def score_round(self, dimension_scores: Dict[str, float]) -> float:
        """
        主持人评分
        
        五个维度，每个 0-20 分，总分 0-100
        """
        print(f"\n{'='*60}")
        print(f"Host Scoring - Round {self.meeting_state.current_round}")
        print(f"{'='*60}")
        
        # 验证维度完整性
        for dim in self.SCORE_DIMENSIONS:
            if dim not in dimension_scores:
                dimension_scores[dim] = 0.0
        
        total_score = sum(dimension_scores.values())
        
        print("Dimension scores:")
        for dim, score in dimension_scores.items():
            print(f"  {dim}: {score:.1f}/20")
        print(f"\nTotal: {total_score:.1f}/100")
        
        # 更新当前轮的评分
        if self.meeting_state.round_summaries:
            current_summary = self.meeting_state.round_summaries[-1]
            current_summary.score = total_score
        
        self.meeting_state.review_score = total_score
        
        # 评分门控逻辑
        if total_score >= 95:
            print("\n✓ Score >= 95: Ready for execution")
            self.meeting_state.continue_deliberation = False
            self.meeting_state.review_passed = True
        elif total_score >= 70:
            print("\n→ Score 70-94: Continue deliberation")
            self.meeting_state.continue_deliberation = True
        else:
            print("\n✗ Score < 70: Consider rejection")
            self.meeting_state.continue_deliberation = False
        
        return total_score


class ThirdPartyReview:
    """第三方审验机构（规则版）"""
    
    REVIEWERS = ["杨戬", "包拯", "钟馗", "丰都大帝"]
    
    def __init__(self, meeting_state: MeetingState):
        self.meeting_state = meeting_state
    
    def conduct_review(self, reviewer_id: str = None) -> ReviewReport:
        """
        执行第三方审验
        
        从现有 pending_questions / blocking_demands / conditions 生成评分
        """
        if reviewer_id is None:
            reviewer_id = random.choice(self.REVIEWERS)
        
        print(f"\n{'='*60}")
        print(f"Third-Party Review: {reviewer_id}")
        print(f"{'='*60}")
        
        # 基于当前会议状态生成评分
        # 简化版：基于未决问题数量计算
        unresolved_count = len(self._get_all_unresolved_issues())
        blocking_count = len(self._get_all_blocking_demands())
        
        # 计算各维度得分（简化规则）
        base_score = 100.0
        base_score -= unresolved_count * 3    # 每个未决问题 -3 分
        base_score -= blocking_count * 5      # 每个阻断要求 -5 分
        
        scores = {
            "goal_alignment": min(20, max(0, base_score * 0.2)),
            "risk_closure": min(20, max(0, base_score * 0.2 - blocking_count * 2)),
            "executability": min(20, max(0, base_score * 0.2)),
            "counter_absorption": min(20, max(0, base_score * 0.2)),
            "audit_completeness": min(20, max(0, base_score * 0.2))
        }
        
        total_score = sum(scores.values())
        
        # 生成缺陷和修改要求
        defects = []
        required_revisions = []
        
        if unresolved_count > 0:
            defects.append(f"{unresolved_count} unresolved issues remain")
            required_revisions.append("Resolve all pending questions")
        
        if blocking_count > 0:
            defects.append(f"{blocking_count} blocking demands unaddressed")
            required_revisions.append("Address all blocking concerns")
        
        passed = total_score >= 95
        
        report = ReviewReport(
            reviewer_id=reviewer_id,
            timestamp=datetime.now().isoformat(),
            scores=scores,
            total_score=total_score,
            defects=defects,
            required_revisions=required_revisions,
            passed=passed
        )
        
        self.meeting_state.review_reports.append(report)
        
        print(f"\nTotal score: {total_score:.1f}/100")
        print(f"Result: {'PASS' if passed else 'REJECT'}")
        
        if defects:
            print(f"\nDefects:")
            for d in defects:
                print(f"  - {d}")
        
        return report
    
    def _get_all_unresolved_issues(self) -> List[str]:
        """获取所有未决问题"""
        issues = []
        for summary in self.meeting_state.round_summaries:
            issues.extend(summary.unresolved_issues)
        return issues
    
    def _get_all_blocking_demands(self) -> List[str]:
        """获取所有阻断要求"""
        demands = []
        for summary in self.meeting_state.round_summaries:
            demands.extend(summary.blocking_demands)
        return demands


class AgentMessageBus:
    """最小 Agent 消息总线"""
    
    VALID_MESSAGE_TYPES = ["clarification", "challenge", "dependency_request"]
    
    def __init__(self, meeting_state: MeetingState):
        self.meeting_state = meeting_state
        self.message_counter = 0
    
    def send_message(self,
                    sender_id: str,
                    receiver_id: str,
                    message_type: str,
                    content: str,
                    context: Dict = None) -> AgentMessage:
        """
        发送消息
        
        只允许三类消息：
        - clarification: 澄清请求
        - challenge: 反驳/质疑
        - dependency_request: 依赖协作请求
        """
        if message_type not in self.VALID_MESSAGE_TYPES:
            raise ValueError(f"Invalid message type: {message_type}. Must be one of {self.VALID_MESSAGE_TYPES}")
        
        self.message_counter += 1
        
        message = AgentMessage(
            message_id=f"msg_{self.message_counter:04d}",
            timestamp=datetime.now().isoformat(),
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
            related_round=self.meeting_state.current_round,
            context=context or {}
        )
        
        self.meeting_state.message_log.append(message)
        
        print(f"\n[Message] {sender_id} -> {receiver_id}")
        print(f"  Type: {message_type}")
        print(f"  Content: {content[:80]}...")
        
        return message
    
    def get_messages_for_round(self, round_id: int) -> List[AgentMessage]:
        """获取指定轮次的消息"""
        return [m for m in self.meeting_state.message_log if m.related_round == round_id]
    
    def get_message_trace(self, agent_id: str = None) -> List[Dict]:
        """获取消息追踪记录（可审计）"""
        messages = self.meeting_state.message_log
        if agent_id:
            messages = [m for m in messages if m.sender_id == agent_id or m.receiver_id == agent_id]
        
        return [m.to_dict() for m in messages]


class MultiRoundDeliberationGate:
    """
    多轮协商门控主控器
    
    整合所有组件，提供完整的多轮协商流程
    """
    
    def __init__(self, meeting_id: str, topic: str, max_rounds: int = 5):
        self.meeting_state = MeetingState(
            meeting_id=meeting_id,
            topic=topic,
            max_rounds=max_rounds
        )
        
        # 初始化各组件
        self.alignment_phase = GoalAlignmentPhase(self.meeting_state)
        self.deliberation = RoundBasedDeliberation(self.meeting_state)
        self.scoring_gate = HostScoringGate(self.meeting_state)
        self.review = ThirdPartyReview(self.meeting_state)
        self.message_bus = AgentMessageBus(self.meeting_state)
    
    def start_meeting(self,
                     problem_definition: str,
                     success_criteria: List[str],
                     hard_constraints: List[str],
                     known_divergences: List[str]) -> MeetingState:
        """
        启动会议（Round 0: Goal Alignment）
        """
        print(f"\n{'#'*60}")
        print(f"# Multi-Round Deliberation Gate")
        print(f"# Meeting: {self.meeting_state.meeting_id}")
        print(f"# Topic: {self.meeting_state.topic}")
        print(f"{'#'*60}")
        
        # Round 0: Goal Alignment
        self.alignment_phase.conduct_alignment(
            topic=self.meeting_state.topic,
            problem_definition=problem_definition,
            success_criteria=success_criteria,
            hard_constraints=hard_constraints,
            known_divergences=known_divergences
        )
        
        return self.meeting_state
    
    def run_deliberation_round(self,
                              proposals: List[str],
                              counter_arguments: List[str],
                              unresolved_issues: List[str],
                              blocking_demands: List[str],
                              conditions: List[str],
                              dimension_scores: Dict[str, float]) -> Tuple[RoundSummary, float]:
        """
        执行一轮完整的协商（包含评分）
        """
        # 1. 协商
        summary = self.deliberation.conduct_round(
            proposals=proposals,
            counter_arguments=counter_arguments,
            unresolved_issues=unresolved_issues,
            blocking_demands=blocking_demands,
            conditions=conditions
        )
        
        # 2. 评分
        score = self.scoring_gate.score_round(dimension_scores)
        
        # 3. 如果评分未达标，推进到下一轮
        if self.meeting_state.continue_deliberation:
            self.deliberation.advance_to_next_round()
        
        return summary, score
    
    def conduct_final_review(self) -> ReviewReport:
        """执行最终审验"""
        report = self.review.conduct_review()
        
        if report.passed:
            self.meeting_state.execution_gate_passed = True
            self.meeting_state.final_status = "approved"
        else:
            self.meeting_state.final_status = "rejected"
        
        return report
    
    def save_state(self, filepath: str):
        """保存会议状态"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.meeting_state.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n✓ Meeting state saved to: {filepath}")


def demo():
    """演示第十五轮完整流程"""
    
    # 创建多轮协商门控
    gate = MultiRoundDeliberationGate(
        meeting_id="demo_001",
        topic="是否集成 ConsensusPredictor 到生产环境",
        max_rounds=3
    )
    
    # Round 0: Goal Alignment
    gate.start_meeting(
        problem_definition="评估 ConsensusPredictor 是否达到生产环境集成标准",
        success_criteria=[
            "ECE < 0.22",
            "Rolling ECE(50) < 0.18",
            "High-conf error rate < 18%",
            "200+ 真实样本验证"
        ],
        hard_constraints=[
            "不能影响现有 Python 主逻辑",
            "必须通过影子模式验证",
            "决策框架门槛不可更改"
        ],
        known_divergences=[
            "模型校准问题：严重欠自信",
            "输出范围受限：[0.26, 0.38]"
        ]
    )
    
    # Round 1: 初提案
    print(f"\n{'='*60}")
    summary1, score1 = gate.run_deliberation_round(
        proposals=[
            "基于 Round 19 训练的 ConsensusPredictor 已达到基本可用状态",
            "建议启动影子模式进行生产环境验证"
        ],
        counter_arguments=[
            "ECE 0.37 远超门槛 0.22，校准不合格",
            "输出范围 [0.26, 0.38] 无法形成有效概率分层"
        ],
        unresolved_issues=[
            "如何修复模型欠自信问题",
            "是否需要重新训练或调整架构"
        ],
        blocking_demands=[
            "必须解决校准问题才能进入影子模式"
        ],
        conditions=[
            "如果校准问题修复，可考虑继续"
        ],
        dimension_scores={
            "goal_alignment": 18.0,      # 目标对齐度
            "risk_closure": 12.0,        # 风险闭环度（扣分）
            "executability": 10.0,       # 可执行性（扣分）
            "counter_absorption": 14.0,  # 反驳吸收度
            "audit_completeness": 16.0   # 审计完备度
        }
    )
    
    # 使用消息总线
    gate.message_bus.send_message(
        sender_id="LOGOS",
        receiver_id="Casey",
        message_type="challenge",
        content="ECE 0.37 的数据统计是否存在偏差？需要重新验证吗？"
    )
    
    gate.message_bus.send_message(
        sender_id="Casey",
        receiver_id="LOGOS",
        message_type="clarification",
        content="数据已确认。问题在模型本身，不是统计误差。"
    )
    
    # 继续 Round 2（如果需要）
    if gate.meeting_state.continue_deliberation:
        print(f"\n{'='*60}")
        summary2, score2 = gate.run_deliberation_round(
            proposals=[
                "放弃当前模型，保持 Python 主逻辑",
                "ConsensusPredictor 退出升级候选"
            ],
            counter_arguments=[],
            unresolved_issues=[],
            blocking_demands=[],
            conditions=[],
            dimension_scores={
                "goal_alignment": 19.0,
                "risk_closure": 18.0,
                "executability": 19.0,
                "counter_absorption": 18.0,
                "audit_completeness": 19.0
            }
        )
    
    # 最终审验
    final_report = gate.conduct_final_review()
    
    # 保存状态
    gate.save_state("/home/admin/CodeBuddy/20260310101858/rounds/round15/meeting_state_demo.json")
    
    print(f"\n{'='*60}")
    print("FINAL RESULT")
    print(f"{'='*60}")
    print(f"Total rounds: {gate.meeting_state.current_round}")
    print(f"Final status: {gate.meeting_state.final_status}")
    print(f"Execution gate: {'PASS' if gate.meeting_state.execution_gate_passed else 'REJECT'}")
    print(f"Messages exchanged: {len(gate.meeting_state.message_log)}")


if __name__ == "__main__":
    demo()

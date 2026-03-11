#!/usr/bin/env python3
"""
Decision Gate Executor
决策门控执行器 (模块 #10)

作用: 只有当多轮评分 + 第三方审验 + 必要影子观察都达标，才允许进入执行层
接入位置: 第十五轮闭环的最后一层

为什么值得做: 把"执行"也纳入门控，而不是只在讨论层结束
"""

import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class GateStatus(Enum):
    """门控状态"""
    CLOSED = "closed"             # 门关闭，不允许执行
    CONDITIONAL = "conditional"   # 有条件通过
    OPEN = "open"                 # 门打开，允许执行


class ExecutionPhase(Enum):
    """执行阶段"""
    PENDING = "pending"           # 等待中
    APPROVED = "approved"         # 已批准
    IN_PROGRESS = "in_progress"   # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 执行失败
    ROLLED_BACK = "rolled_back"   # 已回滚


@dataclass
class GateCheck:
    """单项门控检查"""
    check_name: str               # 检查名称
    check_type: str               # deliberation / review / shadow / dependency
    status: str                   # pass / fail / pending / waived
    score: Optional[float] = None
    threshold: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    checked_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "check_name": self.check_name,
            "check_type": self.check_type,
            "status": self.status,
            "score": self.score,
            "threshold": self.threshold,
            "details": self.details,
            "checked_at": self.checked_at
        }
    
    def is_passed(self) -> bool:
        return self.status == "pass"


@dataclass
class ExecutionTicket:
    """执行票据"""
    ticket_id: str
    meeting_id: str
    
    # 门控检查记录
    gate_checks: List[GateCheck] = field(default_factory=list)
    
    # 最终决策
    gate_status: GateStatus = GateStatus.CLOSED
    final_score: float = 0.0
    
    # 执行授权
    authorized_by: str = ""       # 授权者
    authorization_time: Optional[str] = None
    authorization_conditions: List[str] = field(default_factory=list)
    
    # 执行跟踪
    execution_phase: ExecutionPhase = ExecutionPhase.PENDING
    execution_start_time: Optional[str] = None
    execution_end_time: Optional[str] = None
    execution_result: Optional[Dict] = None
    
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "ticket_id": self.ticket_id,
            "meeting_id": self.meeting_id,
            "gate_checks": [c.to_dict() for c in self.gate_checks],
            "gate_status": self.gate_status.value,
            "final_score": self.final_score,
            "authorized_by": self.authorized_by,
            "authorization_time": self.authorization_time,
            "authorization_conditions": self.authorization_conditions,
            "execution_phase": self.execution_phase.value,
            "execution_start_time": self.execution_start_time,
            "execution_end_time": self.execution_end_time,
            "execution_result": self.execution_result,
            "created_at": self.created_at
        }


@dataclass
class ExecutionPlan:
    """执行计划"""
    plan_id: str
    meeting_id: str
    
    # 计划内容
    tasks: List[Dict] = field(default_factory=list)
    dependencies: List[Tuple[str, str]] = field(default_factory=list)  # (task_id, depends_on)
    
    # 执行策略
    execution_mode: str = "sequential"  # sequential / parallel / phased
    rollback_strategy: str = "immediate"  # immediate / gradual / manual
    
    # 监控配置
    health_checks: List[str] = field(default_factory=list)
    abort_conditions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "meeting_id": self.meeting_id,
            "tasks": self.tasks,
            "dependencies": self.dependencies,
            "execution_mode": self.execution_mode,
            "rollback_strategy": self.rollback_strategy,
            "health_checks": self.health_checks,
            "abort_conditions": self.abort_conditions
        }


class DecisionGateExecutor:
    """
    决策门控执行器
    
    职责:
    1. 收集所有门控检查 (多轮评分、第三方审验、影子观察)
    2. 综合评估是否达到执行门槛
    3. 生成执行票据
    4. 监督执行过程
    5. 必要时触发回滚
    """
    
    # 默认阈值配置
    DEFAULT_THRESHOLDS = {
        'deliberation_min_score': 95.0,      # 多轮协商最低分
        'review_min_score': 95.0,             # 第三方审验最低分
        'shadow_observation_required': False,  # 是否必须影子观察
        'shadow_min_confidence': 0.8,         # 影子观察最低置信度
        'max_defects_allowed': 0,             # 允许的最大缺陷数
    }
    
    def __init__(self, thresholds: Dict[str, float] = None):
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}
        self.tickets: Dict[str, ExecutionTicket] = {}
        self.plans: Dict[str, ExecutionPlan] = {}
    
    def evaluate_meeting(self, 
                         meeting_id: str,
                         deliberation_score: float,
                         deliberation_rounds: int,
                         review_score: float,
                         review_passed: bool,
                         review_defects: List[str],
                         shadow_result: Optional[Dict] = None,
                         dependencies_satisfied: bool = True) -> Tuple[GateStatus, ExecutionTicket, str]:
        """
        评估会议是否可以进入执行层
        
        Args:
            meeting_id: 会议ID
            deliberation_score: 多轮协商最终评分
            deliberation_rounds: 协商轮数
            review_score: 第三方审验分数
            review_passed: 审验是否通过
            review_defects: 审验发现的缺陷
            shadow_result: 影子观察结果 (可选)
            dependencies_satisfied: 依赖是否满足
            
        Returns:
            (gate_status, execution_ticket, reason)
        """
        ticket_id = f"ticket_{meeting_id}_{datetime.now().strftime('%H%M%S')}"
        ticket = ExecutionTicket(
            ticket_id=ticket_id,
            meeting_id=meeting_id,
            created_at=datetime.now().isoformat()
        )
        
        checks = []
        all_passed = True
        
        # 检查 1: 多轮协商评分
        deliberation_check = GateCheck(
            check_name="deliberation_score",
            check_type="deliberation",
            status="pass" if deliberation_score >= self.thresholds['deliberation_min_score'] else "fail",
            score=deliberation_score,
            threshold=self.thresholds['deliberation_min_score'],
            details={"rounds": deliberation_rounds},
            checked_at=datetime.now().isoformat()
        )
        checks.append(deliberation_check)
        if not deliberation_check.is_passed():
            all_passed = False
        
        # 检查 2: 第三方审验
        review_check = GateCheck(
            check_name="third_party_review",
            check_type="review",
            status="pass" if review_passed and review_score >= self.thresholds['review_min_score'] else "fail",
            score=review_score,
            threshold=self.thresholds['review_min_score'],
            details={"defects": len(review_defects), "defect_list": review_defects[:5]},
            checked_at=datetime.now().isoformat()
        )
        checks.append(review_check)
        if not review_check.is_passed():
            all_passed = False
        
        # 检查 3: 缺陷数量
        defects_check = GateCheck(
            check_name="defect_count",
            check_type="review",
            status="pass" if len(review_defects) <= self.thresholds['max_defects_allowed'] else "fail",
            score=float(len(review_defects)),
            threshold=self.thresholds['max_defects_allowed'],
            details={"max_allowed": self.thresholds['max_defects_allowed']},
            checked_at=datetime.now().isoformat()
        )
        checks.append(defects_check)
        if not defects_check.is_passed():
            all_passed = False
        
        # 检查 4: 影子观察 (如果配置需要)
        if self.thresholds['shadow_observation_required']:
            if shadow_result:
                shadow_check = GateCheck(
                    check_name="shadow_observation",
                    check_type="shadow",
                    status="pass" if shadow_result.get('confidence', 0) >= self.thresholds['shadow_min_confidence'] else "fail",
                    score=shadow_result.get('confidence', 0),
                    threshold=self.thresholds['shadow_min_confidence'],
                    details={"observations": shadow_result.get('observation_count', 0)},
                    checked_at=datetime.now().isoformat()
                )
            else:
                shadow_check = GateCheck(
                    check_name="shadow_observation",
                    check_type="shadow",
                    status="fail",
                    details={"error": "Shadow observation required but not provided"},
                    checked_at=datetime.now().isoformat()
                )
            checks.append(shadow_check)
            if not shadow_check.is_passed():
                all_passed = False
        else:
            # 影子观察可选，标记为 waived
            shadow_check = GateCheck(
                check_name="shadow_observation",
                check_type="shadow",
                status="waived",
                details={"reason": "Shadow observation not required by policy"},
                checked_at=datetime.now().isoformat()
            )
            checks.append(shadow_check)
        
        # 检查 5: 依赖满足
        dependency_check = GateCheck(
            check_name="dependencies",
            check_type="dependency",
            status="pass" if dependencies_satisfied else "fail",
            details={"satisfied": dependencies_satisfied},
            checked_at=datetime.now().isoformat()
        )
        checks.append(dependency_check)
        if not dependency_check.is_passed():
            all_passed = False
        
        # 保存检查记录
        ticket.gate_checks = checks
        
        # 计算综合分数
        scores = [c.score for c in checks if c.score is not None]
        ticket.final_score = sum(scores) / len(scores) if scores else 0.0
        
        # 确定门控状态
        if all_passed:
            ticket.gate_status = GateStatus.OPEN
            reason = "All gate checks passed. Execution authorized."
        elif len([c for c in checks if c.status == "fail"]) == 1 and review_passed:
            # 只有一个失败且审验通过，可能是条件通过
            ticket.gate_status = GateStatus.CONDITIONAL
            reason = "Most checks passed with conditions. Review authorization_conditions."
        else:
            ticket.gate_status = GateStatus.CLOSED
            failed_checks = [c.check_name for c in checks if c.status == "fail"]
            reason = f"Gate checks failed: {', '.join(failed_checks)}"
        
        # 保存票据
        self.tickets[ticket_id] = ticket
        
        return ticket.gate_status, ticket, reason
    
    def authorize_execution(self, ticket_id: str, authorized_by: str,
                           conditions: List[str] = None) -> bool:
        """
        授权执行
        
        Args:
            ticket_id: 执行票据ID
            authorized_by: 授权者ID
            conditions: 授权条件
            
        Returns:
            是否授权成功
        """
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        
        # 只有 OPEN 或 CONDITIONAL 状态可以授权
        if ticket.gate_status == GateStatus.CLOSED:
            return False
        
        ticket.authorized_by = authorized_by
        ticket.authorization_time = datetime.now().isoformat()
        ticket.authorization_conditions = conditions or []
        ticket.execution_phase = ExecutionPhase.APPROVED
        
        return True
    
    def create_execution_plan(self, ticket_id: str, tasks: List[Dict],
                             mode: str = "sequential") -> Optional[ExecutionPlan]:
        """
        创建执行计划
        
        Args:
            ticket_id: 执行票据ID
            tasks: 任务列表
            mode: 执行模式
            
        Returns:
            ExecutionPlan 或 None
        """
        if ticket_id not in self.tickets:
            return None
        
        ticket = self.tickets[ticket_id]
        
        if ticket.execution_phase != ExecutionPhase.APPROVED:
            return None
        
        plan_id = f"plan_{ticket.meeting_id}_{datetime.now().strftime('%H%M%S')}"
        
        plan = ExecutionPlan(
            plan_id=plan_id,
            meeting_id=ticket.meeting_id,
            tasks=tasks,
            execution_mode=mode,
            health_checks=["pre_execution", "post_execution"],
            abort_conditions=["health_check_failed", "manual_abort", "timeout"]
        )
        
        self.plans[plan_id] = plan
        
        return plan
    
    def start_execution(self, ticket_id: str, plan_id: str) -> bool:
        """
        开始执行
        
        Args:
            ticket_id: 执行票据ID
            plan_id: 执行计划ID
            
        Returns:
            是否成功启动
        """
        if ticket_id not in self.tickets or plan_id not in self.plans:
            return False
        
        ticket = self.tickets[ticket_id]
        plan = self.plans[plan_id]
        
        if ticket.execution_phase != ExecutionPhase.APPROVED:
            return False
        
        if ticket.meeting_id != plan.meeting_id:
            return False
        
        ticket.execution_phase = ExecutionPhase.IN_PROGRESS
        ticket.execution_start_time = datetime.now().isoformat()
        
        return True
    
    def complete_execution(self, ticket_id: str, result: Dict,
                          success: bool = True) -> bool:
        """
        完成执行
        
        Args:
            ticket_id: 执行票据ID
            result: 执行结果
            success: 是否成功
            
        Returns:
            是否成功记录
        """
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        
        if ticket.execution_phase != ExecutionPhase.IN_PROGRESS:
            return False
        
        ticket.execution_end_time = datetime.now().isoformat()
        ticket.execution_result = result
        ticket.execution_phase = ExecutionPhase.COMPLETED if success else ExecutionPhase.FAILED
        
        return True
    
    def trigger_rollback(self, ticket_id: str, reason: str) -> bool:
        """
        触发回滚
        
        Args:
            ticket_id: 执行票据ID
            reason: 回滚原因
            
        Returns:
            是否成功触发
        """
        if ticket_id not in self.tickets:
            return False
        
        ticket = self.tickets[ticket_id]
        
        if ticket.execution_phase not in [ExecutionPhase.IN_PROGRESS, ExecutionPhase.COMPLETED]:
            return False
        
        ticket.execution_phase = ExecutionPhase.ROLLED_BACK
        if ticket.execution_result is None:
            ticket.execution_result = {}
        ticket.execution_result['rollback'] = {
            "triggered_at": datetime.now().isoformat(),
            "reason": reason
        }
        
        return True
    
    def get_ticket_summary(self, ticket_id: str) -> Optional[Dict]:
        """获取票据摘要"""
        if ticket_id not in self.tickets:
            return None
        
        ticket = self.tickets[ticket_id]
        
        return {
            "ticket_id": ticket.ticket_id,
            "meeting_id": ticket.meeting_id,
            "gate_status": ticket.gate_status.value,
            "final_score": ticket.final_score,
            "checks_summary": {
                "total": len(ticket.gate_checks),
                "passed": len([c for c in ticket.gate_checks if c.status == "pass"]),
                "failed": len([c for c in ticket.gate_checks if c.status == "fail"]),
                "waived": len([c for c in ticket.gate_checks if c.status == "waived"])
            },
            "execution_phase": ticket.execution_phase.value,
            "can_execute": ticket.gate_status == GateStatus.OPEN and ticket.execution_phase == ExecutionPhase.APPROVED
        }
    
    def export_ticket(self, ticket_id: str, filepath: str = None) -> str:
        """导出票据"""
        if ticket_id not in self.tickets:
            raise ValueError(f"Ticket {ticket_id} not found")
        
        ticket = self.tickets[ticket_id]
        
        if filepath is None:
            filepath = f"/home/admin/CodeBuddy/20260310101858/data/tickets/{ticket_id}.json"
        
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            json.dump(ticket.to_dict(), f, indent=2, ensure_ascii=False)
        
        return filepath


# 与 Round 15 的集成函数
def evaluate_round15_meeting(meeting_state: Dict, shadow_result: Dict = None) -> Tuple[GateStatus, ExecutionTicket, str]:
    """
    评估 Round 15 会议状态
    
    这是 DecisionGateExecutor 与 Round 15 系统的集成入口
    """
    executor = DecisionGateExecutor()
    
    # 从 meeting_state 提取必要信息
    meeting_id = meeting_state.get('meeting_id', 'unknown')
    
    # 获取最新协商评分
    round_summaries = meeting_state.get('round_summaries', [])
    deliberation_score = round_summaries[-1].get('score', 0) if round_summaries else 0
    deliberation_rounds = len(round_summaries)
    
    # 获取审验信息
    review_reports = meeting_state.get('review_reports', [])
    if review_reports:
        latest_review = review_reports[-1]
        review_score = latest_review.get('total_score', 0)
        review_passed = latest_review.get('passed', False)
        review_defects = latest_review.get('defects', [])
    else:
        review_score = 0
        review_passed = False
        review_defects = []
    
    # 执行评估
    return executor.evaluate_meeting(
        meeting_id=meeting_id,
        deliberation_score=deliberation_score,
        deliberation_rounds=deliberation_rounds,
        review_score=review_score,
        review_passed=review_passed,
        review_defects=review_defects,
        shadow_result=shadow_result,
        dependencies_satisfied=True
    )


# 演示
if __name__ == "__main__":
    executor = DecisionGateExecutor()
    
    print("=" * 70)
    print("Decision Gate Executor Demo")
    print("=" * 70)
    
    # 场景 1: 完全通过
    print("\n[场景 1] 所有检查通过")
    status, ticket, reason = executor.evaluate_meeting(
        meeting_id="council_test_001",
        deliberation_score=96.0,
        deliberation_rounds=3,
        review_score=97.0,
        review_passed=True,
        review_defects=[],
        dependencies_satisfied=True
    )
    print(f"Status: {status.value}")
    print(f"Final Score: {ticket.final_score:.1f}")
    print(f"Checks: {len([c for c in ticket.gate_checks if c.status == 'pass'])}/{len(ticket.gate_checks)} passed")
    print(f"Reason: {reason}")
    
    # 授权并创建执行计划
    executor.authorize_execution(ticket.ticket_id, "system_admin")
    plan = executor.create_execution_plan(
        ticket.ticket_id,
        tasks=[
            {"id": "task_1", "name": "部署配置", "type": "config"},
            {"id": "task_2", "name": "启动服务", "type": "deploy"}
        ]
    )
    print(f"Execution Plan Created: {plan.plan_id if plan else 'Failed'}")
    
    # 场景 2: 审验失败
    print("\n[场景 2] 审验未通过")
    status, ticket, reason = executor.evaluate_meeting(
        meeting_id="council_test_002",
        deliberation_score=96.0,
        deliberation_rounds=3,
        review_score=87.0,
        review_passed=False,
        review_defects=["校准问题", "输出范围受限"],
        dependencies_satisfied=True
    )
    print(f"Status: {status.value}")
    print(f"Final Score: {ticket.final_score:.1f}")
    print(f"Failed Checks: {[c.check_name for c in ticket.gate_checks if c.status == 'fail']}")
    print(f"Reason: {reason}")
    
    # 场景 3: 有条件通过
    print("\n[场景 3] 协商评分略低但审验通过")
    executor2 = DecisionGateExecutor({'deliberation_min_score': 90.0})  # 降低门槛
    status, ticket, reason = executor2.evaluate_meeting(
        meeting_id="council_test_003",
        deliberation_score=88.0,
        deliberation_rounds=5,
        review_score=96.0,
        review_passed=True,
        review_defects=["minor_issue"],
        dependencies_satisfied=True
    )
    print(f"Status: {status.value}")
    print(f"Reason: {reason}")

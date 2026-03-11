#!/usr/bin/env python3
"""
Round 15.1: Matrix Bridge Integration

将 Multi-Round Deliberation Gate 接入真实 !council start 会议生命周期

集成目标:
1. 扩展 !council start 进入 Goal Alignment Phase
2. 自动生成 alignment_brief 和自动 round 递进
3. 自动评分、审验和继续讨论决策
4. 完整的会议状态持久化

与现有系统集成点:
- TianxinCouncilV2: 核心议会功能
- Matrix Bot: 命令处理 (!council start/status/close)
- MeetingState: 扩展为多轮状态
"""

import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import sys
import os

# 添加路径以导入现有模块
sys.path.insert(0, '/home/admin')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/rounds/round15')

# 导入第十五轮核心组件
from multi_round_deliberation_gate import (
    MultiRoundDeliberationGate,
    MeetingState,
    GoalAlignmentPhase,
    RoundBasedDeliberation,
    HostScoringGate,
    ThirdPartyReview,
    AgentMessageBus,
    RoundSummary,
    AlignmentBrief,
    ReviewReport
)


class MatrixBridgeCouncil:
    """
    Matrix Bridge 集成版天心议会
    
    将 Multi-Round Deliberation Gate 接入 Matrix 会议流程
    """
    
    def __init__(self, storage_path: str = "/home/admin/CodeBuddy/20260310101858/data/meetings"):
        self.storage_path = storage_path
        os.makedirs(storage_path, exist_ok=True)
        
        # 活跃的会议
        self.active_meetings: Dict[str, MultiRoundDeliberationGate] = {}
        
        # 会议历史
        self.meeting_history: List[str] = []
        
        print(f"🔌 MatrixBridgeCouncil initialized")
        print(f"   Storage: {storage_path}")
    
    async def start_council(
        self,
        room_id: str,
        topic: str,
        problem_definition: str,
        success_criteria: List[str],
        hard_constraints: List[str],
        known_divergences: List[str],
        max_rounds: int = 5
    ) -> Tuple[str, str]:
        """
        启动会议 (!council start)
        
        扩展为包含 Goal Alignment Phase 的完整流程
        
        Returns:
            (meeting_id, status_message)
        """
        meeting_id = f"council_{room_id.replace(':', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        print(f"\n🚀 Starting Council Meeting")
        print(f"   Meeting ID: {meeting_id}")
        print(f"   Topic: {topic}")
        print(f"   Room: {room_id}")
        
        # 创建多轮协商门控
        gate = MultiRoundDeliberationGate(
            meeting_id=meeting_id,
            topic=topic,
            max_rounds=max_rounds
        )
        
        # Round 0: Goal Alignment Phase
        gate.start_meeting(
            problem_definition=problem_definition,
            success_criteria=success_criteria,
            hard_constraints=hard_constraints,
            known_divergences=known_divergences
        )
        
        # 保存活跃会议
        self.active_meetings[meeting_id] = gate
        self.meeting_history.append(meeting_id)
        
        # 生成状态消息
        alignment_brief = gate.meeting_state.alignment_brief
        message = f"""
🎯 **Council Meeting Started**
📋 **Meeting ID**: `{meeting_id}`
📌 **Topic**: {topic}
🔄 **Phase**: Round 0 (Goal Alignment) ✅

**Alignment Brief**:
🎯 Problem: {problem_definition[:100]}...
✅ Success Criteria ({len(success_criteria)}):
{chr(10).join(f'  • {c}' for c in success_criteria[:3])}
{'  ...' if len(success_criteria) > 3 else ''}

⚠️ Hard Constraints ({len(hard_constraints)}):
{chr(10).join(f'  • {c}' for c in hard_constraints[:2])}
{'  ...' if len(hard_constraints) > 2 else ''}

💬 Use `!council deliberation` to start Round 1
"""
        
        # 持久化状态
        self._save_meeting_state(gate)
        
        return meeting_id, message
    
    async def start_deliberation_round(
        self,
        meeting_id: str,
        proposals: List[str],
        counter_arguments: List[str],
        unresolved_issues: List[str],
        blocking_demands: List[str],
        conditions: List[str],
        dimension_scores: Dict[str, float]
    ) -> Tuple[bool, str]:
        """
        执行一轮协商 (!council deliberation)
        
        自动评分并决定是否继续讨论
        """
        if meeting_id not in self.active_meetings:
            return False, f"❌ Meeting {meeting_id} not found"
        
        gate = self.active_meetings[meeting_id]
        
        print(f"\n💬 Running Deliberation Round")
        print(f"   Meeting: {meeting_id}")
        print(f"   Current Round: {gate.meeting_state.current_round}")
        
        # 执行协商轮
        summary, score = gate.run_deliberation_round(
            proposals=proposals,
            counter_arguments=counter_arguments,
            unresolved_issues=unresolved_issues,
            blocking_demands=blocking_demands,
            conditions=conditions,
            dimension_scores=dimension_scores
        )
        
        # 生成状态消息
        continue_flag = gate.meeting_state.continue_deliberation
        current_round = gate.meeting_state.current_round
        
        message = f"""
🎯 **Round {summary.round_id} Complete**
📋 **Meeting**: `{meeting_id}`
📊 **Score**: {score:.1f}/100

**Breakdown**:
{chr(10).join(f'  • {k}: {v:.1f}/20' for k, v in dimension_scores.items())}

**Status**: {'✅ Ready for execution' if score >= 95 else '➡️ Continue deliberation' if continue_flag else '⚠️ Consider rejection'}

**Current State**:
• Proposals: {len(proposals)}
• Counter-arguments: {len(counter_arguments)}
• Unresolved issues: {len(unresolved_issues)}
• Blocking demands: {len(blocking_demands)}

"""
        
        if continue_flag and current_round <= gate.meeting_state.max_rounds:
            message += f"💬 Use `!council deliberation` to continue to Round {current_round}"
        elif score >= 95:
            message += "✅ Score >= 95! Ready for final review. Use `!council review`"
        else:
            message += "⚠️ Max rounds reached or score too low. Consider rejection."
        
        # 持久化状态
        self._save_meeting_state(gate)
        
        return True, message
    
    async def conduct_review(self, meeting_id: str, reviewer_id: str = None) -> Tuple[bool, str]:
        """
        执行第三方审验 (!council review)
        """
        if meeting_id not in self.active_meetings:
            return False, f"❌ Meeting {meeting_id} not found"
        
        gate = self.active_meetings[meeting_id]
        
        print(f"\n🔍 Conducting Third-Party Review")
        print(f"   Meeting: {meeting_id}")
        
        # 执行审验
        report = gate.conduct_final_review()
        
        # 生成状态消息
        message = f"""
🔍 **Third-Party Review Complete**
👤 **Reviewer**: {report.reviewer_id}
📊 **Score**: {report.total_score:.1f}/100
📋 **Status**: {'✅ PASS' if report.passed else '❌ REJECT'}

**Dimension Scores**:
{chr(10).join(f'  • {k}: {v:.1f}/20' for k, v in report.scores.items())}

**Defects** ({len(report.defects)}):
{chr(10).join(f'  ⚠️ {d}' for d in report.defects) if report.defects else '  None'}

**Required Revisions** ({len(report.required_revisions)}):
{chr(10).join(f'  📝 {r}' for r in report.required_revisions) if report.required_revisions else '  None'}

"""
        
        if report.passed:
            message += "✅ **Execution Gate: OPEN**\nProposal approved for execution!"
            gate.meeting_state.execution_gate_passed = True
            gate.meeting_state.final_status = "approved"
        else:
            message += f"❌ **Execution Gate: CLOSED**\nScore {report.total_score:.1f} < 95. Proposal rejected."
            gate.meeting_state.final_status = "rejected"
        
        # 持久化最终状态
        self._save_meeting_state(gate)
        
        return True, message
    
    async def get_status(self, meeting_id: str) -> str:
        """
        获取会议状态 (!council status)
        """
        if meeting_id not in self.active_meetings:
            # 尝试从历史加载
            loaded = self._load_meeting_state(meeting_id)
            if loaded:
                return self._format_status_message(loaded)
            return f"❌ Meeting {meeting_id} not found"
        
        gate = self.active_meetings[meeting_id]
        return self._format_status_message(gate)
    
    async def close_meeting(self, meeting_id: str, final_decision: str = None) -> str:
        """
        关闭会议 (!council close)
        """
        if meeting_id not in self.active_meetings:
            return f"❌ Meeting {meeting_id} not found"
        
        gate = self.active_meetings[meeting_id]
        
        if final_decision:
            gate.meeting_state.final_status = final_decision
        
        # 生成会议报告
        report_path = os.path.join(self.storage_path, f"{meeting_id}_final_report.json")
        gate.save_state(report_path)
        
        # 从活跃会议中移除
        del self.active_meetings[meeting_id]
        
        message = f"""
🔒 **Council Meeting Closed**
📋 **Meeting ID**: `{meeting_id}`
📊 **Final Status**: {gate.meeting_state.final_status}
🔄 **Total Rounds**: {gate.meeting_state.current_round}
📄 **Report**: `{report_path}`

**Summary**:
• Alignment: ✅ Completed
• Deliberation Rounds: {len(gate.meeting_state.round_summaries)}
• Review Reports: {len(gate.meeting_state.review_reports)}
• Messages: {len(gate.meeting_state.message_log)}
• Execution Gate: {'✅ OPEN' if gate.meeting_state.execution_gate_passed else '❌ CLOSED'}

Meeting archived successfully.
"""
        
        return message
    
    async def send_agent_message(
        self,
        meeting_id: str,
        sender_id: str,
        receiver_id: str,
        message_type: str,
        content: str
    ) -> Tuple[bool, str]:
        """
        发送 agent 间消息 (!council message)
        """
        if meeting_id not in self.active_meetings:
            return False, f"❌ Meeting {meeting_id} not found"
        
        gate = self.active_meetings[meeting_id]
        
        try:
            message = gate.message_bus.send_message(
                sender_id=sender_id,
                receiver_id=receiver_id,
                message_type=message_type,
                content=content
            )
            
            # 持久化
            self._save_meeting_state(gate)
            
            return True, f"✅ Message sent: {message.message_id}"
        except ValueError as e:
            return False, f"❌ {str(e)}"
    
    def _save_meeting_state(self, gate: MultiRoundDeliberationGate):
        """持久化会议状态"""
        filepath = os.path.join(self.storage_path, f"{gate.meeting_state.meeting_id}_state.json")
        gate.save_state(filepath)
    
    def _load_meeting_state(self, meeting_id: str) -> Optional[MultiRoundDeliberationGate]:
        """从历史加载会议状态"""
        filepath = os.path.join(self.storage_path, f"{meeting_id}_state.json")
        if not os.path.exists(filepath):
            return None
        
        # 简化版：只加载基本状态
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # 创建新的 gate 对象并恢复状态
        gate = MultiRoundDeliberationGate(
            meeting_id=data['meeting_id'],
            topic=data['topic'],
            max_rounds=data.get('max_rounds', 5)
        )
        
        # 恢复状态
        gate.meeting_state.current_round = data['current_round']
        gate.meeting_state.alignment_status = data['alignment_status']
        gate.meeting_state.review_score = data.get('review_score')
        gate.meeting_state.review_passed = data.get('review_passed', False)
        gate.meeting_state.continue_deliberation = data.get('continue_deliberation', True)
        gate.meeting_state.final_status = data['final_status']
        gate.meeting_state.execution_gate_passed = data.get('execution_gate_passed', False)
        
        self.active_meetings[meeting_id] = gate
        return gate
    
    def _format_status_message(self, gate: MultiRoundDeliberationGate) -> str:
        """格式化状态消息"""
        state = gate.meeting_state
        
        current_round = state.current_round
        alignment_status = "✅ Completed" if state.alignment_status == "completed" else "⏳ Pending"
        
        latest_score = state.review_score if state.review_score else "N/A"
        
        message = f"""
📊 **Council Meeting Status**
📋 **Meeting ID**: `{state.meeting_id}`
📌 **Topic**: {state.topic}
🔄 **Current Round**: {current_round}
🎯 **Alignment**: {alignment_status}
📊 **Latest Score**: {latest_score if isinstance(latest_score, str) else f'{latest_score:.1f}/100'}
📈 **Status**: {state.final_status.upper()}

**Progress**:
• Deliberation Rounds: {len(state.round_summaries)}
• Review Reports: {len(state.review_reports)}
• Messages: {len(state.message_log)}
• Execution Gate: {'✅ OPEN' if state.execution_gate_passed else '❌ CLOSED'}
"""
        
        if state.round_summaries:
            latest_round = state.round_summaries[-1]
            message += f"""
**Latest Round ({latest_round.round_id})**:
• Score: {latest_round.score if latest_round.score else 'N/A'}
• Proposals: {len(latest_round.proposals)}
• Counter-arguments: {len(latest_round.counter_arguments)}
• Unresolved: {len(latest_round.unresolved_issues)}
• Blocking: {len(latest_round.blocking_demands)}
"""
        
        return message


class MatrixBotCommands:
    """
    Matrix Bot 命令处理器
    
    处理 !council start/status/close/deliberation/review/message
    """
    
    def __init__(self):
        self.council = MatrixBridgeCouncil()
        print("🤖 MatrixBotCommands initialized")
    
    async def handle_command(self, command: str, args: Dict, room_id: str) -> str:
        """
        处理 Matrix 命令
        
        支持的命令:
        - !council start topic="..." problem="..." criteria=[...] constraints=[...]
        - !council status meeting_id=...
        - !council deliberation meeting_id=... proposals=[...] scores={...}
        - !council review meeting_id=...
        - !council close meeting_id=... decision=...
        - !council message meeting_id=... from=... to=... type=... content=...
        """
        cmd = command.lower()
        
        if cmd == "start":
            return await self._cmd_start(args, room_id)
        elif cmd == "status":
            return await self._cmd_status(args)
        elif cmd == "deliberation":
            return await self._cmd_deliberation(args)
        elif cmd == "review":
            return await self._cmd_review(args)
        elif cmd == "close":
            return await self._cmd_close(args)
        elif cmd == "message":
            return await self._cmd_message(args)
        else:
            return f"❌ Unknown command: {cmd}. Available: start, status, deliberation, review, close, message"
    
    async def _cmd_start(self, args: Dict, room_id: str) -> str:
        """处理 !council start"""
        topic = args.get("topic", "Untitled Meeting")
        problem = args.get("problem", "No problem definition provided")
        criteria = args.get("criteria", []).split(",") if isinstance(args.get("criteria"), str) else args.get("criteria", [])
        constraints = args.get("constraints", []).split(",") if isinstance(args.get("constraints"), str) else args.get("constraints", [])
        divergences = args.get("divergences", []).split(",") if isinstance(args.get("divergences"), str) else args.get("divergences", [])
        max_rounds = int(args.get("max_rounds", 5))
        
        meeting_id, message = await self.council.start_council(
            room_id=room_id,
            topic=topic,
            problem_definition=problem,
            success_criteria=criteria,
            hard_constraints=constraints,
            known_divergences=divergences,
            max_rounds=max_rounds
        )
        
        return message
    
    async def _cmd_status(self, args: Dict) -> str:
        """处理 !council status"""
        meeting_id = args.get("meeting_id")
        if not meeting_id:
            return "❌ Usage: !council status meeting_id=xxx"
        
        return await self.council.get_status(meeting_id)
    
    async def _cmd_deliberation(self, args: Dict) -> str:
        """处理 !council deliberation"""
        meeting_id = args.get("meeting_id")
        if not meeting_id:
            return "❌ Usage: !council deliberation meeting_id=xxx proposals=..."
        
        # 解析参数
        proposals = args.get("proposals", "").split("|") if args.get("proposals") else []
        counter_args = args.get("counter", "").split("|") if args.get("counter") else []
        unresolved = args.get("unresolved", "").split("|") if args.get("unresolved") else []
        blocking = args.get("blocking", "").split("|") if args.get("blocking") else []
        conditions = args.get("conditions", "").split("|") if args.get("conditions") else []
        
        # 解析评分
        scores = {}
        for dim in ["goal_alignment", "risk_closure", "executability", "counter_absorption", "audit_completeness"]:
            if dim in args:
                scores[dim] = float(args[dim])
            else:
                scores[dim] = 15.0  # 默认值
        
        success, message = await self.council.start_deliberation_round(
            meeting_id=meeting_id,
            proposals=proposals,
            counter_arguments=counter_args,
            unresolved_issues=unresolved,
            blocking_demands=blocking,
            conditions=conditions,
            dimension_scores=scores
        )
        
        return message
    
    async def _cmd_review(self, args: Dict) -> str:
        """处理 !council review"""
        meeting_id = args.get("meeting_id")
        reviewer = args.get("reviewer")
        
        if not meeting_id:
            return "❌ Usage: !council review meeting_id=xxx"
        
        success, message = await self.council.conduct_review(meeting_id, reviewer)
        return message
    
    async def _cmd_close(self, args: Dict) -> str:
        """处理 !council close"""
        meeting_id = args.get("meeting_id")
        decision = args.get("decision")
        
        if not meeting_id:
            return "❌ Usage: !council close meeting_id=xxx"
        
        return await self.council.close_meeting(meeting_id, decision)
    
    async def _cmd_message(self, args: Dict) -> str:
        """处理 !council message"""
        meeting_id = args.get("meeting_id")
        sender = args.get("from")
        receiver = args.get("to")
        msg_type = args.get("type")
        content = args.get("content")
        
        if not all([meeting_id, sender, receiver, msg_type, content]):
            return "❌ Usage: !council message meeting_id=xxx from=xxx to=xxx type=xxx content=xxx"
        
        success, message = await self.council.send_agent_message(
            meeting_id=meeting_id,
            sender_id=sender,
            receiver_id=receiver,
            message_type=msg_type,
            content=content
        )
        
        return message


# 演示
async def demo():
    """演示 Round 15.1 完整流程"""
    
    print("="*70)
    print("Round 15.1: Matrix Bridge Integration Demo")
    print("="*70)
    
    bot = MatrixBotCommands()
    room_id = "!demo:matrix.org"
    
    # 1. Start council
    print("\n[1] !council start")
    result = await bot.handle_command("start", {
        "topic": "是否集成 ConsensusPredictor",
        "problem": "评估 ConsensusPredictor 是否达到生产环境集成标准",
        "criteria": "ECE<0.22,Rolling ECE<0.18,High-conf error<18%,200+ samples",
        "constraints": "不影响主逻辑,必须通过影子模式,门槛不可更改",
        "divergences": "模型校准问题,输出范围受限"
    }, room_id)
    print(result)
    
    # 从结果中提取 meeting_id
    import re
    meeting_id_match = re.search(r'`(council_[^`]+)`', result)
    meeting_id = meeting_id_match.group(1) if meeting_id_match else None
    
    if not meeting_id:
        print("❌ Failed to extract meeting_id")
        return
    
    print(f"   Extracted meeting_id: {meeting_id}")
    
    # 2. Check status
    print("\n[2] !council status")
    result = await bot.handle_command("status", {"meeting_id": meeting_id}, room_id)
    print(result)
    
    # 3. Round 1 deliberation
    print("\n[3] !council deliberation (Round 1)")
    result = await bot.handle_command("deliberation", {
        "meeting_id": meeting_id,
        "proposals": "模型基本可用|建议启动影子模式",
        "counter": "ECE超标|输出范围受限",
        "unresolved": "如何修复欠自信|是否需重训练",
        "blocking": "必须解决校准问题",
        "conditions": "修复后可考虑",
        "goal_alignment": "18",
        "risk_closure": "12",
        "executability": "10",
        "counter_absorption": "14",
        "audit_completeness": "16"
    }, room_id)
    print(result)
    
    # 4. Send message
    print("\n[4] !council message")
    result = await bot.handle_command("message", {
        "meeting_id": meeting_id,
        "from": "LOGOS",
        "to": "Casey",
        "type": "challenge",
        "content": "ECE 数据是否准确？"
    }, room_id)
    print(result)
    
    # 5. Round 2 deliberation
    print("\n[5] !council deliberation (Round 2)")
    result = await bot.handle_command("deliberation", {
        "meeting_id": meeting_id,
        "proposals": "放弃当前模型|保持Python主逻辑",
        "goal_alignment": "19",
        "risk_closure": "18",
        "executability": "19",
        "counter_absorption": "18",
        "audit_completeness": "19"
    }, room_id)
    print(result)
    
    # 6. Review
    print("\n[6] !council review")
    result = await bot.handle_command("review", {
        "meeting_id": meeting_id,
        "reviewer": "钟馗"
    }, room_id)
    print(result)
    
    # 7. Close
    print("\n[7] !council close")
    result = await bot.handle_command("close", {
        "meeting_id": meeting_id,
        "decision": "rejected"
    }, room_id)
    print(result)
    
    print("\n" + "="*70)
    print("Demo Complete!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(demo())

#!/usr/bin/env python3
"""
Goal Alignment Intake Wizard
目标对齐摄入向导 (模块 #6)

作用: 在正式开会前先把模糊需求压成结构化 brief
接入位置: Goal Alignment Phase / Round 0

为什么值得做: 能把"产品经理式问题"前置，不让 19 席直接在模糊问题上乱跑
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class IntakeStatus(Enum):
    """摄入状态"""
    RAW = "raw"                    # 原始输入
    CLARIFYING = "clarifying"      # 正在澄清
    STRUCTURED = "structured"      # 已结构化
    VALIDATED = "validated"        # 已验证
    REJECTED = "rejected"          # 被拒绝


@dataclass
class RawIntake:
    """原始需求摄入"""
    intake_id: str
    timestamp: str
    source: str                    # matrix / api / internal
    raw_text: str                  # 原始文本
    submitter_id: str              # 提交者
    
    def to_dict(self) -> Dict:
        return {
            "intake_id": self.intake_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "raw_text": self.raw_text,
            "submitter_id": self.submitter_id
        }


@dataclass
class StructuredBrief:
    """结构化简报输出"""
    # 核心字段 (必须)
    topic: str
    problem_definition: str
    success_criteria: List[str]
    
    # 约束字段 (必须)
    hard_constraints: List[str]
    
    # 可选字段
    known_divergences: List[str] = field(default_factory=list)
    priority: str = "normal"       # critical / high / normal / low
    deadline: Optional[str] = None
    involved_domains: List[str] = field(default_factory=list)
    
    # 元数据
    extracted_at: str = ""
    confidence_score: float = 0.0  # 提取置信度 0-1
    missing_fields: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "topic": self.topic,
            "problem_definition": self.problem_definition,
            "success_criteria": self.success_criteria,
            "hard_constraints": self.hard_constraints,
            "known_divergences": self.known_divergences,
            "priority": self.priority,
            "deadline": self.deadline,
            "involved_domains": self.involved_domains,
            "extracted_at": self.extracted_at,
            "confidence_score": self.confidence_score,
            "missing_fields": self.missing_fields
        }
    
    def is_complete(self) -> bool:
        """检查是否完整"""
        return (
            len(self.topic) > 0 and
            len(self.problem_definition) > 0 and
            len(self.success_criteria) > 0 and
            len(self.hard_constraints) > 0 and
            len(self.missing_fields) == 0
        )


class GoalAlignmentIntakeWizard:
    """
    目标对齐摄入向导
    
    处理流程:
    1. 接收原始需求 (自然语言/模糊输入)
    2. 提取结构化字段
    3. 识别缺失信息
    4. 生成澄清问题
    5. 输出标准化 AlignmentBrief
    """
    
    # 提取模式
    PATTERNS = {
        'topic': [
            r'(?:关于|主题|议题|讨论)[：:]\s*([^\n。]+)',
            r'(?:topic|subject)[：:]\s*([^\n]+)',
            r'^\s*([^\n]{5,50})\s*(?:\n|$)'
        ],
        'problem': [
            r'(?:问题|痛点|背景)[：:]\s*([^\n]+(?:\n[^\n]+){0,5})',
            r'(?:problem|issue|background)[：:]\s*([^\n]+(?:\n[^\n]+){0,5})',
            r'(?:需要|要|希望)([^\n]{10,200})(?:解决|评估|讨论)'
        ],
        'criteria': [
            r'(?:成功标准|验收条件|标准)[：:]\s*((?:[^\n]+\n?)+?)(?:\n\n|\n(?:约束|禁区|限制)|$)',
            r'(?:criteria|success|goal)[：:]\s*((?:[^\n]+\n?)+?)(?:\n\n|\nconstraint|$)',
            r'(?:达到|满足|符合)([^\n，。]+(?:[，,][^\n，。]+)*)'
        ],
        'constraints': [
            r'(?:约束|禁区|限制|硬约束)[：:]\s*((?:[^\n]+\n?)+?)(?:\n\n|$)',
            r'(?:constraints|limitations|must not)[：:]\s*((?:[^\n]+\n?)+?)(?:\n\n|$)',
            r'(?:不能|不可|禁止|必须不)([^\n，。]+)'
        ],
        'priority': [
            r'(?:优先级|紧急程度|priority)[：:]\s*(critical|high|normal|low|紧急|高|中|低)',
            r'(紧急|critical|urgent|高优先级)',
        ]
    }
    
    def __init__(self, storage_path: str = "/home/admin/CodeBuddy/20260310101858/data/intake"):
        self.storage_path = storage_path
        self.intake_history: List[RawIntake] = []
        self.structured_history: List[StructuredBrief] = []
    
    def intake(self, raw_text: str, submitter_id: str, source: str = "matrix") -> Tuple[IntakeStatus, StructuredBrief, List[str]]:
        """
        摄入原始需求
        
        Args:
            raw_text: 原始输入文本
            submitter_id: 提交者ID
            source: 来源 (matrix/api/internal)
            
        Returns:
            (status, structured_brief, clarification_questions)
        """
        # 记录原始摄入
        intake_record = RawIntake(
            intake_id=f"intake_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{submitter_id[:8]}",
            timestamp=datetime.now().isoformat(),
            source=source,
            raw_text=raw_text,
            submitter_id=submitter_id
        )
        self.intake_history.append(intake_record)
        
        # 提取结构化信息
        structured = self._extract_structure(raw_text)
        structured.extracted_at = datetime.now().isoformat()
        
        # 评估完整性
        missing = self._identify_missing(structured)
        structured.missing_fields = missing
        
        # 计算置信度
        confidence = self._calculate_confidence(structured, raw_text)
        structured.confidence_score = confidence
        
        # 生成澄清问题
        questions = self._generate_clarification_questions(structured, missing)
        
        # 确定状态
        if len(missing) == 0 and confidence >= 0.8:
            status = IntakeStatus.VALIDATED
            self.structured_history.append(structured)
        elif len(missing) <= 2 and confidence >= 0.6:
            status = IntakeStatus.STRUCTURED
        else:
            status = IntakeStatus.CLARIFYING
        
        return status, structured, questions
    
    def _extract_structure(self, text: str) -> StructuredBrief:
        """从文本中提取结构化信息"""
        
        # 提取主题
        topic = self._extract_field(text, 'topic', "未命名议题")
        topic = topic.strip()[:100]  # 限制长度
        
        # 提取问题定义
        problem = self._extract_field(text, 'problem', "")
        if not problem:
            # 如果没有显式问题定义，用前200字符
            problem = text[:200].strip()
        problem = problem[:500]
        
        # 提取成功标准
        criteria_text = self._extract_field(text, 'criteria', "")
        success_criteria = self._split_items(criteria_text) if criteria_text else []
        if not success_criteria:
            # 尝试从文本中提取列表
            success_criteria = self._extract_list_items(text)
        
        # 提取约束
        constraints_text = self._extract_field(text, 'constraints', "")
        hard_constraints = self._split_items(constraints_text) if constraints_text else []
        
        # 提取优先级
        priority_match = self._extract_field(text, 'priority', "normal")
        priority_map = {
            '紧急': 'critical', 'critical': 'critical', 'urgent': 'critical',
            '高': 'high', 'high': 'high',
            '中': 'normal', 'normal': 'normal',
            '低': 'low', 'low': 'low'
        }
        priority = priority_map.get(priority_match.lower(), 'normal')
        
        # 提取分歧点 (从"但是"、"然而"等转折词)
        divergences = self._extract_divergences(text)
        
        return StructuredBrief(
            topic=topic,
            problem_definition=problem,
            success_criteria=success_criteria,
            hard_constraints=hard_constraints,
            known_divergences=divergences,
            priority=priority
        )
    
    def _extract_field(self, text: str, field_name: str, default: str = "") -> str:
        """使用模式提取字段"""
        patterns = self.PATTERNS.get(field_name, [])
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1).strip()
        return default
    
    def _split_items(self, text: str) -> List[str]:
        """将文本分割成列表项"""
        if not text:
            return []
        
        # 尝试多种分隔符
        for sep in ['\n', '；', ';', '，,']:
            if sep in text:
                items = [item.strip() for item in text.split(sep) if item.strip()]
                if len(items) > 1:
                    return items
        
        # 如果没有分隔符，返回整个文本
        return [text.strip()] if text.strip() else []
    
    def _extract_list_items(self, text: str) -> List[str]:
        """从文本中提取列表项 (如 1. xxx 2. xxx)"""
        pattern = r'(?:^|\n)\s*(?:\d+[.．]|[-•*])\s*([^\n]+)'
        matches = re.findall(pattern, text)
        return [m.strip() for m in matches if len(m.strip()) > 5]
    
    def _extract_divergences(self, text: str) -> List[str]:
        """提取已知分歧点"""
        divergences = []
        
        # 转折词模式
        patterns = [
            r'(?:但是|然而|不过|只是)[，,]?\s*([^\n。]{10,200})',
            r'(?:分歧|争议|不同意见)[：:]\s*([^\n]+)',
            r'(?:concern|worry|worried about)[：:]?\s*([^\n]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            divergences.extend(matches)
        
        return divergences[:5]  # 限制数量
    
    def _identify_missing(self, brief: StructuredBrief) -> List[str]:
        """识别缺失的字段"""
        missing = []
        
        if not brief.topic or brief.topic == "未命名议题":
            missing.append("topic")
        if not brief.problem_definition or len(brief.problem_definition) < 20:
            missing.append("problem_definition")
        if len(brief.success_criteria) == 0:
            missing.append("success_criteria")
        if len(brief.hard_constraints) == 0:
            missing.append("hard_constraints")
        
        return missing
    
    def _calculate_confidence(self, brief: StructuredBrief, raw_text: str) -> float:
        """计算提取置信度"""
        scores = []
        
        # 主题质量
        if brief.topic and len(brief.topic) > 5:
            scores.append(0.2)
        
        # 问题定义质量
        if brief.problem_definition and len(brief.problem_definition) > 30:
            scores.append(0.2)
        
        # 成功标准数量
        if len(brief.success_criteria) >= 3:
            scores.append(0.2)
        elif len(brief.success_criteria) >= 1:
            scores.append(0.1)
        
        # 约束数量
        if len(brief.hard_constraints) >= 1:
            scores.append(0.2)
        
        # 输入长度 (作为质量的粗略指标)
        if len(raw_text) > 100:
            scores.append(0.2)
        elif len(raw_text) > 50:
            scores.append(0.1)
        
        return sum(scores)
    
    def _generate_clarification_questions(self, brief: StructuredBrief, missing: List[str]) -> List[str]:
        """生成澄清问题"""
        questions = []
        
        question_map = {
            "topic": "请明确这次会议的主题或议题名称是什么？",
            "problem_definition": "请详细描述需要解决的具体问题或背景？",
            "success_criteria": "请列出判断这次会议成功的标准（至少3条）",
            "hard_constraints": "请说明必须遵守的约束条件或禁区"
        }
        
        for field in missing:
            if field in question_map:
                questions.append(question_map[field])
        
        # 如果有分歧点，添加相关问题
        if brief.known_divergences:
            questions.append(f"检测到{brief.priority}优先级议题，是否有其他需要考虑的分歧点？")
        
        return questions
    
    def refine_with_clarification(self, brief: StructuredBrief, clarification_text: str) -> StructuredBrief:
        """使用澄清回答优化简报"""
        # 提取新信息
        new_criteria = self._extract_list_items(clarification_text)
        new_constraints = self._split_items(clarification_text)
        
        # 合并信息
        if new_criteria and len(brief.success_criteria) < 3:
            brief.success_criteria.extend(new_criteria)
            brief.success_criteria = brief.success_criteria[:5]  # 限制数量
        
        if new_constraints and len(brief.hard_constraints) < 2:
            brief.hard_constraints.extend([c for c in new_constraints if c not in brief.hard_constraints])
            brief.hard_constraints = brief.hard_constraints[:5]
        
        # 重新评估
        brief.missing_fields = self._identify_missing(brief)
        
        return brief
    
    def to_alignment_brief(self, structured: StructuredBrief) -> Dict:
        """转换为 Round 15 的 AlignmentBrief 格式"""
        return {
            "topic": structured.topic,
            "problem_definition": structured.problem_definition,
            "success_criteria": structured.success_criteria,
            "hard_constraints": structured.hard_constraints,
            "known_divergences": structured.known_divergences
        }


# 演示
if __name__ == "__main__":
    wizard = GoalAlignmentIntakeWizard()
    
    # 测试用例 1: 模糊输入
    raw_input_1 = """
    我们想讨论一下那个预测器的事情
    感觉好像不太对
    """
    
    print("=" * 60)
    print("Test 1: 模糊输入")
    print("=" * 60)
    status, brief, questions = wizard.intake(raw_input_1, "user_001")
    print(f"Status: {status.value}")
    print(f"Confidence: {brief.confidence_score:.2f}")
    print(f"Missing: {brief.missing_fields}")
    print(f"Questions:\n" + "\n".join(f"  Q: {q}" for q in questions))
    
    # 测试用例 2: 结构化输入
    raw_input_2 = """
    主题：是否集成 ConsensusPredictor
    
    问题：评估 ConsensusPredictor 是否达到生产环境集成标准，当前存在模型校准问题
    
    成功标准：
    1. ECE < 0.22
    2. Rolling ECE < 0.18
    3. High-confidence error < 18%
    4. 200+ samples collected
    
    约束：
    - 不影响主逻辑
    - 必须通过影子模式
    - 门槛不可更改
    
    分歧：模型校准问题可能导致欠自信，输出范围受限
    优先级：Critical
    """
    
    print("\n" + "=" * 60)
    print("Test 2: 结构化输入")
    print("=" * 60)
    status, brief, questions = wizard.intake(raw_input_2, "user_002")
    print(f"Status: {status.value}")
    print(f"Topic: {brief.topic}")
    print(f"Problem: {brief.problem_definition[:50]}...")
    print(f"Criteria: {brief.success_criteria}")
    print(f"Constraints: {brief.hard_constraints}")
    print(f"Divergences: {brief.known_divergences}")
    print(f"Priority: {brief.priority}")
    print(f"Confidence: {brief.confidence_score:.2f}")
    print(f"Is Complete: {brief.is_complete()}")

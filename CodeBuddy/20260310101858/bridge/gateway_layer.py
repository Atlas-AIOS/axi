#!/usr/bin/env python3
"""
Gateway Layer - 网关层

包含3个模块:
1. Request Replay Parser (模块 #1) - 请求解析与路由信号提取
2. Header Sanitization Layer (模块 #2) - 输入净化层  
3. Audit-First Gateway (模块 #5) - 审计优先网关

接入位置: Matrix Bridge Integration 前置网关层
"""

import json
import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import copy


class RoutingDecision(Enum):
    """路由决策"""
    PROCEED = "proceed"           # 继续处理
    REJECT = "reject"             # 拒绝
    SANITIZE = "sanitize"         # 需要净化
    AUDIT_ONLY = "audit_only"     # 仅审计，不处理
    RATE_LIMIT = "rate_limit"     # 限流


@dataclass
class ParsedRequest:
    """解析后的请求"""
    # 标识
    request_id: str
    timestamp: str
    
    # 来源信息
    source_type: str              # matrix / api / webhook / internal
    room_id: Optional[str] = None
    user_id: Optional[str] = None
    client_ip: Optional[str] = None
    
    # 命令信息
    command: str = ""             # start / status / deliberation / review / close / message
    raw_args: Dict[str, Any] = field(default_factory=dict)
    
    # 路由信号
    route_signals: Dict[str, Any] = field(default_factory=dict)
    
    # 原始body (可用于重放)
    raw_body: str = ""
    body_hash: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "source_type": self.source_type,
            "room_id": self.room_id,
            "user_id": self.user_id,
            "client_ip": self.client_ip,
            "command": self.command,
            "raw_args": self.raw_args,
            "route_signals": self.route_signals,
            "body_hash": self.body_hash
        }


@dataclass
class SanitizedRequest:
    """净化后的请求"""
    original_request: ParsedRequest
    
    # 净化记录
    removed_headers: List[str] = field(default_factory=list)
    modified_fields: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)  # field: (old, new)
    sanitization_reasons: List[str] = field(default_factory=list)
    
    # 净化后的值
    clean_args: Dict[str, Any] = field(default_factory=dict)
    
    # 风险标记
    risk_flags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "request_id": self.original_request.request_id,
            "removed_headers": self.removed_headers,
            "modified_fields": {k: {"from": v[0], "to": v[1]} for k, v in self.modified_fields.items()},
            "sanitization_reasons": self.sanitization_reasons,
            "risk_flags": self.risk_flags,
            "is_clean": len(self.risk_flags) == 0
        }


@dataclass
class AuditEntry:
    """审计条目"""
    entry_id: str
    timestamp: str
    request_id: str
    
    # 路由信息
    gateway_action: str           # parse / sanitize / route / reject
    routing_decision: str
    
    # 参与者
    source_type: str
    user_id: Optional[str]
    room_id: Optional[str]
    
    # 内容摘要
    command: str
    arg_summary: Dict[str, Any]   # 脱敏后的参数
    
    # 决策依据
    decision_factors: List[str] = field(default_factory=list)
    
    # 下游处理
    downstream_service: Optional[str] = None
    processing_time_ms: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "gateway_action": self.gateway_action,
            "routing_decision": self.routing_decision,
            "source_type": self.source_type,
            "user_id": self.user_id,
            "room_id": self.room_id,
            "command": self.command,
            "arg_summary": self.arg_summary,
            "decision_factors": self.decision_factors,
            "downstream_service": self.downstream_service,
            "processing_time_ms": self.processing_time_ms
        }


class RequestReplayParser:
    """
    请求重放解析器 (模块 #1)
    
    作用: 先读请求体，提取路由信号，再把 body 放回去供下游继续用
    """
    
    # 命令模式
    COMMAND_PATTERNS = {
        'start': r'!council\s+start',
        'status': r'!council\s+status',
        'deliberation': r'!council\s+deliberation',
        'review': r'!council\s+review',
        'close': r'!council\s+close',
        'message': r'!council\s+message'
    }
    
    # 路由信号提取模式
    ROUTE_SIGNALS = {
        'has_topic': lambda args: 'topic' in args and len(args.get('topic', '')) > 0,
        'has_meeting_id': lambda args: 'meeting_id' in args,
        'is_admin': lambda args, user_id: user_id and user_id.startswith('@admin'),
        'urgent_keywords': lambda args: any(kw in str(args).lower() for kw in ['urgent', 'critical', '紧急', 'critical']),
        'has_risk_level': lambda args: 'risk_level' in args,
        'extended_personas': lambda args: 'extended_personas' in args or 'personas' in args,
    }
    
    def parse(self, raw_body: str, source_type: str = "matrix", 
              room_id: str = None, user_id: str = None, client_ip: str = None) -> ParsedRequest:
        """
        解析请求
        
        Args:
            raw_body: 原始请求体
            source_type: 来源类型
            room_id: 房间ID
            user_id: 用户ID
            client_ip: 客户端IP
            
        Returns:
            ParsedRequest 对象
        """
        # 生成请求ID
        body_hash = hashlib.sha256(raw_body.encode()).hexdigest()[:16]
        request_id = f"req_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{body_hash[:8]}"
        
        # 识别命令
        command = self._extract_command(raw_body)
        
        # 解析参数
        args = self._parse_args(raw_body)
        
        # 提取路由信号
        route_signals = self._extract_route_signals(args, user_id)
        
        return ParsedRequest(
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            source_type=source_type,
            room_id=room_id,
            user_id=user_id,
            client_ip=client_ip,
            command=command,
            raw_args=args,
            route_signals=route_signals,
            raw_body=raw_body,
            body_hash=body_hash
        )
    
    def _extract_command(self, body: str) -> str:
        """从请求体中提取命令"""
        body_lower = body.lower()
        
        for cmd, pattern in self.COMMAND_PATTERNS.items():
            if re.search(pattern, body_lower):
                return cmd
        
        return "unknown"
    
    def _parse_args(self, body: str) -> Dict[str, Any]:
        """解析命令参数"""
        args = {}
        
        # 提取 key="value" 或 key='value' 或 key=value 格式
        patterns = [
            r'(\w+)=["\']([^"\']+)["\']',  # key="value" or key='value'
            r'(\w+)=([^\s]+)',              # key=value
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, body)
            for key, value in matches:
                if key not in args:  # 避免重复
                    args[key] = value
        
        # 提取列表参数 (key=[item1,item2])
        list_pattern = r'(\w+)=[\[\{]([^\]\}]+)[\]\}]'
        for match in re.finditer(list_pattern, body):
            key = match.group(1)
            items = [item.strip().strip('"\'') for item in match.group(2).split(',')]
            args[key] = items
        
        return args
    
    def _extract_route_signals(self, args: Dict, user_id: str) -> Dict[str, Any]:
        """提取路由信号"""
        signals = {}
        
        for signal_name, extractor in self.ROUTE_SIGNALS.items():
            try:
                if signal_name == 'is_admin':
                    signals[signal_name] = extractor(args, user_id)
                else:
                    signals[signal_name] = extractor(args)
            except:
                signals[signal_name] = False
        
        # 计算综合路由信号
        signals['requires_persistence'] = signals.get('has_meeting_id', False) or signals.get('has_topic', False)
        signals['requires_admin'] = False  # 目前没有需要admin的命令
        signals['is_complex_deliberation'] = signals.get('has_risk_level', False) or signals.get('extended_personas', False)
        
        return signals
    
    def get_body_for_downstream(self, parsed: ParsedRequest) -> str:
        """获取可重放的body供下游使用"""
        return parsed.raw_body


class HeaderSanitizationLayer:
    """
    Header 净化层 (模块 #2)
    
    作用: 清洗外部输入头，避免用户请求把内部 worker / route / account 痕迹带进来
    """
    
    # 敏感字段模式 (需要移除或脱敏)
    SENSITIVE_PATTERNS = [
        r'password\s*[=:]\s*\S+',
        r'token\s*[=:]\s*\S+',
        r'secret\s*[=:]\s*\S+',
        r'api[_-]?key\s*[=:]\s*\S+',
        r'auth\s*[=:]\s*\S+',
        r'credential\s*[=:]\s*\S+',
    ]
    
    # 需要检查的风险关键词
    RISK_KEYWORDS = [
        '<script', 'javascript:', 'onerror=', 'onload=',
        'SELECT * FROM', 'DROP TABLE', 'DELETE FROM',
        '${', '{{', '{%', '<%',
        '../', '..\\', '/etc/passwd', '\\x00'
    ]
    
    # 长度限制
    MAX_FIELD_LENGTHS = {
        'topic': 200,
        'problem': 2000,
        'content': 5000,
        'proposals': 10000,
    }
    
    def sanitize(self, parsed_request: ParsedRequest) -> SanitizedRequest:
        """
        净化请求
        
        Args:
            parsed_request: 解析后的请求
            
        Returns:
            SanitizedRequest 对象
        """
        sanitized = SanitizedRequest(
            original_request=parsed_request,
            clean_args=copy.deepcopy(parsed_request.raw_args)
        )
        
        # 1. 移除敏感信息
        self._remove_sensitive_data(sanitized)
        
        # 2. 检查并限制字段长度
        self._enforce_length_limits(sanitized)
        
        # 3. 检查注入风险
        self._check_injection_risks(sanitized)
        
        # 4. 规范化字段值
        self._normalize_values(sanitized)
        
        return sanitized
    
    def _remove_sensitive_data(self, sanitized: SanitizedRequest):
        """移除敏感数据"""
        args = sanitized.clean_args
        
        for key in list(args.keys()):
            value = str(args[key])
            
            for pattern in self.SENSITIVE_PATTERNS:
                if re.search(pattern, value, re.IGNORECASE):
                    # 记录被移除的内容
                    sanitized.removed_headers.append(f"{key}: [SENSITIVE_DATA_REMOVED]")
                    sanitized.sanitization_reasons.append(f"Removed sensitive data from {key}")
                    
                    # 替换为脱敏版本
                    old_value = args[key]
                    args[key] = "[REDACTED]"
                    sanitized.modified_fields[key] = (old_value, "[REDACTED]")
                    break
    
    def _enforce_length_limits(self, sanitized: SanitizedRequest):
        """强制执行长度限制"""
        args = sanitized.clean_args
        
        for field, max_len in self.MAX_FIELD_LENGTHS.items():
            if field in args:
                value = str(args[field])
                if len(value) > max_len:
                    old_value = args[field]
                    args[field] = value[:max_len] + "... [TRUNCATED]"
                    sanitized.modified_fields[field] = (old_value, args[field])
                    sanitized.sanitization_reasons.append(f"Truncated {field} from {len(value)} to {max_len} chars")
    
    def _check_injection_risks(self, sanitized: SanitizedRequest):
        """检查注入风险"""
        args = sanitized.clean_args
        
        for key, value in args.items():
            value_str = str(value).lower()
            
            for keyword in self.RISK_KEYWORDS:
                if keyword.lower() in value_str:
                    sanitized.risk_flags.append(f"potential_injection:{key}")
                    sanitized.sanitization_reasons.append(f"Flagged potential injection in {key}: {keyword}")
                    
                    # 转义危险字符
                    old_value = args[key]
                    cleaned = self._escape_dangerous_chars(str(value))
                    args[key] = cleaned
                    
                    if cleaned != old_value:
                        sanitized.modified_fields[key] = (old_value, cleaned)
                    break
    
    def _escape_dangerous_chars(self, value: str) -> str:
        """转义危险字符"""
        # 替换危险的HTML/脚本字符
        replacements = [
            ('<', '&lt;'),
            ('>', '&gt;'),
            ('"', '&quot;'),
            ("'", '&#x27;'),
        ]
        
        result = value
        for old, new in replacements:
            result = result.replace(old, new)
        
        return result
    
    def _normalize_values(self, sanitized: SanitizedRequest):
        """规范化字段值"""
        args = sanitized.clean_args
        
        # 规范化 meeting_id
        if 'meeting_id' in args:
            meeting_id = str(args['meeting_id']).strip()
            # 移除可能的危险字符
            meeting_id = re.sub(r'[^\w\-_]', '', meeting_id)
            if meeting_id != args['meeting_id']:
                old_value = args['meeting_id']
                args['meeting_id'] = meeting_id
                sanitized.modified_fields['meeting_id'] = (old_value, meeting_id)
        
        # 规范化命令类型
        if 'type' in args and sanitized.original_request.command == 'message':
            valid_types = ['clarification', 'challenge', 'dependency_request']
            msg_type = str(args['type']).lower().strip()
            if msg_type not in valid_types:
                old_value = args['type']
                args['type'] = 'clarification'  # 默认为澄清
                sanitized.modified_fields['type'] = (old_value, 'clarification')
                sanitized.sanitization_reasons.append(f"Invalid message type '{old_value}', defaulted to 'clarification'")


class AuditFirstGateway:
    """
    审计优先网关 (模块 #5)
    
    作用: 每次路由、切换、降级、出口、认证都生成审计链
    接入位置: 网关层与执行层的边界
    """
    
    def __init__(self, storage_path: str = "/home/admin/CodeBuddy/20260310101858/logs/gateway_audit"):
        self.storage_path = storage_path
        self.audit_chain: List[AuditEntry] = []
        self.decision_log: List[Dict] = []
    
    def record_parse(self, parsed_request: ParsedRequest) -> AuditEntry:
        """记录解析事件"""
        entry = AuditEntry(
            entry_id=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{parsed_request.request_id[:8]}",
            timestamp=datetime.now().isoformat(),
            request_id=parsed_request.request_id,
            gateway_action="parse",
            routing_decision="proceed",
            source_type=parsed_request.source_type,
            user_id=parsed_request.user_id,
            room_id=parsed_request.room_id,
            command=parsed_request.command,
            arg_summary=self._sanitize_args_for_audit(parsed_request.raw_args),
            decision_factors=["command_parsed", "args_extracted"]
        )
        
        self.audit_chain.append(entry)
        return entry
    
    def record_sanitization(self, sanitized: SanitizedRequest) -> AuditEntry:
        """记录净化事件"""
        req = sanitized.original_request
        
        decision = "proceed"
        factors = ["sanitization_applied"]
        
        if sanitized.risk_flags:
            factors.append(f"risk_flags:{len(sanitized.risk_flags)}")
        
        if len(sanitized.sanitization_reasons) > 3:
            decision = "sanitize"  # 需要额外审查
        
        entry = AuditEntry(
            entry_id=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{req.request_id[:8]}_sanitize",
            timestamp=datetime.now().isoformat(),
            request_id=req.request_id,
            gateway_action="sanitize",
            routing_decision=decision,
            source_type=req.source_type,
            user_id=req.user_id,
            room_id=req.room_id,
            command=req.command,
            arg_summary={"sanitized": True, "modifications": len(sanitized.modified_fields)},
            decision_factors=factors
        )
        
        self.audit_chain.append(entry)
        return entry
    
    def record_routing(self, request_id: str, decision: RoutingDecision, 
                       downstream: str, factors: List[str]) -> AuditEntry:
        """记录路由决策"""
        # 查找原始请求
        req_entry = next((e for e in self.audit_chain if e.request_id == request_id), None)
        
        entry = AuditEntry(
            entry_id=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request_id[:8]}_route",
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            gateway_action="route",
            routing_decision=decision.value,
            source_type=req_entry.source_type if req_entry else "unknown",
            user_id=req_entry.user_id if req_entry else None,
            room_id=req_entry.room_id if req_entry else None,
            command=req_entry.command if req_entry else "unknown",
            arg_summary={},
            decision_factors=factors,
            downstream_service=downstream
        )
        
        self.audit_chain.append(entry)
        return entry
    
    def record_rejection(self, request_id: str, reason: str) -> AuditEntry:
        """记录拒绝事件"""
        req_entry = next((e for e in self.audit_chain if e.request_id == request_id), None)
        
        entry = AuditEntry(
            entry_id=f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{request_id[:8]}_reject",
            timestamp=datetime.now().isoformat(),
            request_id=request_id,
            gateway_action="reject",
            routing_decision="reject",
            source_type=req_entry.source_type if req_entry else "unknown",
            user_id=req_entry.user_id if req_entry else None,
            room_id=req_entry.room_id if req_entry else None,
            command=req_entry.command if req_entry else "unknown",
            arg_summary={},
            decision_factors=[f"rejection_reason:{reason}"]
        )
        
        self.audit_chain.append(entry)
        return entry
    
    def _sanitize_args_for_audit(self, args: Dict) -> Dict:
        """为审计脱敏参数"""
        sanitized = {}
        
        for key, value in args.items():
            # 对长字段截断
            value_str = str(value)
            if len(value_str) > 100:
                sanitized[key] = value_str[:100] + "..."
            else:
                sanitized[key] = value
        
        return sanitized
    
    def get_audit_chain(self, request_id: str) -> List[AuditEntry]:
        """获取特定请求的审计链"""
        return [e for e in self.audit_chain if e.request_id == request_id]
    
    def export_audit_log(self, filepath: str = None) -> str:
        """导出审计日志"""
        if filepath is None:
            filepath = f"{self.storage_path}/audit_{datetime.now().strftime('%Y%m%d')}.jsonl"
        
        import os
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        with open(filepath, 'w') as f:
            for entry in self.audit_chain:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + '\n')
        
        return filepath


class GatewayOrchestrator:
    """
    网关编排器
    
    组合 Parser + Sanitization + Audit 的完整流程
    """
    
    def __init__(self):
        self.parser = RequestReplayParser()
        self.sanitizer = HeaderSanitizationLayer()
        self.audit = AuditFirstGateway()
    
    def process(self, raw_body: str, source_type: str = "matrix",
                room_id: str = None, user_id: str = None, client_ip: str = None) -> Tuple[RoutingDecision, Optional[SanitizedRequest], str]:
        """
        处理完整网关流程
        
        Returns:
            (decision, sanitized_request, reason)
        """
        # 1. 解析
        parsed = self.parser.parse(raw_body, source_type, room_id, user_id, client_ip)
        self.audit.record_parse(parsed)
        
        # 2. 净化
        sanitized = self.sanitizer.sanitize(parsed)
        self.audit.record_sanitization(sanitized)
        
        # 3. 路由决策
        decision, reason = self._make_routing_decision(sanitized)
        
        if decision == RoutingDecision.REJECT:
            self.audit.record_rejection(parsed.request_id, reason)
        else:
            self.audit.record_routing(
                parsed.request_id, 
                decision,
                downstream="council_core",
                factors=["sanitization_clean" if not sanitized.risk_flags else "risk_flagged"]
            )
        
        return decision, sanitized if decision != RoutingDecision.REJECT else None, reason
    
    def _make_routing_decision(self, sanitized: SanitizedRequest) -> Tuple[RoutingDecision, str]:
        """做出路由决策"""
        
        # 检查风险标志
        if sanitized.risk_flags:
            if len(sanitized.risk_flags) >= 3:
                return RoutingDecision.REJECT, f"Too many risk flags: {sanitized.risk_flags}"
            return RoutingDecision.SANITIZE, f"Risk flags detected: {sanitized.risk_flags}"
        
        # 检查命令有效性
        if sanitized.original_request.command == "unknown":
            return RoutingDecision.REJECT, "Unknown command"
        
        # 检查必要参数
        if sanitized.original_request.command == "status" and 'meeting_id' not in sanitized.clean_args:
            return RoutingDecision.REJECT, "Missing meeting_id for status command"
        
        # 默认通过
        return RoutingDecision.PROCEED, "All checks passed"


# 演示
if __name__ == "__main__":
    gateway = GatewayOrchestrator()
    
    # 测试用例 1: 正常请求
    print("=" * 70)
    print("Test 1: Normal Request")
    print("=" * 70)
    
    raw_request_1 = """
    !council start topic="测试会议" problem="评估某功能" criteria=[标准1,标准2] constraints=[约束1]
    """
    
    decision, sanitized, reason = gateway.process(
        raw_request_1, 
        source_type="matrix",
        room_id="!test:matrix.org",
        user_id="@user:matrix.org"
    )
    
    print(f"Decision: {decision.value}")
    print(f"Reason: {reason}")
    print(f"Command: {sanitized.original_request.command}")
    print(f"Args: {sanitized.clean_args}")
    print(f"Route Signals: {sanitized.original_request.route_signals}")
    
    # 测试用例 2: 包含敏感信息的请求
    print("\n" + "=" * 70)
    print("Test 2: Request with Sensitive Data")
    print("=" * 70)
    
    raw_request_2 = """
    !council start topic="敏感测试" problem="包含 password=secret123 和 api_key=abc123"
    """
    
    decision, sanitized, reason = gateway.process(raw_request_2)
    
    print(f"Decision: {decision.value}")
    print(f"Sanitization Reasons: {sanitized.sanitization_reasons}")
    print(f"Modified Fields: {list(sanitized.modified_fields.keys())}")
    
    # 测试用例 3: 包含注入风险的请求
    print("\n" + "=" * 70)
    print("Test 3: Request with Injection Risk")
    print("=" * 70)
    
    raw_request_3 = """
    !council start topic="<script>alert('xss')</script>" problem="正常内容"
    """
    
    decision, sanitized, reason = gateway.process(raw_request_3)
    
    print(f"Decision: {decision.value}")
    print(f"Risk Flags: {sanitized.risk_flags}")
    print(f"Cleaned Topic: {sanitized.clean_args.get('topic', 'N/A')}")
    
    # 导出审计日志
    print("\n" + "=" * 70)
    print("Audit Log Export")
    print("=" * 70)
    audit_path = gateway.audit.export_audit_log()
    print(f"Exported to: {audit_path}")
    print(f"Total entries: {len(gateway.audit.audit_chain)}")

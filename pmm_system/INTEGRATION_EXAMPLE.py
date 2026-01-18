#!/usr/bin/env python3
"""
Post-Market Monitoring Integration Example
==========================================
演示如何集成 PMM 系统与现有的 health-safety skills

这个文件展示了完整的集成流程，包括：
1. PMM Core Agent 初始化
2. 与 ai-safety-planning 集成
3. 与 ai-ethics-advisor 集成（复用 bias-monitoring.py）
4. 与 incident-responder 集成
5. 完整的监控流程示例
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

# 添加 skills 模块到路径
sys.path.append(str(Path(__file__).parent / "skills/explaining-code/health-safety"))

# 导入现有的 bias monitoring 模块
from skills.explaining_code.health_safety.ai_ethics_advisor.modules.technical_safeguards.bias_monitoring import (
    BiasMonitor,
    compute_fairness_metrics,
    check_four_fifths_rule
)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class AIInteraction:
    """AI 系统交互记录"""
    interaction_id: str
    timestamp: datetime
    user_id: Optional[str]
    prompt: str
    response: str
    response_time: float
    model_version: str
    metadata: Dict
    demographics: Optional[Dict] = None  # 用于偏见监控


@dataclass
class SafetyThreshold:
    """安全阈值配置"""
    metric_name: str
    target: float
    alert_threshold: float
    critical_threshold: float


@dataclass
class MonitoringAlert:
    """监控告警"""
    alert_id: str
    timestamp: datetime
    alert_type: str
    severity: str  # critical, high, medium, low
    metric_name: str
    current_value: float
    threshold: float
    details: Dict


# ============================================================================
# Integration 1: SafetyMetricsProvider - 与 ai-safety-planning 集成
# ============================================================================

class SafetyMetricsProvider:
    """
    从 ai-safety-planning 加载安全指标配置

    基于: skills/health-safety/ai-safety-SKILL.md
    章节: Safety Evaluation Metrics (行 418-428)
    """

    def __init__(self):
        self.thresholds = self._load_default_thresholds()

    def _load_default_thresholds(self) -> Dict[str, SafetyThreshold]:
        """
        加载默认的安全阈值

        这些阈值来自 ai-safety-SKILL.md 的标准定义
        """
        return {
            'refusal_rate': SafetyThreshold(
                metric_name='refusal_rate',
                target=0.99,
                alert_threshold=0.95,
                critical_threshold=0.90
            ),
            'false_positive_rate': SafetyThreshold(
                metric_name='false_positive_rate',
                target=0.05,
                alert_threshold=0.10,
                critical_threshold=0.15
            ),
            'jailbreak_resistance': SafetyThreshold(
                metric_name='jailbreak_resistance',
                target=0.95,
                alert_threshold=0.90,
                critical_threshold=0.85
            ),
            'toxicity_score': SafetyThreshold(
                metric_name='toxicity_score',
                target=0.1,
                alert_threshold=0.2,
                critical_threshold=0.3
            ),
            'bias_score': SafetyThreshold(
                metric_name='bias_score',
                target=0.9,
                alert_threshold=0.8,
                critical_threshold=0.7
            ),
            # MYTASK.md 定义的指标
            'response_accuracy': SafetyThreshold(
                metric_name='response_accuracy',
                target=0.95,
                alert_threshold=0.90,
                critical_threshold=0.85
            ),
            'hallucination_rate': SafetyThreshold(
                metric_name='hallucination_rate',
                target=0.05,
                alert_threshold=0.10,
                critical_threshold=0.15
            ),
            'user_satisfaction': SafetyThreshold(
                metric_name='user_satisfaction',
                target=4.0,
                alert_threshold=3.5,
                critical_threshold=3.0
            ),
        }

    def get_threshold(self, metric_name: str) -> SafetyThreshold:
        """获取指定指标的阈值"""
        return self.thresholds.get(metric_name)

    def check_threshold(self, metric_name: str, value: float) -> Optional[str]:
        """
        检查指标是否违反阈值

        Returns:
            None if within threshold
            'alert' if alert threshold breached
            'critical' if critical threshold breached
        """
        threshold = self.get_threshold(metric_name)
        if not threshold:
            return None

        # 根据指标类型判断（有些指标是越高越好，有些是越低越好）
        higher_is_better = metric_name in [
            'refusal_rate', 'jailbreak_resistance',
            'bias_score', 'response_accuracy', 'user_satisfaction'
        ]

        if higher_is_better:
            if value < threshold.critical_threshold:
                return 'critical'
            elif value < threshold.alert_threshold:
                return 'alert'
        else:
            if value > threshold.critical_threshold:
                return 'critical'
            elif value > threshold.alert_threshold:
                return 'alert'

        return None


# ============================================================================
# Integration 2: EthicsMonitoringBridge - 与 ai-ethics-advisor 集成
# ============================================================================

class EthicsMonitoringBridge:
    """
    与 ai-ethics-advisor 的双向集成

    复用: skills/health-safety/ai-ethics-advisor/modules/technical-safeguards/bias-monitoring.py
    """

    def __init__(self, protected_attributes: List[str] = None):
        """
        初始化伦理监控桥

        Args:
            protected_attributes: 需要监控的受保护属性
        """
        if protected_attributes is None:
            protected_attributes = ['gender', 'race', 'age', 'disability']

        # 复用现有的 BiasMonitor
        self.bias_monitor = BiasMonitor(
            protected_attributes=protected_attributes,
            alert_thresholds={
                'demographic_parity': 0.8,  # 4/5ths rule
                'tpr_disparity': 0.05,
                'fpr_disparity': 0.05
            },
            window_size=1000
        )

        self.alert_history = []

    def log_interaction(self, interaction: AIInteraction):
        """
        记录交互用于偏见监控

        Args:
            interaction: AI 交互记录
        """
        if not interaction.demographics:
            return

        # 记录预测（假设响应不为空视为正面预测）
        prediction = 1 if interaction.response else 0

        self.bias_monitor.log_prediction(
            prediction=prediction,
            ground_truth=None,  # 通常需要后续标注
            attributes=interaction.demographics
        )

    def check_bias_alerts(self) -> List[Dict]:
        """
        检查偏见告警

        Returns:
            当前活跃的偏见告警列表
        """
        alerts = self.bias_monitor.check_alerts()

        # 记录告警历史
        for alert in alerts:
            alert['detected_at'] = datetime.utcnow()
            self.alert_history.append(alert)

        return alerts

    def get_bias_report(self) -> str:
        """
        生成偏见监控报告

        Returns:
            格式化的报告字符串
        """
        return self.bias_monitor.get_summary_report()

    def should_trigger_ethics_assessment(self, alerts: List[Dict]) -> bool:
        """
        判断是否应该触发完整的伦理评估

        基于: ai-ethics-advisor/SKILL.md
        - Tier 1: Rapid Screen (15-30 min) - 用于轻微问题
        - Tier 2: Comprehensive Assessment (2-4 hours) - 用于严重问题

        Args:
            alerts: 当前告警列表

        Returns:
            True if comprehensive assessment needed
        """
        # 如果有任何 demographic_parity 违规，触发评估
        for alert in alerts:
            if alert['type'] == 'demographic_parity':
                return True

        # 如果多个群体同时出现问题，触发评估
        affected_groups = set()
        for alert in alerts:
            if 'group' in alert:
                affected_groups.add(alert['group'])

        return len(affected_groups) >= 2

    async def trigger_ethics_assessment(self, alerts: List[Dict]) -> Dict:
        """
        触发伦理评估

        Args:
            alerts: 触发评估的告警列表

        Returns:
            评估结果
        """
        # 判断使用哪个层级的评估
        if len(alerts) > 3 or any(a.get('severity') == 'critical' for a in alerts):
            assessment_tier = 'tier2_comprehensive'
            print("🔴 Triggering Tier 2 Comprehensive Ethics Assessment")
        else:
            assessment_tier = 'tier1_rapid'
            print("🟡 Triggering Tier 1 Rapid Ethics Screen")

        # 在实际系统中，这里会调用 ai-ethics-advisor 的 API
        # 这里我们返回一个模拟结果
        return {
            'assessment_tier': assessment_tier,
            'triggered_at': datetime.utcnow(),
            'alerts_count': len(alerts),
            'recommendation': 'Review model training data and implement bias mitigation',
            'action_required': True
        }


# ============================================================================
# Integration 3: IncidentTrigger - 与 incident-responder 集成
# ============================================================================

class IncidentTrigger:
    """
    与 incident-responder 集成

    基于: skills/health-safety/skills/incident-responder/SKILL.md
    """

    # 严重级别映射到响应时间
    SEVERITY_MAPPING = {
        'critical': {
            'priority': 'P1',
            'response_time': '< 5 minutes',
            'classification': 'security_breach'
        },
        'high': {
            'priority': 'P2',
            'response_time': '< 1 hour',
            'classification': 'compliance_violation'
        },
        'medium': {
            'priority': 'P3',
            'response_time': '< 24 hours',
            'classification': 'service_outage'
        },
        'low': {
            'priority': 'P4',
            'response_time': '< 1 week',
            'classification': 'data_incident'
        }
    }

    def __init__(self):
        self.incident_counter = 0
        self.active_incidents = []

    def create_incident(self,
                       alert: MonitoringAlert,
                       context: Dict = None) -> str:
        """
        创建事件并触发响应

        基于 incident-responder/SKILL.md 的 First response procedures (行 36-44):
        - Initial assessment
        - Severity determination
        - Team mobilization
        - Containment actions
        - Evidence preservation

        Args:
            alert: 监控告警
            context: 额外的上下文信息

        Returns:
            incident_id
        """
        self.incident_counter += 1
        incident_id = f"INC-{datetime.utcnow().strftime('%Y%m%d')}-{self.incident_counter:04d}"

        severity_config = self.SEVERITY_MAPPING.get(alert.severity, self.SEVERITY_MAPPING['medium'])

        incident = {
            'incident_id': incident_id,
            'created_at': datetime.utcnow(),
            'alert': alert,
            'priority': severity_config['priority'],
            'classification': severity_config['classification'],
            'response_time_sla': severity_config['response_time'],
            'status': 'open',
            'context': context or {},
            'actions_taken': []
        }

        self.active_incidents.append(incident)

        print(f"\n{'='*60}")
        print(f"🚨 INCIDENT CREATED: {incident_id}")
        print(f"{'='*60}")
        print(f"Priority: {severity_config['priority']}")
        print(f"Classification: {severity_config['classification']}")
        print(f"Response Time SLA: {severity_config['response_time']}")
        print(f"Alert Type: {alert.alert_type}")
        print(f"Severity: {alert.severity}")
        print(f"Metric: {alert.metric_name} = {alert.current_value:.3f}")
        print(f"Threshold: {alert.threshold:.3f}")
        print(f"{'='*60}\n")

        # 在实际系统中，这里会：
        # 1. 通知响应团队
        # 2. 创建 PagerDuty/Opsgenie 告警
        # 3. 发送 Slack 通知
        # 4. 启动响应流程

        return incident_id

    def get_active_incidents(self) -> List[Dict]:
        """获取活跃事件列表"""
        return [inc for inc in self.active_incidents if inc['status'] == 'open']

    def close_incident(self, incident_id: str, resolution: str):
        """关闭事件"""
        for incident in self.active_incidents:
            if incident['incident_id'] == incident_id:
                incident['status'] = 'closed'
                incident['closed_at'] = datetime.utcnow()
                incident['resolution'] = resolution
                print(f"✓ Incident {incident_id} closed: {resolution}")
                break


# ============================================================================
# PMM Core Agent - 主协调器
# ============================================================================

class PMMCoreAgent:
    """
    Post-Market Monitoring 核心代理

    协调所有监控功能和集成
    """

    def __init__(self):
        self.safety_provider = SafetyMetricsProvider()
        self.ethics_bridge = EthicsMonitoringBridge()
        self.incident_trigger = IncidentTrigger()

        # 监控数据
        self.interactions_log = []
        self.metrics_buffer = {
            'response_accuracy': [],
            'hallucination_rate': [],
            'user_satisfaction': [],
        }

    async def process_interaction(self, interaction: AIInteraction):
        """
        处理单个 AI 交互

        流程:
        1. 记录交互
        2. 提取指标
        3. 检查阈值
        4. 如果有人口统计信息，记录到偏见监控
        5. 触发告警（如果需要）
        """
        print(f"\n📝 Processing interaction: {interaction.interaction_id}")

        # 1. 记录交互
        self.interactions_log.append(interaction)

        # 2. 提取指标（这里是模拟计算）
        metrics = await self._extract_metrics(interaction)

        # 3. 更新指标缓冲区
        for metric_name, value in metrics.items():
            if metric_name in self.metrics_buffer:
                self.metrics_buffer[metric_name].append(value)

        # 4. 检查阈值
        alerts = []
        for metric_name, value in metrics.items():
            violation = self.safety_provider.check_threshold(metric_name, value)
            if violation:
                alert = MonitoringAlert(
                    alert_id=f"ALT-{datetime.utcnow().timestamp()}",
                    timestamp=datetime.utcnow(),
                    alert_type=f"{metric_name}_threshold_violation",
                    severity=violation,
                    metric_name=metric_name,
                    current_value=value,
                    threshold=self.safety_provider.get_threshold(metric_name).alert_threshold,
                    details={'interaction_id': interaction.interaction_id}
                )
                alerts.append(alert)
                print(f"⚠️  Alert: {metric_name} = {value:.3f} (threshold: {alert.threshold:.3f})")

        # 5. 偏见监控（如果有人口统计信息）
        if interaction.demographics:
            self.ethics_bridge.log_interaction(interaction)
            bias_alerts = self.ethics_bridge.check_bias_alerts()

            if bias_alerts:
                print(f"⚠️  Bias alerts detected: {len(bias_alerts)}")

                # 判断是否需要触发伦理评估
                if self.ethics_bridge.should_trigger_ethics_assessment(bias_alerts):
                    assessment = await self.ethics_bridge.trigger_ethics_assessment(bias_alerts)
                    print(f"📊 Ethics assessment completed: {assessment['recommendation']}")

        # 6. 触发事件（如果是严重告警）
        for alert in alerts:
            if alert.severity == 'critical':
                incident_id = self.incident_trigger.create_incident(
                    alert=alert,
                    context={
                        'user_id': interaction.user_id,
                        'model_version': interaction.model_version,
                        'recent_interactions': len(self.interactions_log)
                    }
                )

    async def _extract_metrics(self, interaction: AIInteraction) -> Dict[str, float]:
        """
        从交互中提取指标

        在实际系统中，这会包括：
        - 响应准确性检查
        - 幻觉检测
        - 引用验证
        - 情感分析
        等等

        这里我们返回模拟值
        """
        # 模拟指标计算
        import random

        return {
            'response_accuracy': random.uniform(0.85, 0.98),
            'hallucination_rate': random.uniform(0.02, 0.12),
            'user_satisfaction': random.uniform(3.0, 4.8),
        }

    def generate_summary_report(self) -> str:
        """生成监控摘要报告"""
        report = []
        report.append("\n" + "="*60)
        report.append("POST-MARKET MONITORING SUMMARY REPORT")
        report.append("="*60)
        report.append(f"Report Generated: {datetime.utcnow().isoformat()}")
        report.append(f"Total Interactions: {len(self.interactions_log)}")
        report.append("")

        # 指标摘要
        report.append("METRICS SUMMARY:")
        report.append("-"*60)
        for metric_name, values in self.metrics_buffer.items():
            if values:
                avg = sum(values) / len(values)
                threshold = self.safety_provider.get_threshold(metric_name)
                status = "✓" if self.safety_provider.check_threshold(metric_name, avg) is None else "✗"
                report.append(f"{status} {metric_name}: {avg:.3f} (target: {threshold.target:.3f})")
        report.append("")

        # 偏见报告
        report.append("BIAS MONITORING:")
        report.append("-"*60)
        bias_report = self.ethics_bridge.get_bias_report()
        report.append(bias_report)
        report.append("")

        # 活跃事件
        active_incidents = self.incident_trigger.get_active_incidents()
        report.append(f"ACTIVE INCIDENTS: {len(active_incidents)}")
        report.append("-"*60)
        for incident in active_incidents:
            report.append(f"  - {incident['incident_id']}: {incident['alert'].alert_type}")

        report.append("="*60)

        return "\n".join(report)


# ============================================================================
# 演示主函数
# ============================================================================

async def demo_pmm_system():
    """演示 PMM 系统的完整流程"""

    print("\n" + "="*70)
    print("POST-MARKET MONITORING SYSTEM - INTEGRATION DEMO")
    print("="*70)
    print("\nThis demo shows how PMM integrates with:")
    print("1. ai-safety-planning (metrics and thresholds)")
    print("2. ai-ethics-advisor (bias monitoring)")
    print("3. incident-responder (incident management)")
    print("\n" + "="*70 + "\n")

    # 初始化 PMM Agent
    pmm = PMMCoreAgent()

    # 模拟一系列 AI 交互
    demographics_options = [
        {'gender': 'male', 'age_group': '25-35', 'ethnicity': 'caucasian'},
        {'gender': 'female', 'age_group': '35-45', 'ethnicity': 'asian'},
        {'gender': 'male', 'age_group': '45-55', 'ethnicity': 'african_american'},
        {'gender': 'female', 'age_group': '25-35', 'ethnicity': 'hispanic'},
        None  # 有些交互可能没有人口统计信息
    ]

    print("Simulating 20 AI interactions...\n")

    for i in range(20):
        interaction = AIInteraction(
            interaction_id=f"int_{i+1:03d}",
            timestamp=datetime.utcnow(),
            user_id=f"user_{i % 5 + 1}",
            prompt=f"Sample query {i+1}",
            response=f"Sample response {i+1}",
            response_time=0.5 + (i % 5) * 0.1,
            model_version="gpt-4",
            metadata={'temperature': 0.7},
            demographics=demographics_options[i % len(demographics_options)]
        )

        await pmm.process_interaction(interaction)

        # 每 5 个交互后暂停一下
        if (i + 1) % 5 == 0:
            await asyncio.sleep(0.5)
            print(f"\n{'─'*60}")
            print(f"Processed {i+1}/20 interactions")
            print(f"{'─'*60}\n")

    # 生成最终报告
    print("\n" + "="*70)
    print("GENERATING FINAL REPORT...")
    print("="*70)

    report = pmm.generate_summary_report()
    print(report)

    # 显示活跃事件详情
    active_incidents = pmm.incident_trigger.get_active_incidents()
    if active_incidents:
        print("\n" + "="*70)
        print("ACTIVE INCIDENTS DETAILS")
        print("="*70)
        for incident in active_incidents:
            print(f"\nIncident ID: {incident['incident_id']}")
            print(f"Priority: {incident['priority']}")
            print(f"Created: {incident['created_at'].isoformat()}")
            print(f"Alert Type: {incident['alert'].alert_type}")
            print(f"Severity: {incident['alert'].severity}")
            print(f"Response SLA: {incident['response_time_sla']}")


# ============================================================================
# 运行演示
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════╗
║     POST-MARKET MONITORING INTEGRATION EXAMPLE                   ║
║     EU AI Act Article 72 Compliance                               ║
╚══════════════════════════════════════════════════════════════════╝
    """)

    # 运行异步演示
    asyncio.run(demo_pmm_system())

    print("\n" + "="*70)
    print("DEMO COMPLETED")
    print("="*70)
    print("\nNext Steps:")
    print("1. Review POST_MARKET_MONITORING_DESIGN.md for full architecture")
    print("2. Read QUICK_START_GUIDE.md for deployment instructions")
    print("3. Explore the API documentation at http://localhost:8000/docs")
    print("\n" + "="*70 + "\n")

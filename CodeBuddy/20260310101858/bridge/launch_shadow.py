#!/usr/bin/env python3
"""
Shadow Deployment Launcher
影子部署启动器

正式入口 - 启动 30 天真实环境观察期
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858')
sys.path.insert(0, '/home/admin/CodeBuddy/20260310101858/bridge')

from bridge.shadow_deployment import ShadowDeploymentManager, ShadowStatus


def print_banner():
    """打印启动横幅"""
    print("="*70)
    print("🚀 TAICHU SHADOW DEPLOYMENT LAUNCHER")
    print("   华夏文明谱影子部署启动器")
    print("="*70)
    print()


def print_three_disciplines():
    """打印三条纪律"""
    print("⚠️  SHADOW 期间三条纪律 (强制执行):")
    print("-" * 50)
    print("  1️⃣  新系统只记录，不拦截")
    print("      影子系统的建议仅用于观察，不影响实际决策")
    print()
    print("  2️⃣  旧系统仍是唯一执行链")
    print("      所有执行仍由旧系统控制，影子系统无执行权")
    print()
    print("  3️⃣  所有分歧都落日志，不人工挑样本")
    print("      100%记录，无选择性过滤，无人工干预")
    print("-" * 50)
    print()


def print_five_metrics():
    """打印5个观察指标"""
    print("📊 30天观察指标:")
    print("-" * 50)
    print("  1. False-Block Rate")
    print("     旧系统批准但影子系统拦截的比例")
    print("     门槛: ≤ 15%")
    print()
    print("  2. Review Disagreement Rate")
    print("     协商评分与审验评分差异 > 20 的比例")
    print("     观察趋势是否稳定下降")
    print()
    print("  3. Extra Round Overhead")
    print("     影子系统建议的额外轮次平均值")
    print("     门槛: ≤ 0.4")
    print()
    print("  4. Human Override Rate")
    print("     人工覆盖影子建议的比例")
    print("     观察是否有集中抱怨")
    print()
    print("  5. Accepted-Risk Miss Rate ⭐ NEW")
    print("     旧放行+新高置信拦截案例中，后续验证确实有风险的比例")
    print("     区分'误拦'与'提前发现风险'")
    print("-" * 50)
    print()


def print_decision_criteria():
    """打印30天后判定标准"""
    print("📋 30天后判定标准:")
    print("-" * 50)
    print("  🟢 PROMOTE (晋升为主系统)")
    print("     - False-Block ≤ 15%")
    print("     - Extra Round ≤ 40%")
    print("     - Review Disagreement 稳定下降")
    print("     - Human Override 低且无集中抱怨")
    print()
    print("  🟡 EXTEND (延长观察)")
    print("     - 指标接近门槛")
    print("     - 趋势改善但样本不够稳")
    print()
    print("  🔴 RETUNE (重新调参)")
    print("     - False-Block 持续偏高")
    print("     - 分歧率不降")
    print("     - 人工覆盖频繁")
    print("-" * 50)
    print()


def confirm_launch():
    """确认启动"""
    print("⚡ 准备启动影子部署...")
    print()
    print("配置:")
    print(f"  - Shadow ID: SHADOW-{datetime.now().strftime('%Y%m%d')}-PROD")
    print(f"  - 观察周期: 30天")
    print(f"  - 目标会议: 50个")
    print(f"  - 存储路径: data/shadow/")
    print()
    
    response = input("确认启动影子部署? [yes/no]: ")
    return response.lower() in ["yes", "y"]


def launch():
    """启动影子部署"""
    print_banner()
    print_three_disciplines()
    print_five_metrics()
    print_decision_criteria()
    
    if not confirm_launch():
        print("\n❌ 已取消启动")
        return
    
    print("\n" + "="*70)
    print("🚀 正在启动影子部署...")
    print("="*70)
    
    # 创建管理器
    shadow_id = f"SHADOW-{datetime.now().strftime('%Y%m%d')}-PROD"
    manager = ShadowDeploymentManager(
        shadow_id=shadow_id,
        config=ShadowDeploymentManager.DEFAULT_CONFIG
    )
    
    print(f"\n✅ 影子部署已启动: {shadow_id}")
    print()
    print("下一步:")
    print("  1. 将影子系统集成到 Matrix Bridge 流程")
    print("  2. 确保每个会议调用 manager.process_meeting()")
    print("  3. 30天后运行评估脚本")
    print()
    print("监控命令:")
    print(f"  python3 -c \"from bridge.shadow_deployment import ShadowDeploymentManager; "
          f"m = ShadowDeploymentManager(shadow_id='{shadow_id}'); m.print_status()\"")
    print()
    print("="*70)


if __name__ == "__main__":
    launch()

#!/usr/bin/env python3
"""Hermes Script — 检查超时未回复的线索。

用法:
    hermes cron create "0 9 * * *" \
      "检查超过3天未回复的线索..." \
      --script server/szyg/pipelines/check_stale_leads.py

此脚本在 Hermes Agent 运行前执行，stdout 内容注入为 Agent 上下文。
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import datetime, timedelta
from szyg.lead_store import get_lead_store
from szyg.models.lead import ConversionStage, IntentLevel

store = get_lead_store()
all_leads = store.list_leads(limit=200)

# 筛选超过 3 天未更新且不是「已成交」或「已流失」的线索
cutoff = datetime.utcnow() - timedelta(days=3)
stale = []
for lead in all_leads:
    if lead.conversion_stage in (ConversionStage.WON, ConversionStage.LOST):
        continue
    if lead.updated_at < cutoff:
        stale.append(lead)

if not stale:
    print("NO_STALE_LEADS: 所有线索都在 3 天内有更新。")
    sys.exit(0)

print(f"发现 {len(stale)} 个超过 3 天未回复的线索：\n")
for lead in stale[:20]:  # 限制上下文长度
    days = (datetime.utcnow() - lead.updated_at).days
    print(f"- ID: {lead.id} | {lead.name or lead.platform_account} | "
          f"{lead.intent_level.value} | {lead.conversion_stage.value} | "
          f"静默 {days} 天 | 平台: {lead.platform.value}")
    if lead.source_content:
        print(f"  触发内容: {lead.source_content[:100]}")
    print()

print("\n请为以上每条线索生成一条个性化跟进话术，语气自然，针对不同意向等级调整策略。")

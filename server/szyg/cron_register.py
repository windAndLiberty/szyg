"""
Hermes Cron 注册脚本 — 智能评论引擎定时任务

用法:
    python -m szyg.cron_register          # 注册默认 cron job（每5分钟）
    python -m szyg.cron_register --remove # 移除已注册的 job

注册后，Hermes 的 cron scheduler 每 5 分钟自动调用引擎 tick()，
驱动状态机自动流转（monitoring → analyzing → generating → queued → executed）。
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from hermes_constants import get_hermes_home

CRON_JOB_NAME = "szyg-smart-comment-engine"
CRON_SCHEDULE = "*/5 * * * *"
CRON_SCRIPT = "python -m szyg.comment_engine tick"


def get_cron_db_path():
    return Path(get_hermes_home()) / "cron" / "jobs.json"


def load_jobs():
    db = get_cron_db_path()
    if not db.exists():
        return []
    try:
        return json.loads(db.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def save_jobs(jobs):
    db = get_cron_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")


def register():
    jobs = load_jobs()

    # 检查是否已存在
    for job in jobs:
        if job.get("id") == CRON_JOB_NAME or job.get("name") == CRON_JOB_NAME:
            print(f"[Cron] Job '{CRON_JOB_NAME}' already registered.")
            print(f"       Schedule: {job.get('schedule', {}).get('value', '?')}")
            return

    jobs.append({
        "id": CRON_JOB_NAME,
        "name": CRON_JOB_NAME,
        "prompt": "szyg 智能评论引擎 tick — 驱动所有活跃评论任务的状态流转",
        "no_agent": True,
        "script": CRON_SCRIPT,
        "schedule": {"type": "cron", "value": CRON_SCHEDULE},
        "enabled": True,
        "created_at": str(Path(__file__).stat().st_mtime),
    })
    save_jobs(jobs)
    print(f"[Cron] Registered '{CRON_JOB_NAME}'")
    print(f"       Schedule: {CRON_SCHEDULE} (every 5 minutes)")
    print(f"       Script:   {CRON_SCRIPT}")
    print(f"       Mode:     no_agent (纯脚本执行，无LLM开销)")
    print()
    print("确保 Hermes gateway 正在运行以执行 cron jobs:")
    print("    hermes gateway")


def remove():
    jobs = load_jobs()
    original_len = len(jobs)
    jobs = [j for j in jobs if j.get("id") != CRON_JOB_NAME and j.get("name") != CRON_JOB_NAME]
    if len(jobs) == original_len:
        print(f"[Cron] Job '{CRON_JOB_NAME}' not found.")
        return
    save_jobs(jobs)
    print(f"[Cron] Removed '{CRON_JOB_NAME}'.")


def list_jobs():
    jobs = load_jobs()
    szyg_jobs = [j for j in jobs if "szyg" in j.get("name", "")]
    if not szyg_jobs:
        print("[Cron] No szyg jobs found.")
        return
    print(f"[Cron] Found {len(szyg_jobs)} szyg job(s):")
    for job in szyg_jobs:
        sched = job.get("schedule", {}).get("value", "?")
        enabled = "✓" if job.get("enabled") else "✗"
        print(f"  [{enabled}] {job.get('name')} — {sched}")


def main():
    parser = argparse.ArgumentParser(description="szyg Hermes Cron 管理")
    parser.add_argument("--register", action="store_true", help="注册智能评论引擎 cron job")
    parser.add_argument("--remove", action="store_true", help="移除 cron job")
    parser.add_argument("--list", action="store_true", help="列出 szyg 相关 cron jobs")
    args = parser.parse_args()

    if args.remove:
        remove()
    elif args.list:
        list_jobs()
    else:
        register()


if __name__ == "__main__":
    main()

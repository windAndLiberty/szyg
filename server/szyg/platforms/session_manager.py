"""
Session Manager — 平台登录态持久化管理

对标数创引擎:
  - data/state.json → Playwright storage_state 格式
  - core/douyin.pyd → storage_state 参数
  - 各平台 adapter 的 run_*() 函数中的 Token 概念

功能:
  1. 保存/加载 Playwright storage_state (cookies + localStorage)
  2. 验证登录态是否过期
  3. 管理多个平台的会话文件
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from szyg.data_path import DATA_DIR
from szyg.publisher import Platform

logger = logging.getLogger(__name__)

# 会话存储目录
SESSIONS_DIR = DATA_DIR / "sessions"


class SessionManager:
    """
    管理各平台的持久化登录态。

    每个平台一个 storage_state_{platform}.json 文件，
    格式兼容 Playwright 的 browser_context.storage_state()。

    Usage:
        mgr = SessionManager()
        state = mgr.load(Platform.DOUYIN)
        if state and mgr.is_valid(Platform.DOUYIN):
            context = await browser.new_context(storage_state=state)
    """

    def __init__(self, storage_dir: Path | None = None):
        self._dir = storage_dir or SESSIONS_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, platform: Platform) -> Path:
        return self._dir / f"storage_state_{platform.value}.json"

    # ── 保存 ────────────────────────────────────────────

    async def save(self, platform: Platform, context) -> None:
        """
        保存浏览器 context 的登录态。

        Args:
            platform: 平台标识
            context: Playwright BrowserContext
        """
        state = await context.storage_state()
        state["_saved_at"] = datetime.now().isoformat()
        path = self._path(platform)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"[{platform.value}] 登录态已保存 ({len(state.get('cookies',[]))} cookies)")

    def save_raw(self, platform: Platform, state: dict) -> None:
        """保存原始 storage_state dict (不依赖 Playwright context)"""
        # 添加保存时间戳
        state["_saved_at"] = datetime.now().isoformat()
        path = self._path(platform)
        path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"[{platform.value}] 登录态已保存 (raw)")

    # ── 加载 ────────────────────────────────────────────

    def load(self, platform: Platform) -> dict | None:
        """
        加载保存的登录态。

        Returns:
            Playwright-compatible storage_state dict, 或 None
        """
        path = self._path(platform)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"[{platform.value}] 登录态文件损坏: {e}")
            return None

    # ── 验证 ────────────────────────────────────────────

    def is_valid(self, platform: Platform, grace_hours: int = 24) -> bool:
        """
        检查登录态是否可能仍有效。

        判断依据:
          1. 文件存在
          2. 至少有一个 cookie 未过期 (留 grace_hours 容差)
          3. 文件保存时间在 30 天内

        Args:
            platform: 平台标识
            grace_hours: cookie 过期容差 (小时)
        """
        state = self.load(platform)
        if not state:
            return False

        cookies = state.get("cookies", [])
        if not cookies:
            return False

        # 检查是否有未过期的 cookie
        now_ms = datetime.now(timezone.utc).timestamp()
        grace_ms = grace_hours * 3600

        has_valid = False
        for c in cookies:
            expires = c.get("expires", 0)
            if expires < 0:  # Session cookie — 视为有效
                has_valid = True
                break
            if expires > (now_ms - grace_ms):
                has_valid = True
                break

        if not has_valid:
            return False

        # 检查保存时间
        saved_at = state.get("_saved_at", "")
        if saved_at:
            try:
                saved_dt = datetime.fromisoformat(saved_at)
                age_days = (datetime.now() - saved_dt).days
                if age_days > 30:
                    logger.info(f"[{platform.value}] 登录态已保存 {age_days} 天，可能已过期")
                    return False
            except ValueError:
                pass

        return True

    def get_cookie_expiry(self, platform: Platform) -> str | None:
        """
        获取最早过期的关键 cookie 时间。

        Returns:
            ISO datetime string, 或 None
        """
        state = self.load(platform)
        if not state:
            return None

        key_cookies = {"sessionid", "sid_tt", "web_session", "token", "JSESSIONID"}
        min_expiry = None

        for c in state.get("cookies", []):
            if c.get("name", "").lower() in key_cookies or "session" in c.get("name", "").lower():
                expires = c.get("expires", 0)
                if expires > 0:
                    if min_expiry is None or expires < min_expiry:
                        min_expiry = expires

        if min_expiry:
            from datetime import timezone as tz
            return datetime.fromtimestamp(min_expiry, tz=tz.utc).isoformat()
        return None

    # ── 清除 ────────────────────────────────────────────

    def invalidate(self, platform: Platform) -> None:
        """删除平台的登录态文件"""
        path = self._path(platform)
        if path.exists():
            path.unlink()
            logger.info(f"[{platform.value}] 登录态已清除")

    def invalidate_all(self) -> None:
        """清除所有平台的登录态"""
        for path in self._dir.glob("storage_state_*.json"):
            path.unlink()
        logger.info("所有平台登录态已清除")

    # ── 状态查询 ────────────────────────────────────────

    def get_info(self, platform: Platform) -> dict:
        """获取平台登录态摘要信息"""
        state = self.load(platform)
        if not state:
            return {"has_session": False, "cookie_count": 0, "valid": False}

        return {
            "has_session": True,
            "cookie_count": len(state.get("cookies", [])),
            "valid": self.is_valid(platform),
            "saved_at": state.get("_saved_at", ""),
            "cookie_expiry": self.get_cookie_expiry(platform),
        }

    def list_all(self) -> dict[str, dict]:
        """列出所有平台的登录态信息"""
        result = {}
        for path in sorted(self._dir.glob("storage_state_*.json")):
            # 从文件名提取平台名: storage_state_douyin.json → douyin
            stem = path.stem  # storage_state_douyin
            platform_name = stem.replace("storage_state_", "")

            try:
                platform = Platform(platform_name)
                result[platform_name] = self.get_info(platform)
            except ValueError:
                continue
        return result

    # ── 账号元数据 ─────────────────────────────────────────

    def _meta_path(self, platform: Platform) -> Path:
        return self._dir / f"account_meta_{platform.value}.json"

    def save_account_meta(self, platform: Platform, meta: dict) -> None:
        """保存账号元数据（昵称、粉丝数等）"""
        meta["_updated_at"] = datetime.now().isoformat()
        path = self._meta_path(platform)
        path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.debug(f"[{platform.value}] 账号元数据已保存: {meta.get('nickname', '')}")

    def get_account_meta(self, platform: Platform) -> dict:
        """获取账号元数据"""
        path = self._meta_path(platform)
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            return {}

    def delete_account_meta(self, platform: Platform) -> None:
        """删除账号元数据"""
        path = self._meta_path(platform)
        if path.exists():
            path.unlink()
            logger.debug(f"[{platform.value}] 账号元数据已删除")


# ── 全局单例 ────────────────────────────────────────────────

_session_manager: SessionManager | None = None


def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

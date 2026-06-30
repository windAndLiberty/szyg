"""
「域灵」数字员工系统 - Main 模块测试
"""

from fastapi import FastAPI


def test_get_app_returns_fastapi():
    """get_app() 应返回 FastAPI 实例。"""
    from szyg.main import get_app
    app = get_app()
    assert isinstance(app, FastAPI)


def test_get_app_is_singleton():
    """get_app() 应返回同一实例。"""
    from szyg.main import get_app
    app1 = get_app()
    app2 = get_app()
    assert app1 is app2

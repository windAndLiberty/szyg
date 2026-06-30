#!/usr/bin/env python3
"""MCP Server: Acquisition — 平台采集工具 (搜索/评论/私信)

集成开源项目提供统一的跨平台采集能力:
  - B站: bilibili-api-python (API方式)
  - 抖音/小红书/快手: Playwright 浏览器自动化

提供 6 个 MCP 工具，让 Hermes Agent 可以执行搜索、评论获取、评论发送、私信等操作。
"""
import sys, os, asyncio, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from szyg.mcp_server import MCPServer

server = MCPServer(
    "szyg-acquisition",
    "Platform acquisition tools: search, comments, DMs across Douyin/XHS/Bilibili/Kuaishou"
)


@server.tool("acq_platforms", "列出所有支持的采集平台及其状态")
def acq_platforms():
    """返回每个平台的 id、type、ready 状态"""
    from szyg.integrations.acquisition_adapters import list_acquisition_platforms
    return {"platforms": list_acquisition_platforms()}


@server.tool("acq_search", "在指定平台搜索视频")
def acq_search(platform: str, keyword: str, limit: int = 20):
    """搜索指定平台的视频内容，返回统一格式的搜索结果列表。

    Args:
        platform: 平台名称 (bilibili/douyin/xhs/kuaishou)
        keyword: 搜索关键词
        limit: 返回结果数量上限 (默认20)
    """
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    try:
        adapter = get_acquisition_adapter(platform)

        async def _search():
            results = await adapter.search(keyword, limit=limit)
            return {"platform": platform, "keyword": keyword, "total": len(results), "videos": results}

        return asyncio.run(_search())
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"搜索失败: {e}"}


@server.tool("acq_get_comments", "获取指定视频的评论列表")
def acq_get_comments(platform: str, video_url: str, limit: int = 30):
    """获取指定平台上某个视频/笔记的评论列表。

    Args:
        platform: 平台名称 (bilibili/douyin/xhs/kuaishou)
        video_url: 视频/笔记的完整URL
        limit: 返回评论数量上限 (默认30)
    """
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    try:
        adapter = get_acquisition_adapter(platform)

        async def _get():
            comments = await adapter.get_comments(video_url, limit=limit)
            return {"platform": platform, "video_url": video_url, "total": len(comments), "comments": comments}

        return asyncio.run(_get())
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"获取评论失败: {e}"}


@server.tool("acq_send_comment", "在指定视频下发送评论")
def acq_send_comment(platform: str, video_url: str, comment_text: str):
    """在指定平台的视频/笔记下发表评论。需要该平台已登录。

    Args:
        platform: 平台名称 (bilibili/douyin/xhs/kuaishou)
        video_url: 视频/笔记的完整URL
        comment_text: 评论内容
    """
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    try:
        adapter = get_acquisition_adapter(platform)

        async def _send():
            result = await adapter.send_comment(video_url, comment_text)
            return result

        return asyncio.run(_send())
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"发送评论失败: {e}"}


@server.tool("acq_batch_send_comments", "批量发送评论到指定平台")
def acq_batch_send_comments(platform: str, comments_json: str):
    """批量在多个视频下发送评论。每个评论项包含 video_url 和 comment_text。

    Args:
        platform: 平台名称 (bilibili/douyin/xhs/kuaishou)
        comments_json: JSON数组，每项包含 {video_url, comment_text}
    """
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    try:
        items = json.loads(comments_json)
        if not isinstance(items, list):
            return {"error": "comments_json 必须是JSON数组"}
        adapter = get_acquisition_adapter(platform)

        async def _batch():
            results = []
            for item in items:
                video_url = item.get("video_url", "")
                comment_text = item.get("comment_text", item.get("text", ""))
                if not video_url or not comment_text:
                    results.append({"video_url": video_url, "success": False, "error": "缺少 video_url 或 comment_text"})
                    continue
                result = await adapter.send_comment(video_url, comment_text)
                result["video_url"] = video_url
                results.append(result)
                await asyncio.sleep(2)
            return {"platform": platform, "total": len(results), "results": results}

        return asyncio.run(_batch())
    except ValueError as e:
        return {"error": str(e)}
    except json.JSONDecodeError as e:
        return {"error": f"JSON解析失败: {e}"}
    except Exception as e:
        return {"error": f"批量发送失败: {e}"}


@server.tool("acq_send_dm", "发送私信给指定用户")
def acq_send_dm(platform: str, user_id: str, text: str):
    """向指定平台的用户发送私信。目前仅支持B站。

    Args:
        platform: 平台名称 (bilibili)
        user_id: 目标用户ID
        text: 私信内容
    """
    from szyg.integrations.acquisition_adapters import get_acquisition_adapter

    try:
        adapter = get_acquisition_adapter(platform)

        async def _send():
            result = await adapter.send_dm(user_id, text)
            return result

        return asyncio.run(_send())
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        return {"error": f"发送私信失败: {e}"}


if __name__ == "__main__":
    server.run()

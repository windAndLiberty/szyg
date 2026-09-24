"""
Normalize Utils — 统一数据格式化工具

提供各平台搜索结果和评论的统一格式化函数，
避免模块间循环依赖。
"""


def _normalize_search_result(item: dict, platform: str) -> dict:
    """将各平台搜索结果统一为标准格式"""
    return {
        "video_id": str(item.get("video_id", item.get("id", item.get("bvid", "")))),
        "platform": platform,
        "title": item.get("title", item.get("desc", ""))[:200],
        "description": item.get("description", item.get("desc", ""))[:500],
        "author": item.get("author", item.get("name", item.get("nickname", ""))),
        "author_followers": item.get("author_followers", item.get("followers", 0)),
        "url": item.get("url", item.get("link", "")),
        "cover": item.get("cover", item.get("pic", item.get("cover_url", ""))),
        "plays": item.get("plays", item.get("play", item.get("view_count", 0))),
        "likes": item.get("likes", item.get("like", item.get("digg_count", 0))),
        "comments_count": item.get("comments_count", item.get("comment", item.get("comment_count", 0))),
        "shares": item.get("shares", item.get("share", item.get("share_count", 0))),
        "published_at": item.get("published_at", item.get("pubdate", item.get("create_time", ""))),
    }


def _normalize_comment(item: dict, platform: str) -> dict:
    """将各平台评论统一为标准格式"""
    return {
        "comment_id": str(item.get("comment_id", item.get("rpid", item.get("cid", "")))),
        "platform": platform,
        "author": item.get("author", item.get("name", item.get("nickname", item.get("member", {}).get("uname", "")))),
        "author_id": str(item.get("author_id", item.get("mid", item.get("uid", "")))),
        "text": item.get("text", item.get("content", item.get("message", ""))),
        "likes": item.get("likes", item.get("like", item.get("digg_count", 0))),
        "reply_count": item.get("reply_count", item.get("replies", item.get("sub_comment_count", 0))),
        "replies": item.get("replies", item.get("rcount", 0)),
        "ip_location": item.get("ip_location", ""),
        "created_at": item.get("created_at", item.get("ctime", item.get("create_time", ""))),
        "root_comment_id": str(item.get("root_comment_id", item.get("root", item.get("root_id", ""))) or ""),
        "parent_comment_id": str(item.get("parent_comment_id", item.get("parent", item.get("parent_id", ""))) or ""),
    }

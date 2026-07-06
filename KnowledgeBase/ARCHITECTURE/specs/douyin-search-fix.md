# 🔧 抖音搜索适配器修复规范

> 本文件记录抖音搜索功能的 bug 根因与修复方案，供 Elite_Coder 执行。
> 涉及源码：`server/szyg/integrations/acquisition_adapters.py` → `_search_douyin()`

---

## 1. Bug 描述

- **现象**：超级员工调用抖音搜索时，浏览器成功打开抖音搜索页并展示了结果，但后端返回 `total: 0, videos: []`。
- **根因**：`_search_douyin()` 使用 CSS 选择器 `[data-e2e="search-video-item"]` 提取视频卡片，抖音页面 DOM 结构更新后该属性已不存在，导致匹配 0 个元素。

## 2. 修复方案：双层策略

### 策略 1（主）：网络响应拦截

通过 Playwright 的 `page.on("response")` 监听抖音页面的 XHR 响应，直接从 JSON 中提取结构化数据。

**匹配的 API 路径**：
- `/aweme/v1/web/general/search/`
- `/aweme/v1/web/search/item/`

**响应 JSON 结构**：
```json
{
  "data": [
    {
      "aweme_info": {
        "aweme_id": "7xxx",
        "desc": "视频描述文本",
        "author": {
          "nickname": "作者昵称",
          "follower_count": 12345
        },
        "statistics": {
          "play_count": 10000,
          "digg_count": 500,
          "comment_count": 30,
          "share_count": 10
        },
        "video": {
          "cover": { "url_list": ["https://..."] },
          "play_addr": { "url_list": ["https://..."] }
        },
        "create_time": 1719000000
      }
    }
  ]
}
```

**提取字段映射**：

| API 字段 | 统一字段 | 说明 |
|----------|----------|------|
| `aweme_id` | `video_id` | 视频 ID |
| `desc` | `title` / `description` | 视频描述（截断 200/500） |
| `author.nickname` | `author` | 作者昵称 |
| `author.follower_count` | `author_followers` | 粉丝数 |
| `statistics.play_count` | `plays` | 播放量 |
| `statistics.digg_count` | `likes` | 点赞数 |
| `statistics.comment_count` | `comments_count` | 评论数 |
| `statistics.share_count` | `shares` | 分享数 |
| `video.cover.url_list[0]` | `cover` | 封面图 URL |
| `create_time` | `published_at` | 发布时间戳 |
| — | `url` | `https://www.douyin.com/video/{aweme_id}` |

**实现要点**：
- `page.on("response", handler)` 在 `page.goto()` 之前注册
- `page.goto()` 后 `wait_for_timeout(4000)` 等待 API 响应
- handler 中 `await response.json()` 解析响应体
- `finally` 块中 `page.remove_listener("response", handler)` 避免泄漏
- 响应数据兼容 `data` 为 list 或 dict（`aweme_list` 嵌套）的情况
- `aweme_info` / `aweme` / entry 本身三级 fallback

### 策略 2（fallback）：DOM 选择器

仅当 API 拦截拿到 0 条结果时启用。

**选择器 fallback 链**（按优先级）：
1. `[data-e2e="search-video-item"]`
2. `[data-e2e="search-result-video"]`
3. `ul[data-e2e="search-result-list"] li`
4. `a[href*="/video/"]`

**DOM 提取逻辑**：
- 判断元素是否为 `<a>` 标签，是则直接用，否则在子元素中查找 `a[href*='/video/']`
- 只保留 href 包含 `/video/` 的链接
- 用 `re.search(r'/video/(\d+)', href)` 提取视频 ID
- `seen_ids` 集合去重

## 3. 日志规范

- API 拦截成功：`"Douyin search via API intercept: {N} results"`
- API 拦截失败触发 fallback：`"Douyin API intercept got 0 results, falling back to DOM scraping"`
- DOM fallback 完成：`"Douyin search via DOM fallback: {N} results"`
- API 响应解析失败：`logger.debug("Douyin API response parse failed: %s", e)`

## 4. 验收标准

- [ ] 搜索"超级员工"返回 `total > 0`，包含视频标题、作者、播放量等结构化字段
- [ ] API 拦截策略命中时，日志输出 `"Douyin search via API intercept: N results"`
- [ ] DOM fallback 策略在 API 拦截失败时仍能提取结果
- [ ] 同一视频不被重复采集（`seen_ids` 去重）
- [ ] `page.remove_listener` 在 finally 中执行，无监听器泄漏
- [ ] 返回数据经 `_normalize_search_result()` 统一格式化

## 5. 注意事项

- 本次修复已直接写入 `acquisition_adapters.py`（越权操作），后续如需调整仍以本规范为准。
- 抖音 API 路径可能随版本更新变化，策略 2 的 DOM fallback 是必要兜底。
- `wait_for_timeout(4000)` 可根据网络情况调整，但不宜过短（API 响应需要时间）。

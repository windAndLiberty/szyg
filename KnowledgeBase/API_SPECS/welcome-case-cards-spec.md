# 欢迎页精选案例卡片 — 动态抖音短视频推荐

> 文件范围：后端 `szyg/api/hermes_chat.py` 新增端点 + 前端 `web/src/pages/SuperAgent.vue` 修改
> 状态：待 Elite_Coder 执行
> 依赖模块：`szyg.integrations.acquisition_adapters` (PlaywrightAcquisitionAdapter)、`szyg.api.conversation_routes`

---

## 1. 功能概述

将欢迎页面底部硬编码的 3 个"精选案例"卡片替换为从抖音实时搜索到的短视频。搜索关键词基于用户近期对话历史自动生成，通过 agent 流水线（LLM + acquisition_search 工具）完成关键词推断 → 视频搜索 → 结果筛选的全流程。

**同时验证内容爬取模块**：此功能直接调用 `PlaywrightAcquisitionAdapter._search_douyin()`，可验证 Playwright 浏览器自动化、抖音搜索、API 拦截/DOM 抓取的完整链路。

---

## 2. 数据流

```
SuperAgent.vue (onMounted, 欢迎状态)
  │
  ├─ 1. GET /api/conversations  → 获取近期对话标题列表
  │
  ├─ 2. POST /api/hermes/case-cards
  │      body: { "recent_titles": ["标题1","标题2",...], "limit": 3 }
  │
  └─ 后端流水线:
       │
       ├─ a. LLM 分析 recent_titles → 生成 1-2 个搜索关键词
       │     (调用 _call_llm_for_tools 或直接 _stream_llm_response)
       │
       ├─ b. 调用 PlaywrightAcquisitionAdapter.search(keyword, limit=10)
       │     → 抖音搜索，返回视频列表
       │
       ├─ c. LLM 对搜索结果排序，选出最匹配的 3 个
       │
       └─ d. 返回 JSON { cards: [{ title, cover_url, video_url, author }] }
```

---

## 3. 后端 API 规范

### 3.1 新增端点：`POST /api/hermes/case-cards`

**路由文件**：`d:\szyg\server\szyg\api\hermes_chat.py`

**请求模型**：

```python
class CaseCardRequest(BaseModel):
    recent_titles: list[str] = Field(default_factory=list, description="近期对话标题列表，最多10条")
    limit: int = Field(default=3, description="返回卡片数量")
```

**请求示例**：

```json
{
  "recent_titles": ["帮我搜索抖音AI培训视频并截流", "生成5条护肤文案", "今天12点发3个视频到抖音"],
  "limit": 3
}
```

**响应模型**：

```python
class CaseCard(BaseModel):
    title: str          # 视频标题（截断至 50 字符）
    cover_url: str      # 视频封面图 URL
    video_url: str      # 视频页面 URL (https://www.douyin.com/video/{vid})
    author: str         # 作者昵称
    likes: int          # 点赞数

class CaseCardResponse(BaseModel):
    cards: list[CaseCard]
    keyword: str        # 实际使用的搜索关键词（用于调试/展示）
    source: str         # "douyin" (固定)
```

**响应示例**：

```json
{
  "cards": [
    {
      "title": "AI自动化营销实操教程｜3天涨粉10万",
      "cover_url": "https://p3-sign.douyinpic.com/...",
      "video_url": "https://www.douyin.com/video/7123456789",
      "author": "营销老司机",
      "likes": 12500
    },
    {
      "title": "护肤品牌从0到1的抖音营销策略",
      "cover_url": "https://p9-sign.douyinpic.com/...",
      "video_url": "https://www.douyin.com/video/7123456790",
      "author": "品牌增长官",
      "likes": 8300
    },
    {
      "title": "抖音定时发布工具测评",
      "cover_url": "https://p6-sign.douyinpic.com/...",
      "video_url": "https://www.douyin.com/video/7123456791",
      "author": "效率工具控",
      "likes": 5600
    }
  ],
  "keyword": "抖音AI营销自动化",
  "source": "douyin"
}
```

**错误处理**：

| 场景 | HTTP 状态码 | 响应体 |
|------|------------|--------|
| 无对话历史（空列表） | 200 | `{"cards": [], "keyword": "", "source": "douyin"}` |
| 抖音搜索失败（Playwright 异常） | 200 | `{"cards": [], "keyword": "推断的关键词", "source": "douyin"}` — 不报错，前端降级显示 |
| LLM 调用失败 | 200 | 降级使用 `recent_titles[0]` 作为关键词直接搜索 |
| 全部失败 | 200 | `{"cards": [], "keyword": "", "source": "douyin"}` |

> **重要**：此端点永远返回 HTTP 200，不抛 500。失败时返回空卡片列表，前端降级处理。

### 3.2 后端实现逻辑（伪代码）

```python
@router.post("/api/hermes/case-cards")
async def get_case_cards(req: CaseCardRequest):
    # 1. 关键词推断
    if not req.recent_titles:
        return CaseCardResponse(cards=[], keyword="", source="douyin")

    keyword = await _infer_search_keyword(req.recent_titles)
    if not keyword:
        keyword = req.recent_titles[0]  # fallback

    # 2. 抖音搜索
    try:
        from szyg.integrations.acquisition_adapters import get_acquisition_adapter
        adapter = get_acquisition_adapter("douyin")
        results = await adapter.search(keyword, limit=10)
    except Exception as e:
        logger.warning(f"Case card search failed: {e}")
        return CaseCardResponse(cards=[], keyword=keyword, source="douyin")

    if not results:
        return CaseCardResponse(cards=[], keyword=keyword, source="douyin")

    # 3. LLM 排序筛选（可选，如果 LLM 不可用则取前3条按 likes 排序）
    top_cards = await _select_top_videos(results, req.recent_titles, req.limit)

    return CaseCardResponse(cards=top_cards, keyword=keyword, source="douyin")


async def _infer_search_keyword(titles: list[str]) -> str:
    """用 LLM 从近期对话标题中推断搜索关键词。

    Prompt: "根据以下用户近期任务标题，生成一个适合在抖音搜索的短视频关键词（5-15个字，不要加引号）：
    标题列表: {titles}
    只返回关键词本身，不要其他文字。"
    """
    # 调用 _stream_llm_response 或 _call_llm_for_tools
    # 超时 10 秒，失败返回 ""
    pass


async def _select_top_videos(videos: list[dict], titles: list[str], limit: int) -> list[CaseCard]:
    """从搜索结果中选出最匹配的 limit 个视频。

    策略:
    1. 优先用 LLM 对视频标题与用户任务标题做相关性排序
    2. LLM 不可用时 fallback: 按 likes 降序取前 limit 条
    """
    pass
```

### 3.3 搜索适配器调用细节

使用 `PlaywrightAcquisitionAdapter`（已存在于 `d:\szyg\server\szyg\integrations\acquisition_adapters.py`）：

```python
from szyg.integrations.acquisition_adapters import get_acquisition_adapter
adapter = get_acquisition_adapter("douyin")
results = await adapter.search(keyword, limit=10)
```

`results` 中每个 item 的结构（来自 `_normalize_search_result`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | `str` | 视频标题/描述 |
| `url` | `str` | 视频页面 URL |
| `cover` | `str` | 封面图 URL |
| `author` | `str` | 作者昵称 |
| `likes` | `int` | 点赞数 |
| `plays` | `int` | 播放量 |
| `platform` | `str` | "douyin" |

映射到 `CaseCard`：

```python
CaseCard(
    title=item.get("title", "")[:50],
    cover_url=item.get("cover", ""),
    video_url=item.get("url", ""),
    author=item.get("author", ""),
    likes=item.get("likes", 0),
)
```

---

## 4. 前端变更规范

### 4.1 新增 API 调用函数

在 `SuperAgent.vue` 的 `<script setup>` 中新增：

```js
const caseCards = ref([])
const caseCardsLoading = ref(false)

async function loadCaseCards() {
  if (state.messages.length > 0) return  // 仅欢迎页面加载
  caseCardsLoading.value = true
  try {
    // 获取近期对话标题
    const titles = state.conversations
      .slice(0, 10)
      .map(c => c.title)
      .filter(Boolean)

    const { data } = await axios.post('/api/hermes/case-cards', {
      recent_titles: titles,
      limit: 3,
    })
    caseCards.value = data.cards || []
  } catch (e) {
    console.error('加载精选案例失败:', e)
    caseCards.value = []
  } finally {
    caseCardsLoading.value = false
  }
}
```

### 4.2 修改 `onMounted` 调用

在现有 `onMounted` 中追加 `loadCaseCards()` 调用：

```js
onMounted(() => {
  loadConversations()
  loadCaseCards()  // 新增
})
```

> **注意**：`loadCaseCards` 内部依赖 `state.conversations`，而 `loadConversations` 是异步的。需要确保 `loadConversations` 完成后再调用 `loadCaseCards`，或在 `loadConversations` 的 `.then()` 中触发。建议改为：

```js
onMounted(async () => {
  await loadConversations()
  await loadCaseCards()
})
```

> **合并重复 onMounted**：当前文件有两个 `onMounted` 调用（约第 497 行和第 764 行），应合并为一个。

### 4.3 模板变更

**移除**：`caseCards` 常量定义（硬编码数组）

**修改模板**：将案例区改为动态渲染 + 加载态 + 空态：

```html
<!-- 精选案例 -->
<div class="case-section">
  <div class="case-header">
    <span class="case-title">智能员工 精选案例</span>
  </div>
  <div class="case-cards" v-loading="caseCardsLoading">
    <div
      v-for="card in caseCards"
      :key="card.video_url"
      class="case-card"
      @click="sendQuickCard(card.title)"
    >
      <div class="case-card-image">
        <img v-if="card.cover_url" :src="card.cover_url" :alt="card.title" />
      </div>
      <div class="case-card-title">{{ card.title }}</div>
  </div>
  <div v-if="!caseCardsLoading && caseCards.length === 0" class="case-empty">
    暂无推荐案例
  </div>
</div>
```

**移除项**：
- `<span class="case-more">更多 →</span>` — 完全移除
- 硬编码的 `caseCards` 常量数组

### 4.4 CSS 变更

```css
.case-card-image {
  height: 100px;
  background: var(--accent-soft);
  overflow: hidden;
}

.case-card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.case-empty {
  text-align: center;
  font-size: 13px;
  color: var(--text-tertiary);
  padding: 24px 0;
}
```

### 4.5 欢迎页容器约束

欢迎页面**禁止滚动**，所有元素**整体居中**：

```css
.welcome-page {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;  /* 垂直居中 */
  overflow: hidden;          /* 禁止滚动 */
  padding: 24px 32px;
  max-width: 640px;
  margin: 0 auto;
  width: 100%;
  box-sizing: border-box;
  gap: 32px;                 /* 各区块统一间距 */
}
```

> `overflow: hidden` 确保无论卡片数量多少都不会出现滚动条。`justify-content: center` + `align-items: center` 实现内容整体在可用空间内水平+垂直居中。

### 4.6 点击行为变更

卡片点击后，当前行为是 `sendQuickCard(card.content)`（填入输入框并发送）。

**新行为**：点击卡片将视频标题填入输入框（不自动发送），让用户可以编辑后发送：

```js
function sendQuickCard(content) {
  inputText.value = content
  // 不自动发送，让用户编辑
}
```

> 或者保持自动发送行为不变，将 `card.title` 作为 `content` 传入。由产品决定，暂保持自动发送。

---

## 5. 性能与缓存

### 5.1 超时控制

- LLM 关键词推断：10 秒超时
- 抖音搜索：60 秒超时（Playwright 需要启动浏览器）
- LLM 排序：10 秒超时
- 总超时：90 秒（前端 axios timeout 设置 90s）

### 5.2 缓存策略

- 后端缓存搜索结果 30 分钟（避免每次刷新都触发 Playwright）
- 缓存 key: `f"case_cards:{keyword}"`
- 缓存存储：内存字典（无需持久化）
- 前端不缓存，每次进入欢迎页都请求（但后端有缓存）

```python
_case_card_cache: dict[str, tuple[float, list]] = {}  # keyword -> (timestamp, cards)
_CASE_CARD_CACHE_TTL = 1800  # 30 分钟
```

### 5.3 降级策略

| 失败点 | 降级行为 |
|--------|---------|
| 无对话历史 | 返回空卡片列表，前端显示"暂无推荐案例" |
| LLM 关键词推断失败 | 使用 `recent_titles[0]` 作为关键词 |
| 抖音搜索失败 | 返回空卡片列表 |
| LLM 排序失败 | 按 `likes` 降序取前 3 条 |
| 全部失败 | 空卡片列表，前端显示空态 |

---

## 6. 验收标准

1. 欢迎页加载时，自动调用 `/api/hermes/case-cards` 获取抖音短视频
2. 卡片显示真实视频封面图（`cover_url`）、标题、作者
3. 无对话历史时，显示"暂无推荐案例"空态
4. 搜索失败时，不报错，显示空态
5. "更多 →"链接已移除
6. 卡片点击后，视频标题填入输入框
7. 后端 30 分钟内重复请求使用缓存，不重复启动 Playwright
8. 加载中显示 loading 动画
9. 对话历史面板和底部输入框不受影响（始终保留）
10. 欢迎页面**不可上下滚动**（`overflow: hidden`），所有内容在一屏内完整展示
11. 所有元素**整体在可用空间内水平+垂直居中**（`justify-content: center` + `align-items: center`）

---

## 7. 涉及文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `d:\szyg\server\szyg\api\hermes_chat.py` | 新增端点 | `POST /api/hermes/case-cards` + `_infer_search_keyword` + `_select_top_videos` |
| `d:\szyg\web\src\pages\SuperAgent.vue` | 修改 | 模板、脚本、CSS |
| `d:\szyg\KnowledgeBase\ARCHITECTURE\welcome-page-redesign-spec.md` | 更新 | 移除硬编码 `caseCards` 描述，引用本规范 |

---

## 8. 测试要点

- **内容爬取验证**：首次调用会触发 Playwright 打开抖音搜索页面，检查 `data/audit/douyin/` 下是否生成截图和 HTML
- **无对话历史**：清空 `data/conversations/` 目录，验证空态显示
- **缓存验证**：连续两次调用，第二次应从缓存返回（日志无 "PlaywrightAcquisitionAdapter" 启动）
- **超时验证**：模拟 Playwright 挂起，验证 90 秒后前端不卡死

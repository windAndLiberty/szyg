# szyg 端到端视觉验收测试计划

> 测试目标：验证全部 Phase 1–3 功能在真实浏览器中可正常使用
> 测试环境：http://127.0.0.1:8000  
> 测试工具：Playwright (Chromium headful)

---

## 一、测试范围

### 7 个主导航 + 左侧二级导航 + 深色主题 + API 连通性

| # | 测试模块 | 页面 | 验证点 |
|---|---------|------|--------|
| 1 | 登录认证 | /login | JWT 登录、Token 持久化、错误提示 |
| 2 | 工作台 | /dashboard | 统计卡片、平台就绪数、发布记录表 |
| 3 | 内容中心 | /publisher | 内容 CRUD、审核审批流、AI 生成、平台选择 |
| 4 | 私域运营 | /platforms | 微信卡片、登录按钮、详情弹窗 |
| 5 | 公域获客 | /platforms | 抖音/小红书/B站/快手 4 卡片、发布历史 |
| 6 | 营销自动化 | /scheduler | 任务 CRUD、执行、暂停/恢复、历史 |
| 7 | AI 工作室 | /chat, /image, /video, /agents, /hub | 对话、绘图、视频、智能体列表、AI 导航 |
| 8 | 系统设置 | /admin, /oem, /tools | 用户管理、品牌配置、工具市场 |
| 9 | 深色主题 | 全页面 | 对比度 ≥4.5:1、无消失元素、过渡平滑 |
| 10 | API 连通性 | 所有端点 | 200 响应、JSON 格式正确、无 500 |

---

## 二、测试用例明细

### Test Suite 1: 登录认证 (4 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T1.1 | 正常登录 | 输入 admin/admin → 点击登录 | 跳转 /dashboard，Token 写入 localStorage |
| T1.2 | 错误密码 | 输入 admin/wrong → 点击登录 | 红色错误提示 "密码错误" |
| T1.3 | 空表单 | 不输入 → 点击登录 | 表单校验提示 "请输入用户名" |
| T1.4 | 未登录拦截 | 清除 Token → 访问 /dashboard | 跳转 /login |

### Test Suite 2: 工作台 (3 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T2.1 | 统计卡片 | 登录后查看 /dashboard | 5 张卡片：工具总数、已安装、AI智能体、用户数、平台就绪 |
| T2.2 | 平台就绪数 | 观察第 5 张卡片 | 数字为 0（未登录平台状态） |
| T2.3 | 发布记录表 | 滚动到"最近发布记录" | 表格有表头（时间/平台/内容ID/状态/结果） |

### Test Suite 3: 内容中心 (5 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T3.1 | 创建内容 | 点击"新建内容" → 填标题+正文 → 选平台 → 保存 | 列表出现新内容，状态为"草稿" |
| T3.2 | 提交审核 | 点击"提交审核"按钮 | 状态变为"待审核" |
| T3.3 | 批准 | 点击"通过"按钮 | 状态变为"已批准" |
| T3.4 | AI 生成 | 点击"🤖 AI生成草稿" → 输入主题 → 生成 | 返回 AI 标记的内容草稿 |
| T3.5 | 平台状态图标 | 展开创建对话框 → 查看平台选择器 | 平台旁有 ✓ 或 ? 状态标签 |

### Test Suite 4 & 5: 私域运营 + 公域获客 (6 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T4.1 | 平台卡片展示 | 点击"公域获客" → 查看页面 | 5 张卡片：抖音/小红书/B站/快手/微信 |
| T4.2 | 平台状态 | 观察每张卡片 | 显示"未登录" + "扫码登录"按钮 |
| T4.3 | 点击扫码登录 | 点击抖音的"扫码登录" | Loading 状态 → 提示需桌面扫码 |
| T4.4 | 平台详情 | 点击某平台的"详情"按钮 | 弹窗显示适配器名/状态/登录信息 |
| T4.5 | 发布历史 | 滚动到"发布历史"表格 | 表头完整（时间/平台/内容ID/状态/帖子ID） |
| T4.6 | 私域运营 | 点击"私域运营"导航 | 显示微信相关卡片 + 左侧子菜单 |

### Test Suite 6: 营销自动化 (4 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T6.1 | 任务列表 | 访问 /scheduler | 显示 5 个 demo 任务 |
| T6.2 | 创建任务 | 点击新建 → 填名称 → 选 interval → 保存 | 列表出现新任务 |
| T6.3 | 执行任务 | 点击"立即执行" | 弹出执行结果 |
| T6.4 | 暂停/恢复 | 点击暂停 → 再点击恢复 | 状态切换正常 |

### Test Suite 7: AI 工作室 (7 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T7.1 | 左侧子菜单 | 点击"AI 工作室"导航 | 左侧出现：AI对话/AI绘图/AI视频/AI智能体/AI导航 |
| T7.2 | AI 对话 | 点击"AI 对话" → 输入消息 → 发送 | SSE 流式返回（取决于 Ollama 是否运行） |
| T7.3 | AI 绘图 | 点击"AI 绘图" | 页面加载，显示输入框和风格选择 |
| T7.4 | AI 视频 | 点击"AI 视频" | 页面加载，显示脚本输入区 |
| T7.5 | AI 智能体 | 点击"AI 智能体" | 显示 12 个 Agent 卡片列表 |
| T7.6 | AI 导航 (107 tools) | 点击"AI 导航" | 左侧分类 + 右侧工具卡片网格 |
| T7.7 | AI 导航筛选 | 点击左侧"AI 绘画"分类 | 右侧仅显示绘画类工具卡片 |

### Test Suite 8: 系统设置 (4 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T8.1 | 左侧子菜单 | 点击"系统设置"导航 | 左侧：用户管理/品牌设置/工具市场 |
| T8.2 | 用户管理 | 点击"用户管理"（需 admin） | 用户列表表格 |
| T8.3 | 品牌设置 | 点击"品牌设置" | 品牌名/Logo/Copyright 配置表单 |
| T8.4 | 工具市场 | 点击"工具市场" | 8 个工具分类列表 |

### Test Suite 9: 深色主题 (5 cases)

| ID | 用例 | 操作 | 预期结果 |
|----|------|------|---------|
| T9.1 | 切换主题 | 点击右上角 💡 | 页面切换为深色背景 |
| T9.2 | 文字对比度 | 观察侧边栏未选中项 | 文字清晰可辨（≥4.5:1 对比度） |
| T9.3 | 卡片可见 | 查看 AI 导航工具卡片 | 卡片边框清晰、文字可读 |
| T9.4 | 输入框可见 | 查看搜索框/表单 | 边框可见、placeholder 可辨 |
| T9.5 | 再切回浅色 | 再次点击 💡 | 恢复浅色主题，无残留深色元素 |

### Test Suite 10: API 连通性 (7 cases)

| ID | 用例 | 端点 | 预期 |
|----|------|------|------|
| T10.1 | 健康检查 | GET /api/health | 200, {"status":"ok"} |
| T10.2 | 平台列表 | GET /api/platforms | 200, platforms 数组长度 ≥5 |
| T10.3 | 发布统计 | GET /api/publisher/stats | 200, 含 total/drafts/published |
| T10.4 | 调度任务 | GET /api/scheduler/jobs | 200, 任务数组 |
| T10.5 | AI 导航 | GET /api/hub/list | 200, 107 个工具 |
| T10.6 | Brain MCP | GET /api/brain/mcp | 200, 9 个 MCP 服务器 |
| T10.7 | Brain 提示词 | GET /api/brain/prompt | 200, 含"文案写作""AI SEO""视频剪辑" |

---

## 三、执行方式

### 方式 A：手动视觉验收
打开 http://127.0.0.1:8000，逐项对照上表验证，记录通过/失败。

### 方式 B：Playwright 自动化脚本
编写 `e2e_test.py`，使用 Playwright 自动执行上述用例，截图 + 断言。
覆盖范围：T1–T10 共 **45 个用例**。

---

## 四、通过标准

- 全部 45 个用例通过 = ✅ 验收通过
- API 端点全部 200，无 500 错误
- 深色主题所有文字对比度 ≥4.5:1（肉眼可辨）
- 导航切换无白屏、无 JS 报错

---

等待确认后编写 Playwright E2E 脚本并执行。

---

# 系统脆弱性分析

> 评估日期: 2026-06-07  
> 原则: 按"用户实际使用中先崩哪个"排序

## 崩溃等级定义

| 等级 | 含义 | 用户感知 |
|------|------|---------|
| 🔴 Critical | 必然崩溃，无限循环 | 功能完全不可用 |
| 🟠 High | 高概率崩溃，无恢复路径 | 需手动重启/修复 |
| 🟡 Medium | 中等概率，有降级路径 | 部分功能不可用 |
| 🟢 Low | 低概率或自动恢复 | 偶尔异常，自动恢复 |

---

## 🔴 Critical — 必然崩溃

### 1. 数据层: JSON 文件并发写入 → 数据损坏

**位置**: `publisher.py` `_read`/`_write`, `scheduler_engine.py` 同上

**问题**:
```
请求A: _read() → modify → _write()
请求B: _read() → modify → _write()   ← 同时发生
结果:  B 的写入覆盖 A, A 的操作被静默丢失
```

**为什么必然触发**: 一个用户打开 Publisher 页面，Vue 同时发 3 个 API 请求（list + stats + calendar），每个请求都 `_read` 不同的 JSON 文件，读没问题。但只要有两个写操作（比如一个人点"发布"的同时另一个人点"审批"），后到的 `_write` 覆盖前者。

**当前保护**: 无。没有 `threading.Lock`、没有 `asyncio.Lock`、没有文件排他锁。

**修复建议**: 
```python
# publisher.py
_write_lock = asyncio.Lock()

async def _write_safe(path, data):
    async with _write_lock:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ...))
        tmp.replace(path)  # atomic on same filesystem
```

### 2. 错误吞噬 → 无感知故障

**位置**: 全系统 **60+ 处 `except: pass` / `except Exception: pass`**

**典型案例**:
```python
# wechat_desktop.py:196
except Exception:
    pass   # UIA 定位失败 → 静默跳过 → 用户以为朋友圈发出去了，其实没发

# publisher.py:83
except Exception:
    pass   # API 调用失败 → 静默 → 前端收到空数据

# scheduler_engine.py:171
except asyncio.CancelledError:
    pass   # 调度器循环被取消 → 所有定时任务停止 → 用户不知道
```

**为什么必然触发**: 微信 UIA 选择器依赖微信版本，微信升级一次 → 选择器全部失效 → 所有 `except: pass` 触发 → 用户看不到任何报错，以为"朋友圈已发"，实际什么都没发生。

---

## 🟠 High — 高概率崩溃

### 3. Playwright 浏览器: 僵尸进程 + 内存泄漏

**位置**: `douyin.py`, `xiaohongshu.py`, `bilibili.py`, `kuaishou.py`

**问题链**:
```
第1次发布 → launch chromium → 正常
第2次发布 → launch chromium → 又启动一个 ← 旧 browser 没关
第5次发布 → 5 个 chromium 进程 → 消耗 5×800MB = 4GB
...内存耗尽 → Windows OOM → 系统卡死
```

**当前保护**: 
- `Adapter.close()` 方法存在，但**没有人调用它**
- `Publisher.publish_async()` 发布后不 close browser context
- 每个 adapter 独立启动 browser，互不共享

**修复建议**: 一个共享 browser context pool，发布完复用，不每次都启停。

### 4. Scheduler 后台循环: 静默死亡

**位置**: `scheduler_engine.py:_run_loop()`

**问题**:
```python
async def _run_loop(self):
    while self._running:
        try:
            await asyncio.sleep(60)
            await self._tick()
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"tick error: {e}")  # 仅日志，loop 继续
```

`_tick()` 内部如果有一个任务超时 300 秒（Playwright 发布），整个 tick 阻塞，后续到期任务全部延迟。如果 `_async_dispatch` 里抛出未被捕获的 `asyncio.TimeoutError`，循环继续但状态未知。

**修复建议**: `_tick()` 内每个 job 用 `asyncio.wait_for(job, timeout=120)` 独立超时。

### 5. 前端大 Chunk: 首次加载白屏

**位置**: `web/dist/assets/index-B09PQ2Dw.js` — **1,022 KB** (gzip 后 328 KB)

**问题**: 一条 JS bundle 包含全部 13 个页面的代码。用户首次打开 → 下载 1MB JS → 解析 → 渲染。在 4G 网络下耗时 5-8 秒白屏。如果 JS 解析出错（比如一个未 import 的组件），整个 SPA 不可用。

**当前保护**: `did-fail-load` 在 Electron 里显示错误页。浏览器里是白屏。

---

## 🟡 Medium — 中等概率

### 6. 平台反爬风控: 账号被封

**位置**: 所有 Playwright adapter

**问题**: 5 个 adapter 同一 IP 同时登录操作 → 抖音/小红书/B站风控系统标记为自动化 → 封号/限流。`anti_detect.py` 的 stealth.js 能过基础检测，但高频操作（每天发 10 条）必然触发。

**当前保护**: 无频率限制、无 IP 轮换、无行为随机化（虽然有 `HumanBehavior` 但只在个别地方调用）。

### 7. Session Cookie 过期 → 无感发布失败

**位置**: `session_manager.py` → 所有 adapter

**问题**: cookie 过期检查有 24 小时容差，但超过后 adapter 仍然尝试发布 → Playwright 跳转到登录页 → `publish()` 找不到"发布"按钮 → 超时 → 抛出异常 → 被 `except: pass` 吞掉。

**修复建议**: `publish()` 执行前强制 `check_login()`，若未登录则返回明确错误，不做盲操作。

---

## 🟢 Low — 低概率或可自愈

### 8. FFmpeg 大文件处理 → 磁盘满

视频引擎处理 4K 素材时临时文件可能耗尽磁盘。

### 9. MCP Server 子进程僵尸

9 个 MCP server 通过 stdio 通信，如果父进程（Hermes）被杀，子进程可能残留。

### 10. 多租户数据迁移

`data/tenants/{tenant}/` 目录结构是运行时创建的，如果租户 ID 包含特殊字符（`../`, `\`, `:`），可能导致路径遍历或创建失败。

---

## 优先级修复路线图

| 序号 | 问题 | 等级 | 修复量 | 建议版本 |
|------|------|------|--------|---------|
| 1 | JSON 并发写入 | 🔴 | 20 行 | v1.1 |
| 2 | 错误吞噬 | 🔴 | 100+ 行 | v1.1 |
| 3 | Playwright 进程泄漏 | 🟠 | 50 行 | v1.2 |
| 4 | Scheduler 静默死 | 🟠 | 30 行 | v1.2 |
| 5 | 前端大 Chunk | 🟠 | 改 vite 配置 | v1.3 |
| 6 | Session 过期无感知 | 🟡 | 20 行 | v1.2 |
| 7 | 反爬风控 | 🟡 | 需设计 | v1.3 |
| 8 | FFmpeg 磁盘满 | 🟢 | 10 行 | v1.3 |
| 9 | MCP 僵尸进程 | 🟢 | 15 行 | v1.3 |
| 10 | 租户路径遍历 | 🟢 | 5 行 | v1.1 |

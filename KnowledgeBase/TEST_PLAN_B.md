# 🔬 域灵系统 — P0 端到端测试计划 (批次B)

> 版本：v1.0
> 日期：2026-07-05
> 状态：待执行
> 前置：后端8000端口运行 + szyg-frontend构建就绪

---

## 测试总则

### 环境准备

```bash
# 1. 启动后端
cd server/szyg
uv run main.py  （端口8000）

# 2. 验证后端健康
curl http://localhost:8000/api/health
# 预期: {"status":"ok","version":"1.0.0"}

# 3. 前端dev模式 (排查用)
cd szyg-frontend
npm run dev  （端口5173，代理到8000）
```

### 测试原则

- 每轮测试产出：(通过/失败/边界) 三元结果
- 失败需记录：请求/响应/screenshot/console error
- 优先测试可通过curl直接验证的后端接口，再测前端

---

## B1 🔴 SSE对话全链路 — 核心中的核心

### 概述
SuperAgent页面(`/`)的用户输入→SSE流式返回→多模态渲染→自动保存→历史加载的完整闭环。

### B1.1 纯文本消息流

```
Step 1: 发送纯文本消息
  curl -N -X POST http://localhost:8000/api/hermes/chat \
    -H "Content-Type: application/json" \
    -d '{
      "model": "doubao-pro",
      "messages": [{"role":"user","content":"你好，介绍一下自己"}],
      "stream": true
    }'

  预期SSE事件序列:
    event: text      data: {"content":"你好"}
    event: text      data: {"content":"！"}
    event: text      data: {"content":"我是"}
    ... (累加流式文本)
    event: done      data: {}

  验收:
  ✅ SSE连接成功 (HTTP 200 + text/event-stream)
  ✅ 收到多个text事件，内容连贯
  ✅ 最后收到done事件
  ✅ 无error事件
  ✅ 首字延迟 < 2s (火山引擎云端推理)

Step 2: 前端验证
  打开 http://localhost:5173/
  在输入框输入"你好，介绍一下自己" → 按Enter

  验收:
  ✅ 用户消息出现(气泡+头像)
  ✅ AI回复流式出现(光标闪烁→逐字渲染)
  ✅ Markdown渲染正确(标题/列表/代码块)
  ✅ 流结束后光标消失
  ✅ 对话出现在左侧历史面板
  ✅ 刷新页面后对话仍在
```

### B1.2 工具调用可视化

```
Step 1: 触发工具调用
  "搜索抖音上关于AI的视频"

  预期SSE事件序列:
    event: tool_call    data: {"name":"acq_search","arguments":{...},"status":"running"}
    event: tool_result  data: {"name":"acq_search","result":{...,"ok":true}}

  -- Agent可能再调用一次LLM总结后发text --
    event: text        data: {"content":"为你找到以下抖音视频..."}
    event: done        data: {}

  验收:
  ✅ tool_call卡片出现，显示acq_search和参数
  ✅ 卡片状态running→success(绿色)
  ✅ tool_result摘要正确(截断200字符)
  ✅ 后续text总结搜索结果为中文自然语言(非JSON)
  ✅ 无JSON片段泄露到用户可见文本中

Step 2: 测试工具错误场景
  "查看一个不存在的平台状态xxxplatform"

  验收:
  ✅ tool_result卡片状态变为error(红色)
  ✅ AI用自然语言解释失败原因
  ✅ 无原始error JSON展示
```

### B1.3 图片消息

```
  发送: "帮我生成一张蓝色科技风的Logo图"

  预期SSE:
    event: tool_call     → ai_image_generate (running)
    event: tool_result   → ai_image_generate (success, 含image_url)
    event: image         → {"url":"http://...","prompt":"蓝色科技风Logo"}

  验收:
  ✅ 图片卡片在消息流中渲染(图片可见)
  ✅ 点击图片 → Lightbox全屏查看
  ✅ Lightbox支持缩放/旋转/拖动
  ✅ 对话保存后重加载，图片仍存在
```

### B1.4 视频生成完整链路

```
  发送: "生成一个5秒的海浪短视频"

  预期SSE:
    ① event: tool_call     → ai_video_create (running)
    ② event: tool_result   → ai_video_create (success, task_id, prompt)
    ③ event: video_task    → {"task_id":"xxx","prompt":"海浪短视频","status":"queued"}
    ④ (Agent轮询) tool_call → ai_video_task_status (running)
    ⑤ event: video_status  → {"task_id":"xxx","status":"running","progress":50}
    ⑥ (轮询2)
    ⑦ event: video_status  → {"task_id":"xxx","status":"succeed","progress":100}
    ⑧ event: video         → {"task_id":"xxx","url":"http://...","prompt":"..."}
    ⑨ event: done

  前端验收:
  ✅ ③→进度卡片出现 (spinner+提示词+「生成中0%」)
  ✅ ⑤→进度百分比实时更新 (50%)
  ✅ ⑦→进度达到100%
  ✅ ⑧→进度卡片替换为<video>播放器
  ✅ 视频可播放、pause、seek
  ✅ 「放大」按钮→Modal overlay(半透明背景+居中播放器+关闭/全屏)
  ✅ 「全屏」按钮→浏览器原生全屏,ESC退出
  ✅ 「下载」按钮→触发文件下载
  ✅ 对话重新加载后视频仍可播放

  视频生成失败场景:
  验收:
  ✅ 进度卡片状态→error(红色)
  ✅ AI告知"生成失败，请稍后重试"(自然语言)
```

### B1.5 对话保存+历史加载

```
  1. 发送一条文本消息(不切对话)
  2. 流结束后自动保存 (验证左侧面板出现新对话)
  3. 再发一条工具消息(如搜索)
  4. 切换到另一个历史对话
  5. 切回刚才的对话

  验收:
  ✅ 对话自动保存 (title=第一条用户消息截断50字符)
  ✅ 切换对话后消息区刷新为对应对话
  ✅ 混合消息类型(text/image/video/tool_result)全部正确渲染
  ✅ 新对话→POST,已有对话→PUT (F12 Network验证)
```

### B1.6 边界与异常

```
  1. 空消息: 发送空白内容 → 不应发送 / 前端拦截
  2. 超长消息: 发送5000字符 → 正常流式返回(不截断)
  3. 网络断开: 拔网线/断wifi → 前端显示"请求失败"+可重试
  4. 401重试: 手动使token失效 → 前端自动刷新token重试
  5. 并发消息: streaming=true时再发送 → 输入框禁用/拦截
  6. Markdown XSS: 输入"<script>alert(1)</script>" → DOMPurify消毒,不执行
```

---

## B2 🔴 对话历史CRUD

### 概述
左侧对话历史面板的完整管理功能：新建→选择→重命名→置顶→导出→删除。

### B2.1 新建+选择

```
  1. 打开 http://localhost:5173/
  2. 点击左侧面板「+」按钮 → 清空消息区,显示欢迎页
  3. 发送 "测试对话1" → 自动创建新对话
  4. 再点「+」,发送 "测试对话2" → 又创建新对话
  5. 点击左侧"测试对话1" → 加载对话1的消息
  6. 点击"测试对话2" → 加载对话2的消息

  验收:
  ✅ 欢迎页显示(logo+输入框+案例卡片)
  ✅ 发送后创建对话,左侧出现"测试对话1"
  ✅ 点击后加载对应消息,消息渲染一致
  ✅ 切换过程中无闪烁/重叠
  ✅ 欢迎页案例卡片可见(动态加载+缓存)
```

### B2.2 重命名

```
  1. 右键"测试对话1" → 选「重命名」
  2. 弹出输入框,预填"测试对话1"
  3. 改为"我的第一个测试" → 确认
  4. 校验: 输入空字符串 → 提示"标题不能为空"

  验收:
  ✅ 右键菜单在正确位置出现(不溢出屏幕)
  ✅ 重命名后列表更新
  ✅ 空标题校验生效
  ✅ API: PUT /api/conversations/{id} → 200
```

### B2.3 置顶

```
  1. 右键"测试对话2" → 选「置顶」→ 列表顶部出现📌标记
  2. 再右键 → 选「取消置顶」→ 📌消失,恢复原排序
  3. 多个置顶对话共存 → 按时间排序

  验收:
  ✅ 📌图标出现/消失
  ✅ 置顶对话排在最前(pinned=true优先)
  ✅ API: PUT + pinned字段
```

### B2.4 导出

```
  1. 右键一个含混合消息的对话 → 选「导出」
  2. 浏览器下载一个.md文件
  3. 打开.md文件检查

  验收:
  ✅ 文件下载成功,文件名非随机(含标题)
  ✅ Markdown包含: # 标题 / > 导出时间 / > 消息数
  ✅ 用户消息: ### 用户 + 内容
  ✅ 助手消息: ### 助手 + 内容
  ✅ 含工具调用/图片/视频的消息类型在文本中可辨识
```

### B2.5 删除+边界

```
  1. 右键"测试对话1" → 选「删除」→ 弹出确认弹窗
  2. 确认 → 对话从列表消失
  3. 删除当前正在查看的对话 → 消息区清空,回到欢迎页
  4. 取消删除 → 对话保留

  验收:
  ✅ 确认弹窗显示对话标题 + "此操作不可撤销"
  ✅ 删除后列表刷新
  ✅ 删除当前对话→清空消息区回到欢迎页
  ✅ 取消→不删除
  ✅ API: DELETE /api/conversations/{id} → 200
```

---

## B3 🔴 多平台发布

### 概述
验证5平台(抖音/小红书/B站/快手/微信)的登录→发布→数据查询闭环。

### B3.1 平台状态检查

```
  1. "检查所有平台的登录状态"
  或 curl: GET /api/platforms/health

  验收:
  ✅ 返回5平台状态: ready/error/uninitialized
  ✅ 返回is_logged_in字段
  ✅ 微信wechat_mp未运行→显示error(可接受,需桌面客户端)
  ✅ 前端展示为列表或表格
```

### B3.2 发布流程 (以抖音为例)

```
  1. "检查抖音登录状态" → 未登录
  2. "登录抖音" → 打开扫码页面/提示用户扫码
  3. 手机扫码 → 登录成功→Cookie持久化
  4. "将视频/图片发到抖音,标题测试发布,标签AI,测试"
  5. 发布成功 → 返回 post_id
  6. "查看刚才那条抖音的数据" → 返回播放量/点赞/评论/分享

  验收:
  ✅ platform_status返回登录状态
  ✅ platform_login触发扫码(有头浏览器)
  ✅ platform_publish_direct成功返回{post_id, url}
  ✅ AI报告"已成功发布到抖音,帖子ID: xxx"
  ✅ platform_post_status返回播放数据
  ✅ Cookie失效→提示重新登录
```

### B3.3 定时发布

```
  "明天上午10点把这3个视频发到抖音和小红书"

  验收:
  ✅ AI正确解析时间为"2026-07-06 10:00"
  ✅ 调用sau_upload_video带schedule参数
  ✅ 多平台逐一发布,汇总报告成功/失败
```

### B3.4 边界

```
  1. 未登录直接发布 → AI提示"尚未登录,正在打开登录页面"→自动跳转登录
  2. 标题过长(>平台限制) → 发布失败 + AI告知原因
  3. 不支持的视频格式 → 发布失败 + AI告知
  4. 同时发布3个平台 → 顺序发布,汇总结果
```

---

## B4 🟡 视频生成+卡片渲染

### 概述
文生视频异步任务的完整交互：创建→进度→播放器。

**注意**: B4依赖火山引擎视频API(需有效API Key),如Key未配置则先标记为阻塞,跳过。

```
  1. "生成一个5秒的海洋主题短视频"
  2. 观察SSE事件序列: tool_call(video_create)→video_task→轮询→video
  3. 前端验证进度卡片→播放器转换
  4. 点击播放器各按钮:放大/全屏/下载
  5. 对话保存后重加载,视频仍可播放

  验收:
  ✅ 进度卡片实时更新(0%→50%→100%)
  ✅ 完成后自动替换为播放器
  ✅ 放大Modal弹窗(半透明背景+居中播放器)
  ✅ 全屏播放+ESC退出
  ✅ 下载功能
  ✅ 重新加载对话后视频完好
  ✅ 生成失败时进度卡片变红色+AI解释原因
```

---

## B5 🟡 视频剪辑

### 概述
对话驱动的视频处理：查看信息→裁剪→拼接→叠加文字→混音→提取封面。

**注意**: B5依赖本地FFmpeg,需确认`ffmpeg -version`可用。

### B5.1 基础操作

```
  1. "查看 /data/videos/test.mp4 的信息"
     → 返回时长/分辨率/编码
  2. "把视频裁剪成前10秒"
     → 输出 output_cut.mp4
  3. "把视频慢放一半" (speed=0.5)
     → 输出慢速视频
  4. "给视频加上标题新品上市"
     → 输出有水印标题视频
  5. "把视频原声音量降到30%,加上bgm.mp3作为背景音乐"
     → 输出混音视频
  6. "从视频第3秒截取一帧作为封面"
     → 输出 cover.jpg

  验收:
  ✅ video_info返回JSON(时长/分辨率/编码)
  ✅ video_cut按指定start+duration裁剪
  ✅ video_concat正确拼接多视频
  ✅ video_add_title文字叠加后可见
  ✅ video_mix_audio混音后原声+BGM共存
  ✅ video_extract_frame输出封面图
```

### B5.2 链式操作

```
  用户: "把视频裁剪前15秒"
  AI: [调用video_info→video_cut] "已裁剪,输出:output_cut.mp4"
  用户: "给裁剪后的视频加上标题精彩片段"
  AI: [调用video_add_title] "已添加标题,输出:output_title.mp4"
  用户: "从第3秒截取封面"
  AI: [调用video_extract_frame] "已提取封面,输出:cover.jpg"

  验收:
  ✅ 链式操作中AI记住前一步的输出文件路径
  ✅ 每步操作时间 <30s (FFmpeg处理)
```

### B5.3 模板

```
  1. "有哪些可用的视频模板" → AI调用video_templates列出
  2. "用模板1渲染,素材是xxx.mp4,标题新品上市"
     → AI调用video_render

  验收:
  ✅ video_templates返回模板列表(id+名称+描述)
  ✅ video_render输出渲染后视频
```

---

## 批B 执行顺序与依赖

```
B1 ─┬─ 纯文本 ──────── 无依赖,优先
    ├─ 工具调用 ────── 依赖 B1.1 通过
    ├─ 图片生成 ────── 依赖火山引擎API
    ├─ 视频生成卡片 ── 依赖火山引擎API(同B4,可合并验证)
    └─ 保存+加载 ──── 依赖 B1.1

B2 ─── 独立验证 ──── 依赖有对话数据

B3 ─┬─ 平台状态 ──── 无依赖
    ├─ 发布流程 ──── 需有真实登录态
    └─ 定时发布 ──── 依赖B3.2

B4 ─── 视频生成 ──── 依赖火山引擎视频API(如有)

B5 ─── 视频剪辑 ──── 依赖FFmpeg + 本地测试视频文件
```

### 建议执行顺序: B1.1 → B1.2 → B1.5 → B2 → B1.3(如有API) → B3.1 → B3.2(如有登录) → B5(如有FFmpeg) → B1.4/B4


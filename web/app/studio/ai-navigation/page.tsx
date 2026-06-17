'use client'

import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search, Compass, ChevronRight, ArrowUpRight,
  Users, FileText, Palette, Zap, Code, Building2,
} from 'lucide-react'
import AppLayout from '@/components/AppLayout'

interface AITool {
  id: string
  name: string
  desc: string
  url: string
  category: string
  tags: string[]
  isHot?: boolean
  isFree?: boolean
  isDomestic?: boolean
  letter: string
  color: string // Gradient class for icon background
}

const CATEGORIES = [
  { id: 'all', label: '全部工具', icon: Compass },
  { id: 'collab', label: '综合办公协同', icon: Users },
  { id: 'content', label: '文档与写作', icon: FileText },
  { id: 'creative', label: '设计与视频', icon: Palette },
  { id: 'efficiency', label: '会议与效率', icon: Zap },
  { id: 'dev', label: 'IT与低代码', icon: Code },
  { id: 'business', label: '专业业务支撑', icon: Building2 },
]

const AI_TOOLS_DB: AITool[] = [
  // ── 综合办公与全域协同 ──
  {
    id: 'wps365',
    name: 'WPS 365',
    desc: 'AI 深度融入文档、表格、演示的一站式协同办公平台，原生集成办公流。',
    url: 'https://365.wps.cn/',
    category: 'collab',
    tags: ['协同平台', '文档协同', '推荐'],
    isHot: true,
    isDomestic: true,
    letter: 'W',
    color: 'from-red-600 to-orange-500',
  },
  {
    id: 'dingtalk',
    name: '钉钉',
    desc: '集成 AI 的日常沟通、任务管理、流程审批与考勤协同一体化平台。',
    url: 'https://www.dingtalk.com/',
    category: 'collab',
    tags: ['协同平台', '沟通审批'],
    isHot: true,
    isDomestic: true,
    letter: '钉',
    color: 'from-sky-600 to-blue-500',
  },
  {
    id: 'feishu',
    name: '飞书',
    desc: '文档、即时沟通、视频会议、多维表格深度协同，AI 助手贯穿全流程。',
    url: 'https://www.feishu.cn/',
    category: 'collab',
    tags: ['协同平台', '文档', '项目'],
    isHot: true,
    isDomestic: true,
    letter: '飞',
    color: 'from-blue-600 to-cyan-400',
  },
  {
    id: 'wecom',
    name: '企业微信',
    desc: '连接微信生态，做好客户沟通、社群运营与内部协同的企业级工具。',
    url: 'https://work.weixin.qq.com/',
    category: 'collab',
    tags: ['协同平台', '客户沟通'],
    isDomestic: true,
    letter: '企',
    color: 'from-green-600 to-emerald-400',
  },
  {
    id: 'workbuddy',
    name: 'WorkBuddy',
    desc: '腾讯 AI 工作台，串联企业内多种应用，用对话完成日常协同任务。',
    url: 'https://workbuddy.qq.com/',
    category: 'collab',
    tags: ['AI工作台', '协同'],
    isDomestic: true,
    letter: 'W',
    color: 'from-violet-600 to-purple-400',
  },
  {
    id: 'zentao',
    name: '禅道',
    desc: '老牌国产研发项目管理系统，覆盖需求、任务、缺陷的全流程管理。',
    url: 'https://www.zentao.net/',
    category: 'collab',
    tags: ['项目管理', '研发'],
    isDomestic: true,
    letter: '禅',
    color: 'from-slate-600 to-gray-500',
  },
  {
    id: 'lexiang',
    name: '腾讯乐享',
    desc: '企业级知识库与学习平台，沉淀团队经验，支持智能问答与文档管理。',
    url: 'https://lexiang.qq.com/',
    category: 'collab',
    tags: ['企业知识库', '智能问答'],
    isDomestic: true,
    letter: '乐',
    color: 'from-blue-700 to-sky-500',
  },
  {
    id: 'youdao-baoku',
    name: '有道宝库',
    desc: '网易有道的 AI 知识库，让企业信息不再是孤岛，随问随答。',
    url: 'https://baoku.youdao.com/',
    category: 'collab',
    tags: ['AI知识库', '文档管理'],
    isDomestic: true,
    letter: '有',
    color: 'from-rose-600 to-red-400',
  },
  {
    id: 'ima',
    name: 'ima.copilot',
    desc: '腾讯出品的智能工作台，构建专属知识库，边搜边写边问答。',
    url: 'https://ima.qq.com/',
    category: 'collab',
    tags: ['知识库', '智能问答', '腾讯'],
    isFree: true,
    isDomestic: true,
    letter: 'i',
    color: 'from-purple-600 to-fuchsia-400',
  },

  // ── 文档处理与内容创作（写作 / PPT / PDF） ──
  {
    id: 'doubao',
    name: '豆包',
    desc: '字节跳动全能型 AI 助手，撰写公文、营销文案、邮件、报告样样精通。',
    url: 'https://www.doubao.com/',
    category: 'content',
    tags: ['AI写作', '全能型', '免费'],
    isHot: true,
    isFree: true,
    isDomestic: true,
    letter: '豆',
    color: 'from-sky-500 to-blue-400',
  },
  {
    id: 'ernie-bot',
    name: '文心一言',
    desc: '百度文心大模型，擅长中文公文写作、营销策划与知识问答。',
    url: 'https://yiyan.baidu.com/',
    category: 'content',
    tags: ['AI写作', '百度'],
    isHot: true,
    isDomestic: true,
    letter: '文',
    color: 'from-blue-600 to-indigo-400',
  },
  {
    id: 'tongyi-qianwen',
    name: '通义千问',
    desc: '阿里通义大模型，支持多风格文本生成、长文档总结与逻辑推理。',
    url: 'https://tongyi.aliyun.com/',
    category: 'content',
    tags: ['AI写作', '阿里'],
    isHot: true,
    isDomestic: true,
    letter: '千',
    color: 'from-purple-600 to-violet-400',
  },
  {
    id: 'kimi',
    name: 'Kimi',
    desc: '月之暗面出品，超长上下文阅读与写作，适合处理大段资料与长文。',
    url: 'https://kimi.moonshot.cn/',
    category: 'content',
    tags: ['AI写作', '长文本', '免费'],
    isFree: true,
    isDomestic: true,
    letter: 'K',
    color: 'from-green-600 to-emerald-400',
  },
  {
    id: 'spark',
    name: '讯飞星火',
    desc: '科大讯飞认知大模型，写作、翻译、语音交互一体化的办公助手。',
    url: 'https://xinghuo.xfyun.cn/',
    category: 'content',
    tags: ['AI写作', '语音'],
    isDomestic: true,
    letter: '讯',
    color: 'from-blue-700 to-cyan-500',
  },
  {
    id: 'wps-ai',
    name: 'WPS AI',
    desc: '一键将大纲或文档生成专业 PPT，并支持文档智能阅读与排版。',
    url: 'https://ai.wps.cn/',
    category: 'content',
    tags: ['AI PPT', '文档'],
    isHot: true,
    isDomestic: true,
    letter: 'W',
    color: 'from-red-600 to-rose-400',
  },
  {
    id: 'wondershare-pdf',
    name: '万兴PDF',
    desc: '智能编辑、翻译、OCR 识别与文档问答，轻松处理合同、手册、财报。',
    url: 'https://pdf.wondershare.cn/',
    category: 'content',
    tags: ['智能PDF', '编辑问答'],
    isDomestic: true,
    letter: '万',
    color: 'from-red-500 to-orange-400',
  },

  // ── 设计 / 营销素材 / 视频 / 数字人 / 脑图 ──
  {
    id: 'jimeng',
    name: '即梦AI',
    desc: '字节出品，快速生成营销海报、产品图与短视频的一站式创作平台。',
    url: 'https://jimeng.jianying.com/',
    category: 'creative',
    tags: ['营销海报', '字节'],
    isHot: true,
    isDomestic: true,
    letter: '即',
    color: 'from-pink-600 to-rose-400',
  },
  {
    id: 'tuxu',
    name: '图叙AI',
    desc: '智能生成信息图、营销长图文与数据可视化，让内容更有说服力。',
    url: 'https://www.tuxu.ai/',
    category: 'creative',
    tags: ['信息图', '长图文'],
    isDomestic: true,
    letter: '图',
    color: 'from-purple-600 to-indigo-400',
  },
  {
    id: 'kling',
    name: '可灵 AI',
    desc: '快手出品的视频生成大模型，文本/图片一键生成营销短视频与演示。',
    url: 'https://klingai.kuaishou.com/',
    category: 'creative',
    tags: ['AI视频', '快手'],
    isHot: true,
    isDomestic: true,
    letter: '可',
    color: 'from-orange-600 to-rose-500',
  },
  {
    id: 'seedance',
    name: 'Seedance 2.0',
    desc: '字节豆包视频生成模型，擅长高动态、连贯运镜的创意短视频。',
    url: 'https://www.volcengine.com/product/seedance',
    category: 'creative',
    tags: ['AI视频', '高动态'],
    isDomestic: true,
    letter: 'S',
    color: 'from-violet-700 to-purple-500',
  },
  {
    id: 'wondershare-mind',
    name: '万兴脑图',
    desc: '一键 AI 生成思维导图，梳理思路、总结要点、辅助头脑风暴。',
    url: 'https://mindmap.wondershare.cn/',
    category: 'creative',
    tags: ['思维导图', 'AI生成'],
    isDomestic: true,
    letter: '脑',
    color: 'from-emerald-600 to-teal-400',
  },
  {
    id: 'gitmind',
    name: 'GitMind 思乎',
    desc: '多端同步的在线脑图与流程图工具，支持 AI 一键生成与总结。',
    url: 'https://gitmind.cn/',
    category: 'creative',
    tags: ['脑图', '多端同步', '免费'],
    isFree: true,
    isDomestic: true,
    letter: 'G',
    color: 'from-sky-600 to-cyan-400',
  },
  {
    id: 'zhixi',
    name: '知犀',
    desc: '支持 DeepSeek 的思维导图工具，一键生成结构化脑图，适合分析规划。',
    url: 'https://www.zhixi.com/',
    category: 'creative',
    tags: ['思维导图', 'DeepSeek'],
    isFree: true,
    isDomestic: true,
    letter: '知',
    color: 'from-indigo-600 to-blue-400',
  },

  // ── 会议与日常效率提升 ──
  {
    id: 'dingtalk-ai-note',
    name: '钉钉AI听记',
    desc: '实时将会议语音转文字，自动生成结构化纪要与待办事项。',
    url: 'https://www.dingtalk.com/',
    category: 'efficiency',
    tags: ['会议纪要', '实时转写'],
    isHot: true,
    isDomestic: true,
    letter: '听',
    color: 'from-sky-600 to-blue-500',
  },
  {
    id: 'wps-note',
    name: 'WPS笔记',
    desc: 'AI 会议记录与笔记整理，自动归纳要点、生成待办与摘要。',
    url: 'https://note.wps.cn/',
    category: 'efficiency',
    tags: ['会议记录', '待办'],
    isDomestic: true,
    letter: '笔',
    color: 'from-red-600 to-rose-400',
  },
  {
    id: 'iflyrec',
    name: '讯飞听见',
    desc: '高准确率语音转文字与实时翻译，会议、采访、培训记录利器。',
    url: 'https://www.iflyrec.com/',
    category: 'efficiency',
    tags: ['语音转写', '实时翻译'],
    isDomestic: true,
    letter: '听',
    color: 'from-blue-700 to-cyan-500',
  },
  {
    id: 'quark',
    name: '夸克',
    desc: '阿里 AI 搜索与超级助手，快速查找行业信息、市场数据并智能总结。',
    url: 'https://www.quark.cn/',
    category: 'efficiency',
    tags: ['AI搜索', '阿里'],
    isHot: true,
    isDomestic: true,
    letter: '夸',
    color: 'from-blue-600 to-indigo-400',
  },
  {
    id: 'metaso',
    name: '秘塔AI搜索',
    desc: '无广告、有来源、能总结的专业 AI 搜索，适合市场调研与情报收集。',
    url: 'https://metaso.cn/',
    category: 'efficiency',
    tags: ['AI搜索', '无广告', '免费'],
    isHot: true,
    isFree: true,
    isDomestic: true,
    letter: '秘',
    color: 'from-teal-600 to-emerald-400',
  },
  {
    id: '360-ai-search',
    name: '360AI搜索',
    desc: '360 出品的 AI 搜索引擎，提供答案总结与多轮追问，查询更高效。',
    url: 'https://www.so.com/',
    category: 'efficiency',
    tags: ['AI搜索', '答案总结'],
    isFree: true,
    isDomestic: true,
    letter: '3',
    color: 'from-green-600 to-emerald-400',
  },
  {
    id: 'dingtalk-ai-sheet',
    name: '钉钉AI表格',
    desc: '用自然语言操作表格，生成图表、数据透视表并进行对话式数据分析。',
    url: 'https://www.dingtalk.com/',
    category: 'efficiency',
    tags: ['智能表格', '数据分析'],
    isDomestic: true,
    letter: '表',
    color: 'from-sky-700 to-blue-500',
  },
  {
    id: 'baidu-office-agent',
    name: '文库 Office Agent',
    desc: '百度文库网盘的智能表格与文档助手，对话即可处理与分析数据。',
    url: 'https://wenku.baidu.com/',
    category: 'efficiency',
    tags: ['表格智能', '文档'],
    isDomestic: true,
    letter: '度',
    color: 'from-blue-600 to-sky-400',
  },

  // ── IT 与低代码 ──
  {
    id: 'yida',
    name: '钉钉宜搭',
    desc: '零代码拖拽搭建内部业务应用与审批流程，快速满足定制化需求。',
    url: 'https://www.aliwork.com/',
    category: 'dev',
    tags: ['低代码', '搭应用'],
    isDomestic: true,
    letter: '宜',
    color: 'from-sky-600 to-blue-500',
  },
  {
    id: 'miaoda',
    name: '百度秒哒',
    desc: '用自然语言描述需求即可生成应用，无门槛的 AI 低代码开发平台。',
    url: 'https://miaoda.baidu.com/',
    category: 'dev',
    tags: ['低代码', '自然语言开发'],
    isHot: true,
    isDomestic: true,
    letter: '哒',
    color: 'from-blue-600 to-indigo-400',
  },
  {
    id: 'weda',
    name: '腾讯云微搭',
    desc: '可视化 + AI 的低代码平台，快速构建小程序、H5 与内部管理系统。',
    url: 'https://cloud.tencent.com/product/lowcode',
    category: 'dev',
    tags: ['低代码', '可视化'],
    isDomestic: true,
    letter: '微',
    color: 'from-blue-700 to-cyan-500',
  },
  {
    id: 'yonyou-bip',
    name: '用友BIP',
    desc: '企业级数智化平台，AI 赋能财务、供应链与人力的低代码扩展。',
    url: 'https://www.yonyou.com/',
    category: 'dev',
    tags: ['企业级', '低代码'],
    isDomestic: true,
    letter: '友',
    color: 'from-rose-600 to-red-400',
  },
  {
    id: 'comate',
    name: '文心快码',
    desc: '百度 Comate AI 编码助手，智能补全、注释生成与代码调试。',
    url: 'https://comate.baidu.com/',
    category: 'dev',
    tags: ['AI编码', '百度Comate'],
    isHot: true,
    isDomestic: true,
    letter: '码',
    color: 'from-blue-600 to-sky-400',
  },
  {
    id: 'lingma',
    name: '通义灵码',
    desc: '阿里 AI 编程助手，支持行级补全、单元测试生成与研发问答。',
    url: 'https://tongyi.aliyun.com/lingma',
    category: 'dev',
    tags: ['AI编码', '阿里'],
    isHot: true,
    isDomestic: true,
    letter: '灵',
    color: 'from-purple-600 to-violet-400',
  },
  {
    id: 'marscode',
    name: 'MarsCode',
    desc: '字节豆包 MarsCode，免费的 AI 编程助手与云端开发环境。',
    url: 'https://www.marscode.cn/',
    category: 'dev',
    tags: ['AI编码', '字节', '免费'],
    isFree: true,
    isDomestic: true,
    letter: 'M',
    color: 'from-violet-700 to-indigo-500',
  },

  // ── 专业业务支撑（销售 / 客服 / 人力 / 财税 / 法务） ──
  {
    id: 'neocrm',
    name: '销售易 NeoAgent',
    desc: 'AI 原生 CRM，自动化销售过程并生成销售分析，跟踪商机与客户沟通。',
    url: 'https://www.xiaoshouyi.com/',
    category: 'business',
    tags: ['AI CRM', '销售自动化'],
    isHot: true,
    isDomestic: true,
    letter: '销',
    color: 'from-blue-600 to-indigo-400',
  },
  {
    id: 'fxiaoke',
    name: '纷享销客',
    desc: '连接型 CRM，ShareAI 辅助客户管理、销售协同与数据洞察。',
    url: 'https://www.fxiaoke.com/',
    category: 'business',
    tags: ['CRM', 'ShareAI'],
    isDomestic: true,
    letter: '纷',
    color: 'from-orange-600 to-red-400',
  },
  {
    id: 'dianxiaomi',
    name: '阿里店小蜜',
    desc: '电商智能客服，自动回复咨询、处理订单售后，降低人力成本。',
    url: 'https://www.aliyun.com/',
    category: 'business',
    tags: ['AI客服', '电商'],
    isDomestic: true,
    letter: '蜜',
    color: 'from-orange-500 to-amber-400',
  },
  {
    id: 'ronglian',
    name: '容联云',
    desc: '智慧联络平台，融合语音、IM 与 AI 客服，提升服务响应速度。',
    url: 'https://www.rongcloud.cn/',
    category: 'business',
    tags: ['AI客服', '联络平台'],
    isDomestic: true,
    letter: '容',
    color: 'from-indigo-600 to-blue-400',
  },
  {
    id: 'moka',
    name: 'Moka AI',
    desc: 'AI 招聘与人事系统，简历筛选、AI 面试与入职流程自动化。',
    url: 'https://www.mokahr.com/',
    category: 'business',
    tags: ['AI招聘', '人事'],
    isHot: true,
    isDomestic: true,
    letter: 'M',
    color: 'from-emerald-600 to-teal-400',
  },
  {
    id: '17win',
    name: '税友亿企赢',
    desc: '财税智能体，智能记账、自动报税、发票管理与财务分析一站搞定。',
    url: 'https://www.17win.com/',
    category: 'business',
    tags: ['AI财税', '智能记账'],
    isDomestic: true,
    letter: '税',
    color: 'from-green-600 to-emerald-400',
  },
  {
    id: 'kingdee-ai',
    name: '金蝶 AI ERP',
    desc: 'AI 赋能的 ERP 系统，覆盖财务、供应链与经营分析的智能处理。',
    url: 'https://www.kingdee.com/',
    category: 'business',
    tags: ['AI ERP', '财务'],
    isDomestic: true,
    letter: '蝶',
    color: 'from-blue-700 to-indigo-500',
  },

  // ── 补充：文档与写作 ──
  {
    id: 'aippt',
    name: 'AiPPT',
    desc: '一键将想法或文档生成专业 PPT，提供海量专业模板、AI 排版、在线编辑和多端访问。',
    url: 'https://www.aippt.cn',
    category: 'content',
    tags: ['AI PPT', '一键生成', '模板'],
    isDomestic: true,
    letter: 'A',
    color: 'from-blue-600 to-indigo-500',
  },
  {
    id: 'gaoding-ppt',
    name: '稿定PPT',
    desc: '稿定设计旗下的专业在线 PPT 工具，主打海量精美模板和素材。',
    url: 'https://ppt.gaoding.com',
    category: 'content',
    tags: ['AI PPT', '精美模板'],
    isDomestic: true,
    letter: '稿',
    color: 'from-rose-600 to-pink-500',
  },
  {
    id: 'ibiling',
    name: '笔灵AI写作',
    desc: '面向论文、公文、小说等专业人士的一站式 AI 写作平台。',
    url: 'https://ibiling.cn',
    category: 'content',
    tags: ['AI写作', '论文', '公文'],
    isDomestic: true,
    letter: '笔',
    color: 'from-emerald-600 to-teal-500',
  },

  // ── 补充：设计与视频 ──
  {
    id: 'boardmix',
    name: 'boardmix博思白板',
    desc: 'AI 加持的在线协作白板，可一键生成思维导图、流程图与各类可视化图表。',
    url: 'https://boardmix.cn',
    category: 'creative',
    tags: ['AI白板', '思维导图', '协作'],
    isDomestic: true,
    letter: 'B',
    color: 'from-violet-600 to-purple-500',
  },
  {
    id: 'napkin',
    name: 'Napkin AI',
    desc: '能将文本内容直接转换为信息图、流程图、思维导图等视觉内容。',
    url: 'https://www.napkin.ai',
    category: 'creative',
    tags: ['信息图', '流程图', '可视化'],
    letter: 'N',
    color: 'from-amber-500 to-orange-400',
  },
  {
    id: 'chuangkit',
    name: '创客贴',
    desc: '易用的在线设计平台，提供海量模板和素材，支持 AI 智能设计。',
    url: 'https://www.chuangkit.com',
    category: 'creative',
    tags: ['在线设计', '模板', 'AI设计'],
    isDomestic: true,
    letter: '创',
    color: 'from-fuchsia-600 to-pink-500',
  },
  {
    id: 'hailuo',
    name: '海螺AI',
    desc: 'MiniMax 推出的 AI 视频创作平台，能将文字或图片生成高质量视频。',
    url: 'https://hailuoai.com',
    category: 'creative',
    tags: ['AI视频', 'MiniMax', '文生视频'],
    isDomestic: true,
    letter: '海',
    color: 'from-cyan-600 to-blue-500',
  },
  {
    id: 'ttson',
    name: '海豚配音',
    desc: '提供文本转语音服务，支持多种声音风格和语言。',
    url: 'https://www.ttson.cn',
    category: 'creative',
    tags: ['TTS', '配音', '语音合成'],
    isDomestic: true,
    letter: '配',
    color: 'from-sky-600 to-blue-400',
  },
  {
    id: 'kezign',
    name: '可赞AI',
    desc: 'AI 驱动的办公可视化工具，可将文字一键转化为图表、公众号图文等。',
    url: 'https://kezign.cn',
    category: 'creative',
    tags: ['可视化', '图表', '办公'],
    isDomestic: true,
    letter: '赞',
    color: 'from-indigo-600 to-violet-500',
  },

  // ── 补充：综合办公协同 ──
  {
    id: 'lingxi',
    name: 'WPS灵犀',
    desc: '金山办公与 DeepSeek 联合打造的 AI 办公助手，深度接入 WPS 和文档。',
    url: 'https://lingxi.wps.cn',
    category: 'collab',
    tags: ['AI办公', 'DeepSeek', 'WPS'],
    isDomestic: true,
    letter: '灵',
    color: 'from-red-700 to-rose-600',
  },

  // ── 补充：会议与效率 ──
  {
    id: 'feishu-miaoji',
    name: '飞书妙记',
    desc: '飞书内置的智能会议记录工具，可将语音自动转录为文字，并生成待办。',
    url: 'https://www.feishu.cn',
    category: 'efficiency',
    tags: ['语音转写', '会议纪要', '待办'],
    isDomestic: true,
    letter: '妙',
    color: 'from-blue-600 to-cyan-500',
  },

  // ── 补充：IT 与低代码 ──
  {
    id: 'n8n',
    name: 'n8n',
    desc: '一个强大的开源工作流自动化平台，尤其适合构建 AI Agent 和工作流程。',
    url: 'https://n8n.io',
    category: 'dev',
    tags: ['开源', '工作流', 'AI Agent'],
    isFree: true,
    letter: 'n',
    color: 'from-orange-600 to-amber-500',
  },
  {
    id: 'openclaw',
    name: 'Clawdbot (OpenClaw)',
    desc: '一个开源的 AI 智能体框架，经历几次更名后统一为 OpenClaw。',
    url: 'https://openclaw.org',
    category: 'dev',
    tags: ['开源', 'AI框架', '智能体'],
    isFree: true,
    letter: 'C',
    color: 'from-slate-600 to-gray-500',
  },

  // ── 补充：专业业务支撑 ──
  {
    id: 'alphashop',
    name: 'AI电商工具 (AlphaShop)',
    desc: '「遨虾」由阿里巴巴 1688 推出的跨境电商 AI 智能体。',
    url: 'https://alphashop.cn',
    category: 'business',
    tags: ['跨境电商', 'AI智能体', '1688'],
    isDomestic: true,
    letter: '遨',
    color: 'from-orange-500 to-amber-400',
  },

  // ── 补充：综合办公协同 ──
  {
    id: 'feishu-project',
    name: '飞书项目',
    desc: '飞书内置的项目管理工具，支持 AI 辅助任务拆解、进度跟踪与报告生成。',
    url: 'https://www.feishu.cn/product/project',
    category: 'collab',
    tags: ['项目管理', '进度跟踪'],
    isDomestic: true,
    letter: '项',
    color: 'from-blue-600 to-indigo-500',
  },

  // ── 补充：设计与视频 ──
  {
    id: 'figma',
    name: 'Figma',
    desc: '全球主流的在线 UI/UX 设计工具，拥有丰富的 AI 插件生态扩展能力。',
    url: 'https://www.figma.com/',
    category: 'creative',
    tags: ['UI/UX设计', 'AI插件', '协作'],
    letter: 'F',
    color: 'from-purple-600 to-violet-500',
  },
  {
    id: 'jishi-design',
    name: '即时设计 AI',
    desc: '国产在线 UI 设计工具，支持 AI 生成界面、智能排版与实时协作。',
    url: 'https://js.design/',
    category: 'creative',
    tags: ['UI设计', 'AI生成', '国产'],
    isDomestic: true,
    letter: '即',
    color: 'from-blue-600 to-sky-400',
  },
  {
    id: 'wondershare-media',
    name: '万兴超媒',
    desc: '万兴科技旗下的 AI 视频生成平台，支持数字人播报与智能剪辑。',
    url: 'https://www.wondershare.cn/',
    category: 'creative',
    tags: ['AI视频', '数字人', '剪辑'],
    isDomestic: true,
    letter: '超',
    color: 'from-red-600 to-orange-500',
  },
  {
    id: 'pai-video',
    name: '拍我AI',
    desc: 'PixVerse 国内版，AI 视频生成平台，支持文生视频与图生视频。',
    url: 'https://pai.video/',
    category: 'creative',
    tags: ['AI视频', '文生视频', 'PixVerse'],
    isDomestic: true,
    letter: '拍',
    color: 'from-pink-600 to-rose-500',
  },

  // ── 补充：专业业务支撑 ──
  {
    id: 'zhichi',
    name: '智齿科技',
    desc: '智能客服与呼叫中心解决方案，覆盖售前咨询、售后支持全场景。',
    url: 'https://www.zhichi.com/',
    category: 'business',
    tags: ['智能客服', '呼叫中心'],
    isDomestic: true,
    letter: '智',
    color: 'from-blue-600 to-indigo-400',
  },
  {
    id: 'meiqia',
    name: '美洽',
    desc: '一体化智能客服平台，支持多渠道接入、AI 自动回复与数据分析。',
    url: 'https://www.meiqia.com/',
    category: 'business',
    tags: ['智能客服', '多渠道'],
    isDomestic: true,
    letter: '美',
    color: 'from-emerald-600 to-teal-400',
  },
  {
    id: '51job',
    name: '51Job 企业版',
    desc: '前程无忧企业版，AI 辅助简历筛选、职位发布与招聘全流程管理。',
    url: 'https://www.51job.com/',
    category: 'business',
    tags: ['招聘', '前程无忧'],
    isDomestic: true,
    letter: '5',
    color: 'from-orange-600 to-amber-500',
  },
  {
    id: 'nowcoder',
    name: '牛客招聘',
    desc: '技术类招聘平台，覆盖校招、社招，提供笔试面试与 AI 人才筛选。',
    url: 'https://www.nowcoder.com/',
    category: 'business',
    tags: ['技术招聘', '校招', '笔试面试'],
    isDomestic: true,
    letter: '牛',
    color: 'from-green-600 to-emerald-500',
  },
  {
    id: 'ailegal',
    name: '百度法行宝',
    desc: '百度出品的 AI 法律助手，提供法律咨询、合同审查与文书生成。',
    url: 'https://ailegal.baidu.com/',
    category: 'business',
    tags: ['AI法务', '法律咨询'],
    isDomestic: true,
    letter: '法',
    color: 'from-blue-700 to-indigo-500',
  },
  {
    id: 'delilegal',
    name: '得理法搜',
    desc: 'AI 法律检索与知识管理平台，支持案例搜索、法规查询与智能分析。',
    url: 'https://data.delilegal.com/',
    category: 'business',
    tags: ['法律检索', '案例分析'],
    isDomestic: true,
    letter: '理',
    color: 'from-slate-600 to-gray-500',
  },
]

export default function AINavigationPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeCategory, setActiveL2Category] = useState('all')

  // 根据分类与检索进行联想过滤
  const filteredTools = useMemo(() => {
    return AI_TOOLS_DB.filter((tool) => {
      const matchCat = activeCategory === 'all' || tool.category === activeCategory
      const query = searchQuery.trim().toLowerCase()
      if (!query) return matchCat

      const matchName = tool.name.toLowerCase().includes(query)
      const matchDesc = tool.desc.toLowerCase().includes(query)
      const matchTags = tool.tags.some(t => t.toLowerCase().includes(query))
      return matchCat && (matchName || matchDesc || matchTags)
    })
  }, [activeCategory, searchQuery])

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto p-4 md:p-6 space-y-6">
        {/* Header Hero Banner */}
        <div className="relative rounded-2xl overflow-hidden glass-card p-6 md:p-8 flex flex-col md:flex-row md:items-center justify-between gap-6 border border-white/5 bg-gradient-to-br from-white/[0.03] to-transparent">
          <div className="absolute right-0 top-0 w-80 h-80 bg-accent/10 blur-3xl rounded-full -mr-20 -mt-20 pointer-events-none" />
          <div className="space-y-2 relative z-10">
            <h1 className="text-2xl md:text-3xl font-extrabold text-white tracking-tight flex items-center gap-2">
              <Compass className="w-7 h-7 text-accent animate-spin-slow" />
              AI 工具导航
            </h1>
            <p className="text-sm text-white/50 max-w-xl">
              精选贴合国内中小企业业务场景的 AI 工具，覆盖办公协同、文档创作、营销设计、会议效率、低代码开发与销售、客服、财税等环节，助力企业降本增效、一键直达。
            </p>
          </div>

          {/* Search Bar */}
          <div className="relative w-full md:w-80 flex-shrink-0 z-10">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4.5 h-4.5 text-white/30" />
            <input
              type="text"
              placeholder="搜索 AI 工具、功能或场景..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-white/10 bg-white/[0.04] text-sm text-white placeholder:text-white/20 hover:border-white/25 focus:border-accent focus:bg-white/[0.06] focus:outline-none transition-all shadow-inner"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-white/30 hover:text-white/60 transition-colors"
              >
                清除
              </button>
            )}
          </div>
        </div>

        {/* Category Tabs */}
        <div className="flex items-center gap-2 overflow-x-auto pb-1 -mx-2 px-2 scrollbar-none">
          {CATEGORIES.map((cat) => {
            const IconComponent = cat.icon
            const isActive = activeCategory === cat.id
            const count = cat.id === 'all'
              ? AI_TOOLS_DB.length
              : AI_TOOLS_DB.filter(t => t.category === cat.id).length

            return (
              <button
                key={cat.id}
                onClick={() => setActiveL2Category(cat.id)}
                className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 whitespace-nowrap flex-shrink-0 ${
                  isActive
                    ? 'bg-accent text-white shadow-lg shadow-accent/20'
                    : 'text-white/40 hover:text-white/70 hover:bg-white/[0.03]'
                }`}
              >
                <IconComponent className="w-4 h-4" />
                <span>{cat.label}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                  isActive ? 'bg-white/20 text-white' : 'bg-white/5 text-white/30'
                }`}>
                  {count}
                </span>
              </button>
            )
          })}
        </div>

        {/* Tools Grid layout */}
        <AnimatePresence mode="popLayout">
          {filteredTools.length > 0 ? (
            <motion.div
              layout
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
            >
              {filteredTools.map((tool) => (
                <motion.div
                  key={tool.id}
                  layout
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.25 }}
                  whileHover={{ y: -4, transition: { duration: 0.15 } }}
                  className="group relative flex flex-col justify-between p-5 rounded-2xl border border-white/5 bg-gradient-to-b from-white/[0.03] to-white/[0.01] hover:border-white/10 hover:from-white/[0.05] hover:to-white/[0.02] shadow-sm transition-all duration-200 cursor-pointer overflow-hidden"
                  onClick={() => window.open(tool.url, '_blank', 'noopener,noreferrer')}
                >
                  {/* Subtle Background Glow for Hot tools */}
                  {tool.isHot && (
                    <div className="absolute top-0 right-0 w-16 h-16 bg-accent/5 blur-xl rounded-full group-hover:bg-accent/10 transition-colors pointer-events-none" />
                  )}

                  {/* Top: Info Section */}
                  <div className="space-y-3.5">
                    {/* Brand Meta */}
                    <div className="flex items-center justify-between">
                      {/* Logo avatar with gradient */}
                      <div className={`w-11 h-11 rounded-xl bg-gradient-to-br ${tool.color} flex items-center justify-center font-bold text-white text-lg shadow-md`}>
                        {tool.letter}
                      </div>

                      {/* Hot/Domestic Badges */}
                      <div className="flex items-center gap-1.5">
                        {tool.isHot && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20">
                            HOT
                          </span>
                        )}
                        {tool.isFree && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-sky-500/10 text-sky-400 border border-sky-500/20">
                            免费
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Name & Desc */}
                    <div className="space-y-1">
                      <h3 className="text-base font-bold text-white group-hover:text-accent transition-colors flex items-center gap-1">
                        {tool.name}
                        <ArrowUpRight className="w-3.5 h-3.5 opacity-0 -translate-y-0.5 group-hover:opacity-100 group-hover:translate-x-0.5 group-hover:translate-y-0 transition-all text-accent" />
                      </h3>
                      <p className="text-xs text-white/40 leading-relaxed line-clamp-3">
                        {tool.desc}
                      </p>
                    </div>
                  </div>

                  {/* Bottom: Tags */}
                  <div className="pt-4 mt-4 border-t border-white/5 flex flex-wrap gap-1.5 items-center justify-between">
                    <div className="flex flex-wrap gap-1">
                      {tool.tags.slice(0, 2).map((tag, idx) => (
                        <span
                          key={idx}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 text-white/40 font-medium"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                    <span className="text-[11px] text-white/20 group-hover:text-accent font-medium flex items-center gap-0.5 transition-colors">
                      直达
                      <ChevronRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
                    </span>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="glass-card p-12 text-center max-w-sm mx-auto"
            >
              <div className="w-12 h-12 rounded-xl bg-white/5 flex items-center justify-center text-white/20 mx-auto mb-4">
                <Search className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">未找到匹配工具</h3>
              <p className="text-xs text-white/30 leading-relaxed">
                试试搜索其他关键词，或在上方切换不同分类寻找
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </AppLayout>
  )
}

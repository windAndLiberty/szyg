(() => {
  const messages = {
    'zh-CN': {
      brand: '小妤 AI',
      title: '小妤 AI｜专业数字员工',
      description: '小妤 AI 是一位可扩展的本地数字员工，能够理解目标、调用技能、使用电脑并持续推进工作。',
      homeAria: '小妤 AI 首页',
      navCapabilities: '核心能力', navSupport: '支持中心', navMeet: '认识小妤', navStore: 'Windows 商店',
      eyebrow: '你的本地 AI 数字员工', heroLineOne: '把复杂工作，', heroLineTwo: '交给小妤。',
      heroLead: '不只是回答问题，而是理解目标、调用技能、使用电脑，把一项工作持续推进到结果。',
      primaryAction: '了解小妤的能力', supportAction: '获取使用支持',
      storeLabel: 'WINDOWS 版', storeDownload: '从 Microsoft Store 下载', storeDownloadAria: '在 Microsoft Store 下载小妤 AI',
      trustLocal: '本地运行', trustApproval: '关键操作确认', trustTraceable: '过程清晰可追踪',
      stageAria: '小妤 AI 数字员工形象与能力', imageAlt: '小妤 AI 在数字化指挥中心协助工作的形象',
      workStatus: '工作状态', onStandby: '随时待命', capabilityTitle: '能力，不止于对话',
      capabilityLead: '像一位真正的员工一样理解、执行与交付。',
      capabilityUnderstand: '目标理解', capabilityPlan: '任务规划', capabilitySkills: '技能调用',
      capabilityComputer: '电脑操作', capabilityCreate: '内容创作', capabilityOrganize: '资料整理',
      capabilitySchedule: '定时执行', capabilityDeliver: '结果交付', methodTitle: '一个目标，完整推进',
      stepUnderstand: '理解任务', stepUnderstandBody: '梳理目标、资料与完成标准。',
      stepOrchestrate: '调度能力', stepOrchestrateBody: '选择合适技能与工具协同执行。',
      stepConfirm: '确认关键动作', stepConfirmBody: '在发布等重要节点等待你的确认。',
      stepDeliver: '交付结果', stepDeliverBody: '沉淀过程、产物与下一步建议。',
      footerTagline: '专业、可靠、可扩展的数字员工', privacy: '隐私政策', terms: '用户协议', deleteAccount: '账号注销',
    },
    'en-US': {
      brand: 'Yuna AI',
      title: 'Yuna AI | Your Digital Employee',
      description: 'Yuna AI is an extensible local digital employee that understands goals, uses skills and your computer, and keeps work moving through delivery.',
      homeAria: 'Yuna AI home',
      navCapabilities: 'Capabilities', navSupport: 'Support', navMeet: 'Meet Yuna', navStore: 'Microsoft Store',
      eyebrow: 'YOUR LOCAL AI DIGITAL EMPLOYEE', heroLineOne: 'Delegate complex work,', heroLineTwo: 'to Yuna.',
      heroLead: 'More than answers: Yuna understands the goal, applies the right skills, works on your computer, and keeps the job moving to completion.',
      primaryAction: 'Explore Yuna\'s capabilities', supportAction: 'Get support',
      storeLabel: 'FOR WINDOWS', storeDownload: 'Get it from Microsoft Store', storeDownloadAria: 'Download Yuna AI from Microsoft Store',
      trustLocal: 'Runs locally', trustApproval: 'Confirms critical actions', trustTraceable: 'Clear, traceable progress',
      stageAria: 'Yuna AI digital employee and capabilities', imageAlt: 'Yuna AI working in a digital command center',
      workStatus: 'WORK STATUS', onStandby: 'Ready when you are', capabilityTitle: 'More than conversation',
      capabilityLead: 'Understands, executes, and delivers like a real team member.',
      capabilityUnderstand: 'Goal Clarity', capabilityPlan: 'Task Planning', capabilitySkills: 'Skill Use',
      capabilityComputer: 'Computer Use', capabilityCreate: 'Content Creation', capabilityOrganize: 'Knowledge Work',
      capabilitySchedule: 'Scheduled Work', capabilityDeliver: 'Result Delivery', methodTitle: 'One goal, carried through',
      stepUnderstand: 'Understand the task', stepUnderstandBody: 'Clarify goals, inputs, and the definition of done.',
      stepOrchestrate: 'Orchestrate the work', stepOrchestrateBody: 'Coordinate the right skills and tools for the job.',
      stepConfirm: 'Confirm critical actions', stepConfirmBody: 'Pause for your approval before publishing or other consequential steps.',
      stepDeliver: 'Deliver the result', stepDeliverBody: 'Preserve the process, outputs, and recommended next steps.',
      footerTagline: 'A professional, reliable, extensible digital employee', privacy: 'Privacy', terms: 'Terms', deleteAccount: 'Delete account',
    },
  }

  const storageKey = 'yuna-site-locale'
  const queryLocale = new URLSearchParams(window.location.search).get('lang')
  let locale = queryLocale === 'en' || queryLocale === 'en-US'
    ? 'en-US'
    : queryLocale === 'zh' || queryLocale === 'zh-CN'
      ? 'zh-CN'
      : window.localStorage.getItem(storageKey) || (navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en-US')

  function apply(nextLocale) {
    locale = nextLocale === 'en-US' ? 'en-US' : 'zh-CN'
    const copy = messages[locale]
    document.documentElement.lang = locale
    document.title = copy.title
    document.querySelector('meta[name="description"]')?.setAttribute('content', copy.description)
    document.querySelectorAll('[data-i18n]').forEach((element) => {
      const value = copy[element.dataset.i18n]
      if (value) element.textContent = value
    })
    document.querySelectorAll('[data-i18n-aria]').forEach((element) => {
      const value = copy[element.dataset.i18nAria]
      if (value) element.setAttribute('aria-label', value)
    })
    document.querySelectorAll('[data-i18n-alt]').forEach((element) => {
      const value = copy[element.dataset.i18nAlt]
      if (value) element.setAttribute('alt', value)
    })
    const toggle = document.getElementById('language-toggle')
    if (toggle) {
      toggle.textContent = locale === 'zh-CN' ? 'EN' : '中'
      toggle.setAttribute('aria-label', locale === 'zh-CN' ? 'Switch to English' : '切换为中文')
    }
    window.localStorage.setItem(storageKey, locale)
  }

  document.getElementById('language-toggle')?.addEventListener('click', () => {
    apply(locale === 'zh-CN' ? 'en-US' : 'zh-CN')
  })
  apply(locale)
})()

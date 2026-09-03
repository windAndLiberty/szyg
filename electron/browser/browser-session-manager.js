const { WebContentsView, session } = require('electron')

const DEFAULT_URL = 'about:blank'

function asHttpUrl(value) {
  const text = String(value || '').trim()
  if (!text) throw new Error('请提供要打开的网页地址')
  if (text === DEFAULT_URL) return DEFAULT_URL
  const candidate = /^https?:\/\//i.test(text) ? text : `https://${text}`
  const parsed = new URL(candidate)
  if (!['http:', 'https:'].includes(parsed.protocol)) throw new Error('只支持打开安全网页')
  return parsed.toString()
}

class BrowserSessionManager {
  constructor({ partition = 'persist:szyg-agent-browser', blockedOrigins = [] } = {}) {
    this.partition = partition
    this.blockedOrigins = new Set(blockedOrigins.filter(Boolean))
    this.hostWindow = null
    this.view = null
    this.attached = false
    this.visible = false
    this.bounds = { x: 0, y: 0, width: 0, height: 0 }
    this.owner = 'none'
    this.lastAction = ''
    this.sessionConfigured = false
  }

  setHostWindow(window) {
    this.hostWindow = window
    if (this.visible) this._attach()
  }

  _ensureView() {
    if (this.view && !this.view.webContents.isDestroyed()) return this.view
    const browserSession = session.fromPartition(this.partition, { cache: true })
    if (!this.sessionConfigured) {
      browserSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false))
      browserSession.on('will-download', (event, item) => {
        event.preventDefault()
        item.cancel()
        this.lastAction = '已阻止网页下载，如需文件请由你接管后处理'
        this._emitState({ error: this.lastAction })
      })
      this.sessionConfigured = true
    }
    this.view = new WebContentsView({
      webPreferences: {
        session: browserSession,
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        webSecurity: true,
        spellcheck: false,
        autoplayPolicy: 'document-user-activation-required',
      },
    })
    const contents = this.view.webContents
    contents.setWindowOpenHandler(({ url }) => {
      void this.navigate(url).catch(() => {})
      return { action: 'deny' }
    })
    contents.on('will-navigate', (event, url) => {
      try {
        this._assertAllowed(url)
      } catch (_) {
        event.preventDefault()
      }
    })
    contents.on('did-start-navigation', () => this._emitState())
    contents.on('did-navigate', () => this._emitState())
    contents.on('did-navigate-in-page', () => this._emitState())
    contents.on('page-title-updated', () => this._emitState())
    contents.on('did-finish-load', () => {
      if (contents.getURL() === DEFAULT_URL) {
        void contents.executeJavaScript("document.documentElement.style.background='#080C14';document.body.style.background='#080C14'").catch(() => {})
      }
      if (this.owner === 'agent') void this._setAgentCursor(true)
      this._emitState()
    })
    contents.on('did-fail-load', (_event, _code, description, url, isMainFrame) => {
      if (isMainFrame) this._emitState({ error: `网页未能打开：${description}`, url })
    })
    contents.on('render-process-gone', () => {
      this.view = null
      this.attached = false
      this._emitState({ error: '浏览器页面需要重新打开' })
    })
    void contents.loadURL(DEFAULT_URL)
    return this.view
  }

  _assertAllowed(value) {
    const url = asHttpUrl(value)
    const parsed = new URL(url)
    const hostname = parsed.hostname.toLowerCase()
    const isLoopback = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1'
    if (isLoopback || this.blockedOrigins.has(parsed.origin)) {
      throw new Error('不能在操作浏览器中打开领鹿员工自身页面')
    }
    return url
  }

  _attach() {
    const view = this._ensureView()
    if (!this.hostWindow || this.hostWindow.isDestroyed()) return
    if (!this.attached) {
      this.hostWindow.contentView.addChildView(view)
      this.attached = true
    }
    if (this.bounds.width > 0 && this.bounds.height > 0) view.setBounds(this.bounds)
  }

  _detach() {
    if (!this.attached || !this.hostWindow || this.hostWindow.isDestroyed() || !this.view) return
    try { this.hostWindow.contentView.removeChildView(this.view) } catch (_) {}
    this.attached = false
  }

  setVisible(visible) {
    this.visible = Boolean(visible)
    if (this.visible) this._attach()
    else this._detach()
    this._emitState()
    return this.state()
  }

  setBounds(bounds) {
    const next = {
      x: Math.max(0, Math.round(Number(bounds?.x) || 0)),
      y: Math.max(0, Math.round(Number(bounds?.y) || 0)),
      width: Math.max(0, Math.round(Number(bounds?.width) || 0)),
      height: Math.max(0, Math.round(Number(bounds?.height) || 0)),
    }
    this.bounds = next
    if (this.attached && this.view && next.width > 0 && next.height > 0) this.view.setBounds(next)
    return this.state()
  }

  state(extra = {}) {
    const contents = this.view && !this.view.webContents.isDestroyed() ? this.view.webContents : null
    return {
      available: true,
      visible: this.visible,
      owner: this.owner,
      url: contents?.getURL() || '',
      title: contents?.getTitle() || '',
      loading: Boolean(contents?.isLoading()),
      canGoBack: Boolean(contents?.navigationHistory?.canGoBack()),
      canGoForward: Boolean(contents?.navigationHistory?.canGoForward()),
      lastAction: this.lastAction,
      ...extra,
    }
  }

  _emitState(extra = {}) {
    if (!this.hostWindow || this.hostWindow.isDestroyed()) return
    this.hostWindow.webContents.send('szyg-browser-state', this.state(extra))
  }

  async navigate(value) {
    const url = this._assertAllowed(value)
    // Visibility is owned by BrowserWorkView. Navigation must not reopen a
    // native view that the user closed or attach it over an unrelated route.
    this._ensureView()
    this.lastAction = '正在打开网页'
    this.owner = 'agent'
    this._emitState()
    await this._ensureView().webContents.loadURL(url)
    await this._setAgentCursor(true)
    this.lastAction = '网页已打开'
    this._emitState()
    return this.state()
  }

  async observe() {
    const contents = this._ensureView().webContents
    const result = await contents.executeJavaScript(`(() => {
      const selectors = 'a[href],button,input,textarea,select,[role="button"],[role="link"],[contenteditable="true"],[tabindex]';
      const rows = [];
      let index = 0;
      for (const element of document.querySelectorAll(selectors)) {
        index += 1;
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        if (rect.width < 2 || rect.height < 2 || style.visibility === 'hidden' || style.display === 'none') continue;
        if (rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth) continue;
        const ref = element.dataset.szygRef || ('b' + index);
        element.dataset.szygRef = ref;
        const text = (element.innerText || element.value || element.getAttribute('aria-label') || element.getAttribute('placeholder') || '').trim().replace(/\\s+/g, ' ').slice(0, 160);
        rows.push({ ref, tag: element.tagName.toLowerCase(), role: element.getAttribute('role') || '', text, type: element.getAttribute('type') || '', name: element.getAttribute('name') || '', contenteditable: element.isContentEditable, disabled: Boolean(element.disabled || element.getAttribute('aria-disabled') === 'true'), x: Math.round(rect.left + rect.width / 2), y: Math.round(rect.top + rect.height / 2) });
        if (rows.length >= 160) break;
      }
      return { url: location.href, title: document.title, viewport: { width: innerWidth, height: innerHeight }, elements: rows };
    })()`)
    return result
  }

  async _target(ref) {
    const contents = this._ensureView().webContents
    return contents.executeJavaScript(`(() => {
      const ref = ${JSON.stringify(String(ref || ''))};
      const element = Array.from(document.querySelectorAll('[data-szyg-ref]')).find((node) => node.dataset.szygRef === ref);
      if (!element) return null;
      element.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
      const rect = element.getBoundingClientRect();
      return { x: Math.round(rect.left + rect.width / 2), y: Math.round(rect.top + rect.height / 2) };
    })()`)
  }

  async _moveCursor(x, y, click = false) {
    const contents = this._ensureView().webContents
    await contents.executeJavaScript(`(() => {
      let cursor = document.getElementById('__szyg_agent_cursor');
      if (!cursor) {
        cursor = document.createElement('div');
        cursor.id = '__szyg_agent_cursor';
        cursor.innerHTML = '<span></span>';
        Object.assign(cursor.style, { position:'fixed', zIndex:'2147483647', width:'20px', height:'20px', pointerEvents:'none', left:'0', top:'0', transform:'translate3d(-40px,-40px,0)', transition:'transform 180ms cubic-bezier(.2,.8,.2,1)' });
        Object.assign(cursor.firstElementChild.style, { display:'block', width:'12px', height:'12px', borderRadius:'50%', background:'#747BFF', border:'2px solid white', boxShadow:'0 0 0 5px rgba(116,123,255,.22), transition:'transform 120ms ease, box-shadow 120ms ease' });
        document.documentElement.appendChild(cursor);
      }
      cursor.style.display = 'block';
      cursor.style.transform = 'translate3d(' + (${Math.round(x)} - 6) + 'px,' + (${Math.round(y)} - 6) + 'px,0)';
      const dot = cursor.firstElementChild;
      if (${click ? 'true' : 'false'}) {
        dot.style.transform = 'scale(.72)'; dot.style.boxShadow = '0 0 0 12px rgba(116,123,255,.08)';
        setTimeout(() => { dot.style.transform = 'scale(1)'; dot.style.boxShadow = '0 0 0 5px rgba(116,123,255,.22)'; }, 150);
      }
    })()`)
  }

  async _setAgentCursor(enabled) {
    if (!this.view || this.view.webContents.isDestroyed()) return
    await this.view.webContents.executeJavaScript(`(() => {
      const styleId = '__szyg_agent_cursor_style';
      let style = document.getElementById(styleId);
      if (${enabled ? 'true' : 'false'}) {
        if (!style) { style = document.createElement('style'); style.id = styleId; style.textContent = 'html.__szyg_agent_active, html.__szyg_agent_active * { cursor: none !important; }'; document.documentElement.appendChild(style); }
        document.documentElement.classList.add('__szyg_agent_active');
      } else {
        document.documentElement.classList.remove('__szyg_agent_active');
        document.getElementById('__szyg_agent_cursor')?.remove();
      }
    })()`, true).catch(() => {})
  }

  async click(ref) {
    this.owner = 'agent'
    await this._setAgentCursor(true)
    const point = await this._target(ref)
    if (!point) throw new Error('页面已经变化，请重新观察后再点击')
    await this._moveCursor(point.x, point.y, true)
    const contents = this._ensureView().webContents
    contents.focus()
    contents.sendInputEvent({ type: 'mouseMove', x: point.x, y: point.y })
    contents.sendInputEvent({ type: 'mouseDown', x: point.x, y: point.y, button: 'left', clickCount: 1 })
    contents.sendInputEvent({ type: 'mouseUp', x: point.x, y: point.y, button: 'left', clickCount: 1 })
    this.lastAction = '已点击页面内容'
    this._emitState()
    return this.state()
  }

  async type(ref, text, clear = true) {
    this.owner = 'agent'
    await this._setAgentCursor(true)
    const point = await this._target(ref)
    if (!point) throw new Error('页面已经变化，请重新观察后再填写')
    await this._moveCursor(point.x, point.y, true)
    const contents = this._ensureView().webContents
    await contents.executeJavaScript(`(() => { const ref=${JSON.stringify(String(ref || ''))}; const el=Array.from(document.querySelectorAll('[data-szyg-ref]')).find((node)=>node.dataset.szygRef===ref); if(el) el.focus(); })()`)
    if (clear) {
      contents.sendInputEvent({ type: 'keyDown', keyCode: 'A', modifiers: ['control'] })
      contents.sendInputEvent({ type: 'keyUp', keyCode: 'A', modifiers: ['control'] })
    }
    contents.insertText(String(text || ''))
    this.lastAction = '已填写内容'
    this._emitState()
    return this.state()
  }

  async press(key = 'Enter') {
    this.owner = 'agent'
    await this._setAgentCursor(true)
    const contents = this._ensureView().webContents
    contents.focus()
    const keyCode = String(key || 'Enter')
    contents.sendInputEvent({ type: 'keyDown', keyCode })
    contents.sendInputEvent({ type: 'keyUp', keyCode })
    this.lastAction = keyCode.toLowerCase() === 'enter' ? '已提交问题' : '已操作网页键盘'
    this._emitState()
    return this.state()
  }

  async read() {
    const contents = this._ensureView().webContents
    return contents.executeJavaScript(`(() => {
      const normalize = (value, limit = 30000) => String(value || '').replace(/\\s+/g, ' ').trim().slice(0, limit);
      const normalizeText = (value, limit = 30000) => String(value || '')
        .replace(/\\r/g, '')
        .split('\\n')
        .map((line) => line.replace(/[\\t ]+/g, ' ').trim())
        .join('\\n')
        .replace(/\\n{3,}/g, '\\n\\n')
        .trim()
        .slice(0, limit);
      const linkRows = (root) => Array.from(root.querySelectorAll?.('a[href]') || []).map((anchor) => ({
        url: anchor.href || '', title: normalize(anchor.getAttribute('title') || anchor.innerText, 300), text: normalize(anchor.innerText, 300)
      })).filter((row, index, rows) => row.url && rows.findIndex((item) => item.url === row.url) === index).slice(0, 80);
      const selectors = [
        '[data-message-author-role]', '[data-testid*="answer"]', '[data-testid*="response"]',
        'model-response', 'message-content', '.response-content', 'article', '[role="article"]',
        'main [class*="markdown"]', 'main [class*="Markdown"]', 'main [class*="answer"]',
        'main [class*="response"]', 'main [class*="message-content"]',
        'main [class*="message_content"]', 'main [class*="markdown-body"]',
        'main .prose', '.ds-markdown', '.flow-markdown-body'
      ];
      const nodes = Array.from(document.querySelectorAll(selectors.join(',')));
      const blocks = [];
      const seen = new Set();
      for (const node of nodes) {
        const text = normalizeText(node.innerText || node.textContent, 16000);
        if (text.length < 2 || seen.has(text)) continue;
        seen.add(text);
        blocks.push({
          text,
          author: node.getAttribute('data-message-author-role') || node.closest('[data-message-author-role]')?.getAttribute('data-message-author-role') || '',
          tag: node.tagName.toLowerCase(),
          class_name: normalize(node.className, 240),
          links: linkRows(node),
        });
        if (blocks.length >= 60) break;
      }
      const root = document.querySelector('main') || document.body;
      const bodyText = normalizeText(root?.innerText || document.body?.innerText || '', 60000);
      const composer = Array.from(document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]')).some((node) => {
        const rect = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        return rect.width > 2 && rect.height > 2 && style.display !== 'none' && style.visibility !== 'hidden' && !node.disabled;
      });
      const busy = Boolean(document.querySelector('[aria-busy="true"],button[aria-label*="Stop" i],button[aria-label*="停止"],button[data-testid*="stop"]'));
      return {
        url: location.href,
        title: document.title,
        body_text: bodyText,
        content_blocks: blocks,
        links: linkRows(root),
        composer_available: composer,
        busy,
        auth_hint: /(?:登录|登入|验证码|扫码登录|sign in|log in|verify you are human|captcha)/i.test(bodyText),
      };
    })()`)
  }

  async scroll(deltaY = 600) {
    this.owner = 'agent'
    await this._setAgentCursor(true)
    const contents = this._ensureView().webContents
    contents.focus()
    contents.sendInputEvent({ type: 'mouseWheel', x: Math.max(1, Math.round(this.bounds.width / 2)), y: Math.max(1, Math.round(this.bounds.height / 2)), deltaY: Math.round(Number(deltaY) || 600), deltaX: 0 })
    this.lastAction = deltaY < 0 ? '正在向上浏览' : '正在向下浏览'
    this._emitState()
    return this.state()
  }

  async back() {
    const history = this._ensureView().webContents.navigationHistory
    if (history.canGoBack()) history.goBack()
    return this.state()
  }

  async forward() {
    const history = this._ensureView().webContents.navigationHistory
    if (history.canGoForward()) history.goForward()
    return this.state()
  }

  async refresh() {
    this._ensureView().webContents.reload()
    return this.state()
  }

  async takeover() {
    this.owner = 'user'
    await this._setAgentCursor(false)
    this.lastAction = '浏览器已交给你操作'
    this._emitState()
    return this.state()
  }

  async resume() {
    this.owner = 'agent'
    await this._setAgentCursor(true)
    this.lastAction = '超级员工已继续操作'
    this._emitState()
    return this.state()
  }

  async stop() {
    this.owner = 'none'
    await this._setAgentCursor(false)
    this.lastAction = '操作已停止'
    this._emitState()
    return this.state()
  }

  async action(payload = {}) {
    const action = String(payload.action || '').trim().toLowerCase()
    if (this.owner === 'user' && !['state', 'resume', 'takeover', 'stop'].includes(action)) {
      throw new Error('用户正在操作浏览器，请等待用户点击继续')
    }
    if (action === 'open' || action === 'navigate') return this.navigate(payload.url)
    if (action === 'observe') return this.observe()
    if (action === 'read') return this.read()
    if (action === 'click') return this.click(payload.ref)
    if (action === 'type') return this.type(payload.ref, payload.text, payload.clear !== false)
    if (action === 'press') return this.press(payload.key)
    if (action === 'scroll') return this.scroll(payload.delta_y)
    if (action === 'back') return this.back()
    if (action === 'forward') return this.forward()
    if (action === 'refresh') return this.refresh()
    if (action === 'takeover') return this.takeover()
    if (action === 'resume') return this.resume()
    if (action === 'stop') return this.stop()
    if (action === 'state') return this.state()
    throw new Error('不支持的浏览器操作')
  }

  destroy() {
    this._detach()
    if (this.view && !this.view.webContents.isDestroyed()) this.view.webContents.close()
    this.view = null
  }
}

module.exports = { BrowserSessionManager }

const path = require('path')

const repoRoot = path.resolve(__dirname, '..', '..', '..')
const defaultTerminatorDir = path.join(repoRoot, 'external', 'terminator-main')
const terminatorDir = process.env.SZYG_TERMINATOR_DIR || defaultTerminatorDir
const nodePackageDir = path.join(terminatorDir, 'packages', 'terminator-nodejs')

function loadSdk() {
  return require(path.join(nodePackageDir, 'index.js'))
}

function elementToJson(element) {
  if (!element) return {}
  let attrs = {}
  try { attrs = element.attributes ? element.attributes() : {} } catch {}
  let bounds = {}
  try { bounds = element.bounds ? element.bounds() : attrs.bounds } catch {}
  let pid = null
  try { pid = element.processId ? element.processId() : element.process_id ? element.process_id() : null } catch {}
  let process = ''
  try { process = element.processName ? element.processName() : attrs.processName || '' } catch { process = attrs.processName || '' }
  let name = ''
  try { name = element.name ? element.name() : attrs.name || '' } catch { name = attrs.name || '' }
  let role = ''
  try { role = element.role ? element.role() : attrs.role || '' } catch { role = attrs.role || '' }
  return {
    id: safeCall(() => element.id && element.id()),
    name: name || '',
    title: name || '',
    role: role || '',
    pid,
    process,
    bounds: bounds ? {
      x: bounds.x || 0,
      y: bounds.y || 0,
      width: bounds.width || 0,
      height: bounds.height || 0,
    } : {},
  }
}

function safeCall(fn) {
  try { return fn() } catch { return '' }
}

function jsonClean(value, maxString = 12000) {
  return JSON.parse(JSON.stringify(value, (_key, current) => {
    if (typeof current === 'bigint') return Number(current)
    if (typeof current === 'string' && current.length > maxString) return current.slice(0, maxString)
    return current
  }))
}

function treeConfig(input, format = 'CompactYaml') {
  return {
    propertyMode: input.property_mode || 'Fast',
    maxDepth: input.max_depth ?? 4,
    formatOutput: true,
    treeOutputFormat: input.output_format || format,
    treeFromSelector: input.tree_from_selector || undefined,
    includeWindowScreenshot: input.include_window_screenshot ?? false,
    includeMonitorScreenshots: input.include_monitor_screenshots ?? false,
    includeOcr: input.include_ocr ?? false,
    includeBrowserDom: input.include_browser_dom ?? false,
    includeOmniparser: input.include_omniparser ?? false,
    includeGeminiVision: input.include_gemini_vision ?? false,
  }
}

async function main() {
  const input = JSON.parse(process.argv[2] || '{}')
  const sdk = loadSdk()
  const desktop = new sdk.Desktop(false, false, 'error')
  const action = input.action

  if (action === 'health') {
    return { ok: true, backend: 'terminator-nodejs', node_package_dir: nodePackageDir }
  }

  if (action === 'applications') {
    const apps = desktop.applications()
    return { ok: true, applications: apps.map(elementToJson) }
  }

  if (action === 'current_window') {
    const current = await desktop.getCurrentWindow()
    return { ok: true, window: elementToJson(current) }
  }

  if (action === 'open_application') {
    const element = desktop.openApplication(input.name, false, false)
    return { ok: true, element: elementToJson(element) }
  }

  if (action === 'find') {
    const element = await desktop.locator(input.selector).first()
    return { ok: true, element: elementToJson(element), selector: input.selector }
  }

  if (action === 'click') {
    const element = await desktop.locator(input.selector).first()
    const result = element.click()
    return { ok: true, element: elementToJson(element), result: String(result || '') }
  }

  if (action === 'type_text') {
    let element = null
    if (input.selector) {
      element = await desktop.locator(input.selector).first()
    } else {
      const current = await desktop.getCurrentWindow()
      element = await current.locator('role:Document || role:Edit || role:TextBox').first()
    }
    element.typeText(input.text || '', {
      clearBeforeTyping: false,
      useClipboard: true,
      tryFocusBefore: true,
      tryClickBefore: true,
      includeWindowScreenshot: false,
      includeMonitorScreenshots: false,
    })
    return { ok: true, element: elementToJson(element) }
  }

  if (action === 'press_key') {
    await desktop.pressKey(input.key)
    return { ok: true, key: input.key }
  }

  if (action === 'window_tree') {
    const result = await desktop.getWindowTreeResultAsync(
      input.process,
      input.title || null,
      treeConfig(input),
    )
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'clustered_tree') {
    const result = await desktop.getClusteredTree(
      input.process,
      input.max_dom_elements || 100,
      Boolean(input.include_omniparser),
      Boolean(input.include_gemini_vision),
    )
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'ocr_process') {
    const result = await desktop.performOcrForProcess(input.process, input.format_output ?? true)
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'browser_dom') {
    const result = await desktop.captureBrowserDom(input.max_elements || 100, input.format_output ?? true)
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'capture_screenshot') {
    const result = await desktop.captureScreenshot(
      input.process,
      input.selector || null,
      Boolean(input.entire_monitor),
      input.timeout_ms || 5000,
    )
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'click_index') {
    const result = desktop.clickByIndex(
      Number(input.index),
      input.vision_type || 'UiTree',
      input.x_percentage ?? 50,
      input.y_percentage ?? 50,
      input.click_type || 'Left',
      input.restore_cursor ?? true,
      input.process || null,
      input.include_window_screenshot ?? false,
      input.include_monitor_screenshots ?? false,
    )
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'click_bounds') {
    const bounds = input.bounds || {}
    const result = desktop.clickAtBounds(
      Number(bounds.x || 0),
      Number(bounds.y || 0),
      Number(bounds.width || 0),
      Number(bounds.height || 0),
      input.x_percentage ?? 50,
      input.y_percentage ?? 50,
      input.click_type || 'Left',
      input.restore_cursor ?? true,
      input.process || null,
      input.include_window_screenshot ?? false,
      input.include_monitor_screenshots ?? false,
    )
    return { ok: true, result: jsonClean(result) }
  }

  if (action === 'verify_exists') {
    const scope = input.scope_selector
      ? await desktop.locator(input.scope_selector).first()
      : await desktop.getCurrentWindow()
    const element = await desktop.verifyElementExists(scope, input.selector, input.timeout_ms || 3000)
    return { ok: true, element: elementToJson(element), selector: input.selector }
  }

  throw new Error(`Unsupported bridge action: ${action}`)
}

main()
  .then((result) => {
    process.stdout.write(JSON.stringify(result))
  })
  .catch((error) => {
    process.stdout.write(JSON.stringify({ ok: false, error: error.message || String(error) }))
    process.exitCode = 1
  })

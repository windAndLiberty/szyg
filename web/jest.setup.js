import '@testing-library/jest-dom'
import React from 'react'

// Suppress console errors for known non-critical issues
const originalConsoleError = console.error
console.error = (...args) => {
  const msg = args[0]?.toString() || ''
  if (msg.includes('HTMLCanvasElement.prototype.getContext') ||
      msg.includes('Not implemented') ||
      msg.includes('does not recognize the') ||
      msg.includes('whileHover') ||
      msg.includes('whileTap') ||
      msg.includes('layoutId') ||
      msg.includes('initial') ||
      msg.includes('animate') ||
      msg.includes('exit') ||
      msg.includes('transition')) {
    return
  }
  originalConsoleError(...args)
}

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
})

// Mock IntersectionObserver
class MockIntersectionObserver {
  observe() { return null }
  unobserve() { return null }
  disconnect() { return null }
}
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: MockIntersectionObserver,
})

// Mock ResizeObserver
class MockResizeObserver {
  observe() { return null }
  unobserve() { return null }
  disconnect() { return null }
}
Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: MockResizeObserver,
})

// Mock scrollTo
window.scrollTo = jest.fn()
HTMLElement.prototype.scrollTo = jest.fn()

// Mock getComputedStyle for CSS variables
const originalGetComputedStyle = window.getComputedStyle
Object.defineProperty(window, 'getComputedStyle', {
  writable: true,
  value: jest.fn((el) => {
    if (el === document.documentElement) {
      return {
        getPropertyValue: (prop) => {
          if (prop === '--accent') return '#6366f1'
          return ''
        },
      }
    }
    return originalGetComputedStyle(el)
  }),
})

// Mock requestAnimationFrame
Object.defineProperty(window, 'requestAnimationFrame', {
  writable: true,
  value: jest.fn((cb) => setTimeout(cb, 16)),
})
Object.defineProperty(window, 'cancelAnimationFrame', {
  writable: true,
  value: jest.fn((id) => clearTimeout(id)),
})

// Mock localStorage
const localStorageMock = {
  store: {},
  getItem: jest.fn((key) => localStorageMock.store[key] || null),
  setItem: jest.fn((key, value) => { localStorageMock.store[key] = String(value) }),
  removeItem: jest.fn((key) => { delete localStorageMock.store[key] }),
  clear: jest.fn(() => { localStorageMock.store = {} }),
}
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

// Mock fetch
global.fetch = jest.fn()

// Mock TextEncoder / TextDecoder
global.TextEncoder = class TextEncoder {
  encode(text) { return Buffer.from(text) }
}
global.TextDecoder = class TextDecoder {
  decode(buffer) { return buffer ? Buffer.from(buffer).toString() : '' }
}

// Framer-motion props to filter out
const motionPropsToFilter = new Set([
  'initial', 'animate', 'exit', 'whileHover', 'whileTap', 'whileFocus',
  'whileInView', 'whileDrag', 'whileLayout', 'layoutId', 'layout',
  'transition', 'variants', 'drag', 'dragConstraints',
  'onDragStart', 'onDragEnd', 'onHoverStart', 'onHoverEnd',
  'onTapStart', 'onTap', 'onTapCancel',
])

// Helper to create mock motion component
function createMotionComponent(tag) {
  return React.forwardRef(({ children, ...props }, ref) => {
    const filtered = {}
    for (const key of Object.keys(props)) {
      if (!motionPropsToFilter.has(key)) {
        filtered[key] = props[key]
      }
    }
    const Tag = tag
    return React.createElement(Tag, { ...filtered, ref }, children)
  })
}

// Mock framer-motion to avoid animation issues in tests
jest.mock('framer-motion', () => ({
  motion: {
    div: createMotionComponent('div'),
    button: createMotionComponent('button'),
    span: createMotionComponent('span'),
    nav: createMotionComponent('nav'),
    main: createMotionComponent('main'),
    header: createMotionComponent('header'),
    footer: createMotionComponent('footer'),
    table: createMotionComponent('table'),
    tbody: createMotionComponent('tbody'),
    tr: createMotionComponent('tr'),
    td: createMotionComponent('td'),
    th: createMotionComponent('th'),
    thead: createMotionComponent('thead'),
    a: createMotionComponent('a'),
    input: createMotionComponent('input'),
    textarea: createMotionComponent('textarea'),
    select: createMotionComponent('select'),
    option: createMotionComponent('option'),
    label: createMotionComponent('label'),
    pre: createMotionComponent('pre'),
    h1: createMotionComponent('h1'),
    h2: createMotionComponent('h2'),
    h3: createMotionComponent('h3'),
    h4: createMotionComponent('h4'),
    p: createMotionComponent('p'),
    ul: createMotionComponent('ul'),
    li: createMotionComponent('li'),
    img: createMotionComponent('img'),
    canvas: createMotionComponent('canvas'),
  },
  AnimatePresence: ({ children }) => React.createElement(React.Fragment, null, children),
}))

// Mock next/navigation
const mockPush = jest.fn()
const mockReplace = jest.fn()

jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
    refresh: jest.fn(),
    back: jest.fn(),
    forward: jest.fn(),
    prefetch: jest.fn(),
  }),
  usePathname: () => '/dashboard',
  useSearchParams: () => ({
    get: jest.fn(() => null),
    has: jest.fn(() => false),
    getAll: jest.fn(() => []),
    entries: jest.fn(() => []),
    keys: jest.fn(() => []),
    values: jest.fn(() => []),
    toString: jest.fn(() => ''),
    forEach: jest.fn(),
  }),
}))

// Reset mocks before each test
beforeEach(() => {
  jest.clearAllMocks()
  localStorageMock.store = {}
  mockPush.mockClear()
  mockReplace.mockClear()
})

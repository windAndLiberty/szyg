import { useState, useEffect, useCallback, useRef } from 'react'
import type { AgentStatus } from '@/types'

export type PipelineAgent = {
  id: string
  name: string
  nameEn: string
  icon: string
  status: AgentStatus
  progress: number
  description: string
}

export type ExtractedField = {
  label: string
  value: string
  category: 'company' | 'person' | 'budget' | 'pain' | 'competitor' | 'timeline'
}

export type ProfileUpdate = {
  type: 'added' | 'updated'
  field: string
  value: string
  oldValue?: string
}

export type CompDimension = {
  name: string
  ourScore: number
  compScore: number
}

export type StrategyAction = {
  text: string
  priority: 'high' | 'medium' | 'low'
}

export type OutputData = {
  extractedFields: ExtractedField[]
  dealAmount: number
  dealStage: string
  winRate: number
  profileUpdates: ProfileUpdate[]
  compDimensions: CompDimension[]
  strategyActions: StrategyAction[]
  strategyText: string
}

const initialAgents: PipelineAgent[] = [
  { id: 'agent1', name: '信息提取', nameEn: 'Info Extract', icon: 'Search', status: 'Waiting', progress: 0, description: 'Extracting key information from visit data...' },
  { id: 'agent2', name: '纪要结构化', nameEn: 'Structure Notes', icon: 'FileText', status: 'Waiting', progress: 0, description: 'Structuring meeting notes into sections...' },
  { id: 'agent3', name: '商机评级', nameEn: 'Rate Deal', icon: 'TrendingUp', status: 'Waiting', progress: 0, description: 'Analyzing deal potential and scoring...' },
  { id: 'agent4', name: '客户画像更新', nameEn: 'Update Profile', icon: 'Users', status: 'Waiting', progress: 0, description: 'Updating customer profile with new insights...' },
  { id: 'agent5', name: '竞品分析', nameEn: 'Compete Analysis', icon: 'Shield', status: 'Waiting', progress: 0, description: 'Analyzing competitive landscape...' },
  { id: 'agent6', name: '跟进策略', nameEn: 'Follow-up Strategy', icon: 'Lightbulb', status: 'Waiting', progress: 0, description: 'Generating follow-up strategy...' },
]

const statusMessages: Record<string, string> = {
  agent1: 'Extracting key information...',
  agent2: 'Structuring meeting notes...',
  agent3: 'Evaluating deal potential...',
  agent4: 'Updating customer profile...',
  agent5: 'Analyzing competitive landscape...',
  agent6: 'Generating follow-up strategy...',
}

export function usePipelineSimulation() {
  const [agents, setAgents] = useState<PipelineAgent[]>(initialAgents)
  const [currentAgentIndex, setCurrentAgentIndex] = useState(-1)
  const [isComplete, setIsComplete] = useState(false)
  const [isRunning, setIsRunning] = useState(false)
  const [outputData, setOutputData] = useState<OutputData>({
    extractedFields: [],
    dealAmount: 0,
    dealStage: '',
    winRate: 0,
    profileUpdates: [],
    compDimensions: [],
    strategyActions: [],
    strategyText: '',
  })

  const timerRefs = useRef<ReturnType<typeof setTimeout>[]>([])

  const updateAgent = useCallback((index: number, updates: Partial<PipelineAgent>) => {
    setAgents(prev => prev.map((a, i) => i === index ? { ...a, ...updates } : a))
  }, [])

  const clearAllTimers = useCallback(() => {
    timerRefs.current.forEach(t => clearTimeout(t))
    timerRefs.current = []
  }, [])

  const startSimulation = useCallback(() => {
    clearAllTimers()
    setAgents(initialAgents.map(a => ({ ...a, status: 'Waiting' as AgentStatus, progress: 0 })))
    setCurrentAgentIndex(-1)
    setIsComplete(false)
    setIsRunning(true)
    setOutputData({
      extractedFields: [],
      dealAmount: 0,
      dealStage: '',
      winRate: 0,
      profileUpdates: [],
      compDimensions: [],
      strategyActions: [],
      strategyText: '',
    })

    const schedule = (fn: () => void, delay: number) => {
      const t = setTimeout(fn, delay)
      timerRefs.current.push(t)
      return t
    }

    // Agent 1 starts immediately
    schedule(() => {
      setCurrentAgentIndex(0)
      updateAgent(0, { status: 'Processing', progress: 10 })
    }, 500)

    // Agent 1 progress
    schedule(() => updateAgent(0, { progress: 40 }), 1200)
    schedule(() => updateAgent(0, { progress: 75 }), 2200)

    // Agent 1 completes -> Agent 2 starts
    schedule(() => {
      updateAgent(0, { status: 'Complete', progress: 100 })
      setOutputData(prev => ({
        ...prev,
        extractedFields: [
          { label: '客户背景', value: 'Acme Corp', category: 'company' },
          { label: '参会人', value: 'CTO Li Wei', category: 'person' },
          { label: '参会人', value: 'Zhang (Evaluator)', category: 'person' },
          { label: '痛点', value: 'Reporting too slow', category: 'pain' },
          { label: '痛点', value: '3-day month-end close', category: 'pain' },
          { label: '预算', value: '\u00A5500K', category: 'budget' },
          { label: '竞品', value: 'CompetitorX', category: 'competitor' },
          { label: '时间线', value: 'Q3 2026', category: 'timeline' },
        ],
      }))

      schedule(() => {
        setCurrentAgentIndex(1)
        updateAgent(1, { status: 'Processing', progress: 10 })
      }, 400)
    }, 3200)

    // Agent 2 progress
    schedule(() => updateAgent(1, { progress: 50 }), 4200)
    schedule(() => updateAgent(1, { progress: 85 }), 5400)

    // Agent 2 completes -> Agents 3,4,5 start in parallel
    schedule(() => {
      updateAgent(1, { status: 'Complete', progress: 100 })

      schedule(() => {
        setCurrentAgentIndex(2)
        updateAgent(2, { status: 'Processing', progress: 15 })
        updateAgent(3, { status: 'Processing', progress: 10 })
        updateAgent(4, { status: 'Processing', progress: 10 })
      }, 300)
    }, 6400)

    // Parallel agents progress
    schedule(() => {
      updateAgent(2, { progress: 50 })
      updateAgent(3, { progress: 45 })
      updateAgent(4, { progress: 40 })
    }, 7800)

    schedule(() => {
      updateAgent(2, { progress: 80 })
      updateAgent(3, { progress: 75 })
      updateAgent(4, { progress: 70 })
    }, 9200)

    // Parallel agents complete
    schedule(() => {
      updateAgent(2, { status: 'Complete', progress: 100 })
      updateAgent(3, { status: 'Complete', progress: 100 })
      updateAgent(4, { status: 'Complete', progress: 100 })

      setOutputData(prev => ({
        ...prev,
        dealAmount: 350000,
        dealStage: 'Solution Evaluation',
        winRate: 72,
        profileUpdates: [
          { type: 'added', field: 'Pain point', value: 'Reporting speed' },
          { type: 'updated', field: 'Budget', value: '\u00A5500K', oldValue: '\u00A5300K' },
          { type: 'added', field: 'Contact', value: 'CTO Li Wei' },
        ],
        compDimensions: [
          { name: 'Price', ourScore: 80, compScore: 60 },
          { name: 'Features', ourScore: 90, compScore: 75 },
          { name: 'Service', ourScore: 85, compScore: 55 },
          { name: 'Brand', ourScore: 70, compScore: 80 },
        ],
      }))

      schedule(() => {
        setCurrentAgentIndex(5)
        updateAgent(5, { status: 'Processing', progress: 15 })
      }, 400)
    }, 10400)

    // Agent 6 progress
    schedule(() => updateAgent(5, { progress: 50 }), 11400)
    schedule(() => updateAgent(5, { progress: 80 }), 12400)

    // All complete
    schedule(() => {
      updateAgent(5, { status: 'Complete', progress: 100 })
      setOutputData(prev => ({
        ...prev,
        strategyActions: [
          { text: 'Schedule technical demo within 3 days', priority: 'high' },
          { text: 'Send premium tier proposal by Feb 20', priority: 'high' },
          { text: 'Share SOC2 compliance documentation', priority: 'medium' },
          { text: 'Executive alignment call with VP Sales', priority: 'medium' },
          { text: 'Prepare custom reporting module demo', priority: 'low' },
        ],
        strategyText: 'Accelerate proposal delivery. Client timeline is tight (Q3). Competitor threat is moderate. Recommend technical demo within 3 days.',
      }))
      setIsComplete(true)
      setIsRunning(false)
      setCurrentAgentIndex(-1)
    }, 13400)
  }, [clearAllTimers, updateAgent])

  useEffect(() => {
    // Auto-start on mount
    const t = setTimeout(() => startSimulation(), 800)
    return () => {
      clearTimeout(t)
      clearAllTimers()
    }
  }, [startSimulation, clearAllTimers])

  const overallProgress = Math.round(
    agents.reduce((sum, a) => sum + a.progress, 0) / agents.length
  )

  const currentStatusText = currentAgentIndex >= 0
    ? statusMessages[agents[currentAgentIndex]?.id] || 'Processing...'
    : isComplete
      ? 'All agents complete!'
      : 'Waiting to start...'

  return {
    agents,
    currentAgentIndex,
    isComplete,
    isRunning,
    overallProgress,
    currentStatusText,
    outputData,
    startSimulation,
  }
}

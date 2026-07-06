import { motion } from 'framer-motion'
import { ArrowLeft, ArrowRight, Sparkles, RotateCcw } from 'lucide-react'
import { Link } from 'react-router'
import { cn } from '@/lib/utils'
import { usePipelineSimulation } from '@/components/processing/usePipelineSimulation'
import StatusHeader from '@/components/processing/StatusHeader'
import AgentNode from '@/components/processing/AgentNode'
import PipelineConnections from '@/components/processing/PipelineConnections'
import AgentDetail from '@/components/processing/AgentDetail'
import OutputCards from '@/components/processing/OutputCards'
import PipelineFunnel from '@/components/processing/PipelineFunnel'

const agentStepText = (current: number, total: number, isComplete: boolean) => {
  if (isComplete) return 'All steps complete'
  if (current < 0) return 'Waiting to start'
  return `Step ${Math.min(current + 1, total)} of ${total}`
}

const stageIndexFromName = (name: string): number | null => {
  const map: Record<string, number> = {
    'Solution Evaluation': 2,
    'Negotiation': 3,
    'Won': 4,
    'Lost': 5,
  }
  return map[name] ?? null
}

export default function Processing() {
  const {
    agents,
    currentAgentIndex,
    isComplete,
    overallProgress,
    currentStatusText,
    outputData,
    startSimulation,
  } = usePipelineSimulation()

  const dealStageIndex = stageIndexFromName(outputData.dealStage)

  // Determine which output cards to show based on agent completion
  const hasInfoExtract = agents[0]?.status === 'Complete'
  const hasDealCard = agents[2]?.status === 'Complete'
  const hasProfileUpdates = agents[3]?.status === 'Complete'
  const hasCompAnalysis = agents[4]?.status === 'Complete'
  const hasStrategy = agents[5]?.status === 'Complete'

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] as [number, number, number, number] }}
      className="max-w-[1400px] mx-auto space-y-6 pb-8"
    >
      {/* Section 1: Status Header */}
      <StatusHeader
        statusText={currentStatusText}
        stepText={agentStepText(currentAgentIndex, agents.length, isComplete)}
        progress={overallProgress}
        isComplete={isComplete}
      />

      {/* Section 2: Agent Pipeline (Main Visual) */}
      <motion.div
        className="relative rounded-card p-8 border border-[#1E293B] min-h-[240px] flex items-center justify-center overflow-hidden"
        style={{
          background: 'linear-gradient(180deg, rgba(26,34,53,0.6) 0%, rgba(17,24,39,0.9) 100%)',
        }}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.6 }}
      >
        {/* Ambient glow */}
        <div
          className="absolute inset-0 pointer-events-none opacity-60"
          style={{
            background: 'radial-gradient(circle at 50% 50%, rgba(99,102,241,0.08) 0%, transparent 70%)',
          }}
        />

        {/* SVG Connection Lines */}
        <div className="absolute inset-0">
          <PipelineConnections agentStatuses={agents.map(a => a.status)} />
        </div>

        {/* Agent Nodes */}
        <div className="relative z-10 flex items-center justify-between w-full max-w-5xl mx-auto px-4">
          {agents.map((agent, index) => (
            <AgentNode
              key={agent.id}
              id={agent.id}
              name={agent.name}
              nameEn={agent.nameEn}
              icon={agent.icon}
              status={agent.status}
              index={index}
              isActive={currentAgentIndex === index}
            />
          ))}
        </div>
      </motion.div>

      {/* Section 3: Active Agent Detail */}
      <div className="min-h-[140px]">
        {currentAgentIndex >= 0 ? (
          <AgentDetail
            key={agents[currentAgentIndex]?.id}
            agentId={agents[currentAgentIndex]?.id}
            agentName={agents[currentAgentIndex]?.name}
            icon={agents[currentAgentIndex]?.icon}
            status={agents[currentAgentIndex]?.status}
            progress={agents[currentAgentIndex]?.progress}
            isVisible={currentAgentIndex >= 0}
          />
        ) : (
          <motion.div
            className="flex items-center justify-center py-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
          >
            {isComplete ? (
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-[#10B981]/15 flex items-center justify-center">
                  <svg className="w-4 h-4 text-[#10B981]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="text-body-md text-[#94A3B8]">All agents completed successfully</span>
              </div>
            ) : (
              <span className="text-body-sm text-[#64748B]">Pipeline ready to start...</span>
            )}
          </motion.div>
        )}
      </div>

      {/* Section 4: Output Cards Row + Funnel */}
      <div className="grid grid-cols-1 xl:grid-cols-[1fr_280px] gap-6">
        <OutputCards
          data={outputData}
          hasInfoExtract={hasInfoExtract}
          hasDealCard={hasDealCard}
          hasProfileUpdates={hasProfileUpdates}
          hasCompAnalysis={hasCompAnalysis}
          hasStrategy={hasStrategy}
          isComplete={isComplete}
        />

        <PipelineFunnel
          show={hasDealCard}
          highlightStage={dealStageIndex}
        />
      </div>

      {/* Section 5: Bottom Action Bar */}
      <motion.div
        className="flex items-center justify-between pt-4 border-t border-[#1E293B]"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4, duration: 0.4 }}
      >
        <Link
          to="/input"
          className={cn(
            'inline-flex items-center gap-2 px-4 py-2.5 rounded-button text-body-sm font-medium',
            'text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] transition-colors'
          )}
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>

        <div className="flex items-center gap-3">
          {!isComplete && overallProgress === 0 && (
            <button
              onClick={startSimulation}
              className={cn(
                'inline-flex items-center gap-2 px-4 py-2.5 rounded-button text-body-sm font-medium',
                'text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] transition-colors'
              )}
            >
              <RotateCcw className="w-4 h-4" />
              Restart
            </button>
          )}

          {isComplete ? (
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{
                duration: 0.5,
                ease: [0.34, 1.56, 0.64, 1] as [number, number, number, number],
              }}
            >
              <Link
                to="/report/1"
                className={cn(
                  'inline-flex items-center gap-2 px-6 py-3 rounded-button text-body-sm font-semibold',
                  'bg-[#6366F1] text-white hover:bg-[#818CF8] transition-colors',
                  'shadow-glow hover:shadow-glow-strong'
                )}
              >
                <Sparkles className="w-4 h-4" />
                View Full Report
                <ArrowRight className="w-4 h-4" />
              </Link>
            </motion.div>
          ) : (
            <button
              disabled
              className={cn(
                'inline-flex items-center gap-2 px-6 py-3 rounded-button text-body-sm font-semibold',
                'bg-[#1A2235] text-[#64748B] border border-[#1E293B] cursor-not-allowed'
              )}
            >
              <div className="w-4 h-4 border-2 border-[#64748B] border-t-transparent rounded-full animate-spin" />
              Processing...
            </button>
          )}
        </div>
      </motion.div>
    </motion.div>
  )
}

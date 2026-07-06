import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Wand2, Upload, Scissors, Link2, Gauge, Type, Music, Camera,
  Rocket, ChevronDown, ChevronRight, Plus, X, Layers,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { EditStep } from './types'

type VideoToolboxProps = {
  onCreateClick: () => void
  onUploadClick: () => void
  onPublishClick: () => void
  editChain: EditStep[]
  onRemoveStep: (idx: number) => void
  onApplyChain: () => void
  onClearChain: () => void
  onToolClick: (tool: string) => void
  disabled?: boolean
}

const EDIT_TOOLS = [
  { id: 'cut', label: '裁剪', icon: Scissors, desc: '拖动时间轴选取起止点' },
  { id: 'concat', label: '拼接', icon: Link2, desc: '多视频合并排序' },
  { id: 'speed', label: '变速', icon: Gauge, desc: '0.25x ~ 4x 滑块调节' },
  { id: 'title', label: '叠加标题', icon: Type, desc: '文字/字号/颜色/位置' },
  { id: 'mix_audio', label: '混音', icon: Music, desc: '原声 + BGM 混合' },
  { id: 'extract_frame', label: '提取封面', icon: Camera, desc: '指定时间点截图' },
]

export default function VideoToolbox({
  onCreateClick, onUploadClick, onPublishClick,
  editChain, onRemoveStep, onApplyChain, onClearChain, onToolClick,
  disabled,
}: VideoToolboxProps) {
  const [editOpen, setEditOpen] = useState(true)
  const [chainOpen, setChainOpen] = useState(false)

  return (
    <div className="w-[280px] shrink-0 border-r border-[#1E293B] bg-[#0B0F1A] flex flex-col h-full overflow-y-auto">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#1E293B]">
        <h2 className="text-body-md font-semibold text-[#F1F5F9] flex items-center gap-2">
          <Wand2 className="w-4 h-4 text-[#6366F1]" /> 工具箱
        </h2>
      </div>

      <div className="flex-1 p-3 space-y-3">
        {/* AI 生视频 */}
        <motion.button
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          onClick={onCreateClick}
          disabled={disabled}
          className="w-full rounded-card-lg border border-[rgba(99,102,241,0.3)] p-4 text-left transition-all hover:border-[#6366F1]/50 disabled:opacity-50"
          style={{ background: 'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(17,24,39,0.6) 100%)' }}
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[#6366F1] flex items-center justify-center shadow-glow">
              <Wand2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-body-sm font-semibold text-[#F1F5F9]">AI 生成视频</p>
              <p className="text-[11px] text-[#64748B]">输入描述，一键生成</p>
            </div>
          </div>
        </motion.button>

        {/* 本地上传 */}
        <motion.button
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          onClick={onUploadClick}
          disabled={disabled}
          className="w-full rounded-card-lg border border-dashed border-[#334155] p-3 flex items-center gap-3 text-[#94A3B8] hover:text-[#F1F5F9] hover:border-[#6366F1]/50 transition-all disabled:opacity-50"
        >
          <Upload className="w-4 h-4" />
          <span className="text-body-sm">上传视频 (.mp4 .mov .avi)</span>
        </motion.button>

        <div className="border-t border-[#1E293B]" />

        {/* 剪辑工具 */}
        <button
          onClick={() => setEditOpen(!editOpen)}
          className="w-full flex items-center gap-2 text-body-sm font-semibold text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
        >
          {editOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          <Scissors className="w-4 h-4 text-[#F59E0B]" /> 剪辑工具
        </button>

        <AnimatePresence>
          {editOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden space-y-1"
            >
              {EDIT_TOOLS.map((t) => (
                <motion.button
                  key={t.id}
                  whileHover={{ x: 4 }}
                  onClick={() => onToolClick(t.id)}
                  disabled={disabled}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-card text-body-sm text-[#94A3B8] hover:text-[#F1F5F9] hover:bg-[rgba(255,255,255,0.03)] transition-all group disabled:opacity-50"
                >
                  <t.icon className="w-4 h-4 shrink-0 text-[#64748B] group-hover:text-[#94A3B8]" />
                  <div className="text-left min-w-0">
                    <span className="text-[13px]">{t.label}</span>
                    <span className="block text-[10px] text-[#64748B]">{t.desc}</span>
                  </div>
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="border-t border-[#1E293B]" />

        {/* 操作链 */}
        <button
          onClick={() => setChainOpen(!chainOpen)}
          className={cn(
            'w-full flex items-center gap-2 text-body-sm font-semibold transition-colors',
            editChain.length > 0 ? 'text-[#6366F1]' : 'text-[#94A3B8] hover:text-[#F1F5F9]',
          )}
        >
          {chainOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          <Layers className="w-4 h-4" /> 操作链
          {editChain.length > 0 && (
            <span className="px-1.5 py-0.5 rounded text-[10px] bg-[#6366F1]/20 text-[#6366F1]">{editChain.length}</span>
          )}
        </button>

        <AnimatePresence>
          {chainOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="overflow-hidden"
            >
              {editChain.length === 0 ? (
                <p className="text-[11px] text-[#64748B] px-3 py-2">
                  点击上方剪辑工具添加步骤，可一次性提交多项操作
                </p>
              ) : (
                <div className="space-y-1 px-1">
                  {editChain.map((step, idx) => (
                    <div key={idx} className="flex items-center gap-2 px-2 py-1.5 rounded-card bg-[#1A2235] border border-[#1E293B]">
                      <span className="text-[11px] text-[#64748B]">{idx + 1}.</span>
                      <span className="flex-1 text-[12px] text-[#F1F5F9]">{step.label}</span>
                      <button onClick={() => onRemoveStep(idx)} className="p-0.5 rounded text-[#64748B] hover:text-[#EF4444]">
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                  <div className="flex gap-2 pt-2">
                    <button
                      onClick={onApplyChain}
                      disabled={disabled}
                      className="flex-1 py-1.5 rounded-button text-[12px] font-medium bg-[#6366F1] text-white hover:bg-[#818CF8] disabled:opacity-50 transition-colors"
                    >
                      🔄 应用全部
                    </button>
                    <button
                      onClick={onClearChain}
                      className="py-1.5 px-3 rounded-button text-[12px] text-[#94A3B8] hover:text-[#F1F5F9] transition-colors"
                    >
                      🗑 清空
                    </button>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        <div className="border-t border-[#1E293B]" />
      </div>

      {/* 发布入口 */}
      <div className="p-3 border-t border-[#1E293B]">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={onPublishClick}
          disabled={disabled}
          className="w-full py-2.5 rounded-button font-medium text-body-sm flex items-center justify-center gap-2 bg-[#10B981] text-white hover:bg-[#34D399] transition-colors disabled:opacity-50 shadow-glow"
        >
          <Rocket className="w-4 h-4" /> 一键发布
        </motion.button>
      </div>
    </div>
  )
}

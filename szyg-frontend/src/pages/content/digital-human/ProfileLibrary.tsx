import { useState } from 'react'
import { Check, Copy, Loader2, Mic2, Plus, Save, Trash2, UserRound } from 'lucide-react'
import type { DigitalHumanAsset, DigitalHumanProfile } from '@/lib/api'
import DropZone from './DropZone'
import { acceptForAvatar, acceptForVoice } from './studioUtils'
import { useI18n } from '@/lib/i18n'

interface ProfileLibraryProps {
  profiles: DigitalHumanProfile[]
  assetById: Map<string, DigitalHumanAsset>
  selectedProfileId: string
  busyKey: string
  draft: ProfileDraft
  onDraftChange: (next: ProfileDraft) => void
  onUploadAvatar: (file: File) => void
  onUploadVoice: (file: File) => void
  onSaveDraft: () => void
  onSelectProfile: (profile: DigitalHumanProfile) => void
  onRemoveProfile: (profile: DigitalHumanProfile) => void
  onRemix: (profile: DigitalHumanProfile) => void
}

export interface ProfileDraft {
  name: string
  profileType: 'virtual' | 'real'
  avatarIds: string[]
  voiceId: string
}

const EMPTY_DRAFT: ProfileDraft = {
  name: '',
  profileType: 'virtual',
  avatarIds: [],
  voiceId: '',
}

export { EMPTY_DRAFT }

export default function ProfileLibrary(props: ProfileLibraryProps) {
  const { t } = useI18n()
  const {
    profiles,
    assetById,
    selectedProfileId,
    busyKey,
    draft,
    onDraftChange,
    onUploadAvatar,
    onUploadVoice,
    onSaveDraft,
    onSelectProfile,
    onRemoveProfile,
    onRemix,
  } = props

  const [showForm, setShowForm] = useState(false)
  const draftAvatars = draft.avatarIds.map((id) => assetById.get(id)).filter((a): a is DigitalHumanAsset => Boolean(a))
  const canSave = draft.avatarIds.length > 0 && Boolean(draft.voiceId) && busyKey !== 'profile-save'

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">{t('数字人形象库')}</h2>
          <p className="mt-1 text-xs text-[#7F8DA5]">{t('人物和声音绑定保存，后续作品可以直接复用。')}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((value) => !value)}
          className="inline-flex h-9 items-center gap-1.5 bg-[#5965E8] px-3 text-sm"
        >
          <Plus className="h-4 w-4" />
          {showForm ? t('收起') : t('新建形象')}
        </button>
      </div>
      {showForm && (
        <div className="mb-6 grid gap-5 border-y border-[#283448] bg-[#0D1320] px-4 py-5 lg:grid-cols-[240px_1fr_1fr_auto]">
          <div>
            <label className="text-xs text-[#8795AA]">{t('形象名称')}</label>
            <input
              value={draft.name}
              onChange={(event) => onDraftChange({ ...draft, name: event.target.value })}
              placeholder={t('例如：品牌讲解员')}
              className="mt-2 h-10 w-full border border-[#2B374B] bg-[#080D16] px-3 text-sm outline-none"
            />
            <div className="mt-3 flex gap-2">
              {(['virtual', 'real'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => onDraftChange({ ...draft, profileType: value })}
                  className={`h-8 flex-1 border text-xs ${
                    draft.profileType === value ? 'border-[#6974F1] bg-[#252B63]' : 'border-[#2B374B]'
                  }`}
                >
                  {t(value === 'virtual' ? '虚拟人物' : '真人形象')}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-[#8795AA]">{t('人物参考')}</label>
            <div className="mt-2">
              <DropZone
                accept={acceptForAvatar()}
                multiple
                onFiles={(files) => files.forEach((file) => onUploadAvatar(file))}
                busy={busyKey === 'profile-avatar'}
                size="sm"
                icon={<UserRound className="mr-1.5 h-4 w-4" />}
                title={t('拖入或点击上传')}
                hint={t('图片 / 视频，可多次上传')}
                overlayLabel={t('松开即可加入人物参考')}
              />
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {draftAvatars.map((asset) => (
                <AvatarThumb key={asset.id} asset={asset} />
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-[#8795AA]">{t('绑定声音')}</label>
            <div className="mt-2">
              <DropZone
                accept={acceptForVoice()}
                multiple={false}
                onFiles={(files) => {
                  const [first] = files
                  if (first) onUploadVoice(first)
                }}
                busy={busyKey === 'profile-voice'}
                size="sm"
                icon={<Mic2 className="mr-1.5 h-4 w-4" />}
                title={t('拖入或点击上传')}
                hint={t('上传单人清晰说话的音频或有声视频')}
                overlayLabel={t('松开即可绑定声音')}
              />
            </div>
            <p className="mt-2 text-xs text-[#7F8DA5]">{t('生成新台词时，以这段声音的音色和说话风格为参考。')}</p>
            {draft.voiceId && (
              <p className="mt-2 truncate text-xs text-[#83D9C2]">已绑定：{assetById.get(draft.voiceId)?.name}</p>
            )}
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={onSaveDraft}
              disabled={!canSave}
              className="inline-flex h-10 items-center gap-2 bg-[#5965E8] px-4 text-sm disabled:opacity-40"
            >
              {busyKey === 'profile-save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t('保存')}
            </button>
          </div>
        </div>
      )}
      {profiles.length === 0 ? (
        <div className="flex min-h-[200px] flex-col items-center justify-center border border-dashed border-[#2B3850] bg-[#0B101B]/40 px-6 text-center">
          <UserRound className="mb-3 h-7 w-7 text-[#7184A3]" />
          <p className="text-sm font-medium text-[#E7ECF5]">{t('建立第一个数字人形象')}</p>
          <p className="mt-1 max-w-sm text-xs leading-5 text-[#7F8DA5]">{t('上传虚拟人物参考和声音，保存后可以在所有数字人口播作品中复用。')}</p>
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {profiles.map((item) => (
            <li key={item.id}>
              <ProfileCard
                profile={item}
                cover={assetById.get(item.cover_asset_id || item.avatar_asset_ids[0])}
                voiceName={item.voice_asset_id ? assetById.get(item.voice_asset_id)?.name : undefined}
                selected={item.id === selectedProfileId}
                onSelect={() => onSelectProfile(item)}
                onRemove={() => onRemoveProfile(item)}
                onRemix={() => onRemix(item)}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function AvatarThumb({ asset }: { asset: DigitalHumanAsset }) {
  if (asset.kind === 'image') {
    return <img src={asset.url} alt={asset.name} className="h-9 w-9 shrink-0 rounded-md border border-[#2A3448] object-cover" />
  }
  if (asset.kind === 'video') {
    return <video src={asset.url} muted preload="metadata" className="h-9 w-9 shrink-0 rounded-md border border-[#2A3448] object-cover" />
  }
  return <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-[#2A3448] bg-[#111827] text-[10px] text-[#65738A]">AUDIO</div>
}

interface ProfileCardProps {
  profile: DigitalHumanProfile
  cover: DigitalHumanAsset | undefined
  voiceName: string | undefined
  selected: boolean
  onSelect: () => void
  onRemove: () => void
  onRemix: () => void
}

function ProfileCard({ profile, cover, voiceName, selected, onSelect, onRemove, onRemix }: ProfileCardProps) {
  const { t } = useI18n()
  const canRemix = profile.profile_type === 'virtual' && Boolean(profile.voice_asset_id)
  return (
    <article
      onClick={onSelect}
      className={`cursor-pointer border p-4 transition ${
        selected ? 'border-[#6974F1] bg-[#171D3B]' : 'border-[#242F42] bg-[#0D121D] hover:border-[#3B4860]'
      }`}
    >
      <div className="flex items-start gap-3">
        {cover ? (
          <AvatarThumb asset={cover} />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-md border border-[#2A3448] bg-[#151D2B]">
            <UserRound className="h-6 w-6" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium">{profile.name}</p>
            {selected && <Check className="h-4 w-4 text-[#7D87FF]" />}
          </div>
          <p className="mt-1 text-xs text-[#7F8DA5]">
            {t(profile.profile_type === 'virtual' ? '虚拟人物 · 可生成' : '真人形象 · 暂不可生成')}
          </p>
          <p className="mt-2 truncate text-xs text-[#A7B2C3]">
            {voiceName ? `${t('声音：')}${voiceName}` : t('未绑定声音')}
          </p>
        </div>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onRemove()
          }}
          aria-label={t('删除形象')}
          className="p-1 text-[#6E7D93] hover:text-[#F48A9B]"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      {canRemix && (
        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              onRemix()
            }}
            className="inline-flex h-8 items-center gap-1.5 border border-[#535FCB] bg-[#202653] px-3 text-xs text-[#D6DAFF] hover:border-[#6974F1]"
          >
            <Copy className="h-3.5 w-3.5" />
            {t('用此形象高仿复刻')}
          </button>
        </div>
      )}
    </article>
  )
}

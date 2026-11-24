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
          <h2 className="text-base font-semibold">{t('digitalHuman.profile.title')}</h2>
          <p className="mt-1 text-xs text-muted-foreground">{t('digitalHuman.profile.description')}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((value) => !value)}
          className="inline-flex h-9 items-center gap-1.5 bg-primary text-primary-foreground px-3 text-sm"
        >
          <Plus className="h-4 w-4" />
          {showForm ? t('digitalHuman.profile.collapse') : t('digitalHuman.profile.new')}
        </button>
      </div>
      {showForm && (
        <div className="mb-6 grid gap-5 border-y border-border bg-card px-4 py-5 lg:grid-cols-[240px_1fr_1fr_auto]">
          <div>
            <label className="text-xs text-muted-foreground">{t('digitalHuman.profile.name')}</label>
            <input
              value={draft.name}
              onChange={(event) => onDraftChange({ ...draft, name: event.target.value })}
              placeholder={t('digitalHuman.profile.namePlaceholder')}
              className="mt-2 h-10 w-full border border-border bg-background px-3 text-sm outline-none"
            />
            <div className="mt-3 flex gap-2">
              {(['virtual', 'real'] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => onDraftChange({ ...draft, profileType: value })}
                  className={`h-8 flex-1 border text-xs ${
                    draft.profileType === value ? 'border-[#6974F1] bg-accent-soft' : 'border-border'
                  }`}
                >
                  {t(value === 'virtual' ? 'digitalHuman.profile.virtual' : 'digitalHuman.profile.real')}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t('digitalHuman.profile.characterReference')}</label>
            <div className="mt-2">
              <DropZone
                accept={acceptForAvatar()}
                multiple
                onFiles={(files) => files.forEach((file) => onUploadAvatar(file))}
                busy={busyKey === 'profile-avatar'}
                size="sm"
                icon={<UserRound className="mr-1.5 h-4 w-4" />}
                title={t('digitalHuman.profile.upload')}
                hint={t('digitalHuman.profile.characterFormats')}
                overlayLabel={t('digitalHuman.profile.dropCharacter')}
              />
            </div>
            <div className="mt-2 flex flex-wrap gap-2">
              {draftAvatars.map((asset) => (
                <AvatarThumb key={asset.id} asset={asset} />
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-muted-foreground">{t('digitalHuman.profile.voiceReference')}</label>
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
                title={t('digitalHuman.profile.upload')}
                hint={t('digitalHuman.profile.voiceFormats')}
                overlayLabel={t('digitalHuman.profile.dropVoice')}
              />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{t('digitalHuman.profile.voiceDescription')}</p>
            {draft.voiceId && (
              <p className="mt-2 truncate text-xs text-success-ink">{t('digitalHuman.profile.voiceBound', { name: assetById.get(draft.voiceId)?.name || '' })}</p>
            )}
          </div>
          <div className="flex items-end">
            <button
              type="button"
              onClick={onSaveDraft}
              disabled={!canSave}
              className="inline-flex h-10 items-center gap-2 bg-primary text-primary-foreground px-4 text-sm disabled:opacity-40"
            >
              {busyKey === 'profile-save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              {t('digitalHuman.profile.save')}
            </button>
          </div>
        </div>
      )}
      {profiles.length === 0 ? (
        <div className="flex min-h-[200px] flex-col items-center justify-center border border-dashed border-border bg-background/40 px-6 text-center">
          <UserRound className="mb-3 h-7 w-7 text-muted-foreground" />
          <p className="text-sm font-medium text-foreground">{t('digitalHuman.profile.empty')}</p>
          <p className="mt-1 max-w-sm text-xs leading-5 text-muted-foreground">{t('digitalHuman.profile.emptyDescription')}</p>
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
    return <img src={asset.url} alt={asset.name} className="h-9 w-9 shrink-0 rounded-md border border-border object-cover" />
  }
  if (asset.kind === 'video') {
    return <video src={asset.url} muted preload="metadata" className="h-9 w-9 shrink-0 rounded-md border border-border object-cover" />
  }
  return <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border bg-card text-[10px] text-muted-foreground">AUDIO</div>
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
        selected ? 'border-[#6974F1] bg-accent-soft' : 'border-border bg-card hover:border-border'
      }`}
    >
      <div className="flex items-start gap-3">
        {cover ? (
          <AvatarThumb asset={cover} />
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-md border border-border bg-card">
            <UserRound className="h-6 w-6" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium">{profile.name}</p>
            {selected && <Check className="h-4 w-4 text-accent-ink" />}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t(profile.profile_type === 'virtual' ? 'digitalHuman.profile.virtualReady' : 'digitalHuman.profile.realUnavailable')}
          </p>
          <p className="mt-2 truncate text-xs text-muted-foreground">
            {voiceName ? t('digitalHuman.profile.voiceName', { name: voiceName }) : t('digitalHuman.profile.noVoice')}
          </p>
        </div>
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation()
            onRemove()
          }}
          aria-label={t('digitalHuman.profile.delete')}
          className="p-1 text-muted-foreground hover:text-danger-ink"
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
            className="inline-flex h-8 items-center gap-1.5 border border-[#535FCB] bg-accent-soft px-3 text-xs text-accent-ink hover:border-[#6974F1]"
          >
            <Copy className="h-3.5 w-3.5" />
            {t('digitalHuman.profile.remix')}
          </button>
        </div>
      )}
    </article>
  )
}

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { AVATAR_PRESETS, DEFAULT_AVATAR_SRC, useUserAvatar } from '@/lib/avatar'

type UserAvatarProps = {
  className?: string
  imgClassName?: string
  /** 传入后头像变为可点击 */
  onClick?: () => void
  alt?: string
}

/**
 * 全局统一的用户头像：
 * - 始终只显示图片（内置图库 / 用户自定义），不显示任何文字；
 * - 未设置时使用图库第 1 张默认头像，自定义图片异常时回退默认头像；
 * - 全站同步（localStorage，云端不参与）。
 */
export default function UserAvatar({ className, imgClassName, onClick, alt = '用户头像' }: UserAvatarProps) {
  const source = useUserAvatar()
  const [failed, setFailed] = useState(false)

  const custom = source.kind === 'custom'
    ? source.dataUrl
    : source.kind === 'preset'
      ? AVATAR_PRESETS[source.index]
      : null
  const src = custom && !failed ? custom : DEFAULT_AVATAR_SRC

  return (
    <div
      className={cn('overflow-hidden rounded-full bg-[#1E293B]', onClick && 'cursor-pointer transition-transform hover:scale-[1.03] active:scale-95', className)}
      role={onClick ? 'button' : undefined}
      onClick={onClick}
      title={alt}
    >
      <img
        src={src}
        alt={alt}
        loading="lazy"
        draggable={false}
        className={cn('h-full w-full object-cover', imgClassName)}
        onError={() => setFailed(true)}
      />
    </div>
  )
}
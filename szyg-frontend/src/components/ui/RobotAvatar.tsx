import directorAvatar from '@/assets/products/video-director-avatar.webp'
import { product } from '@/lib/product'

export const XIAOYU_AVATAR = 'xiaoyu'
export const DIRECTOR_AVATAR = 'director'
const positions = ['0% 0%', '50% 0%', '100% 0%', '0% 100%', '50% 100%', '100% 100%']
export const robotPresets = positions.map((_, index) => 'robot:' + index)

export function defaultRobotPreset(identity: string, primary = false) {
  if (primary) return XIAOYU_AVATAR
  if (identity === 'xiaoyu-director') return DIRECTOR_AVATAR
  let hash = 0
  for (const character of identity) hash = (Math.imul(hash, 31) + character.charCodeAt(0)) >>> 0
  return robotPresets[1 + hash % (positions.length - 1)]
}

export default function RobotAvatar({ identity, primary = false, avatar, className = '' }: {
  identity: string
  primary?: boolean
  avatar?: string
  className?: string
}) {
  if (avatar && /^data:image\/(?:png|jpeg|webp);base64,/i.test(avatar)) {
    return <img alt="" src={avatar} draggable={false} className={'shrink-0 object-cover ' + className} />
  }
  const preset = avatar === XIAOYU_AVATAR || avatar === DIRECTOR_AVATAR || (avatar && robotPresets.includes(avatar)) ? avatar : defaultRobotPreset(identity, primary)
  if (preset === XIAOYU_AVATAR || preset === DIRECTOR_AVATAR) {
    return <img alt="" src={preset === DIRECTOR_AVATAR ? directorAvatar : product.logoUrl} draggable={false} className={'shrink-0 object-cover ' + className} />
  }
  return <span aria-hidden="true" className={'robot-avatar ' + className} style={{ backgroundPosition: positions[robotPresets.indexOf(preset)] }} />
}

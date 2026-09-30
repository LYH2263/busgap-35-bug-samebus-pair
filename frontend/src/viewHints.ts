// scope_helpers_ready_35
export function unifyStatusLabel(status: string): string {
  if (status === 'same_vehicle') return '同车接续'
  if (status === 'bunching' || status === 'short_turnaround' || status === 'bunching_saturated') return '串车'
  if (status === 'large_gap') return '大间隔'
  return '正常'
}

// 同车接续与串车/大间隔互斥：轴点颜色只按本次检测的判定走，
// 同车接续对用中性色，绝不标成串车红。
export function markColor(status: string | undefined): string {
  if (status === 'bunching') return 'var(--bg-red)'
  if (status === 'large_gap') return 'var(--bg-amber)'
  if (status === 'same_vehicle') return 'var(--bg-dim)'
  return 'var(--bg-cyan)'
}

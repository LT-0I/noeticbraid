import { useTranslation } from 'react-i18next'

import type { CandidateLesson, CapabilityStatus, R6GateStatus } from '@/types/contracts'

import { Badge, type BadgeTone } from './Badge'

type LegacyBadgeStyle = {
  tone: BadgeTone
  legacyColor: string
  expired?: boolean
}

export function r6GateStatus(candidate: CandidateLesson): R6GateStatus {
  const gate = candidate.r6_gate
  if (!gate) return 'candidate'
  if (gate.adopted_at) return 'confirmed'
  if (gate.reuse_count >= 3 && gate.ledger_evidence_refs.length >= 1) return 'confirmed'
  if (gate.expires_at && Date.now() > Date.parse(gate.expires_at)) return 'expired'
  return 'candidate'
}

function r6GateBadgeStyle(status: R6GateStatus): LegacyBadgeStyle {
  if (status === 'confirmed') return { tone: 'success', legacyColor: 'green' }
  if (status === 'expired') return { tone: 'info', legacyColor: 'darkgray', expired: true }
  return { tone: 'warning', legacyColor: 'gray' }
}

export function capabilityTone(status: CapabilityStatus): LegacyBadgeStyle {
  if (status === 'healthy' || status === 'available') return { tone: 'success', legacyColor: 'green' }
  if (status === 'unhealthy' || status === 'unavailable') return { tone: 'danger', legacyColor: 'red' }
  if (status === 'degraded') return { tone: 'warning', legacyColor: 'gray' }
  if (status === 'not_implemented') return { tone: 'info', legacyColor: 'gray' }
  return { tone: 'neutral', legacyColor: 'gray' }
}

export function R6GateBadge({ candidate }: { candidate: CandidateLesson }) {
  const { t } = useTranslation()
  const status = r6GateStatus(candidate)
  const badgeStyle = r6GateBadgeStyle(status)

  return (
    <Badge
      data-testid={`r6-gate-${candidate.candidate_id}`}
      className={badgeStyle.expired ? 'ui-badge--expired' : undefined}
      tone={badgeStyle.tone}
      legacyColor={badgeStyle.legacyColor}
      legacyTextDecoration={badgeStyle.expired ? 'line-through' : undefined}
    >
      {t('routes.omcIngest.r6Gate', { status: t(`status.${status}`) })}
    </Badge>
  )
}

export function CapabilityStatusBadge({
  capabilityId,
  status,
  result = false,
}: {
  capabilityId: string
  status: CapabilityStatus
  result?: boolean
}) {
  const { t } = useTranslation()
  const badgeStyle = capabilityTone(status)

  return (
    <Badge
      data-testid={`${result ? 'result-status-badge' : 'status-badge'}-${capabilityId}`}
      tone={badgeStyle.tone}
      legacyColor={badgeStyle.legacyColor}
    >
      {t(`status.${status}`)}
    </Badge>
  )
}

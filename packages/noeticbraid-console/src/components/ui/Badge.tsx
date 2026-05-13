import type { CSSProperties, HTMLAttributes, ReactNode } from 'react'

import { cx } from './utils'
import styles from './Badge.module.css'

export type BadgeTone = 'neutral' | 'success' | 'warning' | 'error' | 'danger' | 'info'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode
  tone?: BadgeTone
  dot?: boolean
  legacyColor?: string
  legacyTextDecoration?: CSSProperties['textDecoration']
}

export function Badge({
  children,
  className,
  tone = 'neutral',
  dot = false,
  legacyColor,
  legacyTextDecoration,
  style,
  ...props
}: BadgeProps) {
  const legacyStyle: CSSProperties = {
    ...(legacyColor ? { color: legacyColor } : {}),
    ...(legacyTextDecoration ? { textDecoration: legacyTextDecoration } : {}),
  }

  return (
    <span
      className={cx(styles.badge, styles[tone], dot && styles.withDot, className)}
      style={{ ...legacyStyle, ...style }}
      {...props}
    >
      {children}
    </span>
  )
}

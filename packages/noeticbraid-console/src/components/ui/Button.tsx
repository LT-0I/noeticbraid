import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { cx } from './utils'
import styles from './Button.module.css'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost'
export type ButtonSize = 'sm' | 'md' | 'lg'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode
  variant?: ButtonVariant
  size?: ButtonSize
  leadingIcon?: ReactNode
}

export function Button({ children, className, variant = 'secondary', size = 'md', leadingIcon, ...props }: ButtonProps) {
  return (
    <button className={cx(styles.button, styles[variant], styles[size], className)} {...props}>
      {leadingIcon ? <span className={styles.icon}>{leadingIcon}</span> : null}
      <span>{children}</span>
    </button>
  )
}

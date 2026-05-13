import type { HTMLAttributes, ReactNode } from 'react'

import { cx } from './utils'
import styles from './Card.module.css'

export interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode
  interactive?: boolean
}

export function Card({ children, className, interactive = false, ...props }: CardProps) {
  return (
    <section className={cx(styles.card, interactive && styles.interactive, className)} {...props}>
      {children}
    </section>
  )
}

export function CardHeader({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx(styles.header, className)} {...props}>
      {children}
    </div>
  )
}

export function CardTitle({ children, className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={cx(styles.title, className)} {...props}>
      {children}
    </h2>
  )
}

export function CardDescription({ children, className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cx(styles.description, className)} {...props}>
      {children}
    </p>
  )
}

export function CardMeta({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx(styles.meta, className)} {...props}>
      {children}
    </div>
  )
}

export function CardBody({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx(styles.body, className)} {...props}>
      {children}
    </div>
  )
}

export function CardFooter({ children, className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx(styles.footer, className)} {...props}>
      {children}
    </div>
  )
}

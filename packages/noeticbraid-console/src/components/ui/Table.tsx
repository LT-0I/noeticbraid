import type { ReactNode, TableHTMLAttributes } from 'react'

import { cx } from './utils'
import styles from './Table.module.css'

export interface Column<T> {
  key: keyof T | string
  label: ReactNode
  width?: number | string
  align?: 'left' | 'center' | 'right'
  sortable?: boolean
  render?: (row: T) => ReactNode
}

export interface TableProps<T> extends Omit<TableHTMLAttributes<HTMLTableElement>, 'children'> {
  columns?: Array<Column<T>>
  data?: T[]
  rowKey?: (row: T, index: number) => string
  children?: ReactNode
  wrap?: boolean
}

function valueFor<T>(row: T, key: keyof T | string): ReactNode {
  const value = (row as Record<string, unknown>)[String(key)]
  if (value === null || value === undefined) return null
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

export function Table<T>({ columns, data, rowKey, children, className, wrap = false, ...props }: TableProps<T>) {
  const table = (
    <table className={cx(styles.table, className)} {...props}>
      {children ?? (
        <>
          <thead>
            <tr>
              {columns?.map((column) => (
                <th
                  key={String(column.key)}
                  className={cx(column.sortable && styles.sortable, column.align === 'right' && styles.alignRight, column.align === 'center' && styles.alignCenter)}
                  style={column.width ? { width: column.width } : undefined}
                >
                  {column.label}{column.sortable ? '↕' : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data?.map((row, index) => (
              <tr key={rowKey ? rowKey(row, index) : index}>
                {columns?.map((column) => (
                  <td
                    key={String(column.key)}
                    className={cx(column.align === 'right' && styles.alignRight, column.align === 'center' && styles.alignCenter)}
                  >
                    {column.render ? column.render(row) : valueFor(row, column.key)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </>
      )}
    </table>
  )

  return wrap ? <div className={styles.wrap}>{table}</div> : table
}

export function TableWrap({ children }: { children: ReactNode }) {
  return <div className={styles.wrap}>{children}</div>
}

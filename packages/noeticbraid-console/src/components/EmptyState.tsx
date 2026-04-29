export function EmptyState({ message }: { message: string }) {
  return (
    <div data-testid="empty-state" role="status" style={{ padding: 32, textAlign: 'center', color: '#888' }}>
      {message}
    </div>
  )
}

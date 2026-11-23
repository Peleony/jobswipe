import { CheckCircle2, CircleAlert, X } from 'lucide-react'

export default function Toast({ toast, onClose }) {
  if (!toast) return null
  const isError = toast.type === 'error'

  return (
    <div
      className={`toast ${isError ? 'toast-error' : 'toast-success'}`}
      role={isError ? 'alert' : 'status'}
      aria-live={isError ? 'assertive' : 'polite'}
    >
      {isError ? <CircleAlert size={19} /> : <CheckCircle2 size={19} />}
      <p>{toast.message}</p>
      <button className="toast-close" type="button" onClick={onClose} aria-label="Zamknij powiadomienie">
        <X size={17} />
      </button>
    </div>
  )
}

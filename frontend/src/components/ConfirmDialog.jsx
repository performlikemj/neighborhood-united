import React, { useEffect, useRef, useCallback } from 'react'

export default function ConfirmDialog({ open, title='Confirm', message, confirmLabel='Confirm', cancelLabel='Cancel', onConfirm, onCancel, busy=false }){
  const cancelRef = useRef(null)
  const dialogRef = useRef(null)

  // Focus the cancel button when dialog opens
  useEffect(() => {
    if (open && cancelRef.current) {
      cancelRef.current.focus()
    }
  }, [open])

  // Handle Escape key to close
  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape' && !busy) {
      onCancel()
    }
  }, [busy, onCancel])

  if (!open) return null
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="confirm-dialog-title" onKeyDown={handleKeyDown} ref={dialogRef}>
      <div className="modal">
        <h3 id="confirm-dialog-title" style={{marginTop:0}}>{title}</h3>
        {message && <p className="muted" style={{marginTop:'.35rem'}}>{message}</p>}
        <div style={{marginTop:'1rem', display:'flex', justifyContent:'flex-end', gap:'.5rem'}}>
          <button ref={cancelRef} className="btn btn-outline" type="button" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
          <button className="btn btn-danger" type="button" onClick={onConfirm} disabled={busy}>{busy ? 'Working…' : confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}

import React from 'react'

export default function ConfirmDialog({ open, title='Confirm', message, confirmLabel='Confirm', cancelLabel='Cancel', onConfirm, onCancel, busy=false }){
  if (!open) return null
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal">
        <h3 style={{marginTop:0}}>{title}</h3>
        {message && <p className="muted" style={{marginTop:'.35rem'}}>{message}</p>}
        <div style={{marginTop:'1rem', display:'flex', justifyContent:'flex-end', gap:'.5rem'}}>
          <button className="btn btn-outline" type="button" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
          <button className="btn btn-danger" type="button" onClick={onConfirm} disabled={busy}>{busy ? 'Working…' : confirmLabel}</button>
        </div>
      </div>
    </div>
  )
}

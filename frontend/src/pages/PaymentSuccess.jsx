import React, { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'

export default function PaymentSuccess() {
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState('loading') // loading, success, error, pending
  const [paymentData, setPaymentData] = useState(null)
  const [errorMessage, setErrorMessage] = useState('')

  const linkId = searchParams.get('link_id')
  const sessionId = searchParams.get('session_id')

  useEffect(() => {
    const verifyPayment = async () => {
      if (!linkId || !sessionId) {
        setStatus('error')
        setErrorMessage('Missing payment information. Please contact the chef if you completed payment.')
        return
      }

      try {
        const response = await api.post(
          `/chefs/api/payment-links/${linkId}/verify/`,
          { session_id: sessionId },
          { skipUserId: true }
        )

        const data = response.data
        
        if (data.status === 'paid') {
          setStatus('success')
          setPaymentData(data)
        } else {
          setStatus('pending')
          setPaymentData(data)
        }
      } catch (err) {
        console.error('Failed to verify payment:', err)
        setStatus('error')
        setErrorMessage(
          err.response?.data?.error || 
          'Unable to verify payment status. Your payment may still be processing.'
        )
      }
    }

    verifyPayment()
  }, [linkId, sessionId])

  if (status === 'loading') {
    return (
      <div className="container">
        <div className="card" style={{ textAlign: 'center', maxWidth: '500px', margin: '2rem auto' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
          <h2 style={{ marginTop: 0 }}>Verifying Payment...</h2>
          <p className="muted">Please wait while we confirm your payment.</p>
        </div>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="container">
        <div className="card" style={{ textAlign: 'center', maxWidth: '500px', margin: '2rem auto', borderColor: '#28a745' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>✅</div>
          <h2 style={{ marginTop: 0, color: '#28a745' }}>Payment Successful!</h2>
          <p className="muted">Thank you for your payment.</p>
          
          {paymentData && (
            <div style={{ 
              backgroundColor: 'var(--surface-2, #f8f9fa)', 
              padding: '16px', 
              borderRadius: '8px',
              marginTop: '16px',
              marginBottom: '16px'
            }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: 'var(--text, #333)' }}>
                {paymentData.amount_display}
              </div>
              {paymentData.paid_at && (
                <div style={{ fontSize: '14px', color: 'var(--muted, #666)', marginTop: '8px' }}>
                  Paid on {new Date(paymentData.paid_at).toLocaleDateString()}
                </div>
              )}
            </div>
          )}
          
          <p style={{ fontSize: '14px', color: 'var(--muted, #666)' }}>
            The chef has been notified of your payment. You can close this window.
          </p>
          
          <div style={{ display: 'flex', gap: '.5rem', justifyContent: 'center', marginTop: '1rem' }}>
            <Link to="/" className="btn btn-primary">Go to Homepage</Link>
          </div>
        </div>
      </div>
    )
  }

  if (status === 'pending') {
    return (
      <div className="container">
        <div className="card" style={{ textAlign: 'center', maxWidth: '500px', margin: '2rem auto', borderColor: '#ffc107' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px' }}>⏳</div>
          <h2 style={{ marginTop: 0, color: '#ffc107' }}>Payment Processing</h2>
          <p className="muted">Your payment is being processed. This may take a moment.</p>
          <p style={{ fontSize: '14px', color: 'var(--muted, #666)' }}>
            If you completed the payment, please wait a few minutes and refresh this page.
            The chef will be notified once the payment is confirmed.
          </p>
          
          <div style={{ display: 'flex', gap: '.5rem', justifyContent: 'center', marginTop: '1rem' }}>
            <button 
              className="btn btn-primary" 
              onClick={() => window.location.reload()}
            >
              Refresh
            </button>
            <Link to="/" className="btn btn-outline">Go to Homepage</Link>
          </div>
        </div>
      </div>
    )
  }

  // Error state
  return (
    <div className="container">
      <div className="card" style={{ textAlign: 'center', maxWidth: '500px', margin: '2rem auto', borderColor: '#dc3545' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>⚠️</div>
        <h2 style={{ marginTop: 0, color: '#dc3545' }}>Verification Issue</h2>
        <p className="muted">{errorMessage}</p>
        <p style={{ fontSize: '14px', color: 'var(--muted, #666)' }}>
          If you believe your payment was successful, please contact the chef directly.
          They can verify your payment status from their dashboard.
        </p>
        
        <div style={{ display: 'flex', gap: '.5rem', justifyContent: 'center', marginTop: '1rem' }}>
          <Link to="/" className="btn btn-primary">Go to Homepage</Link>
        </div>
      </div>
    </div>
  )
}


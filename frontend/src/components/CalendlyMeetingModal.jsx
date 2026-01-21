/**
 * CalendlyMeetingModal Component
 *
 * Shows the Calendly booking interface for chef verification meetings.
 * Tracks whether the chef has scheduled their meeting.
 */

import React, { useState } from 'react'
import { api } from '../api'

export default function CalendlyMeetingModal({
  isOpen,
  onClose,
  onScheduled,
  meetingConfig = {}
}) {
  const [marking, setMarking] = useState(false)
  const [error, setError] = useState(null)

  const handleMarkScheduled = async () => {
    setMarking(true)
    setError(null)
    try {
      await api.post('/chefs/api/me/verification-meeting/schedule/')
      if (onScheduled) onScheduled()
      onClose()
    } catch (err) {
      console.error('Failed to mark as scheduled:', err)
      setError('Failed to confirm scheduling. Please try again.')
    } finally {
      setMarking(false)
    }
  }

  if (!isOpen) return null

  const {
    calendly_url,
    meeting_title = 'Schedule Verification Call',
    meeting_description,
    status,
    scheduled_at,
    is_complete
  } = meetingConfig

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content calendly-modal" onClick={e => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close">
          <i className="fa-solid fa-times"></i>
        </button>

        <div className="modal-header">
          <h2>{meeting_title}</h2>
          {meeting_description && (
            <p className="muted">{meeting_description}</p>
          )}
        </div>

        <div className="modal-body">
          {is_complete ? (
            <div className="meeting-status meeting-complete">
              <div className="status-icon success">
                <i className="fa-solid fa-check-circle"></i>
              </div>
              <h3>Meeting Completed</h3>
              <p className="muted">Your verification call has been completed. Thank you!</p>
            </div>
          ) : status === 'scheduled' ? (
            <div className="meeting-status meeting-scheduled">
              <div className="status-icon info">
                <i className="fa-solid fa-calendar-check"></i>
              </div>
              <h3>Meeting Scheduled</h3>
              <p className="muted">Your verification call is scheduled. We'll see you soon!</p>
              {scheduled_at && (
                <p className="scheduled-time">
                  <i className="fa-regular fa-clock"></i>
                  {new Date(scheduled_at).toLocaleString()}
                </p>
              )}
              <p className="reschedule-note muted">
                Need to reschedule? You can do so directly in Calendly.
              </p>
            </div>
          ) : (
            <div className="meeting-booking">
              <p className="booking-intro">
                Before you can start accepting orders, we'd like to have a quick call
                to learn more about you and your culinary experience.
              </p>

              {calendly_url && (
                <>
                  <a
                    href={calendly_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn btn-primary btn-lg calendly-btn"
                  >
                    <i className="fa-solid fa-calendar-plus"></i>
                    Book Your Call
                  </a>

                  <div className="booking-confirm">
                    <p className="muted">After booking your call in Calendly, click below to confirm:</p>
                    {error && <p className="error-text">{error}</p>}
                    <button
                      className="btn btn-outline"
                      onClick={handleMarkScheduled}
                      disabled={marking}
                    >
                      {marking ? (
                        <>
                          <i className="fa-solid fa-spinner fa-spin"></i>
                          Confirming...
                        </>
                      ) : (
                        "I've Scheduled My Call"
                      )}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        <style>{`
          .calendly-modal {
            max-width: 480px;
            padding: 1.5rem;
          }

          .calendly-modal .modal-header {
            margin-bottom: 1.5rem;
          }

          .calendly-modal .modal-header h2 {
            margin: 0 0 0.5rem 0;
            font-size: 1.25rem;
            font-weight: 600;
          }

          .calendly-modal .modal-header .muted {
            margin: 0;
            font-size: 0.9rem;
          }

          .meeting-status {
            text-align: center;
            padding: 1.5rem 1rem;
          }

          .status-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
          }

          .status-icon.success {
            color: var(--success);
          }

          .status-icon.info {
            color: var(--info);
          }

          .meeting-status h3 {
            margin: 0 0 0.5rem 0;
            font-size: 1.1rem;
          }

          .scheduled-time {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            margin: 1rem 0;
            padding: 0.75rem;
            background: var(--surface-2);
            border-radius: 8px;
            font-weight: 500;
          }

          .reschedule-note {
            font-size: 0.85rem;
            margin-top: 1rem;
          }

          .meeting-booking {
            text-align: center;
          }

          .booking-intro {
            margin: 0 0 1.5rem 0;
            line-height: 1.6;
          }

          .calendly-btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            width: 100%;
            justify-content: center;
            padding: 0.875rem 1.5rem;
          }

          .booking-confirm {
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid var(--border);
          }

          .booking-confirm .muted {
            margin: 0 0 1rem 0;
            font-size: 0.9rem;
          }

          .booking-confirm .btn {
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
          }

          .error-text {
            color: var(--danger);
            font-size: 0.9rem;
            margin: 0 0 0.75rem 0;
          }
        `}</style>
      </div>
    </div>
  )
}

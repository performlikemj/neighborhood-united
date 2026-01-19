import React from 'react'

/**
 * Household members section with add/edit capabilities
 */
export default function HouseholdSection({
  client,
  canEdit,
  householdMembers,
  showAddMember,
  editingMember,
  memberForm,
  saving,
  onSetMemberForm,
  onStartAddMember,
  onStartEditMember,
  onDeleteMember,
  onSubmitMember,
  onCancelMember,
  DIETARY_OPTIONS,
  ALLERGY_OPTIONS,
  ChipSelector,
  MemberForm
}) {
  const memberCount = (householdMembers?.length || 0) + 1

  return (
    <div className="cc-section">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
        <h4 className="cc-section-title" style={{ margin: 0 }}>
          👥 Household ({memberCount})
          {client.household_size > memberCount && (
            <span style={{ fontWeight: 400, color: 'var(--warning)', marginLeft: '0.5rem', fontSize: '0.75rem' }}>
              ({client.household_size} claimed)
            </span>
          )}
        </h4>
        {canEdit && !showAddMember && !editingMember && (
          <button
            className="cc-btn cc-btn-secondary cc-btn-sm"
            onClick={onStartAddMember}
          >
            + Add Member
          </button>
        )}
      </div>

      {/* Household members list */}
      {householdMembers?.length > 0 ? (
        householdMembers.map(member => (
          editingMember?.id === member.id ? (
            <MemberForm
              key={member.id}
              isEditing={true}
              memberForm={memberForm}
              saving={saving}
              onSetMemberForm={onSetMemberForm}
              onSubmit={onSubmitMember}
              onCancel={onCancelMember}
              DIETARY_OPTIONS={DIETARY_OPTIONS}
              ALLERGY_OPTIONS={ALLERGY_OPTIONS}
              ChipSelector={ChipSelector}
            />
          ) : (
            <div key={member.id} className="cc-household-member">
              <div className="cc-household-header">
                <span className="cc-household-name">{member.name}</span>
                <div className="cc-household-meta">
                  <span>{member.relationship}{member.age && `, ${member.age}y`}</span>
                  {canEdit && (
                    <>
                      <button
                        onClick={() => onStartEditMember(member)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0.2rem', fontSize: '0.8rem' }}
                        title="Edit member"
                      >
                        ✏️
                      </button>
                      <button
                        onClick={() => onDeleteMember(member.id)}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '0.2rem', fontSize: '0.8rem', color: 'var(--danger)' }}
                        title="Remove member"
                      >
                        🗑️
                      </button>
                    </>
                  )}
                </div>
              </div>

              {(member.dietary_preferences?.length > 0 || member.allergies?.filter(a => a && a !== 'None').length > 0) && (
                <div className="cc-household-tags">
                  {member.dietary_preferences?.map(p => (
                    <span key={p} className="cc-household-tag cc-household-tag-dietary">{p}</span>
                  ))}
                  {member.allergies?.filter(a => a && a !== 'None').map(a => (
                    <span key={a} className="cc-household-tag cc-household-tag-allergy">⚠ {a}</span>
                  ))}
                </div>
              )}

              {member.notes && (
                <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--muted)', fontStyle: 'italic' }}>
                  {member.notes}
                </div>
              )}
            </div>
          )
        ))
      ) : (
        !showAddMember && (
          <div className="cc-info-box" style={{ color: 'var(--muted)', fontSize: '0.9rem' }}>
            {client.household_size > 1 ? (
              <>
                <span style={{ color: 'var(--warning)' }}>⚠</span> Customer indicated {client.household_size} household members but profiles haven't been added yet.
              </>
            ) : (
              'No additional household members'
            )}
          </div>
        )
      )}

      {/* Add member form */}
      {showAddMember && (
        <MemberForm
          isEditing={false}
          memberForm={memberForm}
          saving={saving}
          onSetMemberForm={onSetMemberForm}
          onSubmit={onSubmitMember}
          onCancel={onCancelMember}
          DIETARY_OPTIONS={DIETARY_OPTIONS}
          ALLERGY_OPTIONS={ALLERGY_OPTIONS}
          ChipSelector={ChipSelector}
        />
      )}
    </div>
  )
}

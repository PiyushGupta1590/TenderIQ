import { useState } from 'react'
import { evaluateApi, bidderApi } from '../api/client'

function VerdictChip({ verdict }) {
  const cls = { ELIGIBLE: 'chip-eligible', NOT_ELIGIBLE: 'chip-not-eligible', MANUAL_REVIEW: 'chip-manual' }
  return <span className={`chip ${cls[verdict] || 'chip-queued'}`}>{verdict?.replace('_', ' ')}</span>
}

function VerdictIcon({ verdict }) {
  if (verdict === 'ELIGIBLE') return <span className="material-symbols-outlined icon-filled" style={{ color: '#16a34a', fontSize: 22 }}>check_circle</span>
  if (verdict === 'NOT_ELIGIBLE') return <span className="material-symbols-outlined icon-filled" style={{ color: '#dc2626', fontSize: 22 }}>cancel</span>
  return <span className="material-symbols-outlined icon-filled" style={{ color: '#f59e0b', fontSize: 22 }}>warning</span>
}

export default function Stage3({ toast, onDone }) {
  const [running, setRunning] = useState(false)
  const [report, setReport] = useState(null)
  const [selected, setSelected] = useState(null)
  const [overrideModal, setOverrideModal] = useState(null)
  const [overrideNote, setOverrideNote] = useState('')
  const [deleteModal, setDeleteModal] = useState(null)   // bidder row to delete
  const [deleting, setDeleting] = useState(false)

  const runEval = async () => {
    setRunning(true)
    try {
      const res = await evaluateApi.run()
      setReport(res.data)
      setSelected(res.data.bidder_results[0])
      toast(`Evaluation complete — ${res.data.eligible_count} eligible, ${res.data.not_eligible_count} rejected, ${res.data.manual_review_count} need review`, 'success')
    } catch (e) { toast(e.response?.data?.detail || 'Evaluation failed', 'error') }
    finally { setRunning(false) }
  }

  const doOverride = async (verdict) => {
    if (!overrideModal || !report) return
    try {
      await evaluateApi.override(report.report_id, overrideModal.bidder_id, verdict, overrideNote)
      setReport(p => ({
        ...p,
        bidder_results: p.bidder_results.map(b =>
          b.bidder_id === overrideModal.bidder_id ? { ...b, overall_verdict: verdict, officer_override: verdict, officer_override_note: overrideNote } : b
        )
      }))
      if (selected?.bidder_id === overrideModal.bidder_id) setSelected(p => ({ ...p, overall_verdict: verdict, officer_override: verdict }))
      setOverrideModal(null); setOverrideNote('')
      toast(`Verdict overridden to ${verdict}`, 'info')
    } catch { toast('Override failed', 'error') }
  }

  const deleteBidder = async () => {
    if (!deleteModal || !report) return
    setDeleting(true)
    try {
      await bidderApi.remove(deleteModal.bidder_id)
      const updated = report.bidder_results.filter(b => b.bidder_id !== deleteModal.bidder_id)
      setReport(p => ({
        ...p,
        bidder_results: updated,
        total_bidders: (p.total_bidders || 0) - 1,
        eligible_count:       deleteModal.overall_verdict === 'ELIGIBLE'       ? (p.eligible_count - 1)       : p.eligible_count,
        not_eligible_count:   deleteModal.overall_verdict === 'NOT_ELIGIBLE'   ? (p.not_eligible_count - 1)   : p.not_eligible_count,
        manual_review_count:  deleteModal.overall_verdict === 'MANUAL_REVIEW'  ? (p.manual_review_count - 1)  : p.manual_review_count,
      }))
      if (selected?.bidder_id === deleteModal.bidder_id) setSelected(updated[0] || null)
      toast(`Bidder "${deleteModal.bidder_name}" removed from the matrix`, 'info')
      setDeleteModal(null)
    } catch { toast('Delete failed — please try again', 'error') }
    finally { setDeleting(false) }
  }

  return (
    <div className="page">
      {overrideModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ width: 440, padding: 24 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--primary)', marginBottom: 4 }}>Officer Override</h3>
            <p style={{ fontSize: 12, color: 'var(--secondary)', marginBottom: 16 }}>Override verdict for <strong>{overrideModal.bidder_name}</strong>. This action is logged.</p>
            <label>Justification Note</label>
            <textarea rows={3} value={overrideNote} onChange={e => setOverrideNote(e.target.value)} placeholder="Required — reason for override..." style={{ marginBottom: 16, resize: 'vertical', fontFamily: 'inherit' }} />
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setOverrideModal(null)}>Cancel</button>
              <button className="btn btn-danger btn-sm" onClick={() => doOverride('NOT_ELIGIBLE')}>Mark Not Eligible</button>
              <button className="btn btn-primary btn-sm" onClick={() => doOverride('ELIGIBLE')}>Override to Eligible</button>
            </div>
          </div>
        </div>
      )}

      {deleteModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 210, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div className="card" style={{ width: 400, padding: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
              <span className="material-symbols-outlined" style={{ fontSize: 28, color: '#dc2626' }}>delete_forever</span>
              <h3 style={{ fontSize: 15, fontWeight: 700, color: 'var(--primary)', margin: 0 }}>Remove Bidder</h3>
            </div>
            <p style={{ fontSize: 13, color: 'var(--secondary)', marginBottom: 20, lineHeight: 1.6 }}>
              Are you sure you want to permanently remove <strong style={{ color: 'var(--primary)' }}>{deleteModal.bidder_name}</strong> from the decision matrix?
              <br /><span style={{ fontSize: 11, color: '#dc2626' }}>This will delete all associated documents and cannot be undone.</span>
            </p>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-secondary btn-sm" onClick={() => setDeleteModal(null)} disabled={deleting}>Cancel</button>
              <button
                className="btn btn-danger btn-sm"
                onClick={deleteBidder}
                disabled={deleting}
                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
              >
                {deleting
                  ? <><div className="spinner" style={{ width: 12, height: 12, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', borderTopColor: '#fff' }} /> Removing…</>
                  : <><span className="material-symbols-outlined" style={{ fontSize: 14 }}>delete</span> Yes, Remove</>
                }
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: 'var(--secondary)', marginBottom: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="badge badge-blue">Stage 3</span><span>→ Eligibility Decision Matrix</span>
          </div>
          <h1 className="section-title">Eligibility Decisioning</h1>
          <p className="section-sub">AI compares bidder data against approved tender rules. Manual review cases are flagged for officer action.</p>
        </div>
        <div className="page-header-actions">
          {!report && (
            <button className="btn btn-primary" onClick={runEval} disabled={running}>
              {running ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Evaluating…</> : <>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span> Run AI Evaluation
              </>}
            </button>
          )}
          {report && (
            <>
              <button className="btn btn-secondary" onClick={() => { setReport(null); setSelected(null) }}>Re-run</button>
              <button className="btn btn-primary" onClick={() => onDone(report.report_id)}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span> Generate Final Report
              </button>
            </>
          )}
        </div>
      </div>

      {!report && !running && (
        <div style={{ maxWidth: 560, margin: '60px auto', textAlign: 'center' }}>
          <span className="material-symbols-outlined" style={{ fontSize: 64, color: 'var(--primary)', opacity: 0.2, display: 'block', marginBottom: 16 }}>rule</span>
          <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--primary)', marginBottom: 8 }}>Ready to Evaluate</p>
          <p style={{ fontSize: 13, color: 'var(--secondary)', marginBottom: 24 }}>Click "Run AI Evaluation" to compare all uploaded bidder documents against the approved tender rules.</p>
          <button className="btn btn-primary" onClick={runEval}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>play_arrow</span> Run AI Evaluation
          </button>
        </div>
      )}

      {running && (
        <div style={{ maxWidth: 500, margin: '80px auto', textAlign: 'center' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 24 }}><div className="spinner" style={{ width: 48, height: 48, borderWidth: 4 }} /></div>
          <p style={{ fontWeight: 700, fontSize: 16, color: 'var(--primary)', marginBottom: 8 }}>AI Evaluation in Progress</p>
          <p style={{ fontSize: 12, color: 'var(--secondary)', marginBottom: 20 }}>Comparing extracted bidder data against approved tender rules…</p>
          <div className="processing-bar"><div className="processing-fill" style={{ width: '70%' }} /></div>
        </div>
      )}

      {report && (
        <div>
          {/* Decision Matrix */}
          <div className="card" style={{ marginBottom: 20 }}>
            <div className="card-header">
              <span className="card-header-title"><span className="material-symbols-outlined" style={{ fontSize: 16 }}>table_chart</span> Decision Matrix</span>
              <div style={{ display: 'flex', gap: 12, fontSize: 11, fontWeight: 600 }}>
                <span style={{ color: 'var(--eligible-text)' }}>✓ {report.eligible_count} Eligible</span>
                <span style={{ color: '#dc2626' }}>✗ {report.not_eligible_count} Rejected</span>
                <span style={{ color: '#92400e' }}>⚠ {report.manual_review_count} Review</span>
                <span style={{ color: 'var(--secondary)', borderLeft: '1px solid #e2e8f0', paddingLeft: 12 }}>Audit: {report.audit_log?.length || 0} entries</span>
              </div>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="matrix-table">
                <thead><tr>
                  <th>Bidder Entity</th>
                  {report.bidder_results[0]?.rule_results.filter(r => r.rule_mandatory).slice(0, 4).map(r => (
                    <th key={r.rule_id} title={r.rule_label}><span style={{ color: '#dc2626' }}>🔴</span> {r.rule_label.substring(0, 18)}</th>
                  ))}
                  {report.bidder_results[0]?.rule_results.filter(r => !r.rule_mandatory).slice(0, 2).map(r => (
                    <th key={r.rule_id} title={r.rule_label}><span style={{ color: '#f59e0b' }}>🟡</span> {r.rule_label.substring(0, 18)}</th>
                  ))}
                  <th>Overall</th>
                  <th>Mandatory</th>
                  <th>Action</th>
                </tr></thead>
                <tbody>
                  {report.bidder_results.map(br => (
                    <tr key={br.bidder_id}
                      className={br.overall_verdict === 'MANUAL_REVIEW' ? 'matrix-row-review' : br.overall_verdict === 'NOT_ELIGIBLE' ? 'matrix-row-ineligible' : ''}
                      style={{ cursor: 'pointer' }}
                      onClick={() => setSelected(br)}
                    >
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div style={{ width: 32, height: 32, borderRadius: '50%', background: br.overall_verdict === 'ELIGIBLE' ? '#dcfce7' : br.overall_verdict === 'NOT_ELIGIBLE' ? '#fee2e2' : '#fef3c7', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: 11, color: br.overall_verdict === 'ELIGIBLE' ? '#166534' : br.overall_verdict === 'NOT_ELIGIBLE' ? '#991b1b' : '#92400e' }}>
                            {br.bidder_name.substring(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div style={{ fontWeight: 600, color: 'var(--primary)', fontSize: 13 }}>{br.bidder_name}</div>
                            <div style={{ fontSize: 10, color: 'var(--secondary)' }}>{br.bidder_id.substring(0, 8).toUpperCase()}</div>
                          </div>
                        </div>
                      </td>
                      {(() => {
                        const mandatory = br.rule_results.filter(r => r.rule_mandatory)
                        const optional  = br.rule_results.filter(r => !r.rule_mandatory)
                        return [...mandatory.slice(0,4), ...optional.slice(0,2)].map(r => (
                          <td key={r.rule_id}><VerdictIcon verdict={r.verdict} /></td>
                        ))
                      })()}
                      <td><VerdictChip verdict={br.overall_verdict} /></td>
                      <td>
                        <VerdictChip verdict={br.mandatory_verdict || br.overall_verdict} />
                        {br.mandatory_fail_count > 0 && <span style={{ fontSize: 9, color: '#dc2626', fontWeight: 700, marginLeft: 4 }}>{br.mandatory_fail_count} fail</span>}
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          {br.overall_verdict === 'MANUAL_REVIEW' && (
                            <button className="btn btn-secondary btn-sm" onClick={e => { e.stopPropagation(); setOverrideModal(br); setOverrideNote('') }}>
                              Officer Review
                            </button>
                          )}
                          <button
                            title="Remove this bidder"
                            onClick={e => { e.stopPropagation(); setDeleteModal(br) }}
                            style={{
                              background: 'none', border: '1px solid #fecaca', borderRadius: 6,
                              cursor: 'pointer', padding: '3px 6px', display: 'flex', alignItems: 'center',
                              color: '#dc2626', transition: 'background 0.15s, transform 0.15s',
                            }}
                            onMouseEnter={e => { e.currentTarget.style.background = '#fee2e2'; e.currentTarget.style.transform = 'scale(1.1)' }}
                            onMouseLeave={e => { e.currentTarget.style.background = 'none'; e.currentTarget.style.transform = 'scale(1)' }}
                          >
                            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>delete</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* AI Reasoning Panel */}
          {selected && (
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 20 }}>
              <div className="card">
                <div className="card-header">
                  <span className="card-header-title">
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>psychology</span>
                    AI Reasoning: {selected.bidder_name}
                    {selected.officer_override && <span className="chip chip-processing" style={{ marginLeft: 8 }}>OVERRIDDEN</span>}
                  </span>
                  <VerdictChip verdict={selected.overall_verdict} />
                </div>
                <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {selected.rule_results.map(r => (
                    <div key={r.rule_id} className="reasoning-card" style={{ borderLeftColor: r.verdict === 'ELIGIBLE' ? '#16a34a' : r.verdict === 'NOT_ELIGIBLE' ? '#dc2626' : '#f59e0b' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                        <div style={{ fontWeight: 700, fontSize: 12, color: 'var(--primary)', display: 'flex', gap: 6, alignItems: 'center' }}>
                          <span style={{ fontSize: 10, background: '#eff4ff', color: 'var(--primary)', padding: '2px 6px', borderRadius: 4 }}>{r.rule_id}</span>
                          <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', borderRadius: 4, background: r.rule_mandatory !== false ? '#fee2e2' : '#fef3c7', color: r.rule_mandatory !== false ? '#dc2626' : '#92400e' }}>
                            {r.rule_mandatory !== false ? '🔴 M' : '🟡 O'}
                          </span>
                          {r.rule_label}
                        </div>
                        <VerdictChip verdict={r.verdict} />
                      </div>
                      <div className="evidence-block">
                        <div style={{ fontSize: 11, marginBottom: 6, color: 'var(--secondary)' }}>
                          Required: <strong style={{ color: 'var(--primary)' }}>{r.rule_description}</strong>
                        </div>
                        <div style={{ fontSize: 11, marginBottom: 6, color: 'var(--secondary)' }}>
                          Found: <strong style={{ color: 'var(--on-surface)' }}>{r.found_value ?? r.found_raw ?? 'Not found'}</strong>
                          {r.source_page && <span style={{ marginLeft: 8, color: 'var(--outline)', fontSize: 10 }}>Page {r.source_page}</span>}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--secondary)', lineHeight: 1.6 }}>{r.explanation}</div>
                        {r.needs_officer_action && (
                          <div style={{ marginTop: 8, padding: '6px 10px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 4, fontSize: 11, color: '#92400e', fontWeight: 600 }}>
                            ⚠ Officer intervention required for this rule
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Summary panel */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card" style={{ background: 'var(--primary-container)', color: 'white', border: 'none' }}>
                  <div style={{ padding: 20 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 16 }}>Batch Summary</h3>
                    {[['Total Bidders', report.total_bidders], ['Auto-Eligible', report.eligible_count], ['Auto-Rejected', report.not_eligible_count], ['Needs Review', report.manual_review_count]].map(([l, v]) => (
                      <div key={l} style={{ display: 'flex', justifyContent: 'space-between', paddingBottom: 10, marginBottom: 10, borderBottom: '1px solid rgba(255,255,255,0.15)' }}>
                        <span style={{ fontSize: 12, opacity: 0.8 }}>{l}</span>
                        <span style={{ fontSize: 18, fontWeight: 800 }}>{v}</span>
                      </div>
                    ))}
                    <div style={{ fontSize: 11, opacity: 0.7, marginTop: 8 }}>AI Confidence: {(report.ai_confidence_avg * 100).toFixed(1)}%</div>
                  </div>
                </div>

                <div className="card" style={{ padding: 16 }}>
                  <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 10 }}>Policy Reference</h4>
                  <p style={{ fontSize: 12, color: 'var(--secondary)', lineHeight: 1.6 }}>
                    TenderIQ provides AI decision support. Final accountability remains with the Procurement Officer. Manual review cases must be verified before finalisation.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="footer-bar">
        <span>SYSTEM ID: IQ-STAGE-3 | ENGINE: v1.0</span>
        <span>All decisions are logged and auditable</span>
      </div>
    </div>
  )
}

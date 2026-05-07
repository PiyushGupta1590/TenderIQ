import { useState, useEffect } from 'react'
import { reportApi, evaluateApi } from '../api/client'

function VerdictChip({ verdict }) {
  const cls = { ELIGIBLE: 'chip-eligible', NOT_ELIGIBLE: 'chip-not-eligible', MANUAL_REVIEW: 'chip-manual' }
  return <span className={`chip ${cls[verdict] || 'chip-queued'}`}>{verdict?.replace(/_/g, ' ')}</span>
}

function DonutChart({ eligible, notEligible, manual }) {
  const total = eligible + notEligible + manual || 1
  const r = 60, circ = 2 * Math.PI * r
  const e = (eligible / total) * circ, ne = (notEligible / total) * circ, m = (manual / total) * circ
  return (
    <svg width="160" height="160" viewBox="0 0 160 160">
      <circle cx="80" cy="80" r={r} fill="none" stroke="#e2e8f0" strokeWidth="22" />
      <circle cx="80" cy="80" r={r} fill="none" stroke="#166534" strokeWidth="22"
        strokeDasharray={`${e} ${circ - e}`} strokeDashoffset={circ * 0.25} strokeLinecap="butt" />
      <circle cx="80" cy="80" r={r} fill="none" stroke="#991b1b" strokeWidth="22"
        strokeDasharray={`${ne} ${circ - ne}`} strokeDashoffset={circ * 0.25 - e} strokeLinecap="butt" />
      <circle cx="80" cy="80" r={r} fill="none" stroke="#f59e0b" strokeWidth="22"
        strokeDasharray={`${m} ${circ - m}`} strokeDashoffset={circ * 0.25 - e - ne} strokeLinecap="butt" />
      <text x="80" y="76" textAnchor="middle" style={{ fontSize: 22, fontWeight: 800, fill: '#001e40', fontFamily: 'Public Sans' }}>{total}</text>
      <text x="80" y="92" textAnchor="middle" style={{ fontSize: 10, fill: '#515f74', fontFamily: 'Public Sans' }}>Total Bids</text>
    </svg>
  )
}

function AuditLogTable({ entries }) {
  const [expanded, setExpanded] = useState(false)
  const shown = expanded ? entries : entries.slice(0, 8)
  return (
    <div>
      <div style={{ overflowX: 'auto' }}>
        <table className="fields-table" style={{ width: '100%', fontSize: 11 }}>
          <thead><tr>
            <th>Bidder</th>
            <th>Type</th>
            <th>Rule</th>
            <th>Verdict</th>
            <th>Conf.</th>
            <th>Found</th>
            <th>Required</th>
            <th>Source Doc</th>
            <th>Pg</th>
          </tr></thead>
          <tbody>
            {shown.map((e, i) => {
              const vc = e.verdict === 'ELIGIBLE' ? '#166534' : e.verdict === 'NOT_ELIGIBLE' ? '#dc2626' : '#92400e'
              return (
                <tr key={i} title={e.decision_basis}>
                  <td style={{ fontWeight: 600, color: 'var(--primary)', maxWidth: 110, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.bidder_name}</td>
                  <td>
                    <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 5px', borderRadius: 3, background: e.rule_mandatory ? '#fee2e2' : '#fef3c7', color: e.rule_mandatory ? '#dc2626' : '#92400e' }}>
                      {e.rule_mandatory ? 'M' : 'O'}
                    </span>
                  </td>
                  <td style={{ maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.rule_label}</td>
                  <td><span style={{ fontWeight: 700, color: vc }}>{e.verdict.replace(/_/g, ' ')}</span></td>
                  <td style={{ textAlign: 'center' }}>{(e.confidence * 100).toFixed(0)}%</td>
                  <td style={{ maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.found_value || '—'}</td>
                  <td style={{ maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.required_value || '—'}</td>
                  <td style={{ maxWidth: 110, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--secondary)' }}>{e.source_document || '—'}</td>
                  <td style={{ textAlign: 'center', color: 'var(--secondary)' }}>{e.source_page || '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {entries.length > 8 && (
        <button onClick={() => setExpanded(p => !p)} style={{ marginTop: 10, fontSize: 11, color: 'var(--primary)', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 600 }}>
          {expanded ? '▲ Show less' : `▼ Show all ${entries.length} audit entries`}
        </button>
      )}
    </div>
  )
}

export default function Stage4({ toast, reportId }) {
  const [report, setReport]       = useState(null)
  const [loading, setLoading]     = useState(true)
  const [selected, setSelected]   = useState(null)
  const [finalizing, setFinalizing] = useState(false)
  const [tab, setTab]             = useState('details') // details | audit

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = reportId ? await reportApi.get(reportId) : await reportApi.latest()
        setReport(res.data)
        setSelected(res.data.bidder_results?.[0])
      } catch { toast('Could not load report — run evaluation first', 'error') }
      finally { setLoading(false) }
    }
    fetch()
  }, [reportId])

  const finalize = async () => {
    if (!report) return
    setFinalizing(true)
    try {
      await evaluateApi.finalize(report.report_id)
      setReport(p => ({ ...p, finalized: true }))
      toast('Tender evaluation finalized and locked', 'success')
    } catch { toast('Finalization failed', 'error') }
    finally { setFinalizing(false) }
  }

  if (loading) return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
      <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }} />
    </div>
  )

  if (!report) return (
    <div className="page">
      <div className="empty-state" style={{ marginTop: 80 }}>
        <span className="material-symbols-outlined">assignment_late</span>
        <p>No report available. Complete Stage 3 evaluation first.</p>
      </div>
    </div>
  )

  const auditEntries = report.audit_log || []

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: 'var(--secondary)', marginBottom: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="badge badge-blue">Stage 4</span><span>→ Final Evaluation Report</span>
            {report.finalized && <span className="chip chip-eligible">FINALIZED</span>}
          </div>
          <h1 className="section-title">Final Evaluation Report</h1>
          <p className="section-sub">Tender Ref: {report.tender_ref} · {report.tender_name}</p>
        </div>
        <div className="page-header-actions">
          <a href={reportApi.pdfUrl(report.report_id)} target="_blank" rel="noreferrer" className="btn btn-secondary">
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>picture_as_pdf</span>
            Download PDF
          </a>
          {!report.finalized && (
            <button className="btn btn-primary" onClick={finalize} disabled={finalizing}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>done_all</span>
              {finalizing ? 'Finalizing…' : 'Finalize & Lock'}
            </button>
          )}
        </div>
      </div>

      {/* KPI Bento */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr', gap: 14, marginBottom: 20 }}>
        {[
          { icon: 'verified', label: 'AI Confidence', value: `${(report.ai_confidence_avg * 100).toFixed(1)}%`, color: 'var(--primary)' },
          { icon: 'check_circle', label: 'Eligible', value: report.eligible_count, color: '#166534' },
          { icon: 'cancel', label: 'Not Eligible', value: report.not_eligible_count, color: '#dc2626' },
          { icon: 'warning', label: 'Manual Review', value: report.manual_review_count, color: '#92400e' },
          { icon: 'fact_check', label: 'Audit Entries', value: auditEntries.length, color: '#1e40af' },
        ].map(({ icon, label, value, color }) => (
          <div key={label} className="card" style={{ padding: 16 }}>
            <span className="material-symbols-outlined" style={{ color, marginBottom: 6, display: 'block', fontSize: 22 }}>{icon}</span>
            <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--secondary)' }}>{label}</div>
            <div style={{ fontSize: 24, fontWeight: 800, color }}>{value}</div>
          </div>
        ))}
      </div>

      {/* Tab Bar */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '2px solid #e2e8f0' }}>
        {[['details', 'Bidder Deep-Dive', 'person_search'], ['audit', `Audit Log (${auditEntries.length})`, 'fact_check']].map(([key, label, icon]) => (
          <button key={key} onClick={() => setTab(key)} style={{ padding: '8px 16px', fontSize: 12, fontWeight: 700, border: 'none', borderBottom: tab === key ? '2px solid var(--primary)' : '2px solid transparent', marginBottom: -2, background: 'none', cursor: 'pointer', color: tab === key ? 'var(--primary)' : 'var(--secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{icon}</span>{label}
          </button>
        ))}
      </div>

      {tab === 'details' && (
        <div style={{ display: 'grid', gridTemplateColumns: '300px 1fr', gap: 20, marginBottom: 24 }}>
          {/* Bidder sidebar */}
          <div className="card" style={{ display: 'flex', flexDirection: 'column' }}>
            <div className="card-header">
              <span className="card-header-title">
                <DonutChart eligible={report.eligible_count} notEligible={report.not_eligible_count} manual={report.manual_review_count} />
              </span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {report.bidder_results.map(br => (
                <div key={br.bidder_id}
                  style={{ padding: '12px 16px', cursor: 'pointer', background: selected?.bidder_id === br.bidder_id ? '#eff4ff' : 'white', borderLeft: selected?.bidder_id === br.bidder_id ? '4px solid var(--primary)' : '4px solid transparent', display: 'flex', justifyContent: 'space-between', alignItems: 'center', transition: 'all 0.15s' }}
                  onClick={() => setSelected(br)}
                >
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--primary)' }}>{br.bidder_name}</div>
                    <div style={{ fontSize: 10, color: 'var(--secondary)', marginTop: 2 }}>
                      {br.eligible_count}✓ {br.not_eligible_count}✗ {br.manual_review_count}⚠ · {br.mandatory_fail_count > 0 ? <span style={{ color: '#dc2626', fontWeight: 700 }}>{br.mandatory_fail_count} mand. fail</span> : 'no mand. fail'}
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, alignItems: 'flex-end' }}>
                    <VerdictChip verdict={br.overall_verdict} />
                    {br.mandatory_verdict && br.mandatory_verdict !== br.overall_verdict && (
                      <span style={{ fontSize: 9, color: '#64748b' }}>Mand: <VerdictChip verdict={br.mandatory_verdict} /></span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Deep dive */}
          {selected && (
            <div className="card" style={{ height: '100%' }}>
              <div className="card-header">
                <span className="card-header-title">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>visibility</span>
                  {selected.bidder_name}
                  {selected.officer_override && <span className="chip chip-processing" style={{ marginLeft: 8 }}>OVERRIDDEN</span>}
                </span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span style={{ fontSize: 10, color: 'var(--secondary)' }}>Overall:</span>
                  <VerdictChip verdict={selected.overall_verdict} />
                  <span style={{ fontSize: 10, color: 'var(--secondary)', marginLeft: 8 }}>Mandatory:</span>
                  <VerdictChip verdict={selected.mandatory_verdict || selected.overall_verdict} />
                </div>
              </div>
              <div style={{ padding: 20, display: 'grid', gridTemplateColumns: '260px 1fr', gap: 20, overflowY: 'auto', maxHeight: 'calc(100vh - 360px)' }}>
                {/* Rule list — mandatory first */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {['mandatory', 'optional'].map(type => {
                    const subset = selected.rule_results.filter(r => type === 'mandatory' ? r.rule_mandatory !== false : r.rule_mandatory === false)
                    if (!subset.length) return null
                    return (
                      <div key={type}>
                        <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: type === 'mandatory' ? '#dc2626' : '#92400e', marginBottom: 6 }}>
                          {type === 'mandatory' ? '🔴 Mandatory' : '🟡 Optional'}
                        </div>
                        {subset.map(r => (
                          <div key={r.rule_id} className="card" style={{ padding: 12, marginBottom: 8, borderLeftWidth: 4, borderLeftStyle: 'solid', borderLeftColor: r.verdict === 'ELIGIBLE' ? '#16a34a' : r.verdict === 'NOT_ELIGIBLE' ? '#dc2626' : '#f59e0b' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                              <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--primary)' }}>{r.rule_label}</span>
                              <VerdictChip verdict={r.verdict} />
                            </div>
                            <p style={{ fontSize: 10, color: 'var(--secondary)', marginBottom: 0 }}>{r.rule_description}</p>
                            {r.source_document && <p style={{ fontSize: 9, color: '#94a3b8', marginTop: 4 }}>📄 {r.source_document}{r.source_page ? ` · p${r.source_page}` : ''}</p>}
                          </div>
                        ))}
                      </div>
                    )
                  })}
                </div>

                {/* Explanations canvas */}
                <div>
                  <div style={{ background: 'var(--surface-low)', borderRadius: 8, padding: 16, minHeight: 400 }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--primary)', marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center' }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>summarize</span>
                      AI Criterion-Level Explanations
                    </div>
                    {selected.rule_results.map(r => (
                      <div key={r.rule_id} style={{ background: 'white', border: '1px solid var(--outline-var)', borderRadius: 6, padding: 14, marginBottom: 10 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, alignItems: 'flex-start' }}>
                          <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 6px', background: '#eff4ff', color: 'var(--primary)', borderRadius: 4 }}>{r.rule_id}</span>
                            <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 5px', borderRadius: 4, background: r.rule_mandatory !== false ? '#fee2e2' : '#fef3c7', color: r.rule_mandatory !== false ? '#dc2626' : '#92400e' }}>
                              {r.rule_mandatory !== false ? '🔴 MANDATORY' : '🟡 OPTIONAL'}
                            </span>
                            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--primary)' }}>{r.rule_label}</span>
                          </div>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                            <span style={{ fontSize: 10, color: 'var(--secondary)' }}>{(r.confidence * 100).toFixed(0)}% conf.</span>
                            <VerdictChip verdict={r.verdict} />
                          </div>
                        </div>
                        <p style={{ fontSize: 11, color: 'var(--secondary)', lineHeight: 1.6, marginBottom: r.needs_officer_action ? 8 : 0 }}>{r.explanation}</p>
                        {r.needs_officer_action && (
                          <div style={{ padding: '6px 10px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 4, fontSize: 11, color: '#92400e', fontWeight: 600 }}>
                            ⚠ Officer action required
                          </div>
                        )}
                        {r.officer_note && (
                          <div style={{ marginTop: 6, padding: '6px 10px', background: '#f0f9ff', borderRadius: 4, fontSize: 11, color: '#1e40af' }}>
                            <strong>Officer Note:</strong> {r.officer_note}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'audit' && (
        <div className="card" style={{ marginBottom: 24 }}>
          <div className="card-header">
            <span className="card-header-title">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>fact_check</span>
              Complete Audit Log — {auditEntries.length} Decision Records
            </span>
            <span style={{ fontSize: 11, color: 'var(--secondary)' }}>
              Immutable · Suitable for RTI / Procurement Proceedings · [M] = Mandatory, [O] = Optional
            </span>
          </div>
          <div style={{ padding: 16 }}>
            {auditEntries.length === 0 ? (
              <div className="empty-state">
                <span className="material-symbols-outlined">search_off</span>
                <p>No audit entries. Run evaluation to generate the audit log.</p>
              </div>
            ) : (
              <AuditLogTable entries={auditEntries} />
            )}
          </div>
        </div>
      )}

      <footer style={{ borderTop: '1px solid var(--outline-var)', paddingTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 24 }}>
        <div style={{ maxWidth: 560 }}>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--secondary)', marginBottom: 6 }}>Explainability & Auditability</div>
          <p style={{ fontSize: 12, color: 'var(--secondary)', lineHeight: 1.6 }}>
            Report generated by TenderIQ AI v2.0. Every criterion-level verdict is traced to the source document,
            page, and extracted value. The Audit Log tab provides a complete immutable decision trail suitable for
            formal government procurement proceedings and RTI responses. Final determination is subject to officer approval.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 24, flexShrink: 0 }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: 'var(--secondary)', fontWeight: 600, textTransform: 'uppercase' }}>Report ID</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--primary)', fontFamily: 'monospace' }}>{report.report_id.substring(0, 16).toUpperCase()}</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: 'var(--secondary)', fontWeight: 600, textTransform: 'uppercase' }}>Generated</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--primary)' }}>{new Date(report.generated_at).toLocaleString()}</div>
          </div>
        </div>
      </footer>
    </div>
  )
}

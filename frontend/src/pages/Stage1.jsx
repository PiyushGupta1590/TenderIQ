import { useState, useCallback } from 'react'
import { tenderApi } from '../api/client'

const CATEGORIES = ['financial', 'technical', 'administrative', 'compliance', 'eligibility']
const OPERATORS  = ['>=', '<=', '>', '<', '==', 'present', 'contains']

function catClass(cat) {
  const m = { financial: 'rule-cat-financial', technical: 'rule-cat-technical', administrative: 'rule-cat-administrative', compliance: 'rule-cat-compliance', eligibility: 'rule-cat-eligibility' }
  return m[cat] || ''
}

function RuleEditModal({ rule, onSave, onClose }) {
  const [label, setLabel] = useState(rule.label)
  const [value, setValue] = useState(rule.value ?? '')
  const [mandatory, setMandatory] = useState(rule.mandatory !== false)
  const [notes, setNotes] = useState(rule.notes ?? '')

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 480, padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--primary)' }}>Edit Rule</h3>
          <button className="icon-btn" onClick={onClose}><span className="material-symbols-outlined">close</span></button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div><label>Label</label><input type="text" value={label} onChange={e => setLabel(e.target.value)} /></div>
          {rule.value !== null && rule.value !== undefined && (
            <div><label>Threshold Value</label><input type="number" value={value} onChange={e => setValue(e.target.value)} /></div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input type="checkbox" id="mandatory-chk" checked={mandatory} onChange={e => setMandatory(e.target.checked)} style={{ width: 16, height: 16 }} />
            <label htmlFor="mandatory-chk" style={{ margin: 0, cursor: 'pointer', fontWeight: 600, color: mandatory ? '#dc2626' : '#64748b' }}>
              {mandatory ? '🔴 Mandatory (disqualifies bidder if failed)' : '🟡 Optional / Desirable'}
            </label>
          </div>
          <div><label>Officer Notes</label><textarea rows={3} value={notes} onChange={e => setNotes(e.target.value)} style={{ resize: 'vertical', fontFamily: 'inherit' }} /></div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button className="btn btn-secondary btn-sm" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={() => onSave({ label, value: value !== '' ? parseFloat(value) : null, mandatory, notes })}>Save Changes</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function AddRuleModal({ tenderId, onAdded, onClose }) {
  const [form, setForm] = useState({
    label: '', field: '', category: 'compliance', operator: 'present',
    value: '', unit: '', mandatory: true, notes: ''
  })
  const [saving, setSaving] = useState(false)

  const set = (k, v) => setForm(p => ({ ...p, [k]: v }))

  const save = async () => {
    if (!form.label.trim() || !form.field.trim()) return
    setSaving(true)
    try {
      const payload = {
        label: form.label.trim(),
        field: form.field.trim().toLowerCase().replace(/\s+/g, '_'),
        category: form.category,
        operator: form.operator,
        mandatory: form.mandatory,
        notes: form.notes || undefined,
        value: form.operator !== 'present' && form.value !== '' ? parseFloat(form.value) : undefined,
        unit: form.unit || undefined,
      }
      const res = await tenderApi.addRule(payload)
      onAdded(res.data)
    } catch { } finally { setSaving(false) }
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="card" style={{ width: 540, padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
          <h3 style={{ fontSize: 16, fontWeight: 700, color: 'var(--primary)' }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18, verticalAlign: 'middle', marginRight: 6 }}>add_circle</span>
            Add Manual Rule
          </h3>
          <button className="icon-btn" onClick={onClose}><span className="material-symbols-outlined">close</span></button>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div><label>Rule Label *</label><input placeholder="e.g. Valid GST Registration" value={form.label} onChange={e => set('label', e.target.value)} /></div>
            <div><label>Field Key *</label><input placeholder="e.g. gst_registration" value={form.field} onChange={e => set('field', e.target.value)} /></div>
            <div>
              <label>Category</label>
              <select value={form.category} onChange={e => set('category', e.target.value)}>
                {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <label>Operator</label>
              <select value={form.operator} onChange={e => set('operator', e.target.value)}>
                {OPERATORS.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            </div>
            {form.operator !== 'present' && (
              <>
                <div><label>Threshold Value</label><input type="number" placeholder="e.g. 50000000" value={form.value} onChange={e => set('value', e.target.value)} /></div>
                <div><label>Unit</label><input placeholder="INR / years / count" value={form.unit} onChange={e => set('unit', e.target.value)} /></div>
              </>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <input type="checkbox" id="add-mand" checked={form.mandatory} onChange={e => set('mandatory', e.target.checked)} style={{ width: 16, height: 16 }} />
            <label htmlFor="add-mand" style={{ margin: 0, cursor: 'pointer', fontWeight: 600, color: form.mandatory ? '#dc2626' : '#64748b' }}>
              {form.mandatory ? '🔴 Mandatory criterion' : '🟡 Optional / desirable'}
            </label>
          </div>
          <div><label>Notes</label><textarea rows={2} placeholder="e.g. Clause 4.3 of tender document" value={form.notes} onChange={e => set('notes', e.target.value)} style={{ resize: 'vertical', fontFamily: 'inherit' }} /></div>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
            <button className="btn btn-secondary btn-sm" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={save} disabled={saving || !form.label.trim() || !form.field.trim()}>
              {saving ? 'Saving…' : 'Add Rule'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function Stage1({ toast, onApproved }) {
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(false)
  const [ruleset, setRuleset] = useState(null)
  const [editRule, setEditRule] = useState(null)
  const [showAddRule, setShowAddRule] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [filter, setFilter] = useState('all') // all | mandatory | optional

  const handleFile = useCallback(async (file) => {
    if (!file || !file.name.toLowerCase().endsWith('.pdf')) { toast('Please upload a PDF file.', 'error'); return }
    setUploading(true)
    try {
      const res = await tenderApi.upload(file)
      setRuleset(res.data)
      toast(`Extracted ${res.data.rules.length} rules from ${res.data.uploaded_filename}`, 'success')
    } catch (e) {
      toast(e.response?.data?.detail || 'Upload failed.', 'error')
    } finally { setUploading(false) }
  }, [toast])

  const approve = async (ruleId) => {
    try {
      await tenderApi.approveRule(ruleId)
      setRuleset(p => ({ ...p, rules: p.rules.map(r => r.id === ruleId ? { ...r, approved: true } : r) }))
    } catch { toast('Failed to approve rule', 'error') }
  }

  const deleteRule = async (ruleId) => {
    try {
      await tenderApi.deleteRule(ruleId)
      setRuleset(p => ({ ...p, rules: p.rules.filter(r => r.id !== ruleId) }))
      toast('Rule removed', 'info')
    } catch { toast('Failed to delete rule', 'error') }
  }

  const saveEdit = async (updates) => {
    try {
      await tenderApi.updateRule(editRule.id, updates)
      setRuleset(p => ({ ...p, rules: p.rules.map(r => r.id === editRule.id ? { ...r, ...updates } : r) }))
      setEditRule(null)
      toast('Rule updated', 'success')
    } catch { toast('Failed to update rule', 'error') }
  }

  const handleAddRule = (newRule) => {
    setRuleset(p => ({ ...p, rules: [...p.rules, newRule] }))
    setShowAddRule(false)
    toast(`Rule "${newRule.label}" added and auto-approved`, 'success')
  }

  const approveAll = async () => {
    if (!ruleset?.rules?.length) { toast('No rules to approve', 'error'); return }
    setLoading(true)
    try {
      await tenderApi.approveAll()
      toast('All rules approved! Proceeding to Stage 2...', 'success')
      setTimeout(onApproved, 800)
    } catch (e) { toast(e.response?.data?.detail || 'Failed to approve rules', 'error') }
    finally { setLoading(false) }
  }

  const approveMandatoryOnly = async () => {
    if (!ruleset?.rules?.length) { toast('No rules to approve', 'error'); return }
    setLoading(true)
    try {
      await tenderApi.approveMandatoryOnly()
      toast('Mandatory rules approved! Proceeding to Stage 2...', 'success')
      setTimeout(onApproved, 800)
    } catch (e) { toast(e.response?.data?.detail || 'Failed', 'error') }
    finally { setLoading(false) }
  }

  const approvedCount  = ruleset?.rules?.filter(r => r.approved).length || 0
  const totalCount     = ruleset?.rules?.length || 0
  const mandatoryCount = ruleset?.rules?.filter(r => r.mandatory !== false).length || 0
  const optionalCount  = totalCount - mandatoryCount

  const visibleRules = (ruleset?.rules || []).filter(r => {
    if (filter === 'mandatory') return r.mandatory !== false
    if (filter === 'optional')  return r.mandatory === false
    return true
  })

  return (
    <div className="page">
      {editRule && <RuleEditModal rule={editRule} onSave={saveEdit} onClose={() => setEditRule(null)} />}
      {showAddRule && <AddRuleModal onAdded={handleAddRule} onClose={() => setShowAddRule(false)} />}

      <div className="page-header">
        <div className="page-header-left">
          <div style={{ fontSize: 12, color: 'var(--secondary)', marginBottom: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="badge badge-blue">Stage 1</span>
            <span>→ Rule Extraction & Approval</span>
          </div>
          <h1 className="section-title">Tender Rule Extraction</h1>
          <p className="section-sub">Upload a tender PDF. AI extracts eligibility rules — review, tag mandatory/optional, and approve before proceeding.</p>
        </div>
        <div className="page-header-actions">
          {ruleset && <button className="btn btn-secondary btn-sm" onClick={() => { setRuleset(null); tenderApi.reset().catch(() => {}) }}>Reset</button>}
          {ruleset && <button className="btn btn-secondary btn-sm" onClick={() => setShowAddRule(true)}>
            <span className="material-symbols-outlined" style={{ fontSize: 15 }}>add</span> Add Rule
          </button>}
          {ruleset && (
            <>
              <button className="btn btn-secondary" onClick={approveMandatoryOnly} disabled={loading || mandatoryCount === 0}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>verified</span>
                {loading ? 'Approving…' : `Mandatory Only (${mandatoryCount})`}
              </button>
              <button className="btn btn-primary" onClick={approveAll} disabled={loading || totalCount === 0}>
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>done_all</span>
                {loading ? 'Approving…' : `Approve All (${approvedCount}/${totalCount})`}
              </button>
            </>
          )}
        </div>
      </div>

      {!ruleset ? (
        <div style={{ maxWidth: 600, margin: '40px auto' }}>
          <div
            className={`dropzone ${dragActive ? 'active' : ''}`}
            onDragOver={e => { e.preventDefault(); setDragActive(true) }}
            onDragLeave={() => setDragActive(false)}
            onDrop={e => { e.preventDefault(); setDragActive(false); handleFile(e.dataTransfer.files[0]) }}
            onClick={() => document.getElementById('tender-file-input').click()}
          >
            <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
              {uploading ? <div className="spinner" /> : <span className="material-symbols-outlined" style={{ fontSize: 52, color: 'var(--primary)', opacity: 0.6 }}>picture_as_pdf</span>}
            </div>
            <div className="dropzone-title">{uploading ? 'Extracting rules…' : 'Upload Tender Document'}</div>
            <div className="dropzone-sub">{uploading ? 'AI is reading the PDF and building your eligibility checklist.' : 'Drag & drop a PDF or click to browse. Supports CRPF, NIT, RFP formats.'}</div>
            <input id="tender-file-input" type="file" accept=".pdf" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
          </div>
          <div className="ai-note" style={{ marginTop: 20 }}>
            <span className="material-symbols-outlined icon-filled" style={{ fontSize: 16, color: 'var(--primary)', flexShrink: 0 }}>smart_toy</span>
            <span>AI detects 22+ rule types: financial thresholds, GST/PAN/MSME compliance, security clearances, ISO certifications, and CRPF/paramilitary experience. Mandatory vs optional is detected from tender language.</span>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 24 }}>
          {/* Left: Document preview */}
          <div style={{ flex: '0 0 46%' }}>
            <div className="card" style={{ height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column' }}>
              <div className="card-header">
                <span className="card-header-title">
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>description</span>
                  {ruleset.uploaded_filename}
                </span>
                <span style={{ fontSize: 11, color: 'var(--secondary)' }}>{ruleset.total_pages} pages</span>
              </div>
              <div style={{ flex: 1, overflow: 'auto', padding: 20, background: '#f0f2f5' }}>
                <div style={{ background: 'white', padding: '40px 36px', minHeight: 600, boxShadow: '0 4px 20px rgba(0,0,0,0.1)', borderRadius: 2 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
                    <span className="badge badge-blue">Official Copy</span>
                    <span style={{ fontSize: 11, color: '#94a3b8' }}>Ref: {ruleset.tender_ref}</span>
                  </div>
                  <h2 style={{ fontSize: 17, fontWeight: 700, color: '#1e293b', borderBottom: '2px solid #e2e8f0', paddingBottom: 14, marginBottom: 20 }}>{ruleset.tender_name}</h2>
                  <div style={{ fontSize: 12, color: '#475569', lineHeight: 1.7 }}>
                    {ruleset.rules.slice(0, 8).map((r, i) => (
                      <p key={i} style={{ marginBottom: 12, paddingLeft: 12, borderLeft: `3px solid ${r.mandatory !== false ? '#dc2626' : '#f59e0b'}`, background: r.mandatory !== false ? '#fff5f5' : '#fffbeb', padding: '6px 12px', borderRadius: '0 4px 4px 0' }}>
                        <strong style={{ color: '#1e293b' }}>[{r.mandatory !== false ? 'M' : 'O'}] {r.source_section || r.id}:</strong> {r.source_text.slice(0, 160)}…
                      </p>
                    ))}
                  </div>
                  <p style={{ marginTop: 20, fontSize: 11, color: '#94a3b8', textAlign: 'center' }}>
                    AI extraction completed · {mandatoryCount} mandatory · {optionalCount} optional
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Right: Rules checklist */}
          <div style={{ flex: 1, overflow: 'auto', maxHeight: 'calc(100vh - 200px)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span className="material-symbols-outlined icon-filled" style={{ color: 'var(--primary-container)', fontSize: 22 }}>smart_toy</span>
                <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--primary)' }}>AI-Extracted Checklist</span>
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {['all', 'mandatory', 'optional'].map(f => (
                  <button key={f} onClick={() => setFilter(f)} style={{ padding: '4px 10px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer', border: '1px solid', borderColor: filter === f ? 'var(--primary)' : '#e2e8f0', background: filter === f ? 'var(--primary)' : 'white', color: filter === f ? 'white' : 'var(--secondary)' }}>
                    {f === 'mandatory' ? `🔴 Mandatory (${mandatoryCount})` : f === 'optional' ? `🟡 Optional (${optionalCount})` : `All (${totalCount})`}
                  </button>
                ))}
              </div>
            </div>

            {visibleRules.map(rule => (
              <div key={rule.id} className={`rule-card ${rule.approved ? 'approved' : rule.confidence < 0.65 ? 'pending' : ''}`}>
                <div className="rule-card-body">
                  <div className="rule-card-meta">
                    <span className={`rule-cat-badge ${catClass(rule.category)}`}>{rule.category}</span>
                    <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 7px', borderRadius: 4, background: rule.mandatory !== false ? '#fee2e2' : '#fef3c7', color: rule.mandatory !== false ? '#dc2626' : '#92400e' }}>
                      {rule.mandatory !== false ? '🔴 MANDATORY' : '🟡 OPTIONAL'}
                    </span>
                    {rule.is_manual && <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4, background: '#eff6ff', color: 'var(--primary)', fontWeight: 700 }}>Officer Added</span>}
                    <span className="rule-conf">Conf: {(rule.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="rule-title">{rule.label}</div>
                  <div className="rule-text">
                    {rule.value !== null && rule.value !== undefined
                      ? `${rule.operator} ${rule.value.toLocaleString()} ${rule.unit || ''}`
                      : 'Must be present in documents'}
                    {rule.source_section && <> · <span style={{ color: 'var(--primary)', fontWeight: 600 }}>{rule.source_section}</span></>}
                  </div>
                  {rule.source_text && (
                    <div style={{ marginTop: 6, fontSize: 10, color: '#94a3b8', fontStyle: 'italic', lineHeight: 1.5 }}>
                      "{rule.source_text.slice(0, 200)}"
                    </div>
                  )}
                  {rule.notes && (
                    <div className="rule-note">
                      <span className="material-symbols-outlined" style={{ fontSize: 13, flexShrink: 0 }}>info</span>
                      <span>Note: {rule.notes}</span>
                    </div>
                  )}
                  <div className="rule-footer">
                    <div className="rule-actions">
                      {!rule.approved && (
                        <button className="rule-btn rule-btn-approve" onClick={() => approve(rule.id)}>
                          <span className="material-symbols-outlined icon-filled" style={{ fontSize: 13 }}>check_circle</span> Approve
                        </button>
                      )}
                      {rule.approved && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 600, color: 'var(--eligible-text)' }}>
                          <span className="material-symbols-outlined icon-filled" style={{ fontSize: 13 }}>check_circle</span> Approved
                        </span>
                      )}
                      <button className="rule-btn rule-btn-edit" onClick={() => setEditRule(rule)}>
                        <span className="material-symbols-outlined" style={{ fontSize: 13 }}>edit</span> Edit
                      </button>
                      <button className="rule-btn rule-btn-delete" onClick={() => deleteRule(rule.id)}>
                        <span className="material-symbols-outlined" style={{ fontSize: 13 }}>delete</span>
                      </button>
                    </div>
                    {rule.source_section && <span className="rule-section">{rule.source_section}</span>}
                  </div>
                </div>
              </div>
            ))}

            {visibleRules.length === 0 && (
              <div className="empty-state">
                <span className="material-symbols-outlined">search_off</span>
                <p>No rules found for this filter. Try uploading a different PDF or add rules manually.</p>
              </div>
            )}
          </div>
        </div>
      )}

      <div className="footer-bar">
        <span>TenderIQ v2.0 | Stage 1 — Rule Extraction</span>
        <span>{mandatoryCount} mandatory · {optionalCount} optional · {approvedCount}/{totalCount} approved</span>
      </div>
    </div>
  )
}

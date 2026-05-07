import { useState, useCallback } from 'react'
import { bidderApi } from '../api/client'

function confColor(c) {
  if (c >= 0.85) return '#16a34a'
  if (c >= 0.65) return '#92400e'
  return '#dc2626'
}

export default function Stage2({ toast, onNext }) {
  const [bidders, setBidders] = useState([])
  const [selected, setSelected] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [bidderName, setBidderName] = useState('')
  const [files, setFiles] = useState([])
  const [dragActive, setDragActive] = useState(false)
  const [showForm, setShowForm] = useState(false)

  const handleUpload = async () => {
    if (!bidderName.trim()) { toast('Enter bidder name', 'error'); return }
    if (!files.length) { toast('Add at least one file', 'error'); return }
    setUploading(true)
    try {
      const res = await bidderApi.upload(bidderName.trim(), files)
      const newBidder = res.data
      setBidders(p => [...p, newBidder])
      setSelected(newBidder)
      setBidderName(''); setFiles([]); setShowForm(false)
      toast(`Processed ${newBidder.bidder_name} — ${newBidder.extracted_fields.length} fields extracted`, 'success')
    } catch (e) { toast(e.response?.data?.detail || 'Upload failed', 'error') }
    finally { setUploading(false) }
  }

  const confirm = async (bidderId) => {
    try {
      await bidderApi.confirm(bidderId)
      setBidders(p => p.map(b => b.bidder_id === bidderId ? { ...b, confirmed: true, status: 'complete' } : b))
      setSelected(p => p?.bidder_id === bidderId ? { ...p, confirmed: true, status: 'complete' } : p)
      toast('Bidder data confirmed', 'success')
    } catch { toast('Failed to confirm', 'error') }
  }

  const removeBidder = async (bidderId) => {
    try {
      await bidderApi.remove(bidderId)
      setBidders(p => p.filter(b => b.bidder_id !== bidderId))
      if (selected?.bidder_id === bidderId) setSelected(null)
    } catch { toast('Failed to remove', 'error') }
  }

  const statusColor = { queued: 'chip-queued', processing: 'chip-processing', complete: 'chip-eligible', manual_review: 'chip-manual', error: 'chip-not-eligible' }
  const statusLabel = { queued: 'Queued', processing: 'Processing', complete: 'Complete', manual_review: 'Manual Review', error: 'Error' }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div style={{ fontSize: 12, color: 'var(--secondary)', marginBottom: 4, display: 'flex', gap: 6, alignItems: 'center' }}>
            <span className="badge badge-blue">Stage 2</span><span>→ Bidder Data Processing</span>
          </div>
          <h1 className="section-title">Bidder Document Processing</h1>
          <p className="section-sub">Upload bidder documents (PDF, Word, scanned images). OCR + AI extracts structured data and traces each field back to its source file.</p>
        </div>
        <div className="page-header-actions">
          <button className="btn btn-secondary btn-sm" onClick={() => setShowForm(p => !p)}>
            <span className="material-symbols-outlined" style={{ fontSize: 16 }}>add</span> Add Bidder
          </button>
          {bidders.length > 0 && (
            <button className="btn btn-primary" onClick={onNext}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>arrow_forward</span>
              Run Evaluation ({bidders.length} bidders)
            </button>
          )}
        </div>
      </div>

      {/* Add Bidder Form */}
      {showForm && (
        <div className="card" style={{ marginBottom: 24, padding: 20 }}>
          <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--primary)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>business</span>
            Add Bidder
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 16, marginBottom: 16 }}>
            <div>
              <label>Bidder / Company Name</label>
              <input type="text" value={bidderName} onChange={e => setBidderName(e.target.value)} placeholder="e.g. Apex Systems Corp" />
            </div>
            <div>
              <label>Documents (PDF, Word, JPG, PNG, scanned)</label>
              <div
                className={`dropzone ${dragActive ? 'active' : ''}`}
                style={{ padding: 20 }}
                onDragOver={e => { e.preventDefault(); setDragActive(true) }}
                onDragLeave={() => setDragActive(false)}
                onDrop={e => { e.preventDefault(); setDragActive(false); setFiles(p => [...p, ...Array.from(e.dataTransfer.files)]) }}
                onClick={() => document.getElementById('bidder-file-input').click()}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 28, color: 'var(--primary)', opacity: 0.5 }}>upload_file</span>
                <div className="dropzone-title" style={{ fontSize: 12 }}>Click or drag files</div>
                {files.length > 0 && <div style={{ marginTop: 8, fontSize: 11, color: 'var(--eligible-text)' }}>{files.length} file(s) selected: {files.map(f => f.name).join(', ')}</div>}
                <input id="bidder-file-input" type="file" multiple accept=".pdf,.docx,.doc,.png,.jpg,.jpeg,.tiff,.bmp,.webp" style={{ display: 'none' }} onChange={e => setFiles(p => [...p, ...Array.from(e.target.files)])} />
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-secondary btn-sm" onClick={() => { setShowForm(false); setBidderName(''); setFiles([]) }}>Cancel</button>
            <button className="btn btn-primary btn-sm" onClick={handleUpload} disabled={uploading}>
              {uploading ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Processing…</> : <>
                <span className="material-symbols-outlined" style={{ fontSize: 15 }}>play_arrow</span> Process Documents
              </>}
            </button>
          </div>
        </div>
      )}

      {/* Main Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: 20, minHeight: 500 }}>
        {/* Queue */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', maxHeight: 600 }}>
          <div className="card-header">
            <span className="card-header-title">
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>list_alt</span>
              Queue ({bidders.length})
            </span>
            {bidders.some(b => b.status === 'processing') && <span className="chip chip-processing">Processing</span>}
          </div>
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {bidders.length === 0 ? (
              <div className="empty-state" style={{ padding: 32 }}>
                <span className="material-symbols-outlined">inbox</span>
                <p>No bidders yet. Click "Add Bidder" to upload documents.</p>
              </div>
            ) : bidders.map(b => (
              <div key={b.bidder_id} className={`bidder-item ${selected?.bidder_id === b.bidder_id ? 'active' : ''}`} onClick={() => setSelected(b)}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <div className="bidder-name">{b.bidder_name}</div>
                  <span className={`chip ${statusColor[b.status] || 'chip-queued'}`}>{statusLabel[b.status] || b.status}</span>
                </div>
                <div className="bidder-ref">{b.uploaded_files.join(', ')}</div>
                <div className="progress-bar">
                  <div className={`progress-fill ${b.status === 'complete' ? 'complete' : b.status === 'manual_review' ? 'review' : ''}`} style={{ width: `${b.progress}%` }} />
                </div>
                <div style={{ fontSize: 10, fontWeight: 600, marginTop: 4, color: b.status === 'complete' ? 'var(--eligible-text)' : b.status === 'manual_review' ? '#92400e' : 'var(--secondary)' }}>
                  {b.status === 'complete' ? `${b.extracted_fields.length} fields extracted` : b.status === 'manual_review' ? 'Needs review' : 'Pending'}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div>
          {!selected ? (
            <div className="card" style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div className="empty-state">
                <span className="material-symbols-outlined">touch_app</span>
                <p>Select a bidder from the queue to view extracted data.</p>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {/* Bidder Header */}
              <div className="card" style={{ padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{ width: 40, height: 40, borderRadius: 6, background: 'var(--primary-container)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 700 }}>
                      {selected.bidder_name.substring(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--primary)' }}>{selected.bidder_name}</div>
                      <div style={{ fontSize: 11, color: 'var(--secondary)' }}>{selected.uploaded_files.join(' · ')} · OCR Confidence: {(selected.ocr_confidence_avg * 100).toFixed(0)}%</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn btn-danger btn-sm" onClick={() => removeBidder(selected.bidder_id)}>
                      <span className="material-symbols-outlined" style={{ fontSize: 14 }}>delete</span>
                    </button>
                    {!selected.confirmed && (
                      <button className="btn btn-primary btn-sm" onClick={() => confirm(selected.bidder_id)}>
                        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>check_circle</span> Confirm Data
                      </button>
                    )}
                    {selected.confirmed && <span className="chip chip-eligible">✓ Confirmed</span>}
                  </div>
                </div>
              </div>

              {/* Extracted Fields Table */}
              <div className="card">
                <div className="card-header">
                  <span className="card-header-title">
                    <span className="material-symbols-outlined icon-filled" style={{ fontSize: 16, color: 'var(--primary-container)' }}>auto_awesome</span>
                    AI Standardised Extracted Data
                  </span>
                  <span style={{ fontSize: 11, color: 'var(--secondary)' }}>{selected.extracted_fields.length} fields</span>
                </div>
                {selected.extracted_fields.length === 0 ? (
                  <div className="empty-state" style={{ padding: 32 }}>
                    <span className="material-symbols-outlined">search_off</span>
                    <p>No structured fields extracted. Check document quality.</p>
                  </div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="fields-table" style={{ width: '100%' }}>
                      <thead><tr>
                        <th>Field</th><th>Extracted Value</th><th>Confidence</th><th>File</th><th>Page</th><th>Status</th>
                      </tr></thead>
                      <tbody>
                        {selected.extracted_fields.map((f, i) => (
                          <tr key={i}>
                            <td style={{ fontWeight: 600, color: 'var(--primary)' }}>{f.field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}</td>
                            <td style={{ fontFamily: 'monospace', fontSize: 12 }}>
                              {f.value !== null && f.value !== undefined ? String(f.value) : <span style={{ color: '#94a3b8' }}>Not found</span>}
                            </td>
                            <td>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <div className="conf-bar">
                                  <div className="conf-fill" style={{ width: `${f.confidence * 100}%`, background: confColor(f.confidence) }} />
                                </div>
                                <span style={{ fontSize: 11, fontWeight: 600, color: confColor(f.confidence) }}>{(f.confidence * 100).toFixed(0)}%</span>
                              </div>
                            </td>
                            <td style={{ color: 'var(--secondary)', fontSize: 10, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={f.source_file}>{f.source_file || '—'}</td>
                            <td style={{ color: 'var(--secondary)', fontSize: 11, textAlign: 'center' }}>{f.source_page}</td>
                            <td>
                              {f.needs_review
                                ? <span className="chip chip-manual">Review</span>
                                : <span className="chip chip-eligible">OK</span>
                              }
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Reasoning Card */}
              {selected.processing_notes?.length > 0 && (
                <div className="reasoning-card">
                  <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--primary)', marginBottom: 6, display: 'flex', gap: 6 }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 15 }}>psychology</span>
                    Processing Notes
                  </div>
                  {selected.processing_notes.map((n, i) => <p key={i} style={{ fontSize: 11, color: 'var(--secondary)', marginBottom: 4 }}>• {n}</p>)}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="footer-bar">
        <span>Batch: {bidders.length} bidder(s) · Avg OCR: {bidders.length ? (bidders.reduce((a, b) => a + b.ocr_confidence_avg, 0) / bidders.length * 100).toFixed(0) : 0}%</span>
        <span>TenderIQ Engine v1.0 · NIST-800 Compliance Active</span>
      </div>
    </div>
  )
}

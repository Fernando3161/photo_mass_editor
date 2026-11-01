import { useEffect, useState } from 'react'
import { api } from '../api'

type Preview = Awaited<ReturnType<typeof api.previewExport>>
type Result = Awaited<ReturnType<typeof api.createExport>>
type Audit = Awaited<ReturnType<typeof api.auditExport>>
type History = Awaited<ReturnType<typeof api.recentExports>>

export function ExportPanel() {
  const [preview, setPreview] = useState<Preview | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [audit, setAudit] = useState<Audit | null>(null)
  const [history, setHistory] = useState<History>([])
  const [authorized, setAuthorized] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { void api.recentExports().then(setHistory).catch(() => {}) }, [])

  const loadPreview = async () => {
    setBusy(true)
    setAuthorized(false)
    setPreview(null)
    try { setPreview(await api.previewExport()); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Export preview failed') }
    finally { setBusy(false) }
  }

  const exportApproved = async () => {
    if (!authorized || !preview?.approved_count) return
    setBusy(true)
    try {
      const created = await api.createExport()
      setResult(created)
      void api.recentExports().then(setHistory).catch(() => {})
      setAuthorized(false)
      setPreview(null)
      setError('')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Export failed') }
    finally { setBusy(false) }
  }

  const runAudit = async () => {
    setBusy(true)
    try { setAudit(await api.auditExport()); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Audit failed') }
    finally { setBusy(false) }
  }

  const openFolder = async (exportId: string) => {
    try { await api.openExportFolder(exportId); setError('') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Could not open export folder') }
  }

  const olderCollections = history.filter((item) => item.export_id !== result?.export_id)

  return <div className="panel-section export-panel">
    <div className="section-heading"><div><p className="eyebrow">Phase 6</p><h3>Website collection</h3></div><span className="phase-chip">Approved only</span></div>
    <p>Export copies each approved website JPEG byte for byte. A separate small thumbnail, privacy filtered manifest, and cost report accompany the collection. Originals and existing versions stay in place.</p>
    <div className="panel-actions"><button type="button" className="button-secondary" disabled={busy} onClick={() => void loadPreview()}>Preview approved collection</button><button type="button" className="button-secondary" disabled={busy} onClick={() => void runAudit()}>Audit files</button></div>
    {preview && <div role="status"><strong>{preview.approved_count} approved image{preview.approved_count === 1 ? '' : 's'}</strong> ready for {preview.target}. {preview.items.filter((item) => item.location_included).length} have confirmed city and country.
      <ul className="export-preview-list">{preview.items.slice(0, 20).map((item) => <li key={item.version_id}>{item.photo_id.slice(0, 8)} · {item.width} × {item.height} · version {item.version_id.slice(0, 8)}</li>)}</ul>
      {preview.items.length > 20 && <small>Showing the first 20 of {preview.items.length}.</small>}
    </div>}
    {preview && preview.approved_count > 0 && <><label className="consent-row"><input type="checkbox" checked={authorized} onChange={(event) => setAuthorized(event.target.checked)} /> I authorize this approved collection export</label><button type="button" className="button-primary" disabled={busy || !authorized} onClick={() => void exportApproved()}>Export approved collection</button></>}
    {result && <div role="status" className="export-result"><strong>Exported {result.item_count} image{result.item_count === 1 ? '' : 's'}.</strong><p>Collection folder:</p><button type="button" className="export-folder-link" onClick={() => void openFolder(result.export_id)} title="Open this folder in File Explorer">{result.directory_path}</button><div className="export-downloads"><a href={`/api/export/${result.export_id}/manifest`}>Download manifest</a><a href={`/api/export/${result.export_id}/cost_report`}>Download cost report</a></div></div>}
    {olderCollections.length > 0 && <section className="export-history" aria-label="Recent collections"><h4>Recent collections</h4>{olderCollections.map((item) => <div key={item.export_id} className="export-history-item"><button type="button" className="export-folder-link" onClick={() => void openFolder(item.export_id)} title="Open this folder in File Explorer">{item.directory_path}</button><small>{item.item_count} images · {item.created_at}</small><div className="export-downloads"><a href={`/api/export/${item.export_id}/manifest`}>Manifest</a><a href={`/api/export/${item.export_id}/cost_report`}>Cost report</a></div></div>)}</section>}
    {audit && <div role="status"><strong>File audit</strong><p>{audit.referenced_files} referenced files · {audit.missing.length} missing · {audit.changed.length} changed · {audit.source_issues.length} source issues · {audit.orphaned.length} unreferenced files · {audit.invalid_manifests.length + audit.invalid_cost_reports.length} invalid reports</p>{(audit.missing.length + audit.changed.length + audit.source_issues.length + audit.orphaned.length + audit.invalid_manifests.length + audit.invalid_cost_reports.length > 0) && <details><summary>Inspect findings</summary><pre>{JSON.stringify(audit, null, 2)}</pre></details>}</div>}
    {error && <p role="alert" className="error-message">{error}</p>}
  </div>
}

import type { PhotoSummary } from '../types'

interface Props {
  photos: PhotoSummary[]
  onSelect: (id: string) => void
  onClose: () => void
  selectedIds: string[]
  onToggle: (id: string) => void
  onSelectVisible: () => void
  onClearSelection: () => void
  onOpenBatch: () => void
}

export function ContactSheet({ photos, onSelect, onClose, selectedIds, onToggle, onSelectVisible, onClearSelection, onOpenBatch }: Props) {
  return (
    <div className="contact-overlay" role="dialog" aria-modal="true" aria-labelledby="contact-title">
      <header>
        <div>
          <p className="eyebrow">Random access</p>
          <h2 id="contact-title">Contact sheet</h2>
        </div>
        <button type="button" className="button-secondary" onClick={onClose}>Close grid</button>
      </header>
      <div className="contact-selection-tools"><strong>{selectedIds.length} selected</strong><button type="button" onClick={onSelectVisible}>Select visible</button><button type="button" onClick={onClearSelection}>Clear selection</button><button type="button" disabled={!selectedIds.length} onClick={onOpenBatch}>Review selection in batch</button></div>
      <div className="contact-grid">
        {photos.map((photo, index) => (
          <div key={photo.id} className={`contact-card ${selectedIds.includes(photo.id) ? 'is-batch-selected' : ''}`}>
            <label className="contact-select"><input type="checkbox" aria-label={`Select ${photo.original_filename} for batch`} checked={selectedIds.includes(photo.id)} onChange={() => onToggle(photo.id)} /> Batch</label>
            <button type="button" onClick={() => onSelect(photo.id)}><img src={photo.thumbnail_url} alt={`Thumbnail for ${photo.original_filename}`} loading="lazy" /><span>{index + 1}</span><strong>{photo.original_filename}</strong><small>{photo.review_state.toLowerCase().replace('_', ' ')}</small></button>
          </div>
        ))}
      </div>
    </div>
  )
}

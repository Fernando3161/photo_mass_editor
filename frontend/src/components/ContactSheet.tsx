import type { PhotoSummary } from '../types'

interface Props {
  photos: PhotoSummary[]
  onSelect: (id: string) => void
  onClose: () => void
}

export function ContactSheet({ photos, onSelect, onClose }: Props) {
  return (
    <div className="contact-overlay" role="dialog" aria-modal="true" aria-labelledby="contact-title">
      <header>
        <div>
          <p className="eyebrow">Random access</p>
          <h2 id="contact-title">Contact sheet</h2>
        </div>
        <button type="button" className="button-secondary" onClick={onClose}>Close grid</button>
      </header>
      <div className="contact-grid">
        {photos.map((photo, index) => (
          <button type="button" key={photo.id} onClick={() => onSelect(photo.id)} className="contact-card">
            <img src={photo.thumbnail_url} alt={`Thumbnail for ${photo.original_filename}`} loading="lazy" />
            <span>{index + 1}</span>
            <strong>{photo.original_filename}</strong>
            <small>{photo.review_state.toLowerCase().replace('_', ' ')}</small>
          </button>
        ))}
      </div>
    </div>
  )
}

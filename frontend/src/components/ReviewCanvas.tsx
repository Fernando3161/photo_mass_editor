import type { PhotoDetail } from '../types'

export function ReviewCanvas({ photo }: { photo: PhotoDetail }) {
  return (
    <section className="compare-canvas" aria-label="Photo comparison">
      <article className="image-stage">
        <header><span>Original</span><small>{photo.width} × {photo.height}</small></header>
        <div className="image-well">
          <img src={photo.original_url} alt={`Original ${photo.original_filename}`} />
        </div>
      </article>
      <article className="image-stage empty-stage">
        <header><span>Edited version</span><small>No attempts</small></header>
        <div className="empty-copy">
          <span className="empty-icon" aria-hidden="true">◇</span>
          <strong>Not edited yet</strong>
          <p>Editing and version comparisons arrive in Phase 4. This space stays explicit so the original is never mistaken for an edit.</p>
        </div>
      </article>
    </section>
  )
}

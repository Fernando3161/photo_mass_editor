import type { ImageVersion, PhotoDetail } from '../types'

export function ReviewCanvas({ photo, version }: { photo: PhotoDetail; version: ImageVersion | null }) {
  return (
    <section className="compare-canvas" aria-label="Photo comparison">
      <article className="image-stage">
        <header><span>Original photo</span><small>{photo.width} × {photo.height}</small></header>
        <div className="image-well">
          <img src={photo.original_url} alt={`Original ${photo.original_filename}`} />
        </div>
      </article>
      <article className={`image-stage ${version ? '' : 'empty-stage'}`}>
        <header><span>{version ? `Edited version ${version.version_number} · ${version.review_status}` : 'Edited version'}</span><small>{version ? `${version.width} × ${version.height}` : 'No attempts'}</small></header>
        {version ? <div className="image-well"><img src={version.image_url} alt={`Edited version ${version.version_number} of ${photo.original_filename}`} /></div>
          : <div className="empty-copy"><span className="empty-icon" aria-hidden="true">◇</span><strong>Not edited yet</strong><p>Run an authorized edit to create a separate version for comparison.</p></div>}
      </article>
    </section>
  )
}

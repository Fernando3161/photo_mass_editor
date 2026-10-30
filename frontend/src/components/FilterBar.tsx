import type { PhotoSummary, ReviewState } from '../types'

export interface Filters {
  query: string
  state: ReviewState | 'ALL'
  subject: string
  tag: string
  city: string
  date: string
}

interface Props {
  filters: Filters
  onChange: (next: Filters) => void
  photos: PhotoSummary[]
  resultCount: number
  onGrid: () => void
}

export function FilterBar({ filters, onChange, photos, resultCount, onGrid }: Props) {
  const subjects = [...new Set(photos.map((photo) => photo.primary_subject).filter(Boolean) as string[])].sort()
  const tags = [...new Set(photos.flatMap((photo) => photo.tags.map((tag) => tag.display_name)))].sort()
  const cities = [...new Set(photos.map((photo) => photo.city).filter(Boolean) as string[])].sort()
  const set = (key: keyof Filters, value: string) => onChange({ ...filters, [key]: value })

  return (
    <section className="filter-bar" aria-label="Catalog filters">
      <label className="search-field">
        <span className="sr-only">Search photos</span>
        <input value={filters.query} onChange={(event) => set('query', event.target.value)} placeholder="Search filename, subject, location…" />
      </label>
      <label><span>Status</span><select value={filters.state} onChange={(event) => set('state', event.target.value)}><option value="ALL">All</option><option value="UNREVIEWED">Unreviewed</option><option value="IN_PROGRESS">In progress</option><option value="REVIEWED">Reviewed</option></select></label>
      <label><span>Subject</span><select value={filters.subject} onChange={(event) => set('subject', event.target.value)}><option value="">Any</option>{subjects.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label><span>Tag</span><select value={filters.tag} onChange={(event) => set('tag', event.target.value)}><option value="">Any</option>{tags.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label><span>City</span><select value={filters.city} onChange={(event) => set('city', event.target.value)}><option value="">Any</option>{cities.map((value) => <option key={value}>{value}</option>)}</select></label>
      <label><span>Month</span><input type="month" value={filters.date} onChange={(event) => set('date', event.target.value)} /></label>
      <span className="result-count">{resultCount} of {photos.length}</span>
      <button type="button" className="button-secondary" onClick={onGrid}>Open grid</button>
    </section>
  )
}

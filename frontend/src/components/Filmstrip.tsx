import { useEffect, useMemo, useRef, useState } from 'react'
import type { PhotoSummary } from '../types'

interface Props {
  photos: PhotoSummary[]
  selectedId: string | null
  onSelect: (id: string) => void
}

const ITEM_WIDTH = 112
const OVERSCAN = 5

export function Filmstrip({ photos, selectedId, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [viewport, setViewport] = useState({ left: 0, width: 900 })

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const update = () => setViewport({ left: element.scrollLeft, width: element.clientWidth || 900 })
    update()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const index = photos.findIndex((photo) => photo.id === selectedId)
    if (index >= 0 && ref.current) {
      const left = Math.max(0, index * ITEM_WIDTH - ref.current.clientWidth / 2)
      if (typeof ref.current.scrollTo === 'function') {
        ref.current.scrollTo({ left, behavior: 'smooth' })
      } else {
        ref.current.scrollLeft = left
      }
    }
  }, [photos, selectedId])

  const windowed = useMemo(() => {
    const start = Math.max(0, Math.floor(viewport.left / ITEM_WIDTH) - OVERSCAN)
    const count = Math.ceil(viewport.width / ITEM_WIDTH) + OVERSCAN * 2
    return { start, items: photos.slice(start, start + count) }
  }, [photos, viewport])

  return (
    <div className="filmstrip" ref={ref} onScroll={(event) => setViewport({ left: event.currentTarget.scrollLeft, width: event.currentTarget.clientWidth })} aria-label="Photo filmstrip">
      <div className="filmstrip-track" style={{ width: photos.length * ITEM_WIDTH }}>
        {windowed.items.map((photo, offset) => {
          const index = windowed.start + offset
          return (
            <button
              type="button"
              className={`filmstrip-item ${photo.id === selectedId ? 'is-current' : ''}`}
              style={{ left: index * ITEM_WIDTH }}
              key={photo.id}
              onClick={() => onSelect(photo.id)}
              aria-current={photo.id === selectedId ? 'true' : undefined}
              aria-label={`${index + 1}. ${photo.original_filename}, ${photo.review_state.toLowerCase().replace('_', ' ')}`}
            >
              <img src={photo.thumbnail_url} alt="" loading="lazy" />
              <span className={`state-mark state-${photo.review_state.toLowerCase()}`} aria-hidden="true" />
              <small>{index + 1}</small>
            </button>
          )
        })}
      </div>
    </div>
  )
}

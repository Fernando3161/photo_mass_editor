import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Filmstrip } from '../components/Filmstrip'
import type { PhotoSummary } from '../types'

const photos: PhotoSummary[] = Array.from({ length: 200 }, (_, index) => ({
  id: `photo-${index + 1}`,
  original_filename: `photo-${index + 1}.jpg`,
  width: 1200,
  height: 800,
  capture_datetime_raw: null,
  camera: null,
  city: null,
  country: null,
  review_state: 'UNREVIEWED',
  revision: 0,
  primary_subject: null,
  thumbnail_url: `/api/photos/photo-${index + 1}/thumbnail`,
  tags: [],
}))

describe('Filmstrip', () => {
  it('windows a 200-photo collection and renders the current distant selection', async () => {
    const onSelect = vi.fn()
    const { container } = render(
      <Filmstrip photos={photos} selectedId="photo-200" onSelect={onSelect} />,
    )

    const strip = screen.getByLabelText('Photo filmstrip')
    Object.defineProperty(strip, 'clientWidth', { configurable: true, value: 900 })
    fireEvent.scroll(strip)

    const current = await screen.findByRole('button', { name: /200\. photo-200\.jpg/i })
    expect(current.getAttribute('aria-current')).toBe('true')
    expect(container.querySelectorAll('.filmstrip-item').length).toBeLessThan(30)
  })
})

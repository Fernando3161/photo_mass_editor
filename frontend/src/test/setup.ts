import '@testing-library/react'
import { afterEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:local-preview') })
Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })

afterEach(() => {
  cleanup()
  localStorage.clear()
  vi.mocked(URL.createObjectURL).mockReset().mockReturnValue('blob:local-preview')
  vi.mocked(URL.revokeObjectURL).mockClear()
})

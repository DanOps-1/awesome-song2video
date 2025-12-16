import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Home from '../pages/Home'
import { describe, it, expect } from 'vitest'

describe('Home Page', () => {
  it('renders the title and description', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    )

    expect(screen.getByText(/让你的音乐/)).toBeInTheDocument()
    expect(screen.getByText(/看见画面/)).toBeInTheDocument()
    expect(screen.getByText(/AI 自动识别歌词情感/)).toBeInTheDocument()
  })

  it('renders the feature cards', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    )

    expect(screen.getByText('音频语义理解')).toBeInTheDocument()
    expect(screen.getByText('智能素材匹配')).toBeInTheDocument()
    expect(screen.getByText('电影级混剪')).toBeInTheDocument()
  })

  it('renders the start button', () => {
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>
    )

    const button = screen.getByRole('button', { name: /立即创作/i })
    expect(button).toBeInTheDocument()
  })
})

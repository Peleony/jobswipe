import { StrictMode, act, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SwipeDeck from './SwipeDeck'

const first = { hash: 'first', title: 'Barista' }
const second = { hash: 'second', title: 'Kurier' }

function DeckHarness({ onSwipe }) {
  const [jobs, setJobs] = useState([first, second])
  return <SwipeDeck job={jobs[0]} onSwipe={(action, job) => {
    onSwipe(action, job)
    setJobs((current) => current.slice(1))
  }} />
}

function pointer(target, type, clientX) {
  target.dispatchEvent(new MouseEvent(type, { bubbles: true, button: 0, clientX }))
}

function key(key, repeat = false) {
  document.dispatchEvent(new KeyboardEvent('keydown', { key, repeat, cancelable: true }))
}

describe('swipe card transitions', () => {
  let container
  let root

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true)
    container = document.body.appendChild(document.createElement('div'))
    root = createRoot(container)
  })

  afterEach(async () => {
    await act(() => root.unmount())
    container.remove()
    vi.unstubAllGlobals()
  })

  it('replaces a mouse-dragged card with a visible card that can be swiped by keyboard', async () => {
    const onSwipe = vi.fn()
    await act(() => root.render(<DeckHarness onSwipe={onSwipe} />))
    const outgoing = container.querySelector('article')

    await act(async () => {
      pointer(outgoing, 'pointerdown', 20)
      pointer(window, 'pointermove', 190)
      await vi.waitFor(() => expect(Number(outgoing.querySelector('.swipe-save').style.opacity)).toBeGreaterThan(0))
      pointer(window, 'pointerup', 190)
      await vi.waitFor(() => expect(onSwipe).toHaveBeenCalledWith('save', first))
    })

    expect(container.querySelectorAll('article')).toHaveLength(1)
    expect(outgoing.isConnected).toBe(false)
    expect(container.querySelector('article h2').textContent).toBe('Kurier')
    expect(container.querySelector('article').style.opacity).toBe('1')

    await act(async () => {
      key('ArrowLeft', true)
      expect(onSwipe).toHaveBeenCalledTimes(1)
      key('ArrowLeft')
      key('ArrowRight')
      await vi.waitFor(() => expect(onSwipe).toHaveBeenCalledTimes(2))
    })
    expect(onSwipe).toHaveBeenLastCalledWith('dismiss', second)
    expect(container.querySelector('article')).toBeNull()
  })

  it('cancels a button swipe when the job is replaced mid-animation', async () => {
    const onSwipe = vi.fn()
    await act(() => root.render(<SwipeDeck job={first} onSwipe={onSwipe} />))
    await act(() => container.querySelector('.action-save').click())
    expect(container.querySelector('.action-save').disabled).toBe(true)

    await act(() => root.render(<SwipeDeck job={second} onSwipe={onSwipe} />))
    expect(container.querySelector('article').style.opacity).toBe('1')
    await act(async () => {
      container.querySelector('.action-save').click()
      await vi.waitFor(() => expect(onSwipe).toHaveBeenCalledWith('save', second))
    })
    expect(onSwipe).toHaveBeenCalledTimes(1)
  })

  it('keeps the details open when Strict Mode reopens the native dialog before its close event', async () => {
    const prototype = window.HTMLDialogElement.prototype
    const pendingCloses = []
    Object.defineProperties(prototype, {
      showModal: { configurable: true, value() { this.open = true } },
      close: { configurable: true, value() {
        this.open = false
        pendingCloses.push(() => this.dispatchEvent(new Event('close')))
      } },
    })
    try {
      await act(() => root.render(<StrictMode><SwipeDeck job={first} onSwipe={vi.fn()} /></StrictMode>))
      await act(() => container.querySelector('.job-details-button').click())
      expect(pendingCloses).toHaveLength(1)
      await act(pendingCloses.shift())
      expect(container.querySelector('dialog')?.open).toBe(true)
      await act(() => container.querySelector('dialog button').click())
      expect(container.querySelector('dialog')).toBeNull()
    } finally {
      delete prototype.showModal
      delete prototype.close
    }
  })

  it('toggles the full description inline without swiping and resets for the next job', async () => {
    const onSwipe = vi.fn()
    const job = { ...first, summary: 'Praca w kawiarni.', description: 'Praca w kawiarni. Szczegóły grafiku ustalisz na rozmowie.' }
    await act(() => root.render(<SwipeDeck job={job} onSwipe={onSwipe} />))
    const toggle = container.querySelector('.job-description-toggle')
    const text = document.getElementById(toggle.getAttribute('aria-controls'))
    expect(toggle.textContent).toBe('Pokaż więcej')
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(text.textContent).toBe(job.summary)

    await act(() => toggle.click())
    expect(toggle.textContent).toBe('Pokaż mniej')
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(text.textContent).toBe(job.description)
    expect(text.tabIndex).toBe(0)

    await act(async () => {
      pointer(text, 'pointerdown', 20)
      pointer(window, 'pointermove', 190)
      await new Promise(requestAnimationFrame)
      expect(Number(container.querySelector('.swipe-save').style.opacity)).toBe(0)
      pointer(window, 'pointerup', 190)
    })
    expect(onSwipe).not.toHaveBeenCalled()

    text.scrollTop = 80
    await act(() => toggle.click())
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(text.textContent).toBe(job.summary)
    await act(() => toggle.click())
    expect(text.scrollTop).toBe(0)

    const nextJob = { ...second, summary: 'Dostawy.', description: 'Dostawy. Samodzielnie wybierasz zmiany.' }
    await act(() => root.render(<SwipeDeck job={nextJob} onSwipe={onSwipe} />))
    expect(container.querySelector('.job-description-toggle').getAttribute('aria-expanded')).toBe('false')
    expect(container.querySelector('.job-description-preview').textContent).toBe(nextJob.summary)
    expect(onSwipe).not.toHaveBeenCalled()
  })

  it('offers expansion of identical summary and description only when the preview overflows', async () => {
    vi.stubGlobal('ResizeObserver', class {
      observe() {}
      disconnect() {}
    })
    const height = vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(80)
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(80)
    const text = 'Praca w kawiarni.'
    await act(() => root.render(<SwipeDeck job={{ ...first, summary: text, description: text }} />))
    expect(container.querySelector('.job-description-toggle')).toBeNull()

    height.mockReturnValue(100)
    await act(() => root.render(<SwipeDeck job={{ ...second, summary: text, description: text }} />))
    expect(container.querySelector('.job-description-toggle').textContent).toBe('Pokaż więcej')
  })

  it('offers expansion when a trailing ellipsis stands in for the last character', async () => {
    const job = { ...first, summary: 'Praca w kawiarni…', description: 'Praca w kawiarni.' }
    await act(() => root.render(<SwipeDeck job={job} />))
    const toggle = container.querySelector('.job-description-toggle')
    expect(toggle.textContent).toBe('Pokaż więcej')
    await act(() => toggle.click())
    expect(container.querySelector('.job-description-expanded').textContent).toBe(job.description)
    expect(container.querySelector('.job-description-source-note')).toBeNull()
  })

  it.each([
    ['…', 'https://example.org/oferta', true],
    ['...', 'http://example.org/oferta', false],
  ])('labels a source excerpt ending with %s and only links to HTTPS', async (ending, url, safe) => {
    const job = { ...first, url, summary: 'Praca w kawiarni.', description: `Praca w kawiarni. Szczegóły grafiku${ending}` }
    await act(() => root.render(<SwipeDeck job={job} />))
    expect(container.querySelector('.job-description-source-note')).toBeNull()
    await act(() => container.querySelector('.job-description-toggle').click())

    const note = container.querySelector('.job-description-source-note')
    expect(note.textContent).toBe('Skrót od źródła — pełny opis na stronie oferty')
    const link = note.querySelector('a')
    if (safe) {
      expect(link.href).toBe(url)
      expect(link.rel).toBe('noopener noreferrer')
      expect(container.querySelector('.job-details-button')).toBeNull()
    } else {
      expect(link).toBeNull()
      expect(container.querySelector('.job-details-button')).not.toBeNull()
    }
  })

  it.each([
    ['olx.pl', 'https://pl.jooble.org/desc/123', ' ...pizzy', '...pizzy i makaronów...', 'Fragment ogłoszenia z Jooble'],
    [' Jooble ', 'https://example.org/oferta', 'opis', ' …opis stanowiska', 'Fragment ogłoszenia z Jooble'],
    ['lento.pl', 'https://notjooble.org/pl.jooble.org/desc/123', ' …pizzy', 'Przygotowywanie pizzy.', 'Fragment ogłoszenia'],
  ])('marks the beginning of an excerpt from %s before and after expanding', async (source, url, summary, description, label) => {
    const job = { ...first, source, url, summary, description }
    await act(() => root.render(<SwipeDeck job={job} />))
    const note = container.querySelector('.job-description-source-note')
    expect(note.textContent).toBe(label)
    expect(note.nextElementSibling.className).toBe('job-description-preview')

    await act(() => container.querySelector('.job-description-toggle').click())
    expect(container.querySelectorAll('.job-description-source-note')).toHaveLength(1)
    expect(note.textContent).toBe(`${label} — pełny opis na stronie oferty`)
    expect(note.querySelector('a').href).toBe(url)
    expect(note.nextElementSibling.className).toBe('job-description-expanded')
    expect(note.nextElementSibling.textContent).toBe(description.trim())
  })
})

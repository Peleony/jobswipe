import { act, useState } from 'react'
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
})

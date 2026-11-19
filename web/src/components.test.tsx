import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { parseTranscript, renderInline } from './components'

describe('parseTranscript', () => {
  it('splits speakers and keeps multi-line bot replies together', () => {
    const t = parseTranscript('USER: Do you charge NSF?\nBOT: No.\n\nOverdrafts cost $34.\nUSER: ok')
    expect(t).toEqual([
      { who: 'Customer', text: 'Do you charge NSF?' },
      { who: 'Bot', text: 'No.\n\nOverdrafts cost $34.' },
      { who: 'Customer', text: 'ok' },
    ])
  })
})

describe('renderInline', () => {
  it('turns **bold** into strong and leaves other text alone', () => {
    const { container } = render(<p>{renderInline('1. **Report it now.** Call us. 2 * 3')}</p>)
    expect(container.querySelector('strong')?.textContent).toBe('Report it now.')
    expect(container.textContent).toBe('1. Report it now. Call us. 2 * 3')
  })
})

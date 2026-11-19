// Labeling state: one save at a time, so fast key presses can't double-save or skip an item.

export interface LabelKey {
  run_id: string
  sample_id: string
  epoch: number
}

export interface LabelState<T extends LabelKey = LabelKey> {
  items: T[]
  index: number
  status: 'idle' | 'saving'
  pending: (LabelKey & { human_pass: boolean }) | null
  history: (LabelKey & { human_pass: boolean })[]
  error: string | null
}

export type LabelAction<T extends LabelKey = LabelKey> =
  | { type: 'loaded'; items: T[] }
  | { type: 'key'; pass: boolean }
  | { type: 'saved' }
  | { type: 'failed'; message: string }
  | { type: 'skip' }
  | { type: 'undo' }

export const initialLabelState: LabelState = {
  items: [], index: 0, status: 'idle', pending: null, history: [], error: null,
}

export function labelReducer<T extends LabelKey>(state: LabelState<T>, action: LabelAction<T>): LabelState<T> {
  switch (action.type) {
    case 'loaded':
      return { ...state, items: action.items, index: 0, status: 'idle', pending: null, error: null }
    case 'key': {
      const cur = state.items[state.index]
      if (state.status === 'saving' || !cur) return state
      const { run_id, sample_id, epoch } = cur
      return { ...state, status: 'saving', error: null, pending: { run_id, sample_id, epoch, human_pass: action.pass } }
    }
    case 'saved':
      if (!state.pending) return state
      return {
        ...state, status: 'idle', index: state.index + 1, history: [...state.history, state.pending], pending: null,
      }
    case 'failed':
      return { ...state, status: 'idle', pending: null, error: action.message }
    case 'skip':
      if (state.status === 'saving' || state.index >= state.items.length) return state
      return { ...state, index: state.index + 1, error: null }
    case 'undo': {
      if (state.status === 'saving' || state.history.length === 0) return state
      const last = state.history[state.history.length - 1]
      const at = state.items.findIndex(
        (i) => i.run_id === last.run_id && i.sample_id === last.sample_id && i.epoch === last.epoch,
      )
      return { ...state, history: state.history.slice(0, -1), index: at >= 0 ? at : state.index, error: null }
    }
  }
}

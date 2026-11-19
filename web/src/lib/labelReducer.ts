// Labeling state: one save at a time, so fast key presses can't double-save or skip an item.
// A save confirmation names the label it confirms, so a late answer for an old label can't
// mark a different one as saved.

import type { Rubric } from '../api'

export interface LabelKey {
  run_id: string
  sample_id: string
  epoch: number
  rubric: Rubric
}

export type PendingLabel = LabelKey & { human_pass: boolean }

export interface LabelState<T extends LabelKey = LabelKey> {
  items: T[]
  index: number
  status: 'idle' | 'saving'
  pending: PendingLabel | null
  history: PendingLabel[]
  error: string | null
}

export type LabelAction<T extends LabelKey = LabelKey> =
  | { type: 'loaded'; items: T[] }
  | { type: 'reset' }
  | { type: 'key'; pass: boolean }
  | { type: 'saved'; key: PendingLabel }
  | { type: 'failed'; key: PendingLabel; message: string }
  | { type: 'skip' }
  | { type: 'undo' }

export const initialLabelState: LabelState = {
  items: [], index: 0, status: 'idle', pending: null, history: [], error: null,
}

export function labelReducer<T extends LabelKey>(state: LabelState<T>, action: LabelAction<T>): LabelState<T> {
  switch (action.type) {
    case 'loaded':
      return { ...state, items: action.items, index: 0, status: 'idle', pending: null, error: null }
    case 'reset':
      return { ...state, items: [], index: 0, status: 'idle', pending: null, error: null }
    case 'key': {
      const cur = state.items[state.index]
      if (state.status === 'saving' || !cur) return state
      const { run_id, sample_id, epoch, rubric } = cur
      return {
        ...state, status: 'saving', error: null,
        pending: { run_id, sample_id, epoch, rubric, human_pass: action.pass },
      }
    }
    case 'saved':
      if (!state.pending || action.key !== state.pending) return state
      return {
        ...state, status: 'idle', index: state.index + 1, history: [...state.history, state.pending], pending: null,
      }
    case 'failed':
      if (!state.pending || action.key !== state.pending) return state
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

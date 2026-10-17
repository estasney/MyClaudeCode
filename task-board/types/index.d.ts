export type TaskStatus = 'pending' | 'in_progress' | 'completed'

export type Task = {
  id: string
  subject: string
  description: string
  activeForm?: string
  status: TaskStatus
  owner?: string
  metadata?: Record<string, unknown>
  blocks: string[]
  blockedBy: string[]
}

// The fields the person changed on a saved task, in TaskUpdate's own terms.
export type TaskEdit = {
  subject?: string
  description?: string
  status?: TaskStatus | 'deleted'
}

// A task added in the pane that has no id until the draft is saved.
export type NewTask = { draftId: string; subject: string; description: string; status: TaskStatus }

export type Draft = { edits: Record<string, TaskEdit>; added: NewTask[] }

// The row field an Input in the pane is editing.
export type FieldEdit = { key: string; field: 'subject' | 'description' }

declare module 'claude-code' {
  interface PluginState {
    'task-board': {
      tasks: Task[]
      draft: Draft
      editing: FieldEdit | null
      focusedKey: string | null
    }
  }
}

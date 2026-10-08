export type TaskStatus = 'pending' | 'in_progress' | 'completed'

export type Task = {
  id: string
  subject: string
  status: TaskStatus
  owner?: string
  blockedBy: string[]
}

// The fields the person changed on a saved task, in TaskUpdate's own terms.
export type TaskEdit = { subject?: string; status?: TaskStatus | 'deleted' }

// A task added in the pane that has no id until the draft is saved.
export type NewTask = { draftId: string; subject: string; status: TaskStatus }

export type Draft = { edits: Record<string, TaskEdit>; added: NewTask[] }

declare module 'claude-code' {
  interface PluginState {
    'task-board': { tasks: Task[]; draft: Draft; editingId: string | null }
  }
}

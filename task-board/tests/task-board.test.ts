import type { On } from 'claude-code'
import { expect, mock, test } from 'claude-code/testing'

import type { Task } from '../types'

const PANE = {
  plugin: 'task-board',
  component: 'Pane',
  requestId: 'task-board',
  props: {
    title: 'Tasks',
    isFocused: true,
    bodyColumns: 80,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 20 },
    view: {},
  },
} as const

const OPEN = {
  command: 'task-board',
  args: '',
  origin: { kind: 'composer' },
  presentation: { isFullscreen: true, columns: 160 },
} as const

const FOCUS = {
  component: 'Pane',
  requestId: 'task-board',
  origin: { kind: 'person' },
} as const

const TASK_FOLDER = '/home/tester/.claude/tasks/session-1'

const SEEDED: Task[] = [
  {
    id: '1',
    subject: 'Write schema',
    description: 'Define the tables.',
    activeForm: 'Writing schema',
    status: 'pending',
    owner: 'main',
    metadata: { area: 'db' },
    blocks: ['2'],
    blockedBy: [],
  },
  {
    id: '2',
    subject: 'Write migration',
    description: 'Migrate the tables.',
    status: 'pending',
    blocks: [],
    blockedBy: ['1'],
  },
]

type FakeClaudeCode = {
  stored: Task[]
  closedId: string
  focused: string | undefined
  prompt: string
  toasts: string[]
}

// Stands in for Claude Code: the task files under TASK_FOLDER, the task tools, the prompt box, and the pane calls.
const fakeClaudeCode = (on: On): FakeClaudeCode => {
  const claude: FakeClaudeCode = {
    stored: [],
    closedId: '',
    focused: undefined,
    prompt: '',
    toasts: [],
  }

  mock.env(on, { HOME: '/home/tester' })
  on('session.id', () => ({ value: 'session-1' }))
  on('fs.exists', ($, e) => ({ value: e.path === TASK_FOLDER }))
  on('fs.list', () => ({
    value: [
      { name: '.lock', kind: 'file', size: 0, mtimeMs: 0, isLink: false },
      ...claude.stored.map(task => ({
        name: `${task.id}.json`,
        kind: 'file' as const,
        size: 0,
        mtimeMs: 0,
        isLink: false,
      })),
    ],
  }))
  on('fs.read', ($, e) => {
    const task = claude.stored.find(task => e.path === `${TASK_FOLDER}/${task.id}.json`)

    return task === undefined ? { deny: `no file at ${e.path}` } : { value: JSON.stringify(task) }
  })
  on('ui.open', () => ({ value: { isPlaced: true as const } }))
  on('ui.close', ($, e) => {
    claude.closedId = e.id

    return { value: undefined }
  })
  on('ui.focus', ($, e) => {
    claude.focused = e.element

    return {}
  })
  on('ui.toast', ($, e) => {
    claude.toasts.push(e.text)

    return { value: undefined }
  })
  on('prompt.fill', ($, e) => {
    claude.prompt = e.mode === 'replace' ? e.text : claude.prompt + e.text

    return { isFilled: true }
  })
  on('tool.call', { tool: 'TaskCreate' }, ($, e) => {
    const id = String(Math.max(0, ...claude.stored.map(task => Number(task.id))) + 1)
    claude.stored = [
      ...claude.stored,
      {
        id,
        subject: e.subject,
        description: e.description,
        status: 'pending',
        blocks: [],
        blockedBy: [],
      },
    ]

    return { result: { task: { id, subject: e.subject } } }
  })
  on('tool.call', { tool: 'TaskUpdate' }, ($, e) => {
    const { status } = e
    claude.stored =
      status === 'deleted'
        ? claude.stored
            .filter(task => task.id !== e.taskId)
            .map(task => ({
              ...task,
              blocks: task.blocks.filter(id => id !== e.taskId),
              blockedBy: task.blockedBy.filter(id => id !== e.taskId),
            }))
        : claude.stored.map(task =>
            task.id === e.taskId
              ? {
                  ...task,
                  subject: e.subject ?? task.subject,
                  description: e.description ?? task.description,
                  status: status ?? task.status,
                }
              : task,
          )

    return { result: { success: true, taskId: e.taskId, updatedFields: [] } }
  })

  return claude
}

test('pane edits stay in a draft until saved, and close discards them', async ($, on) => {
  const claude = fakeClaudeCode(on)

  for (const surface of ['terminal', 'desktop'] as const) {
    claude.stored = SEEDED
    await $.command.run(OPEN)

    const inactive = await $.ui.mount({
      ...PANE,
      surface,
      props: { ...PANE.props, isFocused: false },
    })
    expect(await inactive.findAll({ type: 'Button' })).toHaveLength(0)
    expect(await inactive.findAll({ type: 'Input' })).toHaveLength(0)
    expect(await inactive.find({ type: 'Text', text: /Write migration/ })).toBeDefined()
    expect(await inactive.find({ type: 'Text', text: 'Ctrl+X Tab to edit' })).toBeDefined()
    await inactive.unmount()

    const ui = await $.ui.mount({ ...PANE, surface })

    expect(await ui.find({ type: 'Text', text: /blocked by #1/ })).toBeDefined()
    expect((await ui.find({ key: 'fill' }))?.props.dimColor).toBe(false)
    const keys = (await ui.findAll({})).map(element => element.key)
    expect(keys.indexOf('new')).toBeLessThan(keys.indexOf('task-1'))
    expect(await ui.find({ type: 'Text', text: 'Define the tables.' })).toBeUndefined()
    await $.ui.focus({ ...FOCUS, element: 'task-1' })
    expect(await ui.find({ type: 'Text', text: 'Define the tables.' })).toBeDefined()

    await ui.input({ key: 'new', text: 'Write tests' })
    await ui.press({ key: 'task-1' })
    await $.ui.focus({ ...FOCUS, element: 'task-2' })
    await ui.press({ key: 'delete' })

    expect(await ui.find({ type: 'Text', text: 'Write tests' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^\[~\] #1/ })).toBeDefined()
    expect(await ui.find({ key: 'task-2' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: '3 unsaved' })).toBeDefined()
    expect(claude.stored).toEqual(SEEDED)

    await $.tool.call({
      tool: 'TaskCreate',
      subject: 'Claude adds',
      description: 'Added by Claude.',
    })
    expect(await ui.find({ type: 'Text', text: 'Claude adds' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: /^\[~\] #1/ })).toBeDefined()

    claude.closedId = ''
    await ui.press({ key: 'save' })
    expect(claude.closedId).toBe('task-board')
    expect(claude.stored).toEqual([
      { ...SEEDED[0], status: 'in_progress', blocks: [] },
      {
        id: '3',
        subject: 'Claude adds',
        description: 'Added by Claude.',
        status: 'pending',
        blocks: [],
        blockedBy: [],
      },
      {
        id: '4',
        subject: 'Write tests',
        description: '',
        status: 'pending',
        blocks: [],
        blockedBy: [],
      },
    ])
    await ui.unmount()

    const saved = claude.stored
    await $.command.run(OPEN)
    const reopened = await $.ui.mount({ ...PANE, surface })
    await $.ui.focus({ ...FOCUS, element: 'task-1' })
    await reopened.press({ key: 'delete' })
    expect((await reopened.find({ key: 'close' }))?.props.label).toBe('discard')
    await reopened.press({ key: 'close' })
    expect(claude.stored).toEqual(saved)
    expect(await reopened.find({ key: 'task-1' })).toBeDefined()

    claude.prompt = ''
    await reopened.press({ key: 'fill' })
    expect(claude.prompt).toContain('#1 [in_progress] Write schema')
    await reopened.unmount()

    claude.stored = []
    await $.command.run(OPEN)
    const empty = await $.ui.mount({ ...PANE, surface })
    expect(await empty.find({ type: 'Text', text: 'No tasks yet.' })).toBeDefined()
    expect((await empty.find({ key: 'fill' }))?.props.dimColor).toBe(true)
    claude.prompt = ''
    claude.toasts = []
    await empty.press({ key: 'fill' })
    expect(claude.prompt).toBe('')
    expect(claude.toasts).toEqual(['No tasks to put in the prompt.'])
    await empty.unmount()
  }
})

test('edit and describe focus their fields in the pane and the new text saves', async ($, on) => {
  const claude = fakeClaudeCode(on)

  for (const surface of ['terminal', 'desktop'] as const) {
    claude.stored = SEEDED
    claude.prompt = 'half-typed question'
    await $.command.run(OPEN)
    const ui = await $.ui.mount({ ...PANE, surface })

    await $.ui.focus({ ...FOCUS, element: 'task-1' })
    await ui.press({ key: 'edit' })
    expect(claude.focused).toBe('subject-1')
    await ui.input({ key: 'subject-1', text: 'Write the schema' })
    expect(await ui.find({ type: 'Text', text: 'Write the schema' })).toBeDefined()

    await $.ui.focus({ ...FOCUS, element: 'task-2' })
    await ui.press({ key: 'describe' })
    expect(claude.focused).toBe('description-2')
    expect((await ui.find({ key: 'description-2' }))?.props.value).toBe('Migrate the tables.')
    expect(claude.prompt).toBe('half-typed question')
    await ui.input({ key: 'description-2', text: 'Migrate the tables and their indexes.' })
    expect(await ui.find({ key: 'description-2' })).toBeUndefined()
    await $.ui.focus({ ...FOCUS, element: 'task-2' })
    expect(
      await ui.find({ type: 'Text', text: 'Migrate the tables and their indexes.' }),
    ).toBeDefined()
    expect(await ui.find({ type: 'Text', text: '2 unsaved' })).toBeDefined()
    expect(claude.stored).toEqual(SEEDED)

    await ui.press({ key: 'save' })
    expect(claude.stored).toEqual([
      { ...SEEDED[0], subject: 'Write the schema' },
      { ...SEEDED[1], description: 'Migrate the tables and their indexes.' },
    ])
    await ui.unmount()

    await $.command.run(OPEN)
    const reopened = await $.ui.mount({ ...PANE, surface })
    await $.ui.focus({ ...FOCUS, element: 'task-1' })
    await reopened.press({ key: 'describe' })
    expect(await reopened.find({ key: 'description-1' })).toBeDefined()
    await reopened.press({ key: 'close' })
    expect(await reopened.find({ key: 'description-1' })).toBeUndefined()
    expect(claude.prompt).toBe('half-typed question')
    await reopened.unmount()
  }
})

import { expect, test } from 'claude-code/testing'

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

test('pane edits stay in a draft until saved, and close discards them', async ($, on) => {
  let board: Task[] = []
  let closedId = ''
  let submitted = ''

  on('ui.open', () => ({ value: { isPlaced: true as const } }))
  on('ui.close', ($, e) => {
    closedId = e.id

    return { value: undefined }
  })
  on('prompt.submit', ($, e) => {
    submitted = e.text

    return { text: e.text }
  })
  on('tool.call', { tool: 'TaskList' }, () => ({ result: { tasks: board } }))
  on('tool.call', { tool: 'TaskCreate' }, ($, e) => {
    const id = String(Math.max(0, ...board.map(task => Number(task.id))) + 1)
    board = [...board, { id, subject: e.subject, status: 'pending', blockedBy: [] }]

    return { result: { task: { id, subject: e.subject } } }
  })
  on('tool.call', { tool: 'TaskUpdate' }, ($, e) => {
    const { status } = e
    board =
      status === 'deleted'
        ? board.filter(task => task.id !== e.taskId)
        : board.map(task =>
            task.id === e.taskId
              ? { ...task, subject: e.subject ?? task.subject, status: status ?? task.status }
              : task,
          )

    return { result: { success: true, taskId: e.taskId, updatedFields: [] } }
  })

  for (const surface of ['terminal', 'desktop'] as const) {
    const seeded: Task[] = [
      { id: '1', subject: 'Write schema', status: 'pending', blockedBy: [] },
      { id: '2', subject: 'Write migration', status: 'pending', blockedBy: ['1'] },
    ]
    board = seeded
    await $.command.run(OPEN)

    const inactive = await $.ui.mount({
      ...PANE,
      surface,
      props: { ...PANE.props, isFocused: false },
    })
    expect(await inactive.findAll({ type: 'Button' })).toHaveLength(0)
    expect(await inactive.findAll({ type: 'Input' })).toHaveLength(0)
    expect(await inactive.find({ type: 'Text', text: 'Write migration' })).toBeDefined()
    await inactive.unmount()

    const ui = await $.ui.mount({ ...PANE, surface })

    expect(await ui.find({ type: 'Text', text: /blocked by #1/ })).toBeDefined()
    expect((await ui.find({ key: 'submit' }))?.props.dimColor).toBe(false)
    const keys = (await ui.findAll({})).map(element => element.key)
    expect(keys.indexOf('new')).toBeLessThan(keys.indexOf('row-1'))

    await ui.input({ key: 'new', text: 'Write tests' })
    await ui.press({ key: 'status-1' })
    await ui.press({ key: 'edit-1' })
    await ui.input({ key: 'subject-1', text: 'Write the schema' })
    await ui.press({ key: 'delete-2' })

    expect(await ui.find({ type: 'Text', text: 'Write tests' })).toBeDefined()
    expect((await ui.find({ key: 'status-1' }))?.props.label).toBe('[~]')
    expect(await ui.find({ type: 'Text', text: 'Write the schema' })).toBeDefined()
    expect(await ui.find({ key: 'delete-2' })).toBeUndefined()
    expect(await ui.find({ type: 'Text', text: '3 unsaved' })).toBeDefined()
    expect(board).toEqual(seeded)

    await $.tool.call({ tool: 'TaskCreate', subject: 'Claude adds', description: '' })
    expect(await ui.find({ type: 'Text', text: 'Claude adds' })).toBeDefined()
    expect(await ui.find({ type: 'Text', text: 'Write the schema' })).toBeDefined()

    closedId = ''
    await ui.press({ key: 'save' })
    expect(closedId).toBe('task-board')
    expect(board.map(task => [task.subject, task.status])).toEqual([
      ['Write the schema', 'in_progress'],
      ['Claude adds', 'pending'],
      ['Write tests', 'pending'],
    ])
    await ui.unmount()

    const saved = board
    await $.command.run(OPEN)
    const reopened = await $.ui.mount({ ...PANE, surface })
    await reopened.press({ key: 'delete-1' })
    expect((await reopened.find({ key: 'close' }))?.props.label).toBe('discard and close')
    await reopened.press({ key: 'close' })
    expect(board).toEqual(saved)
    expect(await reopened.find({ key: 'delete-1' })).toBeDefined()

    submitted = ''
    await reopened.press({ key: 'submit' })
    expect(submitted).toContain('#1 [in_progress] Write the schema')
    await reopened.unmount()

    board = []
    await $.command.run(OPEN)
    const empty = await $.ui.mount({ ...PANE, surface })
    expect((await empty.find({ key: 'submit' }))?.props.dimColor).toBe(true)
    submitted = ''
    await empty.press({ key: 'submit' })
    expect(submitted).toBe('')
    await empty.unmount()
  }
})

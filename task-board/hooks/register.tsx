import { atom, read, update } from 'claude-code'
import type { BuiltinToolInputs, EngineInterface, Register } from 'claude-code'

import type { Draft, NewTask, Task, TaskEdit, TaskStatus } from '../types'

const PANE = 'task-board'
const tasks = atom({ plugin: 'task-board', key: 'tasks' } as const, [])
const draft = atom({ plugin: 'task-board', key: 'draft' } as const, { edits: {}, added: [] })
const editingId = atom({ plugin: 'task-board', key: 'editingId' } as const, null)
const focusedKey = atom({ plugin: 'task-board', key: 'focusedKey' } as const, null)

const statusMark: Record<TaskStatus, string> = {
  pending: '[ ]',
  in_progress: '[~]',
  completed: '[x]',
}

const statusAfter: Record<TaskStatus, TaskStatus> = {
  pending: 'in_progress',
  in_progress: 'completed',
  completed: 'pending',
}

type BoardRow = {
  source: { kind: 'saved'; id: string } | { kind: 'new'; draftId: string }
  key: string
  label: string
  subject: string
  status: TaskStatus
  blockedBy: string[]
  isEdited: boolean
}

const composeRows = (saved: Task[], pending: Draft): BoardRow[] => [
  ...saved.flatMap(task => {
    const edit = pending.edits[task.id]
    const status = edit?.status ?? task.status
    if (status === 'deleted') {
      return []
    }

    return [
      {
        source: { kind: 'saved', id: task.id } as const,
        key: task.id,
        label: `#${task.id}`,
        subject: edit?.subject ?? task.subject,
        status,
        blockedBy: task.blockedBy,
        isEdited: edit !== undefined,
      },
    ]
  }),
  ...pending.added.map(added => ({
    source: { kind: 'new', draftId: added.draftId } as const,
    key: added.draftId,
    label: 'new',
    subject: added.subject,
    status: added.status,
    blockedBy: [],
    isEdited: true,
  })),
]

const editRow = (pending: Draft, row: BoardRow, change: TaskEdit): Draft => {
  const { source } = row
  const { subject, status } = change
  switch (source.kind) {
    case 'saved':
      return {
        ...pending,
        edits: { ...pending.edits, [source.id]: { ...pending.edits[source.id], ...change } },
      }
    case 'new':
      return {
        ...pending,
        added:
          status === 'deleted'
            ? pending.added.filter(added => added.draftId !== source.draftId)
            : pending.added.map(added =>
                added.draftId === source.draftId
                  ? {
                      ...added,
                      subject: subject ?? added.subject,
                      status: status ?? added.status,
                    }
                  : added,
              ),
      }
    default: {
      const unknown: never = source
      throw new Error(`Unknown board row source: ${JSON.stringify(unknown)}`)
    }
  }
}

const syncTasks = async ($: EngineInterface) => {
  const listed = await $.tool.call({ tool: 'TaskList' })
  if (listed.deny !== undefined) {
    $.ui.toast(`Task list refused: ${listed.deny}`)
  } else if (listed.isError) {
    $.ui.toast(`Task list failed: ${listed.text}`)
  } else {
    await update($, tasks, () => listed.result.tasks)
  }
}

const updateTask = async ($: EngineInterface, change: BuiltinToolInputs['TaskUpdate']) => {
  const updated = await $.tool.call({ tool: 'TaskUpdate', ...change })
  if (updated.deny !== undefined) {
    $.ui.toast(`Task change refused: ${updated.deny}`)
  } else if (updated.isError) {
    $.ui.toast(`Task change failed: ${updated.text}`)
  } else if (!updated.result.success) {
    $.ui.toast(`Task change failed: ${updated.result.error ?? 'no reason given'}`)
  }
}

const createTask = async ($: EngineInterface, added: NewTask) => {
  const created = await $.tool.call({
    tool: 'TaskCreate',
    subject: added.subject,
    description: added.subject,
  })
  if (created.deny !== undefined) {
    $.ui.toast(`Task add refused: ${created.deny}`)
  } else if (created.isError) {
    $.ui.toast(`Task add failed: ${created.text}`)
  } else if (added.status !== 'pending') {
    await updateTask($, { taskId: created.result.task.id, status: added.status })
  }
}

// The pane's own tool calls skip this plugin's tool.call hook, so saving syncs the board itself.
const saveDraft = async ($: EngineInterface) => {
  const pending = await read($, draft)
  for (const [taskId, edit] of Object.entries(pending.edits)) {
    await updateTask($, { taskId, ...edit })
  }
  for (const added of pending.added) {
    await createTask($, added)
  }
  await update($, draft, () => ({ edits: {}, added: [] }))
  await syncTasks($)
}

// The pane's own $.ui.close skips this plugin's ui.close hook, so its buttons discard here.
const closeBoard = async ($: EngineInterface) => {
  await update($, draft, () => ({ edits: {}, added: [] }))
  await update($, editingId, () => null)
  await $.ui.close({ id: PANE })
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'task-board',
      description: 'Show the task list in a pane you and Claude both edit',
      immediate: true,
    })

    return next(e)
  })

  on('command.run', { command: 'task-board' }, async $ => {
    await syncTasks($)
    await $.ui.open({ id: PANE, title: 'Tasks', focus: true })

    return {}
  })

  // Claude's task changes pass here and redraw the board.
  on('tool.call', { tool: ['TaskCreate', 'TaskUpdate'] }, async ($, e, next) => {
    const ran = await next(e)
    await syncTasks($)

    return ran
  }).catch(($, e, next) => next(e))

  // Closing the pane with Ctrl+X X or Esc discards what was not saved.
  on('ui.close', { id: PANE }, async ($, e, next) => {
    await update($, draft, () => ({ edits: {}, added: [] }))
    await update($, editingId, () => null)

    return next(e)
  }).catch(($, e, next) => next(e))

  // The hotkey buttons join the ring like any Button, so the ring wraps past them.
  on('ui.focus', { component: 'Pane', requestId: PANE }, async ($, e, next) => {
    const element = e.element === 'edit' ? 'new' : e.element === 'delete' ? 'close' : e.element
    const moved = await next({ ...e, element })
    if (moved.deny === undefined) {
      await update($, focusedKey, () => element ?? null)
    }

    return moved
  }).catch(($, e, next) => next(e))

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    if (e.surface === 'mobile') {
      const { Text } = $.ui.resolve(e)

      return <Text dimColor>The task board needs a surface with text input.</Text>
    }

    const { Box, Button, Input, Text } = $.ui.resolve(e)
    const pending = await read($, draft)
    const rows = composeRows(await read($, tasks), pending)
    // While the prompt has the keyboard the board is a dimmed, read-only list.
    const isActive = e.props.isFocused
    const editing = isActive ? await read($, editingId) : null
    const focused = isActive ? await read($, focusedKey) : null
    const focusedRow = rows.find(row => `task-${row.key}` === focused)
    const doneCount = rows.filter(row => row.status === 'completed').length
    const unsavedCount = Object.keys(pending.edits).length + pending.added.length
    const labelWidth = Math.max(3, ...rows.map(row => row.label.length))

    return (
      <Box flexDirection="column" paddingX={1}>
        <Box columnGap={2} marginBottom={1}>
          <Text bold dimColor={!isActive}>
            Tasks
          </Text>
          <Text dimColor>
            {rows.length - doneCount} open · {doneCount} done
          </Text>
          {unsavedCount > 0 && (
            <Text color="warning" dimColor={!isActive}>
              {unsavedCount} unsaved
            </Text>
          )}
        </Box>
        {/* Above the list, so a new row does not shift the focus ring off this field. */}
        {isActive && (
          <Box marginBottom={1}>
            <Input
              key="new"
              label="+ "
              placeholder="New task"
              value=""
              autoFocus={editing === null ? true : undefined}
              submitLabel="add"
              onSubmit={async subject => {
                if (subject.trim() !== '') {
                  const added: NewTask = {
                    draftId: `new-${crypto.randomUUID()}`,
                    subject: subject.trim(),
                    status: 'pending',
                  }
                  await update($, draft, current => ({
                    ...current,
                    added: [...current.added, added],
                  }))
                }
              }}
            />
          </Box>
        )}
        {rows.length === 0 && <Text dimColor>No tasks yet.</Text>}
        {rows.map(row =>
          isActive && row.key !== editing ? (
            <Button
              key={`task-${row.key}`}
              plain
              onPress={() =>
                update($, draft, current =>
                  editRow(current, row, { status: statusAfter[row.status] }),
                )
              }
            >
              <Text dimColor>{`${statusMark[row.status]} ${row.label.padEnd(labelWidth)} `}</Text>
              <Text
                bold={row.status === 'in_progress'}
                italic={row.isEdited}
                dimColor={row.status === 'completed'}
                strikethrough={row.status === 'completed'}
              >
                {row.subject}
              </Text>
              {row.blockedBy.length > 0 && (
                <Text color="warning">
                  {` blocked by ${row.blockedBy.map(id => `#${id}`).join(', ')}`}
                </Text>
              )}
            </Button>
          ) : (
            <Box key={`row-${row.key}`} columnGap={1}>
              <Text dimColor>{statusMark[row.status]}</Text>
              <Box width={labelWidth} flexShrink={0}>
                <Text dimColor>{row.label}</Text>
              </Box>
              {row.key === editing ? (
                <>
                  <Box flexGrow={1} flexShrink={1} minWidth={0}>
                    <Input
                      key={`subject-${row.key}`}
                      value={row.subject}
                      autoFocus
                      submitLabel="keep"
                      onSubmit={async subject => {
                        await update($, draft, current => editRow(current, row, { subject }))
                        await update($, editingId, () => null)
                      }}
                    />
                  </Box>
                  <Box flexShrink={0} marginLeft={2}>
                    <Button
                      key={`cancel-${row.key}`}
                      plain
                      dimColor
                      label="cancel"
                      onPress={() => update($, editingId, () => null)}
                    />
                  </Box>
                </>
              ) : (
                <Text dimColor strikethrough={row.status === 'completed'}>
                  {row.subject}
                  {row.blockedBy.length > 0 &&
                    ` blocked by ${row.blockedBy.map(id => `#${id}`).join(', ')}`}
                </Text>
              )}
            </Box>
          ),
        )}
        {!isActive && (
          <Box marginTop={1}>
            <Text dimColor>Ctrl+X Tab to edit</Text>
          </Box>
        )}
        {isActive && (
          <>
            <Box marginTop={1} flexDirection="column" alignItems="flex-start">
              <Button
                key="save"
                variant="primary"
                label="save"
                onPress={async () => {
                  await saveDraft($)
                  await closeBoard($)
                }}
              />
              <Button
                key="fill"
                label="prompt"
                dimColor={rows.length === 0}
                onPress={async () => {
                  await saveDraft($)
                  const saved = await read($, tasks)
                  await closeBoard($)
                  if (saved.length === 0) {
                    $.ui.toast('No tasks to put in the prompt.')
                    return
                  }
                  const filled = await $.prompt.fill({
                    mode: 'insert',
                    text: [
                      'User updated tasks:',
                      ...saved.map(
                        task =>
                          `#${task.id} [${task.status}] ${task.subject}` +
                          (task.blockedBy.length > 0
                            ? ` (blocked by ${task.blockedBy.map(id => `#${id}`).join(', ')})`
                            : ''),
                      ),
                    ].join('\n'),
                  })
                  if (!filled.isFilled) {
                    $.ui.toast(`Prompt fill refused: ${filled.refusal ?? 'no reason given'}`)
                  }
                }}
              />
              <Button
                key="close"
                role="dismiss"
                label={unsavedCount > 0 ? 'discard' : 'close'}
                onPress={() => closeBoard($)}
              />
            </Box>
            <Box columnGap={2}>
              <Button
                key="edit"
                plain
                hotkey="e"
                label="edit"
                dimColor={focusedRow === undefined}
                onPress={async () => {
                  if (focusedRow !== undefined) {
                    await update($, editingId, () => focusedRow.key)
                    await $.ui.focus({ requestId: PANE, key: `subject-${focusedRow.key}` })
                  }
                }}
              />
              <Button
                key="delete"
                plain
                hotkey="d"
                label="delete"
                dimColor={focusedRow === undefined}
                onPress={async () => {
                  if (focusedRow !== undefined) {
                    await update($, draft, current =>
                      editRow(current, focusedRow, { status: 'deleted' }),
                    )
                  }
                }}
              />
              <Text dimColor>Enter cycles status · Esc back to prompt</Text>
            </Box>
          </>
        )}
      </Box>
    )
  })
}

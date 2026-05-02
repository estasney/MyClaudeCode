# Submission, reset, and default values

How `form.handleSubmit` flows, how to wire server errors back into the form, how to handle the loaded-record-for-edit pattern, and why `defaultValues` is not reactive.

## The submit flow

```ts
const form = useForm({
  defaultValues: { email: '', password: '' },
  validators: { onSubmit: schema },
  onSubmit: async ({ value, formApi }) => {
    await api.login(value)
  },
})
```

The sequence when `form.handleSubmit()` is called:

1. All `onSubmit` + `onSubmitAsync` validators run (form-level and per-field).
2. If any return an error, `state.isSubmitted = true`, `state.isFormValid = false`, and **the `onSubmit` option is not called**.
3. Otherwise, the `onSubmit` option executes with `{ value, formApi, meta? }`.
4. `state.isSubmitSuccessful` becomes true if the handler completes without throwing.

**You must call `preventDefault` yourself** on the native `<form>`:

```tsx
<form
  onSubmit={(e) => {
    e.preventDefault()
    form.handleSubmit()
  }}
>
```

Forgetting this is a common bug — the browser submits the form normally and you get a page reload.

## The `onSubmit` signature

```ts
onSubmit: async ({ value, formApi, meta }) => {
  // value: the full typed form data (see transform warning below)
  // formApi: the same form object; use for reset, setFieldMeta, etc.
  // meta: per-submit metadata if you used onSubmitMeta
}
```

## Zod transforms are NOT preserved into `onSubmit`

From the docs: *"While TanStack Form provides Standard Schema support for validation, it does not preserve the schema's output data. The value passed to onSubmit will always be the input."*

If your schema uses `z.coerce.number()`, `.transform(...)`, `.default(...)`, or anything else that changes the shape between input and output, **re-parse in the handler**:

```ts
onSubmit: async ({ value }) => {
  const parsed = schema.parse(value)
  await api.save(parsed)
}
```

This is a breaking difference from RHF: `zodResolver` does preserve transforms. Migrated RHF forms that relied on coercion will silently send the untransformed input unless you re-parse.

## `onSubmitMeta` — per-click metadata

Useful for "Save" vs "Save & Continue" vs "Save Draft" from different buttons:

```ts
const form = useForm({
  defaultValues: { ... },
  onSubmitMeta: { action: 'save' as 'save' | 'saveAndContinue' | 'draft' },
  onSubmit: async ({ value, meta }) => {
    switch (meta.action) {
      case 'save': await api.save(value); break
      case 'saveAndContinue': await api.save(value); router.next(); break
      case 'draft': await api.saveDraft(value); break
    }
  },
})

<button onClick={() => form.handleSubmit({ action: 'save' })}>Save</button>
<button onClick={() => form.handleSubmit({ action: 'saveAndContinue' })}>Save & continue</button>
<button onClick={() => form.handleSubmit({ action: 'draft' })}>Save draft</button>
```

The `onSubmitMeta` field in `useForm` both declares the shape and provides a default for `handleSubmit()` calls with no argument.

## Handling server errors

After `onSubmit` runs, if the server rejects some fields, write the errors back into the form:

```ts
onSubmit: async ({ value, formApi }) => {
  try {
    await api.save(value)
    formApi.reset()
  } catch (err) {
    if (err.code === 'EMAIL_TAKEN') {
      formApi.setFieldMeta('email', (prev) => ({
        ...prev,
        errorMap: { ...prev.errorMap, onServer: 'Email already in use' },
      }))
    }
    if (err.fieldErrors) {
      for (const [path, message] of Object.entries(err.fieldErrors)) {
        formApi.setFieldMeta(path, (prev) => ({
          ...prev,
          errorMap: { ...prev.errorMap, onServer: message },
        }))
      }
    }
  }
}
```

The `onServer` slot is specifically for this — it stays separate from sync schema errors so you can style them differently in the UI, and it clears independently.

Alternative: let form-level `onSubmitAsync` do the network call and return the error shape:

```ts
validators: {
  onSubmitAsync: async ({ value }) => {
    const res = await api.save(value)
    if (!res.ok) {
      return { fields: res.fieldErrors, form: 'Save failed' }
    }
    return undefined
  },
}
```

When the async validator returns errors, the `onSubmit` option is not called. This can be cleaner when the only server check IS the save — you don't need to distinguish "validating with the server" from "saving."

## Submit state for the button

```tsx
<form.Subscribe selector={(s) => [s.canSubmit, s.isSubmitting] as const}>
  {([canSubmit, isSubmitting]) => (
    <button type="submit" disabled={!canSubmit}>
      {isSubmitting ? 'Saving...' : 'Save'}
    </button>
  )}
</form.Subscribe>
```

`canSubmit` is a composite gate — it's `false` while:
- Any async validator is in flight.
- The `onSubmit` handler is running.
- Critical blocking errors exist.

`isSubmitting` is specifically the `onSubmit` handler's lifecycle. Use it for the loading indicator.

| State | Meaning | RHF equivalent |
|---|---|---|
| `canSubmit` | OK to call `handleSubmit` right now | no direct equivalent |
| `isSubmitting` | handler in progress | `formState.isSubmitting` |
| `isSubmitted` | submit has been attempted | `formState.isSubmitted` |
| `isSubmitSuccessful` | last submit completed | `formState.isSubmitSuccessful` |
| `submissionAttempts` | counter | `formState.submitCount` |

## Reset

`form.reset()` with no arguments restores the original `defaultValues`. `form.reset(newValues)` resets AND treats the new values as the new defaults for subsequent dirty comparisons.

```ts
// back to original defaults
formApi.reset()

// after a successful save with server-assigned values
formApi.reset({ ...value, id: response.id, updatedAt: response.updatedAt })
```

**No `keepDirty` / `keepValues` flags.** RHF's `reset(values, { keepDirty: true })` has no direct equivalent. If you need "reset most fields but keep what the user changed," diff and reset manually:

```ts
const current = form.state.values
const next = { ...newDefaults, ...pickDirtyFields(current, form.state.fieldMeta) }
form.reset(next)
```

## `defaultValues` is not reactive

This is the biggest divergence from modern RHF. RHF supports a reactive `values` prop: `useForm({ values: loadedRecord })` — as `loadedRecord` changes, the form updates. TanStack Form does not. `defaultValues` is consumed once on mount.

For the loaded-record-for-edit pattern:

```tsx
const { data: user, isLoading } = useQuery({
  queryKey: ['user', id],
  queryFn: () => api.user(id),
})

const form = useForm({
  defaultValues: { name: '', email: '' },
  onSubmit: async ({ value }) => api.updateUser(id, value),
})

useEffect(() => {
  if (user) form.reset(user)
}, [user])
```

The `useEffect` is load-bearing. Two patterns if you want to be more explicit:

### Gate render on the query

```tsx
if (isLoading) return <Spinner />
return <UserEditForm initialValues={user} />
```

And in `UserEditForm`, use `initialValues` as `defaultValues` directly — no reset needed because the form only mounts after data arrives.

### Reset manually on save

```ts
onSubmit: async ({ value, formApi }) => {
  const updated = await api.updateUser(id, value)
  formApi.reset(updated)
}
```

This resets the form to the server's version after save, so `isDefaultValue` becomes true again and the "unsaved changes" UI clears.

## `setFieldValue` does not trigger validators

Since v1.14.2. Writing `form.setFieldValue('x', newVal)` updates the store but runs no validators.

Two options when you need validation to run:

1. Use `field.handleChange(newVal)` from inside a render prop (but this requires holding the field handle).
2. Call `form.validateField('x', 'change')` after `setFieldValue`.

For cascaded updates inside a listener:

```tsx
<form.Field
  name="country"
  listeners={{
    onChange: ({ value }) => {
      form.setFieldValue('province', '')
      form.validateField('province', 'change')
    },
  }}
>
  {(f) => <select {...bind(f)}>...</select>}
</form.Field>
```

## Form-level errors outside the fields

Sometimes validation errors aren't tied to a specific field — "this combination is invalid" at the form level. Form-level errors go in `form.state.errors`:

```tsx
<form.Subscribe selector={(s) => s.errors}>
  {(errors) =>
    errors.length > 0 && (
      <div role="alert" className="form-errors">
        {errors.map((e, i) => (
          <div key={i}>{typeof e === 'string' ? e : e.message}</div>
        ))}
      </div>
    )
  }
</form.Subscribe>
```

These come from:
- Form-level validators that return a plain string (e.g., `onSubmitAsync: async () => 'Save failed'`).
- The `form` key in the structured return: `return { form: 'Critical error' }`.
- `form.setFormError(...)` — but you'll usually set these through validator returns, not imperatively.

# RHF → TanStack Form migration reference

A comprehensive mapping from react-hook-form APIs and patterns to TanStack Form equivalents, with the RHF behaviors that have no direct counterpart flagged explicitly.

## Top-level setup

| RHF | TanStack Form |
|---|---|
| `useForm<T>({ resolver: zodResolver(s), defaultValues })` | `useForm({ defaultValues, validators: { onSubmit: s } })` — Zod goes straight in; Standard Schema, no adapter |
| `useForm<T>()` generic | types flow from `defaultValues`; don't pass `<T>` to `useForm`. Use `satisfies MyType` on the defaults object if you need to nail down the shape |
| `useForm({ mode: 'onChange' })` | `validators: { onChange: schema }` — per-trigger, not form-wide |
| `useForm({ mode: 'onSubmit', reValidateMode: 'onChange' })` | `validationLogic: revalidateLogic()` + `validators: { onDynamic: schema }` |
| `useForm({ mode: 'all' })` | set both `onChange` and `onBlur` validators |
| `useForm({ values })` reactive prop | **no equivalent** — use `useEffect(() => form.reset(record), [record])` |
| `useForm({ shouldUnregister: true })` | **no equivalent** — values persist on field unmount; clear manually in a listener or use `z.discriminatedUnion` |
| `FormProvider` + `useFormContext` | `createFormHook` + `useFormContext` from the generated module (different API, same intent) |

## Registering fields

| RHF | TanStack Form |
|---|---|
| `<input {...register('email')} />` | `<form.Field name="email">{(f) => <input value={f.state.value} onChange={(e) => f.handleChange(e.target.value)} onBlur={f.handleBlur} />}</form.Field>` |
| `register('email', { required: true })` | field-level `validators: { onChange: z.string().min(1) }` |
| `<Controller name render control>` | same as a `<form.Field>` — no distinction between native and custom inputs |
| `useController({ name, control })` | `useFieldContext<T>()` inside a component under `form.AppField` |
| `useFieldArray({ control, name: 'items' })` | `<form.Field name="items" mode="array">{(itemsField) => ...}</form.Field>` |

## Reading and watching values

| RHF | TanStack Form |
|---|---|
| `watch('email')` (component re-renders) | `useStore(form.store, (s) => s.values.email)` |
| `watch()` (all fields) | `useStore(form.store, (s) => s.values)` — **watch for issue #1148** (return a narrower selector) |
| `useWatch({ name: 'email' })` | same as `useStore` above |
| `getValues()` | `form.state.values` (snapshot) |
| `getValues('email')` | `form.getFieldValue('email')` |
| `getFieldState('email')` | `form.state.fieldMeta['email']` or `field.state.meta` inside a render prop |

## Writing values

| RHF | TanStack Form |
|---|---|
| `setValue('email', 'a@b.com')` | `form.setFieldValue('email', 'a@b.com')` — **does not trigger validators** (v1.14.2+); follow with `form.validateField('email', 'change')` if needed |
| `setValue('email', v, { shouldValidate: true })` | `field.handleChange(v)` (from inside a render prop or listener with fieldApi) |
| `setValue('email', v, { shouldDirty: false })` | not directly supported; dirty flag follows the change |
| `reset()` | `form.reset()` |
| `reset(values)` | `form.reset(values)` |
| `reset(values, { keepDirty: true })` | **no equivalent** — diff and reset manually |

## Validation triggering

| RHF | TanStack Form |
|---|---|
| `trigger()` | `form.validateAllFields('change')` |
| `trigger('email')` | `form.validateField('email', 'change')` |
| `trigger(['email', 'password'])` | loop `form.validateField` for each, or call `validateAllFields` |
| `clearErrors()` | iterate `fieldMeta` and call `setFieldMeta` with empty `errorMap`; no single-call equivalent |
| `clearErrors('email')` | `form.setFieldMeta('email', (m) => ({ ...m, errorMap: {} }))` |
| `setError('email', { message })` | `form.setFieldMeta('email', (m) => ({ ...m, errorMap: { ...m.errorMap, onSubmit: 'msg' } }))` |

## Form state reads

| RHF `formState.xxx` | TanStack `form.state.xxx` |
|---|---|
| `isDirty` | `isDirty` — **persistent** in TanStack; use `!isDefaultValue` for RHF semantics |
| `isValid` | `isValid` (composite) / `isFieldsValid` / `isFormValid` |
| `isSubmitting` | `isSubmitting` |
| `isSubmitted` | `isSubmitted` |
| `isSubmitSuccessful` | `isSubmitSuccessful` |
| `isValidating` | `isValidating` / `isFieldsValidating` / `isFormValidating` |
| `submitCount` | `submissionAttempts` |
| `touchedFields` | `fieldMeta[path].isTouched` |
| `dirtyFields` | `fieldMeta[path].isDirty` |
| `errors` | `form.state.errors` (form-level) + `fieldMeta[path].errors` (per field) — **flatter structure**, no nested tree |

**Critical:** reading `form.state.xxx` inline does not subscribe the component. To re-render on changes, use `form.Subscribe` or `useStore(form.store, selector)`.

## Submission

| RHF | TanStack Form |
|---|---|
| `handleSubmit(onValid)(e)` | `(e) => { e.preventDefault(); form.handleSubmit() }` with `onSubmit` in `useForm` options |
| `handleSubmit(onValid, onInvalid)(e)` | use `form.state.submissionAttempts` + `form.state.errors` to branch in UI; no separate invalid callback |
| `<button disabled={!formState.isValid}>` | `<form.Subscribe selector={(s) => s.canSubmit}>{c => <button disabled={!c}/>}</form.Subscribe>` |

## `useFieldArray`

| RHF | TanStack Form |
|---|---|
| `const { fields, append, prepend, remove, swap, move, insert, update, replace } = useFieldArray({ control, name: 'items' })` | `<form.Field name="items" mode="array">{(itemsField) => ...}</form.Field>` — array methods on the fieldApi |
| `append(item)` | `itemsField.pushValue(item)` |
| `prepend(item)` | `itemsField.insertValue(0, item)` |
| `remove(index)` | `itemsField.removeValue(index)` |
| `remove()` (all) | `itemsField.clearValues()` |
| `swap(a, b)` | `itemsField.swapValues(a, b)` |
| `move(from, to)` | `itemsField.moveValue(from, to)` |
| `insert(index, item)` | `itemsField.insertValue(index, item)` |
| `update(index, item)` | `itemsField.replaceValue(index, item)` |
| `replace(array)` | no direct equivalent; `clearValues()` + loop `pushValue`, or `form.setFieldValue('items', array)` + `validateField` |
| `fields[i].id` (stable key) | **you generate the ID yourself** — store on the item, e.g., `{ id: crypto.randomUUID(), ... }` |

## Validation patterns

| RHF pattern | TanStack Form pattern |
|---|---|
| `zodResolver(schema)` (form-level) | `validators: { onChange: schema }` (or `onBlur`, `onSubmit`) |
| Per-field Zod via `register('x', { validate })` | `<form.Field name="x" validators={{ onChange: z.string().min(3) }}>` |
| Async validate in `register('x', { validate })` | `validators: { onChangeAsync: async ({ value, signal }) => ... }` — built-in `AbortSignal` |
| Debounced async with `lodash.debounce` in component | `onChangeAsyncDebounceMs: 500` sibling option |
| Cross-field: `watch('password')` + `trigger('confirm')` in `useEffect` | `onChangeListenTo: ['password']` on the dependent field's validator |
| Cross-field: form-level `superRefine` | same — form-level Zod schema with `superRefine` |
| Conditional required: `required: shouldBeRequired` | `z.discriminatedUnion` or `superRefine` gated on the toggle |

## Composition patterns

| RHF pattern | TanStack Form pattern |
|---|---|
| Reusable `<TextField>` wrapping `useController` | reusable `<TextField>` using `useFieldContext<string>()` inside `form.AppField` |
| `<FormProvider>` at top + nested sections consume via `useFormContext` | `createFormHook` + `useAppForm` + `form.AppField` + `withForm` for sub-components |
| Multiple forms sharing a field group | `withFieldGroup` |

## Things RHF does that TanStack Form does not

Flag these for explicit handling during migration:

**1. Reactive `values` prop.** RHF `useForm({ values: loadedRecord })` keeps the form in sync as `loadedRecord` changes. TanStack Form requires `useEffect(() => form.reset(record), [record])` — the form responds to the effect, not to a prop.

**2. `shouldUnregister: true`.** Fields that unmount keep their values in TanStack Form. For conditional fields with persistence concerns, clear manually in a listener or use discriminated unions.

**3. `keepDirty` / `keepValues` / `keepDefaultValues` on reset.** Not supported — `reset(values)` is all-or-nothing.

**4. `resolver` output preserving Zod transforms.** `zodResolver` runs the full Zod pipeline including transforms; `value` in the submit handler is the output. TanStack Form passes the *input* to `onSubmit` — re-parse if you need the transform output.

**5. Nested `errors` tree.** RHF exposes `errors.address?.city?.message` as a mirror of form shape. TanStack Form has a flat per-field meta structure accessed via `fieldMeta[path]` or the local field's `state.meta`.

**6. `errors[name].ref` back-pointer to the input DOM.** Not supported — input refs are not held centrally. For "scroll to first error," iterate your known field paths or use an `Object.keys(fieldMeta)` loop combined with your own ID convention.

**7. `register(..., { disabled: true })` with form-wide disable.** TanStack Form has no field-level disable flag in the API. Disable via the input's own `disabled` prop based on a derived state.

## Things TanStack Form does that RHF does not

For completeness:

**1. `AbortSignal` in async validators.** Built-in, passed to the validator, cancels in-flight `fetch` on next change.

**2. Per-trigger validator slots.** `onChange`, `onBlur`, `onSubmit`, `onMount`, `onChangeAsync`, etc. — each independent. RHF has a single validate function per field.

**3. `onChangeListenTo` / `onBlurListenTo`.** Declarative cross-field validator deps. RHF requires manual `watch` + `trigger`.

**4. `onSubmitMeta`.** Per-submit metadata typed at the form level. RHF requires carrying state externally.

**5. Standard Schema.** Zod, Valibot, ArkType, Effect/Schema all work via the same validator slots. RHF requires a separate resolver per schema library.

**6. `isBlurred` distinct from `isTouched`.** `isTouched` is change-or-blur; `isBlurred` is blur only. RHF's `touchedFields` combines both.

**7. `isDefaultValue`.** Computed on every change so `!isDefaultValue` gives you non-persistent dirty. RHF's `isDirty` is non-persistent by default but doesn't expose the "compared to defaults" signal directly.

## Migration strategy

A pragmatic order of operations when porting an RHF form to TanStack Form:

1. **Keep the Zod schema as-is.** It just works with Standard Schema in `validators.onChange`.
2. **Translate `useForm` options.** `mode` → validator slot; `defaultValues` stays the same.
3. **Convert `register` calls to `<form.Field>`.** Mechanical but tedious. Use the `bind` helper from [RENDERING.md](RENDERING.md) to stay concise.
4. **Convert `<Controller>` calls to `<form.Field>`.** Identical now — same pattern as native inputs.
5. **Convert `useFieldArray` to `<form.Field mode="array">`.** Rename methods per the table above. Add stable IDs if the form supports reordering.
6. **Handle `watch` calls** — replace with `useStore(form.store, selector)` (for logic) or `<form.Subscribe>` (for JSX).
7. **Re-check cross-field validators.** If the RHF form had `trigger` calls driven by `watch` in `useEffect`, replace with `onChangeListenTo` on the dependent field.
8. **Verify `.transform()` usage.** Any Zod schema with `.transform` or `.coerce` needs a re-parse inside `onSubmit`.
9. **Verify conditional fields.** If the RHF form relied on `shouldUnregister`, decide on discriminated union vs listener-based clear.
10. **Run the form.** Specifically check: submit flow, error display after each validation trigger, cross-field clearing behavior, reset after save.

## A worked migration example

Before (RHF):

```tsx
function EditUser({ user }: { user: User }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } =
    useForm<UserInput>({
      resolver: zodResolver(userSchema),
      values: user,
    })

  return (
    <form onSubmit={handleSubmit(api.updateUser)}>
      <input {...register('email')} />
      {errors.email && <p>{errors.email.message}</p>}

      <input {...register('name')} />
      {errors.name && <p>{errors.name.message}</p>}

      <button disabled={isSubmitting}>Save</button>
    </form>
  )
}
```

After (TanStack Form):

```tsx
function EditUser({ user }: { user: User }) {
  const form = useForm({
    defaultValues: { email: user.email, name: user.name },
    validators: { onChange: userSchema },
    onSubmit: async ({ value }) => api.updateUser(user.id, value),
  })

  useEffect(() => {
    form.reset({ email: user.email, name: user.name })
  }, [user])

  return (
    <form onSubmit={(e) => { e.preventDefault(); form.handleSubmit() }}>
      <form.Field name="email">
        {(f) => (
          <>
            <input value={f.state.value} onChange={(e) => f.handleChange(e.target.value)} onBlur={f.handleBlur} />
            {f.state.meta.isTouched && !f.state.meta.isValid && (
              <p>{f.state.meta.errors.map(e => typeof e === 'string' ? e : e?.message).join(', ')}</p>
            )}
          </>
        )}
      </form.Field>

      <form.Field name="name">
        {(f) => (
          <>
            <input value={f.state.value} onChange={(e) => f.handleChange(e.target.value)} onBlur={f.handleBlur} />
            {f.state.meta.isTouched && !f.state.meta.isValid && (
              <p>{f.state.meta.errors.map(e => typeof e === 'string' ? e : e?.message).join(', ')}</p>
            )}
          </>
        )}
      </form.Field>

      <form.Subscribe selector={(s) => [s.canSubmit, s.isSubmitting] as const}>
        {([canSubmit, isSubmitting]) => (
          <button disabled={!canSubmit}>{isSubmitting ? '...' : 'Save'}</button>
        )}
      </form.Subscribe>
    </form>
  )
}
```

Key differences visible in the diff: the `useEffect` replacing `values`, the render-prop shape of `<form.Field>`, the lack of a centralized `errors` object, and the `form.Subscribe` for the submit button.

In a real project, the repeated per-field boilerplate is why `createFormHook` + reusable `TextField` components pay off quickly — see [COMPOSITION.md](COMPOSITION.md).

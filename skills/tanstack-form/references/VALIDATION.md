# Validation

Everything validation-related: the per-trigger lifecycle, form-level vs field-level Zod, async validation, cross-field dependencies, and listeners.

## The lifecycle

Unlike RHF's form-wide `mode: 'onChange' | 'onBlur' | 'onSubmit' | 'onTouched' | 'all'`, TanStack Form has a validator *per trigger*. Each slot runs on its own event. This is the core abstraction to internalize.

| Trigger slot | Fires when | Runs sync/async |
|---|---|---|
| `onMount` | field mounts | sync only |
| `onChange` | `field.handleChange(...)` is called | sync |
| `onChangeAsync` | same as above, async | async |
| `onBlur` | `field.handleBlur()` is called | sync |
| `onBlurAsync` | same as above, async | async |
| `onSubmit` | `form.handleSubmit()` is called | sync |
| `onSubmitAsync` | same as above, async | async |
| `onDynamic` / `onDynamicAsync` | after first submit attempt, re-runs on change (only when paired with `validationLogic: revalidateLogic()`) | both |
| `onServer` | written externally via `form.setFieldMeta` | n/a |

Every `*Async` slot accepts a sibling `*AsyncDebounceMs` option. A global `asyncDebounceMs` on `useForm` sets a default.

## Form-level vs field-level validators

Both forms exist. They compose. Understanding the precedence rule matters:

**Field-level wins for the same field + same trigger.** If a field has its own `validators.onChange` *and* the form has a `validators.onChange` that also produces an error for that field, only the field-level error shows up.

Form-level validators can address specific fields by returning a structured object:

```ts
validators: {
  onSubmitAsync: async ({ value }) => {
    const result = await api.validate(value)
    if (!result.ok) {
      return {
        fields: result.fieldErrors,
        form: 'Some fields have issues',
      }
    }
    return undefined
  },
}
```

The returned `fields` object is keyed by field path, so a form-level validator can set errors on `items[2].price` etc.

## Zod at the form level

Standard Schema means you just pass the schema:

```ts
const schema = z.object({
  email: z.string().email(),
  age: z.number().int().gte(13, 'Must be 13+'),
})

const form = useForm({
  defaultValues: { email: '', age: 0 },
  validators: { onChange: schema },
})
```

Errors land under the field whose `path` the Zod issue references. A `superRefine` that does `ctx.addIssue({ path: ['confirm'], ... })` attaches to the `confirm` field.

**Memoize the schema.** Validators are re-read on every render of the component that owns `useForm`. Declare Zod schemas at **module scope** when possible, or wrap with `useMemo` when dynamic. Failing to do this causes identity-based re-setup and can trigger issue #1625 (form-level Zod re-rendering every field on every keystroke).

**Re-render caveat.** Passing a Zod schema as form-level `onChange` is known to cause all referenced fields to re-render on every keystroke because the schema re-runs whole. If a profile shows this, two options:

1. Move the schema to `onBlur` or `onSubmit`.
2. Wrap the schema in a custom validator that returns the `{ fields: {...} }` shape and handles the memoization itself.

## Zod at the field level

Pass a Zod type directly:

```tsx
<form.Field
  name="email"
  validators={{ onChange: z.string().email('Invalid email') }}
>
  {(field) => <input {...bind(field)} />}
</form.Field>
```

Field-level Zod is better than form-level Zod when the validation is truly local (format check, length check) because:

- Only that field re-renders on its own change.
- The schema doesn't have to traverse the whole form.
- Errors never collide with form-level errors for that field.

Use form-level Zod for cross-field rules and for overall schema integrity.

## Error shapes (the one that bites)

`field.state.meta.errors` is an array whose element type depends on what the validator returned:

- A **Zod/Standard Schema validator** returns `StandardSchemaV1Issue` objects: `{ message: string, path?: ... }`.
- A **function validator returning a string** produces string elements.
- A **function validator returning `{ message: '...' }`** produces that object shape.

Mixing shapes within a single field (a sync `onChange` returning `'too short'` plus a Zod `onChangeAsync`) produces an array where `err.message` is undefined for some entries and valid for others. Pick one shape per field, or render defensively:

```tsx
{field.state.meta.errors.map((err, i) => {
  const msg = typeof err === 'string' ? err : err?.message ?? JSON.stringify(err)
  return <p key={i} className="err">{msg}</p>
})}
```

## The `errorMap`

`field.state.meta.errorMap` is `{ onChange, onBlur, onSubmit, onMount, onServer, onDynamic }`. Useful when you need to distinguish sources — e.g., show server-origin errors differently from client schema errors, or suppress sync errors while async validation is still running.

Setting `disableErrorFlat` on a `<form.Field>` preserves per-trigger separation in `errors` as well, instead of flattening the map into a single array.

## Async validation

The signature: `async ({ value, signal, fieldApi })`. The `signal` is an `AbortSignal` that fires when the user types again (or the field unmounts). Pass it through to `fetch` and in-flight requests get cancelled for free:

```tsx
<form.Field
  name="username"
  validators={{
    onChange: ({ value }) =>
      value.length < 3 ? 'Too short' : undefined,
    onChangeAsyncDebounceMs: 500,
    onChangeAsync: async ({ value, signal }) => {
      const res = await fetch(`/api/users/check?u=${value}`, { signal })
      if (!res.ok) return 'Could not verify'
      const { taken } = await res.json()
      return taken ? 'Username is taken' : undefined
    },
  }}
>
  {(field) => (
    <div>
      <input
        value={field.state.value}
        onChange={(e) => field.handleChange(e.target.value)}
        onBlur={field.handleBlur}
        aria-invalid={!field.state.meta.isValid}
      />
      {field.state.meta.isValidating && <span>Checking...</span>}
    </div>
  )}
</form.Field>
```

Important behaviors:

- **Sync runs before async.** If the sync `onChange` returns an error, the async does not run. This lets you skip API calls on obviously-invalid input.
- **`canSubmit` goes false while any async validator runs.** Disable the submit button through `form.Subscribe`.
- **`field.state.meta.isValidating`** is true while the field's own async is in flight. `form.state.isValidating` covers the whole form.

### The silent async footgun

`onChange` accepts an `async` function without a TS error (the return type includes `unknown`), but TanStack Form **does not await** the Promise. Errors land in the store momentarily and vanish before the next render. The field's `errors` array stays empty in the render prop.

**Always use the `*Async` suffix** when the validator returns a Promise. If you catch yourself typing `async` into a sync slot, stop and rename.

A defensive helper pattern: wrap `useAppForm` (or `useForm`) in a custom hook that `Omit`s the sync keys from the config type, forcing developers to use the `*Async` slots. This adds TS-time enforcement on top of a docs-only rule.

## Cross-field validation — three patterns, three situations

### Pattern A: field-level validator reads another field (`onChangeListenTo`)

For local UX like "confirm password matches password":

```tsx
<form.Field name="password">
  {(f) => <input {...bind(f)} type="password" />}
</form.Field>

<form.Field
  name="confirm_password"
  validators={{
    onChangeListenTo: ['password'],
    onChange: ({ value, fieldApi }) => {
      if (value !== fieldApi.form.getFieldValue('password')) {
        return 'Passwords do not match'
      }
      return undefined
    },
  }}
>
  {(f) => <input {...bind(f)} type="password" />}
</form.Field>
```

`onChangeListenTo: ['password']` is the critical piece. Without it, editing `password` leaves the `confirm_password` error stale. `onBlurListenTo` exists too.

**Known bug (discussion #964):** `onChangeListenTo` can silently fail to fire when the form also has a form-level validator. Symptom: the cross-field error fails to clear after the other field changes. Workaround: call `form.validateField('confirm_password', 'change')` from a listener on the first field.

### Pattern B: form-level Zod refine

For data-integrity rules where one schema is cleaner than scattered field validators:

```ts
const schema = z.object({
  startDay: z.string(),
  endDay: z.string(),
}).superRefine((v, ctx) => {
  if (v.endDay && v.startDay && new Date(v.endDay) <= new Date(v.startDay)) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['endDay'],
      message: 'End must be after start',
    })
  }
})

const form = useForm({
  defaultValues: { startDay: '', endDay: '' },
  validators: { onChange: schema },
})
```

Because the schema runs form-wide on every change, both fields are re-checked whenever either changes. Watch the re-render caveat above.

### Pattern C: conditional required (discriminated union)

For "shipping address is required only when checkbox is checked":

```ts
const schema = z.discriminatedUnion('needsShipping', [
  z.object({ needsShipping: z.literal(false) }),
  z.object({
    needsShipping: z.literal(true),
    shipping: z.object({
      street: z.string().min(1),
      zip: z.string().min(1),
    }),
  }),
])
```

This is cleaner than `superRefine` for conditional-required because the Zod types track the actual shape. Combine with conditional rendering of the `<form.Field>` and a listener that resets `shipping` when `needsShipping` toggles off (see [ARRAYS-AND-NESTED.md](ARRAYS-AND-NESTED.md#conditional-fields)).

## Choosing between patterns

Local UX rule between two fields → Pattern A (`onChangeListenTo`). Precise, only the affected field re-renders.

Data-integrity rule across many fields → Pattern B (form-level Zod with `superRefine`). One source of truth for validity.

Conditional shape → Pattern C (discriminated union). Lets the Zod inference track the actual branches rather than defeating it with `.optional()` everywhere.

You can mix all three in one form. Remember the precedence rule: field-level errors win over form-level for the same field + same trigger.

## Listeners ≠ validators

`listeners` is for *side effects*. Use it when an action on one field should mutate another field's value, log, autosave, etc.

```tsx
<form.Field
  name="country"
  listeners={{
    onChange: ({ value }) => {
      form.setFieldValue('province', '')
    },
    onChangeDebounceMs: 300,
  }}
>
  {(f) => <select {...bind(f)}>...</select>}
</form.Field>
```

Listeners are available at both form and field level. Form-level listeners receive `fieldApi` so you know which field fired.

**Warning:** `form.setFieldValue` inside a listener does not trigger validators. If a cascaded value needs validation, follow with `form.validateField('province', 'change')`.

## `revalidateLogic()` — the RHF "validate on submit, then on change" preset

RHF's common config is `mode: 'onSubmit', reValidateMode: 'onChange'` — validate once on submit, then keep validating on change after the first attempt. In TanStack Form:

```ts
import { revalidateLogic } from '@tanstack/react-form'

const form = useForm({
  defaultValues: { email: '' },
  validationLogic: revalidateLogic(),
  validators: { onDynamic: schema },
})
```

The `onDynamic` slot fires at submit time first, then switches to change-time after the first submission attempt. Use this when you don't want red ink until the user has actually tried to submit once.

## RHF equivalents cheat sheet

| RHF | TanStack Form |
|---|---|
| `mode: 'onChange'` | `validators.onChange: schema` |
| `mode: 'onBlur'` | `validators.onBlur: schema` |
| `mode: 'onSubmit'` | `validators.onSubmit: schema` |
| `mode: 'onSubmit'` + `reValidateMode: 'onChange'` | `validationLogic: revalidateLogic()` + `validators.onDynamic` |
| `mode: 'all'` | both `onChange` and `onBlur` validators |
| `trigger('field')` | `form.validateField('field', 'change')` |
| `trigger()` | `form.validateAllFields('change')` |
| `watch('field')` + `useEffect` + `trigger` | `onChangeListenTo: ['field']` on the dependent field's validator |
| `resolver: zodResolver(schema)` | `validators.onChange: schema` (or whichever trigger you want) |

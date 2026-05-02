# Rendering, subscriptions, and custom inputs

How to read form state without causing unwanted re-renders, how to wire 3rd-party components, and what `form.state` exposes.

## Three ways to access state

Internalizing this table prevents 80% of TanStack Form confusion:

| API | Where to use | Triggers re-render? |
|---|---|---|
| `form.state.xxx` or `form.getFieldValue('x')` | inside event handlers, listeners, validators | no — snapshot only |
| `useStore(form.store, (s) => s.xxx)` | inside a component body for derived values / conditions | yes, scoped to selector output |
| `<form.Subscribe selector={...} children={...}>` | inside JSX where you want scoped re-renders without moving logic out | yes, only the `children` re-renders |

The rule of thumb: if a component should re-render when something changes, you need either `useStore` or `form.Subscribe`. Reading `form.state.xxx` directly gives you a snapshot that will be stale on the next change.

```tsx
const email = useStore(form.store, (s) => s.values.email)

<form.Subscribe selector={(s) => [s.canSubmit, s.isSubmitting] as const}>
  {([canSubmit, isSubmitting]) => (
    <button disabled={!canSubmit}>
      {isSubmitting ? '...' : 'Save'}
    </button>
  )}
</form.Subscribe>
```

## Always pass a selector

The docs are explicit: `useStore(form.store)` without a selector re-renders on **every** form mutation. The selector is how you narrow.

## The reference-equality selector bug

Open issue #1148: `useStore` with a selector that returns an object or array **by reference** can cause infinite update loops or lose input focus because the equality check fails on every render.

```ts
const values = useStore(form.store, (s) => s.values)
```

This returns a new reference each render → infinite loop. Workarounds:

1. Return a primitive: `useStore(form.store, (s) => s.values.items.length)`.
2. Return a `const` tuple of primitives: `useStore(form.store, (s) => [s.canSubmit, s.isSubmitting] as const)`.
3. Use `form.Subscribe` instead. Its internal equality check is more tolerant.

If a selector must return an object, provide a custom equality function (`useStore(form.store, selector, shallowEqual)`) or memoize.

## `form.Subscribe` vs `useStore`

Both scope re-renders to a slice. Pick based on where the consuming code lives:

- **JSX** that conditionally renders or accepts the value as a prop → `form.Subscribe`. Keeps the subscription inline.
- **Logic** in the component body that derives a value used in multiple places, or passes to a non-form hook → `useStore`.

`form.Subscribe`'s `children` render-prop pattern also means the subscribing boundary is localized — nothing outside the `<form.Subscribe>` tag re-renders on that slice.

## Why the parent component re-renders matter

RHF's headline is "zero re-renders of the parent because inputs are uncontrolled." TanStack Form has the same property *if you don't read `form.state.values` in the parent*. The moment you write `const { email } = form.state.values` at the top of your form component, the whole subtree re-renders on every keystroke.

Rule: **never read `form.state.values` (or `form.state.fieldMeta`) in the top-level form component body.** Push those reads into `form.Subscribe` or `useStore` in whichever child component actually needs them.

## Form-wide state

Everything on `form.state`, readable via selectors:

**Values and errors**
- `values` — full typed form data
- `errors` — form-level errors (array)
- `errorMap` — form-level errors by trigger
- `fieldMeta` — map of per-field meta objects

**Submit state**
- `canSubmit` — composite gate: no async running, no blocking errors
- `isSubmitting` — the `onSubmit` callback is in progress
- `isSubmitted` — submit has been attempted
- `isSubmitSuccessful` — last submit completed without throwing
- `submissionAttempts` — counter

**Validation state**
- `isValidating` / `isFieldsValidating` / `isFormValidating` — async in flight
- `isValid` / `isFieldsValid` / `isFormValid` — overall validity flags

**Dirty/touched state**
- `isDirty` / `isPristine` — persistent dirtiness (see gotcha below)
- `isTouched` — any field changed or blurred
- `isBlurred` — any field blurred
- `isDefaultValue` — current values deep-equal defaults

## `isDirty` vs `isDefaultValue`

`isDirty` is persistent by design — once a field is changed, it stays dirty forever, even if the user reverts to the default. Use `!isDefaultValue` for RHF-style "revert to clean":

```tsx
<form.Subscribe selector={(s) => !s.isDefaultValue}>
  {(changedFromDefaults) => changedFromDefaults && <UnsavedChangesIndicator />}
</form.Subscribe>
```

This applies at both form level (`form.state.isDirty` vs `form.state.isDefaultValue`) and field level (`field.state.meta.isDirty` vs `field.state.meta.isDefaultValue`).

## Custom components — the universal pattern

Because every input is controlled, there is no `<Controller>` distinction. Every component wires up the same way:

1. Read the current value from `field.state.value`.
2. Call `field.handleChange(next)` on change.
3. Call `field.handleBlur()` on blur.

A tiny `bind` helper keeps render props readable:

```ts
function bind<T>(field: {
  name: string
  state: { value: T }
  handleChange: (v: T) => void
  handleBlur: () => void
}) {
  return {
    name: field.name,
    value: field.state.value,
    onBlur: field.handleBlur,
    onChange: (v: T) => field.handleChange(v),
  }
}
```

### Native input

```tsx
<form.Field name="email">
  {(f) => (
    <input
      name={f.name}
      value={f.state.value}
      onBlur={f.handleBlur}
      onChange={(e) => f.handleChange(e.target.value)}
    />
  )}
</form.Field>
```

### shadcn/ui Input

shadcn's `<Input>` takes native props, so:

```tsx
<form.Field name="email">
  {(f) => (
    <Input
      name={f.name}
      value={f.state.value}
      onBlur={f.handleBlur}
      onChange={(e) => f.handleChange(e.target.value)}
      aria-invalid={!f.state.meta.isValid}
    />
  )}
</form.Field>
```

shadcn also ships a first-party TanStack Form integration at `ui.shadcn.com/docs/forms/tanstack-form` with `<Field>`, `<FieldError>`, and `data-invalid` wiring — use it if you're already in a shadcn codebase.

### Date picker (object value, not string)

```tsx
<form.Field name="dueDate">
  {(f) => (
    <DatePicker
      value={f.state.value}
      onChange={(d) => f.handleChange(d)}
      onBlur={f.handleBlur}
    />
  )}
</form.Field>
```

The `defaultValues` entry for `dueDate` types the field as `Date` (or `Date | null`), and `f.handleChange` expects that type.

### react-select (option object, stored as string)

```tsx
<form.Field name="country">
  {(f) => (
    <Select
      options={countries}
      value={countries.find(c => c.value === f.state.value) ?? null}
      onChange={(opt) => f.handleChange(opt?.value ?? '')}
      onBlur={f.handleBlur}
    />
  )}
</form.Field>
```

The pattern generalizes: transform at the component boundary. The field stores the string ID; the select component is handed an option object. Both sides see what they expect.

## Error UI

### Shape-tolerant render

```tsx
{field.state.meta.errors.map((err, i) => {
  const msg = typeof err === 'string' ? err : err?.message ?? JSON.stringify(err)
  return <p key={i} className="err">{msg}</p>
})}
```

### Show after touch (RHF default behavior)

```tsx
{field.state.meta.isTouched && !field.state.meta.isValid && (
  <p className="err">{formatErrors(field.state.meta.errors)}</p>
)}
```

### Show after blur only

Use `isBlurred` (v1 addition) instead of `isTouched`. `isTouched` is true on *either* change or blur, so it shows errors too eagerly for blur-only UX.

```tsx
{field.state.meta.isBlurred && !field.state.meta.isValid && (
  <p className="err">{formatErrors(field.state.meta.errors)}</p>
)}
```

### Per-trigger errors

When you need to distinguish server-origin errors from client schema errors:

```tsx
{field.state.meta.errorMap.onServer && (
  <p className="err err--server">{field.state.meta.errorMap.onServer}</p>
)}
{field.state.meta.errorMap.onChange && (
  <p className="err err--client">{field.state.meta.errorMap.onChange}</p>
)}
```

### Form-level error summary

```tsx
<form.Subscribe selector={(s) => s.errors}>
  {(errors) =>
    errors.length > 0 && (
      <div role="alert">
        {errors.map((e, i) => (
          <div key={i}>{typeof e === 'string' ? e : e.message}</div>
        ))}
      </div>
    )
  }
</form.Subscribe>
```

## Performance checklist

If a form feels sluggish:

1. **Check for inline Zod schemas.** `validators: { onChange: z.object({...}) }` inside the component body creates a new schema identity each render. Move to module scope or `useMemo`.
2. **Check for value reads in the parent.** If the top-level form component destructures `form.state.values`, the entire tree re-renders per keystroke. Push reads into `form.Subscribe` / `useStore` where needed.
3. **Check for object-returning selectors.** `useStore(form.store, s => s.values)` is the issue #1148 footgun. Return primitives or tuples.
4. **Check TanStack Form version.** Array subscription re-render bug was fixed in 1.27.4. Pin `>=1.27.4`.
5. **Profile.** React DevTools Profiler tells you which component is re-rendering and why. TanStack Form's field boundaries should keep re-renders scoped to one `<form.Field>` at a time.

## Accessibility

Two things to wire up on every input:

```tsx
<input
  name={field.name}
  value={field.state.value}
  onBlur={field.handleBlur}
  onChange={(e) => field.handleChange(e.target.value)}
  aria-invalid={!field.state.meta.isValid}
  aria-describedby={`${field.name}-err`}
/>
<p id={`${field.name}-err`}>{formatErrors(field.state.meta.errors)}</p>
```

For the submit button, prefer `aria-disabled` + a no-op click handler over `disabled` — a `disabled` button is skipped by screen reader navigation.

# Gotchas: the complete catalog

Every known v1 footgun and open issue in one place. Each entry states the symptom, the cause, and the fix. Version pins are called out where relevant.

## Silent failures (these cause invisible bugs)

### Async function in a sync validator slot is not awaited

**Symptom.** A field has an `onChange` validator that calls `fetch`, but `field.state.meta.errors` is always empty — the error message never displays.

**Cause.** `onChange`, `onBlur`, `onSubmit`, `onDynamic` are sync slots. Their TypeScript return type includes `unknown`, so passing an `async` function does not produce an error at compile time. TanStack Form does not `await` the Promise — errors land in the store briefly and disappear before the next render.

**Fix.** Use the `*Async` suffix: `onChangeAsync`, `onBlurAsync`, `onSubmitAsync`, `onDynamicAsync`. If the validator returns a Promise, its slot name must end in `Async`.

**Stronger defense.** Wrap `useAppForm` in a helper that `Omit`s the sync keys from the config type, making the TS error explicit.

### `form.state.xxx` read inline does not subscribe

**Symptom.** A component renders the wrong value, or fails to update when a field changes.

**Cause.** Reading `form.state.values.email` (or any other slice) in a component body returns a snapshot. It does not subscribe the component to changes.

**Fix.** Use `useStore(form.store, (s) => s.values.email)` for component body logic, or `<form.Subscribe selector={(s) => s.values.email}>` for scoped JSX re-render.

### `form.setFieldValue` does not trigger validators

**Symptom.** Cascaded updates (e.g., resetting `province` when `country` changes) don't re-validate — a stale error persists.

**Cause.** Since v1.14.2, `setFieldValue` only writes to the store. It does not trigger the field's validators.

**Fix.** Either call `field.handleChange(value)` (inside a render prop where you have the field handle), or follow `setFieldValue` with `form.validateField('path', 'change')`.

### `onChangeListenTo` silently not firing with form-level validation

**Symptom.** A cross-field error ("passwords do not match") fails to clear when the other field changes. Symptom is intermittent depending on combinations.

**Cause.** Open discussion #964: `onChangeListenTo` can fail to fire when a form-level validator is also active. The interaction between form-level and field-level runs is the root cause.

**Fix.** Add a listener on the first field that explicitly calls `form.validateField('confirm_password', 'change')`:

```tsx
<form.Field
  name="password"
  listeners={{
    onChange: () => form.validateField('confirm_password', 'change'),
  }}
>
  ...
</form.Field>
```

### Mixed error shapes break rendering

**Symptom.** Some errors display correctly, others render as `undefined` or as JSON strings.

**Cause.** `field.state.meta.errors` is a union of whatever each validator returned. A sync `onChange` returning a string + an async `onChangeAsync` returning `{ message }` produces `(string | { message: string })[]`. Calling `.message` on the string entries returns undefined.

**Fix.** Either standardize on one shape per field, or render defensively:

```tsx
{field.state.meta.errors.map((err, i) => {
  const msg = typeof err === 'string' ? err : err?.message ?? JSON.stringify(err)
  return <p key={i} className="err">{msg}</p>
})}
```

## Behavioral differences from RHF

### `isDirty` is persistent

**Symptom.** Typing and then deleting a character leaves `isDirty === true`.

**Cause.** Intentional design choice, matching Angular Forms and FormKit conventions.

**Fix.** Use `!field.state.meta.isDefaultValue` (field-level) or `!form.state.isDefaultValue` (form-level) for RHF-style "non-persistent dirty."

### Conditional fields keep their values on unmount

**Symptom.** Toggling a checkbox to hide a section, then submitting, sends stale values for the hidden fields.

**Cause.** No `shouldUnregister` equivalent in v1. Values persist in `form.state.values` regardless of whether the `<form.Field>` is mounted.

**Fix.** Three options:
1. Use `z.discriminatedUnion` so validation and the submit handler only see the active branch.
2. Clear values in a listener on the toggle field.
3. Filter in `onSubmit`.

### `defaultValues` is not reactive

**Symptom.** Loading a record into a form, then changing which record is loaded, does not update the form.

**Cause.** `defaultValues` is consumed once on mount. There is no equivalent to RHF's `useForm({ values })`.

**Fix.** `useEffect(() => { if (record) form.reset(record) }, [record])`.

### Zod `.transform()` output is not preserved

**Symptom.** A schema with `z.coerce.number()` or `.transform(...)` is applied successfully, but `onSubmit` receives the untransformed string value.

**Cause.** Standard Schema's integration passes the *input* to `onSubmit`, not the parsed output. Docs acknowledge this explicitly.

**Fix.** Re-parse inside the handler:

```ts
onSubmit: async ({ value }) => {
  const parsed = schema.parse(value)
  await api.save(parsed)
}
```

RHF's `zodResolver` does preserve transforms. Migrated RHF forms that relied on this silently break.

## Performance pitfalls

### Inline Zod schema re-creates every render

**Symptom.** Form feels sluggish. Profiler shows unusually frequent re-renders on the form root.

**Cause.** `validators: { onChange: z.object({...}) }` written inside the component body creates a new schema identity on every render of the owning component.

**Fix.** Declare the schema at module scope, or `useMemo` it if it must be dynamic.

### Form-level Zod re-renders every field on every keystroke

**Symptom.** All field components in the form re-render on every keystroke in any one field.

**Cause.** Open issue #1625: a form-level Zod `onChange` validator re-runs the whole schema for every change, and the `form.state` mutation that results triggers subscribed children broadly.

**Fix.** Three options:
1. Move the form-level Zod to `onBlur` or `onSubmit`.
2. Use field-level Zod instead of form-level for things that don't need cross-field access.
3. Replace the form-level Zod with a custom validator that returns `{ fields: {...} }` with only changed fields.

### Object-returning selector causes infinite re-render loop

**Symptom.** Input loses focus on every keystroke, or browser tab hangs.

**Cause.** Open issue #1148: `useStore(form.store, (s) => s.values)` returns a new object reference on every render, failing equality check, causing subscribe-unsubscribe-subscribe loops.

**Fix.** Return a primitive or a `const` tuple:

```ts
// bad
const values = useStore(form.store, (s) => s.values)

// good
const email = useStore(form.store, (s) => s.values.email)
const [canSubmit, isSubmitting] = useStore(
  form.store,
  (s) => [s.canSubmit, s.isSubmitting] as const,
)
```

Or switch to `form.Subscribe`, which has a more tolerant equality check.

### Array field mount causes extra re-render

**Symptom.** Adding an item to an array field causes one extra render cycle.

**Cause.** Bug fixed in **v1.27.4**.

**Fix.** Pin `@tanstack/react-form` to `>=1.27.4` — preferably the latest 1.29.x. If your lockfile is older, update.

## Type-level pitfalls

### Deep/complex form types become `unknown`

**Symptom.** `field.state.value` types as `unknown` despite `defaultValues` being well-typed. IDE autocomplete fails on the value.

**Cause.** TypeScript inference gives up on very large or recursive form types. Documented in the "Debugging" guide.

**Fix.** Split the form with `withForm` — the sub-component gets a narrower shape to infer on. Or cast at the use site (`value as string`).

### Union-typed fields aren't expressible via `defaultValues`

**Symptom.** A field that should be `string | number` is typed as whichever the default is.

**Cause.** `defaultValues` provides a single concrete default, so inference picks one type.

**Fix.** Use `satisfies` with an explicit type cast:

```ts
const defaults = {
  amount: '' as string | number,
} satisfies FormShape
```

Expect to cast at `handleChange` sites.

### `withFieldGroup` validators type as `unknown`

**Symptom.** Validators declared inside a `withFieldGroup` can't be typed.

**Cause.** Current TS limitation — there's no way to propagate exact types through the group boundary.

**Fix.** Apply validators at the parent form level, or do runtime validation inside group validators with manual casts.

### `defaultValues` and Zod schema can silently drift

**Symptom.** The form accepts values the schema would reject, or defaults don't satisfy the schema.

**Cause.** Nothing enforces that `defaultValues` matches `z.input<typeof schema>`.

**Fix.** Use `satisfies`:

```ts
const defaults = {
  email: '',
  age: 0,
} satisfies z.input<typeof schema>
```

Or derive from the schema: `const defaults = schema.parse(rawDefaults)` (only works if every field has a Zod default).

## UX / correctness

### `isFieldsValid` is true for unvalidated fields

**Symptom.** A newly-mounted conditional field is "valid" before the user has touched it, gating the submit button incorrectly.

**Cause.** Open issue #1149: `isFieldsValid` does not differentiate "known-valid" from "not-yet-validated."

**Fix.** Trigger `form.validateAllFields('mount')` in an effect after the conditional field mounts.

### `key={i}` on array items breaks on reorder

**Symptom.** Dragging an item from position 3 to position 0 shows the wrong form state in position 0.

**Cause.** React uses the key to preserve component identity. Index keys collide after reorder.

**Fix.** Store a stable ID on each item and key on that: `{ id: crypto.randomUUID(), ... }`. This mirrors RHF's `fields[i].id`.

### Forgetting `e.preventDefault()` in the form's onSubmit

**Symptom.** The browser submits the form natively, causing a page reload.

**Cause.** `form.handleSubmit()` does not call `preventDefault` for you. This is deliberate — it lets you use `form.handleSubmit()` outside of a form event.

**Fix.** Always:

```tsx
<form onSubmit={(e) => { e.preventDefault(); form.handleSubmit() }}>
```

### Legacy pre-v1 patterns in tutorials

**Symptom.** Code examples from tutorials don't compile or behave unexpectedly.

**Cause.** Pre-v1 APIs like `createFormFactory`, `validatorAdapter: zodValidator`, `form.Provider`, `@tanstack/zod-form-adapter` are deprecated or removed.

**Fix.** Ignore any tutorial showing these. The current API is `useForm` / `useAppForm`, `<form.Field>`, Standard Schema via direct Zod passing, and `createFormHook` for composition.

## Version-pin summary

| Version | What it fixes |
|---|---|
| v1.0.0 | First stable release (May 2025). Standard Schema support. `@tanstack/zod-form-adapter` deprecated. |
| v1.14.2 | `form.setFieldValue` changed to skip validators. Behavior change — test cascaded updates. |
| v1.27.4 | Fixed extra re-render on array field mount. |
| v1.29.x | Current stable at time of writing (April 2026). Pin to this or later. |

Patch versions within v1 can still introduce type-layer changes. Patch-pin (`~1.29.0`) rather than minor-pin (`^1.29.0`) if you're sensitive to type errors appearing on `pnpm up`.

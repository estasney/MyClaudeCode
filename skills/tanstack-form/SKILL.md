---
name: tanstack-form
description: Guide for building React forms with TanStack Form v1 and Zod validation, framed for developers coming from react-hook-form. Use whenever the codebase imports from @tanstack/react-form
---

# TanStack Form (React + Zod)

This skill is written for someone fluent in react-hook-form + Zod who is now working in a codebase that uses **@tanstack/react-form v1.x**. The goal is to map problems you already know how to solve in RHF onto TanStack Form idioms, and to flag the footguns that silently produce wrong behavior.

## Version anchor

The skill assumes **@tanstack/react-form v1.0 or later** (v1 shipped May 2025; latest at time of writing is ~v1.29). Pre-v1 patterns you will see in old tutorials — `createFormFactory`, `validatorAdapter: zodValidator`, `form.Provider`, `@tanstack/zod-form-adapter` — are dead. If you see them in a tutorial, the article is stale.

## The mental model shift

The five concrete differences that trip up RHF developers:

**Controlled by default.** There is no `register`, no uncontrolled path. `field.state.value` is the source of truth; you wire it through `value={}` and `onChange={v => field.handleChange(v)}`. Because every input is already controlled, the RHF `register` / `<Controller>` split disappears — custom components and 3rd-party widgets work the same way as a native `<input>`.

**Render-prop primitives, not one hook.** `useForm` returns a `form` object. `<form.Field name="..." children={(field) => ...}>` mounts a field. `<form.Subscribe selector={...} children={...}>` subscribes the JSX below it to a slice of form state. There is no top-level `<FormProvider>` requirement — the `form` object is just passed around.

**Store-based, opt-in reactivity.** Form state lives in a `@tanstack/store`. Reading `form.state.values.email` inline in a component body returns a snapshot but **does not subscribe** — the component will not re-render when `email` changes. To subscribe, use `form.Subscribe` (for JSX) or `useStore(form.store, selector)` (for logic). This is the #1 source of "why isn't my UI updating?" confusion.

**Per-validator timing.** RHF has a form-wide `mode: 'onChange' | 'onBlur' | 'onSubmit' | ...`. TanStack Form has a validator *per* trigger: `validators: { onChange: schema, onBlur: otherSchema, onChangeAsync: asyncFn, onSubmitAsync: ... }`. Each slot fires on its own event. This is more expressive and more to learn.

**Zod plugs in directly.** TanStack Form implements Standard Schema, so Zod schemas (and Valibot, ArkType, Effect/Schema) go straight into `validators.onChange: mySchema` with no adapter. The old `@tanstack/zod-form-adapter` is deprecated.

## Minimal working example

The baseline template every form in this project should start from:

```tsx
import { useForm } from '@tanstack/react-form'
import { z } from 'zod'

const schema = z.object({
  email: z.string().email('Invalid email'),
  password: z.string().min(8, 'At least 8 chars'),
})

export function LoginForm() {
  const form = useForm({
    defaultValues: { email: '', password: '' },
    validators: { onChange: schema },
    onSubmit: async ({ value }) => {
      await login(value)
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        form.handleSubmit()
      }}
    >
      <form.Field name="email">
        {(field) => (
          <>
            <input
              name={field.name}
              value={field.state.value}
              onBlur={field.handleBlur}
              onChange={(e) => field.handleChange(e.target.value)}
            />
            {field.state.meta.isTouched && !field.state.meta.isValid && (
              <p>{field.state.meta.errors.map(e => typeof e === 'string' ? e : e?.message).join(', ')}</p>
            )}
          </>
        )}
      </form.Field>

      <form.Field name="password">
        {(field) => (
          <input
            type="password"
            value={field.state.value}
            onBlur={field.handleBlur}
            onChange={(e) => field.handleChange(e.target.value)}
          />
        )}
      </form.Field>

      <form.Subscribe selector={(s) => [s.canSubmit, s.isSubmitting] as const}>
        {([canSubmit, isSubmitting]) => (
          <button type="submit" disabled={!canSubmit}>
            {isSubmitting ? '...' : 'Sign in'}
          </button>
        )}
      </form.Subscribe>
    </form>
  )
}
```

Four things to notice:

1. `defaultValues` is the **type source** for the entire form. Every field must appear in it, or you get React's "uncontrolled → controlled" warning.
2. `validators.onChange: schema` — the Zod schema goes straight in. No `zodResolver`, no adapter.
3. `form.handleSubmit()` does not call `preventDefault` for you. Do it in your handler.
4. The submit button lives inside `form.Subscribe` because `canSubmit` doesn't subscribe when read directly.

## Critical gotchas (read before writing any form)

These produce silent bugs. Surface them here so they are seen before they bite in production.

**1. Async function in a sync validator slot silently fails.** `onChange`, `onBlur`, `onSubmit`, `onDynamic` are sync slots. Putting an `async ({ value }) => ...` into them does not produce a TS error (the declared return type includes `unknown`), but TanStack Form does not `await` the Promise — errors briefly land in the store and vanish before the next render. Always use the `*Async` suffix (`onChangeAsync`, `onBlurAsync`, `onSubmitAsync`) when the validator returns a Promise.

**2. Reading `form.state.xxx` inline does not subscribe.** Snapshots only. If a component needs to re-render when `xxx` changes, use `useStore(form.store, s => s.xxx)` or `<form.Subscribe selector={s => s.xxx}>`.

**3. `isDirty` is persistent by design.** Typing "a" and then deleting it leaves `field.state.meta.isDirty === true` forever. Use `!field.state.meta.isDefaultValue` if you want RHF-style "reverts to clean."

**4. Zod `.transform()` output does not reach `onSubmit`.** The value passed to `onSubmit` is the *input* to the schema, not the transformed output. If you rely on `z.coerce.number()` or `.transform(...)`, re-parse inside the handler: `const parsed = schema.parse(value)`.

**5. `form.setFieldValue` does not trigger validators.** Since v1.14.2. Use `field.handleChange(next)` for user-like writes, or follow `setFieldValue` with `form.validateField('path', 'change')`.

**6. Hidden fields keep their values.** There is no `shouldUnregister` equivalent. When a conditional field unmounts, its value stays in `form.state.values`. Form-level Zod will still validate it unless the schema is gated on the toggle. Clear manually in a listener, or use `z.discriminatedUnion`.

**7. Mixed error shapes break the UI.** A field whose `onChange` validator returns a string and whose `onChangeAsync` returns a `{ message }` object will produce a mixed `errors` array — `err.message` is undefined for half the entries. Pick one shape per field, or render defensively: `typeof err === 'string' ? err : err?.message`.

**8. Passing a Zod schema as form-level `onChange` can re-render every referenced field on every keystroke** (open issue #1625). If profiler shows this, move the schema to `onBlur`/`onSubmit` or swap to a custom validator that returns `{ fields: { ... } }`.

**9. `onChangeListenTo` can silently not fire when combined with a form-level validator** (open discussion #964). If a cross-field error fails to clear after the other field changes, this is likely the cause — call `form.validateField('name', 'change')` explicitly as a workaround.

The full footgun catalog is in [references/GOTCHAS.md](references/GOTCHAS.md).

## Decision tree

**Wiring up validation — timing, Zod schemas, async, cross-field rules?**
See [references/VALIDATION.md](references/VALIDATION.md). Covers the per-trigger lifecycle (`onChange` vs `onBlur` vs `onDynamic`), form-level vs field-level Zod, `z.refine` / `z.superRefine` for cross-field rules, `onChangeListenTo`, async validation with `AbortSignal` and debouncing, and the listener API.

**Dynamic arrays of fields, deeply nested paths, or conditional fields?**
See [references/ARRAYS-AND-NESTED.md](references/ARRAYS-AND-NESTED.md). Covers `<form.Field mode="array">`, the array API (`pushValue`, `removeValue`, etc.), Zod array validation, deep paths like `items[0].tags[2].name`, and patterns for conditional fields where values persist on unmount.

**Re-render optimization, subscriptions, custom inputs, form-wide state?**
See [references/RENDERING.md](references/RENDERING.md). Covers `form.Subscribe` vs `useStore` vs snapshot reads, selector pitfalls (including the reference-equality bug in issue #1148), wiring custom components (shadcn, react-select, date pickers), and the full `form.state` surface.

**Reusable field components, large forms split into sections?**
See [references/COMPOSITION.md](references/COMPOSITION.md). Covers `createFormHook`, `useAppForm`, `form.AppField`, `form.AppForm`, `withForm` for sub-form components, and `withFieldGroup` for groups reusable across different form shapes.

**Submit flow, reset, server errors, loading existing records for edit?**
See [references/SUBMISSION.md](references/SUBMISSION.md). Covers `form.handleSubmit`, the `onSubmit` option signature, `onSubmitMeta` for per-click metadata, `form.reset`, the loaded-record `useEffect(() => form.reset(record), [record])` pattern, and setting server-origin errors via `form.setFieldMeta`.

**Translating a specific RHF pattern or API call?**
See [references/MIGRATION.md](references/MIGRATION.md). A comprehensive mapping table from RHF APIs to TanStack Form equivalents, with the RHF behaviors that have no direct TanStack counterpart (`shouldUnregister`, `keepDirty`, reactive `values` prop, `useWatch`).

**Debugging a subtle bug or performance issue?**
See [references/GOTCHAS.md](references/GOTCHAS.md). The complete catalog of known v1 footguns and open issues, with workarounds and version pins where relevant.

## When NOT to use TanStack Form

This project has already committed to TanStack Form, so the choice is made. This section exists only so you recognize when a question is actually "can I have RHF for this edge case?" and can redirect the conversation. The honest trade-offs:

- TanStack Form's bundle is ~20 KB min+gz vs RHF's ~8 KB. On a landing-page form this matters; on an app form it does not.
- TanStack Form has ~1–1.5M weekly downloads vs RHF's ~25M. Stack Overflow / tutorial density is much lower.
- Deep generic inference can fail on recursive or large discriminated-union form shapes — see [references/COMPOSITION.md](references/COMPOSITION.md) for `withForm` as the escape hatch.
- Zod `.transform()` output is not preserved into `onSubmit`; re-parse if you need it.

What TanStack Form does better than RHF, and why it's plausibly the right choice for this project:

- Async validation with `AbortSignal` cancellation and `onChangeAsyncDebounceMs` is built in. RHF requires DIY wiring.
- Per-trigger validators give you fine-grained UX (cheap sync gate, expensive async only on blur, different rules per event) without a global `mode`.
- The store/selector model scales to large dynamic forms (deep arrays, conditional sections) without manual memoization gymnastics.
- Standard Schema support means Zod today, Valibot or ArkType tomorrow, with no code changes beyond the schema itself.

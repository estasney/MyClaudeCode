# Composition: reusable fields and large forms

TanStack Form's official answer to "this is verbose" is `createFormHook` + `withForm` + `withFieldGroup`. Use these when the form grows past ~5 fields or when the same field types (text, select, checkbox) recur across forms.

The docs explicitly concede: *"A common criticism of TanStack Form is that it is verbose out-of-the-box."* The composition primitives are the answer, and adopting them early saves a lot of render-prop boilerplate later.

## `createFormHook` — the central setup

Create a single `form.ts` in the project that wires up your pre-bound components:

```tsx
// hooks/form.ts
import {
  createFormHook,
  createFormHookContexts,
} from '@tanstack/react-form'
import { TextField, CheckboxField, SelectField } from '@/components/fields'
import { SubmitButton } from '@/components/submit-button'

export const {
  fieldContext,
  useFieldContext,
  formContext,
  useFormContext,
} = createFormHookContexts()

export const { useAppForm, withForm, withFieldGroup } = createFormHook({
  fieldContext,
  formContext,
  fieldComponents: { TextField, CheckboxField, SelectField },
  formComponents: { SubmitButton },
})
```

From then on, use `useAppForm` instead of `useForm` and `form.AppField` instead of `form.Field`. The pre-bound `fieldComponents` are accessible as `f.TextField`, `f.CheckboxField`, etc. inside the `AppField` render prop.

## A reusable field component

Use `useFieldContext<T>()` to get a typed field handle inside a component that will be used under `form.AppField`:

```tsx
// components/fields/TextField.tsx
import { useFieldContext } from '@/hooks/form'

export function TextField({ label }: { label: string }) {
  const field = useFieldContext<string>()

  return (
    <label>
      <span>{label}</span>
      <input
        name={field.name}
        value={field.state.value}
        onBlur={field.handleBlur}
        onChange={(e) => field.handleChange(e.target.value)}
        aria-invalid={!field.state.meta.isValid}
      />
      {field.state.meta.isTouched && !field.state.meta.isValid && (
        <em>{field.state.meta.errors.map(e => typeof e === 'string' ? e : e?.message).join(', ')}</em>
      )}
    </label>
  )
}
```

The `<string>` generic on `useFieldContext` tells the component what value type to expect. If you pass it under an `AppField` of the wrong type, TypeScript warns.

## Using it in a form

```tsx
import { useAppForm } from '@/hooks/form'

export function SignupForm() {
  const form = useAppForm({
    defaultValues: { email: '', password: '', acceptsTerms: false },
    validators: { onChange: signupSchema },
    onSubmit: async ({ value }) => signup(value),
  })

  return (
    <form onSubmit={(e) => { e.preventDefault(); form.handleSubmit() }}>
      <form.AppField name="email">
        {(f) => <f.TextField label="Email" />}
      </form.AppField>

      <form.AppField name="password">
        {(f) => <f.TextField label="Password" />}
      </form.AppField>

      <form.AppField name="acceptsTerms">
        {(f) => <f.CheckboxField label="I accept the terms" />}
      </form.AppField>

      <form.AppForm>
        <form.SubmitButton label="Sign up" />
      </form.AppForm>
    </form>
  )
}
```

The render prop shrinks from ~12 lines per field to 2. The reusable field components own the input markup, error display, and labels.

## `form.AppForm` — for pre-bound form-level components

Submit buttons, progress indicators, form-level error summaries. Wrap them in `<form.AppForm>` so the `formComponents` you registered are accessible:

```tsx
<form.AppForm>
  <form.SubmitButton label="Sign up" />
  <form.ErrorSummary />
</form.AppForm>
```

Only components inside `form.AppForm` can use the pre-bound form components. Anything outside still has access to `form.Subscribe` and the raw form API.

## `withForm` — splitting a big form into sections

When a form is large enough that a single component becomes unwieldy, use `withForm` to create sub-components that share the typed form:

```tsx
// sections/AddressSection.tsx
import { withForm } from '@/hooks/form'

export const AddressSection = withForm({
  defaultValues: { street: '', zip: '', country: '' },
  render: ({ form, title }: { form: /* inferred */; title: string }) => (
    <fieldset>
      <legend>{title}</legend>
      <form.AppField name="street">{(f) => <f.TextField label="Street" />}</form.AppField>
      <form.AppField name="zip">{(f) => <f.TextField label="ZIP" />}</form.AppField>
      <form.AppField name="country">{(f) => <f.TextField label="Country" />}</form.AppField>
    </fieldset>
  ),
})

// usage
<AddressSection form={form} title="Shipping address" />
```

The `defaultValues` in `withForm` declares the **shape that the parent form must contain**. It is not creating a new form — it is asserting the subset of the parent's shape this section knows how to render.

When to use `withForm`:

- The form is too big for one file.
- The same section repeats (shipping address + billing address both use `AddressSection`).
- TypeScript inference is failing on a deeply nested field — splitting can recover inference.

## `withFieldGroup` — groups of fields reusable across forms with different shapes

`withForm` requires the section's shape to match the parent's shape exactly. `withFieldGroup` is for sections that should work across *different* forms whose roots don't match — e.g., a `PasswordFields` group (password + confirm) used in both signup and change-password forms.

```tsx
export const PasswordFields = withFieldGroup({
  defaultValues: { password: '', confirm: '' },
  render: ({ group }) => (
    <>
      <group.AppField name="password">{(f) => <f.TextField label="Password" />}</group.AppField>
      <group.AppField name="confirm">{(f) => <f.TextField label="Confirm" />}</group.AppField>
    </>
  ),
})

<PasswordFields form={form} fields="credentials" />
```

The `fields="credentials"` prop tells the group where in the parent's shape its fields live — so the parent can have `{ credentials: { password, confirm }, email }` and the group writes into `credentials.*`.

**Current limitation:** validators declared on the group are typed as `unknown`. There is no way today to propagate exact types through the group boundary. Live with runtime validation inside group validators, or apply validators at the parent form level.

## `useFieldContext` vs `useController` (RHF)

RHF's convention for reusable fields is a wrapper around `useController`:

```tsx
function RHFTextField({ name, control, label }: ...) {
  const { field, fieldState } = useController({ name, control })
  return <input {...field} aria-invalid={!!fieldState.error} />
}
```

TanStack Form's `useFieldContext<T>()` is the equivalent, but with one important difference: it reads from the `fieldContext` populated by `form.AppField`, not from a control prop passed explicitly. This means:

- The reusable component doesn't need a `control` / `form` prop — it picks up from context.
- It can only be used inside `<form.AppField>`, not standalone.

The trade-off is less explicit coupling at the use site (cleaner) but a harder error if someone uses the component outside an `AppField` (the context is undefined).

## When to NOT use createFormHook

For a one-off form with 2-3 fields, the render-prop form is shorter than setting up the hook. Reach for `createFormHook` when:

- You have 3+ reusable field types.
- You have 2+ forms in the codebase.
- You feel the verbosity actively hurting.

For this project, `createFormHook` is the default because forms will recur and consistency matters.

## A warning from the docs

The older pattern of using `useFormContext` / raw context to grab the form outside `AppField` "will not warn you when the types do not align — you risk runtime errors." Prefer `withForm` and `withFieldGroup` for composition; avoid hand-rolling context consumers.

## `AnyFieldApi` and `AnyFormApi`

Escape hatches for components that accept a field but don't need the concrete value type — e.g., a generic `<FieldError field={field} />` component. Type the prop as `AnyFieldApi` and you can pass any field:

```tsx
import type { AnyFieldApi } from '@tanstack/react-form'

export function FieldError({ field }: { field: AnyFieldApi }) {
  if (!field.state.meta.isTouched || field.state.meta.isValid) return null
  return (
    <p className="err">
      {field.state.meta.errors.map((e, i) => (
        <span key={i}>{typeof e === 'string' ? e : e?.message}</span>
      ))}
    </p>
  )
}
```

Use this sparingly — you lose the type-narrowing of `useFieldContext<T>()`. Good for truly-generic wrappers, not for actual input components.

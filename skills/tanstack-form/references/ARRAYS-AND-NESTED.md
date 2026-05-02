# Arrays, nested paths, and conditional fields

How to model variable-length data, deeply nested object paths, and fields that appear/disappear based on other field values.

## Field arrays

RHF's `useFieldArray` equivalent. Declare the parent field with `mode="array"` and the fieldApi exposes array helpers.

```tsx
type Line = { description: string; quantity: number; price: number }
type Invoice = { customer: string; items: Line[] }

const schema = z.object({
  customer: z.string().min(1, 'Required'),
  items: z
    .array(
      z.object({
        description: z.string().min(1, 'Required'),
        quantity: z.number().int().positive(),
        price: z.number().nonnegative(),
      }),
    )
    .min(1, 'At least one line item'),
})

export function InvoiceForm() {
  const form = useForm({
    defaultValues: { customer: '', items: [] as Line[] } satisfies Invoice,
    validators: { onSubmit: schema },
    onSubmit: async ({ value }) => save(value),
  })

  return (
    <form onSubmit={(e) => { e.preventDefault(); form.handleSubmit() }}>
      <form.Field name="customer">
        {(f) => <input {...bind(f)} placeholder="Customer" />}
      </form.Field>

      <form.Field name="items" mode="array">
        {(itemsField) => (
          <>
            {itemsField.state.value.map((_, i) => (
              <div key={i} style={{ display: 'flex', gap: 8 }}>
                <form.Field name={`items[${i}].description`}>
                  {(f) => <input {...bind(f)} placeholder="Description" />}
                </form.Field>
                <form.Field name={`items[${i}].quantity`}>
                  {(f) => (
                    <input
                      type="number"
                      value={f.state.value}
                      onChange={(e) => f.handleChange(Number(e.target.value))}
                    />
                  )}
                </form.Field>
                <form.Field name={`items[${i}].price`}>
                  {(f) => (
                    <input
                      type="number"
                      step="0.01"
                      value={f.state.value}
                      onChange={(e) => f.handleChange(Number(e.target.value))}
                    />
                  )}
                </form.Field>
                <button type="button" onClick={() => itemsField.removeValue(i)}>×</button>
              </div>
            ))}

            <button
              type="button"
              onClick={() =>
                itemsField.pushValue({ description: '', quantity: 1, price: 0 })
              }
            >
              + Line
            </button>

            {itemsField.state.meta.errors.map((e, i) => (
              <p key={i} className="err">{typeof e === 'string' ? e : e?.message}</p>
            ))}
          </>
        )}
      </form.Field>

      <form.Subscribe selector={(s) => s.canSubmit}>
        {(can) => <button disabled={!can}>Save</button>}
      </form.Subscribe>
    </form>
  )
}
```

## Array API

Available on the fieldApi of a `mode="array"` field:

| Method | Purpose | RHF equivalent |
|---|---|---|
| `pushValue(item)` | append | `append` |
| `removeValue(index)` | remove at index | `remove` |
| `insertValue(index, item)` | insert at index | `insert` |
| `replaceValue(index, item)` | replace at index | `update` |
| `moveValue(from, to)` | move | `move` |
| `swapValues(a, b)` | swap | `swap` |
| `clearValues()` | empty | `remove()` with no args |

These are imperative — call them from event handlers. They update `form.state.values` and trigger the appropriate validators.

## Keys and reordering

The docs' standard example uses `key={i}` (array index). **This is fine for append/remove but breaks for reorder.** When the user drags an item from position 3 to position 0, React sees the key at index 0 is the same and preserves that component instance — which is holding the *wrong* field state.

For any form with drag-and-drop or sort-on-input, store a stable ID on each item and key on that:

```tsx
type Line = { id: string; description: string; quantity: number; price: number }

itemsField.pushValue({ id: crypto.randomUUID(), description: '', quantity: 1, price: 0 })

// then
{itemsField.state.value.map((item, i) => (
  <div key={item.id}>...</div>
))}
```

This mirrors RHF's `fields[i].id` — RHF generates the ID for you; in TanStack Form you generate it.

## Array-level validation

Three places errors can come from:

1. **Item schema** (`z.array(z.object({ description: z.string().min(1) }))`) — errors surface on `items[i].description`.
2. **Array schema** (`.min(1, 'At least one item')`) — errors surface on the `items` field itself, readable from `itemsField.state.meta.errors`.
3. **Field-level validator on the array** — optional, if you need logic beyond what Zod expresses.

Item errors render next to the relevant input (through their own `<form.Field>`). Array-level errors render in the parent render prop (see the example above where the `items` field's own errors are rendered next to the "+ Line" button).

## Known fix worth pinning

`form.Subscribe` had an extra re-render bug on array-field mounts — fixed in **v1.27.4**. Pin `>=1.27.4` (preferably the latest 1.29.x). If you see phantom re-renders on `pushValue`, check your version.

## Nested object paths

Path syntax is identical to RHF: dots for objects, brackets for arrays.

```tsx
<form.Field name="address.city">{(f) => <input {...bind(f)} />}</form.Field>
<form.Field name="items[0].quantity">{(f) => <input {...bind(f)} />}</form.Field>
<form.Field name="items[0].tags[2].name">{(f) => <input {...bind(f)} />}</form.Field>
```

## Type inference for paths

Paths are derived from `defaultValues` via `DeepKeys<TFormData>`. Autocompletion works deeply, typos are compile errors, and `field.state.value` is narrowed to the leaf type.

Three pitfalls that break inference:

**Very large or recursive form types.** TS can give up and type a deep field value as `unknown`. The official workaround is to split the form with `withForm` (see [COMPOSITION.md](COMPOSITION.md)) or to cast at the use site (`value as string`).

**Union-typed fields.** A field that can be `string | number` can't be expressed through `defaultValues` alone because the default has to be one or the other. You end up typing `defaultValues as { x: string | number }` and writing manual casts at `handleChange` sites.

**Optional object branches.** `address?: { city: string }` means `address.city` is undefined when `address` itself is undefined. If the user hasn't opened that section yet, the field traversal yields nothing. Safer to default-initialize the branch as `address: { city: '' }` and use `z.optional()` only at the schema level.

## Conditional fields

TanStack Form has **no `shouldUnregister` equivalent**. When a conditional `<form.Field>` unmounts, its value stays in `form.state.values` by default. This is a deliberate difference from RHF.

Two consequences to manage:

1. Form-level Zod still validates the hidden field's data. If the schema says `shipping: z.object({...})`, the hidden shipping fields fail validation.
2. Submitting the form includes the stale values.

Three patterns to deal with this:

### Gate with a discriminated union

Cleanest when the "hidden vs shown" is a boolean toggle:

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

Zod type-narrows the two branches, so the submit handler can `if (value.needsShipping) { ... use value.shipping ... }` with no casts.

### Clear values in a listener

When the toggle flips, reset the dependent fields:

```tsx
<form.Field
  name="needsShipping"
  listeners={{
    onChange: ({ value }) => {
      if (!value) form.setFieldValue('shipping', { street: '', zip: '' })
    },
  }}
>
  {(f) => (
    <input
      type="checkbox"
      checked={f.state.value}
      onChange={(e) => f.handleChange(e.target.checked)}
    />
  )}
</form.Field>

<form.Subscribe selector={(s) => s.values.needsShipping}>
  {(needs) =>
    needs ? (
      <>
        <form.Field name="shipping.street">{(f) => <input {...bind(f)} />}</form.Field>
        <form.Field name="shipping.zip">{(f) => <input {...bind(f)} />}</form.Field>
      </>
    ) : null
  }
</form.Subscribe>
```

This gives you clean form state whether the user toggles before or after filling in the shipping fields.

### Filter before submit

If you can't change the schema (e.g., it's generated), filter in `onSubmit`:

```ts
onSubmit: async ({ value }) => {
  const payload = value.needsShipping
    ? value
    : { ...value, shipping: undefined }
  await api.save(payload)
}
```

Least clean of the three — the validator still runs on stale data, and you lose Zod's type narrowing. Prefer the discriminated union.

## `isFieldsValid` gotcha on newly-mounted fields

Open issue #1149: `isFieldsValid` can return `true` for a field that has never been validated, including conditional fields that just appeared. If your submit button relies on `isValid` / `canSubmit` for gating, trigger `form.validateAllFields('mount')` in an effect after the conditional field mounts:

```tsx
useEffect(() => {
  if (form.state.values.needsShipping) {
    form.validateAllFields('mount')
  }
}, [form.state.values.needsShipping])
```

Note: the effect reads `form.state.values` as a snapshot, which is fine here because we want the effect to re-run on change — React handles that via the dependency array, not the subscription system.

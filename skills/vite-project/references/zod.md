# Zod

Schema composition, type inference, and validation patterns.

## Core patterns

### Schema-first types

Define the schema, derive the type. Never duplicate.

```ts
const userSchema = z.object({
  id: z.number(),
  name: z.string().min(1),
  email: z.string().email(),
  role: z.enum(["admin", "member", "viewer"]),
  createdAt: z.string().datetime(),
});

type User = z.infer<typeof userSchema>;
```

### Input vs output schemas

Separate schemas for API responses and form inputs when they differ:

```ts
const userResponseSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string().email(),
  createdAt: z.string().datetime(),
});

const createUserInputSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email"),
});

type UserResponse = z.infer<typeof userResponseSchema>;
type CreateUserInput = z.infer<typeof createUserInputSchema>;
```

## Composition

### Extending schemas

```ts
const baseEntitySchema = z.object({
  id: z.number(),
  createdAt: z.string().datetime(),
  updatedAt: z.string().datetime(),
});

const userSchema = baseEntitySchema.extend({
  name: z.string(),
  email: z.string().email(),
});
```

### Picking and omitting

```ts
const createUserSchema = userSchema.omit({ id: true, createdAt: true, updatedAt: true });
const userSummarySchema = userSchema.pick({ id: true, name: true });
```

### Merging schemas

```ts
const withPaginationSchema = z.object({
  page: z.number(),
  pageSize: z.number(),
  total: z.number(),
});

const paginatedUsersSchema = withPaginationSchema.extend({
  items: z.array(userSchema),
});
```

## Discriminated unions

Model API responses and state machines with discriminated unions:

```ts
const apiResultSchema = z.discriminatedUnion("status", [
  z.object({ status: z.literal("success"), data: userSchema }),
  z.object({ status: z.literal("error"), code: z.number(), message: z.string() }),
]);

type ApiResult = z.infer<typeof apiResultSchema>;
```

## Transforms and preprocessing

### Coerce strings to numbers

```ts
const queryParamsSchema = z.object({
  page: z.coerce.number().int().positive().default(1),
  limit: z.coerce.number().int().positive().max(100).default(20),
});
```

### Transform dates

```ts
const eventSchema = z.object({
  name: z.string(),
  startDate: z.string().datetime().transform((s) => new Date(s)),
});
```

### Pipe for multi-step validation

```ts
const percentageSchema = z
  .string()
  .transform((s) => parseFloat(s))
  .pipe(z.number().min(0).max(100));
```

## Refinements

### Custom validation

```ts
const passwordSchema = z
  .string()
  .min(8)
  .refine((p) => /[A-Z]/.test(p), "Must contain an uppercase letter")
  .refine((p) => /[0-9]/.test(p), "Must contain a number");
```

### Cross-field validation with superRefine

```ts
const signupSchema = z
  .object({
    password: z.string().min(8),
    confirmPassword: z.string(),
  })
  .superRefine((val, ctx) => {
    if (val.password !== val.confirmPassword) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Passwords must match",
        path: ["confirmPassword"],
      });
    }
  });
```

## Branded types

Create nominal types for compile-time safety:

```ts
const UserIdSchema = z.number().int().positive().brand<"UserId">();
type UserId = z.infer<typeof UserIdSchema>;

const OrderIdSchema = z.number().int().positive().brand<"OrderId">();
type OrderId = z.infer<typeof OrderIdSchema>;

// Cannot accidentally pass a UserId where OrderId is expected
const fetchOrder = (id: OrderId) => { /* ... */ };
```

## Shared schemas

When a schema is used by both the API layer and forms, colocate it in `~/schemas/`:

```
src/
  schemas/
    user.ts      # userSchema, createUserSchema, updateUserSchema
    order.ts     # orderSchema, createOrderSchema
```

Import from both API functions and form components.

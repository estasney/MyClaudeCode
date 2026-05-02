# Type Patterns

## Discriminated unions for async state

Never model async states as independent booleans.

```ts
// BAD
type UserState = {
  isLoading: boolean;
  error: Error | null;
  data: User | null;
};
// allows impossible states: { isLoading: true, error: someError, data: someUser }

// GOOD
type AsyncState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: T }
  | { status: "error"; error: Error };
```

The `status` field acts as a discriminant — TypeScript narrows the type in switch/if branches automatically.

## Exhaustive switch

```ts
const assertNever = (value: never): never => {
  throw new Error(`Unhandled value: ${JSON.stringify(value)}`);
};

const renderState = (state: AsyncState<User>) => {
  switch (state.status) {
    case "idle":
      return null;
    case "loading":
      return <Spinner />;
    case "success":
      return <UserCard user={state.data} />;
    case "error":
      return <ErrorDisplay error={state.error} />;
    default:
      return assertNever(state);
  }
};
```

If a new variant is added to the union, TypeScript errors at every switch that doesn't handle it.

## Branded types

Prevent mixing structurally identical types:

```ts
type Brand<T, B extends string> = T & { readonly __brand: B };

type UserId = Brand<number, "UserId">;
type OrderId = Brand<number, "OrderId">;

const asUserId = (id: number): UserId => id as UserId;
const asOrderId = (id: number): OrderId => id as OrderId;

const fetchUser = (id: UserId) => { /* ... */ };
const fetchOrder = (id: OrderId) => { /* ... */ };

const userId = asUserId(1);
const orderId = asOrderId(1);

fetchUser(userId);  // ok
fetchUser(orderId); // type error
```

Pair with Zod branded schemas (see `references/zod.md`) for runtime + compile-time safety.

## Utility type recipes

### Make specific fields required

```ts
type WithRequired<T, K extends keyof T> = T & { [P in K]-?: T[P] };

type UserWithEmail = WithRequired<Partial<User>, "email">;
```

### Strict omit (errors on invalid keys)

```ts
type StrictOmit<T, K extends keyof T> = Omit<T, K>;
// Unlike built-in Omit, K is constrained to actual keys of T
```

### Extract discriminated union variant

```ts
type Extract<T, U> = T extends U ? T : never;

type SuccessState = Extract<AsyncState<User>, { status: "success" }>;
// { status: "success"; data: User }
```

### Template literal types for API routes

```ts
type ApiRoute = `/api/${string}`;
type UserRoute = `/api/users/${number}`;

const fetchFromApi = (route: ApiRoute) => fetch(route);
```

## Const assertions for literal types

```ts
const ROLES = ["admin", "member", "viewer"] as const;
type Role = (typeof ROLES)[number]; // "admin" | "member" | "viewer"

const isRole = (value: string): value is Role =>
  (ROLES as readonly string[]).includes(value);
```

## NoInfer for preventing unwanted inference

```ts
const createHandler = <T>(schema: z.ZodType<T>, handler: (data: NoInfer<T>) => void) => {
  return (raw: unknown) => {
    const result = schema.parse(raw);
    handler(result);
  };
};
```

`NoInfer` prevents TypeScript from inferring `T` from the `handler` parameter — it must be inferred from `schema` only.

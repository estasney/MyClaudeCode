# Component Contracts

Core principle: **components that need data to render must require that data in their props**. Push loading/error/empty states to boundaries and parents, not into every component.

## The invariant function

An invariant is a runtime assertion that narrows types and crashes loudly when violated.

```ts
function invariant(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(`Invariant violation: ${message}`);
  }
}
```

Use `tiny-invariant` for a production-ready version (strips messages in prod builds).

### When to use invariant vs optional chaining

```tsx
// BAD: silent fallback hides bugs
const UserProfile = ({ user }: { user?: User }) => {
  return <h1>{user?.name ?? "Unknown"}</h1>;
};

// GOOD: component requires real data
const UserProfile = ({ user }: { user: User }) => {
  return <h1>{user.name}</h1>;
};

// GOOD: invariant at the boundary where data transitions from optional to required
const UserProfilePage = () => {
  const { data, isLoading, error } = useUserQuery();

  if (isLoading) return <UserProfileSkeleton />;
  if (error) return <ErrorDisplay error={error} />;

  invariant(data, "User data should exist after successful query");

  return <UserProfile user={data} />;
};
```

### Rules

- Use `invariant` at boundaries where data transitions from `T | undefined` to `T`.
- Never use `invariant` as a substitute for proper error handling — it's for "this should be impossible" cases.
- If a condition is expected to fail sometimes (network errors, user input), use explicit error handling instead.

## No optional props for required render data

```tsx
// BAD: component renders meaningless UI when data is missing
type Props = {
  title?: string;
  items?: Item[];
};

const ItemList = ({ title = "Items", items = [] }: Props) => {
  return (
    <section>
      <h2>{title}</h2>
      {items.map((item) => (
        <ItemCard key={item.id} item={item} />
      ))}
    </section>
  );
};

// GOOD: component declares what it needs
type Props = {
  title: string;
  items: Item[];
};

const ItemList = ({ title, items }: Props) => {
  return (
    <section>
      <h2>{title}</h2>
      {items.map((item) => (
        <ItemCard key={item.id} item={item} />
      ))}
    </section>
  );
};
```

Default values mask bugs. If `items` is undefined, something went wrong upstream — don't paper over it.

## Loading skeletons

Loading states are explicit UI states, not fallback renders hidden inside components.

### Pattern: skeleton as a sibling component

```tsx
const UserCard = ({ user }: { user: User }) => (
  <div className="p-4 rounded-lg">
    <h3 className="text-lg font-bold">{user.name}</h3>
    <p className="text-gray-600">{user.email}</p>
  </div>
);

const UserCardSkeleton = () => (
  <div className="p-4 rounded-lg animate-pulse">
    <div className="h-5 w-32 bg-gray-200 rounded mb-2" />
    <div className="h-4 w-48 bg-gray-200 rounded" />
  </div>
);
```

### Pattern: loading boundary

```tsx
const UserSection = () => {
  const { data, isLoading, error } = useUserQuery();

  if (isLoading) return <UserCardSkeleton />;
  if (error) return <ErrorDisplay error={error} />;
  invariant(data, "User data must exist after successful query");

  return <UserCard user={data} />;
};
```

### Suspense boundaries

For route-level or section-level loading, use React Suspense:

```tsx
import { Suspense, lazy } from "react";

const Dashboard = lazy(() => import("~/pages/Dashboard"));

const App = () => (
  <Suspense fallback={<DashboardSkeleton />}>
    <Dashboard />
  </Suspense>
);
```

Place Suspense boundaries at meaningful UI divisions — route level, panel level, or section level. Avoid wrapping individual components in Suspense unless they have independent async data needs.

## Error boundaries

Use error boundaries to catch rendering errors at section boundaries:

```tsx
import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

type Props = {
  fallback: ReactNode;
  children: ReactNode;
};

type State = {
  hasError: boolean;
};

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
```

Place error boundaries around independent sections of UI so one failure doesn't take down the entire page.

## Summary

1. Components declare required data as non-optional props.
2. Parents/boundaries handle loading, error, and empty states.
3. `invariant()` narrows types at the boundary between optional and required.
4. Skeletons are sibling components, not conditional branches inside the real component.
5. Suspense and error boundaries handle async and failure states at meaningful UI divisions.

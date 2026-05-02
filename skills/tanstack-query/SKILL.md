---
name: tanstack-query
description: Rules for building React data-fetching and mutation code with TanStack Query (React Query) v5, framed around a strict component-gating discipline. 
---

# TanStack Query (React)

Patterns for query keys, mutations, invalidation, and the component-gating discipline that keeps children's prop types clean.

## Version anchor

This skill assumes **@tanstack/react-query v5** (v5.0 shipped Oct 2023; the line is at v5.100.x in 2026). Pre-v5 patterns you may see in stale tutorials are dead:

- `isLoading` on queries → renamed `isPending` (a derived `isLoading = isPending && isFetching` exists, but the status field is `pending`).
- `loading` status → `pending`. Same rename for mutations.
- `useErrorBoundary` option → `throwOnError`.
- Experimental `suspense: true` flag → removed; use the dedicated `useSuspenseQuery` / `useSuspenseInfiniteQuery` / `useSuspenseQueries` hooks.
- `cacheTime` → `gcTime`.
- `keepPreviousData: true` → `placeholderData: keepPreviousData` (the helper, imported from the package).

If a snippet uses any of those, it's v4 or earlier.

## The gating principle

**Children render with valid data, or they don't render at all.** A child component should never accept `User | undefined` as a prop just to handle a loading state inline, and it should never receive `User` as a prop drilled down from a parent that already fetched it. The parent owns the gate; the cache holds the data; children read from the cache directly.

The key insight: **a stable query key is an address.** Once data is in the cache, any component in the tree can read it by calling the same hook with the same key — TanStack Query deduplicates the underlying request, so there's no extra fetch. That means components that need data take an *identifier* (a `userId`, a `filterSpec`), never a pre-loaded payload.

What this rules out:

- Prop drilling fetched data. `<UserCard user={user} />` is wrong; `<UserCard userId={userId} />` is right. The card resolves the user from the cache via `userKeys.detail(userId)`.
- `T | undefined` in child prop types. If the gate is honest, the child only mounts when the cache has data.
- Non-null assertions (`data!.name`). Those are type lies that defeat `noUncheckedIndexedAccess`.
- Scattered loading/error UX. The gate defines it once per route or feature.

### `null` for empty, `undefined` for pending

This is the foundation that makes the rest of the gating discipline work cleanly. Adopt it as the convention for every queryFn in the codebase.

`queryFn` returns `T | null`. `null` means "the fetch succeeded but there is no data" — the user that doesn't exist, the search that found nothing, the optional record that wasn't set. This frees `undefined` to mean exactly one thing: "the query is pending."

This isn't fighting the library — it's aligning with it. The TanStack Query docs are explicit that `queryFn` cannot return `undefined` (it must resolve a value or throw); `undefined` is reserved by the library for pending state. Returning `null` puts the empty-result semantics in the user-space slot where they belong.

Concretely, `findUserById` looks like this:

```ts
const findUserById = async (id: number): Promise<User | null> => {
  const res = await fetch(`/api/users/${id}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json() as Promise<User>;
};
```

Three states, three types, one discriminator at the call site:

- `data === undefined` → pending (only ever set by the library)
- `data === null` → fetched, no record
- `data` is `T` → fetched, here it is

This collapses every "is it loading or is it just empty?" footgun in the codebase. The empty-state UX (`<NotFound />`, `<EmptyResults />`) lives in a `data === null` branch; loading UX lives in a `data === undefined` (or `isPending`) branch; the success branch sees only `T`.

### Suspense gate

The parent wraps children in `<Suspense>` + `<ErrorBoundary>`. Children call `useSuspenseQuery` with the stable key — the returned `data` is typed as the queryFn's return type, **never** `undefined` (Suspense handles pending). Combined with the null convention, that's `User | null`. No prop drilling, no defensive `undefined` branch, one explicit empty-state branch.

```tsx
// Parent — gates with Suspense; passes only the identifier
const UserPage = ({ userId }: { userId: number }) => (
  <ErrorBoundary fallback={<ErrorView />}>
    <Suspense fallback={<UserCardSkeleton />}>
      <UserCard userId={userId} />
    </Suspense>
  </ErrorBoundary>
);

// Child — reads from cache via the stable key
const UserCard = ({ userId }: { userId: number }) => {
  const { data: user } = useSuspenseQuery(userDetailOptions(userId));
  // user: User | null
  if (user === null) return <NotFound />;
  // user: User
  return (
    <div>
      <h1>{user.name}</h1>
      <p>{user.email}</p>
    </div>
  );
};
```

A grandchild four levels deep can call `useSuspenseQuery(userDetailOptions(userId))` and discriminate on null itself — the only thing that flows down the tree is `userId`.

`useSuspenseQuery` does not accept `enabled`, `placeholderData`, or `throwOnError` — accepting them would reintroduce `undefined` into the return type. For conditional fetching with Suspense, gate higher up (don't mount `UserCard` until `userId` is a definite number).

### Manual gate

The parent calls `useQuery`, branches on the status flags, and only mounts the child once the cache is populated. Children take the identifier and call `useQuery` with the same key — the cache is hot, so the call is a deduped no-op at runtime.

```tsx
// Parent — gates with status flags; passes only the identifier
const UserPage = ({ userId }: { userId: number }) => {
  const query = useQuery(userDetailOptions(userId));
  if (query.isPending) return <UserCardSkeleton />;
  if (query.isError) return <ErrorView error={query.error} />;
  // query.data: User | null (TS narrows after pending+error checks)
  if (query.data === null) return <NotFound />;
  return <UserCard userId={userId} />;
};

// Child — reads from cache via the same stable key
const UserCard = ({ userId }: { userId: number }) => {
  const { data: user } = useQuery(userDetailOptions(userId));
  // user: User | null | undefined — TS can't see parent's narrowing
  if (!user) return null; // unreachable at runtime; satisfies the type checker
  return (
    <div>
      <h1>{user.name}</h1>
      <p>{user.email}</p>
    </div>
  );
};
```

The discriminated union `useQuery` returns means the parent's narrowing is honest — after `isPending` and `isError` are ruled out, `data` is `T | null` (no `undefined`). The null branch shows the empty-state UX; the success branch passes the identifier down.

The child's `if (!user)` is the residual snag: TS can't see that the parent gated, so the child's `useQuery` still returns `T | null | undefined`. The defensive branch is unreachable at runtime (the cache is hot, and the parent already routed nulls to `<NotFound />`), but required for type-correctness. Two alternatives if the noise is unwelcome:

1. Use `useSuspenseQuery` in the child even though the parent uses `useQuery`. The cache is hot so it never actually suspends — it just gives you `T | null` directly. This works, but a Suspense boundary needs to exist somewhere above, at which point the Suspense gate is usually the cleaner whole.
2. Read synchronously with `queryClient.getQueryData(userDetailOptions(userId).queryKey)`. Returns the cached value but bypasses the subscription, so the child does not re-render on cache updates. Rarely what you want.

### Anti-pattern: `enabled` + non-null assertion in the queryFn

A common shape in older codebases:

```tsx
// AVOID — child must handle maybe-undefined userId, queryFn lies about types
const useUserPosts = (userId: number | undefined) =>
  useQuery({
    queryKey: postKeys.list(userId!),
    queryFn: () => fetchUserPosts(userId!),
    enabled: userId !== undefined,
  });
```

The `userId!` non-null assertions are correct at runtime (because `enabled` blocks execution when `userId` is undefined) but the type system has no way to know that. The hook accepts `undefined`, so the call site has to plumb `undefined` through, and the child component renders with no data and an in-progress query.

Replace with a parent-side gate so the hook's input is guaranteed:

```tsx
// Parent — gate before calling the hook
const UserPostsSection = ({ userId }: { userId: number | undefined }) => {
  if (userId === undefined) return null; // or an empty-state component
  return <UserPostsList userId={userId} />;
};

// Child — userId is definitely a number, no `enabled`, no `!`
const UserPostsList = ({ userId }: { userId: number }) => {
  const { data: posts } = useSuspenseQuery({
    queryKey: postKeys.list(userId),
    queryFn: () => fetchUserPosts(userId),
  });
  return <ul>{posts.map((p) => <li key={p.id}>{p.title}</li>)}</ul>;
};
```

The hook now takes `number`, the queryFn has no assertions, and the call site decides whether to render the section at all.

## Query key factory

Structured, composable query keys prevent key collisions and enable targeted invalidation. Use this factory pattern by default for every resource — the cost is one tiny module, the payoff is precise invalidation and discoverable keys.

```ts
const userKeys = {
  all: ["users"] as const,
  lists: () => [...userKeys.all, "list"] as const,
  list: (filters: UserFilters) => [...userKeys.lists(), filters] as const,
  details: () => [...userKeys.all, "detail"] as const,
  detail: (id: number) => [...userKeys.details(), id] as const,
};
```

The hierarchy maps directly to invalidation scope:

- `userKeys.all` — invalidate everything user-related (after a bulk operation).
- `userKeys.lists()` — invalidate every filtered list (a user was added/removed).
- `userKeys.list(filters)` — invalidate one specific filtered list.
- `userKeys.detail(id)` — invalidate a specific user's detail (a user was edited).

```ts
queryClient.invalidateQueries({ queryKey: userKeys.all });
queryClient.invalidateQueries({ queryKey: userKeys.lists() });
queryClient.invalidateQueries({ queryKey: userKeys.detail(userId) });
```

`invalidateQueries` does prefix matching, which is why the hierarchy works: invalidating `["users"]` matches `["users", "list", filters]` and `["users", "detail", id]`.

## queryOptions for type-safe sharing

When a query definition is used from more than one place — a hook, a prefetch, an imperative `getQueryData` call — wrap it with `queryOptions` so the key, fn, and result type stay in lockstep.

```ts
import { queryOptions } from "@tanstack/react-query";

const userDetailOptions = (id: number) =>
  queryOptions({
    queryKey: userKeys.detail(id),
    queryFn: () => findUserById(id), // returns Promise<User | null>
  });

// In a component
const { data: user } = useSuspenseQuery(userDetailOptions(userId));
// user: User | null

// In a route loader / prefetch
await queryClient.prefetchQuery(userDetailOptions(userId));

// In an imperative read — return type is User | null | undefined
//   undefined → cache miss
//   null      → cached, no such user
//   User      → cached, found
const cached = queryClient.getQueryData(userDetailOptions(userId).queryKey);
```

Without `queryOptions`, `getQueryData` returns `unknown` because the queryKey alone doesn't carry a result type. With it, the return type is inferred from the queryFn.

## Query patterns

### Basic query

```ts
const useUsersQuery = (filters: UserFilters) =>
  useQuery({
    queryKey: userKeys.list(filters),
    queryFn: () => fetchUsers(filters),
  });
```

### Derived data with select

Compute derived values at the cache level, not in the component body. `select` runs only when source data changes and the result is memoized per consumer.

```ts
const useActiveUserCount = () =>
  useQuery({
    queryKey: userKeys.lists(),
    queryFn: fetchAllUsers,
    select: (users) => users.filter((u) => u.isActive).length,
  });
```

Two consumers selecting different shapes from the same query share the underlying fetch but each gets its own memoized projection.

### Prefetching on hover

```ts
const prefetchUser = (queryClient: QueryClient, id: number) =>
  queryClient.prefetchQuery(userDetailOptions(id));
```

```tsx
const UserLink = ({ id, name }: { id: number; name: string }) => {
  const queryClient = useQueryClient();
  return (
    <Link to={`/users/${id}`} onMouseEnter={() => prefetchUser(queryClient, id)}>
      {name}
    </Link>
  );
};
```

`prefetchQuery` is a no-op if fresh data already exists in the cache, so hover-spam is safe.

## Mutation patterns

Default to optimistic updates. The user-perceived latency win is large and the rollback path is explicit. Reserve the simpler invalidate-on-success pattern for cases where the optimistic projection is genuinely hard to compute (e.g., the server assigns IDs you can't predict and the UI needs them immediately).

### Optimistic update (preferred)

```ts
const useToggleUserStatus = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: toggleUserStatus,
    onMutate: async (userId) => {
      // Cancel in-flight refetches so they don't overwrite our optimistic value
      await queryClient.cancelQueries({ queryKey: userKeys.detail(userId) });

      const previous = queryClient.getQueryData<User | null>(userKeys.detail(userId));

      queryClient.setQueryData<User | null>(userKeys.detail(userId), (old) =>
        old ? { ...old, isActive: !old.isActive } : old,
      );

      return { previous };
    },
    onError: (_err, userId, context) => {
      // Restore unconditionally — undefined snapshot means there was no cached value to begin with
      queryClient.setQueryData(userKeys.detail(userId), context?.previous);
    },
    onSettled: (_data, _err, userId) => {
      // Reconcile with server truth
      queryClient.invalidateQueries({ queryKey: userKeys.detail(userId) });
    },
  });
};
```

The `<User | null>` generics match the cached type. The `old ?` check handles all three falsy states (`null` for empty, `undefined` for cache miss, falsy values cleanly skipping the toggle). On error, restoring `context?.previous` even when undefined is the right move — it puts the cache back in the "no value here" state it was in before `onMutate`.

### Basic mutation with invalidation (fallback)

When the optimistic projection is impractical:

```ts
const useCreateUser = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
  });
};
```

The user sees the loading state during the network round-trip, then the list updates after invalidation refetches.

### Alternative: UI-only optimistic via `mutation.variables`

v5 exposes `variables` on the mutation result while a mutation is pending. For UI that displays only the in-flight value (not cache reads from elsewhere), this avoids touching the cache:

```tsx
const { mutate, variables, isPending } = useToggleUserStatus();
// While pending, `variables` holds the userId you passed to mutate()
```

Use this when the optimistic state is local to one component. Use the cache-write version (above) when multiple components need to see the optimistic value.

## staleTime vs gcTime

- **staleTime** — how long fetched data is considered fresh. While fresh, re-renders and remounts reuse the cache without a network round-trip. Default: `0` (always stale, refetch on every mount/focus). Bump to `5 * 60 * 1000` (5 min) or higher for data that doesn't change often.
- **gcTime** — how long *unused* cache entries are kept in memory after their last consumer unmounts. Default: `5 * 60 * 1000`. After this, the entry is garbage collected.

Rule of thumb: `staleTime` controls network frequency; `gcTime` controls memory. Set `staleTime` based on how fast the underlying data actually changes; rarely need to touch `gcTime`.

## Query client setup

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      retry: 1,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <RouterOrApp />
  </QueryClientProvider>
);
```

`retry: 1` instead of the default 3 keeps failed requests from hammering a broken endpoint while still absorbing transient blips. If the API has known flake patterns (cold starts, intermittent 502s), bump per-query rather than globally.

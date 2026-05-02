# Tanstack Query

Patterns for query keys, mutations, invalidation, and data fetching architecture.

## Query key factory

Structured, composable query keys prevent key collisions and enable targeted invalidation.

```ts
const userKeys = {
  all: ["users"] as const,
  lists: () => [...userKeys.all, "list"] as const,
  list: (filters: UserFilters) => [...userKeys.lists(), filters] as const,
  details: () => [...userKeys.all, "detail"] as const,
  detail: (id: number) => [...userKeys.details(), id] as const,
};
```

*Always* use this query key factory by default

### Why this structure

- `userKeys.all` — invalidate everything user-related.
- `userKeys.lists()` — invalidate all list variations without touching details.
- `userKeys.list(filters)` — target a specific filtered list.
- `userKeys.detail(id)` — target a specific user's detail cache.

```ts
// Invalidate all user data after a bulk operation
queryClient.invalidateQueries({ queryKey: userKeys.all });

// Invalidate only lists (user was added/removed)
queryClient.invalidateQueries({ queryKey: userKeys.lists() });

// Invalidate a specific user's detail (user was edited)
queryClient.invalidateQueries({ queryKey: userKeys.detail(userId) });
```

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

Avoid computing derived data in the component — use `select` to transform at the cache level:

```ts
const useActiveUserCount = () =>
  useQuery({
    queryKey: userKeys.lists(),
    queryFn: fetchAllUsers,
    select: (users) => users.filter((u) => u.isActive).length,
  });
```

### Dependent queries

```ts
const useUserPosts = (userId: number | undefined) =>
  useQuery({
    queryKey: postKeys.list(userId!),
    queryFn: () => fetchUserPosts(userId!),
    enabled: userId !== undefined,
  });
```

The user does not like this pattern

### Prefetching

```ts
const prefetchUser = (queryClient: QueryClient, id: number) =>
  queryClient.prefetchQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => fetchUser(id),
  });
```

Prefetch on hover for perceived performance:

```tsx
const UserLink = ({ id, name }: { id: number; name: string }) => {
  const queryClient = useQueryClient();

  const handleMouseEnter = () => {
    prefetchUser(queryClient, id);
  };

  return (
    <Link to={`/users/${id}`} onMouseEnter={handleMouseEnter}>
      {name}
    </Link>
  );
};
```

## Mutation patterns

### Basic mutation with invalidation

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

The user prefers using optimisitic updates

### Optimistic updates

```ts
const useToggleUserStatus = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: toggleUserStatus,
    onMutate: async (userId) => {
      await queryClient.cancelQueries({ queryKey: userKeys.detail(userId) });

      const previous = queryClient.getQueryData(userKeys.detail(userId));

      queryClient.setQueryData(userKeys.detail(userId), (old: User) => ({
        ...old,
        isActive: !old.isActive,
      }));

      return { previous };
    },
    onError: (_err, userId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(userKeys.detail(userId), context.previous);
      }
    },
    onSettled: (_data, _err, userId) => {
      queryClient.invalidateQueries({ queryKey: userKeys.detail(userId) });
    },
  });
};
```

## Stale time vs gc time

- **staleTime** — how long data is considered fresh. During this window, re-renders reuse cached data without refetching. Default: `0` (always stale). Set to `5 * 60 * 1000` (5 min) for data that doesn't change often.
- **gcTime** — how long unused cache entries are kept in memory. Default: `5 * 60 * 1000`. After this, garbage collected.

Rule of thumb: `staleTime` controls how often you hit the network. `gcTime` controls memory. Set `staleTime` based on how frequently the data actually changes.

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

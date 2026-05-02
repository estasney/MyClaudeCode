# Performance

Patterns for avoiding unnecessary rerenders, especially relevant since `react/jsx-no-bind` is enabled.

## Handler extraction

The `jsx-no-bind` rule errors on inline arrow functions in JSX props. Extract handlers.

```tsx
// ERROR: creates new function reference every render
const UserList = ({ users }: { users: User[] }) => (
  <ul>
    {users.map((user) => (
      <li key={user.id} onClick={() => selectUser(user.id)}>
        {user.name}
      </li>
    ))}
  </ul>
);

// OPTION 1: extract to a child component
const UserListItem = ({ user, onSelect }: { user: User; onSelect: (id: number) => void }) => {
  const handleClick = useCallback(() => onSelect(user.id), [user.id, onSelect]);
  return <li onClick={handleClick}>{user.name}</li>;
};

// OPTION 2: data attributes (avoids useCallback for simple cases)
const UserList = ({ users, onSelect }: { users: User[]; onSelect: (id: number) => void }) => {
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLLIElement>) => {
      const id = Number(e.currentTarget.dataset.userId);
      onSelect(id);
    },
    [onSelect]
  );

  return (
    <ul>
      {users.map((user) => (
        <li key={user.id} data-user-id={user.id} onClick={handleClick}>
          {user.name}
        </li>
      ))}
    </ul>
  );
};
```

## useCallback and useMemo

### When to use useCallback

- Passing a function to a memoized child (`React.memo`).
- Passing a function as a dependency to `useEffect` or another hook.
- Passing a handler to a list of items (see above).

### When NOT to use useCallback

- The child doesn't use `React.memo` — the callback is recreated but nothing skips.
- The component itself is cheap to render — memoization overhead exceeds savings.

### useMemo

```ts
// Expensive computation that shouldn't run every render
const sortedUsers = useMemo(
  () => [...users].sort((a, b) => a.name.localeCompare(b.name)),
  [users]
);
```

Don't use `useMemo` for trivial computations — the bookkeeping cost can exceed the computation cost.

## React.memo

Wrap components that receive stable props but have expensive render trees:

```tsx
const UserCard = memo(({ user }: { user: User }) => (
  <div className="p-4">
    <h3>{user.name}</h3>
    <p>{user.email}</p>
    <ExpensiveAvatar src={user.avatarUrl} />
  </div>
));
```

### Common pitfall: object/array literals in JSX

```tsx
// BAD: new object every render, memo is useless
<UserCard user={{ name, email }} />

// GOOD: stable reference
const user = useMemo(() => ({ name, email }), [name, email]);
<UserCard user={user} />
```

## Context splitting for performance

See `references/state-management.md` for the full pattern. Summary:

- Split contexts by update frequency.
- Separate state context from dispatch context.
- Components that only dispatch don't rerender on state changes.

## Avoiding cascading rerenders

### Problem: parent state change rerenders all children

```tsx
// BAD: toggling sidebar rerenders the entire page
const Layout = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return (
    <div>
      <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      <MainContent /> {/* rerenders unnecessarily */}
    </div>
  );
};
```

### Solution: isolate the stateful part

```tsx
const SidebarToggle = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  return <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />;
};

const Layout = () => (
  <div>
    <SidebarToggle />
    <MainContent /> {/* no longer rerenders on sidebar toggle */}
  </div>
);
```

The principle: push state down to the lowest component that needs it, or lift it into context with proper splitting.

## Measuring performance

- React DevTools Profiler — identifies which components rerender and why.
- `React.Profiler` component — programmatic render timing.
- `why-did-you-render` — logs unnecessary rerenders in development.

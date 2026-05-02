# Custom Hooks

## Typed context hooks (raise when null)

Never return `T | undefined` from a context hook. If the provider is missing, that's a bug — crash loudly.

```ts
import { createContext, useContext } from "react";
import type { ReactNode } from "react";

type AuthContextValue = {
  user: User;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
};

const AuthProvider = ({ children, user, logout }: { children: ReactNode; user: User; logout: () => void }) => (
  <AuthContext.Provider value={{ user, logout }}>
    {children}
  </AuthContext.Provider>
);

export { AuthProvider, useAuth };
```

### Factory for typed context hooks

When you create many contexts, extract the pattern:

```ts
const createSafeContext = <T>(displayName: string) => {
  const Context = createContext<T | null>(null);
  Context.displayName = displayName;

  const useContextValue = (): T => {
    const ctx = useContext(Context);
    if (ctx === null) {
      throw new Error(`use${displayName} must be used within a ${displayName}Provider`);
    }
    return ctx;
  };

  return [Context.Provider, useContextValue] as const;
};

// Usage
const [ThemeProvider, useTheme] = createSafeContext<ThemeContextValue>("Theme");
```

## Hook composition

### Wrapping Tanstack Query

Encapsulate query configuration so components don't know about keys or fetch functions:

```ts
const useUser = (id: number) => {
  const result = useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => fetchUser(id),
  });

  return result;
};

const useUpdateUser = (id: number) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateUserInput) => updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: userKeys.detail(id) });
      queryClient.invalidateQueries({ queryKey: userKeys.lists() });
    },
  });
};
```

### Composing hooks from hooks

```ts
const useUserWithPosts = (userId: number) => {
  const user = useUser(userId);
  const posts = useUserPosts(userId);

  return {
    user: user.data,
    posts: posts.data,
    isLoading: user.isLoading || posts.isLoading,
    error: user.error ?? posts.error,
  };
};
```

## Common utility hooks

### useDebounce

```ts
import { useEffect, useState } from "react";

const useDebounce = <T>(value: T, delay: number): T => {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
};
```

### useEventListener

```ts
import { useEffect, useRef } from "react";

const useEventListener = <K extends keyof WindowEventMap>(
  event: K,
  handler: (e: WindowEventMap[K]) => void,
  element: EventTarget = window
) => {
  const handlerRef = useRef(handler);
  handlerRef.current = handler;

  useEffect(() => {
    const listener = (e: Event) => handlerRef.current(e as WindowEventMap[K]);
    element.addEventListener(event, listener);
    return () => element.removeEventListener(event, listener);
  }, [event, element]);
};
```

### usePrevious

```ts
import { useEffect, useRef } from "react";

const usePrevious = <T>(value: T): T | undefined => {
  const ref = useRef<T | undefined>(undefined);

  useEffect(() => {
    ref.current = value;
  });

  return ref.current;
};
```

## Conventions

- Custom hooks that wrap a context always throw when used outside a provider — never return `undefined`.
- Data-fetching hooks wrap Tanstack Query and own the query key. Components don't construct keys.
- Hooks are named `use<Thing>` — not `use<Thing>Hook` or `useGet<Thing>`.
- Place hooks in `~/hooks/` for project-wide hooks, or colocate with the feature that uses them.
- Every hook that accepts cleanup-sensitive values (event handlers, callbacks) should use a ref to avoid stale closures.

# State Management

## State location decision tree

Before adding state, ask where it belongs:

1. **URL state** — filters, pagination, search terms, selected tab. Use URL params so the state is shareable and survives refresh. Tanstack Router or `useSearchParams`.
2. **Server state** — data from an API. Use Tanstack Query. Don't duplicate in local state.
3. **Global client state** — auth, theme, locale, sidebar open/closed. Use Context + useReducer.
4. **Local component state** — form inputs, hover/focus, animations. Use `useState`.

If you find yourself lifting state up more than two levels, it probably belongs in context or URL params.

## Context + useReducer

For state that multiple components need and that has complex transitions.

### Typed reducer pattern

```ts
type CounterState = {
  count: number;
  lastAction: string;
};

type CounterAction =
  | { type: "increment" }
  | { type: "decrement" }
  | { type: "reset" }
  | { type: "set"; payload: number };

const counterReducer = (state: CounterState, action: CounterAction): CounterState => {
  switch (action.type) {
    case "increment":
      return { count: state.count + 1, lastAction: "increment" };
    case "decrement":
      return { count: state.count - 1, lastAction: "decrement" };
    case "reset":
      return { count: 0, lastAction: "reset" };
    case "set":
      return { count: action.payload, lastAction: "set" };
  }
};
```

### Wiring into context

```tsx
import { useReducer } from "react";
import type { Dispatch, ReactNode } from "react";

type CounterContextValue = {
  state: CounterState;
  dispatch: Dispatch<CounterAction>;
};

const [CounterProvider, useCounter] = createSafeContext<CounterContextValue>("Counter");

const CounterContextProvider = ({ children }: { children: ReactNode }) => {
  const [state, dispatch] = useReducer(counterReducer, { count: 0, lastAction: "" });

  return (
    <CounterProvider value={{ state, dispatch }}>
      {children}
    </CounterProvider>
  );
};
```

### Exhaustive action handling

The discriminated union on `action.type` ensures the switch is exhaustive. TypeScript errors if you miss a case (when using `noUncheckedIndexedAccess` and strict).

Add an exhaustive check if you want a runtime guard:

```ts
const assertNever = (value: never): never => {
  throw new Error(`Unhandled action: ${JSON.stringify(value)}`);
};

// In reducer, after all cases:
default:
  return assertNever(action);
```

## Context splitting

Avoid the "god context" — a single context that holds everything forces every consumer to rerender when anything changes.

### Split by update frequency

```tsx
// Separate contexts for values that change at different rates
const AuthContext = createSafeContext<AuthState>("Auth");        // changes rarely
const SidebarContext = createSafeContext<SidebarState>("Sidebar"); // changes often
```

### Split state from dispatch

When many components dispatch but few read state:

```tsx
const TodoStateContext = createSafeContext<TodoState>("TodoState");
const TodoDispatchContext = createSafeContext<Dispatch<TodoAction>>("TodoDispatch");

const TodoProvider = ({ children }: { children: ReactNode }) => {
  const [state, dispatch] = useReducer(todoReducer, initialState);

  return (
    <TodoStateContext.Provider value={state}>
      <TodoDispatchContext.Provider value={dispatch}>
        {children}
      </TodoDispatchContext.Provider>
    </TodoStateContext.Provider>
  );
};
```

Components that only dispatch actions import `useTodoDispatch` — they don't rerender when state changes.

## When NOT to use Context

- **Server data** — Tanstack Query is the right tool. Don't fetch in an effect and store in context.
- **Prop drilling through 1-2 levels** — just pass the prop. Context adds indirection.
- **Frequently changing values** (mouse position, scroll offset) — context rerenders all consumers. Use refs or a dedicated subscription model.

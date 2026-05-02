# Project Conventions

## File naming

- Components: `PascalCase.tsx` — `UserCard.tsx`, `ErrorBoundary.tsx`
- Hooks: `camelCase.ts` — `useAuth.ts`, `useDebounce.ts`
- Utilities: `camelCase.ts` — `formatDate.ts`, `invariant.ts`
- Schemas: `camelCase.ts` — `userSchema.ts`, `orderSchema.ts`
- Types (standalone): `camelCase.ts` — `apiTypes.ts`
- Constants: `camelCase.ts` — `routes.ts`, `queryKeys.ts`

## Declarations

Prefer ES6 `const` arrow functions over `function` declarations, including for components, hooks, and utilities:

```ts
const formatDate = (d: Date) => d.toISOString();
const UserCard = ({ user }: Props) => <div>{user.name}</div>;
```

## Export patterns

Prefer **named exports** over default exports:

- Named exports enable refactoring (rename symbol, all imports update).
- Named exports prevent import name mismatches.
- Named exports work better with tree-shaking in some bundlers.

Exception: lazy-loaded route components need `export default` for `React.lazy()`:

```ts
// ~/pages/Dashboard.tsx
const Dashboard = () => { /* ... */ };
export default Dashboard;

// Usage
const Dashboard = lazy(() => import("~/pages/Dashboard"));
```

### Barrel files (index.ts)

Use sparingly. Barrel files are useful for public API surfaces of a feature module:

```
src/features/auth/
  index.ts          # re-exports public API
  AuthProvider.tsx
  useAuth.ts
  authReducer.ts    # internal, not re-exported
```

```ts
// src/features/auth/index.ts
export { AuthProvider } from "./AuthProvider";
export { useAuth } from "./useAuth";
```

Avoid deep barrel file chains — they hurt tree-shaking and obscure import origins.

## Folder structure

Start flat. Add structure when a directory gets crowded. Don't prematurely organize.

### Small project (starting point)

```
src/
  components/     # shared UI components
  hooks/          # shared custom hooks
  schemas/        # shared Zod schemas
  pages/          # route-level components
  lib/            # utilities, invariant, api client
  App.tsx
  main.tsx
  index.css
  vite-env.d.ts
```

### Growing project (feature-based)

```
src/
  components/     # truly shared UI (Button, Modal, Skeleton)
  hooks/          # truly shared hooks (useDebounce, useEventListener)
  schemas/        # shared schemas
  lib/            # api client, invariant, utils
  features/
    auth/
      AuthProvider.tsx
      useAuth.ts
      LoginForm.tsx
      index.ts
    users/
      UserCard.tsx
      useUser.ts
      useUpdateUser.ts
      userKeys.ts
      userSchema.ts
      index.ts
  pages/
    Dashboard.tsx
    UserProfile.tsx
  App.tsx
  main.tsx
```

Rule: if a file is only used by one feature, it lives in that feature's directory.

## Build strategy

### Vite defaults (recommended starting point)

Vite automatically splits code by module graph. Vendor dependencies end up in separate chunks. No configuration needed.

### Route-based lazy splitting

For apps with many routes, split at the route level:

```tsx
import { lazy, Suspense } from "react";

const Dashboard = lazy(() => import("~/pages/Dashboard"));
const UserProfile = lazy(() => import("~/pages/UserProfile"));
const Settings = lazy(() => import("~/pages/Settings"));

const App = () => (
  <Suspense fallback={<PageSkeleton />}>
    <Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/users/:id" element={<UserProfile />} />
      <Route path="/settings" element={<Settings />} />
    </Routes>
  </Suspense>
);
```

Each lazy import becomes its own chunk — users only download the code for the route they visit.

### Single bundle (no splitting)

For internal tools, Electron apps, or offline-first where a single request is cheaper than multiple:

```ts
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: undefined,
      },
    },
  },
});
```

### Manual chunk splitting

For fine-grained control over what goes into which chunk:

```ts
// vite.config.ts
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ["react", "react-dom"],
          query: ["@tanstack/react-query"],
        },
      },
    },
  },
});
```

This keeps vendor libraries in stable chunks that browsers cache across deploys.

## Fonts

Self-host fonts in `public/fonts/` or `src/assets/fonts/`.

```css
/* In index.css, before @import "tailwindcss" */
@font-face {
  font-family: "Inter";
  src: url("/fonts/Inter-Variable.woff2") format("woff2");
  font-weight: 100 900;
  font-display: swap;
}
```

Use `font-display: swap` to prevent invisible text during font loading.

For Tailwind, extend the font family in your CSS:

```css
@import "tailwindcss";

@theme {
  --font-sans: "Inter", sans-serif;
}
```

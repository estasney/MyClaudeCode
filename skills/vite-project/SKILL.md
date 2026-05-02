---
name: vite-project
description: Skill guide for new and existing Vite projects with TypeScript, Tailwind CSS v4, ESLint v9 flat config, and opinionated defaults.
---

# Vite Project Setup

Scaffold and configure a Vite + TypeScript project with opinionated defaults.

## Supported variants

- **React + TypeScript** (primary — includes React-specific ESLint rules, JSX config)
- **Vanilla TypeScript** (no framework — omit React plugins, jsx config, React reference files)

Ask which variant if not obvious from context.

## Scaffold workflow

### 1. Create the project

```bash
npm create vite@latest <project-name> -- --template react-ts
# or for vanilla: --template vanilla-ts
```

### 2. Install dependencies

```bash
cd <project-name>
npm install

# Always installed
npm install zod react-hook-form @hookform/resolvers
npm install @tanstack/react-query

# Tanstack Query ESLint plugin
npm install -D @tanstack/eslint-plugin-query

# Tailwind v4
npm install tailwindcss @tailwindcss/vite

# ESLint ecosystem
npm install -D \
  eslint-plugin-react \
  eslint-config-prettier \
  prettier

# Path alias
npm install -D vite-tsconfig-paths

# SVG as React component (only when user requests)
# npm install -D vite-plugin-svgr
```

**React Vite plugin**: Default to `@vitejs/plugin-react-swc` (faster, Rust-based). Fall back to `@vitejs/plugin-react` (Babel) only when the user needs a Babel plugin with no SWC equivalent. Document this choice in the project README.

To switch:
```bash
npm uninstall @vitejs/plugin-react
npm install -D @vitejs/plugin-react-swc
```
Update `vite.config.ts` import accordingly.

**Additional Tanstack libraries** (install only when user requests, always pair with ESLint plugin):
- `@tanstack/react-router` + `@tanstack/eslint-plugin-router`
- `@tanstack/react-table`
- `@tanstack/react-form` (alternative to react-hook-form)

### 3. Configure Tailwind v4

Update `vite.config.ts`:
```ts
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

Replace contents of `src/index.css`:
```css
@import "tailwindcss";
```

No `tailwind.config.js` needed — Tailwind v4 is zero-config by default.

**Gotcha: `.gitignore` kills auto-detection.** Tailwind v4 auto-detection skips all files matched by `.gitignore`. If `.gitignore` uses broad patterns like `*.*` with selective overrides, Tailwind will silently find zero classes and emit no utilities. Symptoms: build succeeds, CSS loads, but only contains theme/reset — no utility classes like `mb-2`, `flex`, etc. Fix: add an explicit `@source` directive in `index.css`:

```css
@import "tailwindcss";
@source "./**/*.{ts,tsx}";
```

The `@source` path is relative to the CSS file. This bypasses gitignore-based detection entirely and is the robust choice for any project with non-standard `.gitignore` patterns.

### 4. Configure path alias

In `tsconfig.app.json`, add to `compilerOptions`:
```json
{
  "paths": {
    "~/*": ["./src/*"]
  }
}
```

Do **not** set `baseUrl` — it is deprecated as of TS 5.x and will stop functioning in TS 7.0. When `baseUrl` is absent, `paths` resolves relative to the tsconfig directory, which is the correct behavior.

In `vite.config.ts`, add the plugin (single source of truth — reads from tsconfig):
```ts
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [react(), tailwindcss(), tsconfigPaths()],
});
```

Usage: `import { Button } from "~/components/Button";`

### 5. Configure tsconfig

Vite scaffolds a project-references structure: `tsconfig.json` -> `tsconfig.app.json` + `tsconfig.node.json`. Most changes go in `tsconfig.app.json`.

Set these in `tsconfig.app.json` `compilerOptions`:

```json
{
  "target": "ES2022",
  "lib": ["DOM", "DOM.Iterable", "ES2022"],
  "module": "ESNext",
  "moduleResolution": "bundler",
  "jsx": "react-jsx",
  "strict": true,
  "noEmit": true,
  "skipLibCheck": true,
  "esModuleInterop": true,
  "resolveJsonModule": true,
  "verbatimModuleSyntax": true,
  "forceConsistentCasingInFileNames": true,
  "noUncheckedIndexedAccess": true,
  "noFallthroughCasesInSwitch": true,
  "noPropertyAccessFromIndexSignature": true,
  "noUncheckedSideEffectImports": true,
  "useDefineForClassFields": true,
  "allowImportingTsExtensions": true,
  "types": ["vite/client"]
}
```

**Vanilla TS variant**: remove `"jsx": "react-jsx"`.

**Flags intentionally off** (ESLint handles these): `noUnusedLocals`, `noUnusedParameters`.

**`module` choice**: `ESNext` is the default. It's the most permissive for Vite since Vite handles actual bundling. Document in comments if changing.

#### tsconfig troubleshooting: moduleResolution

Default is `bundler` (correct for Vite). Known edge cases:

- **Old packages** without `package.json` `exports` field: add to `optimizeDeps.include` in `vite.config.ts` so Vite pre-bundles them.
- **Tools running outside Vite** (test runners, standalone scripts): use a separate tsconfig (e.g. `tsconfig.node.json`) with `moduleResolution: "Node16"`.

### 6. Configure ESLint

Modify the Vite-scaffolded `eslint.config.js`. Target structure:

```js
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import pluginQuery from "@tanstack/eslint-plugin-query";
import eslintConfigPrettier from "eslint-config-prettier/flat";
import globals from "globals";

export default tseslint.config(
  { ignores: ["dist/**"] },

  // Base
  js.configs.recommended,

  // TypeScript + React (scoped to TS files for type-aware linting)
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      ...tseslint.configs.strictTypeChecked,
      react.configs.flat.recommended,
      react.configs.flat["jsx-runtime"],
      reactHooks.configs.flat.recommended,
      ...pluginQuery.configs["flat/recommended"],
    ],
    languageOptions: {
      globals: { ...globals.browser },
      parserOptions: {
        project: ["./tsconfig.app.json", "./tsconfig.node.json"],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-refresh": reactRefresh,
    },
    settings: {
      react: { version: "detect" },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      // TypeScript
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/consistent-type-imports": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      "@typescript-eslint/ban-ts-comment": [
        "error",
        {
          "ts-expect-error": "allow-with-description",
          "ts-ignore": true,
          "ts-nocheck": true,
          "ts-check": false,
        },
      ],

      // General (use TS extension to avoid conflict with strictTypeChecked)
      "no-unused-expressions": "off",
      "@typescript-eslint/no-unused-expressions": [
        "error",
        { allowShortCircuit: true, allowTernary: true },
      ],
      "no-console": "warn",

      // React
      "react/prop-types": "off",
      "react/self-closing-comp": "error",
      "react/jsx-boolean-value": ["error", "never"],
      "react/jsx-no-useless-fragment": "warn",
      "react/jsx-key": "error",
      "react/jsx-no-target-blank": "off",
      "react/no-array-index-key": "error",
      "react/no-unstable-nested-components": "error",
      "react/jsx-no-leaked-render": "error",
      "react/jsx-no-constructed-context-values": "error",
      "react/jsx-no-bind": "error",
      // NOTE: no-unstable-default-props is not available in eslint-plugin-react.
      // Enforce via code review — see references/component-contracts.md.
      "react/no-danger": "error",
      "react/void-dom-elements-no-children": "warn",

      // React refresh
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],

      // Hooks
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "error",
    },
  },

  // Disable type-checked rules on plain JS files (e.g. eslint.config.js)
  {
    files: ["**/*.js"],
    extends: [tseslint.configs.disableTypeChecked],
  },

  // Prettier — must be last (disables formatting rules that conflict)
  eslintConfigPrettier
);
```

**Vanilla TS variant**: remove `react`, `reactHooks`, `reactRefresh`, `pluginQuery` imports and all React-specific rules/extends. Keep `tseslint.configs.strictTypeChecked`, `eslintConfigPrettier`, and the TypeScript/general rules.

Add Prettier scripts to `package.json`:
```json
{
  "scripts": {
    "format": "prettier --write .",
    "format:check": "prettier --check ."
  }
}
```

### 7. Scaffold vite-env.d.ts

Replace `src/vite-env.d.ts` with typed env vars and asset declarations:

```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Add project-specific VITE_ vars here
  readonly VITE_API_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Asset imports
declare module "*.svg" {
  const src: string;
  export default src;
}

declare module "*.png" {
  const src: string;
  export default src;
}

declare module "*.jpg" {
  const src: string;
  export default src;
}

declare module "*.jpeg" {
  const src: string;
  export default src;
}

declare module "*.gif" {
  const src: string;
  export default src;
}

declare module "*.webp" {
  const src: string;
  export default src;
}

declare module "*.woff" {
  const src: string;
  export default src;
}

declare module "*.woff2" {
  const src: string;
  export default src;
}
```

When `vite-plugin-svgr` is installed, add:
```ts
declare module "*.svg?react" {
  import type { FC, SVGProps } from "react";
  const ReactComponent: FC<SVGProps<SVGSVGElement>>;
  export default ReactComponent;
}
```

### 8. Strip boilerplate

Remove Vite's demo content:
- Delete `src/App.css`
- Delete `src/assets/` contents (keep the directory if desired)
- Remove the `import './App.css'` from `App.tsx`
- Replace `App.tsx` with a minimal shell:

```tsx
const App = () => {
  return <div></div>;
};

export default App;
```

- Replace `main.tsx` to satisfy `strictTypeChecked` (no non-null assertion):

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./index.css";
import App from "./App";

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

- Replace `src/index.css` with just `@import "tailwindcss";`
- Remove all files in `public/` (current template ships `favicon.svg`, `icons.svg` — names vary across versions)
- Strip the `<link rel="icon" ...>` line from `index.html` (prevents 404 on favicon after cleanup)

### 9. Verify

```bash
npm run dev          # should compile clean
npx tsc -b           # should pass type check (uses project references)
npx eslint .         # should pass lint
npx prettier --check . # should pass formatting (scaffolded README may need formatting)
```

---

## Reference files

Consult these when working on patterns beyond the scaffold itself. Read the relevant file before advising on that topic.

| File | When to read |
|------|-------------|
| `references/api-layer.md` | Fetch wrappers, response validation, error types |
| `references/tanstack-query.md` | Query keys, mutations, invalidation, prefetching |
| `references/forms.md` | react-hook-form + Zod, TanStack Form |
| `references/zod.md` | Schema patterns, inference, transforms |
| `references/component-contracts.md` | Invariants, loading states, prop requirements |
| `references/type-patterns.md` | Discriminated unions, branded types, exhaustive checks |
| `references/performance.md` | Memoization, handler extraction, context splitting |
| `references/project-conventions.md` | Naming, exports, folder structure |
| `references/state-management.md` | Context + useReducer, state location decisions |
| `references/custom-hooks.md` | Hook composition, typed context hooks, patterns |
| `references/web-workers.md` | Vite worker build config, typed message channels, RPC manager, spawn hook |

---

## Build strategy

Read `references/project-conventions.md` for the full breakdown. Summary:

- **SPA single bundle**: set `build.rollupOptions.output.manualChunks` to disable splitting. Use for internal tools, Electron apps, or offline-first.
- **Vite defaults**: automatic chunk splitting by module graph. Good baseline for most projects.
- **Route-based lazy splitting**: `React.lazy()` + `Suspense` at route boundaries. Best for public-facing apps with many routes.

Document the chosen strategy in the project README.

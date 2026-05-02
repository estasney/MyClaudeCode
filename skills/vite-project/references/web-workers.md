# Web Workers in Vite + TypeScript

Patterns for offloading work to a dedicated web worker with a typed message channel and request/response RPC over `postMessage`.

For service workers (PWA, offline caching, network proxy), this is the wrong file — different lifecycle, different concerns.

## When to reach for a worker

- CPU-bound work that would block the main thread (parsing, compression, crypto, large transforms)
- Long-running tasks where you want to keep the UI responsive
- Isolation: untrusted code, OPFS access from a non-UI context, WASM workloads with their own heap

Not a free win for small synchronous transforms — structured-clone serialization cost can dominate. Profile before assuming.

## Vite build configuration

These are documented constraints from `vite.dev/guide/features#web-workers`, not stylistic choices.

### The two construction syntaxes

```ts
// 1. Standards-aligned, recommended in Vite docs
const worker = new Worker(new URL("./my-worker.ts", import.meta.url), {
  type: "module",
});

// 2. Suffix-based (Vite-specific)
import MyWorker from "./my-worker.ts?worker";
const worker = new MyWorker();
```

Either works. The first is portable across non-Vite tooling; the second hides the URL/options ceremony.

### Static analysis is strict

Vite docs (verbatim): "The worker detection will only work if the `new URL()` constructor is used directly inside the `new Worker()` declaration. Additionally, all options parameters must be static values (i.e. string literals)."

Concretely, this **breaks** the build:

```ts
// Anti-pattern: factory wrapping defeats Vite's static analysis.
// Symptom: worker gets inlined as base64 with wrong MIME type
// (Vite issue #11823 — `.ts` files inline as `data:video/mp2t`).
const makeWorker = (url: URL, opts: WorkerOptions) => new Worker(url, opts);
const w = makeWorker(new URL("./my-worker.ts", import.meta.url), { type: "module" });
```

The literal `new Worker(new URL(...), { type: "module" })` must appear at the call site. A wrapper class can hold the resulting `Worker` instance, but cannot encapsulate its construction.

### vite.config.ts

```ts
export default defineConfig({
  plugins: [react()],
  worker: {
    format: "es",
  },
});
```

Without `worker.format: "es"`, an ESM worker (one that uses `import` statements) throws `SyntaxError: Cannot use import statement outside a module` at runtime in production builds. With `type: "module"` on the constructor and `format: "es"` in config, Vite emits the worker as an ES module chunk.

### Inline workers

```ts
import MyWorker from "./my-worker.ts?worker&inline";
```

The worker bundle is base64-embedded into the main bundle. Useful for small workers when you want a single-file deploy; bad for large workers (blocks main bundle parse).

## Message type design

Define both directions as discriminated unions. Each `kind` is a named string-literal type; envelopes are constrained to `T extends { kind: TMsgKind }`. The discriminant carries the operation; a correlation id pairs requests with responses.

```ts
// messages.ts — shared between main thread and worker

type TParseKind = "parse";
type TComputeKind = "compute";
type TCancelKind = "cancel";

export type TMsgKind = TParseKind | TComputeKind | TCancelKind;

type TParseRequest = { kind: TParseKind; source: string };
type TComputeRequest = { kind: TComputeKind; input: number[] };
type TCancelRequest = { kind: TCancelKind; targetId: string };

type TParseResponse = { kind: TParseKind; tree: TParseTree };
type TComputeResponse = { kind: TComputeKind; result: number };
type TCancelResponse = { kind: TCancelKind };

type TRequestEnvelope<T extends { kind: TMsgKind }> = T & { id: string };
type TResponseEnvelope<T extends { kind: TMsgKind }> =
  | (T & { id: string; ok: true })
  | { id: string; ok: false; error: string };

export type TToWorker = TRequestEnvelope<
  TParseRequest | TComputeRequest | TCancelRequest
>;
export type TFromWorker = TResponseEnvelope<
  TParseResponse | TComputeResponse | TCancelResponse
>;
```

Notes on the shape:

- `id` is shared between request and response. Manager uses it to resolve the right promise.
- `ok` discriminates success vs error on the response side. The error branch does not carry `kind` — failures are uniform regardless of which request failed. The success branch is keyed by `kind`, so `Extract<TFromWorker, { kind: K; ok: true }>` narrows correctly.
- Errors are data on the wire, not thrown — exceptions don't cross the postMessage boundary cleanly.
- Pairing `kind` across both unions means you can write exhaustive handlers on each side.

## Worker-side handler

```ts
// my-worker.ts
import type { TToWorker, TFromWorker } from "./messages";

const assertNever = (value: never): never => {
  throw new Error(`Unhandled variant: ${JSON.stringify(value)}`);
};

const post = (msg: TFromWorker): void => {
  (self as DedicatedWorkerGlobalScope).postMessage(msg);
};

self.onmessage = (event: MessageEvent<TToWorker>) => {
  const msg = event.data;
  try {
    switch (msg.kind) {
      case "parse": {
        const tree = parse(msg.source);
        post({ id: msg.id, ok: true, kind: "parse", tree });
        return;
      }
      case "compute": {
        const result = compute(msg.input);
        post({ id: msg.id, ok: true, kind: "compute", result });
        return;
      }
      case "cancel": {
        cancel(msg.targetId);
        post({ id: msg.id, ok: true, kind: "cancel" });
        return;
      }
      default:
        assertNever(msg);
    }
  } catch (err) {
    post({
      id: msg.id,
      ok: false,
      error: err instanceof Error ? err.message : String(err),
    });
  }
};

export {};
```

The `export {}` makes the file a module, which `tsconfig` requires when `verbatimModuleSyntax` is set (which the scaffold enables).

## Worker tsconfig

The worker file uses globals like `self` typed as `DedicatedWorkerGlobalScope`, which lives in the `webworker` lib. The main app's tsconfig typically includes `dom` but not `webworker` — including both causes type collisions (`MessageEvent`, `EventTarget`, etc., are defined in both).

The clean solution is a worker-scoped tsconfig:

```jsonc
// tsconfig.worker.json
{
  "extends": "./tsconfig.json",
  "compilerOptions": {
    "lib": ["webworker", "es2022"],
    "types": []
  },
  "include": ["src/**/*.worker.ts"]
}
```

Reference it from the root tsconfig as a project reference:

```jsonc
// tsconfig.json
{
  "references": [
    { "path": "./tsconfig.worker.json" }
  ]
}
```

Adopt a naming convention (e.g. `*.worker.ts`) so `include`/`exclude` patterns can sort files into the right tsconfig. Any imports from the main app that the worker pulls in must be type-compatible under both configs — keep shared modules (like `messages.ts`) free of DOM-specific types.

If you skip the separate tsconfig, the cast `(self as DedicatedWorkerGlobalScope)` shown in the handler example is the escape hatch. It works but loses type checking for everything reached through `self`.

## Manager wrapper

Generic over the kind union, request union, and response union. The kind constraint propagates: callers can't accidentally instantiate with a request union and response union whose kinds disagree.

```ts
// worker-manager.ts

type TBaseResponse = { id: string } & (
  | { ok: true; kind: string }
  | { ok: false; error: string }
);

type TPending = {
  settle: (msg: TBaseResponse) => void;
  abort: (reason: Error) => void;
  timer: ReturnType<typeof setTimeout> | null;
};

export class WorkerManager<
  TKind extends string,
  TToWorker extends { id: string; kind: TKind },
  TFromWorker extends { id: string } & (
    | { ok: true; kind: TKind }
    | { ok: false; error: string }
  ),
> {
  private readonly worker: Worker;
  private readonly pending = new Map<string, TPending>();
  private isTerminated = false;

  constructor(worker: Worker) {
    this.worker = worker;
    this.worker.onmessage = this.handleMessage;
    this.worker.onerror = this.handleError;
  }

  get terminated(): boolean {
    return this.isTerminated;
  }

  request<K extends TKind>(
    payload: Omit<Extract<TToWorker, { kind: K }>, "id">,
    options: { timeoutMs?: number } = {},
  ): Promise<Extract<TFromWorker, { kind: K; ok: true }>> {
    return new Promise<Extract<TFromWorker, { kind: K; ok: true }>>((resolve, reject) => {
      const id = crypto.randomUUID();
      const timer =
        options.timeoutMs != null
          ? setTimeout(() => {
              this.pending.delete(id);
              reject(new Error(`Worker request timed out: ${payload.kind}`));
            }, options.timeoutMs)
          : null;

      const settle: TPending["settle"] = (msg) => {
        if (msg.ok) {
          resolve(msg as Extract<TFromWorker, { kind: K; ok: true }>);
        } else {
          reject(new Error(msg.error));
        }
      };

      this.pending.set(id, { settle, abort: reject, timer });
      this.worker.postMessage({ ...payload, id } as TToWorker);
    });
  }

  terminate(): void {
    if (this.isTerminated) return;
    this.isTerminated = true;
    for (const pending of this.pending.values()) {
      if (pending.timer != null) clearTimeout(pending.timer);
      pending.abort(new Error("Worker terminated"));
    }
    this.pending.clear();
    this.worker.terminate();
  }

  private handleMessage = (event: MessageEvent<TFromWorker>): void => {
    const msg = event.data;
    const pending = this.pending.get(msg.id);
    if (!pending) return;

    this.pending.delete(msg.id);
    if (pending.timer != null) clearTimeout(pending.timer);

    pending.settle(msg);
  };

  private handleError = (event: ErrorEvent): void => {
    const err = new Error(`Worker error: ${event.message}`);
    for (const pending of this.pending.values()) {
      if (pending.timer != null) clearTimeout(pending.timer);
      pending.abort(err);
    }
    this.pending.clear();
  };
}
```

Design notes:

- Constructor takes a `Worker`, not a URL — keeps Vite's static analysis intact at the call site.
- `TKind` is an explicit type parameter so the kind union shared by request/response is named once and reused. The constraint enforces that response variants pair with declared request kinds.
- `settle` is a closure that captures the typed `resolve`/`reject` for one specific request. The cast `msg as Extract<TFromWorker, { kind: K; ok: true }>` lives inside the closure; runtime safety holds because `id`-based correlation guarantees the message matches the request that produced this closure. TypeScript has no existential types, so some erasure point is unavoidable when one `Map` aggregates resolves across heterogeneous calls — this form keeps the gap inside the function body rather than on the storage type. An alternative is to type `pending.resolve` as `(value: unknown) => void` and cast at storage time; same soundness story, different aesthetic.
- `abort` holds the raw `reject` for non-message terminations (`terminate()`, `handleError`). Splitting `settle` from `abort` keeps message-driven and termination-driven rejection paths distinct.
- `crypto.randomUUID()` is widely supported (all modern browsers, Node 19+). Fall back to a manual UUID v4 only for older environments.
- Errors-as-data on the wire, exceptions on the API. The wrapper translates `{ ok: false, error }` into a rejected promise.

Instantiation:

```ts
const manager = new WorkerManager<TMsgKind, TToWorker, TFromWorker>(worker);
```

## Spawn hook

Returns the manager directly — never null. Consumers don't need to gate calls.

```ts
// use-worker-manager.ts
import { useEffect, useState } from "react";
import { WorkerManager } from "./worker-manager";
import type { TMsgKind, TToWorker, TFromWorker } from "./messages";

const createWorkerManager = (): WorkerManager<TMsgKind, TToWorker, TFromWorker> => {
  const worker = new Worker(new URL("./my-worker.ts", import.meta.url), {
    type: "module",
  });
  return new WorkerManager<TMsgKind, TToWorker, TFromWorker>(worker);
};

export const useWorkerManager = (): WorkerManager<TMsgKind, TToWorker, TFromWorker> => {
  const [manager, setManager] = useState(createWorkerManager);

  useEffect(() => {
    if (manager.terminated) {
      setManager(createWorkerManager());
      return;
    }
    return () => manager.terminate();
  }, [manager]);

  return manager;
};
```

How this handles StrictMode in dev:

1. First mount: lazy `useState` constructs manager. Effect runs, registers cleanup.
2. StrictMode unmount: cleanup runs, terminates the manager.
3. StrictMode remount: effect re-runs. Sees `manager.terminated === true`, swaps in a fresh manager via `setManager`. The fresh manager's effect then registers cleanup normally.

In production with StrictMode off, the `if (manager.terminated)` branch never fires.

The literal `new Worker(new URL("./my-worker.ts", import.meta.url), { type: "module" })` lives inside `createWorkerManager`. Vite's static-analysis requirement is about the literal call expression, not its position — having it inside a regular function called by the hook is fine, as long as nothing parameterizes the URL or options.

## TanStack Query integration

Worker requests fit cleanly as query functions. The manager's `request()` already narrows by `kind`, so no runtime check on the response variant is needed:

```ts
const useParseTree = (source: string) => {
  const manager = useWorkerManager();
  return useQuery({
    queryKey: ["parse", source],
    queryFn: async () => {
      const res = await manager.request({ kind: "parse", source });
      return res.tree; // res is Extract<TFromWorker, { kind: "parse"; ok: true }>
    },
  });
};
```

Because `useWorkerManager` returns a non-null manager, no `enabled` gate is needed.

## Sharp edges

- **Structured clone, not reference passing.** Messages are deep-cloned. Functions, DOM nodes, class instances with methods, and most non-data objects don't survive. Use `Transferable` (`ArrayBuffer`, `MessagePort`, `OffscreenCanvas`, etc.) for zero-copy transfer of large binary data: `worker.postMessage(buf, [buf])`.
- **`import.meta.url` is required** for the URL constructor. Without it, the path resolves against the wrong base in production.
- **No DOM in the worker.** No `window`, `document`, `localStorage`. `fetch`, `crypto`, `IndexedDB`, `OPFS`, and most Web APIs are available.
- **Module workers in dev rely on browser support.** Vite docs note this used to be Chrome-only; current Firefox/Safari support is broad, but if you hit issues in dev with a non-Chrome browser, that's where to look first.
- **Cancellation is cooperative.** `terminate()` kills the worker hard but discards in-progress work and any pending state. For finer cancellation, send a `cancel` message and have the worker check for it at safe points.

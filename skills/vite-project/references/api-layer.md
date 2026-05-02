# API Layer

Type-safe API layer with Zod-validated responses and discriminated union error handling.

## Fetch wrapper

```ts
import { z } from "zod";

type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError };

type ApiError =
  | { kind: "network"; message: string }
  | { kind: "parse"; message: string; raw: unknown }
  | { kind: "client"; status: number; message: string }
  | { kind: "server"; status: number; message: string };

const apiFetch = async <T>(
  url: string,
  schema: z.ZodType<T>,
  init?: RequestInit
): Promise<ApiResult<T>> => {
  let response: Response;

  try {
    response = await fetch(url, init);
  } catch (err) {
    return {
      ok: false,
      error: {
        kind: "network",
        message: err instanceof Error ? err.message : "Network error",
      },
    };
  }

  if (!response.ok) {
    const kind = response.status >= 500 ? "server" : "client";
    return {
      ok: false,
      error: {
        kind,
        status: response.status,
        message: response.statusText,
      },
    };
  }

  const raw: unknown = await response.json();
  const parsed = schema.safeParse(raw);

  if (!parsed.success) {
    return {
      ok: false,
      error: {
        kind: "parse",
        message: parsed.error.message,
        raw,
      },
    };
  }

  return { ok: true, data: parsed.data };
};
```

## Usage with Tanstack Query

```ts
const userSchema = z.object({
  id: z.number(),
  name: z.string(),
  email: z.string().email(),
});

type User = z.infer<typeof userSchema>;

const fetchUser = (id: number) =>
  apiFetch(`/api/users/${id}`, userSchema);

const useUserQuery = (id: number) =>
  useQuery({
    queryKey: userKeys.detail(id),
    queryFn: () => fetchUser(id),
  });
```

## Error handling in components

```tsx
const UserProfile = () => {
  const { data: result, isLoading } = useUserQuery(1);

  if (isLoading) return <UserSkeleton />;
  if (!result) return null;

  if (!result.ok) {
    switch (result.error.kind) {
      case "network":
        return <NetworkError message={result.error.message} />;
      case "client":
        return <NotFound />;
      case "server":
        return <ServerError />;
      case "parse":
        return <UnexpectedError />;
    }
  }

  return <UserCard user={result.data} />;
};
```

## Conventions

- Every API response is validated with a Zod schema — no blind `as T` casts.
- Errors are values (discriminated unions), not thrown exceptions.
- The `kind` field on errors enables exhaustive switch handling.
- Parse errors in production mean the API contract changed — log these prominently.
- Keep schemas colocated with the API functions that use them, or in a shared `~/schemas/` directory if reused across forms and API calls.

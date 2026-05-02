# Forms

## react-hook-form + Zod (default)

### Basic setup

```ts
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

const createUserSchema = z.object({
  name: z.string().min(1, "Name is required"),
  email: z.string().email("Invalid email address"),
});

type CreateUserForm = z.infer<typeof createUserSchema>;
```

### Component

```tsx
const CreateUserForm = ({ onSubmit }: { onSubmit: (data: CreateUserForm) => void }) => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<CreateUserForm>({
    resolver: zodResolver(createUserSchema),
  });

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <div>
        <input {...register("name")} />
        {errors.name && <span>{errors.name.message}</span>}
      </div>
      <div>
        <input {...register("email")} type="email" />
        {errors.email && <span>{errors.email.message}</span>}
      </div>
      <button type="submit" disabled={isSubmitting}>
        Create
      </button>
    </form>
  );
};
```

### With mutation

```tsx
const CreateUserPage = () => {
  const createUser = useCreateUser();

  const handleSubmit = (data: CreateUserForm) => {
    createUser.mutate(data);
  };

  return <CreateUserForm onSubmit={handleSubmit} />;
};
```

### Field-level async validation

```ts
const usernameSchema = z.object({
  username: z.string().min(3),
});

const form = useForm({
  resolver: zodResolver(usernameSchema),
  mode: "onBlur",
});
```

For server-side uniqueness checks, use `setError` after mutation:

```ts
createUser.mutate(data, {
  onError: (error) => {
    if (error.field === "email") {
      form.setError("email", { message: "Email already in use" });
    }
  },
});
```

### Default values from API data

```ts
const useEditUserForm = (user: User) =>
  useForm<UpdateUserForm>({
    resolver: zodResolver(updateUserSchema),
    defaultValues: {
      name: user.name,
      email: user.email,
    },
  });
```

## TanStack Form (alternative)

TanStack Form v1 is stable. Use when you want:
- First-class type safety without a separate resolver
- Signals-based reactivity (fewer rerenders on large forms)
- Standard schema spec support (Zod, Valibot, ArkType)
- Cross-framework compatibility

```tsx
import { useForm } from "@tanstack/react-form";
import { z } from "zod";

const CreateUserForm = () => {
  const form = useForm({
    defaultValues: { name: "", email: "" },
    onSubmit: async ({ value }) => {
      await createUser(value);
    },
  });

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        form.handleSubmit();
      }}
    >
      <form.Field
        name="name"
        validators={{ onChange: z.string().min(1) }}
        children={(field) => (
          <div>
            <input
              value={field.state.value}
              onChange={(e) => field.handleChange(e.target.value)}
            />
            {field.state.meta.errors.map((err) => (
              <span key={err.message}>{err.message}</span>
            ))}
          </div>
        )}
      />
      <button type="submit">Create</button>
    </form>
  );
};
```

## Conventions

- Schema lives in `~/schemas/` when shared between API layer and forms.
- Form component receives an `onSubmit` callback — it doesn't own the mutation. Parent handles side effects.
- Validation messages come from the Zod schema, not hardcoded in JSX.
- Use `mode: "onBlur"` for forms where real-time validation is distracting.

# TypeScript / JavaScript Guide

Use for both TS and JS projects — TS is JS plus a type layer; the runtime rules are the same. Where they differ, the TS-specific note is called out.

## Manifest & Layout

- **Manifest**: `package.json`. Type config: `tsconfig.json` (TS only).
- **Source**: `src/` (most projects); some put it at the root.
- **Tests**: alongside source (`foo.test.ts` next to `foo.ts`) or in `__tests__/` directories.
- **Module system**: read `"type": "module"` in `package.json` — `module` means ESM, absent/`commonjs` means CommonJS. Don't mix without an explicit boundary.

## Idioms

- **`const` by default, `let` only when reassignment is needed.** Never `var`.
- **Arrow functions for callbacks.** `function` keyword only when you need its own `this` or hoisting.
- **Destructuring for objects.** `const { id, name } = user;` over `user.id`/`user.name` repeated.
- **TS: `unknown` instead of `any`.** `any` defeats the type system; `unknown` forces narrowing at the boundary.
- **TS: prefer `interface` for object shapes, `type` for unions/intersections/aliases.** Project may have a different convention — match it.
- **Async/await over `.then()` chains** — clearer, easier to error-handle.

## Common Anti-Patterns

- **`==` instead of `===`.** `==` does type coercion (`0 == ""` is `true`). Always `===` / `!==`.
- **Forgotten `await`.** Returns a Promise object; `if (await isReady())` works, `if (isReady())` checks if a Promise is truthy (always).
- **Mutating function arguments.** Often surprises callers. Return a new object/array.
- **`for…in` over arrays.** Iterates enumerable keys (strings), not values; pulls in inherited properties. Use `for…of` or `.forEach`.
- **TS: `as` casts hiding genuine type errors.** Treat `as` as a code smell — narrow the type with a type guard instead.
- **CommonJS `require` mixed into an ESM file** (or vice versa). Causes runtime failures that pass linting.

## Complexity Budget Notes

- Function length ≤30 lines: arrow-function expressions assigned to `const` count from `=>` to the matching brace.
- Parameters ≤4: destructured object counts as 1 parameter — preferred over 5+ positional args.
- Nesting ≤2: a `.then(...).then(...)` chain is sequential, not nested. `async/await` reads as flat.

## Tests

- **Framework**: jest (most common), vitest (Vite projects), mocha+chai (legacy), node:test (stdlib)
- **Naming**: `<name>.test.ts` or `<name>.spec.ts` — match existing files
- **Run**: `npm test -- --watchAll=false` (jest) or `npm test -- --run` (vitest). Always non-interactive in CI/scripts.
- **Don't mock filesystem or network** unless the test would otherwise hit a real one. Prefer fixtures.

## Lint, Format, Type-Check

- **Lint**: `eslint .` — config in `eslint.config.js` (flat) or `.eslintrc.*` (legacy)
- **Format**: `prettier --check .` (or `--write` to fix)
- **Type check**: `tsc --noEmit` (TS only)
- **TS strict mode**: check `tsconfig.json` for `"strict": true`. If false, types are advisory at best.

## Canonical Verify Sequence

```bash
npm install
npx prettier --check .
npx eslint .
npx tsc --noEmit          # TS only
npm test -- --watchAll=false
```

Replace `npm` with `pnpm`/`yarn`/`bun` if the project's lockfile says so (`pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`).

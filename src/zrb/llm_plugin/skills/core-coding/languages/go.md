# Go Guide

## Manifest & Layout

- **Manifest**: `go.mod` (module name + Go version + dependencies); `go.sum` (lockfile — don't hand-edit)
- **Source**: package per directory; `cmd/<app>/main.go` for binaries
- **Tests**: `<file>_test.go` in the same package as the code under test
- **Go version**: read first non-comment line of `go.mod`

## Idioms

- **Errors are values, returned not thrown.** `result, err := f(); if err != nil { return nil, err }` — the canonical pattern.
- **`defer` for cleanup.** Right after acquiring a resource: `f, err := os.Open(...); if err != nil { return err }; defer f.Close()`.
- **Small interfaces, defined at the use site.** `io.Reader` has one method; consumer-defined interfaces stay focused.
- **Zero values matter.** Design types so the zero value is usable (`var m sync.Mutex` works; no `NewMutex()` constructor).
- **Slices over arrays.** Almost always — arrays are fixed-size and rare outside of cryptography.
- **`context.Context` as the first parameter** for any function that does I/O or might be cancelled.

## Common Anti-Patterns

- **Ignored errors.** `_, _ = f.Write(...)` — almost always a bug. If you really mean it, comment why.
- **`panic` for normal control flow.** `panic` is for unrecoverable invariants; return errors otherwise.
- **Goroutine leaks.** A goroutine started in a handler that never exits leaks a stack. Always have a way to signal completion (`context.Context`, `chan struct{}`, `sync.WaitGroup`).
- **`time.Sleep` in tests.** Race-prone. Use `sync.WaitGroup`, channels, or `testify/eventually`.
- **Capturing loop variables in goroutines** (pre-1.22). Take the variable as an argument to the closure or alias it inside the loop.
- **Returning a pointer to a stack-local that escapes anyway.** Let the compiler decide — return values, not pointers, unless mutation or large size demands it.

## Complexity Budget Notes

- Function length ≤30 lines: `if err != nil { return ... }` chains push function length up — count them but don't extract just to reduce the number; the chain itself is idiomatic.
- Parameters ≤4: `context.Context` always counts as one even when first.
- Nesting ≤2: early returns on errors are the canonical way to flatten — embrace them.

## Tests

- **Framework**: stdlib `testing` package
- **Naming**: `TestXxx(t *testing.T)`; table-driven: `tests := []struct{ name string; in X; want Y }{...}`; `t.Run(tt.name, func(t *testing.T) { ... })`
- **Run**: `go test ./...` (all packages); `go test -race ./...` (race detector — use in CI)
- **Subtests over multiple `TestX` functions.** Cleaner failure messages, easier filtering with `-run`.

## Lint, Format

- **Format**: `gofmt -l .` (lists unformatted files; exit 0 = clean) or `goimports -l .`
- **Lint**: `golangci-lint run` — runs many linters under one binary; configure via `.golangci.yml`
- **Vet**: `go vet ./...` — built-in, catches common bugs

## Canonical Verify Sequence

```bash
gofmt -l .
go vet ./...
golangci-lint run
go test -race ./...
go build ./...
```

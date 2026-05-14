# API Documentation Template

Use when documenting a function, method, class, endpoint, or CLI command for *users of the interface* (not for the maintainer reading the source).

## Function / Method

````markdown
### `<signature>`

<One-sentence summary in imperative or descriptive voice. What does this do?>

**Parameters**
- `<name>` (`<type>`) — what it represents, and any constraint not obvious from the type.
- `<name>` (`<type>`, optional, default `<value>`) — same.

**Returns**
- `<type>` — what's in the returned value. For complex returns, describe the shape.

**Raises** (omit if none)
- `<ExceptionType>` — when this is raised.

**Example**
```<lang>
<minimum useful example, runnable as-is>
```

**Notes** (only if non-obvious)
- Mutates `<arg>` in place.
- Not thread-safe.
- Idempotent.
````

## REST Endpoint

````markdown
### `<METHOD> <path>`

<One-sentence summary.>

**Auth**: <required scope/role, or "none">
**Rate limit**: <N per minute, or "none">

**Path parameters**
- `<name>` (`<type>`) — description.

**Query parameters**
- `<name>` (`<type>`, optional) — description.

**Request body** (omit for GET)
```json
{
  "field": "type — purpose"
}
```

**Response 200**
```json
{
  "field": "type — purpose"
}
```

**Response 4xx / 5xx**
| Code | Meaning | When |
|------|---------|------|
| 400 | Bad Request | <specific trigger> |
| 401 | Unauthorized | Missing/invalid auth |
| 404 | Not Found | <specific trigger> |
| 429 | Rate Limited | Rate limit exceeded |

**Example**
```bash
curl -X <METHOD> https://api.example.com<path> \
  -H "Authorization: Bearer $TOKEN" \
  -d '<body>'
```
````

## CLI Command

````markdown
### `<command> [options] <args>`

<One-sentence summary.>

**Usage**
```
<command> [--flag] [--option=VALUE] <required-arg> [optional-arg]
```

**Arguments**
- `<arg>` — description.

**Options**
- `--flag` — what enabling it does.
- `--option=VALUE` (default: `<default>`) — what it controls.

**Examples**
```bash
# Common case
<command> arg

# With option
<command> --option=value arg
```

**Exit codes** (only if non-standard)
| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | <specific failure> |
| 2 | <specific failure> |
````

## Rules

- **Document the interface, not the implementation.** Users don't care that the function uses a hash map internally; they care what they pass in and get out.
- **Examples are mandatory.** A doc without an example is a doc nobody can use.
- **Be specific about types.** `dict[str, int]` beats `dict`. `list[User]` beats `list`.
- **Note errors at the boundary.** Document what makes the function raise, not what it does once it has.
- **Don't restate the signature in prose.** "This function takes a string and returns an integer" is noise — the signature already says that.
- **Keep examples runnable.** Copy-paste should work. If it requires setup, show the setup.
- **One-sentence summary in imperative or descriptive voice — be consistent across the file.** Pick one style and stick to it.

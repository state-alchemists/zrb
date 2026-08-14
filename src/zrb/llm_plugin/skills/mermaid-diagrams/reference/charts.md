# Chart and layout types

Each of these is individually small, so they share one file. All render; each is line-oriented and unforgiving about its own shape, so follow the forms below.

## pie

```mermaid
pie title Traffic
    "Direct" : 45
    "Search" : 30
```

Supports `title`, `showData`, and `%%` comments. It is drawn as bars, not a circle.

## mindmap

Indentation-based nesting. Write labels **plain** — shape markers are *not* stripped in this version, so `root((Project))` renders with the parentheses visible.

```mermaid
mindmap
  Project
    Design
      API
    Build
```

## gitGraph

`commit` (with `id:`, `type:`, `tag:`), `branch`, `checkout`/`switch`, `merge`, `cherry-pick`. Commit types `NORMAL`, `REVERSE`, `HIGHLIGHT`. This is the only diagram type that honours a `%%{init: …}%%` directive.

```mermaid
gitGraph
    commit
    branch feature
    commit
    checkout main
    merge feature
```

## gantt

Needs `dateFormat` and at least one `section`.

```mermaid
gantt
    title Plan
    dateFormat YYYY-MM-DD
    section Phase1
    Design :a1, 2026-01-01, 10d
    Build  :a2, after a1, 20d
```

## quadrantChart

The keyword is case-sensitive — `quadrantchart` falls through to the flowchart parser and renders as boxes of your source.

```mermaid
quadrantChart
    title Effort vs Value
    x-axis Low Effort --> High Effort
    y-axis Low Value --> High Value
    Quick win: [0.3, 0.8]
    Money pit: [0.8, 0.2]
```

## architecture-beta

```mermaid
architecture-beta
    group api(cloud)[API]
    service db(database)[DB] in api
    service srv(server)[Server] in api
    db:L -- R:srv
```

## timeline, journey, xychart-beta, block-beta, packet-beta, treemap-beta, kanban

Standard Mermaid syntax for each; all verified rendering.

```mermaid
timeline
    title Releases
    2024 : v1.0 : v1.1
    2025 : v2.0
```

```mermaid
journey
    title Signup
    section Onboard
      Visit: 5: User
      Register: 3: User
```

```mermaid
xychart-beta
    title "Sales"
    x-axis [jan, feb, mar]
    y-axis "Rev" 0 --> 100
    bar [30, 60, 90]
```

```mermaid
block-beta
    columns 3
    A B C
    D:2 E
```

```mermaid
packet-beta
    0-15: "Source Port"
    16-31: "Dest Port"
```

```mermaid
treemap-beta
"Root"
    "A": 40
    "B": 60
```

```mermaid
kanban
    Todo
        t1[Write docs]
    Doing
        t2[Fix bug]
```

## Calling `termaid` directly (rarely needed)

`render(source, *, use_ascii=False, padding_x=4, padding_y=2, rounded_edges=True, gap=4)`. The parameter names differ from the CLI flags (`use_ascii`, not `ascii`). `padding_x` and `gap` are forwarded to non-flowchart renderers **only when they differ from the default 4**, and `padding_y` / `rounded_edges` are ignored by most non-flowchart types — so passing the defaults explicitly is not the same as passing nothing.

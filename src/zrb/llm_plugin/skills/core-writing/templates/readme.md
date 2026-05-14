# README Template

Use when writing a project README. Match existing project tone — read 2–3 nearby READMEs first via `Glob` + `ReadMany` to anchor style.

## Structure (in order)

````markdown
# <Project Name>

<One-sentence value proposition: what this is and who it's for.>

<!-- Optional badges: build, version, license — only if the project uses them. -->

## Quick Start

```bash
# minimal install + smoke run
<exact commands>
```

If the user sees output from those three lines, they have a working install.

## Features

- <Bullet — concrete, not "fast and easy">
- <Bullet — concrete, not "powerful">
- <Bullet>

## Installation

For real installs (not just the smoke test above):

- Prerequisites
- Step-by-step commands
- Verification step ("you should see…")

## Usage

```<lang>
<minimum runnable example>
```

Then a second example covering a non-trivial use case. Two examples is usually enough; let the docs site cover the rest.

## Configuration

Only if the project has runtime config. Table of env vars or a config-file example:

| Variable | Default | Purpose |
|----------|---------|---------|
| `EXAMPLE_VAR` | `42` | What it controls |

## Development

How to set up locally, run tests, run the linter. Three to five commands max.

## Contributing

Link to `CONTRIBUTING.md` if one exists. Otherwise a one-paragraph "PRs welcome — open an issue first for non-trivial changes" line.

## License

One line. `MIT — see LICENSE.` is sufficient.
````

## Rules

- **First sentence earns the read.** If a reader can't tell what the project does after the first line, the README has failed.
- **Show working code before explaining.** Quick Start before Architecture. Examples before API reference.
- **Imperative voice in commands.** "Install dependencies" not "You should install dependencies".
- **No marketing adjectives.** Cut "powerful", "modern", "blazing fast", "elegant". Replace with a benchmark, a code snippet, or a specific capability.
- **Omit needless sections.** If there's no Configuration, no Contributing process, no badges — leave them out. Empty sections are worse than missing ones.

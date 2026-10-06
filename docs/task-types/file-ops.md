🔖 [Documentation Home](../../README.md) > [Task Types](./) > File Operations

# File Operations

Zrb provides specialized tasks for manipulating and synchronizing the filesystem.

---

## Table of Contents

- [`Scaffolder`](#1-scaffolder)
- [`RsyncTask`](#2-rsynctask)
- [Quick Comparison](#quick-comparison)

---

## 1. `Scaffolder`

The `Scaffolder` task is a templating engine. It copies an entire directory structure from a source to a destination, performing find-and-replace text transformations on the file contents (`transform_content`) **and even the file and directory names themselves** (`transform_path`).

### When to Use

| Use Case | Description |
|----------|-------------|
| Project scaffolding | Create "new project" wizards |
| Boilerplate generation | Generate standardized code modules |
| Configuration templates | Establish team-wide config standards |

### Example

Imagine you have a template directory at `./templates/basic-app`. You want to copy it to a new location and replace the word `APP_NAME_PLACEHOLDER` with a user-provided name.

```python
from zrb import Scaffolder, StrInput, Tpl, cli

create_project = cli.add_task(
    Scaffolder(
        name="create-project",
        input=StrInput(name="project_name", description="Name of the app"),
        
        # The directory containing your template files
        source_path="./templates/basic-app",
        
        # The destination path — Tpl renders {ctx.x} placeholders from inputs
        destination_path=Tpl("./projects/{ctx.input.project_name}"),
        
        # A dictionary of strings to find and replace in the copied files
        transform_content={
            "APP_NAME_PLACEHOLDER": Tpl("{ctx.input.project_name}")
        },

        # The same, applied to copied file and directory names
        transform_path={
            "APP_NAME_PLACEHOLDER": Tpl("{ctx.input.project_name}")
        },
    )
)
```

When a user runs `zrb create-project --project_name my-cool-app`, Zrb creates the new directory and injects `my-cool-app` wherever the placeholder existed in the templates — inside files, and in names such as `APP_NAME_PLACEHOLDER.py`, which becomes `my-cool-app.py`.

### Per-File Transforms with `ContentTransformer`

The dict shorthand above rewrites every copied file the same way. To limit a
transform to specific files, pass `ContentTransformer` instance(s) to
`transform_content` instead of a dict:

```python
from zrb import ContentTransformer, Scaffolder, StrInput, Tpl, cli

create_project = cli.add_task(
    Scaffolder(
        name="create-project",
        input=StrInput(name="project_name", description="Name of the app"),
        source_path="./templates/basic-app",
        destination_path=Tpl("./projects/{ctx.input.project_name}"),
        transform_content=[
            ContentTransformer(
                name="rename-app",
                match="*.py",  # glob, matched against each file's basename
                transform={"APP_NAME_PLACEHOLDER": Tpl("{ctx.input.project_name}")},
            ),
        ],
    )
)
```

`match` accepts a glob, a list of globs, or a predicate `(ctx, file_path) -> bool`
(`file_path` is the copied file's absolute path). By default (`match_mode="auto"`)
a string pattern is first tried as a regex against the **whole absolute path**
(`re.fullmatch`), then falls back to a glob — matched against the basename when the
pattern has no path separator, otherwise against the full path. So `"*.py"` and
`"config.json"` behave as globs in practice, while a regex must span the path
(`r".*/src/.*\.py"`). Because regex is tried first, a pattern such as
`".*config.json"` also matches `configXjson` (`.` is a regex wildcard). Pass
`match_mode="glob"` to force plain glob matching, or `match_mode="regex"` to force
regex-only.

---

## 2. `RsyncTask`

The `RsyncTask` provides a strongly-typed Python interface over the battle-tested `rsync` command-line utility. It handles complex synchronization between local folders or remote servers via SSH. The `rsync` binary must be installed (plus `sshpass` if you use password authentication).

### When to Use

| Use Case | Description |
|----------|-------------|
| Backups | Sync local folders |
| Mirror deployments | Deploy to remote servers |
| Artifact sync | Transfer build outputs |

### Local to Local Sync

```python
from zrb import RsyncTask, cli

sync_local = cli.add_task(
    RsyncTask(
        name="backup-data",
        local_source_path="./data/",
        local_destination_path="./backup/data/",
    )
)
```

### Local to Remote Sync (Push via SSH)

You can sync files directly to a remote server. While SSH keys are the recommended authentication method, `RsyncTask` also supports password authentication.

```python
from zrb import RsyncTask, Tpl, cli

deploy_remote = cli.add_task(
    RsyncTask(
        name="deploy",
        local_source_path="./dist/",
        remote_host="prod.example.com",
        remote_user="deploy_user",
        remote_destination_path="/var/www/html/",
        
        # Optional advanced configurations
        remote_port=2222,
        exclude_from=".rsyncignore",
        
        # Password auth: read the real secret from an env var via zrb's
        # templating, and pass it through the `remote_password` kwarg.
        # Zrb injects it as the `SSHPASS` env var and shells out via
        # `sshpass -e` under the hood. A bare string is a literal, so the
        # placeholder must be wrapped in `Tpl` to be rendered.
        remote_password=Tpl("{ctx.env.MY_SSH_PASSWORD}")
    )
)
```

---

## Quick Comparison

| Feature | `Scaffolder` | `RsyncTask` |
|---------|--------------|-------------|
| **Purpose** | Template generation | File synchronization |
| **Direction** | Source → Destination (one-way) | Source → Destination (one-way; upload or download, chosen by which side is remote) |
| **Transformations** | Yes (find/replace) | No (exact copy) |
| **Remote support** | No | Yes (via SSH) |
| **Best for** | New projects, boilerplate | Backups, deployments |

---

🔖 [Documentation Home](../../README.md) > [Task Types](./) > File Operations

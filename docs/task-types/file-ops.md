🔖 [Documentation Home](../../README.md) > [Task Types](./) > File Operations

# File Operations

Zrb provides specialized tasks for manipulating and synchronizing the filesystem.

---

## 1. `Scaffolder`

The `Scaffolder` task is a powerful templating engine. It copies an entire directory structure from a source to a destination, performing find-and-replace text transformations on the file contents and even the filenames themselves.

### When to use
Perfect for creating "new project" wizards, generating boilerplate code modules, or establishing standardized configuration templates across a team.

### Example

Imagine you have a template directory at `./templates/basic-app`. You want to copy it to a new location and replace the word `APP_NAME_PLACEHOLDER` with a user-provided name.

```python
from zrb import Scaffolder, StrInput, cli

create_project = cli.add_task(
    Scaffolder(
        name="create-project",
        input=StrInput(name="project_name", description="Name of the app"),
        
        # The directory containing your template files
        source_path="./templates/basic-app",
        
        # The destination path (can use Jinja templating from inputs)
        destination_path="./projects/{ctx.input.project_name}",
        
        # A dictionary of strings to find and replace in the copied files
        transform_content={
            "APP_NAME_PLACEHOLDER": "{ctx.input.project_name}"
        }
    )
)
```
When a user runs `zrb create-project --project-name my-cool-app`, Zrb creates the new directory and injects `my-cool-app` wherever the placeholder existed in the templates.

---

## 2. `RsyncTask`

The `RsyncTask` provides a strongly-typed Python interface over the battle-tested `rsync` command-line utility. It handles complex synchronization between local folders or remote servers via SSH.

### When to use
Use `RsyncTask` for backups, mirror deployments, or syncing build artifacts to remote testing environments.

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

You can sync files directly to a remote server. While SSH keys are the recommended authentication method, `RsyncTask` also securely handles password authentication via environment variables if needed.

```python
from zrb import RsyncTask, Env, cli

deploy_remote = cli.add_task(
    RsyncTask(
        name="deploy",
        local_source_path="./dist/",
        remote_host="prod.example.com",
        remote_user="deploy_user",
        remote_destination_path="/var/www/html/",
        
        # Optional advanced configurations:
        # remote_port=2222,
        # remote_ssh_key="~/.ssh/id_rsa_deploy",
        # exclude_from=".rsyncignore",
        
        # If using password auth (SSHPASS is picked up by rsync under the hood)
        env=[Env(name="SSHPASS", is_secret=True)] 
    )
)
```

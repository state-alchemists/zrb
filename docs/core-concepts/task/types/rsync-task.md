🔖 [Documentation Home](../../../../README.md) > [Core Concepts](../../../README.md) > [Task](../../README.md) > [Task Types](./README.md) > RsyncTask

# `RsyncTask`

The `RsyncTask` is a powerful, specialized task for synchronizing files and directories. It's built on top of the battle-tested `rsync` command-line utility, providing a convenient Python interface for common sync operations, especially between local and remote systems via SSH.

## Examples

### Local to Local Sync

A simple backup from one local folder to another.

```python
from zrb import RsyncTask, cli

sync_local = cli.add_task(
    RsyncTask(
        name="sync-local",
        description="Syncs files between two local folders",
        local_source_path="./source_folder/",
        local_destination_path="./destination_folder/",
    )
)
```

### Local to Remote Sync (Push)

Deploying a local directory to a remote server.

```python
from zrb import RsyncTask, cli

sync_to_remote = cli.add_task(
    RsyncTask(
        name="sync-to-remote",
        description="Pushes local files to a remote server",
        local_source_path="./local_data/",
        remote_host="your_remote_host.com",
        remote_user="your_user",
        remote_destination_path="/path/on/remote/",
        # For SSH keys, you can specify:
        # remote_port=22,
        # remote_password="your_password", # Use with caution, consider environment variables
        # remote_ssh_key="/path/to/your/ssh/key",
    )
)
```

### Remote to Local Sync (Pull)

Backing up a remote directory to your local machine.

```python
from zrb import RsyncTask, cli

sync_from_remote = cli.add_task(
    RsyncTask(
        name="sync-from-remote",
        description="Pulls files from a remote server to local",
        remote_host="your_remote_host.com",
        remote_user="your_user",
        remote_source_path="/path/on/remote/source/",
        local_destination_path="./local_backup/",
    )
)
```

### Handling Passwords

While SSH keys are recommended, `RsyncTask` can handle password authentication using environment variables.

```python
from zrb import RsyncTask, Env, cli

sync_with_pass = cli.add_task(
    RsyncTask(
        name="sync-with-password",
        description="Syncs using a password from an environment variable",
        local_source_path="./sensitive_data/",
        remote_host="another_remote.com",
        remote_user="remote_user",
        remote_destination_path="/remote/target/",
        env=[
            # The SSHPASS env var is used automatically by rsync
            Env(name="SSHPASS", prompt="Enter SSH password", is_secret=True),
        ],
    )
)
```

**When to use**: Use `RsyncTask` for any file synchronization needs. It's perfect for deployments, backups, and mirroring directories, leveraging the efficiency and reliability of `rsync`.
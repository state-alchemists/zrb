🔖 [Documentation Home](../../../README.md) > [Task](../../README.md) > Task Types > RsyncTask

# RsyncTask

The `RsyncTask` is a specialized task type that extends `CmdTask` to simplify file synchronization using the `rsync` command. It provides parameters specifically for configuring source and destination paths, including support for remote hosts via SSH.

Here's an example of how to use `RsyncTask`:

```python
from zrb import RsyncTask, StrInput, cli

# Example 1: Synchronize files from a local source to a local destination
sync_local_folders = cli.add_task(
    RsyncTask(
        name="sync-local",
        description="Synchronizes files between two local folders",
        local_source_path="./source_folder/",
        local_destination_path="./destination_folder/",
        # Additional rsync options can be added via the 'cmd' parameter if needed,
        # but RsyncTask handles basic sync with its dedicated parameters.
    )
)

# Example 2: Synchronize files from a local source to a remote destination via SSH
sync_to_remote = cli.add_task(
    RsyncTask(
        name="sync-to-remote",
        description="Synchronizes files from local to a remote server",
        local_source_path="./local_data/",
        remote_host="your_remote_host.com",
        remote_user="your_user",
        remote_destination_path="/path/on/remote/",
        # You can also specify remote_port, remote_password, or remote_ssh_key
        # remote_port=22,
        # remote_password="your_password", # Use with caution, consider environment variables
        # remote_ssh_key="/path/to/your/ssh/key",
    )
)

# Example 3: Synchronize files from a remote source to a local destination via SSH
sync_from_remote = cli.add_task(
    RsyncTask(
        name="sync-from-remote",
        description="Synchronizes files from a remote server to local",
        remote_host="your_remote_host.com",
        remote_user="your_user",
        remote_source_path="/path/on/remote/source/",
        local_destination_path="./local_backup/",
    )
)

# RsyncTask inherits from CmdTask, so you can still use CmdTask parameters
# For example, adding environment variables for SSH password if not using ssh_key
sync_with_password = cli.add_task(
    RsyncTask(
        name="sync-with-password",
        description="Synchronizes using password authentication",
        local_source_path="./sensitive_data/",
        remote_host="another_remote.com",
        remote_user="remote_user",
        remote_destination_path="/remote/target/",
        env=[
            Env(name="SSHPASS", prompt="Enter SSH password", is_secret=True),
        ],
        # RsyncTask automatically uses SSHPASS if available and remote_password is not set
    )
)
```

**When to use**: Use `RsyncTask` when your task involves copying or synchronizing files and directories, especially between local and remote systems. It leverages the efficient `rsync` utility, making it suitable for backups, deployments, and data migration.
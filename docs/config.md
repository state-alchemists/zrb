🔖 [Table of Contents](README.md)

# Configuration

You can configure Zrb using environment variables.

## Setting Environment Variables

### UNIX-like Systems (Linux, macOS, WSL, Termux)

In UNIX-like systems, you can set environment variables using the following methods:

1. Temporarily (for current session):
   Open a terminal and use the `export` command:

   ```
   export VARIABLE_NAME=value
   ```

   For example:
   ```
   export ZRB_LOG_LEVEL=DEBUG
   ```

2. Permanently:
   Add the export command to your shell configuration file (e.g., `~/.bashrc`, `~/.zshrc`, or `~/.profile`):

   ```
   echo 'export VARIABLE_NAME=value' >> ~/.bashrc
   ```

   Then, reload the configuration:
   ```
   source ~/.bashrc
   ```

### Windows

On Windows, you can set environment variables using the following methods:

1. Temporarily (for current session):
   Open a Command Prompt and use the `set` command:

   ```
   set VARIABLE_NAME=value
   ```

   For example:
   ```
   set ZRB_LOG_LEVEL=DEBUG
   ```

2. Permanently:
   a. Right-click on "This PC" or "My Computer" and select "Properties"
   b. Click on "Advanced system settings"
   c. Click on "Environment Variables"
   d. Under "User variables" or "System variables", click "New"
   e. Enter the variable name and value, then click "OK"

Alternatively, you can use the `setx` command in Command Prompt (run as administrator):

```
setx VARIABLE_NAME value
```

Note: After setting environment variables permanently on Windows, you may need to restart your command prompt or application for the changes to take effect.


🔖 [Table of Contents](README.md)

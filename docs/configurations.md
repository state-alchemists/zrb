🔖 [Table of Contents](README.md)

# Configuration

You can configure Zrb using environment variables. For example, you can turn off advertisement by set `ZRB_SHOW_ADVERTISEMENT` to `false`

```bash
export ZRB_SHOW_ADVERTISEMENT=false
zrb base64 encode --text non-credential-string
```

Try to set `ZRB_SHOW_ADVERTISEMENT` to `true` and `false` and see the result.

Some configurations are boolean. That's mean you can set them into:

- `true`, `1`, `yes`, `y`, or `active` to represent `True`
- `false`, `0`, `no`, `n`, or `inactivate` to represent `True`

# List of configurations

## `ZRB_ENV`

Environment variable prefix for your tasks. When define, Zrb will first try to find `<ZRB_ENV>_<VARIABLE_NAME>`. If the variable is not defined, Zrb will use `<VARIABLE_NAME>`. Very useful if you have multiple environments (i.e., prod, dev, staging)

- __Default value:__ Empty
- __Possible values:__ Any combination of alpha-numeric and underscore
- __Example:__ `DEV`

## `ZRB_INIT_SCRIPTS`

List of Python scripts that should be loaded by default.

- __Default value:__ Empty
- __Possible values:__ List of script paths, separated by colons(`:`).
- __Example:__ `~/personal/zrb_init.py:~/work/zrb_init.py`

## `ZRB_LOGGING_LEVEL`

Zrb log verbosity.

- __Default value:__ `WARNING`
- __Possible values:__ (sorted from the least verbose to the most verbose)
    - `CRITICAL`
    - `ERROR`
    - `WARNING`
    - `WARN` (or `WARNING`)
    - `INFO`
    - `DEBUG`

## `ZRB_SHELL`

Default shell to run Cmd Task. Should be `bash` compatible.

- __Default value:__ `bash`
- __Possible value:__
    - `/usr/bin/bash`
    - `/usr/bin/sh` 
    - etc.

## `ZRB_SHOULD_LOAD_BULTIN`

Whether Zrb should load builtin tasks or not.

- __Default value:__ `true`
- __Possible value:__ boolean values

## `ZRB_SHOW_ADVERTISEMENT`

Whether Zrb should load show advertisement or not.

- __Default value:__ `true`
- __Possible value:__ boolean values

## `ZRB_SHOW_PROMPT`

Whether Zrb should always show prompt or not.

- __Default value:__ `true`
- __Possible value:__ boolean values

## `ZRB_SHOW_TIME`

Whether Zrb should log the time or not.

- __Default value:__ `true`
- __Possible value:__ boolean values

## `ZRB_ENABLE_TYPE_CHECKING`

Whether Zrb should check data type or not.

Although it is safer to enable type checking, you can improve Zrb performance by turning off type checking.

- __Default value:__ `true`
- __Possible value:__ boolean values


🔖 [Table of Contents](README.md)
🔖 [Table of Contents](../README.md)

# Task Env

<!--start-doc-->
## `Env`
Task Environment

__Attributes:__

- `name` (`str`): environment name as recognized by Task.
- `os_name` (`Optional[str]`): OS's environment name. Empty string for no os_name.
- `default` (`JinjaTemplate`): Default value of the environment
- `should_render` (`bool`): Whether the environment value should be rendered or not.

### `Env._Env__get_prefixed_name`
No documentation available.

### `Env.get`
## Description

Return environment value.

You can use prefix to distinguish development environment
(e.g., 'DEV', 'PROD')

## Example

```python
os.environ['DEV_SERVER'] = 'localhost'
os.environ['PROD_SERVER'] = 'example.com'

env = Env(name='HOST', os_name='SERVER', default='0.0.0.0')

print(env.get('DEV'))   # will show 'localhost'
print(env.get('PROD'))  # will show 'example.com'
print(env.get('STAG'))  # will show '0.0.0.0'
```
### `Env.get_default`
## Description
Return environment's default value.
### `Env.get_name`
## Description
Return environment's name.
### `Env.get_os_name`
## Description
Return environment's os name.
### `Env.should_render`
## Description
Return boolean value, whether the value should be rendered or not.
<!--end-doc-->

🔖 [Table of Contents](../README.md)

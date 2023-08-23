# Human readable zrb package name

kebab-zrb-package-name is a [pypi](https://pypi.org) package.

You can install kebab-zrb-package-name by invoking the following command:

```bash
pip install kebab-zrb-package-name
```

Once kebab-zrb-package-name is installed, you can then run it by invoking the following command:

```bash
kebab-zrb-package-name
```

You can also import `kebab-zrb-package-name` into your Python program:

```python
from snake_zrb_package_name import hello

print(hello())
```


# For maintainers

## Publish to pypi

To publish kebab-zrb-package-name, you need to have a `Pypi` account:

- Log in or register to [https://pypi.org/](https://pypi.org/)
- Create an API token

You can also create a `TestPypi` account:

- Log in or register to [https://test.pypi.org/](https://test.pypi.org/)
- Create an API token

Once you have your API token, you need to create a `~/.pypirc` file:

```
[distutils]
index-servers =
   pypi
   testpypi

[pypi]
  repository = https://upload.pypi.org/legacy/
  username = __token__
  password = pypi-xxx-xxx
[testpypi]
  repository = https://test.pypi.org/legacy/
  username = __token__
  password = pypi-xxx-xxx
```

To publish kebab-zrb-package-name, you can do the following command:

```bash
zrb project publish-kebab-zrb-package-name
```

## Updating version

You can update kebab-zrb-package-name version by modifying the following section in `pyproject.toml`:

```toml
[project]
version = "0.0.2"
```

## Adding dependencies

To add kebab-zrb-package-name dependencies, you can edit the following section in `pyproject.toml`:

```toml
[project]
dependencies = [
    "Jinja2==3.1.2",
    "jsons==1.6.3"
]
```

## Adding script

To make zrb-package-name executable, you can edit the following section in `pyproject.toml`:

```toml
[project-scripts]
kebab-zrb-package-name = "kebab-zrb-package-name.__main__:hello"
```

This will look for `hello` callable inside of your `__main__.py` file

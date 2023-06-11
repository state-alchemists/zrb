🔖 [Table of Contents](README.md)

# For maintainers


To publish Zrb, you need a `Pypi` account:

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

To publish Zrb, you can do the following:

```bash
source ./project.sh

# Publish Zrb to TestPypi
zrb publish-test

# Publish Zrb to Pypi
zrb publish
```

🔖 [Table of Contents](README.md)
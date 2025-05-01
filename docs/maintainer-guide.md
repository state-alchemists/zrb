🔖 [Documentation Home](../README.md) > Maintainer Guide

# Maintainer Guide


To publish Zrb, you need a `Pypi` account:

- Log in or register to [https://pypi.org/](https://pypi.org/)
- Create an API token

You can also create a `TestPypi` account:

- Log in or register to [https://test.pypi.org/](https://test.pypi.org/)
- Create an API token

Once you have your API token, you need to configure poetry as follow:

```bash
poetry config pypi-token.pypi <your-api-token>
```


To publish Zrb, you can do the following command:

```bash
source ./project.sh
docker login -U stalchmst

zrb publish all
```

# Inspecting Import Performance

To inspect import peformance, you can run the following command:

```bash
pip install benchmark-imports
python -m benchmark_imports zrb
```

You can use the result to decide whether a module/dependency should be lazy-loaded or not.

🔖 [Documentation Home](../README.md)

🔖 [Table of Contents](README.md)

# Plugins

You can make part of your flows available worldwide by creating a Zrb plugin.

Zrb plugin is a pip package containing Zrb tasks. Nothing more.

# Creating a Plugin

To create a plugin, you can use Zrb builtin command:

```bash
zrb plugin create
```

Once you do so, you will have Zrb project containing a `pyproject.toml`.

You can modify the package as necessary, and you can publish your package to pypi by invoking the following command:

```bash
zrb plugin publish
```

# Installing a plugin

You can install a plugin as you install any Python Package.

The following are the most common ways to install Python Packages:

```bash
# Install a published Python package
pip install package-name

# Install a package from a directory
pip install --use-feature=in-tree-build /path/to/directory

# Install a package from a git repository
pip install git+https://github.com/user-name/repo-name.git
```


🔖 [Table of Contents](README.md)

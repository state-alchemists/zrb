🔖 [Table of Contents](README.md)

# Plugins

You can make part of your flows available worldwide by creating a Zrb plugin.

A Zrb plugin is a pip package containing Zrb tasks. Nothing more.

# Creating a Plugin

To create a plugin, you can use the Zrb builtin command:

```bash
zrb plugin create
```

Once you do so, you will have a Zrb Project containing a `pyproject.toml`.

You can modify the package as necessary, and you can publish your package to pypi by invoking the following command:

```bash
zrb plugin publish
```

# Installing a Plugin

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

# Existing Plugins

- [Zrb-Ollama](https://pypi.org/project/zrb-ollama/): Wrapper for Langchain and Ollama. Provides custom Zrb Task incorporating LLM into your workflow.
- [Zrb-Extras](https://pypi.org/project/zrb-extras/): Provides custom Zrb Tasks and helpers, currently WIP.


🔖 [Table of Contents](README.md)

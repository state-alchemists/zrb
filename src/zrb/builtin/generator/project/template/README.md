# PascalProjectName

This is a Zrb project.

To learn more about Zrb, please visit the [Zrb homepage](https://pypi.org/project/zrb/).

# PascalProjectName Directory Structure

```
.
    _automate/
        <your-automation-script>.py
    src/
        <your-source-code>
    .gitignore
    project.sh
    README.md
    requirements.txt
    template.env
    venv
    zrb_init.py
```

All automation scripts should be put in `_automate` directory and should be imported at `zrb_init.py`.

All other resources like application source code, Dockerfile, Helm charts, etc should be located under `src`.

If your automation script depends on third-party pip packages, add them to `requirements.txt`. To get more information about your existing pip package, you can do:

```bash
pip freeze
# or to get specified package information (e.g., dbt):
pip freeze | grep dbt
```


# How to Start PascalProjectName

```bash
source ./project.sh
zrb
```

Once you invoke the command, PascalProjectName virtual environment will be created.

# PascalProjectName Configurations

See [template.env](template.env)

To make your configuration, please copy `template.env` to `.env`


# Reloading PascalProjectName Configurations

To reload your configurations, you can invoke the following command:

```bash
reload
```

Please note that PascalProjectName's virtual environment has to be activated first.
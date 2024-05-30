🔖 [Table of Contents](../README.md) / [Concepts and Terminologies](README.md)

# Project 

<div align="center">
  <img src="../_images/emoji/building_construction.png"/>
  <p>
    <sub>
      A project is like a fridge light; it only works when you open it to check.
    </sub>
  </p>
</div>

Zrb allows you to isolate your work by putting them into Zrb Projects.

# Simple Project

At its core, a Project is a directory containing a single file named `zrb_init.py`. This simple setup is already sufficient for a simple hello-world project. Let's see how you can make a Project with a few commands.

```bash
mkdir my-project
cd my-project
touch zrb_init.py
```

# Standard Project

To make something more than a simple hello-world, you better use the `zrb project create` command.

```bash
zrb project create --project-dir my-project --project-name my-project
```

Once invoked, you will see a Project named `my-project` under your current directory. Let's see what this Project looks like:

```bash
cd my-project
ls -al
```

```
total 52
drwxr-xr-x  6 gofrendi gofrendi 4096 Nov 12 07:52 .
drwxr-xr-x 14 gofrendi gofrendi 4096 Nov 12 07:52 ..
drwxr-xr-x  7 gofrendi gofrendi 4096 Nov 12 07:52 .git
drwxr-xr-x  3 gofrendi gofrendi 4096 Nov 12 07:52 .github
-rw-r--r--  1 gofrendi gofrendi   27 Nov 12 07:52 .gitignore
-rw-r--r--  1 gofrendi gofrendi    7 Nov 12 07:52 .python-version
-rw-r--r--  1 gofrendi gofrendi 1937 Nov 12 07:52 README.md
drwxr-xr-x  3 gofrendi gofrendi 4096 Nov 12 07:52 _automate
-rwxr-xr-x  1 gofrendi gofrendi 1507 Nov 12 07:52 project.sh
-rw-r--r--  1 gofrendi gofrendi   13 Nov 12 07:52 requirements.txt
drwxr-xr-x  2 gofrendi gofrendi 4096 Nov 12 07:52 src
-rw-r--r--  1 gofrendi gofrendi  118 Nov 12 07:52 template.env
-rw-r--r--  1 gofrendi gofrendi   54 Nov 12 07:52 zrb_init.py
```

Every Zrb Project has a file named `zrb_init.py` under the top-level directory. This file is your entry point to define your Task definitions.

By convention, a Project usually contains two other sub-directories:

- ___automate__: This folder contains all your automation scripts and task definitions
- __src__: This folder contains all your resources like Docker compose file, helm charts, and source code.

Moreover, Zrb provides some built-in Tasks under the `project` Task Group. As always, you can invoke `zrb project` to see those tasks.

## Using `project.sh`

When you create a Project using `zrb project create` command, you will find a file named `project.sh`. This script file helps you to load the virtual environment, install requirements, and activate shell completion.

To use the script, you need to invoke the following command:

```bash
source project.sh
```

Make sure you load `project.sh` every time you start working on a Project.


🔖 [Table of Contents](../README.md) / [Concepts and Terminologies](README.md)

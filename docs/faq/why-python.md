🔖 [Table of Contents](../README.md) / [FAQ](README.md)

# Why Python?

Python is a general multi-purpose language. It support a lot of pogramming paradigms like OOP/FP, or procedural. Writing a configuration in Python let you do a lot of things like control structure, etc.

Python has been around since the 90's, and it was battle tested everywhere. Many people already familiar with the language. Even if you are new to the language, learning Python will be highly rewarding.

Nevertheless, there are a lot of tools out there that don't use Python.

So, we can extend the question: Why Python? Why not YAML/HCL/anything else?

# Why not YAML?

YAML format is widely used because of it's readability and simplicity. Many tools like [Ansible](https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html) or [Docker Compose](https://docs.docker.com/compose/) use YAML files for their configuration.

Using YAML for simple configuration can be a good idea.

However, for more complex scenario (like when you need to do looping or branching), using YAML is quite challenging. You need to overcome this with some tricks:

- Generating the YAML configuration somewhere else
- Using templating language like Jinja or Go template
- Implementing branch/loop structure in your YAML parser configuration

Compared to this, Python already has built-in control structure.

Moreover, you can define your Python configuration declaratively, almost like YAML.

Let's see how Ansible playbook and Zrb config might like similar to each other:

## Ansible Playbook

First of all, you need to define your virtual machines

```ini
# file: vm_inventory.ini
[my_vms]
192.168.1.100 ansible_ssh_user=ubuntu
192.168.1.101 ansible_ssh_user=ubuntu
192.168.1.102 ansible_ssh_user=ubuntu
```

Then you create a playbook to define what you want to do with the virtual machines

```yaml
# file: install_curl.yml
---
- name: Install curl on VMs
  hosts: my_vms
  become: true
  tasks:
    - name: Update package cache
      apt:
        update_cache: yes

    - name: Install curl
      apt:
        name: curl
        state: present
```

Finally, you run the playbook agains the virtual machines:

```bash
ansible-playbook -i vm_inventory.ini install_curl.yml
```

## Zrb Task Definition

You can define something similar with Zrb:

```python
# file: zrb_init.py
from zrb import (
    runner, CmdTask, RemoteCmdTask, RemoteConfig, PasswordInput
)

remote_configs = [
    RemoteConfig(
        host=f'192.168.1.{sub_ip}',
        user='ubuntu'
    ) for sub_ip in range(100, 103)
]

update_package_cache = RemoteCmdTask(
    name='update-package-cache',
    remote_configs=remote_configs,
    cmd='sudo apt update'
)

install_curl = RemoteCmdTask(
    name='install-curl',
    remote_configs=remote_configs,
    upstreams=[update_package_cache],
    cmd='sudo apt install curl --y'
)
runner.register(install_curl)
```

Then you can run the the task by invoking:

```bash
zrb install-curl
```

## Comparing Ansible Playbook and Zrb Task Definition

If you are not familiar with Python, Ansible Playbook will makes more sense for you. Ansible task definition is carefully crafted to cover most use cases.

The trickiest part when you work with Ansible or any YAML based configuration is you need to understand the tool specification. Docker compose for example, has a very different configuration from ansible eventough both of them are using YAML.

On the other hand, Python is just Python. You can use list comprehension, loop, branch, or anything you already know. The syntax highlighting, hint, and auto completion are commonly provided in your favorite tools.

Even if you are new to Python, Zrb Task Definition is not very difficult to grasp. You can follow the [getting started guide](../getting-started.md) and tag along.


# Why not Anything Else?

There are a few of considerations.

- Python is interpreted.

  Other language like go or rust might give you a better performance, but the iteration is generally slower. You need to compile them into machine code in order to make it works.

  Zrb is an automation tool. It helps developers doing their job. It doesn't serve any service to the end user. Thus, we can sacrifice the execution speed a little bit. No one will complain if your deployment is late for 0.5 seconds.

- Python is popular.

  If you are using macOS, there is a high chance you already have Python installed in your computer. Even if you are using Linux/Windows, installing Python is usually quite easy.

- We want to focus on the features.

  Building our own parser can be fun and challenging, but it doesn't bring any value to the user. We want to build Zrb on top of something battle proven, something you are already familiar with, something you can hack on without learning the whole new concept and specs.


🔖 [Table of Contents](../README.md) / [FAQ](README.md)

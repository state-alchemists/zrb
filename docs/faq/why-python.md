🔖 [Table of Contents](../README.md) / [FAQ](README.md)

# Why Python?

Python is a general multi-purpose language. It support a lot of pogramming paradigms like OOP/FP, or procedural. Writing a configuration in Python let you do a lot of things like control structure, etc.

Python has been around since the 90's, and you won't have to worry about the language. Many people already familiar with the language. Even if you are new to the language, learning Python will be highly rewarding.

However, there are a lot of tools out there that don't use Python. So, why Python? Why not YAML/HCL/anything else?

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
[my_vms]
192.168.1.100 ansible_ssh_user=ubuntu
192.168.1.101 ansible_ssh_user=ubuntu
192.168.1.102 ansible_ssh_user=ubuntu
```

Then you create a playbook to define what you want to do with the virtual machines

```yaml
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

## Zrb configs

You can define something similar with Zrb:

```python
from zrb import (
    runner, CmdTask, RemoteCmdTask, RemoteConfig, PasswordInput
)

remote_configs = [
    RemoteConfig(
        host=f'192.168.1.{sub_ip}',
        user='ubuntu'
    ) for sub_ip in range(100, 103)
]

install_curl = RemoteCmdTask(
    name='install-curl',
    remote_configs= remote_configs,
    cmd=[
        'sudo apt update',
        'sudo apt install curl --y'
    ]
)
runner.register(install_curl)
```


🔖 [Table of Contents](../README.md) / [FAQ](README.md)

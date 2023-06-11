# Resource maker

Resource maker is used to generate resources. Let's say you have a `template` folder containing a file named `app_name.py`:

```python
# file: template/app_name.py
message = 'Hello world_name'
print(message)
```

You can define a ResourceMaker like this:

```python
from zrb import ResourceMaker, StrInput, runner

create_hello_world = ResourceMaker(
    name='create-hello-world',
    inputs=[
        StrInput('app-name'),
        StrInput('world-name'),
    ],
    replacements={
        'app_name': '{{input.app_name}}',
        'world_name': '{{input.world_name}}',
    },
    template_path='template',
    destination_path='.',
)
runner.register(create_hello_world)
```

Now when you invoke the task, you will get a new file as expected:

```bash
zrb create-hello-world --app-name=wow --world-name=kalimdor
echo ./wow.py
```

The result will be:

```python
# file: template/wow.py
message = 'Hello kalimdor'
print(message)
```

This is a very powerful building block to build anything based on the template.


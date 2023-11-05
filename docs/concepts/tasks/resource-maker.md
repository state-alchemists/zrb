🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

# ResourceMaker

ResourceMaker helps you create text resources, whether they are code or licenses.

For example, let's say you have the following template under `mit-license-template/license`

```
Copyright (c) <zrb_year> <zrb_copyright_holders>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

You want your user to be able to add the license to any app and replacing `<year>` and `<copyright holders>` with user input.

To accomplish this, you can make a resource maker:

```python
from zrb import ResourceMaker, StrInput, runner
import os

CURRENT_DIR = os.path.dirname(__file__)

add_mit_license = ResourceMaker(
    name='add-mit-license',
    inputs=[
        StrInput(name='destination'),
        StrInput(name='year'),
        StrInput(name='copyright-holder')
    ],
    destination_path='{{input.destination}}',
    template_path=os.path.join(CURRENT_DIR, 'mit-license-template'),
    replacements={
        '<zrb_year>': '{{input.year}}',
        '<zrb_copyright_holders>': '{{input.copyright_holder}}',
    }
)

runner.register(add_mit_license)
```

Note that your template folder might contains a very complex structure. For example, you can make your application boiler plate into a template.


# ResourceMaker Parameters

Every [task parameters](./task.md#common-task-parameters) are applicable here. Additionally, a `ResourceMaker` has it's own specific parameters.


## template_path

## destination_path

## replacements

## replacement_mutator

## excludes

## skip_parsing

# ResourceMaker methods

Please refer to [common task methods](./README.md#common-task-methods).


🔖 [Table of Contents](../../README.md) / [Concepts](../README.md) / [Tasks](README.md)

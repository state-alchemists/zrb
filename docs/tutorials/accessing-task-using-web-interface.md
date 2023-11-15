🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

# Generating PDF Form

```bash
sudo apt-get install pdflatex
```

```tex
\documentclass{article}
\usepackage{hyperref}

\usepackage{fancyhdr}

\pagestyle{fancy}
\fancyhf{} % clear all header and footer fields
\fancyhead[C]{Iron Bank, Esos}
\fancyfoot{} % clear footer
\fancyfoot[R]{Confidential}

\begin{document}

\begin{Form}
\begin{tabular}{ll}
    Name & applicant-name \\
    Premi & applicant-premi \\
    Address & \TextField[name=address,width=5cm]{} \\
\end{tabular}
\end{Form}

\end{document}
```

```python
from zrb import CmdTask, ResourceMaker, runner, StrInput
from zrb.builtin.group import project_group
import os

CURRENT_DIR = os.path.dirname(__file__)
TEMPLATE_DIR = os.path.join(CURRENT_DIR, 'template')
RESULT_DIR = os.path.join(CURRENT_DIR, '../src/result')


applicant_name = StrInput(name='applicant-name', default='John Doe')
applicant_premi = StrInput(name='applicant-premi', default='12345')
applicant_address = StrInput(name='applicant-address', default='Jakarta')
inputs = [applicant_name, applicant_premi, applicant_address]


create_tex = ResourceMaker(
    name='create-tex',
    inputs=inputs,
    template_path=TEMPLATE_DIR,
    destination_path=RESULT_DIR,
    replacements={
        'applicant-name': '{{input.applicant_name}}',
        'applicant-premi': '{{input.applicant_premi}}',
        'applicant-address': '{{input.applicant_address}}',
    }
)

create_form = CmdTask(
    name='create-form',
    description='create form',
    group=project_group,
    inputs=inputs,
    upstreams=[create_tex],
    cwd=RESULT_DIR,
    cmd=[
        'pdflatex \\',
        '--jobname "{{ input.applicant_premi}}-{{ input.applicant_name }}" \\',
        '"{{ input.applicant_premi}}-{{ input.applicant_name }}.tex"',
        'rm "{{ input.applicant_premi}}-{{ input.applicant_name }}.aux"',
        'rm "{{ input.applicant_premi}}-{{ input.applicant_name }}.log"',
        'rm "{{ input.applicant_premi}}-{{ input.applicant_name }}.out"',
    ]
)
runner.register(create_form)
```

# Accessing Task Using Web Interface

```
uvicorn==0.24.0.post1
fastapi==0.104.1
```

```python
from fastapi import FastAPI
from fastapi.responses import FileResponse
from _automate.create_form import create_form

import os

CURRENT_DIR = os.path.dirname(__file__)
RESULT_DIR = os.path.join(CURRENT_DIR, 'src/result')

create_form_fn = create_form.to_function(is_async=True)

app = FastAPI()


# Endpoint to send a file as a response
@app.get("/get-file/")
async def get_file(name: str, premi: str):
    await create_form_fn(applicant_name=name, applicant_premi=premi)
    return FileResponse(f'{RESULT_DIR}/{premi}-{name}.pdf')

```

![](_images/pdf-form.png)

🔖 [Table of Contents](../README.md) / [Tutorials](README.md)

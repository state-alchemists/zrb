from zrb import CmdTask, HTTPChecker, StrInput, runner

cmd_template = '''
for i in 1 2 3 4 5
do
    sleep 1
    echo "{word} $i"
done
'''

ding = CmdTask(
    name='ding',
    color='green',
    inputs=[
        StrInput(name='satu', shortcut='s', default='1', prompt='satu'),
        StrInput(name='dua', shortcut='d', default='2', prompt='dua'),
    ],
    cmd=cmd_template.format(word='ding')
)

dong = CmdTask(
    name='dong',
    color='magenta',
    inputs=[
        StrInput(name='tiga', shortcut='t', default='3', prompt='tiga'),
        StrInput(name='empat', shortcut='e', default='4', prompt='empat'),
    ],
    cmd=cmd_template.format(word='dong')
)

dingdong = CmdTask(
    name='dingdong',
    upstreams=[ding, dong],
    cmd=cmd_template.format(word='ding dong')
)

run_server = CmdTask(
    name='runserver',
    upstreams=[ding, dong],
    cmd='python -m http.server',
    checkers=[
        HTTPChecker(port=8000)
    ]
)

runner.register(ding)
runner.register(dong)
runner.register(dingdong)
runner.register(run_server)

from zrb import CmdTask, Env, HTTPChecker, StrInput, runner

cmd_template = '''
for i in 1 2 3
do
    sleep 1
    echo "{word} $i"
done
'''

ding = CmdTask(
    name='ding',
    color='green',
    inputs=[
        StrInput(name='ding1', shortcut='i', default='ding', prompt='ding 1'),
        StrInput(name='ding2', shortcut='j', default='ding', prompt='ding 2')
    ],
    cmd=cmd_template.format(word='{{input.ding1}} {{input.ding2}}')
)

dong = CmdTask(
    name='dong',
    color='magenta',
    inputs=[
        StrInput(name='dong', shortcut='k', default='dong', prompt='dong word')
    ],
    cmd=cmd_template.format(word='{{input.dong}}')
)

dingdong = CmdTask(
    name='dingdong',
    upstreams=[ding, dong],
    cmd=cmd_template.format(word='{{input.ding1}} {{input.dong}}')
)

run_server = CmdTask(
    name='runserver',
    upstreams=[ding, dong],
    cmd='python -m http.server ${PORT}',
    envs=[
        Env(name='PORT', os_name='MY_PORT', default='3000')
    ],
    checkers=[
        HTTPChecker(port='{{env.PORT}}')
    ]
)

runner.register(ding)
runner.register(dong)
runner.register(dingdong)
runner.register(run_server)

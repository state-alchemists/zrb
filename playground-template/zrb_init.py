from zrb import (
    Group, CmdTask, Env, HTTPChecker, StrInput, runner
)

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

server = Group(name='server', description='Server related tasks')
run_server = CmdTask(
    name='run',
    group=server,
    upstreams=[ding, dong, dingdong],
    cmd='python -m http.server ${PORT}',
    envs=[
        Env(name='PORT', os_name='MY_PORT', default='3000')
    ],
    checkers=[
        HTTPChecker(port='{{env.PORT}}')
    ]
)

greeting = Group(name='greeting', description='Greeting')

greeting_id = Group(
    name='id', description='Indonesian greeting', parent=greeting
)


selamat_pagi = CmdTask(
    name='good-morning',
    group=greeting_id,
    cmd='echo Selamat Pagi'
)

selamat_malam = CmdTask(
    name='good-night',
    group=greeting_id,
    cmd='echo Selamat Malam'
)

greeting_jp = Group(
    name='jp', description='Japanese greeting', parent=greeting
)


ohayou = CmdTask(
    name='good-morning',
    group=greeting_jp,
    cmd='echo Ohayou'
)

oyasumi = CmdTask(
    name='good-night',
    group=greeting_jp,
    cmd='echo Oyasumi'
)


runner.register(ding)
runner.register(dong)
runner.register(dingdong)
runner.register(run_server)
runner.register(selamat_pagi)
runner.register(selamat_malam)
runner.register(ohayou)
runner.register(oyasumi)

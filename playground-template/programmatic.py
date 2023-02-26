from zrb_init import concat, register_trainer, fibo

print('Result', concat.create_main_loop()(
    'angry', 'bulbasaur', separator='-'
))

print('Result', register_trainer.create_main_loop()(
    name='John',
    password='secret',
    age=10,
    starter_pokemon='bulbasaur'
))

print('Result', fibo.create_main_loop()(
    n=7
))

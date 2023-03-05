from zrb_init import concat, register_trainer, fibo

print('Concat result', concat.create_main_loop()(
    'angry', 'bulbasaur', separator='-'
))

print('Register trainer result', register_trainer.create_main_loop()(
    name='John',
    password='secret',
    age=10,
    starter_pokemon='bulbasaur'
))

print('Fibo result', fibo.create_main_loop()(
    n=7
))

print('Fibo result (without default value)', fibo.create_main_loop()())

from zrb_init import concat, register_trainer, fibo

print('Concat result', concat.to_function()(
    'angry', 'bulbasaur', separator='-'
))

print('Register trainer result', register_trainer.to_function()(
    name='John',
    password='secret',
    age=10,
    starter_pokemon='bulbasaur'
))

print('Fibo result', fibo.to_function()(
    n=7
))

print('Fibo result (without default value)', fibo.to_function()())

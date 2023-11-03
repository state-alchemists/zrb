from zrb.task.docker_compose_task import (
    DockerComposeTask, ServiceConfig, Env, EnvFile
)

import pathlib
import os


def test_docker_compose_task_simple():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        compose_file=os.path.join(resource_path, 'docker-compose-simple.yml'),
        compose_service_configs={
            'myapp_simple': ServiceConfig(
                envs=[Env(name='POST_MESSAGE_2', default='As below so above')],
                env_files=[EnvFile(os.path.join(resource_path, 'runtime.env'))]
            )
        },
        compose_flags=['--build']
    )
    function = docker_compose_task.to_function()
    result = function()
    assert 'Hello, Compose!' in result.output
    assert 'As above so below' in result.output
    assert 'As below so above' in result.output


def test_docker_compose_task_with_cwd_and_compose_file():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='with-cwd-and-compose-file',
        cwd=resource_path,
        compose_file='docker-compose-simple.yml',
        compose_service_configs={
            'myapp_simple': ServiceConfig(
                envs=[Env(name='POST_MESSAGE_2', default='As below so above')],
                env_files=[EnvFile(os.path.join(resource_path, 'runtime.env'))]
            )
        },
        compose_flags=['--build']
    )
    function = docker_compose_task.to_function()
    result = function()
    assert 'Hello, Compose!' in result.output
    assert 'As above so below' in result.output
    assert 'As below so above' in result.output


def test_docker_compose_task_with_cwd():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='with-cwd',
        cwd=resource_path,
        compose_service_configs={
            'myapp': ServiceConfig(
                envs=[Env(name='POST_MESSAGE_2', default='As below so above')],
                env_files=[EnvFile(os.path.join(resource_path, 'runtime.env'))]
            )
        },
        compose_flags=['--build']
    )
    function = docker_compose_task.to_function()
    result = function()
    assert 'Hello, Compose!' in result.output
    assert 'As above so below' in result.output
    assert 'As below so above' in result.output


def test_docker_compose_task_invalid_compose_file():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    is_error: bool = False
    try:
        DockerComposeTask(
            name='simple',
            cwd=resource_path,
            compose_file='non-existing.yml',
        )
    except Exception:
        is_error = True
    assert is_error


def test_docker_compose_task_simple_no_default_env():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple-no-default-env',
        compose_file=os.path.join(
            resource_path, 'docker-compose-simple-no-default-env.yml'
        ),
        compose_service_configs={
            'myapp_simple_no_default_env': ServiceConfig(
                envs=[Env(name='POST_MESSAGE_2', default='As below so above')],
                env_files=[EnvFile(os.path.join(resource_path, 'runtime.env'))]
            )
        },
        compose_flags=['--build']
    )
    function = docker_compose_task.to_function()
    # run with env set
    if 'ZRB_TEST_DC_TASK_SIMPLE_NO_DEFAULT_MESSAGE' in os.environ:
        del os.environ['ZRB_TEST_DC_TASK_SIMPLE_NO_DEFAULT_MESSAGE']
    os.environ['ZRB_TEST_DC_TASK_SIMPLE_NO_DEFAULT_MESSAGE'] = 'Good night'
    result_default = function()
    assert 'Good night' in result_default.output
    assert 'As above so below' in result_default.output
    assert 'As below so above' in result_default.output
    del os.environ['ZRB_TEST_DC_TASK_SIMPLE_NO_DEFAULT_MESSAGE']


def test_docker_compose_task_simple_map_env():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple-map-env',
        compose_file=os.path.join(
            resource_path, 'docker-compose-simple-map-env.yml'
        ),
        compose_service_configs={
            'myapp_simple_map_env': ServiceConfig(
                envs=[Env(name='POST_MESSAGE_2', default='As below so above')],
                env_files=[EnvFile(os.path.join(resource_path, 'runtime.env'))]
            )
        },
        compose_flags=['--build']
    )
    function = docker_compose_task.to_function()
    # run with no env
    if 'ZRB_TEST_DC_TASK_SIMPLE_MAP_MESSAGE' in os.environ:
        del os.environ['ZRB_TEST_DC_TASK_SIMPLE_MAP_MESSAGE']
    result_default = function()
    assert 'Good morning' in result_default.output
    # run with env set to empty string
    os.environ['ZRB_TEST_DC_TASK_SIMPLE_MAP_MESSAGE'] = ''
    result_default = function()
    assert 'Good morning' in result_default.output
    # run with env set
    os.environ['ZRB_TEST_DC_TASK_SIMPLE_MAP_MESSAGE'] = 'Good night'
    result_custom = function()
    assert 'Good night' in result_custom.output
    del os.environ['ZRB_TEST_DC_TASK_SIMPLE_MAP_MESSAGE']


def test_docker_compose_task_simple_list_env():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple-list-env',
        compose_file=os.path.join(
            resource_path, 'docker-compose-simple-list-env.yml'
        ),
        compose_service_configs={
            'myapp_simple_list_env': ServiceConfig(
                envs=[Env(name='POST_MESSAGE_2', default='As below so above')],
                env_files=[EnvFile(os.path.join(resource_path, 'runtime.env'))]
            )
        },
        compose_flags=['--build']
    )
    function = docker_compose_task.to_function()
    # run with no env
    if 'ZRB_TEST_DC_TASK_SIMPLE_LIST_MESSAGE' in os.environ:
        del os.environ['ZRB_TEST_DC_TASK_SIMPLE_LIST_MESSAGE']
    result_default = function()
    assert 'Good morning' in result_default.output
    # run with env set to empty string
    os.environ['ZRB_TEST_DC_TASK_SIMPLE_LIST_MESSAGE'] = ''
    result_default = function()
    assert 'Good morning' in result_default.output
    # run with env set
    os.environ['ZRB_TEST_DC_TASK_SIMPLE_LIST_MESSAGE'] = 'Good night'
    result_custom = function()
    assert 'Good night' in result_custom.output
    del os.environ['ZRB_TEST_DC_TASK_SIMPLE_LIST_MESSAGE']

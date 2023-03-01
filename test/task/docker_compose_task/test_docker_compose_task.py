from zrb.task.docker_compose_task import DockerComposeTask

import pathlib
import os


def test_docker_compose_task_simple():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        compose_file=os.path.join(resource_path, 'docker-compose-simple.yml')
    )
    main_loop = docker_compose_task.create_main_loop()
    result = main_loop()
    assert 'Hello, Compose!' in result.output


def test_docker_compose_task_with_cwd_and_compose_file():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        cwd=resource_path,
        compose_file='docker-compose-simple.yml',
    )
    main_loop = docker_compose_task.create_main_loop()
    result = main_loop()
    assert 'Hello, Compose!' in result.output


def test_docker_compose_task_with_cwd():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        cwd=resource_path,
    )
    main_loop = docker_compose_task.create_main_loop()
    result = main_loop()
    assert 'Hello, Compose!' in result.output


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
        name='simple',
        compose_file=os.path.join(
            resource_path, 'docker-compose-simple-no-default-env.yml'
        )
    )
    main_loop = docker_compose_task.create_main_loop()
    # run with env set
    if 'ZRB_TEST_SIMPLE_NO_DEFAULT_MESSAGE' in os.environ:
        del os.environ['ZRB_TEST_SIMPLE_NO_DEFAULT_MESSAGE']
    os.environ['ZRB_TEST_SIMPLE_NO_DEFAULT_MESSAGE'] = 'Good night'
    result_default = main_loop()
    assert 'Good night' in result_default.output
    del os.environ['ZRB_TEST_SIMPLE_NO_DEFAULT_MESSAGE']


def test_docker_compose_task_simple_map_env():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        compose_file=os.path.join(
            resource_path, 'docker-compose-simple-map-env.yml'
        )
    )
    main_loop = docker_compose_task.create_main_loop()
    # run with no env
    if 'ZRB_TEST_SIMPLE_MAP_MESSAGE' in os.environ:
        del os.environ['ZRB_TEST_SIMPLE_MAP_MESSAGE']
    result_default = main_loop()
    assert 'Good morning' in result_default.output
    # run with env set to empty string
    os.environ['ZRB_TEST_SIMPLE_MAP_MESSAGE'] = ''
    result_default = main_loop()
    assert 'Good morning' in result_default.output
    # run with env set
    os.environ['ZRB_TEST_SIMPLE_MAP_MESSAGE'] = 'Good night'
    result_custom = main_loop()
    assert 'Good night' in result_custom.output
    del os.environ['ZRB_TEST_SIMPLE_MAP_MESSAGE']


def test_docker_compose_task_simple_list_env():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        compose_file=os.path.join(
            resource_path, 'docker-compose-simple-list-env.yml'
        )
    )
    main_loop = docker_compose_task.create_main_loop()
    # run with no env
    if 'ZRB_TEST_SIMPLE_LIST_MESSAGE' in os.environ:
        del os.environ['ZRB_TEST_SIMPLE_LIST_MESSAGE']
    result_default = main_loop()
    assert 'Good morning' in result_default.output
    # run with env set to empty string
    os.environ['ZRB_TEST_SIMPLE_LIST_MESSAGE'] = ''
    result_default = main_loop()
    assert 'Good morning' in result_default.output
    # run with env set
    os.environ['ZRB_TEST_SIMPLE_LIST_MESSAGE'] = 'Good night'
    result_custom = main_loop()
    assert 'Good night' in result_custom.output
    del os.environ['ZRB_TEST_SIMPLE_LIST_MESSAGE']

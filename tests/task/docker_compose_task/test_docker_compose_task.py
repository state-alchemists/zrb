from zrb.task.docker_compose_task import DockerComposeTask

import pathlib
import os


def test_docker_compose():
    dir_path = pathlib.Path(__file__).parent.absolute()
    resource_path = os.path.join(dir_path, 'resource')
    docker_compose_task = DockerComposeTask(
        name='simple',
        compose_file=os.path.join(resource_path, 'docker-compose-simple.yml')
    )
    main_loop = docker_compose_task.create_main_loop()
    result = main_loop()
    assert 'Hello, Compose!' in result.output

import os

from zrb import Scaffolder

_DIR = os.path.dirname(__file__)


def test_generate_with_basic_config():
    scaffolder = Scaffolder(
        name="scaffold",
        source_path=os.path.join(_DIR, "template"),
        destination_path=os.path.join(_DIR, "test-generated-basic"),
        transform_path={"project_name": "test_app"},
        transform_content={
            "Project Name": "Test App",
            "Project description": "A fancy test application",
        },
    )
    scaffolder.run()
    generated_dir = os.path.join(_DIR, "test-generated-basic")
    assert os.path.isdir(generated_dir)

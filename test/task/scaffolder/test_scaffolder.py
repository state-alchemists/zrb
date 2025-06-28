import os
from unittest import mock

from zrb import Scaffolder

_DIR = os.path.dirname(__file__)


@mock.patch("zrb.task.scaffolder.os.makedirs")
@mock.patch("zrb.task.scaffolder.shutil.copy2")
def test_generate_with_basic_config(mock_copy2, mock_makedirs):
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
    mock_makedirs.assert_called()
    mock_copy2.assert_called()

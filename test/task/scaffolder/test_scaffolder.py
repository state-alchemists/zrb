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


def test_generate_with_render_destination_path_false_keeps_literal_braces():
    """Regression: render_destination_path was accepted but never applied, so
    a destination containing literal `{...}` was always rendered as an
    f-string expression regardless of this flag."""
    literal_dir_name = "test-generated-{undefined_name}"
    scaffolder = Scaffolder(
        name="scaffold-no-render-dest",
        source_path=os.path.join(_DIR, "template"),
        destination_path=os.path.join(_DIR, literal_dir_name),
        render_destination_path=False,
        transform_path={"project_name": "test_app"},
        transform_content={
            "Project Name": "Test App",
            "Project description": "A fancy test application",
        },
    )
    # Would raise NameError on "undefined_name" if rendered instead of kept literal.
    scaffolder.run()
    generated_dir = os.path.join(_DIR, literal_dir_name)
    assert os.path.isdir(generated_dir)

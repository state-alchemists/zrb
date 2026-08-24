import os

from zrb import Scaffolder
from zrb.content_transformer.content_transformer import ContentTransformer

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


def _make_single_file_template(tmp_path):
    src = tmp_path / "src.txt"
    src.write_text("Hello Project Name\n")
    return str(src)


def test_generate_from_single_file_source(tmp_path):
    """A file (not a directory) source is copied and rewritten in place."""
    source = _make_single_file_template(tmp_path)
    destination = str(tmp_path / "out.txt")
    scaffolder = Scaffolder(
        name="scaffold-file",
        source_path=source,
        destination_path=destination,
        transform_path={},
        transform_content={"Project Name": "Rewritten App"},
    )
    scaffolder.run()
    assert os.path.isfile(destination)
    with open(destination) as f:
        assert f.read() == "Hello Rewritten App\n"


def test_generate_with_callable_path_transformer(tmp_path):
    """A callable transform_path rewrites copied names directly."""
    src_dir = tmp_path / "template"
    src_dir.mkdir()
    (src_dir / "placeholder.txt").write_text("data")

    scaffolder = Scaffolder(
        name="scaffold-callable-path",
        source_path=str(src_dir),
        destination_path=str(tmp_path / "generated"),
        transform_path=lambda ctx, path: path.replace("placeholder", "renamed"),
        transform_content=None,
    )
    scaffolder.run()
    assert (tmp_path / "generated" / "renamed.txt").exists()


def test_generate_with_content_transformer_object_and_list(tmp_path):
    """transform_content accepts a single ContentTransformer or a list of them."""
    src_dir = tmp_path / "template"
    src_dir.mkdir()
    (src_dir / "doc.txt").write_text("alpha beta")
    transformer_alpha = ContentTransformer(
        name="alpha",
        match="*.txt",
        transform={"alpha": "ALPHA"},
        auto_render=False,
    )
    transformer_beta = ContentTransformer(
        name="beta",
        match="*.txt",
        transform={"beta": "BETA"},
        auto_render=False,
    )

    # A single transformer object...
    single = Scaffolder(
        name="scaffold-single-transformer",
        source_path=str(src_dir),
        destination_path=str(tmp_path / "out-single"),
        transform_path={},
        transform_content=transformer_alpha,
    )
    single.run()
    assert (tmp_path / "out-single" / "doc.txt").read_text() == "ALPHA beta"

    # ...and a list of them.
    listing = Scaffolder(
        name="scaffold-list-transformer",
        source_path=str(src_dir),
        destination_path=str(tmp_path / "out-list"),
        transform_path={},
        transform_content=[transformer_alpha, transformer_beta],
    )
    listing.run()
    assert (tmp_path / "out-list" / "doc.txt").read_text() == "ALPHA BETA"


def test_generate_survives_transformer_decoding_failure(tmp_path):
    """A transformer blowing up on undecodable content doesn't crash the
    scaffold — the failure is swallowed and scaffolding continues."""
    src_dir = tmp_path / "template"
    src_dir.mkdir()
    (src_dir / "blob.bin").write_bytes(b"\x80\x81\xff\xfe")

    def raise_unicode_decode_error(ctx, file_path):
        raise UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte")

    failing_transformer = ContentTransformer(
        name="bin",
        match="*.bin",
        transform=raise_unicode_decode_error,
        auto_render=False,
    )
    scaffolder = Scaffolder(
        name="scaffold-binary",
        source_path=str(src_dir),
        destination_path=str(tmp_path / "out"),
        transform_path={},
        transform_content=failing_transformer,
    )
    scaffolder.run()  # must not raise
    assert (tmp_path / "out" / "blob.bin").exists()


def test_generate_copies_directory_tree_structure(tmp_path):
    """Nested directories are recreated under the destination."""
    src_dir = tmp_path / "template"
    nested = src_dir / "deep" / "nested"
    nested.mkdir(parents=True)
    (nested / "leaf.txt").write_text("leaf")

    scaffolder = Scaffolder(
        name="scaffold-tree",
        source_path=str(src_dir),
        destination_path=str(tmp_path / "generated"),
        transform_path={},
        transform_content=None,
    )
    scaffolder.run()
    leaf = tmp_path / "generated" / "deep" / "nested" / "leaf.txt"
    assert leaf.read_text() == "leaf"

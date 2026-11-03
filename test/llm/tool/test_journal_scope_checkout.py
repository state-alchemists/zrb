"""The tree a `file:` condition is read in, and why the answer is not cached.

Split from `test_journal_scope.py` by feature: that file is about which notes a
session sees, this one about the directory their relative paths are read from.
The two checkouts it builds are the shapes a cached answer gets wrong — a
linked worktree, and a path whose checkout was replaced under a live session.
"""

import os
import shutil
import subprocess

from zrb.llm.tool.journal_scope import repo_root


def test_the_tree_is_probed_again_when_a_checkout_is_replaced(tmp_path):
    """A re-cloned checkout at the same path is a different tree, not a cache hit.

    A session outlives a `rm -rf` and a fresh clone. A cached root would go on
    naming the tree that used to be there — the same wrong-tree comparison the
    worktree bug made — so the probe re-runs.
    """
    root = tmp_path / "project"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    assert repo_root(str(root)) == os.path.realpath(str(root))

    shutil.rmtree(root)
    root.mkdir()

    assert repo_root(str(root)) == ""

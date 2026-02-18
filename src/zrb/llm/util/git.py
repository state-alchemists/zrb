import subprocess


def is_inside_git_dir() -> bool:
    try:
        # Check if inside git repo
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except Exception:
        return False

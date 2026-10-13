from zrb.util.platform import is_wsl


def test_is_wsl_detects_distro_name(monkeypatch):
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.delenv("WSLENV", raising=False)
    assert is_wsl() is True


def test_is_wsl_detects_wslenv(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.setenv("WSLENV", "TERM/u")
    assert is_wsl() is True


def test_is_wsl_false_off_wsl(monkeypatch):
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSLENV", raising=False)
    assert is_wsl() is False

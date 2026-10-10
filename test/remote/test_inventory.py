import pytest

from zrb.remote.inventory import Host, Inventory, Target


def test_select_matches_any_label_or_name_and_empty_selects_all():
    inv: Inventory[Host] = Inventory()
    inv.add(Host("a", labels=["k8s", "prod"]), Host("b", labels=["db"]), Host("c"))
    assert [h.name for h in inv.select(["k8s", "db"])] == ["a", "b"]
    assert [h.name for h in inv.select(["c"])] == ["c"]
    assert [h.name for h in inv.select()] == ["a", "b", "c"]


def test_add_replaces_by_name_and_remove_drops():
    inv: Inventory[Host] = Inventory()
    inv.add(Host("a", labels=["x"]))
    inv.add(Host("a", labels=["y"]))
    assert [h.labels for h in inv.get_all()] == [frozenset({"y"})]
    inv.remove("a")
    assert inv.get_all() == []


def test_string_label_is_one_label_and_password_is_not_in_repr():
    host = Host("a", labels="k8s", remote_password="secret")
    assert host.labels == frozenset({"k8s"})
    assert "secret" not in repr(host)


def test_target_url_and_validation():
    t = Target("web", host="h", port=443, kind="http", scheme="https", path="/ping")
    assert t.get_url() == "https://h:443/ping"
    assert Target("w", kind="http", url="http://x/y").get_url() == "http://x/y"
    with pytest.raises(ValueError):
        Target("bad", kind="tcp")


def test_get_choices_lists_every_name_and_label_once_sorted():
    inv: Inventory[Host] = Inventory()
    inv.add(Host("a", labels=["z", "k8s"]), Host("b", labels=["k8s"]))
    assert inv.get_choices() == ["a", "b", "k8s", "z"]
    assert Inventory().get_choices() == []


def test_target_url_brackets_an_ipv6_host():
    t = Target("v6", host="2001:db8::1", port=443, kind="http", scheme="https")
    assert t.get_url() == "https://[2001:db8::1]:443/"

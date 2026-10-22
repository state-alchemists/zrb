"""A local speech service builds its model under the shared load slot (ADR-0115).

Two heavy models peaking at once is what a small machine's OOM killer picks the
chat for; one after another is survivable.
"""

import threading

from zrb.llm.speech.config import SpeechConfig
from zrb.llm.util.model_load import heavy_model_load
from zrb.llm.voice.manager import TTSServiceManager
from zrb.llm.voice.registry import TTSServiceRegistry
from zrb.llm.voice.spec import TTSServiceSpec


def _manager(factories, is_local=True):
    specs = {
        name: TTSServiceSpec(name=name, is_local=is_local, factory=factory)
        for name, factory in factories.items()
    }
    return TTSServiceManager(TTSServiceRegistry(specs))


def test_two_local_services_do_not_build_at_the_same_time():
    first_inside = threading.Event()
    release_first = threading.Event()
    second_inside = threading.Event()

    def first_factory(config):
        first_inside.set()
        release_first.wait(5)
        return "first service"

    def second_factory(config):
        second_inside.set()
        return "second service"

    manager = _manager({"first": first_factory, "second": second_factory})
    first_thread = threading.Thread(
        target=manager.create_service, args=("first", SpeechConfig())
    )
    first_thread.start()
    assert first_inside.wait(5)
    second_thread = threading.Thread(
        target=manager.create_service, args=("second", SpeechConfig())
    )
    second_thread.start()
    try:
        # The second waits for the first model to finish building.
        assert not second_inside.wait(0.2)
    finally:
        release_first.set()
        first_thread.join(5)
        second_thread.join(5)
    assert second_inside.is_set()


def test_a_remote_service_does_not_wait_for_a_local_model():
    """A voice that runs elsewhere builds a client, not a model: it has no
    reason to queue behind one."""

    def factory(config):
        return "remote service"

    manager = _manager({"cloud": factory}, is_local=False)
    built = []
    with heavy_model_load("a local model"):
        thread = threading.Thread(
            target=lambda: built.append(manager.create_service("cloud", SpeechConfig()))
        )
        thread.start()
        thread.join(1.0)
    assert not thread.is_alive()
    assert built == ["remote service"]

__version__ = "0.1.0"

from .storage import Store, default_db_path

_store = None


def get_store():
    global _store
    if _store is None:
        _store = Store()
    return _store


def instrument(store=None):
    from . import patcher

    return patcher.instrument(store or get_store())


def trace(name=None):
    from . import context

    return context.trace(get_store(), name)


__all__ = ["__version__", "Store", "default_db_path", "get_store", "instrument", "trace"]

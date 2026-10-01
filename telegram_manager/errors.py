from __future__ import annotations


def describe_error(exc: BaseException) -> str:
    """Readable reason for an exception (many have an empty str(), e.g. TimeoutError)."""
    return str(exc).strip() or exc.__class__.__name__


class AccountAlreadyConnectedError(ValueError):
    """The Telegram account being added is already connected."""

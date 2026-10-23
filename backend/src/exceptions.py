"""Custom exceptions for the Liêng Stealer system.

Every error the engine raises on purpose derives from ``LiengError``, so callers can catch the
whole family with one ``except``. Two classes also derive from a built-in, so code written against
the built-in keeps working: bad numbers are a ``ValueError``, unknown hands a ``KeyError``.
"""


class LiengError(Exception):
    """Base exception class for all Liêng engine errors."""


class InvalidCardError(LiengError):
    """Raised when card string or parameters are invalid."""


class InvalidHandSizeError(LiengError):
    """Raised when hand does not contain exactly 3 unique cards."""


class DuplicateCardError(InvalidHandSizeError):
    """Raised when the same card appears more than once in a hand."""


class InvalidGameParamsError(LiengError, ValueError):
    """Raised when pot, bet size, fold equity, or opponent model are invalid."""


class UnknownHandError(LiengError, KeyError):
    """Raised when a canonical hand ID is not one of the 455 known classes."""

    def __str__(self) -> str:
        # KeyError.__str__ quotes its argument; report the message as written instead.
        return str(self.args[0]) if self.args else ""


class DatabaseError(LiengError):
    """Base error for precomputed database operations."""


class DatabaseNotLoadedError(DatabaseError):
    """Raised when querying a database that has not been loaded."""

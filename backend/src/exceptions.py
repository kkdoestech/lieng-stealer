"""Custom exceptions for the Liêng Stealer system."""


class LiengError(Exception):
    """Base exception class for all Liêng engine errors."""
    pass


class InvalidCardError(LiengError):
    """Raised when card string or parameters are invalid."""
    pass


class InvalidHandSizeError(LiengError):
    """Raised when hand does not contain exactly 3 unique cards."""
    pass


class DatabaseError(LiengError):
    """Base error for precomputed database operations."""
    pass


class DatabaseNotLoadedError(DatabaseError):
    """Raised when querying a database that has not been loaded."""
    pass


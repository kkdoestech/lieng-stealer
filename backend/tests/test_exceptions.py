"""Pin the exception hierarchy.

Callers rely on these parents: the CLI and the API catch ``LiengError`` to report bad input, and
code written against built-ins catches ``ValueError`` / ``KeyError``. Changing a parent would not
break any other test, so this file is the safety net (weak spot M17).
"""

import pytest

from src.exceptions import (
    DatabaseError,
    DatabaseNotLoadedError,
    DuplicateCardError,
    InvalidCardError,
    InvalidGameParamsError,
    InvalidHandSizeError,
    LiengError,
    ModelError,
    UnknownHandError,
)


@pytest.mark.parametrize(
    ("error", "parents"),
    [
        (InvalidCardError, (LiengError,)),
        (InvalidHandSizeError, (LiengError,)),
        (DuplicateCardError, (InvalidHandSizeError, LiengError)),
        (InvalidGameParamsError, (LiengError, ValueError)),
        (UnknownHandError, (LiengError, KeyError)),
        (ModelError, (LiengError,)),
        (DatabaseError, (LiengError,)),
        (DatabaseNotLoadedError, (DatabaseError, LiengError)),
    ],
)
def test_exception_parents(error: type[Exception], parents: tuple[type[Exception], ...]) -> None:
    for parent in parents:
        assert issubclass(error, parent), f"{error.__name__} must derive from {parent.__name__}"


def test_unknown_hand_error_message_is_not_quoted() -> None:
    """KeyError would print "'msg'"; the subclass prints the message as written."""
    assert str(UnknownHandError("Canonical hand 'X' not found.")) == "Canonical hand 'X' not found."

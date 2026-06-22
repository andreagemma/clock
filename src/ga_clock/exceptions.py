"""Public exceptions and warnings raised by GA Clock."""

from __future__ import annotations


class GAClockError(Exception):
    """Base exception for all GA Clock errors."""


class ClockError(GAClockError, ValueError):
    """Raised when an operation is invalid for the selected clock mode."""


class GAClockWarning(UserWarning):
    """Base warning for non-fatal GA Clock conditions."""

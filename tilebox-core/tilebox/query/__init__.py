"""Shared query value types for Tilebox clients."""

from tilebox.query.id_interval import IDInterval, IDIntervalLike
from tilebox.query.pagination import Pagination
from tilebox.query.time_interval import TimeInterval, TimeIntervalLike

__all__ = ["IDInterval", "IDIntervalLike", "Pagination", "TimeInterval", "TimeIntervalLike"]

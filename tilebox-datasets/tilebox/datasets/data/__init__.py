# for backwards compatibility, we can remove this hack in the future

from warnings import warn

from tilebox.datasets.query.time_interval import TimeInterval as _TimeInterval
from tilebox.datasets.query.time_interval import TimeIntervalLike


class TimeInterval(_TimeInterval):
    def __post_init__(self) -> None:
        warn(
            "The TimeInterval class has been deprecated, import from tilebox.datasets.query instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__post_init__()

    @classmethod
    def parse(cls, arg: TimeIntervalLike) -> "_TimeInterval":
        warn(
            "The TimeInterval class has been deprecated, import from tilebox.datasets.query instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return super().parse(arg)


__all__ = ["TimeInterval"]

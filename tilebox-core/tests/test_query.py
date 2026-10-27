import subprocess
import sys


def test_shared_query_types_work_without_scientific_libraries() -> None:
    script = """
import sys
from importlib.abc import MetaPathFinder
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID
from tilebox.query import IDInterval, Pagination, TimeInterval

# Simulate a core-only installation even when pytest runs in the full workspace.
blocked = ('pandas', 'numpy', 'xarray', 'tilebox.datasets')
for name in blocked:
    assert name not in sys.modules

class MissingDependencies(MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname in blocked:
            raise ModuleNotFoundError(f'No module named {fullname!r}', name=fullname)

sys.meta_path.insert(0, MissingDependencies())

start = datetime(2026, 3, 4, 2, 30, tzinfo=timezone(timedelta(hours=2)))
end = datetime(2026, 3, 5, 1, 15)
interval = TimeInterval.parse((start, end))
assert interval.start == datetime(2026, 3, 4, 0, 30, tzinfo=UTC)
assert interval.end == datetime(2026, 3, 5, 1, 15, tzinfo=UTC)
assert not interval.start_exclusive and not interval.end_inclusive
assert TimeInterval.from_message(interval.to_message()) == interval
instant = TimeInterval.parse(start)
assert instant.start == interval.start == instant.end
assert instant.end_inclusive
assert TimeInterval.parse(interval) is interval
ids = IDInterval.parse((UUID(int=1), UUID(int=9)))
assert IDInterval.from_message(ids.to_message()) == ids
page = Pagination(limit=7, starting_after=UUID(int=3))
assert Pagination.from_message(page.to_message()) == page

for value in ('2026-01-01', ('2026-01-01', '2026-01-02')):
    try:
        TimeInterval.parse(value)
    except ImportError as error:
        assert 'Install pandas or pass Python datetime objects' in str(error)
    else:
        raise AssertionError('String parsing should explain the missing pandas dependency')
"""
    subprocess.run([sys.executable, "-c", script], check=True)  # noqa: S603

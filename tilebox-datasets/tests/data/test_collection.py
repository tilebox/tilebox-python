from hypothesis import assume, given

from tests.data.collection import collection_infos, collections
from tilebox.datasets.data.collection import Collection, CollectionInfo
from tilebox.datasets.data.time_interval import _EMPTY_TIME_INTERVAL


@given(collections())
def test_collections_to_message_and_back(collection: Collection) -> None:
    assert Collection.from_message(collection.to_message()) == collection


@given(collection_infos())
def test_collection_infos_to_message_and_back(info: CollectionInfo) -> None:
    assert CollectionInfo.from_message(info.to_message()) == info


@given(collection_infos())
def test_collection_infos_repr(info: CollectionInfo) -> None:
    for r in (repr(info), str(info)):
        assert info.collection.name in r

        # make sure we hide the collection id in the repr
        assume(info.collection.id not in info.collection.name)  # otherwise id would be in repr
        assert info.collection.id not in r, "collection id should not be in repr"

        if info.availability is None:
            assert "unknown" in r
        elif info.availability == _EMPTY_TIME_INTERVAL:
            assert "empty" in r
        else:
            assert repr(info.availability) in r
        if info.count is None:
            assert "data points" not in r
        else:
            assert f"{info.count} data points" in r

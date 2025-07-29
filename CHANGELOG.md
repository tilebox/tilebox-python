# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.40.0] - 2025-07-29

### Added

- Added `NetworkError` and `NetworkTimeoutError` exceptions classes to indicate network related errors in grpc calls.

### Changed

- Dropped support for `protobuf v5` and below, minimum supported version is now `protobuf>=6`.

### Fixed

- `tilebox-workflows`: Fix opentelemetry logging and tracing initialization on Windows, which was relying on `os.uname`,
  a stdlib function that does not exist on Windows python SDKs.

## [0.39.0] - 2025-07-16

### Added

- `tilebox-workflows`: Added `cancel_jobs` argument to `AutomationClient.delete` to optionally cancel all currently queued or running jobs of the automation.

### Changed

- `tilebox-datasets`: Changed `TimeInterval` and `TimeIntervalLike` imports from `tilebox.datasets.data` to `tilebox.datasets.query`.

## [0.38.0] - 2025-06-24

### Added

- `tilebox-datasets`: Added `delete_collection` method to `DatasetClient` to delete a collection.
- `tilebox-workflows`: Added support for nested dataclasses and protobuf messages inside a `list`, `dict` or `tuple`
  as task arguments.

## [0.37.1] - 2025-06-10

### Fixed

- `tilebox-datasets`: Fixed a bug in `TimeseriesDatasetChunk.from_message` relying on incorrect bool assumptions about
  missing protobuf fields.
- `tilebox-grpc`: More robust parsing of GRPC channel URLs.
- `tilebox-workflows`: Fixed a bug in the timeseries interceptor that resulted in an error when accessing a collection.

## [0.37.0] - 2025-06-06

### Changed

- Dropped support for legacy Tilebox datasets, no longer necessary since all datasets have been migrated on the server.

## [0.36.1] - 2025-06-04

### Changed

- Changed the `runner` method of the `Client` to take an optional `cluster` argument. If not provided, the default cluster will be used.
- Changed the `create_cron_automation` and `create_storage_event_automation` methods of the `AutomationClient` to take an optional `cluster` argument. If not provided, the default cluster will be used.
- Changed the `submit` method of the `JobClient` to take an optional `cluster` argument. If not provided, the default cluster will be used.

## [0.36.0] - 2025-05-27

## Added

- Added `query` method to `JobClient` to query jobs in a given temporal extent and filter by automation id

## [0.35.0] - 2025-04-29

## Added

- Support for ingestion of enum values into datasets
- Pagination support for ingestion / deletion of large numbers of datapoints

## Changed

- Renamed `TimeseriesDataset` to `DatasetClient`
- Renamed `TimeseriesCollection` to `CollectionClient`

## [0.34.0] - 2025-04-15

## Added

- Added spatial-query support via new `query` method in `TimeseriesDatasetCollection`
- Added `submit_subtasks` method to `TaskRunner`
- Added deprecation warning for `submit_batch` method to `TaskRunner`

## [0.33.1] - 2025-04-01

### Changed

- Replaced Job field `completed` by `state`

## [0.33.0] - 2025-03-21

### Added

- Support for custom datasets
- `collection.ingest` method to ingest data into a collection
  - ingest takes data in the form of either a `xarray.Dataset`, a `pandas.DataFrame` or a dictionary of Iterables
    (which will be converted to a `pandas.DataFrame` using its constructor)
- `collection.delete` method to delete datapoints from a collection

## [0.32.1] - 2025-03-11

### Changed

- Update protobuf due to server side refactoring

## [0.32.0] - 2025-03-11

### Added

- Add `get_or_create_collection` and `create_collection` method to timeseries dataset
- Added deprecation warning for `availability` and `count` for collection info
- Add dataset_type protobuf files

## [0.31.0] - 2025-02-12

### Added

- Added `list_objects` method to storage clients to list available objects for a given datapoint.
- Added `download_objects` method to storage clients to download a subset of the available objects for a given datapoint.

## [0.30.2] - 2025-01-27

### Changed

- Renamed recurrent tasks to automations.

## [0.30.1] - 2025-01-10

### Added

- Added `_load_page` method to `TimeseriesCollection` to easily allow individual pages, allowing to not do auto-pagination for use cases where it is not needed.
- Added docstrings to the dataset client constructors.

## [0.30.0] - 2024-11-29

### Changed

- Removed `async` API for `tilebox-workflows`.
- Changed argument order of create recurrent task methods to be consistent with the job client.

## [0.29.0] - 2024-11-14

### Added

- Added support for Python `3.12` and `3.13`

### Fixed

- `tilebox-grpc`: Fixed a dependency version error resulting in an outdated version of the package being installed by `pip` by default.
- `tilebox-workflows`: Fixed a bug where `grpc` errors were not wrapped in Tilebox Python exceptions.

## [0.28.0] - 2024-10-12

### Added

- Added `SubscriptionLimitExceededError` error to indicate subscription rate limiting related errors.

### Changed

- `client.dataset` method of the datasets client now takes a dataset slug instead of an id as input argument
- Changed default value of `count` for the `collection.info` method to `True`, since it's no longer an expensive operation

## [0.27.2] - 2024-10-05

### Added

- Added `format` method to `TimeInterval` to format the interval as a string with custom precision and with or without the endpoint chars.

### Fixed

- `tilebox-workflows`: Fixed a bug where the root logger was not set to DEBUG level, which would cause all DEBUG messages to be discarded.

## [0.27.1] - 2024-10-04

### Fixed

- Properly offload datapoint parsing to a background thread during `load` in the async client.
- Progress callbacks during `load` are now always done from the main thread in the sync client.
  This resolves an issue when using it in `streamlit` to update a progress bar, since interacting with
  streamlit widgets from a background thread is not allowed without setting some streamlit context in the background
  thread.
- Accept any return type for show_progress callbacks in `load`

## [0.27.0] - 2024-10-02

### Changed

- Refactored timeseries dataset to a proper sync / async client containing correct types.

## [0.26.0] - 2024-09-30

### Added

- Create collection RPC stub and service method
- Ingest and delete datapoints RPC stubs and service methods
- Configure a default console logger if `get_logger()` is called without any configured loggers.
- Callback function for reporting progress percentage for timeseries datasets `.load()` method.

### Changed

- Updated TimeInterval and TimeChunk tasks to use protobuf messages from datasets package.

## [0.25.1] - 2024-09-12

### Added

- Added descriptions for the pypi.org pages of the packages.

## [0.25.0] - 2024-08-12

### Added

- Initial version of the tilebox python library
- Released under the [MIT](https://opensource.org/license/mit) license.
- Released packages: `tilebox-datasets`, `tilebox-workflows`, `tilebox-storage`, `tilebox-grpc`


[Unreleased]: https://github.com/tilebox/tilebox-python/compare/v0.40.0...HEAD
[0.40.0]: https://github.com/tilebox/tilebox-python/compare/v0.39.0...v0.40.0
[0.39.0]: https://github.com/tilebox/tilebox-python/compare/v0.38.0...v0.39.0
[0.38.0]: https://github.com/tilebox/tilebox-python/compare/v0.37.1...v0.38.0
[0.37.1]: https://github.com/tilebox/tilebox-python/compare/v0.37.0...v0.37.1
[0.37.0]: https://github.com/tilebox/tilebox-python/compare/v0.36.1...v0.37.0
[0.36.1]: https://github.com/tilebox/tilebox-python/compare/v0.36.0...v0.36.1
[0.36.0]: https://github.com/tilebox/tilebox-python/compare/v0.35.0...v0.36.0
[0.35.0]: https://github.com/tilebox/tilebox-python/compare/v0.34.0...v0.35.0
[0.34.0]: https://github.com/tilebox/tilebox-python/compare/v0.33.1...v0.34.0
[0.33.1]: https://github.com/tilebox/tilebox-python/compare/v0.33.0...v0.33.1
[0.33.0]: https://github.com/tilebox/tilebox-python/compare/v0.32.1...v0.33.0
[0.32.1]: https://github.com/tilebox/tilebox-python/compare/v0.32.0...v0.32.1
[0.32.0]: https://github.com/tilebox/tilebox-python/compare/v0.31.0...v0.32.0
[0.31.0]: https://github.com/tilebox/tilebox-python/compare/v0.30.2...v0.31.0
[0.30.2]: https://github.com/tilebox/tilebox-python/compare/v0.30.1...v0.30.2
[0.30.1]: https://github.com/tilebox/tilebox-python/compare/v0.30.0...v0.30.1
[0.30.0]: https://github.com/tilebox/tilebox-python/compare/v0.29.0...v0.30.0
[0.29.0]: https://github.com/tilebox/tilebox-python/compare/v0.28.0...v0.29.0
[0.28.0]: https://github.com/tilebox/tilebox-python/compare/v0.27.2...v0.28.0
[0.27.2]: https://github.com/tilebox/tilebox-python/compare/v0.27.1...v0.27.2
[0.27.1]: https://github.com/tilebox/tilebox-python/compare/v0.27.0...v0.27.1
[0.27.0]: https://github.com/tilebox/tilebox-python/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/tilebox/tilebox-python/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/tilebox/tilebox-python/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/tilebox/tilebox-python/releases/tag/v0.25.0

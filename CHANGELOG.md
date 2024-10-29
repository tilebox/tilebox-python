# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Changed collection.info count default value to True

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


[Unreleased]: https://github.com/tilebox/tilebox-python/compare/v0.27.2...HEAD
[0.27.2]: https://github.com/tilebox/tilebox-python/compare/v0.27.1...v0.27.2
[0.27.1]: https://github.com/tilebox/tilebox-python/compare/v0.27.0...v0.27.1
[0.27.0]: https://github.com/tilebox/tilebox-python/compare/v0.26.0...v0.27.0
[0.26.0]: https://github.com/tilebox/tilebox-python/compare/v0.25.1...v0.26.0
[0.25.1]: https://github.com/tilebox/tilebox-python/compare/v0.25.0...v0.25.1
[0.25.0]: https://github.com/tilebox/tilebox-python/releases/tag/v0.25.0

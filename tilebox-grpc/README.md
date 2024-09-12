# Tilebox GRPC

![PyPI - Version](https://img.shields.io/pypi/v/tilebox-grpc.svg?style=flat-square&label=version&color=f43f5e)
![Python](https://img.shields.io/pypi/pyversions/tilebox-grpc.svg?style=flat-square&logo=python&color=f43f5e&logoColor=f43f5e)

GRPC and Protobuf related functionality used by Tilebox python packages.

## Quickstart

Install using `pip`:

```bash
pip install tilebox-grpc
```

Open a gRPC channel:

```python
from _tilebox.grpc.channel import open_channel

channel = open_channel(
    "https://api.tilebox.com",
    auth_token="YOUR_TILEBOX_API_KEY"
)
```

## License

Distributed under the MIT License (`The MIT License`).

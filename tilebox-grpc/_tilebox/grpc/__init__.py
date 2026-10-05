import os

# Suppress native gRPC fork-log spam while preserving explicit user settings.
# Remove once our minimum grpcio version resolves https://github.com/grpc/grpc/issues/42293.
# This must run before gRPC initializes; it also affects other Abseil-based native logging.
os.environ.setdefault("GRPC_VERBOSITY", "ERROR")

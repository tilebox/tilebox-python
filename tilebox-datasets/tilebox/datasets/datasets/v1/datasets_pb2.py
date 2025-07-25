# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: datasets/v1/datasets.proto
# Protobuf Python Version: 5.29.3
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    3,
    '',
    'datasets/v1/datasets.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from tilebox.datasets.buf.validate import validate_pb2 as buf_dot_validate_dot_validate__pb2
from tilebox.datasets.datasets.v1 import core_pb2 as datasets_dot_v1_dot_core__pb2
from tilebox.datasets.datasets.v1 import dataset_type_pb2 as datasets_dot_v1_dot_dataset__type__pb2
from tilebox.datasets.tilebox.v1 import id_pb2 as tilebox_dot_v1_dot_id__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x1a\x64\x61tasets/v1/datasets.proto\x12\x0b\x64\x61tasets.v1\x1a\x1b\x62uf/validate/validate.proto\x1a\x16\x64\x61tasets/v1/core.proto\x1a\x1e\x64\x61tasets/v1/dataset_type.proto\x1a\x13tilebox/v1/id.proto\"\xb2\x01\n\x14\x43reateDatasetRequest\x12\x1b\n\x04name\x18\x01 \x01(\tB\x07\xbaH\x04r\x02\x10\x01R\x04name\x12\x34\n\x04type\x18\x02 \x01(\x0b\x32\x18.datasets.v1.DatasetTypeB\x06\xbaH\x03\xc8\x01\x01R\x04type\x12!\n\x07summary\x18\x03 \x01(\tB\x07\xbaH\x04r\x02\x10\x01R\x07summary\x12$\n\tcode_name\x18\x04 \x01(\tB\x07\xbaH\x04r\x02\x10\x01R\x08\x63odeName\"~\n\x11GetDatasetRequest\x12\x36\n\x04slug\x18\x01 \x01(\tB\"\xbaH\x1fr\x1d\x32\x1b^[a-z0-9_]+(\\.[a-z0-9_]+)+$R\x04slug\x12\x1e\n\x02id\x18\x02 \x01(\x0b\x32\x0e.tilebox.v1.IDR\x02id:\x11\xbaH\x0e\"\x0c\n\x04slug\n\x02id\x10\x01\"\xb4\x01\n\x14UpdateDatasetRequest\x12&\n\x02id\x18\x01 \x01(\x0b\x32\x0e.tilebox.v1.IDB\x06\xbaH\x03\xc8\x01\x01R\x02id\x12\x1b\n\x04name\x18\x02 \x01(\tB\x07\xbaH\x04r\x02\x10\x01R\x04name\x12\x34\n\x04type\x18\x03 \x01(\x0b\x32\x18.datasets.v1.DatasetTypeB\x06\xbaH\x03\xc8\x01\x01R\x04type\x12!\n\x07summary\x18\x04 \x01(\tB\x07\xbaH\x04r\x02\x10\x01R\x07summary\"t\n\nClientInfo\x12\x12\n\x04name\x18\x01 \x01(\tR\x04name\x12 \n\x0b\x65nvironment\x18\x02 \x01(\tR\x0b\x65nvironment\x12\x30\n\x08packages\x18\x03 \x03(\x0b\x32\x14.datasets.v1.PackageR\x08packages\"7\n\x07Package\x12\x12\n\x04name\x18\x01 \x01(\tR\x04name\x12\x18\n\x07version\x18\x02 \x01(\tR\x07version\"k\n\x1fUpdateDatasetDescriptionRequest\x12&\n\x02id\x18\x01 \x01(\x0b\x32\x0e.tilebox.v1.IDB\x06\xbaH\x03\xc8\x01\x01R\x02id\x12 \n\x0b\x64\x65scription\x18\x02 \x01(\tR\x0b\x64\x65scription\">\n\x14\x44\x65leteDatasetRequest\x12&\n\x02id\x18\x01 \x01(\x0b\x32\x0e.tilebox.v1.IDB\x06\xbaH\x03\xc8\x01\x01R\x02id\"1\n\x15\x44\x65leteDatasetResponse\x12\x18\n\x07trashed\x18\x01 \x01(\x08R\x07trashed\"O\n\x13ListDatasetsRequest\x12\x38\n\x0b\x63lient_info\x18\x01 \x01(\x0b\x32\x17.datasets.v1.ClientInfoR\nclientInfo\"\x86\x02\n\x14ListDatasetsResponse\x12\x30\n\x08\x64\x61tasets\x18\x01 \x03(\x0b\x32\x14.datasets.v1.DatasetR\x08\x64\x61tasets\x12\x31\n\x06groups\x18\x02 \x03(\x0b\x32\x19.datasets.v1.DatasetGroupR\x06groups\x12%\n\x0eserver_message\x18\x03 \x01(\tR\rserverMessage\x12%\n\x0eowned_datasets\x18\x04 \x01(\x03R\rownedDatasets\x12;\n\x16maximum_owned_datasets\x18\x05 \x01(\x03\x42\x05\xaa\x01\x02\x08\x01R\x14maximumOwnedDatasets2\x81\x04\n\x0e\x44\x61tasetService\x12J\n\rCreateDataset\x12!.datasets.v1.CreateDatasetRequest\x1a\x14.datasets.v1.Dataset\"\x00\x12\x44\n\nGetDataset\x12\x1e.datasets.v1.GetDatasetRequest\x1a\x14.datasets.v1.Dataset\"\x00\x12J\n\rUpdateDataset\x12!.datasets.v1.UpdateDatasetRequest\x1a\x14.datasets.v1.Dataset\"\x00\x12`\n\x18UpdateDatasetDescription\x12,.datasets.v1.UpdateDatasetDescriptionRequest\x1a\x14.datasets.v1.Dataset\"\x00\x12X\n\rDeleteDataset\x12!.datasets.v1.DeleteDatasetRequest\x1a\".datasets.v1.DeleteDatasetResponse\"\x00\x12U\n\x0cListDatasets\x12 .datasets.v1.ListDatasetsRequest\x1a!.datasets.v1.ListDatasetsResponse\"\x00\x42r\n\x0f\x63om.datasets.v1B\rDatasetsProtoP\x01\xa2\x02\x03\x44XX\xaa\x02\x0b\x44\x61tasets.V1\xca\x02\x0b\x44\x61tasets\\V1\xe2\x02\x17\x44\x61tasets\\V1\\GPBMetadata\xea\x02\x0c\x44\x61tasets::V1\x92\x03\x02\x08\x02\x62\x08\x65\x64itionsp\xe8\x07')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'datasets.v1.datasets_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  _globals['DESCRIPTOR']._loaded_options = None
  _globals['DESCRIPTOR']._serialized_options = b'\n\017com.datasets.v1B\rDatasetsProtoP\001\242\002\003DXX\252\002\013Datasets.V1\312\002\013Datasets\\V1\342\002\027Datasets\\V1\\GPBMetadata\352\002\014Datasets::V1\222\003\002\010\002'
  _globals['_CREATEDATASETREQUEST'].fields_by_name['name']._loaded_options = None
  _globals['_CREATEDATASETREQUEST'].fields_by_name['name']._serialized_options = b'\272H\004r\002\020\001'
  _globals['_CREATEDATASETREQUEST'].fields_by_name['type']._loaded_options = None
  _globals['_CREATEDATASETREQUEST'].fields_by_name['type']._serialized_options = b'\272H\003\310\001\001'
  _globals['_CREATEDATASETREQUEST'].fields_by_name['summary']._loaded_options = None
  _globals['_CREATEDATASETREQUEST'].fields_by_name['summary']._serialized_options = b'\272H\004r\002\020\001'
  _globals['_CREATEDATASETREQUEST'].fields_by_name['code_name']._loaded_options = None
  _globals['_CREATEDATASETREQUEST'].fields_by_name['code_name']._serialized_options = b'\272H\004r\002\020\001'
  _globals['_GETDATASETREQUEST'].fields_by_name['slug']._loaded_options = None
  _globals['_GETDATASETREQUEST'].fields_by_name['slug']._serialized_options = b'\272H\037r\0352\033^[a-z0-9_]+(\\.[a-z0-9_]+)+$'
  _globals['_GETDATASETREQUEST']._loaded_options = None
  _globals['_GETDATASETREQUEST']._serialized_options = b'\272H\016\"\014\n\004slug\n\002id\020\001'
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['id']._loaded_options = None
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['id']._serialized_options = b'\272H\003\310\001\001'
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['name']._loaded_options = None
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['name']._serialized_options = b'\272H\004r\002\020\001'
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['type']._loaded_options = None
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['type']._serialized_options = b'\272H\003\310\001\001'
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['summary']._loaded_options = None
  _globals['_UPDATEDATASETREQUEST'].fields_by_name['summary']._serialized_options = b'\272H\004r\002\020\001'
  _globals['_UPDATEDATASETDESCRIPTIONREQUEST'].fields_by_name['id']._loaded_options = None
  _globals['_UPDATEDATASETDESCRIPTIONREQUEST'].fields_by_name['id']._serialized_options = b'\272H\003\310\001\001'
  _globals['_DELETEDATASETREQUEST'].fields_by_name['id']._loaded_options = None
  _globals['_DELETEDATASETREQUEST'].fields_by_name['id']._serialized_options = b'\272H\003\310\001\001'
  _globals['_LISTDATASETSRESPONSE'].fields_by_name['maximum_owned_datasets']._loaded_options = None
  _globals['_LISTDATASETSRESPONSE'].fields_by_name['maximum_owned_datasets']._serialized_options = b'\252\001\002\010\001'
  _globals['_CREATEDATASETREQUEST']._serialized_start=150
  _globals['_CREATEDATASETREQUEST']._serialized_end=328
  _globals['_GETDATASETREQUEST']._serialized_start=330
  _globals['_GETDATASETREQUEST']._serialized_end=456
  _globals['_UPDATEDATASETREQUEST']._serialized_start=459
  _globals['_UPDATEDATASETREQUEST']._serialized_end=639
  _globals['_CLIENTINFO']._serialized_start=641
  _globals['_CLIENTINFO']._serialized_end=757
  _globals['_PACKAGE']._serialized_start=759
  _globals['_PACKAGE']._serialized_end=814
  _globals['_UPDATEDATASETDESCRIPTIONREQUEST']._serialized_start=816
  _globals['_UPDATEDATASETDESCRIPTIONREQUEST']._serialized_end=923
  _globals['_DELETEDATASETREQUEST']._serialized_start=925
  _globals['_DELETEDATASETREQUEST']._serialized_end=987
  _globals['_DELETEDATASETRESPONSE']._serialized_start=989
  _globals['_DELETEDATASETRESPONSE']._serialized_end=1038
  _globals['_LISTDATASETSREQUEST']._serialized_start=1040
  _globals['_LISTDATASETSREQUEST']._serialized_end=1119
  _globals['_LISTDATASETSRESPONSE']._serialized_start=1122
  _globals['_LISTDATASETSRESPONSE']._serialized_end=1384
  _globals['_DATASETSERVICE']._serialized_start=1387
  _globals['_DATASETSERVICE']._serialized_end=1900
# @@protoc_insertion_point(module_scope)

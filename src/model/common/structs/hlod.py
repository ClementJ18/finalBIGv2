# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import logging
from model.w3d.io_binary import (
    LARGE_STRING_LENGTH,
    read_chunk_head,
    read_fixed_string,
    read_float,
    read_long_fixed_string,
    read_ulong,
)
from model.w3d.structs.version import Version
from model.w3d.utils.helpers import const_size, list_size, skip_unknown_chunk

W3D_CHUNK_HLOD_HEADER = 0x00000701


class HLodHeader:
    def __init__(
        self, version=Version(major=1, minor=0), lod_count=1, model_name="", hierarchy_name=""
    ):
        self.version = version
        self.lod_count = lod_count
        self.model_name = model_name
        self.hierarchy_name = hierarchy_name

    @staticmethod
    def read(io_stream):
        return HLodHeader(
            version=Version.read(io_stream),
            lod_count=read_ulong(io_stream),
            model_name=read_fixed_string(io_stream),
            hierarchy_name=read_fixed_string(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(40, include_head)


W3D_CHUNK_HLOD_SUB_OBJECT_ARRAY_HEADER = 0x00000703

MAX_SCREEN_SIZE = 340282346638528859811704183484516925440.000000


class HLodArrayHeader:
    def __init__(self, model_count=0, max_screen_size=MAX_SCREEN_SIZE):
        self.model_count = model_count
        self.max_screen_size = max_screen_size

    @staticmethod
    def read(io_stream):
        return HLodArrayHeader(
            model_count=read_ulong(io_stream), max_screen_size=read_float(io_stream)
        )

    @staticmethod
    def size(include_head=True):
        return const_size(8, include_head)


W3D_CHUNK_HLOD_SUB_OBJECT = 0x00000704


class HLodSubObject:
    def __init__(self, bone_index=0, identifier="", name="", is_box=False):
        self.bone_index = bone_index
        self.identifier = identifier
        self.name = name

        # non struct properties
        self.is_box = is_box

    @staticmethod
    def read(io_stream):
        sub_obj = HLodSubObject(
            bone_index=read_ulong(io_stream), identifier=read_long_fixed_string(io_stream)
        )

        sub_obj.name = sub_obj.identifier.split(".", 1)[-1]
        return sub_obj

    @staticmethod
    def size(include_head=True):
        return const_size(36, include_head)


class HLodBaseArray:
    def __init__(self, header=None, sub_objects=None):
        self.header = header
        self.sub_objects = sub_objects if sub_objects is not None else []

    @staticmethod
    def read_base(io_stream, chunk_end, array):
        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, _) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_HLOD_SUB_OBJECT_ARRAY_HEADER:
                array.header = HLodArrayHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_HLOD_SUB_OBJECT:
                array.sub_objects.append(HLodSubObject.read(io_stream))
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return array

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        size += list_size(self.sub_objects, False)
        return size


W3D_CHUNK_HLOD_LOD_ARRAY = 0x00000702


class HLodLodArray(HLodBaseArray):
    @staticmethod
    def read(io_stream, chunk_end):
        return HLodBaseArray.read_base(io_stream, chunk_end, HLodLodArray())


W3D_CHUNK_HLOD_AGGREGATE_ARRAY = 0x00000705


class HLodAggregateArray(HLodBaseArray):
    @staticmethod
    def read(io_stream, chunk_end):
        return HLodBaseArray.read_base(io_stream, chunk_end, HLodAggregateArray())


W3D_CHUNK_HLOD_PROXY_ARRAY = 0x00000706


class HLodProxyArray(HLodBaseArray):
    @staticmethod
    def read(io_stream, chunk_end):
        return HLodBaseArray.read_base(io_stream, chunk_end, HLodProxyArray())


W3D_CHUNK_HLOD = 0x00000700


class HLod:
    def __init__(self, header=None, lod_arrays=None, aggregate_array=None, proxy_array=None):
        self.header = header
        self.lod_arrays = lod_arrays if lod_arrays is not None else []
        self.aggregate_array = aggregate_array
        self.proxy_array = proxy_array

    def model_name(self):
        return self.header.model_name

    def hierarchy_name(self):
        return self.header.hierarchy_name

    def validate(self, context):
        if context.file_format == "W3X":
            return True
        for lod_array in self.lod_arrays:
            for sub_obj in lod_array.sub_objects:
                if len(sub_obj.identifier) >= LARGE_STRING_LENGTH:
                    logging.error(
                        f"identifier '{sub_obj.identifier}' exceeds max length of {LARGE_STRING_LENGTH}"
                    )
                    return False
        return True

    @staticmethod
    def read(io_stream, chunk_end):
        result = HLod()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_HLOD_HEADER:
                result.header = HLodHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_HLOD_LOD_ARRAY:
                result.lod_arrays.append(HLodLodArray.read(io_stream, subchunk_end))
            elif chunk_type == W3D_CHUNK_HLOD_AGGREGATE_ARRAY:
                result.aggregate_array = HLodAggregateArray.read(io_stream, subchunk_end)
            elif chunk_type == W3D_CHUNK_HLOD_PROXY_ARRAY:
                result.proxy_array = HLodProxyArray.read(io_stream, subchunk_end)
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        for lod_array in self.lod_arrays:
            size += lod_array.size()
        if self.aggregate_array is not None:
            size += self.aggregate_array.size()
        if self.proxy_array is not None:
            size += self.proxy_array.size()
        return size

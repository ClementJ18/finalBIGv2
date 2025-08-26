# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import logging

from model.w3d.io_binary import (
    STRING_LENGTH,
    Vector,
    read_chunk_head,
    read_fixed_string,
    read_list,
    read_long,
    read_quaternion,
    read_ulong,
    read_vector,
)
from model.w3d.structs.version import Version
from model.w3d.utils.helpers import const_size, list_size, skip_unknown_chunk, vec_list_size

W3D_CHUNK_HIERARCHY_HEADER = 0x00000101


class HierarchyHeader:
    def __init__(
        self,
        version=Version(major=4, minor=1),
        name="",
        num_pivots=0,
        center_pos=Vector((0.0, 0.0, 0.0)),
    ):
        self.version = version
        self.name = name
        self.num_pivots = num_pivots
        self.center_pos = center_pos

    @staticmethod
    def read(io_stream):
        return HierarchyHeader(
            version=Version.read(io_stream),
            name=read_fixed_string(io_stream),
            num_pivots=read_ulong(io_stream),
            center_pos=read_vector(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(36, include_head)


class HierarchyPivot:
    def __init__(
        self,
        name="",
        name_id=None,
        parent_id=-1,
        translation=Vector(),
        euler_angles=Vector(),
        rotation=None,
        fixup_matrix=None,
    ):
        self.name = name
        self.name_id = name_id
        self.parent_id = parent_id
        self.translation = translation
        self.euler_angles = euler_angles
        self.rotation = rotation
        self.fixup_matrix = fixup_matrix

    @staticmethod
    def read(io_stream):
        return HierarchyPivot(
            name=read_fixed_string(io_stream),
            parent_id=read_long(io_stream),
            translation=read_vector(io_stream),
            euler_angles=read_vector(io_stream),
            rotation=read_quaternion(io_stream),
        )

    @staticmethod
    def size():
        return 60


W3D_CHUNK_HIERARCHY = 0x00000100
W3D_CHUNK_PIVOTS = 0x00000102
W3D_CHUNK_PIVOT_FIXUPS = 0x00000103


class Hierarchy:
    def __init__(self, header=None, pivots=None, pivot_fixups=None):
        self.header = header
        self.pivots = pivots if pivots is not None else []
        self.pivot_fixups = pivot_fixups if pivot_fixups is not None else []

    def name(self):
        return self.header.name

    def validate(self, context):
        if context.file_format == "W3X":
            return True
        if len(self.header.name) >= STRING_LENGTH:
            logging.error(
                f"armature name '{self.header.name}' exceeds max length of {STRING_LENGTH}"
            )
            return False
        for pivot in self.pivots:
            if len(pivot.name) >= STRING_LENGTH:
                logging.error(
                    f"name of object '{pivot.name}' exceeds max length of {STRING_LENGTH}"
                )
                return False
        return True

    @staticmethod
    def read(io_stream, chunk_end):
        result = Hierarchy()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_HIERARCHY_HEADER:
                result.header = HierarchyHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_PIVOTS:
                result.pivots = read_list(io_stream, subchunk_end, HierarchyPivot.read)
            elif chunk_type == W3D_CHUNK_PIVOT_FIXUPS:
                result.pivot_fixups = read_list(io_stream, subchunk_end, read_vector)
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        size += list_size(self.pivots)
        size += vec_list_size(self.pivot_fixups)
        return size

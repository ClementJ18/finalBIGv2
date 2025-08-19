# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import logging

from model.w3d.io_binary import (
    STRING_LENGTH,
    read_chunk_head,
    read_fixed_list,
    read_fixed_string,
    read_float,
    read_quaternion,
    read_ubyte,
    read_ulong,
    read_ushort,
)
from model.w3d.structs.version import Version
from model.w3d.utils.helpers import const_size, list_size, skip_unknown_chunk

W3D_CHUNK_ANIMATION_HEADER = 0x00000201

CHANNEL_X = 0
CHANNEL_Y = 1
CHANNEL_Z = 2
CHANNEL_Q = 6
CHANNEL_VIS = 15


class AnimationHeader:
    def __init__(
        self,
        version=Version(major=4, minor=1),
        name="",
        hierarchy_name="",
        num_frames=0,
        frame_rate=0,
    ):
        self.version = version
        self.name = name
        self.hierarchy_name = hierarchy_name
        self.num_frames = num_frames
        self.frame_rate = frame_rate

    @staticmethod
    def read(io_stream):
        return AnimationHeader(
            version=Version.read(io_stream),
            name=read_fixed_string(io_stream),
            hierarchy_name=read_fixed_string(io_stream),
            num_frames=read_ulong(io_stream),
            frame_rate=read_ulong(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(44, include_head)


W3D_CHUNK_ANIMATION_CHANNEL = 0x00000202


class AnimationChannel:
    def __init__(
        self, first_frame=0, last_frame=0, vector_len=1, type=0, pivot=0, unknown=0, data=None
    ):
        self.first_frame = first_frame
        self.last_frame = last_frame
        self.vector_len = vector_len
        self.type = type
        self.pivot = pivot
        self.unknown = unknown
        self.data = data if data is not None else []
        self.pad_bytes = []

    @staticmethod
    def read(io_stream, chunk_end):
        result = AnimationChannel(
            first_frame=read_ushort(io_stream),
            last_frame=read_ushort(io_stream),
            vector_len=read_ushort(io_stream),
            type=read_ushort(io_stream),
            pivot=read_ushort(io_stream),
            unknown=read_ushort(io_stream),
        )

        num_elements = result.last_frame - result.first_frame + 1

        if result.vector_len == 1:
            result.data = read_fixed_list(io_stream, num_elements, read_float)
        else:
            result.data = read_fixed_list(io_stream, num_elements, read_quaternion)

        while io_stream.tell() < chunk_end:
            result.pad_bytes.append(read_ubyte(io_stream))
        return result

    def size(self, include_head=True):
        size = const_size(12, include_head)
        size += (len(self.data) * self.vector_len) * 4
        size += len(self.pad_bytes)
        return size


W3D_CHUNK_ANIMATION_BIT_CHANNEL = 0x00000203


class AnimationBitChannel:
    def __init__(self, first_frame=0, last_frame=0, type=0, pivot=0, default=1.0, data=None):
        self.first_frame = first_frame
        self.last_frame = last_frame
        self.type = type
        self.pivot = pivot
        self.default = default
        self.data = data if data is not None else []

    @staticmethod
    def read(io_stream):
        result = AnimationBitChannel(
            first_frame=read_ushort(io_stream),
            last_frame=read_ushort(io_stream),
            type=read_ushort(io_stream),
            pivot=read_ushort(io_stream),
            default=float(read_ubyte(io_stream) / 255),
        )

        num_frames = result.last_frame - result.first_frame + 1
        result.data = [float] * num_frames
        temp = 0
        for i in range(num_frames):
            if i % 8 == 0:
                temp = read_ubyte(io_stream)
            val = (temp & (1 << (i % 8))) != 0
            result.data[i] = val
        return result

    def size(self, include_head=True):
        size = const_size(9, include_head)
        size += int(len(self.data) / 8)
        if len(self.data) % 8 > 0:
            size += 1
        return size


W3D_CHUNK_ANIMATION = 0x00000200


class Animation:
    def __init__(self, header=None, channels=None):
        self.header = header
        self.channels = channels if channels is not None else []

    def validate(self, context):
        if not self.channels:
            logging.error("Scene does not contain any animation data!")
            return False

        if context.file_format == "W3X":
            return True

        if len(self.header.name) >= STRING_LENGTH:
            logging.error(
                f"animation name '{self.header.name}' exceeds max length of {STRING_LENGTH}"
            )
            return False
        if len(self.header.hierarchy_name) >= STRING_LENGTH:
            logging.error(
                f"armature name '{self.header.hierarchy_name}' exceeds max length of {STRING_LENGTH}"
            )
            return False
        return True

    @staticmethod
    def read(io_stream, chunk_end):
        result = Animation()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)
            if chunk_type == W3D_CHUNK_ANIMATION_HEADER:
                result.header = AnimationHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_ANIMATION_CHANNEL:
                result.channels.append(AnimationChannel.read(io_stream, subchunk_end))
            elif chunk_type == W3D_CHUNK_ANIMATION_BIT_CHANNEL:
                result.channels.append(AnimationBitChannel.read(io_stream))
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        size += list_size(self.channels, False)
        return size

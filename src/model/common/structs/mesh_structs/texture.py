# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

from model.w3d.io_binary import read_chunk_head, read_float, read_string, read_ulong, read_ushort
from model.w3d.utils.helpers import const_size, skip_unknown_chunk, text_size

W3D_CHUNK_TEXTURES = 0x00000030
W3D_CHUNK_TEXTURE_INFO = 0x00000033


class TextureInfo:
    def __init__(self, attributes=0, animation_type=0, frame_count=0, frame_rate=0):
        self.attributes = attributes
        self.animation_type = animation_type
        self.frame_count = frame_count
        self.frame_rate = frame_rate

    @staticmethod
    def read(io_stream):
        return TextureInfo(
            attributes=read_ushort(io_stream),
            animation_type=read_ushort(io_stream),
            frame_count=read_ulong(io_stream),
            frame_rate=read_float(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(12, include_head)


W3D_CHUNK_TEXTURE = 0x00000031
W3D_CHUNK_TEXTURE_NAME = 0x00000032


class Texture:
    def __init__(self, id="", file="", texture_info=None):
        self.id = id
        self.file = file
        self.texture_info = texture_info

    @staticmethod
    def read(io_stream, chunk_end):
        result = Texture()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, _) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_TEXTURE_NAME:
                result.file = read_string(io_stream)
                result.id = result.file
            elif chunk_type == W3D_CHUNK_TEXTURE_INFO:
                result.texture_info = TextureInfo.read(io_stream)
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += text_size(self.file)
        if self.texture_info is not None:
            size += self.texture_info.size()
        return size

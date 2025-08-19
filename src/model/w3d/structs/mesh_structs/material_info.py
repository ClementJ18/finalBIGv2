# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

from model.w3d.io_binary import read_ulong
from model.w3d.utils.helpers import const_size

W3D_CHUNK_MATERIAL_INFO = 0x00000028


class MaterialInfo:
    def __init__(self, pass_count=0, vert_matl_count=0, shader_count=0, texture_count=0):
        self.pass_count = pass_count
        self.vert_matl_count = vert_matl_count
        self.shader_count = shader_count
        self.texture_count = texture_count

    @staticmethod
    def read(io_stream):
        return MaterialInfo(
            pass_count=read_ulong(io_stream),
            vert_matl_count=read_ulong(io_stream),
            shader_count=read_ulong(io_stream),
            texture_count=read_ulong(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(16, include_head)

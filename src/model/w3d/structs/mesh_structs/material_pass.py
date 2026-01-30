# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

from model.common.structs.rgba import RGBA
from model.w3d.io_binary import (
    Vector,
    read_chunk_head,
    read_list,
    read_long,
    read_ulong,
    read_vector,
    read_vector2,
)
from model.w3d.utils.helpers import (
    const_size,
    list_size,
    long_list_size,
    skip_unknown_chunk,
    vec2_list_size,
    vec_list_size,
)

W3D_CHUNK_TEXTURE_STAGE = 0x00000048
W3D_CHUNK_TEXTURE_IDS = 0x00000049
W3D_CHUNK_STAGE_TEXCOORDS = 0x0000004A
W3D_CHUNK_PER_FACE_TEXCOORD_IDS = 0x0000004B


class TextureStage:
    def __init__(self, tx_ids=None, per_face_tx_coords=None, tx_coords=None):
        self.tx_ids = tx_ids if tx_ids is not None else []
        self.per_face_tx_coords = per_face_tx_coords if per_face_tx_coords is not None else []
        self.tx_coords: list[list[Vector]] = tx_coords if tx_coords is not None else []

    @staticmethod
    def read(io_stream, chunk_end):
        result = TextureStage()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_TEXTURE_IDS:
                result.tx_ids.append(read_list(io_stream, subchunk_end, read_long))
            elif chunk_type == W3D_CHUNK_STAGE_TEXCOORDS:
                result.tx_coords.append(read_list(io_stream, subchunk_end, read_vector2))
            elif chunk_type == W3D_CHUNK_PER_FACE_TEXCOORD_IDS:
                result.per_face_tx_coords.append(read_list(io_stream, subchunk_end, read_vector))
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        for tx_id in self.tx_ids:
            size += long_list_size(tx_id)
        for tx_coord in self.tx_coords:
            size += vec2_list_size(tx_coord)
        for per_face_tx_coord in self.per_face_tx_coords:
            size += vec_list_size(per_face_tx_coord)
        return size


W3D_CHUNK_MATERIAL_PASS = 0x00000038
W3D_CHUNK_VERTEX_MATERIAL_IDS = 0x00000039
W3D_CHUNK_SHADER_IDS = 0x0000003A
W3D_CHUNK_DCG = 0x0000003B
W3D_CHUNK_DIG = 0x0000003C
W3D_CHUNK_SCG = 0x0000003E
W3D_CHUNK_SHADER_MATERIAL_ID = 0x0000003F


class MaterialPass:
    def __init__(
        self,
        vertex_material_ids=None,
        shader_ids=None,
        dcg=None,
        dig=None,
        scg=None,
        shader_material_ids=None,
        tx_stages=None,
        tx_coords=None,
    ):
        self.vertex_material_ids = vertex_material_ids if vertex_material_ids is not None else []
        self.shader_ids = shader_ids if shader_ids is not None else []
        self.dcg = dcg if dcg is not None else []
        self.dig = dig if dig is not None else []
        self.scg = scg if scg is not None else []
        self.shader_material_ids = shader_material_ids if shader_material_ids is not None else []
        self.tx_stages: list[TextureStage] = tx_stages if tx_stages is not None else []
        self.tx_coords: list[Vector] = tx_coords if tx_coords is not None else []
        self.tx_coords_2 = tx_coords if tx_coords is not None else []

    @staticmethod
    def read(io_stream, chunk_end):
        result = MaterialPass()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_VERTEX_MATERIAL_IDS:
                result.vertex_material_ids = read_list(io_stream, subchunk_end, read_ulong)
            elif chunk_type == W3D_CHUNK_SHADER_IDS:
                result.shader_ids = read_list(io_stream, subchunk_end, read_ulong)
            elif chunk_type == W3D_CHUNK_DCG:
                result.dcg = read_list(io_stream, subchunk_end, RGBA.read)
            elif chunk_type == W3D_CHUNK_DIG:
                result.dig = read_list(io_stream, subchunk_end, RGBA.read)
            elif chunk_type == W3D_CHUNK_SCG:
                result.scg = read_list(io_stream, subchunk_end, RGBA.read)
            elif chunk_type == W3D_CHUNK_SHADER_MATERIAL_ID:
                result.shader_material_ids = read_list(io_stream, subchunk_end, read_ulong)
            elif chunk_type == W3D_CHUNK_TEXTURE_STAGE:
                result.tx_stages.append(TextureStage.read(io_stream, subchunk_end))
            elif chunk_type == W3D_CHUNK_STAGE_TEXCOORDS:
                result.tx_coords = read_list(io_stream, subchunk_end, read_vector2)
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += long_list_size(self.vertex_material_ids)
        size += long_list_size(self.shader_ids)
        size += list_size(self.dcg)
        size += list_size(self.dig)
        size += list_size(self.scg)
        size += long_list_size(self.shader_material_ids)
        size += list_size(self.tx_stages, False)
        size += vec2_list_size(self.tx_coords)
        # size += vec2_list_size(self.tx_coords_2)
        return size

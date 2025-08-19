# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import logging

from model.common.structs.mesh_structs.aabbtree import W3D_CHUNK_AABBTREE, AABBTree
from model.common.structs.mesh_structs.shader_material import (
    W3D_CHUNK_SHADER_MATERIAL,
    ShaderMaterial,
)
from model.common.structs.mesh_structs.texture import (
    W3D_CHUNK_TEXTURE,
    W3D_CHUNK_TEXTURES,
    Texture,
)
from model.common.structs.mesh_structs.triangle import Triangle
from model.common.structs.mesh_structs.vertex_influence import VertexInfluence
from model.w3d.io_binary import (
    STRING_LENGTH,
    Vector,
    read_chunk_head,
    read_fixed_string,
    read_float,
    read_list,
    read_long,
    read_string,
    read_ulong,
    read_vector,
)
from model.w3d.structs.mesh_structs.material_info import W3D_CHUNK_MATERIAL_INFO, MaterialInfo
from model.w3d.structs.mesh_structs.material_pass import W3D_CHUNK_MATERIAL_PASS, MaterialPass
from model.w3d.structs.mesh_structs.prelit import (
    W3D_CHUNK_PRELIT_LIGHTMAP_MULTI_PASS,
    W3D_CHUNK_PRELIT_LIGHTMAP_MULTI_TEXTURE,
    W3D_CHUNK_PRELIT_UNLIT,
    W3D_CHUNK_PRELIT_VERTEX,
    PrelitBase,
)
from model.w3d.structs.mesh_structs.shader import W3D_CHUNK_SHADERS, Shader
from model.w3d.structs.mesh_structs.vertex_material import (
    W3D_CHUNK_VERTEX_MATERIAL,
    W3D_CHUNK_VERTEX_MATERIALS,
    VertexMaterial,
)
from model.w3d.structs.version import Version
from model.w3d.utils.helpers import (
    const_size,
    list_size,
    long_list_size,
    read_chunk_array,
    skip_unknown_chunk,
    text_size,
    vec_list_size,
)

W3D_CHUNK_MESH_HEADER = 0x0000001F

# Geometry types
GEOMETRY_TYPE_NORMAL = 0x00000000
GEOMETRY_TYPE_HIDDEN = 0x00001000
GEOMETRY_TYPE_TWO_SIDED = 0x00002000
GEOMETRY_TYPE_CAST_SHADOW = 0x00008000
GEOMETRY_TYPE_CAMERA_ALIGNED = 0x00010000
GEOMETRY_TYPE_SKIN = 0x00020000
GEOMETRY_TYPE_CAMERA_ORIENTED = 0x00060000

# Prelit types
PRELIT_MASK = 0x0F000000
PRELIT_UNLIT = 0x01000000
PRELIT_VERTEX = 0x02000000
PRELIT_LIGHTMAP_MULTI_PASS = 0x04000000
PRELIT_LIGHTMAP_MULTI_TEXTURE = 0x08000000

# Vertex channels
VERTEX_CHANNEL_LOCATION = 0x01
VERTEX_CHANNEL_NORMAL = 0x02
VERTEX_CHANNEL_BONE_ID = 0x10
VERTEX_CHANNEL_TANGENT = 0x20
VERTEX_CHANNEL_BITANGENT = 0x40


class MeshHeader:
    def __init__(
        self,
        version=Version(major=4, minor=2),
        attrs=GEOMETRY_TYPE_NORMAL,
        mesh_name="",
        container_name="",
        face_count=0,
        vert_count=0,
        matl_count=0,
        damage_stage_count=0,
        sort_level=0,
        prelit_version=0,
        future_count=0,
        vert_channel_flags=0,
        face_channel_flags=1,
        min_corner=Vector(),
        max_corner=Vector(),
        sph_center=Vector(),
        sph_radius=0.0,
    ):
        self.version = version
        self.attrs = attrs
        self.mesh_name = mesh_name
        self.container_name = container_name
        self.face_count = face_count
        self.vert_count = vert_count
        self.matl_count = matl_count
        self.damage_stage_count = damage_stage_count
        self.sort_level = sort_level
        self.prelit_version = prelit_version
        self.future_count = future_count
        self.vert_channel_flags = vert_channel_flags
        self.face_channel_flags = face_channel_flags
        self.min_corner = min_corner
        self.max_corner = max_corner
        self.sph_center = sph_center
        self.sph_radius = sph_radius

    @staticmethod
    def read(io_stream):
        return MeshHeader(
            version=Version.read(io_stream),
            attrs=read_ulong(io_stream),
            mesh_name=read_fixed_string(io_stream),
            container_name=read_fixed_string(io_stream),
            face_count=read_ulong(io_stream),
            vert_count=read_ulong(io_stream),
            matl_count=read_ulong(io_stream),
            damage_stage_count=read_ulong(io_stream),
            sort_level=read_ulong(io_stream),
            prelit_version=read_ulong(io_stream),
            future_count=read_ulong(io_stream),
            vert_channel_flags=read_ulong(io_stream),
            face_channel_flags=read_ulong(io_stream),
            # bounding volumes
            min_corner=read_vector(io_stream),
            max_corner=read_vector(io_stream),
            sph_center=read_vector(io_stream),
            sph_radius=read_float(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(116, include_head)


W3D_CHUNK_MESH = 0x00000000
W3D_CHUNK_VERTICES = 0x00000002
W3D_CHUNK_VERTICES_2 = 0xC00
W3D_CHUNK_VERTEX_NORMALS = 0x00000003
W3D_CHUNK_NORMALS_2 = 0xC01
W3D_CHUNK_MESH_USER_TEXT = 0x0000000C
W3D_CHUNK_VERTEX_INFLUENCES = 0x0000000E
W3D_CHUNK_TRIANGLES = 0x00000020
W3D_CHUNK_VERTEX_SHADE_INDICES = 0x00000022
W3D_CHUNK_SHADER_MATERIALS = 0x50
W3D_CHUNK_TANGENTS = 0x60
W3D_CHUNK_BITANGENTS = 0x61


class Mesh:
    def __init__(self):
        self.header = None
        self.user_text = ""
        self.verts = []
        self.normals = []
        self.verts_2 = []
        self.normals_2 = []
        self.tangents = []
        self.bitangents = []
        self.vert_infs = []
        self.triangles = []
        self.shade_ids = []
        self.mat_info = None
        self.shaders = []
        self.vert_materials = []
        self.textures = []
        self.shader_materials = []
        self.material_passes = []
        self.aabbtree = None
        self.prelit_unlit = None
        self.prelit_vertex = None
        self.prelit_lightmap_multi_pass = None
        self.prelit_lightmap_multi_texture = None

        # non struct properties
        self.multi_bone_skinned = False

    def validate(self, context):
        if len(self.header.mesh_name) >= STRING_LENGTH and context.file_format == "W3D":
            logging.error(
                f"mesh name '{self.header.mesh_name}' exceeds max length of {STRING_LENGTH}"
            )
            return False
        return True

    def casts_shadow(self):
        return (self.header.attrs & GEOMETRY_TYPE_CAST_SHADOW) == GEOMETRY_TYPE_CAST_SHADOW

    def two_sided(self):
        return (self.header.attrs & GEOMETRY_TYPE_TWO_SIDED) == GEOMETRY_TYPE_TWO_SIDED

    def is_hidden(self):
        return (self.header.attrs & GEOMETRY_TYPE_HIDDEN) == GEOMETRY_TYPE_HIDDEN

    def is_skin(self):
        return (self.header.attrs & GEOMETRY_TYPE_SKIN) == GEOMETRY_TYPE_SKIN

    def is_camera_oriented(self):
        return (self.header.attrs & GEOMETRY_TYPE_CAMERA_ORIENTED) == GEOMETRY_TYPE_CAMERA_ORIENTED

    def is_camera_aligned(self):
        return (self.header.attrs & GEOMETRY_TYPE_CAMERA_ALIGNED) == GEOMETRY_TYPE_CAMERA_ALIGNED

    def container_name(self):
        return self.header.container_name

    def name(self):
        return self.header.mesh_name

    def identifier(self):
        return self.header.container_name + "." + self.name()

    def get_material_pass(self):
        if not self.material_passes:
            mat_pass = MaterialPass(shader_material_ids=[0])
            self.material_passes.append(mat_pass)
        return self.material_passes[0]

    @staticmethod
    def read(io_stream, chunk_end):
        result = Mesh()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_VERTICES:
                result.verts = read_list(io_stream, subchunk_end, read_vector)
            elif chunk_type == W3D_CHUNK_VERTICES_2:
                logging.info("-> vertices 2 chunk is not supported")
                io_stream.seek(chunk_size, 1)
            elif chunk_type == W3D_CHUNK_VERTEX_NORMALS:
                result.normals = read_list(io_stream, subchunk_end, read_vector)
            elif chunk_type == W3D_CHUNK_NORMALS_2:
                logging.info("-> normals 2 chunk is not supported")
                io_stream.seek(chunk_size, 1)
            elif chunk_type == W3D_CHUNK_MESH_USER_TEXT:
                result.user_text = read_string(io_stream)
            elif chunk_type == W3D_CHUNK_VERTEX_INFLUENCES:
                result.vert_infs = read_list(io_stream, subchunk_end, VertexInfluence.read)
            elif chunk_type == W3D_CHUNK_MESH_HEADER:
                result.header = MeshHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_TRIANGLES:
                result.triangles = read_list(io_stream, subchunk_end, Triangle.read)
            elif chunk_type == W3D_CHUNK_VERTEX_SHADE_INDICES:
                result.shade_ids = read_list(io_stream, subchunk_end, read_long)
            elif chunk_type == W3D_CHUNK_MATERIAL_INFO:
                result.mat_info = MaterialInfo.read(io_stream)
            elif chunk_type == W3D_CHUNK_SHADERS:
                result.shaders = read_list(io_stream, subchunk_end, Shader.read)
            elif chunk_type == W3D_CHUNK_VERTEX_MATERIALS:
                result.vert_materials = read_chunk_array(
                    io_stream, subchunk_end, W3D_CHUNK_VERTEX_MATERIAL, VertexMaterial.read
                )
            elif chunk_type == W3D_CHUNK_TEXTURES:
                result.textures = read_chunk_array(
                    io_stream, subchunk_end, W3D_CHUNK_TEXTURE, Texture.read
                )
            elif chunk_type == W3D_CHUNK_MATERIAL_PASS:
                result.material_passes.append(MaterialPass.read(io_stream, subchunk_end))
            elif chunk_type == W3D_CHUNK_SHADER_MATERIALS:
                result.shader_materials = read_chunk_array(
                    io_stream, subchunk_end, W3D_CHUNK_SHADER_MATERIAL, ShaderMaterial.read
                )
            elif chunk_type == W3D_CHUNK_TANGENTS:
                logging.info("-> tangents are computed in blender")
                io_stream.seek(chunk_size, 1)
            elif chunk_type == W3D_CHUNK_BITANGENTS:
                logging.info("-> bitangents are computed in blender")
                io_stream.seek(chunk_size, 1)
            elif chunk_type == W3D_CHUNK_AABBTREE:
                result.aabbtree = AABBTree.read(io_stream, subchunk_end)
            elif chunk_type == W3D_CHUNK_PRELIT_UNLIT:
                result.prelit_unlit = PrelitBase.read(io_stream, subchunk_end, chunk_type)
            elif chunk_type == W3D_CHUNK_PRELIT_VERTEX:
                result.prelit_vertex = PrelitBase.read(io_stream, subchunk_end, chunk_type)
            elif chunk_type == W3D_CHUNK_PRELIT_LIGHTMAP_MULTI_PASS:
                result.prelit_lightmap_multi_pass = PrelitBase.read(
                    io_stream, subchunk_end, chunk_type
                )
            elif chunk_type == W3D_CHUNK_PRELIT_LIGHTMAP_MULTI_TEXTURE:
                result.prelit_lightmap_multi_texture = PrelitBase.read(
                    io_stream, subchunk_end, chunk_type
                )
            elif chunk_type == W3D_CHUNK_DEFORM:
                logging.info("-> deform chunk is not supported")
                io_stream.seek(chunk_size, 1)
            elif chunk_type == W3D_CHUNK_PS2_SHADERS:
                logging.info("-> ps2 shaders chunk is not supported")
                io_stream.seek(chunk_size, 1)
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        size += text_size(self.user_text)
        size += vec_list_size(self.verts)
        size += vec_list_size(self.normals)
        if self.multi_bone_skinned and self.verts_2:
            size += vec_list_size(self.verts_2)
        if self.multi_bone_skinned and self.normals_2:
            size += vec_list_size(self.normals_2)
        size += vec_list_size(self.tangents)
        size += vec_list_size(self.bitangents)
        size += list_size(self.triangles)
        size += list_size(self.vert_infs)
        size += list_size(self.shaders)
        size += list_size(self.textures)
        size += long_list_size(self.shade_ids)
        size += list_size(self.shader_materials)
        if self.mat_info is not None:
            size += self.mat_info.size()
        size += list_size(self.vert_materials)
        size += list_size(self.material_passes, False)
        if self.aabbtree is not None:
            size += self.aabbtree.size()
        if self.prelit_unlit is not None:
            size += self.prelit_unlit.size()
        if self.prelit_vertex is not None:
            size += self.prelit_vertex.size()
        if self.prelit_lightmap_multi_pass is not None:
            size += self.prelit_lightmap_multi_pass.size()
        if self.prelit_lightmap_multi_texture is not None:
            size += self.prelit_lightmap_multi_texture.size()
        return size


##########################################################################
# Unsupported
##########################################################################


W3D_CHUNK_DEFORM = 0x00000058
W3D_CHUNK_PS2_SHADERS = 0x00000080

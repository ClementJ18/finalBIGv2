# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import logging
from model.w3d.io_binary import (
    read_chunk_head,
    read_float,
    read_long,
    read_long_fixed_string,
    read_string,
    read_ubyte,
    read_vector2,
    read_vector4,
)
from model.w3d.io_binary import Vector
from model.w3d.utils.helpers import const_size, skip_unknown_chunk


W3D_CHUNK_SHADER_MATERIAL_HEADER = 0x52

W3D_NORMTYPE_TEXTURE = 1
W3D_NORMTYPE_BUMP = 2
W3D_NORMTYPE_COLORS = 5
W3D_NORMTYPE_ALPHA = 7


class ShaderMaterialHeader:
    def __init__(self, version=1, type_name="", technique=0):
        self.version = version
        self.type_name = type_name
        self.technique = technique

    @staticmethod
    def read(io_stream):
        return ShaderMaterialHeader(
            version=read_ubyte(io_stream),
            type_name=read_long_fixed_string(io_stream),
            technique=read_long(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(37, include_head)


W3D_CHUNK_SHADER_MATERIAL_PROPERTY = 0x53

STRING_PROPERTY = 1
FLOAT_PROPERTY = 2
VEC2_PROPERTY = 3
VEC3_PROPERTY = 4
VEC4_PROPERTY = 5
LONG_PROPERTY = 6
BOOL_PROPERTY = 7


class ShaderMaterialProperty:
    def __init__(self, type=0, name="", value=Vector((1.0, 1.0, 1.0, 1.0))):
        self.type = type
        self.name = name
        self.value = value

    def to_rgb(self):
        return self.value.x, self.value.y, self.value.z

    def to_rgba(self):
        return (
            self.value.x,
            self.value.y,
            self.value.z,
            self.value.w if len(self.value) > 3 else 1.0,
        )

    @staticmethod
    def read(io_stream):
        prop_type = read_long(io_stream)
        read_long(io_stream)  # num chars
        name = read_string(io_stream)
        result = ShaderMaterialProperty(
            type=prop_type, name=name, value=Vector((1.0, 1.0, 1.0, 1.0))
        )

        if result.type == STRING_PROPERTY:
            read_long(io_stream)  # num chars
            result.value = read_string(io_stream)
        elif result.type == FLOAT_PROPERTY:
            result.value = read_float(io_stream)
        elif result.type == VEC2_PROPERTY:
            result.value = read_vector2(io_stream)
        elif result.type == VEC4_PROPERTY:
            result.value = read_vector4(io_stream)
        elif result.type == LONG_PROPERTY:
            result.value = read_long(io_stream)
        elif result.type == BOOL_PROPERTY:
            result.value = bool(read_ubyte(io_stream))
        else:
            logging.warning(f"unknown property type '{result.type}' in shader material")
        return result

    def size(self, include_head=True):
        size = const_size(8, include_head)
        size += len(self.name) + 1
        if self.type == STRING_PROPERTY:
            size += 4 + len(self.value) + 1
        elif self.type == FLOAT_PROPERTY:
            size += 4
        elif self.type == VEC2_PROPERTY:
            size += 8
        elif self.type == VEC3_PROPERTY:
            size += 12
        elif self.type == VEC4_PROPERTY:
            size += 16
        elif self.type == LONG_PROPERTY:
            size += 4
        else:
            size += 1
        return size


W3D_CHUNK_SHADER_MATERIAL = 0x51


class ShaderMaterial:
    def __init__(self, header=None, properties=None):
        self.header = header
        self.properties = properties if properties is not None else []

    @staticmethod
    def read(io_stream, chunk_end):
        result = ShaderMaterial()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, _) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_SHADER_MATERIAL_HEADER:
                result.header = ShaderMaterialHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_SHADER_MATERIAL_PROPERTY:
                result.properties.append(ShaderMaterialProperty.read(io_stream))
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        for prop in self.properties:
            size += prop.size()
        return size

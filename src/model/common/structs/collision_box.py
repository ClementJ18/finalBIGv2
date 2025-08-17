# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import logging

from model.common.structs.rgba import RGBA
from model.w3d.io_binary import (
    LARGE_STRING_LENGTH,
    read_long_fixed_string,
    read_ulong,
    read_vector,
)
from model.w3d.structs.version import Version
from model.w3d.io_binary import Vector
from model.w3d.utils.helpers import const_size

W3D_CHUNK_BOX = 0x00000740
ATTRIBUTE_MASK = 0xF
COLLISION_TYPE_MASK = 0xFF0

COLLISION_TYPE_PHYSICAL = 0x10
COLLISION_TYPE_PROJECTILE = 0x20
COLLISION_TYPE_VIS = 0x40
COLLISION_TYPE_CAMERA = 0x80
COLLISION_TYPE_VEHICLE = 0x100


class CollisionBox:
    def __init__(
        self,
        version=Version(),
        box_type=0,
        collision_types=0,
        name_="",
        color=RGBA(),
        center=Vector((0.0, 0.0, 0.0)),
        extend=Vector((0.0, 0.0, 0.0)),
        joypad_picking_only=False,
    ):
        self.version = version
        self.box_type = box_type
        self.collision_types = collision_types
        self.name_ = name_
        self.color = color
        self.center = center
        self.extend = extend
        self.joypad_picking_only = joypad_picking_only

    def validate(self, context):
        if context.file_format == "W3X":
            return True
        if len(self.name_) >= LARGE_STRING_LENGTH:
            logging.error(f"box name '{self.name_}' exceeds max length of: {LARGE_STRING_LENGTH}")
            return False
        return True

    def container_name(self):
        return self.name_.split(".", 1)[0]

    def name(self):
        return self.name_.split(".", 1)[-1]

    @staticmethod
    def read(io_stream):
        ver = Version.read(io_stream)
        flags = read_ulong(io_stream)
        return CollisionBox(
            version=ver,
            box_type=(flags & ATTRIBUTE_MASK),
            collision_types=(flags & COLLISION_TYPE_MASK),
            name_=read_long_fixed_string(io_stream),
            color=RGBA.read(io_stream),
            center=read_vector(io_stream),
            extend=read_vector(io_stream),
        )

    @staticmethod
    def size(include_head=True):
        return const_size(68, include_head)

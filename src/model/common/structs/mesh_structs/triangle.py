# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel


import logging
from model.w3d.io_binary import read_float, read_ulong, read_vector
from model.w3d.io_binary import Vector


surface_types = [
    "LightMetal",
    "HeavyMetal",
    "Water",
    "Sand",
    "Dirt",
    "Mud",
    "Grass",
    "Wood",
    "Concrete",
    "Flesh",
    "Rock",
    "Snow",
    "Ice",
    "Default",
    "Glass",
    "Cloth",
    "TiberiumField",
    "FoliagePermeable",
    "GlassPermeable",
    "IcePermeable",
    "ClothPermeable",
    "Electrical",
    "Flammable",
    "Steam",
    "ElectricalPermeable",
    "FlammablePermeable",
    "SteamPermeable",
    "WaterPermeable",
    "TiberiumWater",
    "TiberiumWaterPermeable",
    "UnderwaterDirt",
    "UnderwaterTiberiumDirt",
]


class Triangle:
    def __init__(
        self, vert_ids=None, surface_type=13, normal=Vector((0.0, 0.0, 0.0)), distance=0.0
    ):
        self.vert_ids = vert_ids if vert_ids is not None else []
        self.surface_type = surface_type
        self.normal = normal
        self.distance = distance

    @staticmethod
    def validate_face_map_names(context, face_map_names):
        for name in face_map_names:
            if name not in surface_types:
                logging.warning(
                    f"name of face map '{name}' is not one of valid surface types: {surface_types}"
                )

    def get_surface_type_name(self, context, index):
        if self.surface_type >= len(surface_types):
            logging.warning(f"triangle {index} has an invalid surface type '{self.surface_type}'")
            return "Default"
        return surface_types[self.surface_type]

    def set_surface_type(self, name):
        if name not in surface_types:
            return
        self.surface_type = surface_types.index(name)

    @staticmethod
    def read(io_stream):
        return Triangle(
            vert_ids=[read_ulong(io_stream), read_ulong(io_stream), read_ulong(io_stream)],
            surface_type=read_ulong(io_stream),
            normal=read_vector(io_stream),
            distance=read_float(io_stream),
        )

    @staticmethod
    def size():
        return 32

# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import io
import logging

from model.common.structs.animation import W3D_CHUNK_ANIMATION, Animation
from model.common.structs.collision_box import W3D_CHUNK_BOX, CollisionBox
from model.common.structs.data_context import DataContext
from model.common.structs.hierarchy import W3D_CHUNK_HIERARCHY, Hierarchy
from model.common.structs.hlod import W3D_CHUNK_HLOD, HLod
from model.common.structs.mesh import W3D_CHUNK_MESH, Mesh
from model.w3d.io_binary import read_chunk_head
from model.w3d.structs.compressed_animation import (
    W3D_CHUNK_COMPRESSED_ANIMATION,
    CompressedAnimation,
)
from model.w3d.structs.dazzle import W3D_CHUNK_DAZZLE, Dazzle
from model.w3d.utils.helpers import skip_unknown_chunk


def load_file(data_context: DataContext, data: bytes):
    file = io.BytesIO(data)
    filesize = len(data)

    while file.tell() < filesize:
        chunk_type, chunk_size, chunk_end = read_chunk_head(file)

        if chunk_type == W3D_CHUNK_MESH:
            data_context.meshes.append(Mesh.read(file, chunk_end))
        elif chunk_type == W3D_CHUNK_HIERARCHY:
            if data_context.hierarchy is None:
                data_context.hierarchy = Hierarchy.read(file, chunk_end)
            else:
                logging.warning("-> already got one hierarchy chunk (skipping this one)!")
                file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_HLOD:
            if data_context.hlod is None:
                data_context.hlod = HLod.read(file, chunk_end)
            else:
                logging.warning("-> already got one hlod chunk (skipping this one)!")
                file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_ANIMATION:
            if data_context.animation is None and data_context.compressed_animation is None:
                data_context.animation = Animation.read(file, chunk_end)
            else:
                logging.warning("-> already got one animation chunk (skipping this one)!")
                file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_COMPRESSED_ANIMATION:
            if data_context.animation is None and data_context.compressed_animation is None:
                data_context.compressed_animation = CompressedAnimation.read(file, chunk_end)
            else:
                logging.warning("-> already got one animation chunk (skipping this one)!")
                file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_BOX:
            data_context.collision_boxes.append(CollisionBox.read(file))
        elif chunk_type == W3D_CHUNK_DAZZLE:
            data_context.dazzles.append(Dazzle.read(file, chunk_end))
        elif chunk_type == W3D_CHUNK_MORPH_ANIMATION:
            logging.info("-> morph animation chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_HMODEL:
            logging.info("-> hmodel chnuk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_LODMODEL:
            logging.info("-> lodmodel chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_COLLECTION:
            logging.info("-> collection chunk not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_POINTS:
            logging.info("-> points chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_LIGHT:
            logging.info("-> light chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_EMITTER:
            logging.info("-> emitter chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_AGGREGATE:
            logging.info("-> aggregate chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_NULL_OBJECT:
            logging.info("-> null object chunkt is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_LIGHTSCAPE:
            logging.info("-> lightscape chunk is not supported")
            file.seek(chunk_size, 1)
        elif chunk_type == W3D_CHUNK_SOUNDROBJ:
            logging.info("-> soundobj chunk is not supported")
            file.seek(chunk_size, 1)
        else:
            skip_unknown_chunk(file, chunk_type, chunk_size)

    file.close()


##########################################################################
# Unsupported
##########################################################################

W3D_CHUNK_MORPH_ANIMATION = 0x000002C0
W3D_CHUNK_HMODEL = 0x00000300
W3D_CHUNK_LODMODEL = 0x00000400
W3D_CHUNK_COLLECTION = 0x00000420
W3D_CHUNK_POINTS = 0x00000440
W3D_CHUNK_LIGHT = 0x00000460
W3D_CHUNK_EMITTER = 0x00000500
W3D_CHUNK_AGGREGATE = 0x00000600
W3D_CHUNK_NULL_OBJECT = 0x00000750
W3D_CHUNK_LIGHTSCAPE = 0x00000800
W3D_CHUNK_SOUNDROBJ = 0x00000A00

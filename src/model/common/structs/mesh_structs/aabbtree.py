# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

from model.w3d.io_binary import (
    read_chunk_head,
    read_list,
    read_long,
    read_padding,
    read_ulong,
    read_vector,
)
from model.w3d.io_binary import Vector
from model.w3d.utils.helpers import const_size, list_size, long_list_size, skip_unknown_chunk


W3D_CHUNK_AABBTREE_HEADER = 0x00000091


class AABBTreeHeader:
    def __init__(self, node_count=0, poly_count=0):
        self.node_count = node_count
        self.poly_count = poly_count  # num tris of mesh

    @staticmethod
    def read(io_stream):
        result = AABBTreeHeader(node_count=read_ulong(io_stream), poly_count=read_ulong(io_stream))

        read_padding(io_stream, 24)
        return result

    @staticmethod
    def size(include_head=True):
        return const_size(32, include_head)


class Children:
    def __init__(self, front=0, back=0):
        self.front = front
        self.back = back


class Polys:
    def __init__(self, begin=0, count=0):
        self.begin = begin
        self.count = count


class AABBTreeNode:
    def __init__(
        self, min=Vector((0.0, 0.0, 0.0)), max=Vector((0.0, 0.0, 0.0)), children=None, polys=None
    ):
        self.min = min
        self.max = max
        self.children = children
        self.polys = polys

    @staticmethod
    def read(io_stream):
        node = AABBTreeNode(min=read_vector(io_stream), max=read_vector(io_stream))
        node.children = Children(front=read_long(io_stream), back=read_long(io_stream))
        return node

    @staticmethod
    def size():
        return 32


W3D_CHUNK_AABBTREE = 0x00000090
W3D_CHUNK_AABBTREE_POLYINDICES = 0x00000092
W3D_CHUNK_AABBTREE_NODES = 0x00000093


class AABBTree:
    def __init__(self, header=None, poly_indices=None, nodes=None):
        self.header = header
        self.poly_indices = poly_indices if poly_indices is not None else []
        self.nodes = nodes if nodes is not None else []

    @staticmethod
    def read(io_stream, chunk_end):
        result = AABBTree()

        while io_stream.tell() < chunk_end:
            (chunk_type, chunk_size, subchunk_end) = read_chunk_head(io_stream)

            if chunk_type == W3D_CHUNK_AABBTREE_HEADER:
                result.header = AABBTreeHeader.read(io_stream)
            elif chunk_type == W3D_CHUNK_AABBTREE_POLYINDICES:
                result.poly_indices = read_list(io_stream, subchunk_end, read_long)
            elif chunk_type == W3D_CHUNK_AABBTREE_NODES:
                result.nodes = read_list(io_stream, subchunk_end, AABBTreeNode.read)
            else:
                skip_unknown_chunk(io_stream, chunk_type, chunk_size)
        return result

    def size(self, include_head=True):
        size = const_size(0, include_head)
        size += self.header.size()
        size += long_list_size(self.poly_indices)
        size += list_size(self.nodes)
        return size

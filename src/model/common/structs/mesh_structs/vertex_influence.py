# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel


from model.w3d.io_binary import read_ushort


class VertexInfluence:
    def __init__(self, bone_idx=0, xtra_idx=0, bone_inf=0.0, xtra_inf=0.0):
        self.bone_idx = bone_idx
        self.xtra_idx = xtra_idx
        self.bone_inf = bone_inf
        self.xtra_inf = xtra_inf

    @staticmethod
    def read(io_stream):
        return VertexInfluence(
            bone_idx=read_ushort(io_stream),
            xtra_idx=read_ushort(io_stream),
            bone_inf=read_ushort(io_stream) / 100,
            xtra_inf=read_ushort(io_stream) / 100,
        )

    @staticmethod
    def size():
        return 8

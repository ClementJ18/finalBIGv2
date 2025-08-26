# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

from model.w3d.io_binary import read_float, read_ubyte


class RGBA:
    def __init__(self, vec=None, a=None, scale=255, r=0, g=0, b=0):
        if vec is None:
            self.r = r
            self.g = g
            self.b = b
            if a is not None:
                self.a = int(a)
            else:
                self.a = 0
            return

        self.r = int(vec[0] * scale)
        self.g = int(vec[1] * scale)
        self.b = int(vec[2] * scale)
        if a is not None:
            self.a = int(a)
        else:
            self.a = int(vec[3] * scale)

    @staticmethod
    def read(io_stream):
        return RGBA(
            r=read_ubyte(io_stream),
            g=read_ubyte(io_stream),
            b=read_ubyte(io_stream),
            a=read_ubyte(io_stream),
        )

    @staticmethod
    def read_f(io_stream):
        return RGBA(
            r=int(read_float(io_stream) * 255),
            g=int(read_float(io_stream) * 255),
            b=int(read_float(io_stream) * 255),
            a=int(read_float(io_stream) * 255),
        )

    @staticmethod
    def size():
        return 4

    def to_vector_rgba(self, scale=255.0):
        return self.r / scale, self.g / scale, self.b / scale, self.a / scale

    def to_vector_rgb(self, scale=255.0):
        return self.r / scale, self.g / scale, self.b / scale

    def __eq__(self, other):
        if isinstance(other, RGBA):
            return (
                self.r == other.r and self.g == other.g and self.b == other.b and self.a == other.a
            )
        return False

    def __str__(self):
        return f"RGBA({self.r}, {self.g}, {self.b}, {self.a})"

# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

from model.w3d.io_binary import read_ulong


class Version:
    def __init__(self, major=5, minor=0):
        self.major = major
        self.minor = minor

    @staticmethod
    def read(io_stream):
        data = read_ulong(io_stream)
        return Version(major=data >> 16, minor=data & 0xFFFF)

    def __eq__(self, other):
        if isinstance(other, Version):
            return self.major == other.major and self.minor == other.minor
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

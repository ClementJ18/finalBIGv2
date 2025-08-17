# <pep8 compliant>
# Written by Stephan Vedder and Michael Schnabel

import math
import struct


HEAD = 8  # chunk_type(long) + chunk_size(long)
STRING_LENGTH = 16
LARGE_STRING_LENGTH = STRING_LENGTH * 2


def read_string(io_stream):
    str_buf = []
    byte = io_stream.read(1)
    while ord(byte) != 0:
        str_buf.append(byte)
        byte = io_stream.read(1)
    return (b"".join(str_buf)).decode("utf-8")


def read_fixed_string(io_stream):
    return ((str(io_stream.read(STRING_LENGTH)))[2:18]).split("\\")[0]


def read_long_fixed_string(io_stream):
    return ((str(io_stream.read(LARGE_STRING_LENGTH)))[2:34]).split("\\")[0]


def read_long(io_stream):
    return struct.unpack("<l", io_stream.read(4))[0]


def read_ulong(io_stream):
    return struct.unpack("<L", io_stream.read(4))[0]


def read_short(io_stream):
    return struct.unpack("<h", io_stream.read(2))[0]


def read_ushort(io_stream):
    return struct.unpack("<H", io_stream.read(2))[0]


def read_float(io_stream):
    return struct.unpack("<f", io_stream.read(4))[0]


def read_byte(io_stream):
    return struct.unpack("<b", io_stream.read(1))[0]


def read_ubyte(io_stream):
    return struct.unpack("<B", io_stream.read(1))[0]


class Vector:
    def __init__(self, xyz=None):
        if xyz is None:
            xyz = (0.0, 0.0, 0.0)

        self.x = xyz[0]
        self.y = xyz[1]
        self.z = xyz[2]

    @staticmethod
    def read(io_stream):
        x = read_float(io_stream)
        y = read_float(io_stream)
        z = read_float(io_stream)
        return Vector((x, y, z))


class Quaternion:
    def __init__(self, wxyz):
        self.w = wxyz[0]
        self.x = wxyz[1]
        self.y = wxyz[2]
        self.z = wxyz[3]

    @classmethod
    def from_axis_angle(cls, axis, angle_rad):
        """Create quaternion from axis (Vector) and angle in radians."""
        half = angle_rad / 2.0
        s = math.sin(half)
        return cls(math.cos(half), axis.x * s, axis.y * s, axis.z * s)

    @classmethod
    def from_euler(cls, roll, pitch, yaw):
        """Create quaternion from Euler angles (in radians)."""
        cr = math.cos(roll / 2)
        sr = math.sin(roll / 2)
        cp = math.cos(pitch / 2)
        sp = math.sin(pitch / 2)
        cy = math.cos(yaw / 2)
        sy = math.sin(yaw / 2)

        w = cr * cp * cy + sr * sp * sy
        x = sr * cp * cy - cr * sp * sy
        y = cr * sp * cy + sr * cp * sy
        z = cr * cp * sy - sr * sp * cy
        return cls(w, x, y, z)

    def __mul__(self, other):
        """Quaternion multiplication (rotation composition)."""
        w = self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z
        x = self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y
        y = self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x
        z = self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w
        return Quaternion(w, x, y, z)

    def conjugate(self):
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def inverse(self):
        norm_sq = self.w**2 + self.x**2 + self.y**2 + self.z**2
        if norm_sq == 0:
            return Quaternion()
        conj = self.conjugate()
        return Quaternion(conj.w / norm_sq, conj.x / norm_sq, conj.y / norm_sq, conj.z / norm_sq)

    def normalize(self):
        mag = math.sqrt(self.w**2 + self.x**2 + self.y**2 + self.z**2)
        if mag == 0:
            self.w, self.x, self.y, self.z = 1, 0, 0, 0
        else:
            self.w /= mag
            self.x /= mag
            self.y /= mag
            self.z /= mag
        return self

    def to_euler(self):
        """Convert quaternion to Euler angles (roll, pitch, yaw)."""
        # roll (x-axis rotation)
        sinr_cosp = 2 * (self.w * self.x + self.y * self.z)
        cosr_cosp = 1 - 2 * (self.x**2 + self.y**2)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        # pitch (y-axis rotation)
        sinp = 2 * (self.w * self.y - self.z * self.x)
        if abs(sinp) >= 1:
            pitch = math.copysign(math.pi / 2, sinp)
        else:
            pitch = math.asin(sinp)

        # yaw (z-axis rotation)
        siny_cosp = 2 * (self.w * self.z + self.x * self.y)
        cosy_cosp = 1 - 2 * (self.y**2 + self.z**2)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return roll, pitch, yaw

    def __repr__(self):
        return f"Quaternion({self.w:.3f}, {self.x:.3f}, {self.y:.3f}, {self.z:.3f})"


def read_vector(io_stream):
    vec = Vector((0, 0, 0))
    vec.x = read_float(io_stream)
    vec.y = read_float(io_stream)
    vec.z = read_float(io_stream)
    return vec


def read_vector4(io_stream):
    vec = Vector((0, 0, 0, 0))
    vec.x = read_float(io_stream)
    vec.y = read_float(io_stream)
    vec.z = read_float(io_stream)
    vec.w = read_float(io_stream)
    return vec


def read_quaternion(io_stream):
    quat = Quaternion((0, 0, 0, 0))
    quat.x = read_float(io_stream)
    quat.y = read_float(io_stream)
    quat.z = read_float(io_stream)
    quat.w = read_float(io_stream)
    return quat


def read_vector2(io_stream):
    vec = Vector((0, 0, 0))
    vec.x = read_float(io_stream)
    vec.y = read_float(io_stream)
    return vec


def read_channel_value(io_stream, channel_type):
    if channel_type == 6:
        return read_quaternion(io_stream)
    return read_float(io_stream)


def read_chunk_head(io_stream):
    chunk_type = read_ulong(io_stream)
    chunk_size = read_ulong(io_stream) & 0x7FFFFFFF
    chunk_end = io_stream.tell() + chunk_size
    return chunk_type, chunk_size, chunk_end


def read_list(io_stream, chunk_end, read_func):
    result = []
    while io_stream.tell() < chunk_end:
        result.append(read_func(io_stream))
    return result


def read_fixed_list(io_stream, count, read_func, par1=None):
    result = []
    for _ in range(count):
        if par1 is not None:
            result.append(read_func(io_stream, par1))
        else:
            result.append(read_func(io_stream))
    return result


def read_padding(io_stream, count):
    io_stream.read(count)

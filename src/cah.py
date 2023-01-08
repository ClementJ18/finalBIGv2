import io

# Credits to withmorten
class CustomHero:
    def __init__(self, b):
        buffer = io.BytesIO(b)
        buffer.seek(0)

        self.alae2str = buffer.read(8).decode("Latin-1")

        buffer.read(1)  # blank

        self.header1 = int.from_bytes(buffer.read(4), "little")
        self.header2 = int.from_bytes(buffer.read(4), "little")

        self.version = int.from_bytes(buffer.read(4), "little")

        self.name_size = int.from_bytes(buffer.read(1), "little")

        self.name = buffer.read(self.name_size * 2).decode("Latin-1").replace("\x00", "")

        buffer.read(16)

        self.color1 = int.from_bytes(buffer.read(4), "little")
        self.color2 = int.from_bytes(buffer.read(4), "little")
        self.color3 = int.from_bytes(buffer.read(4), "little")

        self.powers = []

        for _ in range(10):
            length = int.from_bytes(buffer.read(1), "little")
            power = buffer.read(length).decode("Latin-1")
            level = int.from_bytes(buffer.read(4), "little")
            button_index = int.from_bytes(buffer.read(4), "little")
            self.powers.append((power, level, button_index))

        buffer.read(45)

        self.bling_number = int.from_bytes(buffer.read(4), "little")
        self.blings = []

        for _ in range(self.bling_number):
            length = int.from_bytes(buffer.read(1), "little")
            bling = buffer.read(length).decode("Latin-1")
            index = int.from_bytes(buffer.read(4), "little")
            self.blings.append((bling, index))

        self.something_lenght = int.from_bytes(buffer.read(1), "little")
        self.the_something = buffer.read(self.something_lenght).decode("Latin-1")

        self.is_system = bool.from_bytes(buffer.read(1), "little")
        self.checksum = buffer.read(4).decode("Latin-1")

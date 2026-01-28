import io
import logging
import traceback

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from tabs.generic_tab import GenericTab

# logging.basicConfig(level=logging.DEBUG)


# Credits to withmorten
class CustomHero:
    def __init__(self, b, encoding=None):
        self.bytes = b

        self.encoding = "utf-8"

        self.alae2str = ""
        self.blank = b""
        self.header1 = 0
        self.header2 = 0
        self.version = 0
        self.name_size = 0
        self.name = ""
        self.class_index = 0
        self.sub_class_index = 0
        self.reserved1 = 0
        self.reserved2 = 0
        self.color1 = 0
        self.color2 = 0
        self.color3 = 0
        self.powers = []
        self.bling_number = 0
        self.blings = []
        self.something_length = 0
        self.the_something = ""
        self.is_system = False
        self.checksum = None

        self.read()

    def read(self):
        buffer = io.BytesIO(self.bytes)
        buffer.seek(0)

        logging.debug(f"Reading alae2str at position {buffer.tell()}")
        self.alae2str = buffer.read(8).decode(self.encoding)
        logging.debug(f"alae2str: {self.alae2str}")

        self.blank = buffer.read(1)  # blank

        logging.debug(f"Reading headers at position {buffer.tell()}")
        self.header1 = int.from_bytes(buffer.read(4), "little")
        self.header2 = int.from_bytes(buffer.read(4), "little")
        logging.debug(f"header1: {self.header1}, header2: {self.header2}")

        self.version = int.from_bytes(buffer.read(4), "little")
        logging.debug(f"version: {self.version}")

        self.name_size = int.from_bytes(buffer.read(1), "little")
        logging.debug(f"name_size: {self.name_size}")

        name_bytes = buffer.read(self.name_size * 2)
        logging.debug(f"Reading name bytes: {name_bytes}")
        self.name = name_bytes.decode("utf-16le")
        logging.debug(f"name: {self.name}")

        self.class_index = int.from_bytes(buffer.read(4), byteorder="little")
        self.sub_class_index = int.from_bytes(buffer.read(4), byteorder="little")
        self.reserved1 = int.from_bytes(buffer.read(4), byteorder="little")
        self.reserved2 = int.from_bytes(buffer.read(4), byteorder="little")
        logging.debug(
            f"class_index: {self.class_index}, sub_class_index: {self.sub_class_index}, reserved1: {self.reserved1}, reserved2: {self.reserved2}"
        )

        self.color1 = int.from_bytes(buffer.read(4), "little")
        self.color2 = int.from_bytes(buffer.read(4), "little")
        self.color3 = int.from_bytes(buffer.read(4), "little")
        logging.debug(f"colors: {self.color1}, {self.color2}, {self.color3}")

        self.powers = []
        for i in range(10):
            length_bytes = buffer.read(1)
            if not length_bytes:
                logging.warning(f"Power {i} length missing at pos {buffer.tell()}")
                break
            length = int.from_bytes(length_bytes, "little")
            power_bytes = buffer.read(length)
            power = power_bytes.decode(self.encoding)
            level = int.from_bytes(buffer.read(4), "little")
            button_index = int.from_bytes(buffer.read(4), "little")
            self.powers.append((power, level, button_index))
            logging.debug(f"Power {i}: {power}, level {level}, index {button_index}")

        buffer.read(45)  # padding

        self.bling_number = int.from_bytes(buffer.read(4), "little")
        logging.debug(f"bling_number: {self.bling_number}")
        self.blings = []
        for i in range(self.bling_number):
            length = int.from_bytes(buffer.read(1), "little")
            bling_bytes = buffer.read(length)
            bling = bling_bytes.decode(self.encoding)
            index = int.from_bytes(buffer.read(4), "little")
            self.blings.append((bling, index))
            logging.debug(f"Bling {i}: {bling}, index {index}")

        self.something_length = int.from_bytes(buffer.read(1), "little")
        self.the_something = buffer.read(self.something_length).decode(self.encoding)
        logging.debug(f"the_something: {self.the_something}")

        is_system_byte = buffer.read(1)
        self.is_system = (
            bool(int.from_bytes(is_system_byte, "little")) if is_system_byte else False
        )
        logging.debug(f"is_system: {self.is_system}")

        checksum_bytes = buffer.read(4)
        self.checksum = checksum_bytes.hex() if checksum_bytes else None
        logging.debug(f"checksum: {self.checksum}")

    def write(self):
        buffer = io.BytesIO()

        logging.debug(f"Writing alae2str at position {buffer.tell()}: {self.alae2str}")
        buffer.write(self.alae2str.encode(self.encoding))

        logging.debug(f"Writing blank byte at position {buffer.tell()}")
        buffer.write(self.blank)

        logging.debug(
            f"Writing headers at position {buffer.tell()}: header1={self.header1}, header2={self.header2}, version={self.version}"
        )
        buffer.write(self.header1.to_bytes(4, "little"))
        buffer.write(self.header2.to_bytes(4, "little"))
        buffer.write(self.version.to_bytes(4, "little"))

        logging.debug(f"Writing name_size at position {buffer.tell()}: {self.name_size}")
        buffer.write(self.name_size.to_bytes(1, "little"))

        logging.debug(f"Writing name at position {buffer.tell()}: {self.name}")
        buffer.write(self.name.encode("utf-16le"))

        logging.debug(
            f"Writing class_index, sub_class_index, reserved1, reserved2 at position {buffer.tell()}: {self.class_index}, {self.sub_class_index}, {self.reserved1}, {self.reserved2}"
        )
        buffer.write(self.class_index.to_bytes(4, "little"))
        buffer.write(self.sub_class_index.to_bytes(4, "little"))
        buffer.write(self.reserved1.to_bytes(4, "little"))
        buffer.write(self.reserved2.to_bytes(4, "little"))

        logging.debug(
            f"Writing colors at position {buffer.tell()}: {self.color1}, {self.color2}, {self.color3}"
        )
        buffer.write(self.color1.to_bytes(4, "little"))
        buffer.write(self.color2.to_bytes(4, "little"))
        buffer.write(self.color3.to_bytes(4, "little"))

        logging.debug(f"Writing powers at position {buffer.tell()}")
        for i, power in enumerate(self.powers):
            logging.debug(f" Power {i}: {power}")
            buffer.write(len(power[0]).to_bytes(1, "little"))
            buffer.write(power[0].encode(self.encoding))
            buffer.write(power[1].to_bytes(4, "little"))
            buffer.write(power[2].to_bytes(4, "little"))

        logging.debug(f"Writing 45-byte padding at position {buffer.tell()}")
        buffer.write(b"\x00" * 45)

        logging.debug(f"Writing bling_number at position {buffer.tell()}: {self.bling_number}")
        buffer.write(self.bling_number.to_bytes(4, "little"))

        logging.debug(f"Writing blings at position {buffer.tell()}")
        for i, bling in enumerate(self.blings):
            logging.debug(f" Bling {i}: {bling}")
            buffer.write(len(bling[0]).to_bytes(1, "little"))
            buffer.write(bling[0].encode(self.encoding))
            buffer.write(bling[1].to_bytes(4, "little"))

        logging.debug(
            f"Writing something_length at position {buffer.tell()}: {self.something_length}"
        )
        buffer.write(self.something_length.to_bytes(1, "little"))

        logging.debug(f"Writing the_something at position {buffer.tell()}: {self.the_something}")
        buffer.write(self.the_something.encode(self.encoding))

        logging.debug(f"Writing is_system flag at position {buffer.tell()}: {self.is_system}")
        buffer.write(int(self.is_system).to_bytes(1, "little"))

        # this is not correct but I don't know if it matters
        # to investigate later
        # https://github.com/withmorten/cah_file/blob/master/src/cah_file.cpp#L312
        data_bytes = buffer.getvalue()
        checksum = sum(data_bytes) & 0xFFFFFFFF
        logging.debug(f"Writing checksum at position {buffer.tell()}: {checksum:#010x}")
        buffer.write(checksum.to_bytes(4, "little"))

        return buffer.getvalue()


class CustomHeroTab(GenericTab):
    def __init__(self, main, archive, name, preview):
        super().__init__(main, archive, name, preview)

        self.warned_about_editing = False

    def generate_layout(self):
        layout = QHBoxLayout()
        try:
            self.hero = CustomHero(self.data, self.main.settings.encoding)
        except Exception:
            traceback_text = traceback.format_exc()
            layout.addWidget(QLabel(traceback_text))
            self.setLayout(layout)
            return

        # Left panel for info
        left_layout = QVBoxLayout()
        self.name_edit = QLineEdit(self.hero.name)
        left_layout.addWidget(QLabel("Hero Name:"))
        left_layout.addWidget(self.name_edit)

        self.color1_edit = QLineEdit(str(self.hero.color1))
        self.color2_edit = QLineEdit(str(self.hero.color2))
        self.color3_edit = QLineEdit(str(self.hero.color3))
        left_layout.addWidget(QLabel("Colors:"))
        left_layout.addWidget(self.color1_edit)
        left_layout.addWidget(self.color2_edit)
        left_layout.addWidget(self.color3_edit)

        # Powers Table
        self.powers_table = QTableWidget()
        self.powers_table.setColumnCount(3)
        self.powers_table.setHorizontalHeaderLabels(["Power", "Level", "Button Index"])
        self.powers_table.setRowCount(len(self.hero.powers))
        for row, (power, level, index) in enumerate(self.hero.powers):
            self.powers_table.setItem(row, 0, QTableWidgetItem(power))
            self.powers_table.setItem(row, 1, QTableWidgetItem(str(level)))
            self.powers_table.setItem(row, 2, QTableWidgetItem(str(index)))
        self.powers_table.resizeColumnsToContents()
        self.powers_table.horizontalHeader().setStretchLastSection(True)

        left_layout.addWidget(QLabel("Powers:"))
        left_layout.addWidget(self.powers_table)

        # Blings Table
        self.blings_table = QTableWidget()
        self.blings_table.setColumnCount(2)
        self.blings_table.setHorizontalHeaderLabels(["Bling", "Index"])
        self.blings_table.setRowCount(len(self.hero.blings))
        for row, (bling, index) in enumerate(self.hero.blings):
            self.blings_table.setItem(row, 0, QTableWidgetItem(bling))
            self.blings_table.setItem(row, 1, QTableWidgetItem(str(index)))
        self.blings_table.resizeColumnsToContents()
        self.blings_table.horizontalHeader().setStretchLastSection(True)

        left_layout.addWidget(QLabel("Blings:"))
        left_layout.addWidget(self.blings_table)

        # Save button
        save_btn = QPushButton("Save .cah")
        save_btn.clicked.connect(self.save)
        left_layout.addWidget(save_btn)

        layout.addLayout(left_layout)
        self.setLayout(layout)

        if not self.preview:
            self.show_edit_warning()

        for line_edit in [self.name_edit, self.color1_edit, self.color2_edit, self.color3_edit]:
            line_edit.textChanged.connect(self.become_unsaved)

        self.powers_table.cellChanged.connect(self.become_unsaved)
        self.blings_table.cellChanged.connect(self.become_unsaved)

    def generate_preview(self):
        self.generate_layout()
        self.set_layout_read_only(self.layout())

    def show_edit_warning(self):
        if not self.warned_about_editing:
            QMessageBox.warning(
                self,
                "Warning",
                "Editing a .cah file can break it if you don't know what you're doing!\n"
                "Proceed with caution.",
            )
            self.warned_about_editing = True

    def save(self):
        try:
            if self.external:
                with open(self.path, "rb") as f:
                    cah_bytes = f.read()
            else:
                # Update hero info from UI
                self.hero.name = self.name_edit.text()
                self.hero.color1 = int(self.color1_edit.text())
                self.hero.color2 = int(self.color2_edit.text())
                self.hero.color3 = int(self.color3_edit.text())

                # Update powers
                new_powers = []
                for row in range(self.powers_table.rowCount()):
                    power = self.powers_table.item(row, 0).text()
                    level = int(self.powers_table.item(row, 1).text())
                    index = int(self.powers_table.item(row, 2).text())
                    new_powers.append((power, level, index))
                self.hero.powers = new_powers

                # Update blings
                new_blings = []
                for row in range(self.blings_table.rowCount()):
                    bling = self.blings_table.item(row, 0).text()
                    index = int(self.blings_table.item(row, 1).text())
                    new_blings.append((bling, index))
                self.hero.blings = new_blings

                # Generate bytes and save
                cah_bytes = self.hero.write()

            self.archive.edit_file(self.name, cah_bytes)
            super().save()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def set_layout_read_only(self, layout: QLayout, read_only=True):
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget()
            if widget:
                # For text input fields
                if isinstance(widget, (QLineEdit, QTextEdit)):
                    widget.setReadOnly(read_only)
                # For tables
                elif isinstance(widget, QTableWidget):
                    widget.setEditTriggers(
                        QTableWidget.EditTrigger.NoEditTriggers
                        if read_only
                        else QTableWidget.EditTrigger.AllEditTriggers
                    )
                # For buttons, optionally disable them
                elif isinstance(widget, QPushButton):
                    widget.setDisabled(read_only)
            # If the item is a nested layout, recurse
            elif item.layout():
                self.set_layout_read_only(item.layout(), read_only)

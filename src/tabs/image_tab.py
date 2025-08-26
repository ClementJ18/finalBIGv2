import io
import struct
import traceback

from PIL import Image
from PIL.ImageQt import ImageQt
from pyBIG.base_archive import BaseArchive
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
)

from tabs.generic_tab import GenericTab


class ImageTab(GenericTab):
    def __init__(self, main: QMainWindow, archive: BaseArchive, name, preview):
        super().__init__(main, archive, name, preview)

        self.scale = 1
        self.image = None
        self.qimage = None
        self.pixmap = None
        self.image_label = None
        self.showing_alpha = False

    @staticmethod
    def _get_dds_mipmap_count(dds_data: bytes) -> int:
        if len(dds_data) < 32:
            return 1

        dwFlags = struct.unpack_from("<I", dds_data, 8)[0]
        if dwFlags & 0x20000:
            return struct.unpack_from("<I", dds_data, 28)[0]

        return 1

    @staticmethod
    def _get_dds_format(dds_data: bytes) -> str:
        if len(dds_data) < 88:
            return "N/A"

        if struct.unpack_from("<I", dds_data, 80)[0] & 0x4:
            return (
                struct.unpack_from("<4s", dds_data, 84)[0].decode("ascii", errors="ignore").strip()
            )
        else:
            return "Uncompressed"

    def generate_layout(self):
        main_layout = QVBoxLayout(self)
        self.image_label = QLabel(self)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.image_label)
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        controls_layout = QHBoxLayout()

        self.alpha_button = QPushButton("Show Alpha")
        self.alpha_button.clicked.connect(self.toggle_alpha_view)
        controls_layout.addWidget(self.alpha_button)

        main_layout.addLayout(controls_layout)

        try:
            self.image = Image.open(io.BytesIO(self.data))

            if self.image.mode not in ("RGBA", "LA"):
                self.alpha_button.setEnabled(False)

            width, height = self.image.size
            controls_layout.addWidget(QLabel(f"<b>Dimensions:</b> {width}x{height}"))

            if self.file_type == ".tga":
                bit_depth = {"RGBA": "32-bit", "RGB": "24-bit"}.get(self.image.mode, "N/A")
                controls_layout.addWidget(QLabel(f"<b>Format:</b> {bit_depth}"))
            elif self.file_type == ".dds":
                controls_layout.addWidget(
                    QLabel(f"<b>Format:</b> {self._get_dds_format(self.data)}")
                )
                controls_layout.addWidget(
                    QLabel(f"<b>Mipmaps:</b> {self._get_dds_mipmap_count(self.data)}")
                )

            controls_layout.addStretch()
            self.update_display()
        except Exception as e:
            error_box = QTextEdit(self)
            error_box.setReadOnly(True)
            error_box.setText(f"Couldn't display image:\n{e}\n\n{traceback.format_exc()}")
            main_layout.addWidget(error_box)

    def toggle_alpha_view(self):
        self.showing_alpha = not self.showing_alpha
        self.update_display()

    def update_display(self):
        if not self.image:
            return

        display_image = self.image.getchannel("A") if self.showing_alpha else self.image
        self.alpha_button.setText("Show Color" if self.showing_alpha else "Show Alpha")
        self.qimage = ImageQt(display_image)
        self.pixmap = QPixmap.fromImage(self.qimage)
        self.image_label.setPixmap(self.pixmap)

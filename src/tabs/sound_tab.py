import shutil
import tempfile

import audio_metadata
import playsound
import tbm_utils
from PyQt6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout

from tabs.generic_tab import GenericTab


class SoundTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()

        with tempfile.NamedTemporaryFile(delete=False, suffix=self.file_type) as f:
            f.write(self.data)
            self.path = f.name

        play_button = QPushButton(self)
        play_button.setText("Play")
        play_button.clicked.connect(self.play_audio)
        layout.addWidget(play_button)

        metadata = audio_metadata.loads(self.data)

        data = QTextEdit(self)
        data.setReadOnly(True)
        data.setText(
            f"""
            File: {self.name}
            Size: {tbm_utils.humanize_filesize(metadata.filesize)}
            Duration: {tbm_utils.humanize_duration(metadata.streaminfo.duration)}
            """
        )

        layout.addWidget(data)
        layout.addWidget(self.generate_controller())
        self.setLayout(layout)

    def play_audio(self):
        playsound.playsound(self.path, False)

    def deleteLater(self) -> None:
        shutil.rmtree(self.path, True)
        return super().deleteLater()

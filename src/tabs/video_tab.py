import shutil
import tempfile

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout

from tabs.generic_tab import GenericTab

AUDIO_MEDIA_TYPES = (
    ".mp3",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",
    ".m4a",
    ".opus",
    ".wma",
    ".aiff",
    ".amr",
    ".mid",
    ".midi",
    ".au",
    ".ra",
    ".mp2",
)

VIDEO_MEDIA_TYPES = (
    ".mp4",
    ".m4v",
    ".avi",
    ".mkv",
    ".mov",
    ".flv",
    ".webm",
    ".ts",
    ".m2ts",
    ".ogv",
    ".wmv",
    ".3gp",
    ".3g2",
    ".asf",
    ".mxf",
)

MULTIE_MEDIA_TYPES = AUDIO_MEDIA_TYPES + VIDEO_MEDIA_TYPES


class VideoTab(GenericTab):
    def __init__(self, main, archive, name, preview):
        super().__init__(main, archive, name, preview)
        self.player = None
        self.audio_output = None
        self.path = None
        self.slider_being_dragged = False
        self.has_video = False

    def generate_layout(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        with tempfile.NamedTemporaryFile(delete=False, suffix=self.file_type) as f:
            f.write(self.data)
            self.path = f.name

        self.video_frame = QVideoWidget()
        layout.addWidget(self.video_frame, stretch=1)

        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_frame)
        self.player.setSource(QUrl.fromLocalFile(self.path))

        if self.file_type.lower() in AUDIO_MEDIA_TYPES:
            self.has_video = False
            self.video_frame.hide()
        else:
            self.has_video = True
            self.video_frame.show()

        control_layout = QHBoxLayout()
        layout.addLayout(control_layout)

        self.play_pause_button = QPushButton("Play")
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        control_layout.addWidget(self.play_pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop)
        control_layout.addWidget(self.stop_button)

        slider_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.total_time_label = QLabel("00:00")
        slider_layout.addWidget(self.current_time_label)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.sliderPressed.connect(self.start_slider_drag)
        self.slider.sliderReleased.connect(self.end_slider_drag)
        self.slider.sliderMoved.connect(self.drag_slider)
        slider_layout.addWidget(self.slider)

        slider_layout.addWidget(self.total_time_label)
        layout.addLayout(slider_layout)

        layout.addWidget(self.generate_controller())

        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.update_slider)
        self.timer.start()

    def toggle_play_pause(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.play_pause_button.setText("Play")
        else:
            self.player.play()
            self.play_pause_button.setText("Pause")

    def stop(self):
        self.player.stop()
        self.play_pause_button.setText("Play")

    def start_slider_drag(self):
        self.slider_being_dragged = True

    def end_slider_drag(self):
        self.slider_being_dragged = False
        self.set_position(self.slider.value())

    def drag_slider(self, value):
        if self.player is None:
            return
        pos = int(value / 1000.0 * self.player.duration())
        self.player.setPosition(pos)
        self.update_time_labels(pos, self.player.duration())

    def set_position(self, position):
        if self.player is None:
            return
        pos = int(position / 1000.0 * self.player.duration())
        self.player.setPosition(pos)
        self.update_time_labels(pos, self.player.duration())

    def update_slider(self):
        if self.player is None or self.player.duration() == 0 or self.slider_being_dragged:
            return
        pos = int(self.player.position() / self.player.duration() * 1000)
        self.slider.setValue(pos)
        self.update_time_labels(self.player.position(), self.player.duration())

    def update_time_labels(self, position_ms, duration_ms):
        self.current_time_label.setText(self.format_time(position_ms))
        self.total_time_label.setText(self.format_time(duration_ms))

    @staticmethod
    def format_time(ms):
        seconds = ms // 1000
        mins = seconds // 60
        secs = seconds % 60
        return f"{mins:02}:{secs:02}"

    def deleteLater(self) -> None:
        if self.player is not None:
            self.player.stop()
            try:
                shutil.rmtree(self.path, True)
            except Exception:
                pass
        return super().deleteLater()

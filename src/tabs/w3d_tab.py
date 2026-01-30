import io
import math

import pyBIG
from OpenGL.GL import (
    GL_AMBIENT,
    GL_AMBIENT_AND_DIFFUSE,
    GL_CLAMP_TO_EDGE,
    GL_COLOR_BUFFER_BIT,
    GL_COLOR_MATERIAL,
    GL_CULL_FACE,
    GL_DEPTH_BUFFER_BIT,
    GL_DEPTH_TEST,
    GL_DIFFUSE,
    GL_FRONT_AND_BACK,
    GL_LIGHT0,
    GL_LIGHTING,
    GL_LINEAR,
    GL_MODELVIEW,
    GL_POSITION,
    GL_PROJECTION,
    GL_RGBA,
    GL_TEXTURE_2D,
    GL_TEXTURE_MAG_FILTER,
    GL_TEXTURE_MIN_FILTER,
    GL_TEXTURE_WRAP_S,
    GL_TEXTURE_WRAP_T,
    GL_TRIANGLES,
    GL_UNSIGNED_BYTE,
    glBegin,
    glBindTexture,
    glClear,
    glClearColor,
    glColorMaterial,
    glDisable,
    glEnable,
    glEnd,
    glGenTextures,
    glLightfv,
    glLoadIdentity,
    glMatrixMode,
    glNormal3f,
    glRotatef,
    glTexCoord2f,
    glTexImage2D,
    glTexParameteri,
    glTranslatef,
    glVertex3f,
    glViewport,
)
from OpenGL.GLU import gluPerspective
from PIL import Image
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent, QWheelEvent
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from model.common.structs.data_context import DataContext
from model.w3d.import_w3d import load_file
from tabs.generic_tab import GenericTab


class GLWidget(QOpenGLWidget):
    def __init__(self, parent, data_context: DataContext, subobject_data):
        super().__init__(parent)
        self.data_context = data_context
        self.subobject_data = subobject_data
        self.meshes = []
        self.rot_x = 0
        self.rot_y = 0
        self.zoom = -50.0
        self.bbox_center = (0.0, 0.0, 0.0)
        self.last_mouse_pos = None
        self.textures = {
            subobject["name"]: {"texture": None, "file_name": subobject["texture"]}
            for subobject in subobject_data
        }

        self.lighting_preset = "Default"
        self.subobject_visibility = {}

        self.camera_presets = {
            "front": (0, 0),
            "back": (0, 180),
            "left": (0, -90),
            "right": (0, 90),
            "top": (-90, 0),
            "bottom": (90, 0),
        }

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.compute_bounding_box()

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_CULL_FACE)
        glClearColor(0.2, 0.2, 0.2, 1.0)

        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glLightfv(GL_LIGHT0, GL_POSITION, [0.5, 1.0, 1.0, 0.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, w / max(h, 1), 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        self._apply_lighting()

        glTranslatef(0, 0, self.zoom)
        glTranslatef(self.bbox_center[0], self.bbox_center[1], self.bbox_center[2])

        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)

        glTranslatef(-self.bbox_center[0], -self.bbox_center[1], -self.bbox_center[2])

        for mesh in self.data_context.meshes:
            mesh_name = mesh.name()
            if mesh_name and mesh_name in self.subobject_visibility:
                if not self.subobject_visibility[mesh_name]:
                    continue

            if self.textures.get(mesh_name, {}).get("texture") is not None:
                glEnable(GL_TEXTURE_2D)
                glBindTexture(GL_TEXTURE_2D, self.textures[mesh_name]["texture"])
            else:
                glDisable(GL_TEXTURE_2D)

            if mesh.material_passes[0].tx_coords:
                tx_coords = mesh.material_passes[0].tx_coords
            else:
                tx_coords = mesh.material_passes[0].tx_stages[0].tx_coords[0]

            glBegin(GL_TRIANGLES)
            for tri in mesh.triangles:
                for idx in tri.vert_ids:
                    uv = tx_coords[idx]
                    v = mesh.verts[idx]
                    n = tri.normal
                    glTexCoord2f(uv.x, uv.y)
                    glNormal3f(n.x, n.y, n.z)
                    glVertex3f(v.x, v.y, v.z)

            glEnd()

    def compute_bounding_box(self):
        if not self.data_context.meshes:
            return

        min_x = min_y = min_z = float("inf")
        max_x = max_y = max_z = float("-inf")

        for mesh in self.data_context.meshes:
            for v in mesh.verts:
                min_x = min(min_x, v.x)
                max_x = max(max_x, v.x)
                min_y = min(min_y, v.y)
                max_y = max(max_y, v.y)
                min_z = min(min_z, v.z)
                max_z = max(max_z, v.z)

        self.bbox_center = (
            (min_x + max_x) / 2,
            (min_y + max_y) / 2,
            (min_z + max_z) / 2,
        )

        max_dim = max(max_x - min_x, max_y - min_y, max_z - min_z)
        fov = 45.0
        padding = 1.5
        self.zoom = -max_dim * padding / (2 * math.tan(math.radians(fov / 2)))

        self.rot_x = 0
        self.rot_y = 0

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            self.rot_y -= 5
        elif event.key() == Qt.Key.Key_Right:
            self.rot_y += 5
        elif event.key() == Qt.Key.Key_Up:
            self.rot_x -= 5
        elif event.key() == Qt.Key.Key_Down:
            self.rot_x += 5
        elif event.key() in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_PageUp):
            self.zoom += 2.0
            self.zoom = min(-5.0, self.zoom)
        elif event.key() in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_PageDown):
            self.zoom -= 2.0
            self.zoom = max(-400.0, self.zoom)
        self.update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last_mouse_pos = event.position()
        self.setFocus()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.last_mouse_pos is None:
            return

        pos = event.position()
        dx = pos.x() - self.last_mouse_pos.x()
        dy = pos.y() - self.last_mouse_pos.y()

        self.rot_x += dy * 0.5
        self.rot_y += dx * 0.5

        self.last_mouse_pos = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.last_mouse_pos = None

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y() / 120
        self.zoom += delta * 2.0
        self.zoom = min(-5.0, max(-400.0, self.zoom))
        self.update()

    def set_camera_preset(self, preset_name: str):
        if preset_name in self.camera_presets:
            self.rot_x, self.rot_y = self.camera_presets[preset_name]
            self.update()

    def reset_camera(self):
        self.compute_bounding_box()
        self.update()

    def set_lighting(self, preset: str):
        self.lighting_preset = preset
        self.update()

    def _apply_lighting(self):
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)

        if self.lighting_preset == "Default":
            glLightfv(GL_LIGHT0, GL_POSITION, [0.5, 1.0, 1.0, 0.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.2, 0.2, 0.2, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.8, 1.0])

        elif self.lighting_preset == "Bright":
            glLightfv(GL_LIGHT0, GL_POSITION, [0.5, 1.0, 1.0, 0.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.4, 0.4, 0.4, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])

        elif self.lighting_preset == "Moody":
            glLightfv(GL_LIGHT0, GL_POSITION, [-0.2, 0.5, 0.2, 0.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.05, 0.05, 0.1, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.3, 0.3, 0.5, 1.0])

        elif self.lighting_preset == "Top Light":
            glLightfv(GL_LIGHT0, GL_POSITION, [0.0, 2.0, 0.0, 0.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.1, 0.1, 0.1, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.8, 0.8, 0.7, 1.0])

        elif self.lighting_preset == "Side Light":
            glLightfv(GL_LIGHT0, GL_POSITION, [2.0, 0.0, 0.0, 0.0])
            glLightfv(GL_LIGHT0, GL_AMBIENT, [0.1, 0.1, 0.1, 1.0])
            glLightfv(GL_LIGHT0, GL_DIFFUSE, [0.7, 0.8, 0.8, 1.0])

    def load_texture(self, image_data: bytes) -> int:
        """Load a texture from file and return texture ID."""
        texture_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, texture_id)

        img = Image.open(io.BytesIO(image_data))
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img_data = img.convert("RGBA").tobytes()

        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            img.width,
            img.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            img_data,
        )

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

        return texture_id


class W3DTab(GenericTab):
    def generate_layout(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        # all credit goes to the OpenSage team for their blender plugin
        # https://github.com/OpenSAGE/OpenSAGE.BlenderPlugin
        # I just stripped it down to be read-only and removed
        # blender specific code
        self.context = DataContext()
        load_file(self.context, self.data)
        self.subobject_data = self._get_subobject_data()

        top_row = QHBoxLayout()

        self.gl_widget = GLWidget(self, self.context, self.subobject_data)
        top_row.addWidget(self.gl_widget, stretch=1)

        self.info_box = self._create_info_box()
        top_row.addWidget(self.info_box)

        layout.addLayout(top_row)

        control_bar = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")
        control_bar.addWidget(zoom_in_btn)
        control_bar.addWidget(zoom_out_btn)

        zoom_in_btn.clicked.connect(self._zoom_in)
        zoom_out_btn.clicked.connect(self._zoom_out)

        preset_combo = QComboBox()
        preset_combo.addItems(["Front", "Back", "Left", "Right", "Top", "Bottom"])
        preset_combo.currentTextChanged.connect(
            lambda text: self.gl_widget.set_camera_preset(text.lower())
        )
        control_bar.addWidget(preset_combo)

        self.light_combo = QComboBox()
        self.light_combo.addItems(["Default", "Bright", "Moody", "Top Light", "Side Light"])
        control_bar.addWidget(self.light_combo)

        reset_light_btn = QPushButton("Reset Light")
        control_bar.addWidget(reset_light_btn)
        self.light_combo.currentIndexChanged.connect(self._change_lighting)
        reset_light_btn.clicked.connect(self._reset_light)

        reset_btn = QPushButton("Reset Camera")
        reset_btn.clicked.connect(self.gl_widget.reset_camera)
        control_bar.addWidget(reset_btn)

        layout.addLayout(control_bar)
        return layout

    def _create_info_box(self):
        """Create a collapsible info box with a toggle button."""
        info_container = QGroupBox("Object Info")
        info_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        info_container.setMaximumWidth(250)
        info_container.setMinimumWidth(200)

        info_layout = QVBoxLayout()
        info_container.setLayout(info_layout)

        self.info_label = QLabel("Object information will be displayed here.")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(self.info_label)

        subobjects_header = QLabel("<b>SubObjects:</b>")
        info_layout.addWidget(subobjects_header)

        if self.subobject_data:
            self.subobject_checkboxes = {}
            self.texture_buttons = {}
            for subobject in self.subobject_data:
                checkbox = QCheckBox(subobject["name"], info_container)
                checkbox.setChecked(True)
                checkbox.stateChanged.connect(
                    lambda state, n=subobject["name"]: self._toggle_subobject(n, state)
                )
                info_layout.addWidget(checkbox)
                self.subobject_checkboxes[subobject["name"]] = checkbox
                self.gl_widget.subobject_visibility[subobject["name"]] = True

                texture_row = QHBoxLayout()
                texture_label = QLabel(f"  - {subobject['texture']}")
                texture_label.setWordWrap(True)
                texture_row.addWidget(texture_label, stretch=1)

                load_texture_btn = QPushButton("+")
                load_texture_btn.setMaximumWidth(25)
                load_texture_btn.setMaximumHeight(20)
                load_texture_btn.setStyleSheet("background-color: red; color: white;")
                load_texture_btn.clicked.connect(
                    lambda _, name=subobject["name"]: self._load_texture_for_subobject(name)
                )
                texture_row.addWidget(load_texture_btn)

                self.texture_buttons[subobject["name"]] = load_texture_btn

                info_layout.addLayout(texture_row)

        info_layout.addStretch()
        return info_container

    def _get_subobject_data(self):
        """Get list of subobject names from the data context."""
        subobjects = []

        for mesh in self.context.meshes:
            subobjects.append({"name": mesh.name(), "texture": mesh.textures[0].file})

        return subobjects

    def _toggle_subobject(self, name, state):
        """Toggle visibility of a subobject and re-render."""
        is_visible = state == Qt.CheckState.Checked.value
        self.gl_widget.subobject_visibility[name] = is_visible
        self.gl_widget.update()

    def _load_texture_for_subobject(self, subobject_name):
        """Prompt user to select a texture file for the subobject."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select texture for {subobject_name}",
            "",
            "Texture Files (*.dds *.tga);;BIG Archives (*.big);;All Files (*.*)",
        )

        if file_path:
            is_archive = file_path.lower().endswith(".big")
            if is_archive:
                texture_archive = pyBIG.InDiskArchive(file_path)
                loaded_count = 0

                archive_texture_map = {}
                for file in texture_archive.file_list():
                    if not file.lower().endswith((".dds", ".tga")):
                        continue
                    file_name = file.split("\\")[-1].lower()
                    texture_base_name = file_name.split(".")[0]
                    archive_texture_map[texture_base_name] = file

                for subobj_name, texture_info in self.gl_widget.textures.items():
                    texture_base_name = texture_info["file_name"].split(".")[0].lower()

                    if texture_base_name in archive_texture_map:
                        image_data = texture_archive.read_file(
                            archive_texture_map[texture_base_name]
                        )
                        texture_id = self.gl_widget.load_texture(image_data)
                        self.gl_widget.textures[subobj_name]["texture"] = texture_id
                        loaded_count += 1

                        if subobj_name in self.texture_buttons:
                            self.texture_buttons[subobj_name].setStyleSheet(
                                "background-color: green; color: white;"
                            )

                if loaded_count == 0:
                    QMessageBox.warning(
                        self, "No Textures Found", "No matching textures found in archive."
                    )
                elif loaded_count > 1:
                    QMessageBox.information(
                        self,
                        "Textures Loaded",
                        f"Successfully loaded {loaded_count} texture(s) from archive.",
                    )
            else:
                with open(file_path, "rb") as f:
                    image_data = f.read()
                    texture_id = self.gl_widget.load_texture(image_data)
                    self.gl_widget.textures[subobject_name]["texture"] = texture_id

                    if subobject_name in self.texture_buttons:
                        self.texture_buttons[subobject_name].setStyleSheet(
                            "background-color: green; color: white;"
                        )

        self.gl_widget.update()

    def _zoom_in(self):
        self.gl_widget.zoom += 5.0
        self.gl_widget.zoom = min(-5.0, self.gl_widget.zoom)
        self.gl_widget.update()

    def _zoom_out(self):
        self.gl_widget.zoom -= 5.0
        self.gl_widget.zoom = max(-400.0, self.gl_widget.zoom)
        self.gl_widget.update()

    def _change_lighting(self, index):
        preset = self.light_combo.currentText()
        self.gl_widget.set_lighting(preset)

    def _reset_light(self):
        self.light_combo.setCurrentIndex(0)
        self.gl_widget.set_lighting("Default")

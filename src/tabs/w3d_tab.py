import base64
import io
import math
import os

import numpy as np
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
    glMultMatrixf,
    glNormal3f,
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

# Constants
ROTATION_STEP = 5.0  # Degrees per arrow key press
MOUSE_SENSITIVITY = 0.5  # Mouse rotation sensitivity
ZOOM_STEP = 2.0  # Zoom increment
ZOOM_MIN = -5.0  # Minimum zoom distance
ZOOM_MAX = -400.0  # Maximum zoom distance
CAMERA_FOV = 45.0  # Field of view in degrees
CAMERA_PADDING = 1.5  # Bounding box padding multiplier

# Button styling
BUTTON_SIZE_SMALL = 25
BUTTON_HEIGHT_SMALL = 20
BUTTON_STYLE_UNLOADED = "background-color: red; color: white;"
BUTTON_STYLE_LOADED = "background-color: green; color: white;"


class TransformedVertex:
    """Lightweight vertex container for skinned vertices."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z


LIGHTING_PRESETS = {
    "Default": {
        "position": [0.5, 1.0, 1.0, 0.0],
        "ambient": [0.2, 0.2, 0.2, 1.0],
        "diffuse": [0.8, 0.8, 0.8, 1.0],
    },
    "Bright": {
        "position": [0.5, 1.0, 1.0, 0.0],
        "ambient": [0.4, 0.4, 0.4, 1.0],
        "diffuse": [1.0, 1.0, 1.0, 1.0],
    },
    "Moody": {
        "position": [-0.2, 0.5, 0.2, 0.0],
        "ambient": [0.05, 0.05, 0.1, 1.0],
        "diffuse": [0.3, 0.3, 0.5, 1.0],
    },
    "Top Light": {
        "position": [0.0, 2.0, 0.0, 0.0],
        "ambient": [0.1, 0.1, 0.1, 1.0],
        "diffuse": [0.8, 0.8, 0.7, 1.0],
    },
    "Side Light": {
        "position": [2.0, 0.0, 0.0, 0.0],
        "ambient": [0.1, 0.1, 0.1, 1.0],
        "diffuse": [0.7, 0.8, 0.8, 1.0],
    },
}


class GLWidget(QOpenGLWidget):
    def __init__(self, parent, data_context: DataContext, subobject_data):
        super().__init__(parent)
        self.data_context = data_context
        self.subobject_data = subobject_data
        self.rotation_matrix = np.eye(4, dtype=np.float32)
        self.zoom = -50.0
        self.bbox_center = (0.0, 0.0, 0.0)
        self.last_mouse_pos = None
        self.textures = {
            subobject["name"]: {
                "texture": None,
                "file_name": subobject["texture"],
                "image_data": None,
            }
            for subobject in subobject_data
        }

        self.lighting_preset = "Default"
        self.subobject_visibility = {}
        self.bone_transforms = []

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

        glMultMatrixf(self.rotation_matrix.T)

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

            material_pass = mesh.material_passes[0]

            tx_coords = []
            if material_pass.tx_coords:
                tx_coords = material_pass.tx_coords
            else:
                if material_pass.tx_stages and material_pass.tx_stages[0].tx_coords:
                    tx_coords = material_pass.tx_stages[0].tx_coords[0]

            use_skinning = self.bone_transforms and mesh.vert_infs
            base_vertices = mesh.verts
            normals = mesh.normals if mesh.normals else None

            glBegin(GL_TRIANGLES)
            for tri in mesh.triangles:
                for idx in tri.vert_ids:
                    uv = None
                    if tx_coords and idx < len(tx_coords):
                        uv = tx_coords[idx]

                    if use_skinning and idx < len(mesh.vert_infs):
                        influence = mesh.vert_infs[idx]
                        v = self.transform_vertex(
                            base_vertices[idx],
                            influence.bone_idx,
                            influence.bone_inf,
                            influence.xtra_idx,
                            influence.xtra_inf,
                        )
                    else:
                        v = mesh.verts_2[idx] if mesh.verts_2 else base_vertices[idx]

                    n = normals[idx] if normals and idx < len(normals) else tri.normal

                    if uv is not None:
                        glTexCoord2f(uv.x, uv.y)

                    glNormal3f(n.x, n.y, n.z)
                    glVertex3f(v.x, v.y, v.z)

            glEnd()

    def compute_bounding_box(self):
        if not self.data_context.meshes:
            return

        all_verts = []
        for mesh in self.data_context.meshes:
            for v in mesh.verts:
                all_verts.append([v.x, v.y, v.z])

        if not all_verts:
            return

        verts_array = np.array(all_verts)
        bbox_min = verts_array.min(axis=0)
        bbox_max = verts_array.max(axis=0)

        self.bbox_center = tuple((bbox_min + bbox_max) / 2)

        max_dim = np.max(bbox_max - bbox_min)
        self.zoom = -max_dim * CAMERA_PADDING / (2 * math.tan(math.radians(CAMERA_FOV / 2)))

        self.rotation_matrix = np.eye(4, dtype=np.float32)

    def _create_rotation_matrix_y(self, angle_deg):
        """Create a rotation matrix around the Y-axis."""
        rot = np.eye(4, dtype=np.float32)
        rad = np.radians(angle_deg)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        rot[0, 0] = cos_a
        rot[0, 2] = sin_a
        rot[2, 0] = -sin_a
        rot[2, 2] = cos_a
        return rot

    def _create_rotation_matrix_x(self, angle_deg):
        """Create a rotation matrix around the X-axis."""
        rot = np.eye(4, dtype=np.float32)
        rad = np.radians(angle_deg)
        cos_a, sin_a = np.cos(rad), np.sin(rad)
        rot[1, 1] = cos_a
        rot[1, 2] = -sin_a
        rot[2, 1] = sin_a
        rot[2, 2] = cos_a
        return rot

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()

        # Rotation key mappings: (axis_function, angle)
        rotation_keys = {
            Qt.Key.Key_Left: (self._create_rotation_matrix_y, ROTATION_STEP),
            Qt.Key.Key_Right: (self._create_rotation_matrix_y, -ROTATION_STEP),
            Qt.Key.Key_Up: (self._create_rotation_matrix_x, -ROTATION_STEP),
            Qt.Key.Key_Down: (self._create_rotation_matrix_x, ROTATION_STEP),
        }

        if key in rotation_keys:
            create_matrix, angle = rotation_keys[key]
            rot = create_matrix(angle)
            self.rotation_matrix = rot @ self.rotation_matrix
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal, Qt.Key.Key_PageUp):
            self.zoom = min(ZOOM_MIN, self.zoom + ZOOM_STEP)
        elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore, Qt.Key.Key_PageDown):
            self.zoom = max(ZOOM_MAX, self.zoom - ZOOM_STEP)

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

        if abs(dx) > 0.01 or abs(dy) > 0.01:
            rot_y = self._create_rotation_matrix_y(-dx * MOUSE_SENSITIVITY)
            rot_x = self._create_rotation_matrix_x(dy * MOUSE_SENSITIVITY)
            self.rotation_matrix = rot_y @ self.rotation_matrix @ rot_x

        self.last_mouse_pos = pos
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.last_mouse_pos = None

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y() / 120
        self.zoom += delta * ZOOM_STEP
        self.zoom = min(ZOOM_MIN, max(ZOOM_MAX, self.zoom))
        self.update()

    def set_camera_preset(self, preset_name: str):
        if preset_name in self.camera_presets:
            rot_x, rot_y = self.camera_presets[preset_name]
            self.rotation_matrix = np.eye(4, dtype=np.float32)

            rot_y_mat = self._create_rotation_matrix_y(rot_y)
            rot_x_mat = self._create_rotation_matrix_x(rot_x)

            self.rotation_matrix = rot_y_mat @ rot_x_mat
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

        preset = LIGHTING_PRESETS.get(self.lighting_preset, LIGHTING_PRESETS["Default"])
        glLightfv(GL_LIGHT0, GL_POSITION, preset["position"])
        glLightfv(GL_LIGHT0, GL_AMBIENT, preset["ambient"])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, preset["diffuse"])

    def compute_bone_transforms(self, hierarchy):
        """Compute world-space bone transformation matrices from hierarchy pivots."""
        if not hierarchy or not hierarchy.pivots:
            return []

        bone_transforms = []

        for i, pivot in enumerate(hierarchy.pivots):
            trans = np.eye(4)
            trans[0:3, 3] = [pivot.translation.x, pivot.translation.y, pivot.translation.z]

            q = pivot.rotation
            rot = np.eye(4)
            rot[0, 0] = 1 - 2 * q.y * q.y - 2 * q.z * q.z
            rot[0, 1] = 2 * q.x * q.y - 2 * q.z * q.w
            rot[0, 2] = 2 * q.x * q.z + 2 * q.y * q.w
            rot[1, 0] = 2 * q.x * q.y + 2 * q.z * q.w
            rot[1, 1] = 1 - 2 * q.x * q.x - 2 * q.z * q.z
            rot[1, 2] = 2 * q.y * q.z - 2 * q.x * q.w
            rot[2, 0] = 2 * q.x * q.z - 2 * q.y * q.w
            rot[2, 1] = 2 * q.y * q.z + 2 * q.x * q.w
            rot[2, 2] = 1 - 2 * q.x * q.x - 2 * q.y * q.y

            local_transform = trans @ rot

            if pivot.fixup_matrix is not None:
                local_transform = local_transform @ pivot.fixup_matrix

            if pivot.parent_id >= 0 and pivot.parent_id < len(bone_transforms):
                world_transform = bone_transforms[pivot.parent_id] @ local_transform
            else:
                world_transform = local_transform

            bone_transforms.append(world_transform)

        return bone_transforms

    def transform_vertex(self, vertex, bone_idx1, weight1, bone_idx2, weight2):
        """Apply bone transforms to a vertex with blending."""
        if not self.bone_transforms:
            return vertex

        v = np.array([vertex.x, vertex.y, vertex.z, 1.0])
        result = np.zeros(4)

        if bone_idx1 < len(self.bone_transforms):
            result += (self.bone_transforms[bone_idx1] @ v) * weight1

        if weight2 > 0 and bone_idx2 < len(self.bone_transforms):
            result += (self.bone_transforms[bone_idx2] @ v) * weight2

        return TransformedVertex(result[0], result[1], result[2])

    def _setup_texture_parameters(self):
        """Configure standard OpenGL texture parameters."""
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)

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

        self._setup_texture_parameters()

        return texture_id

    def set_subobject_visibility(self, name: str, visible: bool):
        """Set visibility for a specific subobject."""
        self.subobject_visibility[name] = visible
        self.update()

    def set_texture_for_subobject(self, name: str, image_data: bytes):
        """Load and assign a texture to a subobject."""
        if name in self.textures:
            texture_id = self.load_texture(image_data)
            self.textures[name]["texture"] = texture_id
            self.textures[name]["image_data"] = image_data
            self.update()

    def get_texture_info(self, name: str):
        """Get texture information for a subobject."""
        return self.textures.get(name)

    def get_all_textures(self):
        """Get all texture data for serialization."""
        return {name: info.copy() for name, info in self.textures.items()}

    def set_bone_transforms(self, bone_transforms):
        """Set bone transformation matrices."""
        self.bone_transforms = bone_transforms
        self.update()

    def adjust_zoom(self, delta: float):
        """Adjust zoom level by the given delta."""
        self.zoom += delta
        self.zoom = min(ZOOM_MIN, max(ZOOM_MAX, self.zoom))
        self.update()


class W3DTab(GenericTab):
    def _find_files_in_archive(self, archive, extensions, name_pattern=None):
        """Find files in archive matching extensions and optional name pattern.

        Args:
            archive: pyBIG archive object
            extensions: tuple of file extensions (e.g., ('.dds', '.tga'))
            name_pattern: optional substring to match in filename (case-insensitive)

        Returns:
            dict: mapping of base filename (without extension) to full file path
        """
        file_map = {}
        for file in archive.file_list():
            if not file.lower().endswith(extensions):
                continue

            file_name = os.path.basename(file)
            if name_pattern and name_pattern.lower() not in file_name.lower():
                continue

            base_name = file_name.split(".")[0].lower()
            file_map[base_name] = file
        return file_map

    def _decode_base64_data(self, encoded_data):
        """Safely decode base64 data, returning None on error."""
        try:
            return base64.b64decode(encoded_data)
        except Exception:
            return None

    def _get_base_filename(self, filename):
        """Extract base filename without extension (e.g., 'texture.dds' -> 'texture')."""
        return os.path.basename(filename).split(".")[0].lower()

    def _set_button_loaded(self, button_name):
        """Mark a button as loaded (green)."""
        if button_name in self.texture_buttons:
            self.texture_buttons[button_name].setStyleSheet(BUTTON_STYLE_LOADED)

    def _set_button_unloaded(self, button_name):
        """Mark a button as unloaded (red)."""
        if button_name in self.texture_buttons:
            self.texture_buttons[button_name].setStyleSheet(BUTTON_STYLE_UNLOADED)

    def _create_small_button(self, text, callback):
        """Create a small button with standard styling."""
        button = QPushButton(text)
        button.setMaximumWidth(BUTTON_SIZE_SMALL)
        button.setMaximumHeight(BUTTON_HEIGHT_SMALL)
        button.setStyleSheet(BUTTON_STYLE_UNLOADED)
        button.clicked.connect(callback)
        return button

    def _apply_skeleton_data(self, w3d_data, update_button=True):
        """Load skeleton from W3D data and update the GL widget.

        Args:
            w3d_data: Raw W3D file bytes
            update_button: Whether to update the skeleton button style

        Returns:
            bool: True if skeleton was loaded successfully
        """
        temp_context = DataContext()
        load_file(temp_context, w3d_data)

        if temp_context.hierarchy:
            self.context.hierarchy = temp_context.hierarchy
            self.skeleton_data = w3d_data
            bone_transforms = self.gl_widget.compute_bone_transforms(temp_context.hierarchy)
            self.gl_widget.set_bone_transforms(bone_transforms)
            if update_button and hasattr(self, "skeleton_button"):
                self.skeleton_button.setStyleSheet(BUTTON_STYLE_LOADED)
            return True
        return False

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
        self.skeleton_data = None

        top_row = QHBoxLayout()

        self.gl_widget = GLWidget(self, self.context, self.subobject_data)
        top_row.addWidget(self.gl_widget, stretch=1)

        self.info_box = self._create_info_box()
        top_row.addWidget(self.info_box)

        self._auto_load_skeleton()
        self._auto_load_textures()

        layout.addLayout(top_row)

        control_bar = QHBoxLayout()
        zoom_in_btn = QPushButton("Zoom In")
        zoom_out_btn = QPushButton("Zoom Out")
        control_bar.addWidget(zoom_in_btn)
        control_bar.addWidget(zoom_out_btn)

        zoom_in_btn.clicked.connect(lambda: self._zoom(5.0))
        zoom_out_btn.clicked.connect(lambda: self._zoom(-5.0))

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

        if self.subobject_data:
            subobjects_header = QLabel("<b>SubObjects:</b>")
            info_layout.addWidget(subobjects_header)

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
                self.gl_widget.set_subobject_visibility(subobject["name"], True)

                texture_row = QHBoxLayout()
                texture_label = QLabel(f"  - {subobject['texture']}")
                texture_label.setWordWrap(True)
                texture_row.addWidget(texture_label, stretch=1)

                load_texture_btn = self._create_small_button(
                    "+", lambda _, name=subobject["name"]: self.load_texture_for_subobject(name)
                )
                texture_row.addWidget(load_texture_btn)

                self.texture_buttons[subobject["name"]] = load_texture_btn

                info_layout.addLayout(texture_row)

        hierarchy_name = self.context.hlod.header.hierarchy_name if self.context.hlod else None
        if hierarchy_name:
            skeleton_header = QLabel("<b>Skeleton:</b>")
            info_layout.addWidget(skeleton_header)

            skeleton_row = QHBoxLayout()
            skeleton_label = QLabel(f"  {hierarchy_name}")
            skeleton_label.setWordWrap(True)
            skeleton_row.addWidget(skeleton_label, stretch=1)

            self.skeleton_button = self._create_small_button("+", self._load_skeleton)
            skeleton_row.addWidget(self.skeleton_button)

            info_layout.addLayout(skeleton_row)

        info_layout.addStretch()
        return info_container

    def _get_subobject_data(self):
        """Get list of subobject names from the data context."""
        subobjects = []

        for mesh in self.context.meshes:
            if mesh.textures:
                subobjects.append({"name": mesh.name(), "texture": mesh.textures[0].file})

        return subobjects

    def _toggle_subobject(self, name, state):
        """Toggle visibility of a subobject and re-render."""
        is_visible = state == Qt.CheckState.Checked.value
        self.gl_widget.set_subobject_visibility(name, is_visible)

    def load_texture_for_subobject(self, subobject_name):
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
                archive_texture_map = self._find_files_in_archive(
                    texture_archive, (".dds", ".tga")
                )

                loaded_count = 0
                for subobj_name in self.gl_widget.textures.keys():
                    texture_info = self.gl_widget.get_texture_info(subobj_name)
                    texture_base_name = self._get_base_filename(texture_info["file_name"])

                    if texture_base_name in archive_texture_map:
                        image_data = texture_archive.read_file(
                            archive_texture_map[texture_base_name]
                        )
                        self.gl_widget.set_texture_for_subobject(subobj_name, image_data)
                        loaded_count += 1
                        self._set_button_loaded(subobj_name)

                self._show_texture_load_result(loaded_count)
            else:
                with open(file_path, "rb") as f:
                    image_data = f.read()
                    self.gl_widget.set_texture_for_subobject(subobject_name, image_data)

                    self._set_button_loaded(subobject_name)

    def _show_texture_load_result(self, loaded_count):
        """Display appropriate message based on texture load results."""
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

    def _load_skeleton(self):
        """Prompt user to select a skeleton/hierarchy file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select skeleton/hierarchy file",
            "",
            "W3D Files (*.w3d);;BIG Archives (*.big);;All Files (*.*)",
        )

        if file_path:
            hierarchy_loaded = False
            is_archive = file_path.lower().endswith(".big")

            if is_archive:
                hierarchy_archive = pyBIG.InDiskArchive(file_path)
                hierarchy_name = (
                    self.context.hlod.header.hierarchy_name if self.context.hlod else None
                )

                if hierarchy_name:
                    skeleton_files = self._find_files_in_archive(
                        hierarchy_archive, (".w3d",), hierarchy_name
                    )

                    for file_path in skeleton_files.values():
                        w3d_data = hierarchy_archive.read_file(file_path)
                        if self._apply_skeleton_data(w3d_data):
                            hierarchy_loaded = True
                            break

                    if not hierarchy_loaded:
                        QMessageBox.warning(
                            self,
                            "Hierarchy Not Found",
                            f"Hierarchy '{hierarchy_name}' not found in archive.",
                        )
                else:
                    QMessageBox.warning(
                        self, "No Hierarchy Name", "Model does not specify a hierarchy name."
                    )
            else:
                with open(file_path, "rb") as f:
                    w3d_data = f.read()
                    hierarchy_loaded = self._apply_skeleton_data(w3d_data)
                    if not hierarchy_loaded:
                        QMessageBox.warning(
                            self,
                            "No Hierarchy Found",
                            "Selected file does not contain a hierarchy.",
                        )

            if hierarchy_loaded:
                self.skeleton_button.setStyleSheet(BUTTON_STYLE_LOADED)
                QMessageBox.information(
                    self,
                    "Skeleton Loaded",
                    f"Skeleton loaded with {len(self.context.hierarchy.pivots)} bones.",
                )

        self.gl_widget.update()

    def _auto_load_skeleton(self):
        """Automatically load skeleton from the same archive if it exists."""
        hierarchy_name = self.context.hlod.header.hierarchy_name if self.context.hlod else None

        if not hierarchy_name or not self.archive:
            return

        try:
            skeleton_files = self._find_files_in_archive(self.archive, (".w3d",), hierarchy_name)

            for file_path in skeleton_files.values():
                w3d_data = self.archive.read_file(file_path)
                if self._apply_skeleton_data(w3d_data):
                    break
        except (OSError, IOError) as e:
            pass
        except Exception:
            pass

    def _auto_load_textures(self):
        """Automatically load textures from the same archive if they exist."""
        if not self.archive:
            return

        try:
            archive_texture_map = self._find_files_in_archive(self.archive, (".dds", ".tga"))

            for subobj_name in self.gl_widget.textures.keys():
                texture_info = self.gl_widget.get_texture_info(subobj_name)
                texture_base_name = self._get_base_filename(texture_info["file_name"])

                if texture_base_name in archive_texture_map:
                    image_data = self.archive.read_file(archive_texture_map[texture_base_name])
                    self.gl_widget.set_texture_for_subobject(subobj_name, image_data)
                    self._set_button_loaded(subobj_name)
        except (OSError, IOError) as e:
            pass
        except Exception:
            pass

    def _zoom(self, delta):
        """Adjust zoom level by the given delta."""
        self.gl_widget.adjust_zoom(delta)

    def _change_lighting(self):
        """Update lighting based on current combo box selection."""
        preset = self.light_combo.currentText()
        self.gl_widget.set_lighting(preset)

    def _reset_light(self):
        self.light_combo.setCurrentIndex(0)
        self.gl_widget.set_lighting("Default")

    def to_dict(self) -> dict:
        textures_data = {}
        for subobj_name, texture_info in self.gl_widget.get_all_textures().items():
            if texture_info["texture"] is not None and texture_info["image_data"] is not None:
                textures_data[subobj_name] = {
                    "image_data": base64.b64encode(texture_info["image_data"]).decode("utf-8")
                }

        result = {"textures": textures_data}

        if self.skeleton_data is not None:
            result["skeleton"] = base64.b64encode(self.skeleton_data).decode("utf-8")

        return result

    def from_dict(self, data: dict):
        if "textures" in data:
            textures_data = data["textures"]
            for subobj_name, texture_info in textures_data.items():
                encoded_image = texture_info.get("image_data")

                if not encoded_image or self.gl_widget.get_texture_info(subobj_name) is None:
                    continue

                image_data = self._decode_base64_data(encoded_image)
                if image_data:
                    self.gl_widget.set_texture_for_subobject(subobj_name, image_data)
                    self._set_button_loaded(subobj_name)

        if "skeleton" in data:
            skeleton_data = self._decode_base64_data(data["skeleton"])
            if skeleton_data:
                self._apply_skeleton_data(skeleton_data)

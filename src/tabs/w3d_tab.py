import base64
import io
import math

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


class GLWidget(QOpenGLWidget):
    def __init__(self, parent, data_context: DataContext, subobject_data):
        super().__init__(parent)
        self.data_context = data_context
        self.subobject_data = subobject_data
        self.meshes = []
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
        self.bone_transforms = []  # Computed bone matrices for skinning

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

            if mesh.material_passes[0].tx_coords:
                tx_coords = mesh.material_passes[0].tx_coords
            else:
                tx_coords = mesh.material_passes[0].tx_stages[0].tx_coords[0]

            # Determine which vertices to use
            use_skinning = self.bone_transforms and mesh.vert_infs
            base_vertices = mesh.verts
            normals = mesh.normals if mesh.normals else None

            glBegin(GL_TRIANGLES)
            for tri in mesh.triangles:
                for idx in tri.vert_ids:
                    uv = tx_coords[idx]

                    # Apply skinning if skeleton is loaded
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
                        # Use bind pose or regular vertices
                        v = mesh.verts_2[idx] if mesh.verts_2 else base_vertices[idx]

                    # Use per-vertex normals if available, otherwise use triangle normal
                    n = normals[idx] if normals and idx < len(normals) else tri.normal
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

        self.rotation_matrix = np.eye(4, dtype=np.float32)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Left:
            angle = -5
            rot = np.eye(4, dtype=np.float32)
            rad = np.radians(angle)
            rot[0, 0] = np.cos(rad)
            rot[0, 2] = np.sin(rad)
            rot[2, 0] = -np.sin(rad)
            rot[2, 2] = np.cos(rad)
            self.rotation_matrix = rot @ self.rotation_matrix
        elif event.key() == Qt.Key.Key_Right:
            angle = 5
            rot = np.eye(4, dtype=np.float32)
            rad = np.radians(angle)
            rot[0, 0] = np.cos(rad)
            rot[0, 2] = np.sin(rad)
            rot[2, 0] = -np.sin(rad)
            rot[2, 2] = np.cos(rad)
            self.rotation_matrix = rot @ self.rotation_matrix
        elif event.key() == Qt.Key.Key_Up:
            angle = -5
            rot = np.eye(4, dtype=np.float32)
            rad = np.radians(angle)
            rot[1, 1] = np.cos(rad)
            rot[1, 2] = -np.sin(rad)
            rot[2, 1] = np.sin(rad)
            rot[2, 2] = np.cos(rad)
            self.rotation_matrix = rot @ self.rotation_matrix
        elif event.key() == Qt.Key.Key_Down:
            angle = 5
            rot = np.eye(4, dtype=np.float32)
            rad = np.radians(angle)
            rot[1, 1] = np.cos(rad)
            rot[1, 2] = -np.sin(rad)
            rot[2, 1] = np.sin(rad)
            rot[2, 2] = np.cos(rad)
            self.rotation_matrix = rot @ self.rotation_matrix
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

        if abs(dx) > 0.01 or abs(dy) > 0.01:
            angle_y = dx * 0.5
            rot_y = np.eye(4, dtype=np.float32)
            rad_y = np.radians(angle_y)
            rot_y[0, 0] = np.cos(rad_y)
            rot_y[0, 2] = np.sin(rad_y)
            rot_y[2, 0] = -np.sin(rad_y)
            rot_y[2, 2] = np.cos(rad_y)

            angle_x = dy * 0.5
            rot_x = np.eye(4, dtype=np.float32)
            rad_x = np.radians(angle_x)
            rot_x[1, 1] = np.cos(rad_x)
            rot_x[1, 2] = -np.sin(rad_x)
            rot_x[2, 1] = np.sin(rad_x)
            rot_x[2, 2] = np.cos(rad_x)

            self.rotation_matrix = rot_y @ self.rotation_matrix @ rot_x

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
            rot_x, rot_y = self.camera_presets[preset_name]
            self.rotation_matrix = np.eye(4, dtype=np.float32)

            rad_y = np.radians(rot_y)
            rot_y_mat = np.eye(4, dtype=np.float32)
            rot_y_mat[0, 0] = np.cos(rad_y)
            rot_y_mat[0, 2] = np.sin(rad_y)
            rot_y_mat[2, 0] = -np.sin(rad_y)
            rot_y_mat[2, 2] = np.cos(rad_y)

            rad_x = np.radians(rot_x)
            rot_x_mat = np.eye(4, dtype=np.float32)
            rot_x_mat[1, 1] = np.cos(rad_x)
            rot_x_mat[1, 2] = -np.sin(rad_x)
            rot_x_mat[2, 1] = np.sin(rad_x)
            rot_x_mat[2, 2] = np.cos(rad_x)

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

        class TransformedVertex:
            def __init__(self, x, y, z):
                self.x = x
                self.y = y
                self.z = z

        return TransformedVertex(result[0], result[1], result[2])

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
        self.skeleton_data = None

        top_row = QHBoxLayout()

        self.gl_widget = GLWidget(self, self.context, self.subobject_data)
        top_row.addWidget(self.gl_widget, stretch=1)

        self.info_box = self._create_info_box()
        top_row.addWidget(self.info_box)

        self._auto_load_skeleton()

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
                    lambda _, name=subobject["name"]: self.load_texture_for_subobject(name)
                )
                texture_row.addWidget(load_texture_btn)

                self.texture_buttons[subobject["name"]] = load_texture_btn

                info_layout.addLayout(texture_row)

        skeleton_header = QLabel("<b>Skeleton:</b>")
        info_layout.addWidget(skeleton_header)

        skeleton_row = QHBoxLayout()
        hierarchy_name = self.context.hlod.header.hierarchy_name if self.context.hlod else "None"
        skeleton_label = QLabel(f"  {hierarchy_name}")
        skeleton_label.setWordWrap(True)
        skeleton_row.addWidget(skeleton_label, stretch=1)

        load_skeleton_btn = QPushButton("+")
        load_skeleton_btn.setMaximumWidth(25)
        load_skeleton_btn.setMaximumHeight(20)
        load_skeleton_btn.setStyleSheet("background-color: red; color: white;")
        load_skeleton_btn.clicked.connect(self._load_skeleton)
        skeleton_row.addWidget(load_skeleton_btn)

        self.skeleton_button = load_skeleton_btn

        info_layout.addLayout(skeleton_row)

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
                        self.gl_widget.textures[subobj_name]["image_data"] = image_data
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
                    self.gl_widget.textures[subobject_name]["image_data"] = image_data

                    if subobject_name in self.texture_buttons:
                        self.texture_buttons[subobject_name].setStyleSheet(
                            "background-color: green; color: white;"
                        )

        self.gl_widget.update()

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
                    for file in hierarchy_archive.file_list():
                        if file.lower().endswith(".w3d"):
                            file_name = file.split("\\")[-1]
                            if hierarchy_name.lower() in file_name.lower():
                                w3d_data = hierarchy_archive.read_file(file)
                                temp_context = DataContext()
                                load_file(temp_context, w3d_data)

                                if temp_context.hierarchy:
                                    self.context.hierarchy = temp_context.hierarchy
                                    self.skeleton_data = w3d_data
                                    self.gl_widget.bone_transforms = (
                                        self.gl_widget.compute_bone_transforms(
                                            temp_context.hierarchy
                                        )
                                    )
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
                    temp_context = DataContext()
                    load_file(temp_context, w3d_data)

                    if temp_context.hierarchy:
                        self.context.hierarchy = temp_context.hierarchy
                        self.skeleton_data = w3d_data
                        self.gl_widget.bone_transforms = self.gl_widget.compute_bone_transforms(
                            temp_context.hierarchy
                        )
                        hierarchy_loaded = True
                    else:
                        QMessageBox.warning(
                            self,
                            "No Hierarchy Found",
                            "Selected file does not contain a hierarchy.",
                        )

            if hierarchy_loaded:
                self.skeleton_button.setStyleSheet("background-color: green; color: white;")
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
            for file in self.archive.file_list():
                if file.lower().endswith(".w3d"):
                    file_name = file.split("\\")[-1]
                    if hierarchy_name.lower() in file_name.lower():
                        w3d_data = self.archive.read_file(file)
                        temp_context = DataContext()
                        load_file(temp_context, w3d_data)

                        if temp_context.hierarchy:
                            self.context.hierarchy = temp_context.hierarchy
                            self.skeleton_data = w3d_data
                            self.gl_widget.bone_transforms = (
                                self.gl_widget.compute_bone_transforms(temp_context.hierarchy)
                            )
                            if hasattr(self, "skeleton_button"):
                                self.skeleton_button.setStyleSheet(
                                    "background-color: green; color: white;"
                                )
                            break
        except Exception as e:
            pass

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

    def to_dict(self) -> dict:
        textures_data = {}
        for subobj_name, texture_info in self.gl_widget.textures.items():
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

                if not encoded_image or subobj_name not in self.gl_widget.textures:
                    continue

                try:
                    image_data = base64.b64decode(encoded_image)
                    texture_id = self.gl_widget.load_texture(image_data)
                    self.gl_widget.textures[subobj_name]["texture"] = texture_id
                    self.gl_widget.textures[subobj_name]["image_data"] = image_data

                    if subobj_name in self.texture_buttons:
                        self.texture_buttons[subobj_name].setStyleSheet(
                            "background-color: green; color: white;"
                        )
                except Exception:
                    pass

        if "skeleton" in data:
            try:
                skeleton_data = base64.b64decode(data["skeleton"])
                temp_context = DataContext()
                load_file(temp_context, skeleton_data)

                if temp_context.hierarchy:
                    self.context.hierarchy = temp_context.hierarchy
                    self.skeleton_data = skeleton_data
                    self.gl_widget.bone_transforms = self.gl_widget.compute_bone_transforms(
                        temp_context.hierarchy
                    )

                    if hasattr(self, "skeleton_button"):
                        self.skeleton_button.setStyleSheet(
                            "background-color: green; color: white;"
                        )
            except Exception:
                pass

        self.gl_widget.update()

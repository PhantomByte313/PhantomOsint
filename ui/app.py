"""
ui/app.py
=========
Phantom OSINT — Main Application Window
Ultra-dark intelligence profiling tool.
"""

import os, sys, json
from typing import Optional, List
from PyQt6.QtCore  import Qt, QTimer, QSize, QPoint, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui   import (QColor, QFont, QPainter, QPen, QBrush, QPixmap,
                            QImage, QKeySequence, QShortcut, QIcon, QCursor)
from PyQt6.QtWidgets import (
    QWidget, QApplication, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox, QScrollArea,
    QFrame, QSizePolicy, QFileDialog, QMessageBox, QSplitter,
    QStackedWidget, QToolButton, QSpacerItem, QDialog, QFormLayout,
    QTabWidget, QListWidget, QListWidgetItem, QGraphicsDropShadowEffect,
    QInputDialog, QProgressBar
)

from core.database import Database, OSINTProfile, FIELD_GROUPS, ALL_FIELDS


# ── Palette ───────────────────────────────────────────────────────────────────
BG         = "#08080f"
BG2        = "#0d0d18"
BG3        = "#111120"
SURFACE    = "#13131f"
SURFACE2   = "#1a1a2e"
BORDER     = "#1e1e30"
BORDER2    = "#252538"
ACCENT     = "#7c6af7"
ACCENT2    = "#5b4fd4"
ACCENT_DIM = "#2a2450"
RED        = "#e05577"
GREEN      = "#3dd68c"
YELLOW     = "#e8c46a"
CYAN       = "#3ecfcf"
FG         = "#c8c8d4"
FG2        = "#7777908"
FG_DIM     = "#3a3a52"
FG_MED     = "#666680"

FONT_MAIN  = "IBM Plex Mono, Fira Code, Consolas, monospace"
FONT_UI    = "Segoe UI, SF Pro Text, system-ui, sans-serif"


def shadow(widget, radius=20, color="#7c6af7", opacity=60):
    e = QGraphicsDropShadowEffect()
    c = QColor(color)
    c.setAlpha(opacity)
    e.setColor(c)
    e.setBlurRadius(radius)
    e.setOffset(0, 0)
    widget.setGraphicsEffect(e)


# ─────────────────────────────────────────────────────────────────────────────
# Title Bar
# ─────────────────────────────────────────────────────────────────────────────

class TitleBar(QWidget):
    def __init__(self, win):
        super().__init__(win)
        self._win = win
        self._drag = None
        self.setFixedHeight(42)
        self.setStyleSheet(f"background:{BG}; border-bottom:1px solid {BORDER};")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 8, 0)
        lay.setSpacing(10)

        # Logo
        logo = QLabel("◈")
        logo.setStyleSheet(f"color:{ACCENT}; font-size:18px; font-family:{FONT_MAIN};")
        lay.addWidget(logo)

        title = QLabel("PHANTOM  OSINT")
        title.setStyleSheet(f"""
            color:{FG_MED}; font-size:11px; font-weight:700;
            letter-spacing:3px; font-family:{FONT_MAIN};
        """)
        lay.addWidget(title)
        lay.addStretch()

        # Stats
        self._stats = QLabel("0 هدف")
        self._stats.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-family:{FONT_UI};")
        lay.addWidget(self._stats)
        lay.addSpacing(16)

        for sym, tip, cb, name in [
            ("─", "تصغير",  win.showMinimized, "min"),
            ("□", "تكبير",  self._toggle_max,  "max"),
            ("✕", "إغلاق",  win.close,         "cls"),
        ]:
            b = QPushButton(sym)
            b.setFixedSize(34, 24)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(cb)
            close_style = f"QPushButton{{background:transparent;color:{FG_DIM};border:none;font-size:11px;}} QPushButton:hover{{background:#c0392b;color:white;}}" if name=="cls" else f"QPushButton{{background:transparent;color:{FG_DIM};border:none;font-size:11px;}} QPushButton:hover{{background:{SURFACE2};color:{FG};}}"
            b.setStyleSheet(close_style)
            lay.addWidget(b)

    def _toggle_max(self):
        self._win.showNormal() if self._win.isMaximized() else self._win.showMaximized()

    def set_stats(self, count: int):
        self._stats.setText(f"{count} هدف مسجّل")

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton and self._drag:
            self._win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self._toggle_max()


# ─────────────────────────────────────────────────────────────────────────────
# Profile Card (in the list panel)
# ─────────────────────────────────────────────────────────────────────────────

class ProfileCard(QWidget):
    clicked = pyqtSignal(int)  # profile id

    def __init__(self, profile: OSINTProfile, db: Database, parent=None):
        super().__init__(parent)
        self.profile = profile
        self._db = db
        self._active = False
        self.setFixedHeight(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        # Photo
        self._photo_lbl = QLabel()
        self._photo_lbl.setFixedSize(48, 48)
        self._photo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_lbl.setStyleSheet(f"""
            background:{SURFACE2}; border-radius:24px;
            color:{ACCENT}; font-size:20px;
        """)
        self._load_photo()
        lay.addWidget(self._photo_lbl)

        # Info
        info = QVBoxLayout()
        info.setSpacing(2)

        self._name_lbl = QLabel(self.profile.display_name())
        self._name_lbl.setStyleSheet(f"color:{FG}; font-size:13px; font-weight:600; font-family:{FONT_UI};")
        info.addWidget(self._name_lbl)

        sub = self.profile.get("phone_primary") or self.profile.get("email_primary") or self.profile.get("city") or "لا توجد بيانات"
        self._sub_lbl = QLabel(sub)
        self._sub_lbl.setStyleSheet(f"color:{FG_MED}; font-size:11px; font-family:{FONT_UI};")
        info.addWidget(self._sub_lbl)

        lay.addLayout(info, stretch=1)

        # Threat badge
        level = self.profile.get("threat_level")
        if level:
            badge = QLabel(level)
            color = self.profile.threat_color()
            badge.setStyleSheet(f"""
                color:{color}; font-size:9px; font-weight:700;
                border:1px solid {color}; border-radius:3px;
                padding:1px 5px; font-family:{FONT_UI}; letter-spacing:1px;
            """)
            lay.addWidget(badge)

        self._update_style()

    def _load_photo(self):
        data = self._db.load_photo(self.profile.id)
        if data:
            img = QImage.fromData(data)
            pix = QPixmap.fromImage(img).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
            # Circular crop
            rounded = QPixmap(48, 48)
            rounded.fill(Qt.GlobalColor.transparent)
            painter = QPainter(rounded)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QBrush(pix))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(0, 0, 48, 48)
            painter.end()
            self._photo_lbl.setPixmap(rounded)
        else:
            initials = self.profile.display_name()[:1].upper() or "?"
            self._photo_lbl.setText(initials)

    def set_active(self, active: bool):
        self._active = active
        self._update_style()

    def _update_style(self):
        if self._active:
            self.setStyleSheet(f"background:{ACCENT_DIM}; border-radius:6px; border-left:2px solid {ACCENT};")
        else:
            self.setStyleSheet(f"background:transparent; border-radius:6px; border-left:2px solid transparent;")

    def refresh(self, profile: OSINTProfile):
        self.profile = profile
        self._name_lbl.setText(profile.display_name())
        sub = profile.get("phone_primary") or profile.get("email_primary") or profile.get("city") or "لا توجد بيانات"
        self._sub_lbl.setText(sub)
        self._load_photo()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.profile.id)


# ─────────────────────────────────────────────────────────────────────────────
# Left Panel — Profile List
# ─────────────────────────────────────────────────────────────────────────────

class ProfileListPanel(QWidget):
    profile_selected = pyqtSignal(int)
    new_requested    = pyqtSignal()
    delete_requested = pyqtSignal(int)

    def __init__(self, db: Database):
        super().__init__()
        self._db = db
        self._cards: dict[int, ProfileCard] = {}
        self._active_id = None
        self.setFixedWidth(280)
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{BG2}; border-right:1px solid {BORDER};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{BG}; border-bottom:1px solid {BORDER};")
        h = QHBoxLayout(hdr)
        h.setContentsMargins(14, 0, 10, 0)

        lbl = QLabel("الأهداف")
        lbl.setStyleSheet(f"color:{FG_MED}; font-size:11px; font-weight:700; letter-spacing:2px; font-family:{FONT_UI};")
        h.addWidget(lbl)
        h.addStretch()

        self._add_btn = QPushButton("＋")
        self._add_btn.setFixedSize(30, 30)
        self._add_btn.setToolTip("هدف جديد")
        self._add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{background:{ACCENT_DIM}; color:{ACCENT}; border:none;
                         border-radius:6px; font-size:16px;}}
            QPushButton:hover {{background:{ACCENT}; color:white;}}
        """)
        self._add_btn.clicked.connect(self.new_requested)
        h.addWidget(self._add_btn)
        lay.addWidget(hdr)

        # Search
        search_wrap = QWidget()
        search_wrap.setFixedHeight(44)
        search_wrap.setStyleSheet(f"background:{BG2}; border-bottom:1px solid {BORDER};")
        sw = QHBoxLayout(search_wrap)
        sw.setContentsMargins(10, 6, 10, 6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  بحث...")
        self._search.setStyleSheet(f"""
            QLineEdit {{
                background:{SURFACE}; color:{FG}; border:1px solid {BORDER2};
                border-radius:5px; padding:4px 10px;
                font-size:12px; font-family:{FONT_UI};
            }}
            QLineEdit:focus {{ border-color:{ACCENT}; }}
        """)
        self._search.textChanged.connect(self._on_search)
        sw.addWidget(self._search)
        lay.addWidget(search_wrap)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{background:{BG2}; border:none;}}
            QScrollBar:vertical {{background:{BG2}; width:4px; border:none;}}
            QScrollBar::handle:vertical {{background:{BORDER2}; border-radius:2px;}}
        """)

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background:{BG2};")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(8, 8, 8, 8)
        self._list_layout.setSpacing(4)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        lay.addWidget(scroll, stretch=1)

        # Bottom count
        self._count_lbl = QLabel("لا يوجد أهداف")
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_lbl.setFixedHeight(28)
        self._count_lbl.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-family:{FONT_UI}; border-top:1px solid {BORDER};")
        lay.addWidget(self._count_lbl)

    def load_profiles(self, profiles: list):
        # Clear
        for card in self._cards.values():
            card.deleteLater()
        self._cards.clear()

        # Remove stretch
        item = self._list_layout.itemAt(self._list_layout.count() - 1)
        if item and item.spacerItem():
            self._list_layout.removeItem(item)

        for p in profiles:
            card = ProfileCard(p, self._db)
            card.clicked.connect(self._on_card_clicked)
            self._list_layout.addWidget(card)
            self._cards[p.id] = card

        self._list_layout.addStretch()

        n = len(profiles)
        self._count_lbl.setText(f"{n} هدف" if n else "لا يوجد أهداف")

    def set_active(self, profile_id: int):
        self._active_id = profile_id
        for pid, card in self._cards.items():
            card.set_active(pid == profile_id)

    def refresh_card(self, profile: OSINTProfile):
        if profile.id in self._cards:
            self._cards[profile.id].refresh(profile)

    def _on_card_clicked(self, profile_id: int):
        self.set_active(profile_id)
        self.profile_selected.emit(profile_id)

    def _on_search(self, text: str):
        for pid, card in self._cards.items():
            name = card.profile.display_name().lower()
            data = json.dumps(card.profile.data, ensure_ascii=False).lower()
            visible = text.lower() in name or text.lower() in data
            card.setVisible(visible)


# ─────────────────────────────────────────────────────────────────────────────
# Field Widget — renders a single input field
# ─────────────────────────────────────────────────────────────────────────────

class FieldWidget(QWidget):
    changed = pyqtSignal(str, str)  # key, value

    def __init__(self, key, label, ftype, options=None):
        super().__init__()
        self.key   = key
        self.ftype = ftype
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{FG_MED}; font-size:10px; font-weight:600; letter-spacing:0.5px; font-family:{FONT_UI};")
        lay.addWidget(lbl)

        base_style = f"""
            background:{SURFACE}; color:{FG}; border:1px solid {BORDER2};
            border-radius:5px; padding:6px 10px;
            font-size:12px; font-family:{FONT_UI};
            selection-background-color:{ACCENT_DIM};
        """
        focus_style = base_style + f"border-color:{ACCENT};"

        if ftype == "textarea":
            self._input = QTextEdit()
            self._input.setFixedHeight(72)
            self._input.setStyleSheet(f"QTextEdit{{{base_style}}} QTextEdit:focus{{{focus_style}}}")
            self._input.textChanged.connect(lambda: self.changed.emit(self.key, self._input.toPlainText()))
        elif ftype == "choice" and options:
            self._input = QComboBox()
            self._input.addItem("— اختر —", "")
            for opt in options:
                self._input.addItem(opt, opt)
            self._input.setStyleSheet(f"""
                QComboBox{{{base_style}}}
                QComboBox:focus{{{focus_style}}}
                QComboBox::drop-down{{border:none; width:20px;}}
                QComboBox QAbstractItemView{{
                    background:{SURFACE2}; color:{FG};
                    border:1px solid {BORDER2};
                    selection-background-color:{ACCENT_DIM};
                    outline:none;
                }}
            """)
            self._input.currentIndexChanged.connect(
                lambda: self.changed.emit(self.key, self._input.currentData() or "")
            )
        else:
            self._input = QLineEdit()
            ph_map = {
                "phone": "+966 5X XXX XXXX",
                "email": "user@example.com",
                "url":   "https://",
                "date":  "YYYY-MM-DD",
                "number": "0",
            }
            self._input.setPlaceholderText(ph_map.get(ftype, ""))
            self._input.setStyleSheet(f"QLineEdit{{{base_style}}} QLineEdit:focus{{{focus_style}}}")
            self._input.textChanged.connect(lambda v: self.changed.emit(self.key, v))

        lay.addWidget(self._input)

    def set_value(self, value: str):
        if isinstance(self._input, QTextEdit):
            self._input.blockSignals(True)
            self._input.setPlainText(value)
            self._input.blockSignals(False)
        elif isinstance(self._input, QComboBox):
            idx = self._input.findData(value)
            self._input.blockSignals(True)
            self._input.setCurrentIndex(max(0, idx))
            self._input.blockSignals(False)
        else:
            self._input.blockSignals(True)
            self._input.setText(value)
            self._input.blockSignals(False)

    def get_value(self) -> str:
        if isinstance(self._input, QTextEdit):
            return self._input.toPlainText()
        elif isinstance(self._input, QComboBox):
            return self._input.currentData() or ""
        return self._input.text()


# ─────────────────────────────────────────────────────────────────────────────
# Profile Editor — right panel with all fields
# ─────────────────────────────────────────────────────────────────────────────

class ProfileEditor(QWidget):
    profile_saved   = pyqtSignal(OSINTProfile)
    profile_deleted = pyqtSignal(int)

    def __init__(self, db: Database):
        super().__init__()
        self._db      = db
        self._profile: Optional[OSINTProfile] = None
        self._fields:  dict[str, FieldWidget] = {}
        self._dirty   = False
        self._build()

    def _build(self):
        self.setStyleSheet(f"background:{BG};")
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Top toolbar ───────────────────────────
        toolbar = QWidget()
        toolbar.setFixedHeight(52)
        toolbar.setStyleSheet(f"background:{BG2}; border-bottom:1px solid {BORDER};")
        tlay = QHBoxLayout(toolbar)
        tlay.setContentsMargins(20, 0, 16, 0)
        tlay.setSpacing(8)

        self._profile_title = QLabel("— اختر هدفاً —")
        self._profile_title.setStyleSheet(f"color:{FG}; font-size:14px; font-weight:700; font-family:{FONT_UI};")
        tlay.addWidget(self._profile_title)

        self._dirty_dot = QLabel("●")
        self._dirty_dot.setStyleSheet(f"color:{YELLOW}; font-size:8px;")
        self._dirty_dot.hide()
        tlay.addWidget(self._dirty_dot)

        tlay.addStretch()

        # Buttons
        for txt, tip, cb, style in [
            ("💾  حفظ",     "حفظ البيانات  Ctrl+S", self._save,   f"background:{ACCENT}; color:white;"),
            ("📤  تصدير",   "تصدير JSON",            self._export, f"background:{SURFACE2}; color:{FG};"),
            ("🖼  صورة",    "تحميل صورة الهدف",      self._load_photo, f"background:{SURFACE2}; color:{FG};"),
            ("🗑  حذف",     "حذف الهدف",              self._delete, f"background:#2a0a10; color:{RED};"),
        ]:
            b = QPushButton(txt)
            b.setFixedHeight(30)
            b.setMinimumWidth(80)
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton{{{style} border:none; border-radius:5px;
                    font-size:12px; font-family:{FONT_UI}; padding:0 12px;}}
                QPushButton:hover{{opacity:0.85; filter:brightness(1.1);}}
                QPushButton:disabled{{opacity:0.3;}}
            """)
            b.clicked.connect(cb)
            tlay.addWidget(b)
            setattr(self, f"_btn_{txt[2:4].strip()}", b)

        main.addWidget(toolbar)

        # ── Empty state ───────────────────────────
        self._empty = QWidget()
        el = QVBoxLayout(self._empty)
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico = QLabel("◈")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(f"color:{FG_DIM}; font-size:64px;")
        el.addWidget(ico)
        msg = QLabel("اختر هدفاً من القائمة\nأو أنشئ ملفاً جديداً")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        msg.setStyleSheet(f"color:{FG_DIM}; font-size:14px; font-family:{FONT_UI}; line-height:2;")
        el.addWidget(msg)

        # ── Scroll area with fields ────────────────
        self._form_scroll = QScrollArea()
        self._form_scroll.setWidgetResizable(True)
        self._form_scroll.setStyleSheet(f"""
            QScrollArea{{background:{BG}; border:none;}}
            QScrollBar:vertical{{background:{BG}; width:5px; border:none;}}
            QScrollBar::handle:vertical{{background:{BORDER2}; border-radius:2px;}}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{{height:0;}}
        """)

        self._form_container = QWidget()
        self._form_container.setStyleSheet(f"background:{BG};")
        self._form_layout = QVBoxLayout(self._form_container)
        self._form_layout.setContentsMargins(24, 20, 24, 40)
        self._form_layout.setSpacing(0)
        self._build_form()
        self._form_scroll.setWidget(self._form_container)

        # Stack
        self._stack = QStackedWidget()
        self._stack.addWidget(self._empty)
        self._stack.addWidget(self._form_scroll)
        main.addWidget(self._stack, stretch=1)

        # Keyboard shortcut
        sc = QShortcut(QKeySequence("Ctrl+S"), self)
        sc.activated.connect(self._save)

    def _build_form(self):
        """Build all field groups."""
        for group_name, fields in FIELD_GROUPS.items():
            # Group header
            gh = QWidget()
            gh.setFixedHeight(36)
            gh.setStyleSheet(f"background:{SURFACE};  border-radius:6px; margin-top:12px;")
            ghl = QHBoxLayout(gh)
            ghl.setContentsMargins(12, 0, 12, 0)
            lbl = QLabel(group_name)
            lbl.setStyleSheet(f"color:{FG}; font-size:12px; font-weight:700; font-family:{FONT_UI};")
            ghl.addWidget(lbl)

            count = QLabel(f"{len(fields)} حقل")
            count.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-family:{FONT_UI};")
            ghl.addStretch()
            ghl.addWidget(count)
            self._form_layout.addWidget(gh)

            # Grid of fields (2 columns)
            grid = QGridLayout()
            grid.setSpacing(12)
            grid.setContentsMargins(0, 12, 0, 4)

            col, row = 0, 0
            for key, label, ftype, options in fields:
                fw = FieldWidget(key, label, ftype, options if isinstance(options, list) else None)
                fw.changed.connect(self._on_field_changed)
                self._fields[key] = fw

                span = 2 if ftype in ("textarea",) else 1
                if span == 2:
                    if col == 1:
                        col = 0; row += 1
                    grid.addWidget(fw, row, 0, 1, 2)
                    row += 1
                    col = 0
                else:
                    grid.addWidget(fw, row, col)
                    col += 1
                    if col >= 2:
                        col = 0; row += 1

            self._form_layout.addLayout(grid)

            # Divider
            div = QFrame()
            div.setFrameShape(QFrame.Shape.HLine)
            div.setStyleSheet(f"color:{BORDER}; margin-top:8px;")
            self._form_layout.addWidget(div)

        self._form_layout.addStretch()

    # ── Public API ────────────────────────────────

    def load_profile(self, profile: OSINTProfile):
        self._profile = profile
        self._dirty   = False
        self._dirty_dot.hide()
        self._profile_title.setText(profile.display_name())
        self._stack.setCurrentIndex(1)

        for key, fw in self._fields.items():
            fw.set_value(profile.get(key))

    def clear(self):
        self._profile = None
        self._stack.setCurrentIndex(0)

    # ── Slots ─────────────────────────────────────

    def _on_field_changed(self, key: str, value: str):
        if self._profile:
            self._profile.set(key, value)
            self._dirty = True
            self._dirty_dot.show()
            # Update title live
            if key in ("full_name", "alias"):
                self._profile_title.setText(self._profile.display_name() or "— بدون اسم —")

    def _save(self):
        if not self._profile:
            return
        self._db.save_profile(self._profile)
        self._dirty = False
        self._dirty_dot.hide()
        self.profile_saved.emit(self._profile)
        self._flash_saved()

    def _flash_saved(self):
        orig = self._profile_title.styleSheet()
        self._profile_title.setStyleSheet(orig + f"color:{GREEN};")
        QTimer.singleShot(800, lambda: self._profile_title.setStyleSheet(orig))

    def _delete(self):
        if not self._profile:
            return
        name = self._profile.display_name()
        dlg = QMessageBox(self)
        dlg.setWindowTitle("تأكيد الحذف")
        dlg.setText(f"حذف ملف «{name}» نهائياً؟")
        dlg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        dlg.setStyleSheet(f"""
            QMessageBox{{background:{SURFACE}; color:{FG};}}
            QPushButton{{background:{SURFACE2}; color:{FG}; border:1px solid {BORDER2};
                border-radius:4px; padding:5px 16px;}}
            QPushButton:hover{{background:{ACCENT_DIM};}}
        """)
        if dlg.exec() == QMessageBox.StandardButton.Yes:
            pid = self._profile.id
            self._db.delete_profile(pid)
            self.profile_deleted.emit(pid)
            self.clear()

    def _export(self):
        if not self._profile:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "تصدير الملف", f"{self._profile.display_name()}.json",
            "JSON Files (*.json)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._db.export_profile_json(self._profile))

    def _load_photo(self):
        if not self._profile:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "اختر صورة الهدف", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            with open(path, "rb") as f:
                data = f.read()
            mime = "image/png" if path.endswith(".png") else "image/jpeg"
            self._db.save_photo(self._profile.id, data, mime)
            self._profile.photo_path = path
            self._db.save_profile(self._profile)
            self.profile_saved.emit(self._profile)


# ─────────────────────────────────────────────────────────────────────────────
# OSINT Map View — visual node graph
# ─────────────────────────────────────────────────────────────────────────────

class MapNode:
    def __init__(self, x, y, label, value, color=ACCENT):
        self.x = x
        self.y = y
        self.label = label
        self.value = value
        self.color = color
        self.w = max(140, len(value) * 7 + 40)
        self.h = 44


class OSINTMapView(QWidget):
    """Interactive visual graph of a profile's data."""

    def __init__(self):
        super().__init__()
        self._profile: Optional[OSINTProfile] = None
        self._nodes:   List[MapNode] = []
        self._drag_node = None
        self._drag_offset = QPoint()
        self._scale = 1.0
        self._offset = QPoint(0, 0)
        self._pan_start = None
        self.setMinimumSize(400, 400)
        self.setStyleSheet(f"background:{BG3};")
        self.setMouseTracking(True)

    def load_profile(self, profile: OSINTProfile):
        self._profile = profile
        self._build_nodes()
        self.update()

    def _build_nodes(self):
        if not self._profile:
            return
        self._nodes.clear()
        p = self._profile

        # Center node
        cx, cy = 500, 300
        center = MapNode(cx, cy, "الهدف", p.display_name(), ACCENT)
        center.w, center.h = 180, 56
        self._nodes.append(center)

        # Category clusters
        categories = [
            ("🪪", "الهوية",   ["full_name","alias","dob","nationality","national_id"], GREEN,   -320, -160),
            ("📞", "التواصل",  ["phone_primary","phone_secondary","email_primary","telegram"], CYAN, 260, -160),
            ("📍", "الموقع",   ["city","country","address_current","coordinates"], YELLOW,  -320, 120),
            ("🌐", "الرقمي",   ["facebook","instagram","twitter","linkedin","usernames"], "#a97af8", 260, 120),
            ("💼", "المهنة",   ["occupation","employer","education"], "#3ecfcf", -160, -260),
            ("🚗", "الممتلكات",["vehicles","plate_numbers","properties"], YELLOW,  160, -260),
            ("👥", "الشبكة",   ["family_members","associates","organizations"], GREEN,   -160, 260),
            ("⚠️", "الأمن",    ["threat_level","criminal_record","known_weapons"], RED,    160, 260),
        ]

        for icon, cat_name, keys, color, dx, dy in categories:
            # Collect non-empty values
            items = [(k, p.get(k)) for k in keys if p.get(k)]
            if not items:
                continue

            # Category hub node
            hub_x = cx + dx
            hub_y = cy + dy
            hub = MapNode(hub_x, hub_y, icon, cat_name, color)
            hub.w, hub.h = 130, 40
            self._nodes.append(hub)

            # Child nodes
            n = len(items)
            for i, (key, val) in enumerate(items[:6]):
                angle_spread = 80
                angle = -angle_spread/2 + i * (angle_spread / max(1, n-1)) if n > 1 else 0
                import math
                rad = math.radians(angle + (270 if dy < 0 else 90) + (180 if dx < 0 else 0))
                child_x = hub_x + int(math.cos(rad) * 160)
                child_y = hub_y + int(math.sin(rad) * 80)

                # Get field label
                label = next((f[1] for f in ALL_FIELDS if f[0] == key), key)
                disp_val = val[:30] + "..." if len(val) > 30 else val
                child = MapNode(child_x, child_y, label, disp_val, color)
                child.w = max(120, len(disp_val) * 7 + 30)
                child.h = 38
                self._nodes.append(child)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background grid
        p.fillRect(self.rect(), QColor(BG3))
        p.setPen(QPen(QColor(BORDER), 1))
        grid = 40
        for x in range(0, self.width(), grid):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), grid):
            p.drawLine(0, y, self.width(), y)

        if not self._nodes:
            p.setPen(QColor(FG_DIM))
            p.setFont(QFont("Segoe UI", 14))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "◈  اختر هدفاً لعرض المخطط")
            p.end()
            return

        p.translate(self._offset)
        p.scale(self._scale, self._scale)

        center = self._nodes[0]
        cx = center.x + center.w // 2
        cy = center.y + center.h // 2

        # Draw edges first
        for node in self._nodes[1:]:
            nx = node.x + node.w // 2
            ny = node.y + node.h // 2
            # Gradient line
            pen = QPen(QColor(node.color))
            pen.setWidth(1)
            pen.setStyle(Qt.PenStyle.DotLine)
            pen.setColor(QColor(node.color + "60"))
            p.setPen(pen)
            p.drawLine(cx, cy, nx, ny)

        # Draw nodes
        for i, node in enumerate(self._nodes):
            self._draw_node(p, node, i == 0)

        p.end()

    def _draw_node(self, p: QPainter, node: MapNode, is_center: bool):
        x, y, w, h = node.x, node.y, node.w, node.h
        color = QColor(node.color)

        if is_center:
            # Center: filled with accent
            p.setBrush(QBrush(QColor(ACCENT_DIM)))
            pen = QPen(color, 2)
            p.setPen(pen)
            p.drawRoundedRect(x, y, w, h, 8, 8)

            p.setPen(color)
            p.setFont(QFont(FONT_UI, 9, QFont.Weight.Bold))
            p.drawText(x, y, w, h//2, Qt.AlignmentFlag.AlignCenter, node.label)
            p.setFont(QFont(FONT_UI, 11, QFont.Weight.Bold))
            p.drawText(x, y + h//2, w, h//2, Qt.AlignmentFlag.AlignCenter, node.value)
        else:
            # Regular node
            bg = QColor(node.color)
            bg.setAlpha(18)
            p.setBrush(QBrush(bg))
            pen = QPen(QColor(node.color + "55"), 1)
            p.setPen(pen)
            p.drawRoundedRect(x, y, w, h, 6, 6)

            # Label (small)
            dim = QColor(node.color)
            dim.setAlpha(120)
            p.setPen(dim)
            p.setFont(QFont(FONT_UI, 8))
            p.drawText(x + 8, y, w - 16, h // 2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, node.label)

            # Value
            p.setPen(QColor(FG))
            p.setFont(QFont(FONT_UI, 10))
            p.drawText(x + 8, y + h//2, w - 16, h//2, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, node.value)

    def wheelEvent(self, e):
        delta = e.angleDelta().y()
        self._scale = max(0.3, min(3.0, self._scale * (1.1 if delta > 0 else 0.9)))
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton or (
            e.button() == Qt.MouseButton.LeftButton and
            not self._node_at(e.position().toPoint())
        ):
            self._pan_start = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._pan_start and e.buttons() & (Qt.MouseButton.LeftButton | Qt.MouseButton.MiddleButton):
            delta = e.position().toPoint() - self._pan_start
            self._offset += delta
            self._pan_start = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        self._pan_start = None

    def _node_at(self, pos: QPoint):
        for node in self._nodes:
            if (node.x <= pos.x() <= node.x + node.w and
                node.y <= pos.y() <= node.y + node.h):
                return node
        return None

    def reset_view(self):
        self._offset = QPoint(0, 0)
        self._scale  = 1.0
        self.update()


# ─────────────────────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────────────────────

class PhantomOSINT(QWidget):
    def __init__(self):
        super().__init__()
        self._db = Database()
        self._current_profile: Optional[OSINTProfile] = None
        self._setup_window()
        self._build_ui()
        self._load_all_profiles()

    def _setup_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setMinimumSize(1100, 700)
        self.resize(1400, 860)
        self.setWindowTitle("Phantom OSINT")
        self.setStyleSheet(f"background:{BG}; color:{FG};")

    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Title bar
        self._title_bar = TitleBar(self)
        main.addWidget(self._title_bar)

        # Body
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Left: profile list
        self._list_panel = ProfileListPanel(self._db)
        self._list_panel.profile_selected.connect(self._on_profile_selected)
        self._list_panel.new_requested.connect(self._new_profile)
        body.addWidget(self._list_panel)

        # Right: tabbed editor + map
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        # View toggle tabs
        self._view_tabs = QWidget()
        self._view_tabs.setFixedHeight(38)
        self._view_tabs.setStyleSheet(f"background:{BG2}; border-bottom:1px solid {BORDER};")
        vt = QHBoxLayout(self._view_tabs)
        vt.setContentsMargins(16, 0, 16, 0)
        vt.setSpacing(0)

        self._tab_form = self._make_tab_btn("📋  بيانات", True)
        self._tab_map  = self._make_tab_btn("🗺  مخطط",   False)
        self._tab_form.clicked.connect(lambda: self._switch_view(0))
        self._tab_map.clicked.connect(lambda:  self._switch_view(1))
        vt.addWidget(self._tab_form)
        vt.addWidget(self._tab_map)
        vt.addStretch()

        # Map reset
        reset_btn = QPushButton("↺  إعادة")
        reset_btn.setFixedSize(70, 26)
        reset_btn.setStyleSheet(f"background:{SURFACE2}; color:{FG_MED}; border:none; border-radius:4px; font-size:11px; font-family:{FONT_UI};")
        reset_btn.clicked.connect(lambda: self._map_view.reset_view())
        vt.addWidget(reset_btn)

        right.addWidget(self._view_tabs)

        # Stacked view
        self._view_stack = QStackedWidget()

        self._editor = ProfileEditor(self._db)
        self._editor.profile_saved.connect(self._on_profile_saved)
        self._editor.profile_deleted.connect(self._on_profile_deleted)
        self._view_stack.addWidget(self._editor)

        self._map_view = OSINTMapView()
        self._view_stack.addWidget(self._map_view)

        right.addWidget(self._view_stack, stretch=1)

        body_widget = QWidget()
        body_widget.setLayout(body)
        body.addLayout(right, stretch=1)

        main.addWidget(body_widget, stretch=1)

        # Status bar
        status = QWidget()
        status.setFixedHeight(22)
        status.setStyleSheet(f"background:{BG}; border-top:1px solid {BORDER};")
        sl = QHBoxLayout(status)
        sl.setContentsMargins(14, 0, 14, 0)
        self._status_lbl = QLabel("◈  Phantom OSINT  |  قاعدة بيانات محلية مشفرة")
        self._status_lbl.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-family:{FONT_UI};")
        sl.addWidget(self._status_lbl)
        sl.addStretch()
        db_lbl = QLabel(f"📁  {self._db.db_path}")
        db_lbl.setStyleSheet(f"color:{FG_DIM}; font-size:10px; font-family:{FONT_UI};")
        sl.addWidget(db_lbl)
        main.addWidget(status)

    def _make_tab_btn(self, text: str, active: bool) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedHeight(38)
        btn.setMinimumWidth(100)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        btn.setChecked(active)
        btn.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{FG_MED};
                border:none; border-bottom:2px solid transparent;
                font-size:12px; font-family:{FONT_UI}; padding:0 16px;
            }}
            QPushButton:checked {{
                color:{FG}; border-bottom:2px solid {ACCENT};
            }}
            QPushButton:hover:!checked {{ color:{FG}; }}
        """)
        return btn

    def _switch_view(self, index: int):
        self._view_stack.setCurrentIndex(index)
        self._tab_form.setChecked(index == 0)
        self._tab_map.setChecked(index == 1)
        if index == 1 and self._current_profile:
            self._map_view.load_profile(self._current_profile)

    # ── Data operations ───────────────────────────

    def _load_all_profiles(self):
        profiles = self._db.list_profiles()
        self._list_panel.load_profiles(profiles)
        self._title_bar.set_stats(len(profiles))

    def _new_profile(self):
        profile = self._db.create_profile()
        self._current_profile = profile
        self._load_all_profiles()
        self._list_panel.set_active(profile.id)
        self._editor.load_profile(profile)
        self._switch_view(0)

    def _on_profile_selected(self, profile_id: int):
        profile = self._db.load_profile(profile_id)
        if profile:
            self._current_profile = profile
            self._editor.load_profile(profile)
            if self._view_stack.currentIndex() == 1:
                self._map_view.load_profile(profile)

    def _on_profile_saved(self, profile: OSINTProfile):
        self._current_profile = profile
        self._list_panel.refresh_card(profile)
        count = self._db.count()
        self._title_bar.set_stats(count)
        self._status_lbl.setText(f"✓  تم الحفظ — {profile.display_name()}  |  {profile.updated_at}")

    def _on_profile_deleted(self, profile_id: int):
        self._current_profile = None
        self._load_all_profiles()
        self._map_view._nodes.clear()
        self._map_view.update()

    # ── Window resize ─────────────────────────────

    RESIZE_MARGIN = 5

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            edge = self._get_edge(e.position().toPoint())
            if edge:
                self._resize_edge  = edge
                self._resize_start = e.globalPosition().toPoint()
                self._resize_rect  = self.geometry()

    def mouseMoveEvent(self, e):
        if hasattr(self, "_resize_edge") and self._resize_edge:
            from PyQt6.QtCore import QRect
            delta = e.globalPosition().toPoint() - self._resize_start
            r = QRect(self._resize_rect)
            if "e" in self._resize_edge: r.setRight(r.right() + int(delta.x()))
            if "s" in self._resize_edge: r.setBottom(r.bottom() + int(delta.y()))
            if "w" in self._resize_edge: r.setLeft(r.left() + int(delta.x()))
            if "n" in self._resize_edge: r.setTop(r.top() + int(delta.y()))
            if r.width() >= self.minimumWidth() and r.height() >= self.minimumHeight():
                self.setGeometry(r)
        else:
            edge = self._get_edge(e.position().toPoint())
            cursors = {
                "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
                "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
                "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
                "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
            }
            self.setCursor(cursors.get(edge, Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, e):
        self._resize_edge = None

    def _get_edge(self, pos):
        m, w, h = self.RESIZE_MARGIN, self.width(), self.height()
        x, y = pos.x(), pos.y()
        if x <= m and y <= m:       return "nw"
        if x >= w-m and y <= m:     return "ne"
        if x <= m and y >= h-m:     return "sw"
        if x >= w-m and y >= h-m:   return "se"
        if x <= m:                  return "w"
        if x >= w-m:                return "e"
        if y <= m:                  return "n"
        if y >= h-m:                return "s"
        return None

    def closeEvent(self, e):
        self._db.close()
        e.accept()

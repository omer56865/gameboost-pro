"""
GameBoost Pro - Görsel Oyun Kütüphanesi (Modern Grid Hub)
"""
import json
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

PLAYTIME_FILE = Path(__file__).parent / "playtime.json"


def load_playtimes():
    if PLAYTIME_FILE.exists():
        try:
            return json.loads(PLAYTIME_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_playtime(game_name, seconds):
    data = load_playtimes()
    data[game_name] = data.get(game_name, 0) + seconds
    PLAYTIME_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


class GameCard(QFrame):
    launch_requested = Signal(dict)
    optimize_requested = Signal(str)

    def __init__(self, game_info, playtime_sec=0, parent=None):
        super().__init__(parent)
        self.game_info = game_info  # {"name": ..., "path": ..., "source": ...}
        self.playtime_sec = playtime_sec
        self.setObjectName("card")
        self.setFixedSize(220, 290)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Üst Bilgi / Poster Alanı
        poster = QFrame()
        poster.setStyleSheet(
            "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e2638, stop:1 #0d111a); border-radius: 10px;"
        )
        poster_layout = QVBoxLayout(poster)
        poster_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        badge = QLabel(f"  {self.game_info.get('source', 'PC')}  ")
        badge.setStyleSheet(
            "background: rgba(108, 140, 255, 40); color: #6c8cff; font-weight: bold; border-radius: 6px; font-size: 10px;"
        )
        badge.setFixedHeight(20)

        icon_lbl = QLabel("🎮")
        icon_lbl.setStyleSheet("font-size: 38px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        poster_layout.addWidget(
            badge, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop
        )
        poster_layout.addWidget(icon_lbl)

        # İsim ve Oynama Süresi
        title = QLabel(self.game_info["name"])
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #e8eaf2;")
        title.setWordWrap(True)

        hours = self.playtime_sec / 3600.0
        time_lbl = QLabel(
            f"⏱ {hours:.1f} saat oynandı" if hours >= 0.1 else "⏱ Henüz oynanmadı"
        )
        time_lbl.setStyleSheet("color: #8a90a6; font-size: 11px;")

        # Butonlar
        btn_box = QHBoxLayout()
        btn_box.setSpacing(6)

        btn_opt = QPushButton("⚡ Optimize")
        btn_opt.setObjectName("ghost")
        btn_opt.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_opt.clicked.connect(
            lambda: self.optimize_requested.emit(self.game_info["name"])
        )

        btn_play = QPushButton("▶ Başlat")
        btn_play.setObjectName("primary")
        btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play.clicked.connect(
            lambda: self.launch_requested.emit(self.game_info)
        )

        btn_box.addWidget(btn_opt)
        btn_box.addWidget(btn_play)

        layout.addWidget(poster, 1)
        layout.addWidget(title)
        layout.addWidget(time_lbl)
        layout.addLayout(btn_box)


class GridHubWidget(QWidget):
    request_optimize = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(18)
        self.grid.setContentsMargins(10, 10, 10, 10)

        scroll.setWidget(self.container)
        main_layout.addWidget(scroll)

    def populate_games(self, games_list):
        # Temizle
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)

        playtimes = load_playtimes()
        cols = 4  # Her satırda 4 kart

        for idx, g in enumerate(games_list):
            row = idx // cols
            col = idx % cols
            pt = playtimes.get(g["name"], 0)

            card = GameCard(g, playtime_sec=pt)
            card.optimize_requested.connect(self.request_optimize.emit)
            card.launch_requested.connect(self.launch_game)
            self.grid.addWidget(card, row, col)

    def launch_game(self, game_info):
        path = game_info.get("path")
        if not path:
            return

        try:
            if path.startswith("steam://"):
                os.startfile(path)
            else:
                subprocess.Popen(path, shell=True)
        except Exception as e:
            print(f"Oyun başlatılamadı: {e}")
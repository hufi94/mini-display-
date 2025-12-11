#!/usr/bin/env python3
# system_status_mock.py
#
# Cyberpunk-style System Status widget:
# - CPU temperature
# - CPU load %
# - RAM usage %
#
# Standalone demo window so you can see how it looks.
# Later we can drop SystemStatusWidget into your bottom-right GlowWidget.

import sys, os, random
import psutil
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import (
    QColor, QFont, QPainter, QPen, QLinearGradient, QBrush
)
from PyQt5.QtWidgets import QApplication, QWidget, QMainWindow, QLabel, QGraphicsDropShadowEffect

# ───────────────── Settings / colors (similar to your dashboard)
WIDGET_W, WIDGET_H = 270, 170
CYAN  = QColor("#00ffff")
PINK  = QColor("#ff00ff")
BG    = QColor("#0d0d0d")

# ───────────────── Glow frame, similar to your GlowWidget
class GlowFrame(QWidget):
    def __init__(self, parent=None, title=""):
        super().__init__(parent)
        self.setFixedSize(WIDGET_W, WIDGET_H)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # Optional title label (centered)
        self.title = QLabel(title, self)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet("color:#ff00ff; background:transparent;")
        font = QFont("Neuropolitical", 20, QFont.Bold)
        if font.family() == "Sans Serif":
            font = QFont("Courier New", 20, QFont.Bold)
        self.title.setFont(font)
        self.title.setGeometry(0, 6, WIDGET_W, 26)

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(180)
        glow.setColor(CYAN)
        glow.setOffset(2, 2)
        self.setGraphicsEffect(glow)

    def inner_rect(self):
        # Slight inner margin for content
        return self.rect().adjusted(18, 30, -18, -18)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Outer neon frame
        pen = QPen(CYAN)
        pen.setWidth(6)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), 26, 26)
        p.end()


# ───────────────── SystemStatusWidget (the actual CPU/RAM/Temp widget)
class SystemStatusWidget(QWidget):
    """
    Draws 3 neon rows:
      CPU:  47%  [■■■■■■      ]
      TEMP: 54°C [■■■■■■■    ]
      RAM:  63%  [■■■■■■■■   ]
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(WIDGET_W - 36, WIDGET_H - 50)  # fits inside GlowFrame.inner_rect()

        self.cpu_load = 0.0
        self.cpu_temp = 0.0
        self.ram_usage = 0.0

        # Timer to update values
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(1000)  # every second
        self.update_metrics()

    # ── helpers to get metrics
    def _read_cpu_temp(self):
        # Try psutil first
        try:
            temps = psutil.sensors_temperatures()
            for key, entries in temps.items():
                if entries:
                    # take first available sensor
                    return float(entries[0].current)
        except Exception:
            pass

        # Fallback: Raspberry Pi thermal file
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                milli = float(f.read().strip())
            return milli / 1000.0
        except Exception:
            # Demo fallback
            return random.uniform(40, 65)

    def update_metrics(self):
        try:
            self.cpu_load = float(psutil.cpu_percent(interval=None))
        except Exception:
            self.cpu_load = random.uniform(5, 80)

        self.cpu_temp = self._read_cpu_temp()

        try:
            mem = psutil.virtual_memory()
            self.ram_usage = float(mem.percent)
        except Exception:
            self.ram_usage = random.uniform(20, 90)

        self.update()

    # ── drawing helpers
    def _draw_row(self, p, x, y, w, label, value_str, percent, bar_color_from, bar_color_to):
        """
        Draw:
          LABEL  value_str
          [====neon bar====]
        """
        # Fonts
        label_font = QFont("Neuropolitical", 11, QFont.Bold)
        if label_font.family() == "Sans Serif":
            label_font = QFont("Courier New", 11, QFont.Bold)
        value_font = QFont("Neuropolitical", 13, QFont.Bold)
        if value_font.family() == "Sans Serif":
            value_font = QFont("Courier New", 13, QFont.Bold)

        # Text row
        p.setFont(label_font)
        p.setPen(CYAN)
        p.drawText(int(x), int(y), int(w // 2), 16, Qt.AlignLeft | Qt.AlignVCenter, label)

        p.setFont(value_font)
        p.setPen(PINK)
        p.drawText(int(x + w // 2), int(y), int(w // 2), 16, Qt.AlignRight | Qt.AlignVCenter, value_str)

        # Bar geometry
        bar_y = y + 18
        bar_h = 9
        bar_margin = 2
        bar_w = w

        # Background bar (dim)
        bg_rect = (x, bar_y, bar_w, bar_h)
        bg_pen = QPen(QColor(40, 40, 40, 180))
        bg_pen.setWidth(1)
        p.setPen(bg_pen)
        p.setBrush(QColor(20, 20, 20, 220))
        p.drawRoundedRect(*bg_rect, 4, 4)

        # Foreground neon bar
        pct = max(0.0, min(100.0, percent)) / 100.0
        fill_w = int(bar_w * pct)

        if fill_w > 0:
            grad = QLinearGradient()
            grad.setStart(x, bar_y)
            grad.setFinalStop(x + fill_w, bar_y)
            c1 = QColor(bar_color_from)
            c2 = QColor(bar_color_to)
            c1.setAlpha(230)
            c2.setAlpha(230)
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1.0, c2)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(x + bar_margin,
                              bar_y + bar_margin,
                              max(0, fill_w - bar_margin * 2),
                              bar_h - bar_margin * 2,
                              4, 4)

            # soft glow outline
            glow_pen = QPen(bar_color_to)
            glow_pen.setWidth(2)
            glow_pen.setColor(QColor(bar_color_to.red(),
                                     bar_color_to.green(),
                                     bar_color_to.blue(), 160))
            p.setPen(glow_pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(x + bar_margin,
                              bar_y + bar_margin,
                              max(0, fill_w - bar_margin * 2),
                              bar_h - bar_margin * 2,
                              4, 4)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # Slight transparent fill to darken interior
        p.fillRect(self.rect(), QColor(5, 5, 5, 200))

        inner_x = 8
        inner_y = 4
        inner_w = self.width() - 2 * inner_x

        # CPU load (top)
        self._draw_row(
            p,
            inner_x, inner_y,
            inner_w,
            "CPU",
            f"{self.cpu_load:4.0f} %",
            self.cpu_load,
            CYAN,
            PINK
        )

        # CPU temp (middle)
        mid_y = inner_y + 38
        temp_pct = (self.cpu_temp / 90.0) * 100.0  # normalize vs ~90°C
        self._draw_row(
            p,
            inner_x, mid_y,
            inner_w,
            "TEMP",
            f"{self.cpu_temp:4.1f} °C",
            temp_pct,
            QColor("#39FF14"),  # neon green-ish
            PINK
        )

        # RAM usage (bottom)
        bot_y = mid_y + 38
        self._draw_row(
            p,
            inner_x, bot_y,
            inner_w,
            "RAM",
            f"{self.ram_usage:4.0f} %",
            self.ram_usage,
            CYAN,
            QColor("#39FF14")
        )

        p.end()


# ───────────────── Demo MainWindow
class DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Status Widget – Mockup")
        self.setFixedSize(400, 260)
        self.setStyleSheet(f"background-color: {BG.name()};")

        self.frame = GlowFrame(self, title="SYSTEM")
        self.frame.move(60, 40)

        self.sys_widget = SystemStatusWidget(self.frame)
        inner = self.frame.inner_rect()
        self.sys_widget.move(inner.x(), inner.y())


# ───────────────── Run
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DemoWindow()
    win.show()
    sys.exit(app.exec_())

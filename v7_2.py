# Cyberpunk Dashboard – PCB v7.3 (Civic GIF + Fixed setText)
import sys, random, datetime
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, QPointF
from PyQt5.QtGui import QColor, QFont, QPainter, QPen, QPainterPath, QMovie

# ──────────────────────────────────────────────
# TUNABLES
# ──────────────────────────────────────────────
WIDGET_W, WIDGET_H = 250, 160
LEFT_X, RIGHT_X_GAP = 40, 40
TOP_Y, BOTTOM_Y_GAP = 50, 50
CYAN = QColor("#00ffff")
PINK = QColor("#ff00ff")
GRID_COLOR = QColor(30, 30, 30)
BORDER_WIDTH = 4
RADIUS = 30
PADDING = 8
CORE = 3
BUS_OFFS = [-20, -10, 10, 20]
SPINE_OFFS = [-34, -32, 34, 36]
BRANCH_OFFSETS = [-13, 13]

# ──────────────────────────────────────────────
# Neon helpers
# ──────────────────────────────────────────────
def neon_stroke(p, path, color, core_width):
    c1 = QColor(color); c1.setAlpha(60)
    c2 = QColor(color); c2.setAlpha(120)
    c3 = QColor(color); c3.setAlpha(255)
    for w, col in ((core_width*3, c1), (int(core_width*1.7), c2), (core_width, c3)):
        pen = QPen(col)
        pen.setWidth(w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

def neon_dot(p, pos, color, radius):
    c1 = QColor(color); c1.setAlpha(60)
    c2 = QColor(color); c2.setAlpha(120)
    c3 = QColor(color); c3.setAlpha(255)
    for r, col in ((radius*2, c1), (int(radius*1.5), c2), (radius, c3)):
        p.setBrush(col)
        p.setPen(Qt.NoPen)
        p.drawEllipse(pos, r, r)

def ortho_path(points):
    path = QPainterPath(QPointF(points[0][0], points[0][1]))
    for x, y in points[1:]:
        path.lineTo(QPointF(x, y))
    return path

# ──────────────────────────────────────────────
# Widget class (with working setText)
# ──────────────────────────────────────────────
class GlowWidget(QWidget):
    def __init__(self, text="", parent=None, big=False):
        super().__init__(parent)
        self.setFixedSize(WIDGET_W, WIDGET_H)
        self.big = big

        # Label
        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("background: transparent; color:#ff00ff;")
        size = 30 if big else 23
        font = QFont("Neuropolitical", size, QFont.Bold)
        if font.family() == "Sans Serif":
            font = QFont("Courier New", size, QFont.Bold)
        self.label.setFont(font)
        self.label.resize(self.size())

        # Neon frame glow
        border_glow = QGraphicsDropShadowEffect(self)
        border_glow.setBlurRadius(80)
        border_glow.setColor(CYAN)
        border_glow.setOffset(0, 0)
        self.setGraphicsEffect(border_glow)

        # Pink text glow
        text_glow = QGraphicsDropShadowEffect(self.label)
        text_glow.setBlurRadius(15)
        glow_color = QColor(PINK)
        glow_color.setAlpha(30)
        text_glow.setColor(glow_color)
        text_glow.setOffset(0, 0)
        self.label.setGraphicsEffect(text_glow)

        self.setAttribute(Qt.WA_TranslucentBackground)

    def setText(self, html):
        """Fix: allows setting new text dynamically"""
        self.label.setText(html)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(CYAN)
        pen.setWidth(BORDER_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)

        rect = self.rect().adjusted(4, 4, -4, -4)
        p.drawRoundedRect(rect, RADIUS, RADIUS)

        inset = self.rect().adjusted(22, 22, -22, -22)
        faint = QColor(CYAN); faint.setAlpha(60)
        pen2 = QPen(faint); pen2.setWidth(2)
        p.setPen(pen2)
        p.drawRoundedRect(inset, RADIUS-10, RADIUS-10)
        p.end()

# ──────────────────────────────────────────────
# Main window
# ──────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cyberpunk Dashboard – PCB v7.3")
        self.setFixedSize(640, 480)
        self.setStyleSheet("background-color:#0d0d0d;")

        self.top_left = self._mk(LEFT_X, TOP_Y, big=True)
        self.top_right = self._mk(self.width()-RIGHT_X_GAP-WIDGET_W, TOP_Y)
        self.bottom_left = self._mk(LEFT_X, self.height()-BOTTOM_Y_GAP-WIDGET_H)
        self.bottom_right = self._mk(self.width()-RIGHT_X_GAP-WIDGET_W,
                                     self.height()-BOTTOM_Y_GAP-WIDGET_H)

        try:
            import Adafruit_DHT
            self.SENSOR_AVAILABLE = True
            self.sensor_type = Adafruit_DHT.DHT22
            self.sensor_pin = 4
            self.Adafruit_DHT = Adafruit_DHT
        except ImportError:
            self.SENSOR_AVAILABLE = False

        self.t_timer = QTimer(self)
        self.t_timer.timeout.connect(self.update_time)
        self.t_timer.start(1000)

        self.s_timer = QTimer(self)
        self.s_timer.timeout.connect(self.update_sensors)
        self.s_timer.start(10000)

        self.update_time()
        self.update_sensors()

        # Civic GIF animation
        self.setup_civic_gif()

    def _mk(self, x, y, big=False):
        w = GlowWidget("", self, big=big)
        w.move(x, y)
        return w

    def setup_civic_gif(self):
        """Replaces bottom-left text with looping GIF."""
        gif_path = "/home/matteo94/Desktop/cd/civic_spin.gif"
        self.movie = QMovie(gif_path)
        if not self.movie.isValid():
            self.bottom_left.label.setText("GIF not found")
            return
        self.movie.setCacheMode(QMovie.CacheAll)
        self.movie.setSpeed(100)
        self.bottom_left.label.setScaledContents(True)
        self.bottom_left.label.setMovie(self.movie)
        self.movie.start()

    def update_time(self):
        now = datetime.datetime.now()
        t = now.strftime("%H:%M")
        d = now.strftime("%d-%m-%Y")
        self.top_left.setText(f"<span style='font-size:30pt'>{t}</span><br>"
                              f"<span style='font-size:14pt'>{d}</span>")

    def update_sensors(self):
        if getattr(self, "SENSOR_AVAILABLE", False):
            h, T = self.Adafruit_DHT.read_retry(self.sensor_type, self.sensor_pin)
            if h is None or T is None:
                self.top_right.setText("Temp:\n-- °C")
                self.bottom_right.setText("Humidity:\n-- %")
            else:
                self.top_right.setText(f"Temp:\n{T:.1f} °C")
                self.bottom_right.setText(f"Humidity:\n{h:.1f} %")
        else:
            T = random.uniform(18, 24)
            H = random.uniform(40, 60)
            self.top_right.setText(f"Outside:\n{T:.1f} °C (demo)")
            self.bottom_right.setText(f"Inside:\n{H:.1f} % (demo)")

# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
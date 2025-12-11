# dashboard_V11.12_swipe_fullpage.py
# Cyberpunk Dashboard – PCB v11.x
# - Page 0 (main): top-right shows temperatures in °C
# - Page 1 (swipe left): top-right shows humidity in %
# - Swipe left/right: full-page linear slide (no elastic, no fade)
# - Grid stays fixed, but PCB traces + dots + pink underline slide with widgets

import sys, os, random, datetime, glob, math
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QLabel, QGraphicsDropShadowEffect
from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt5.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPen, QPainterPath,
    QImage, QPixmap, QBrush, QLinearGradient
)

# ✅ psutil (CPU, RAM)
try:
    import psutil
except Exception:
    psutil = None

# ✅ BME280 imports
import board
from adafruit_bme280 import basic as adafruit_bme280

# ───────────────── Settings
WIDGET_W, WIDGET_H = 270, 170
EDGE_MARGIN_X, EDGE_MARGIN_Y = 21, 29
CYAN  = QColor("#00ffff")
PINK  = QColor("#ff00ff")
BORDER_WIDTH, RADIUS, PADDING, CORE = 6, 30, 8, 3
BUS_OFFS       = [-20, -10, 10, 20]
SPINE_OFFS     = [-34, -32, 34, 36]
BRANCH_OFFSETS = [-13, 13]
FRAMES_DIR = "/home/matteo94/Desktop/cd/civic_frames_alpha"

# Top-right knobs
LABEL_COL_W     = 130
LABEL_VAL_GAP   = 44
VALUE_FONT_SIZE = 22
LINE_THICK      = 3
LINE_GLOW       = 20
SAFE_RIGHT      = -18
VAL_RIGHT_PAD   = -30

# ───────────────── Sensors
class DualBME280:
    """
    Uses two BME280 sensors on the main Pi I2C bus:
      - Inside  = address 0x77
      - Outside = address 0x76

    Falls back to DEMO values if nothing is available.
    """
    def __init__(self):
        self.inside = None
        self.outside = None

        try:
            i2c = board.I2C()

            try:
                self.inside = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x77)
                self.inside.sea_level_pressure = 1013.25
                print("[BME280] Inside sensor OK at 0x77")
            except Exception as e:
                print(f"[WARN] Inside BME280 (0x77) init failed: {e}")
                self.inside = None

            try:
                self.outside = adafruit_bme280.Adafruit_BME280_I2C(i2c, address=0x76)
                self.outside.sea_level_pressure = 1013.25
                print("[BME280] Outside sensor OK at 0x76")
            except Exception as e:
                print(f"[WARN] Outside BME280 (0x76) init failed: {e}")
                self.outside = None

            if not self.inside and not self.outside:
                print("[WARN] No BME280 sensors detected on I2C bus")
        except Exception as e:
            print(f"[WARN] BME280 init failed (I2C setup): {e}")
            self.inside = None
            self.outside = None

    def read(self):
        """
        Returns a dict:
        {
            "inside_temp": int or None,
            "outside_temp": int or None,
            "inside_hum": int or None,
            "outside_hum": int or None,
            "ok": bool,
            "source": "BME280" or "DEMO",
        }
        """
        def safe_read(sensor):
            try:
                t = round(sensor.temperature)
                h = round(sensor.humidity)
                p = round(sensor.pressure)
                return t, h, p
            except Exception:
                return (None, None, None)

        in_t = in_h = out_t = out_h = None

        if self.inside is not None:
            in_t, in_h, _ = safe_read(self.inside)

        if self.outside is not None:
            out_t, out_h, _ = safe_read(self.outside)

        if in_t is None and out_t is None:
            in_t = round(random.uniform(21, 25))
            out_t = in_t - random.randint(0, 6)
            in_h = random.randint(40, 60)
            out_h = max(20, min(80, in_h + random.randint(-10, 10)))
            return {
                "inside_temp": in_t,
                "outside_temp": out_t,
                "inside_hum": in_h,
                "outside_hum": out_h,
                "ok": False,
                "source": "DEMO",
            }

        return {
            "inside_temp": in_t,
            "outside_temp": out_t,
            "inside_hum": in_h,
            "outside_hum": out_h,
            "ok": True,
            "source": "BME280",
        }

# ───────────────── Paint helpers
def neon_stroke(p, path, color, core_width):
    c1 = QColor(color); c1.setAlpha(60)
    c2 = QColor(color); c2.setAlpha(120)
    c3 = QColor(color); c3.setAlpha(255)
    p.setBrush(Qt.NoBrush)
    for w, col in ((core_width * 3, c1), (int(core_width * 1.7), c2), (core_width, c3)):
        pen = QPen(col)
        pen.setWidth(w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

def neon_stroke_pulse(p, path, color, core_width, phase):
    scale = 0.6 + 0.4 * (0.5 + 0.5 * math.sin(phase))

    def a(v):
        return max(0, min(255, int(v * scale)))

    c1 = QColor(color); c1.setAlpha(a(60))
    c2 = QColor(color); c2.setAlpha(a(120))
    c3 = QColor(color); c3.setAlpha(a(255))
    p.setBrush(Qt.NoBrush)
    for w, col in ((core_width * 3, c1), (int(core_width * 1.7), c2), (core_width, c3)):
        pen = QPen(col)
        pen.setWidth(w)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

def neon_dot(p, pos, color, radius):
    for a, s in ((60, 2), (120, 1.5), (255, 1)):
        c = QColor(color)
        c.setAlpha(a)
        p.setBrush(c)
        p.setPen(Qt.NoPen)
        p.drawEllipse(pos, radius * s, radius * s)

def ortho_path(points):
    path = QPainterPath(QPointF(points[0][0], points[0][1]))
    for x, y in points[1:]:
        path.lineTo(QPointF(x, y))
    return path

# ───────────────── Civic frame player
class FramePlayerWidget(QLabel):
    def __init__(self, parent=None, fps=25):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("background: transparent;")
        self.frames = []
        self.idx = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._next)
        self.interval = int(1000 / max(1, fps))

    def load_dir(self, dir_path):
        files = sorted(glob.glob(os.path.join(dir_path, "*.png")))
        self.frames = [
            QImage(f).convertToFormat(QImage.Format_ARGB32_Premultiplied)
            for f in files
        ]
        print(f"[CIVIC] Loaded {len(self.frames)} frames from: {dir_path}")
        self.idx = 0
        if self.frames:
            self._paint_current()
        else:
            self.setText("No frames found")

    def start(self):
        if self.frames:
            self.timer.start(self.interval)

    def _paint_current(self):
        if not self.frames:
            return
        size = self.size()
        canvas = QImage(size, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(Qt.transparent)
        frame = self.frames[self.idx].scaled(
            size, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        x = (size.width() - frame.width()) // 2
        y = (size.height() - frame.height()) // 2
        p = QPainter(canvas)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.drawImage(x, y, frame)
        p.end()
        self.setPixmap(QPixmap.fromImage(canvas))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._paint_current()

    def _next(self):
        if self.frames:
            self.idx = (self.idx + 1) % len(self.frames)
            self._paint_current()

# ───────────────── Glow widget
class GlowWidget(QWidget):
    def __init__(self, text="", parent=None, big=False):
        super().__init__(parent)
        self.setFixedSize(WIDGET_W, WIDGET_H)

        self.label = QLabel(text, self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color:#ff00ff; background:transparent;")

        size = 30 if big else 23
        font = QFont("Neuropolitical", size, QFont.Bold)
        if font.family() == "Sans Serif":
            font = QFont("Courier New", size, QFont.Bold)
        self.label.setFont(font)
        self.label.resize(self.size())

        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(200)
        glow.setColor(CYAN)
        glow.setOffset(2, 2)
        self.setGraphicsEffect(glow)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def setText(self, html):
        self.label.setText(html)

    def _inner_rect(self):
        return self.rect().adjusted(22, 22, -22, -22)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(CYAN)
        pen.setWidth(BORDER_WIDTH)
        p.setPen(pen)
        p.drawRoundedRect(self.rect().adjusted(4, 4, -4, -4), RADIUS, RADIUS)
        p.end()

# ───────────────── EqualizerWidget (smooth random, cyan/pink)
class EqualizerWidget(QWidget):
    def __init__(self, parent=None, bar_count=20, fps=45, title="VISUALIZER"):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(250, 150)

        self.title_scale = 0.30
        self.title_px = 40
        self.bottom_pad = 0

        # Colors
        self.cyan = QColor("#00FFFF")
        self.pink = QColor("#ff00ff")
        self.title = title

        # Layout
        self.bar_count = bar_count
        self.h_pad = 20
        self.v_pad = 0
        self.gap = 5
        self.bar_radius = 0
        self.bar_width_scale = 1.2

        # Motion tuning (VU-ish)
        self.floor = 0.15
        self.fast_rise = 1.5
        self.slow_fall = 0.2
        self.noise_step = 0.12
        self.peak_decay = 0.050
        self.title_scale = 0.30

        # State
        self.values = [self.floor] * bar_count
        self.targets = [self.floor] * bar_count
        self.peaks = [self.floor] * bar_count
        self.phase = [random.random() * 10 for _ in range(bar_count)]

        # Timers
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(int(1000 / fps))

    def _clamp(self, v, lo=0.0, hi=1.0):
        return lo if v < lo else hi if v > hi else v

    def _tick(self):
        for i in range(self.bar_count):
            d = abs(i - (self.bar_count - 1) / 2) / ((self.bar_count - 1) / 2 + 1e-6)
            center_boost = 1.0 - 0.35 * d
            step = (random.random() * 2 - 1) * self.noise_step
            self.targets[i] = self._clamp(self.targets[i] + step)
            t = self.floor + (self.targets[i] * (0.8 - self.floor)) * center_boost

            if t > self.values[i]:
                self.values[i] += (t - self.values[i]) * self.fast_rise
            else:
                self.values[i] += (t - self.values[i]) * self.slow_fall

            if self.values[i] > self.peaks[i]:
                self.peaks[i] = self.values[i]
            else:
                self.peaks[i] = max(self.floor, self.peaks[i] - self.peak_decay)

        self.update()

    def _neon_rect_gradient(self, p: QPainter, x, y, w, h,
                            c_from: QColor, c_to: QColor, vertical=True):
        for a, expand in ((40, 4), (110, 2), (245, 0)):
            grad = QLinearGradient()
            if vertical:
                grad.setStart(0, int(y + h))
                grad.setFinalStop(0, int(y))
            else:
                grad.setStart(int(x), 0)
                grad.setFinalStop(int(x + w), 0)

            c1 = QColor(c_from)
            c2 = QColor(c_to)
            c2.setAlpha(int(a * 0.80))
            c1.setAlpha(a)
            grad.setColorAt(0.0, c1)
            grad.setColorAt(1, c2)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(
                int(x - expand / 2),
                int(y - expand / 2),
                int(w + expand),
                int(h + expand),
                int(self.bar_radius),
                int(self.bar_radius),
            )

    def _neon_text(self, p: QPainter, text, x, y, w, h, col: QColor):
        font = QFont("Neuropolitical", int(h * self.title_scale), QFont.Bold)
        if font.family() == "Sans Serif":
            font = QFont("Courier New", int(h * self.title_scale), QFont.Bold)

        p.setFont(font)
        p.setPen(col)
        p.setBrush(Qt.NoBrush)
        p.drawText(int(x), int(y + int(h * 0.7)), text)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        usable_w = w - self.h_pad * 2
        usable_h = h - self.v_pad * 2
        total_gaps = self.gap * (self.bar_count - 1)
        bar_w = max(
            5, int(((usable_w - total_gaps) / self.bar_count) * self.bar_width_scale)
        )
        x = self.h_pad + (
            usable_w - (bar_w * self.bar_count + self.gap * (self.bar_count - 1))
        ) // 2
        base_y = self.v_pad + usable_h + self.bottom_pad

        title_h = self.title_px
        self._neon_text(
            p, self.title.upper(), self.h_pad - 5, -13, w // 2, title_h, self.cyan
        )

        for i in range(self.bar_count):
            norm = max(self.floor, min(0.70, self.values[i]))
            bar_h = int(usable_h * norm)
            y = base_y - bar_h
            self._neon_rect_gradient(
                p, x, y, bar_w, bar_h, self.pink, self.cyan, vertical=True
            )
            x += bar_w + self.gap

        p.end()

# ───────────────── SystemStatusWidget (CPU / TEMP / RAM, green→red bars)
class SystemStatusWidget(QWidget):
    """
    Bottom-left system widget (PAGE 1):
      - CPU load %
      - CPU temperature °C
      - RAM usage %
    Bars are rectangular, green at low values, blending toward red at high values.
    Only text glows; no bar glow; transparent background.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.cpu_load = 0.0
        self.cpu_temp = 0.0
        self.ram_usage = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_metrics)
        self.timer.start(1000)
        self.update_metrics()

    # ── data helpers
    def _read_cpu_temp(self):
        if psutil is not None:
            try:
                temps = psutil.sensors_temperatures()
                for _, entries in temps.items():
                    if entries:
                        return float(entries[0].current)
            except Exception:
                pass
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                milli = float(f.read().strip())
            return milli / 1000.0
        except Exception:
            return random.uniform(40, 65)

    def update_metrics(self):
        if psutil is not None:
            try:
                self.cpu_load = float(psutil.cpu_percent(interval=None))
            except Exception:
                self.cpu_load = random.uniform(5, 80)
            try:
                mem = psutil.virtual_memory()
                self.ram_usage = float(mem.percent)
            except Exception:
                self.ram_usage = random.uniform(20, 90)
        else:
            self.cpu_load = random.uniform(5, 80)
            self.ram_usage = random.uniform(20, 90)

        self.cpu_temp = self._read_cpu_temp()
        self.update()

    # ── drawing helpers
    def _lerp_color(self, c1: QColor, c2: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, t))
        r = c1.red()   + (c2.red()   - c1.red())   * t
        g = c1.green() + (c2.green() - c1.green()) * t
        b = c1.blue()  + (c2.blue()  - c1.blue())  * t
        a = c1.alpha() + (c2.alpha() - c1.alpha()) * t
        return QColor(int(r), int(g), int(b), int(a))

        
    def _draw_glow_text(self, p, x, y, w, h, text, base_color, font, align):
        rect = QRectF(x, y, w, h)

        # Softer glow (lighter alpha, smaller offset)
        glow = QColor(base_color)
        glow.setAlpha(70)  # lower intensity

        p.setFont(font)
        p.setPen(glow)

        # Only 2-pixel soft blur instead of 4-direction bloom
        for dx, dy in ((0, -1), (0, 1)):
            r = rect.adjusted(dx, dy, dx, dy)
            p.drawText(r, align, text)

        # Crisp text
        p.setPen(base_color)
        p.drawText(rect, align, text)


    def _draw_row(self, p, x, y, w, label, value_str, percent):
        # fonts
        label_font = QFont("Neuropolitical", 16, )
        if label_font.family() == "Sans Serif":
            label_font = QFont("Courier New", 14, )
        value_font = QFont("Neuropolitical", 18, )
        if value_font.family() == "Sans Serif":
            value_font = QFont("Courier New", 18, )

        text_h = 16
        # glowing label
        self._draw_glow_text(
            p, x, y, w // 2, text_h, label, CYAN, label_font,
            Qt.AlignLeft | Qt.AlignVCenter
        )
        # glowing value
        self._draw_glow_text(
            p, x + w // 2, y, w // 2, text_h, value_str, PINK, value_font,
            Qt.AlignRight | Qt.AlignVCenter
        )

        # bar geometry
        bar_y = y + 22
        bar_h = 11
        bar_margin = 2
        bar_w = w
        

        # NO background strip anymore – pure transparent behind the bar

        pct = max(0.0, min(100.0, percent)) / 100.0
        fill_w = int(bar_w * pct)

        if fill_w > 0:
            green = QColor("#39FF14")
            red   = QColor("#ff5555")
            c_to = self._lerp_color(green, red, pct)
            green.setAlpha(230)
            c_to.setAlpha(230)

            grad = QLinearGradient()
            grad.setStart(x, bar_y)
            grad.setFinalStop(x + fill_w, bar_y)
            grad.setColorAt(0.0, green)
            grad.setColorAt(1.0, c_to)

            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(
                int(x + bar_margin),
                int(bar_y + bar_margin),
                max(0, fill_w - bar_margin * 2),
                bar_h - bar_margin * 2,
                2,2     
            )


    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        inner_x = 4
        inner_y = 2
        inner_w = self.width() - 1 * inner_x

        # CPU load
        self._draw_row(p, inner_x, inner_y, inner_w, "CPU", f"{self.cpu_load:4.0f}%", self.cpu_load)
        

        # CPU temp (normalize ~90°C)
        mid_y = inner_y + 47
        temp_pct = (self.cpu_temp / 90.0) * 100.0
        self._draw_row(p, inner_x, mid_y, inner_w, "TEMP", f"{self.cpu_temp:4.0f}°C", temp_pct)
        

        # RAM
        bot_y = mid_y + 47
        self._draw_row(p, inner_x, bot_y, inner_w, "RAM", f"{self.ram_usage:4.0f}%", self.ram_usage)
        

        p.end()

# ───────────────── Slide overlay with FULL-PAGE LINEAR SLIDE
class SlideOverlay(QWidget):
    """
    Draws two page snapshots and slides them fully across the screen.
    progress: 0 → 1
    direction: -1 = user swiped left  (next page comes from right)
               +1 = user swiped right (next page comes from left)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.pix_from = None
        self.pix_to = None
        self.progress = 0.0
        self.direction = -1
        self.animating = False
        self.hide()

    def start(self, pix_from: QPixmap, pix_to: QPixmap, direction: int):
        self.pix_from = pix_from
        self.pix_to = pix_to
        self.direction = -1 if direction < 0 else 1
        self.progress = 0.0
        self.animating = True
        if self.parent() is not None:
            self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    def stop(self):
        self.animating = False
        self.pix_from = None
        self.pix_to = None
        self.hide()

    def set_progress(self, p: float):
        self.progress = max(0.0, min(1.0, p))
        self.update()

    def paintEvent(self, _):
        if not self.animating or self.pix_from is None or self.pix_to is None:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        t = self.progress

        if self.direction < 0:
            from_x = int(-t * w)
            to_x   = int((1.0 - t) * w)
        else:
            from_x = int(t * w)
            to_x   = int(-(1.0 - t) * w)

        p.setOpacity(1.0)
        p.drawPixmap(from_x, 0, w, h, self.pix_from)
        p.drawPixmap(to_x,   0, w, h, self.pix_to)
        p.end()

# ───────────────── PCB layer (traces + dots + underline that move with widgets)
class PCBLayer(QWidget):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main = main_window
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        TL, TR, BL, BR = (
            self.main.top_left.geometry(),
            self.main.top_right.geometry(),
            self.main.bottom_left.geometry(),
            self.main.bottom_right.geometry(),
        )

        mid_x = (TL.right() + TR.left()) // 2
        top_bus_y, bot_bus_y = TL.center().y(), BL.center().y()
        tl_r = (TL.right() + PADDING, TL.center().y())
        tr_l = (TR.left() - PADDING, TR.center().y())
        bl_r = (BL.right() + PADDING, BL.center().y())
        br_l = (BR.left() - PADDING, BR.center().y())

        # top bus
        for o in BUS_OFFS:
            y = top_bus_y + o
            path = ortho_path(
                [
                    (tl_r[0], y),
                    (mid_x - 28, y),
                    (mid_x - 28, y + 12),
                    (mid_x - 12, y + 12),
                    (mid_x - 12, y),
                    (tr_l[0], y),
                ]
            )
            neon_stroke(p, path, CYAN, CORE)

        # bottom bus
        for o in BUS_OFFS:
            y = bot_bus_y + o
            path = ortho_path(
                [
                    (bl_r[0], y),
                    (mid_x + 28, y),
                    (mid_x + 28, y - 12),
                    (mid_x + 12, y - 12),
                    (mid_x + 12, y),
                    (br_l[0], y),
                ]
            )
            neon_stroke(p, path, CYAN, CORE)

        # mid vertical spines
        mid_gap_top = TL.bottom() + PADDING - 40
        mid_gap_bot = BR.top() - PADDING + 40
        for o in SPINE_OFFS:
            x = mid_x + o
            path = ortho_path(
                [
                    (x, mid_gap_top),
                    (x, (mid_gap_top + mid_gap_bot) // 2 - 27),
                    (x + 30, (mid_gap_top + mid_gap_bot) // 2 - 2),
                    (x, (mid_gap_top + mid_gap_bot) // 2 + 27),
                    (x, mid_gap_bot),
                ]
            )
            neon_stroke(p, path, CYAN, max(1, CORE // 3))

        # left zig traces
        left_inner_x = TL.left() + 70
        num_traces = 2
        gap_top = TL.bottom() + 4
        gap_bot = BL.top() - 4
        gap_height = gap_bot - gap_top
        spacing = max(1, gap_height // (num_traces + 1))
        for i in range(num_traces):
            y1 = gap_top + (i + 1) * spacing
            y2 = gap_bot - (i + 1) * spacing
            mid_y = (y1 + y2) // 2
            jog = -40 if i % 2 == 0 else 40
            path = ortho_path(
                [
                    (left_inner_x, y1),
                    (left_inner_x + jog, mid_y),
                    (left_inner_x, y2),
                ]
            )
            width = CORE if i % 2 == 0 else max(1, CORE // 2)
            neon_stroke(p, path, CYAN, width)

        # right vertical + branches
        right_x = TR.right() - 60
        gap_top_r, gap_bot_r = TR.bottom(), BR.top()
        center_y_r = (gap_top_r + gap_bot_r) // 2
        path = ortho_path([(right_x, gap_top_r), (right_x, gap_bot_r)])
        neon_stroke(p, path, CYAN, CORE)
        for o in BRANCH_OFFSETS:
            y = center_y_r + o
            if gap_top_r < y < gap_bot_r:
                path = ortho_path([(right_x, y), (right_x - 80, y)])
                neon_stroke(p, path, CYAN, max(1, CORE // 2))
                neon_dot(p, QPointF(right_x - 80, y), CYAN, 5)

        # pulsing traces between left widgets (static neon here)
        left_column_right = TL.right()
        start_x = left_column_right - 130
        start_y = TL.bottom()
        elbow1_y = start_y + 50
        mid_right_x = start_x + 44
        end_y = elbow1_y + 20
        mid_trace = ortho_path(
            [
                (start_x, start_y),
                (start_x, elbow1_y),
                (mid_right_x, elbow1_y),
                (mid_right_x, end_y),
            ]
        )
        neon_stroke(p, mid_trace, CYAN, CORE)
        neon_dot(p, QPointF(mid_right_x, end_y), CYAN, 6)

        start_x = left_column_right - 50
        elbow_y = start_y + 25
        end_x = start_x - 45
        mid_trace = ortho_path(
            [
                (start_x, start_y),
                (start_x, elbow_y),
                (end_x, elbow_y),
            ]
        )
        neon_stroke(p, mid_trace, CYAN, CORE)
        neon_dot(p, QPointF(end_x, elbow_y), CYAN, 6)

        # bottom pink double underline
        base_y = BR.bottom() + 4
        for w_ in (1, 3):
            path = ortho_path(
                [
                    (TL.left() + 20, base_y + 6 * w_),
                    (TR.right() - 40, base_y + 6 * w_),
                ]
            )
            neon_stroke(p, path, PINK, w_)

        p.end()

# ───────────────── Main Window
class MainWindow(QMainWindow):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            QApplication.quit()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cyberpunk Dashboard – PCB v11.12 (full-page swipe, moving PCB)")
        self.setFixedSize(640, 480)
        self.setStyleSheet("background-color:#0d0d0d;")
        self.setCursor(Qt.BlankCursor)

        # ── Page / swipe state
        self.current_page = 0        # 0 = main (temp), 1 = humidity/system/battery
        self._swipe_start_pos = None
        self._swipe_threshold = 80
        self.last_sensor = None

        # ── Page content layer
        self.page_layer = QWidget(self)
        self.page_layer.setGeometry(self.rect())
        self.page_layer.setAttribute(Qt.WA_TranslucentBackground, True)
        self.page_layer.setStyleSheet("background: transparent;")

        # PCB layer (moves with widgets)
        self.pcb_layer = PCBLayer(self, self.page_layer)
        self.pcb_layer.setGeometry(self.page_layer.rect())
        self.pcb_layer.lower()

        # Slide animation overlay
        self.slide_overlay = SlideOverlay(self)
        self._swipe_anim_running = False
        self._swipe_anim_direction = -1
        self._swipe_anim_target_page = 0
        self._swipe_anim_t = 0.0

        self.swipe_timer = QTimer(self)
        self.swipe_timer.timeout.connect(self._swipe_step)

        # Grid animation (background, fixed)
        self.grid_step = 40
        self.grid_offset_x = 0.5
        self.grid_offset_y = 0.5
        self.grid_timer = QTimer(self)
        self.grid_timer.timeout.connect(self.animate_grid)
        self.grid_timer.start(40)

        # Frames (children of page_layer)
        self.top_left = self._mk(EDGE_MARGIN_X, EDGE_MARGIN_Y, big=True)
        self.top_right = self._mk(
            self.width() - EDGE_MARGIN_X - WIDGET_W, EDGE_MARGIN_Y, big=False
        )
        self.bottom_left = self._mk(
            EDGE_MARGIN_X, self.height() - EDGE_MARGIN_Y - WIDGET_H, big=False
        )
        self.bottom_right = self._mk(
            self.width() - EDGE_MARGIN_X - WIDGET_W,
            self.height() - EDGE_MARGIN_Y - WIDGET_H,
            big=False,
        )

        # --- Top-left: time + cyan line + date (page 0 only) ---
        self.top_left.label.hide()
        self.tl_time_font = QFont("Neuropolitical", 41, QFont.Bold)
        if self.tl_time_font.family() == "Sans Serif":
            self.tl_time_font = QFont("Courier New", 41, QFont.Bold)
        self.tl_date_font = QFont("Neuropolitical", 16, QFont.Bold)
        if self.tl_date_font.family() == "Sans Serif":
            self.tl_date_font = QFont("Courier New", 16, QFont.Bold)

        self.time_lbl = QLabel(self.top_left)
        self.time_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl.setStyleSheet("background:transparent; color:#ff00ff;")

        self.date_lbl = QLabel(self.top_left)
        self.date_lbl.setAlignment(Qt.AlignCenter)
        self.date_lbl.setStyleSheet("background:transparent; color:#ff00ff;")

        self.td_line = QWidget(self.top_left)
        self.td_line.setStyleSheet("background:#00ffff;")
        tl_glow = QGraphicsDropShadowEffect(self.td_line)
        tl_glow.setBlurRadius(20)
        tl_glow.setColor(CYAN)
        tl_glow.setOffset(0, 0)
        self.td_line.setGraphicsEffect(tl_glow)

        self.time_lbl.setFont(self.tl_time_font)
        self.date_lbl.setFont(self.tl_date_font)

        # ── TOP-LEFT BATTERY WIDGET (DEMO, page 1 only)
        self.batt_volt_font = QFont("Neuropolitical", 33, QFont.Bold)
        if self.batt_volt_font.family() == "Sans Serif":
            self.batt_volt_font = QFont("Courier New", 33, QFont.Bold)

        self.batt_status_font = QFont("Neuropolitical", 16, QFont.Bold)
        if self.batt_status_font.family() == "Sans Serif":
            self.batt_status_font = QFont("Courier New", 16, QFont.Bold)

        self.batt_volt_lbl = QLabel(self.top_left)
        self.batt_volt_lbl.setAlignment(Qt.AlignCenter)
        self.batt_volt_lbl.setStyleSheet("background:transparent; color:#ff00ff;")
        self.batt_volt_lbl.setFont(self.batt_volt_font)

        self.batt_status_lbl = QLabel(self.top_left)
        self.batt_status_lbl.setAlignment(Qt.AlignCenter)
        self.batt_status_lbl.setStyleSheet("background:transparent; color:#00ffcc;")
        self.batt_status_lbl.setFont(self.batt_status_font)

        self.batt_line = QWidget(self.top_left)
        self.batt_line.setStyleSheet("background:#00ffff;")
        batt_glow = QGraphicsDropShadowEffect(self.batt_line)
        batt_glow.setBlurRadius(18)
        batt_glow.setColor(CYAN)
        batt_glow.setOffset(0, 0)
        self.batt_line.setGraphicsEffect(batt_glow)

        self._batt_phase = 0.0
        self.batt_timer = QTimer(self)
        self.batt_timer.timeout.connect(self.update_battery_demo)
        self.batt_timer.start(600)
        self.update_battery_demo()

        # Civic (bottom-left)
        self.civic_player = FramePlayerWidget(self.bottom_left, fps=25)
        w, h = self.bottom_left.width(), self.bottom_left.height()
        margin = -7
        self.civic_player.setGeometry(margin, margin, w - 2 * margin, h - 2 * margin)
        self.civic_player.load_dir(FRAMES_DIR)
        self.civic_player.start()

        self.bottom_left.label.hide()
        self.civic_player.raise_()
        eff = self.bottom_left.graphicsEffect()
        if isinstance(eff, QGraphicsDropShadowEffect):
            eff.setColor(PINK)
            eff.setBlurRadius(120)

        # SystemStatusWidget in bottom-left (for PAGE 1)
        self.system_widget = SystemStatusWidget(self.bottom_left)
        inner_bl = self.bottom_left._inner_rect()
        self.system_widget.setGeometry(inner_bl.x(), inner_bl.y(),
                                       inner_bl.width(), inner_bl.height())
        self.system_widget.hide()   # only shown on page 1

        # Sensors
        self.sensors = DualBME280()

        # Bottom-right: animated equalizer
        self.bottom_right.label.hide()
        self.equalizer = EqualizerWidget(
            self.bottom_right, bar_count=19, fps=60, title="Visualizer"
        )
        self.equalizer.setGeometry(
            11,
            13,
            self.bottom_right.width() + 8,
            self.bottom_right.height() + 8,
        )
        self.equalizer.show()

        # ── TOP-RIGHT: labels, values, underlines
        self.top_right.label.hide()
        self.tr_lab_font = QFont("Neuropolitical", 17, QFont.Bold)
        if self.tr_lab_font.family() == "Sans Serif":
            self.tr_lab_font = QFont("Courier New", 17, QFont.Bold)
        self.tr_val_font = QFont("Neuropolitical", VALUE_FONT_SIZE, QFont.Bold)
        if self.tr_val_font.family() == "Sans Serif":
            self.tr_val_font = QFont("Courier New", VALUE_FONT_SIZE, QFont.Bold)

        self.in_lab = QLabel("Inside:", self.top_right)
        self.out_lab = QLabel("Outside:", self.top_right)
        for lab in (self.in_lab, self.out_lab):
            lab.setStyleSheet("background:transparent; color:#00ffff;")
            lab.setFont(self.tr_lab_font)
            lab.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        self.in_val = QLabel("--", self.top_right)
        self.out_val = QLabel("--", self.top_right)
        for val in (self.in_val, self.out_val):
            val.setStyleSheet("background:transparent; color:#ff00ff;")
            val.setFont(self.tr_val_font)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setContentsMargins(0, 0, VAL_RIGHT_PAD, 0)

        self.line_inside = QWidget(self.top_right)
        self.line_outside = QWidget(self.top_right)
        for bar in (self.line_inside, self.line_outside):
            bar.setStyleSheet("background:#ff00ff;")
            glow = QGraphicsDropShadowEffect(bar)
            glow.setBlurRadius(LINE_GLOW)
            glow.setColor(PINK)
            glow.setOffset(0, 0)
            bar.setGraphicsEffect(glow)
            bar.show()
            bar.raise_()

        # Timers
        self.t_timer = QTimer(self)
        self.t_timer.timeout.connect(self.update_time)
        self.t_timer.start(1000)

        self.s_timer = QTimer(self)
        self.s_timer.timeout.connect(self.update_sensors)
        self.s_timer.start(5000)

        self._pulse_phase = 0.0
        self.pulse_timer = QTimer(self)
        self.pulse_timer.timeout.connect(self.animate_pulse)
        self.pulse_timer.start(40)

        # Initial layout + first page
        self.update_time()
        self.update_sensors()
        self.set_page(0)

    def _mk(self, x, y, big=False):
        w = GlowWidget("", self.page_layer, big=big)
        w.move(x, y)
        return w

    # ── Layouts
    def _layout_top_left(self):
        """
        Top-left widget:
        - Page 0: time + date
        - Page 1: battery voltage + status
        """
        inner = self.top_left._inner_rect()
        x, y, w, h = inner.x(), inner.y(), inner.width(), inner.height()

        if self.current_page == 0:
            # Show time/date, hide battery
            self.time_lbl.show()
            self.date_lbl.show()
            self.td_line.show()
            self.batt_volt_lbl.hide()
            self.batt_status_lbl.hide()
            self.batt_line.hide()

            fm_t = QFontMetrics(self.tl_time_font)
            fm_d = QFontMetrics(self.tl_date_font)
            time_h = fm_t.height()
            date_h = fm_d.height()

            time_y = y + 6
            self.time_lbl.setGeometry(x, time_y, w, time_h)

            line_y = time_y + time_h + 4
            line_w = int(w * 0.9)
            line_x = x + (w - line_w) // 2
            self.td_line.setGeometry(line_x, line_y, line_w, 3)

            date_y = line_y + 10
            self.date_lbl.setGeometry(x, date_y, w, date_h)
        else:
            # Show battery, hide time/date
            self.time_lbl.hide()
            self.date_lbl.hide()
            self.td_line.hide()
            self.batt_volt_lbl.show()
            self.batt_status_lbl.show()
            self.batt_line.show()

            fm_v = QFontMetrics(self.batt_volt_font)
            fm_s = QFontMetrics(self.batt_status_font)
            volt_h = fm_v.height()
            status_h = fm_s.height()

            volt_y = y + 12
            self.batt_volt_lbl.setGeometry(x, volt_y, w, volt_h)

            line_h = 3
            line_w = int(w * 0.90)
            line_x = x + (w - line_w) // 2
            line_y = volt_y + volt_h + 6
            self.batt_line.setGeometry(line_x, line_y, line_w, line_h)
            self.batt_line.raise_()

            status_y = line_y + line_h + 10
            self.batt_status_lbl.setGeometry(x, status_y, w, status_h)

    def _layout_top_right_rows(self):
        inner = self.top_right._inner_rect()
        x, y, w, h = inner.x(), inner.y(), inner.width(), inner.height()
        gap = 16
        row_h = max(1, (h - gap) // 2)
        pad_left, pad_right = 10, 10

        content_x = x + pad_left
        content_w = max(0, w - (pad_left + pad_right))

        lab_w = min(LABEL_COL_W + LABEL_VAL_GAP, content_w - 80)
        val_x = content_x + lab_w
        val_w = max(80, content_w - lab_w - SAFE_RIGHT)

        self.in_lab.setGeometry(content_x, y, lab_w, row_h)
        self.in_val.setGeometry(val_x, y, val_w, row_h)
        self.out_lab.setGeometry(content_x, y + row_h + gap, lab_w, row_h)
        self.out_val.setGeometry(val_x, y + row_h + gap, val_w, row_h)

        bar_w = max(60, content_w - 12 - SAFE_RIGHT)
        self.line_inside.setGeometry(content_x, y + row_h - 6, bar_w, LINE_THICK)
        self.line_outside.setGeometry(
            content_x, y + row_h + gap + row_h - 6, bar_w, LINE_THICK
        )
        self.line_inside.raise_()
        self.line_outside.raise_()

    # ── Page handling
    def set_page(self, page_index: int):
        """
        0 = main page → time/date + °C + civic + equalizer
        1 = second page → battery + % humidity + system widget (bottom-left)
        """
        self.current_page = max(0, min(1, page_index))

        civic_eq_widgets = (self.civic_player, self.equalizer)

        if self.current_page == 0:
            for w in civic_eq_widgets:
                w.show()
            self.system_widget.hide()
        else:
            for w in civic_eq_widgets:
                w.hide()
            self.system_widget.show()

        # top-right always visible
        for w in (
            self.in_lab, self.out_lab, self.in_val, self.out_val,
            self.line_inside, self.line_outside
        ):
            w.show()

        self._layout_top_left()
        self._layout_top_right_rows()
        self._update_top_right_display()
        self.pcb_layer.update()
        self.update()

    # ── Swipe animation control
    def start_swipe_anim(self, direction: int, target_page: int):
        if self._swipe_anim_running:
            return

        self.page_layer.show()
        QApplication.processEvents()

        pix_from = self.page_layer.grab()

        old_page = self.current_page
        self.set_page(target_page)
        QApplication.processEvents()
        pix_to = self.page_layer.grab()

        self.set_page(old_page)
        QApplication.processEvents()

        self.page_layer.hide()

        self._swipe_anim_running = True
        self._swipe_anim_direction = -1 if direction < 0 else 1
        self._swipe_anim_target_page = target_page
        self._swipe_anim_t = 0.0

        self.slide_overlay.start(pix_from, pix_to, self._swipe_anim_direction)
        self.swipe_timer.start(16)

    def _swipe_step(self):
        self._swipe_anim_t += 0.06
        if self._swipe_anim_t > 1.0:
            self._swipe_anim_t = 1.0

        self.slide_overlay.set_progress(self._swipe_anim_t)

        if self._swipe_anim_t >= 1.0:
            self.swipe_timer.stop()
            self.slide_overlay.stop()
            self.page_layer.show()
            self.set_page(self._swipe_anim_target_page)
            self._swipe_anim_running = False

    # ── Swipe detection
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._swipe_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self._swipe_start_pos is not None and event.button() == Qt.LeftButton:
            dx = event.pos().x() - self._swipe_start_pos.x()
            dy = event.pos().y() - self._swipe_start_pos.y()

            if abs(dx) > self._swipe_threshold and abs(dx) > abs(dy):
                if dx < 0 and self.current_page == 0:
                    self.start_swipe_anim(direction=-1, target_page=1)
                elif dx > 0 and self.current_page == 1:
                    self.start_swipe_anim(direction=+1, target_page=0)

        self._swipe_start_pos = None
        super().mouseReleaseEvent(event)

    # ── Other updaters & animators
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.page_layer.setGeometry(self.rect())
        self.pcb_layer.setGeometry(self.page_layer.rect())
        self._layout_top_right_rows()
        self._layout_top_left()
        if self.slide_overlay is not None:
            self.slide_overlay.setGeometry(self.rect())

    def update_time(self):
        now = datetime.datetime.now()
        self.time_lbl.setText(now.strftime("%H:%M"))
        self.date_lbl.setText(now.strftime("%d-%m-%Y"))
        self._layout_top_left()

    def update_battery_demo(self):
        import math
        self._batt_phase += 0.09
        v = 13.1 + 1.3 * math.sin(self._batt_phase)
        v = max(11.8, min(14.4, v))
        self.batt_voltage = round(v, 2)

        self.batt_volt_lbl.setText(f"{self.batt_voltage:.2f} V")

        if v >= 12.4:
            status = "BATTERY OK"
            col = "#39ff14"
        elif v >= 12.0:
            status = "CHECK SOON"
            col = "#ffff55"
        else:
            status = "LOW BATTERY"
            col = "#ff5555"

        self.batt_status_lbl.setText(status)
        self.batt_status_lbl.setStyleSheet(
            f"background:transparent; color:{col};"
        )
        self._layout_top_left()

    def _render_top_right_rows(self, inside_text: str, outside_text: str):
        self.in_val.setText(inside_text)
        self.out_val.setText(outside_text)
        self._layout_top_right_rows()

    def _update_top_right_display(self):
        if self.last_sensor is None:
            inside_text = outside_text = "--"
        else:
            d = self.last_sensor
            if self.current_page == 0:
                it = d.get("inside_temp")
                ot = d.get("outside_temp")
                inside_text = f"{it}°C" if it is not None else "--"
                outside_text = f"{ot}°C" if ot is not None else "--"
            else:
                ih = d.get("inside_hum")
                oh = d.get("outside_hum")
                inside_text = f"{ih}%" if ih is not None else "--"
                outside_text = f"{oh}%" if oh is not None else "--"
        self._render_top_right_rows(inside_text, outside_text)

    def update_sensors(self):
        d = self.sensors.read()
        self.last_sensor = d
        self._update_top_right_display()
        print(
            f"[{d['source']}] "
            f"IN={d.get('inside_temp')}°C {d.get('inside_hum')}% | "
            f"OUT={d.get('outside_temp')}°C {d.get('outside_hum')}% ok={d['ok']}"
        )

    def animate_grid(self):
        self.grid_offset_x += 0.5
        self.grid_offset_y += 0.5
        self.update()

    def animate_pulse(self):
        self._pulse_phase += 0.12
        self.update()

    # ── Painter (GRID ONLY – stays fixed while pages slide)
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grid_color = QColor(100, 100, 100, 150)
        pen = QPen(grid_color)
        pen.setWidth(1)
        p.setPen(pen)
        step = 40
        ox, oy = self.grid_offset_x, self.grid_offset_y

        for x in range(-step * 2, self.width() + step * 2, step):
            xp = int(x + (ox % step))
            p.drawLine(xp, 0, xp, self.height())

        for y in range(-step * 2, self.height() + step * 2, step):
            yp = int(y + (oy % step))
            p.drawLine(0, yp, self.width(), yp)

        p.end()

# ───────────────── Run
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setOverrideCursor(Qt.BlankCursor)

    win = MainWindow()
    win.setWindowFlags(Qt.FramelessWindowHint)
    win.showFullScreen()

    from PyQt5.QtGui import QCursor
    from PyQt5.QtCore import QPoint

    try:
        geo = app.primaryScreen().availableGeometry()
        QCursor.setPos(geo.right() - 1, geo.bottom() - 1)
    except Exception:
        pass

    sys.exit(app.exec_())


import re
from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.utils import get_color_from_hex

BG               = "#0e0e11"
BTN_DIGIT        = "#26262c"
BTN_FUNC         = "#3a3a42"
BTN_OP           = "#ff9f0a"
BTN_EQ           = "#5e5ce6"
TEXT_MAIN        = "#f2f2f7"
TEXT_MUTED       = "#8e8e95"
TEXT_ON_OP       = "#1b1200"
RESULT_LIVE      = "#b9b9c0"
RESULT_COMMITTED = "#ffffff"
RESULT_ERROR     = "#ff453a"

SPACE_SM = dp(4)
SPACE_MD = dp(8)
SPACE_LG = dp(12)

Window.clearcolor = get_color_from_hex(BG)

def normalize(expr: str) -> str:
    return expr.replace("×", "*").replace("÷", "/").replace("−", "-")

def evaluate(expr: str):
    if not expr:
        return True, ""
    py = normalize(expr).replace("**", "^").replace("//", "&")
    if len(py) > 500:
        return False, ""
    prev = None
    while prev != py:
        prev = py
        py = re.sub(r"[+\-][+\-]", lambda m: "+" if m.group(0)[0] == m.group(0)[1] else "-", py)
    m = re.match(r"^(\d+(?:\.\d+)?)([+\-])(\d+(?:\.\d+)?)%$", py)
    if m:
        a, op, b = float(m.group(1)), m.group(2), float(m.group(3))
        delta = a * b / 100
        return True, a + delta if op == "+" else a - delta
    py = re.sub(r"(\d+(?:\.\d+)?)%", r"(\1/100)", py)
    py = re.sub(r"(\d)(\()", r"\1*\2", py)
    py = re.sub(r"(\))(\()", r"\1*\2", py)
    py = re.sub(r"(\))(\d)", r"\1*\2", py)
    allowed = set("0123456789.+-*/() ")
    if set(py) - allowed or not py.strip():
        return (False if set(py) - allowed else True), ""
    try:
        value = eval(py, {"__builtins__": None}, {})
        if isinstance(value, int) and abs(value) > 1e15:
            return False, ""
        return True, value
    except ZeroDivisionError:
        return False, "Error"
    except Exception:
        return False, ""

def _group(text: str) -> str:
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    int_part, dot, frac = text.partition(".")
    if not (int_part.isdigit() and len(int_part) > 3):
        return ("-" if neg else "") + text
    return ("-" if neg else "") + f"{int(int_part):,}" + (dot + frac if frac else "")

def format_result(value) -> str:
    if isinstance(value, float):
        if value.is_integer() and abs(value) < 1e15:
            return _group(str(int(value)))
        return _group(f"{value:.10g}")
    if isinstance(value, int):
        return _group(str(value))
    return str(value)

class RoundButton(Button):
    bg_bright = NumericProperty(1.0)
    def __init__(self, bg_hex, fg_hex, font_size, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self._bg = get_color_from_hex(bg_hex)
        self._fg = get_color_from_hex(fg_hex)
        self.font_size = font_size
        self.bold = True
        self.color = self._fg
        self.bind(size=self._redraw, pos=self._redraw, state=self._on_state)
        self.bind(bg_bright=lambda *_: self._redraw())
        self._redraw()

    def _on_state(self, _inst, state):
        Animation(bg_bright=1.35 if state == "down" else 1.0, duration=0.08 if state == "down" else 0.12, t="out_quad").start(self)

    def _redraw(self, *args):
        if self.width and self.height:
            self.font_size = max(sp(16), min(self.width, self.height) * 0.38)
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*[min(1.0, c * self.bg_bright) for c in self._bg])
            radius = min(self.width, self.height) / 2 if self.width and self.height else dp(22)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[radius])

class CalculatorApp(App):
    def build(self):
        self.just_evaluated = False
        self._hold_start = None
        self._hold_event = None
        self._hold_ran = False
        self._portrait = None
        root = self.root_box = BoxLayout(padding=SPACE_LG, spacing=SPACE_LG)
        display = BoxLayout(orientation="vertical", size_hint=(1, 0.30), padding=[SPACE_LG, SPACE_MD, SPACE_LG, 0], spacing=SPACE_SM)
        self.expr_label = Label(text="", font_size=sp(22), color=get_color_from_hex(TEXT_MUTED), halign="right", valign="bottom", bold=True)
        self.result_label = Label(text="0", font_size=sp(56), color=get_color_from_hex(TEXT_MAIN), halign="right", valign="top", bold=True)
        for lbl in (self.expr_label, self.result_label):
            lbl.bind(size=lambda inst, s: setattr(inst, "text_size", s))
            display.add_widget(lbl)
        bar = BoxLayout(orientation="horizontal", size_hint=(1, None), height=dp(44), spacing=SPACE_MD)
        ac_btn = RoundButton(BTN_FUNC, TEXT_MAIN, dp(16), text="AC")
        bs_btn = RoundButton(BTN_FUNC, TEXT_MAIN, dp(16), text="DEL")
        ac_btn.bind(on_release=self.on_key)
        self._bs_btn = bs_btn
        bs_btn.bind(on_press=self._bs_press, on_release=self._bs_release)
        bar.add_widget(ac_btn)
        bar.add_widget(bs_btn)
        display.add_widget(bar)
        self.display_box = display
        keys = [["(", ")", "%", "÷"], ["7", "8", "9", "×"], ["4", "5", "6", "−"], ["1", "2", "3", "+"], ["±", "0", ".", "="]]
        self.pad = GridLayout(cols=4, size_hint=(1, 0.70), spacing=SPACE_LG, padding=SPACE_SM)
        for row in keys:
            for key in row:
                style = (BTN_FUNC, TEXT_MAIN) if key in ("(", ")", "%", "±") else ((BTN_EQ, "#ffffff") if key == "=" else ((BTN_OP, TEXT_ON_OP) if key in ("÷", "×", "−", "+") else (BTN_DIGIT, TEXT_MAIN)))
                btn = RoundButton(*style, dp(30), text=key)
                btn.bind(on_release=self.on_key)
                self.pad.add_widget(btn)
        Window.bind(size=self._relayout)
        Clock.schedule_once(lambda *_: self._relayout(), 0)
        return root

    def _relayout(self, *_args):
        portrait = Window.height >= Window.width
        w, h = Window.width, Window.height
        if portrait:
            self.result_label.font_size = min(sp(56), w * 0.15, dp(72))
            self.expr_label.font_size = max(sp(16), self.result_label.font_size * 0.4)
            if self._portrait is not True:
                self._portrait = True
                self.root_box.orientation = "vertical"
                self.root_box.clear_widgets()
                self.display_box.size_hint = (1, 0.30)
                self.pad.size_hint = (1, 0.70)
                self.root_box.add_widget(self.display_box)
                self.root_box.add_widget(self.pad)
        else:
            self.result_label.font_size = min(sp(56), h * 0.22, dp(72))
            self.expr_label.font_size = max(sp(14), self.result_label.font_size * 0.4)
            if self._portrait is not False:
                self._portrait = False
                self.root_box.orientation = "horizontal"
                self.root_box.clear_widgets()
                self.display_box.size_hint = (0.42, 1)
                self.pad.size_hint = (0.58, 1)
                self.root_box.add_widget(self.display_box)
                self.root_box.add_widget(self.pad)
        Clock.schedule_once(lambda *_: self._shrink(), 0)

    def _shrink(self):
        r = self.result_label
        if r.texture and r.texture_size[0] > r.width and r.width > 0:
            r.font_size = max(sp(24), self.result_label.font_size * 0.8)

    def on_key(self, btn):
        key = btn.text
        expr = self.expr_label.text.rstrip(" =")
        if key == "AC":
            self.expr_label.text = ""
            self._set_result("0", committed=True)
            self._relayout()
            self.just_evaluated = False
            return
        if key == "DEL":
            self._do_backspace()
            return
        if key == "±":
            if expr.endswith("(-"):
                self.expr_label.text = expr[:-2]
                self._preview(self.expr_label.text)
                return
            m = re.search(r"(-?\d+(?:\.\d+)?)$", expr)
            if m:
                num = m.group(1)
                head = expr[: m.start()]
                self.expr_label.text = head + (f"(-{num})" if not num.startswith("-") else num[1:])
            elif not self.just_evaluated:
                self.expr_label.text = expr + "(-"
            else:
                self._start_new(f"(-{self.result_label.text.replace(',', '')})")
            self._preview(self.expr_label.text)
            return
        if key == "(":
            if self.just_evaluated:
                self._start_new("(")
                return
            self.expr_label.text = expr + "("
            self._preview(expr + "(")
            return
        if key == ")":
            opens = expr.count("(") - expr.count(")")
            if self.just_evaluated or opens <= 0 or expr[-1:] in ("÷", "×", "−", "+", "("):
                return
            self.expr_label.text = expr + ")"
            self._preview(expr + ")")
            return
        if key == "=":
            opens = expr.count("(") - expr.count(")")
            if opens > 0:
                expr += ")" * opens
            ok, value = evaluate(expr)
            if ok and value != "":
                self.expr_label.text = expr + " ="
                self._set_result(format_result(value), committed=True)
                self.just_evaluated = True
            elif not ok and value:
                self._set_result("Error", committed=True, error=True)
            return
        if self.just_evaluated:
            if key.isdigit() or key == ".":
                self._start_new(key)
                return
            self.expr_label.text = self.result_label.text.replace(",", "") + key
            self.just_evaluated = False
            self._preview(self.expr_label.text)
            return
        if key in ("÷", "×", "−", "+") and (expr == "" or expr[-1:] in ("÷", "×", "−", "+")):
            if expr and expr[-1:] in ("÷", "×", "−", "+"):
                expr = expr[:-1] + key
                self.expr_label.text = expr
                self._preview(expr)
            return
        if key == ".":
            m = re.search(r"\d*\.?\d*$", expr)
            if m and "." in m.group(0):
                return
        self.expr_label.text = expr + key
        self._preview(expr + key)

    def _start_new(self, first_char):
        self.expr_label.text = first_char
        self.just_evaluated = False
        self._preview(first_char)

    def _set_result(self, text, committed=True, error=False):
        lbl = self.result_label
        color = RESULT_ERROR if error else (RESULT_COMMITTED if committed else RESULT_LIVE)
        if lbl.text != text:
            lbl.opacity = 0.35
            Animation(opacity=1, duration=0.18, t="out_quad").start(lbl)
        lbl.text = text
        lbl.color = get_color_from_hex(color)
        self._relayout()
        Clock.schedule_once(lambda *_: self._shrink(), 0)

    def _bs_press(self, btn):
        self._hold_ran = False
        self._hold_start = Clock.schedule_once(self._begin_hold, 0.45)

    def _begin_hold(self, dt):
        self._hold_ran = True
        self._hold_event = Clock.schedule_interval(lambda *_: self._do_backspace(), 0.08)

    def _bs_release(self, btn):
        if self._hold_start:
            self._hold_start.cancel()
            self._hold_start = None
        if self._hold_event:
            self._hold_event.cancel()
            self._hold_event = None
        if not self._hold_ran:
            self.on_key(btn)

    def _do_backspace(self, *_args):
        if self.just_evaluated:
            self.expr_label.text = ""
            self._set_result("0", committed=True)
            self.just_evaluated = False
        else:
            self.expr_label.text = self.expr_label.text.rstrip(" =")[:-1]
        self._preview(self.expr_label.text)

    def _preview(self, expr):
        ok, value = evaluate(expr)
        if ok and value != "":
            self._set_result(format_result(value), committed=False)
        elif expr == "":
            self._set_result("0", committed=False)

if __name__ == "__main__":
    CalculatorApp().run()
EOF

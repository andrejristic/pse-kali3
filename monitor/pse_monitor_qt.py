#!/usr/bin/env python3
# =============================================================================
# PSE-KALI — NATIVE CONSOLE (PySide6, QPainter)  ·  LIVE STEERING + MODEL SWAP
# The governed swarm, driven and steered from a native window (no browser):
#   · the simplex + audit table (four units live)
#   · a COMMAND panel — talk to the commander; it re-tasks the units live
#   · APPROVALS — judgment holds surface here to approve/deny (the floor stays
#     a hard wall, shown as denied, never one-click approved)
#   · a MODEL dropdown — hot-swap the local GGUF mid-engagement
#
#   pip install PySide6
#   python3 monitor/pse_monitor_qt.py [--backend gguf:models/..gguf|mock] [--execute]
# View-only (no engine) if a backend can't be built: still shows the audit log.
# =============================================================================
import argparse
import math
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, REPO)
from audit_to_timeline import records_from_audit

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
                               QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
                               QHeaderView, QComboBox, QPushButton, QLineEdit,
                               QTextEdit, QFrame, QScrollArea, QMenu)
from PySide6.QtGui import (QPainter, QColor, QPen, QBrush, QPolygonF, QFont,
                           QShortcut, QKeySequence, QAction)
from PySide6.QtCore import Qt, QTimer, QPointF, QPoint

# ---- coordinated cool-jewel palette (same as the web console) --------------
H = math.sqrt(3) / 2
EPS = 0.28
UNIT_COLORS = {"recon": "#38bdf8", "password": "#a78bfa", "sniff": "#34d399",
               "access": "#e879f9"}
C_BLOCK, C_FLOOR, C_ACCENT = "#fb7185", "#fbbf24", "#22d3ee"
C_TRI, C_FILL = "#26374d", "#0e1826"
C_INK, C_MUTED, C_BG = "#e8eef7", "#6b7a90", "#0b0f17"
C_SURFACE, C_LINE = "#111826", "#1e293b"
PAD = 30
AUDIT = os.path.join(REPO, "audit", "engagement.jsonl")
MODELS_DIR = os.path.join(REPO, "models")
APPROVE_SH = os.path.join(HERE, "_approve_run.sh")

# --- attack / defend targets (edit these two lines for your setup) ----------
LAB = "10.10.10.5"          # the docker lab target (recon/password/sniff lessons)
PEER = "PEER-IP"            # the OTHER machine for the ssh lesson:
#   Smer A: your machine's IP (Margaret logs into you) — e.g. 10.0.0.109
#   Smer B: Margaret's laptop IP (you reach her; she defends)

# =============================================================================
# ATTACK / DEFEND CATALOG  — one editable place. Each item is
#   (menu label, shell command, needs_root)
# Attacks go through the governed run_action.py (kernel scores every one).
# Defenses are the matching countermeasure for that tool. <LAB>/<PEER> are
# substituted at click time. Nothing here runs until the operator approves in a
# terminal AND types their password (see _approve_run.sh).
# =============================================================================
_RA = "python3 run_action.py"
_CFG = "--config config.yaml --execute"
UNIT_ACTIONS = {
    "recon": {
        "attack": [
            ("nmap -sV  →  <LAB>  (in scope · ALLOWED)",
             f"{_RA} recon nmap <LAB> --args='-sV' --rationale 'enumerate in scope' {_CFG}", False),
            ("nmap -sV  →  8.8.8.8  (out of scope · HELD)",
             f"{_RA} recon nmap 8.8.8.8 --args='-sV' --rationale 'curious' {_CFG}", False),
        ],
        "defend": [
            ("ufw enable  —  hide the open ports",
             "ufw --force enable && ufw status verbose", True),
            ("ufw disable —  open the ports again",
             "ufw disable", True),
        ],
    },
    "password": {
        "attack": [
            ("hashcat  →  crack the lab hash (finds hunter2)",
             f"HASH=$(curl -s http://<LAB>:8000/hashes.txt); echo \"hash: $HASH\"; "
             f"{_RA} password hashcat <LAB> --artifact \"$HASH\" --args='-m 500 words.txt' "
             f"--rationale 'credential audit in scope' {_CFG}", False),
            ("hashcat  →  8.8.8.8  (out of scope · HELD)",
             f"HASH=$(curl -s http://<LAB>:8000/hashes.txt); "
             f"{_RA} password hashcat 8.8.8.8 --artifact \"$HASH\" --args='-m 500 words.txt' "
             f"--rationale 'x' {_CFG}", False),
        ],
        "defend": [
            ("set a STRONG password on 'margaret' (crack fails)",
             "printf 'margaret:S7rong-%s-pw!\\n' \"$RANDOM$RANDOM\" | chpasswd && "
             "echo 'margaret now has a strong password — the wordlist will not find it.'", True),
        ],
    },
    "sniff": {
        "attack": [
            ("tcpdump  →  capture <LAB> traffic (in scope · ALLOWED)",
             f"{_RA} sniff tcpdump <LAB> --rationale 'traffic analysis in scope' {_CFG}", False),
            ("tcpdump  →  8.8.8.8  (out of scope · HELD)",
             f"{_RA} sniff tcpdump 8.8.8.8 --rationale 'x' {_CFG}", False),
        ],
        "defend": [
            ("show why SSH/TLS defeats sniffing",
             "echo 'Defense against sniffing = ENCRYPTION. Over SSH/HTTPS the captured "
             "packets are ciphertext; the sniffer sees traffic exists but not its content.'", False),
        ],
    },
    "access": {
        "attack": [
            ("ssh  →  drop 'margaret was here' on <PEER>  (ALLOWED)",
             f"{_RA} access ssh <PEER> --user margaret "
             f"--command 'echo \"margaret was here\" > ~/Desktop/margaret_was_here.txt' "
             f"--rationale 'authorized marker' {_CFG}", False),
            ("ssh  →  'rm -rf /' on <PEER>  (over-reach · HELD)",
             f"{_RA} access ssh <PEER> --user margaret --command 'rm -rf /' "
             f"--rationale 'authorized' {_CFG}", False),
            ("ssh  →  8.8.8.8  (out of scope · HELD)",
             f"{_RA} access ssh 8.8.8.8 --user margaret --command 'echo hi' "
             f"--rationale 'x' {_CFG}", False),
        ],
        "defend": [
            ("ssh KEY-ONLY  (PasswordAuthentication no)",
             "sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication no/' "
             "/etc/ssh/sshd_config && systemctl restart ssh && "
             "echo 'Password logins are now OFF — only holders of an authorized key get in.'", True),
            ("allow ssh passwords again",
             "sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication yes/' "
             "/etc/ssh/sshd_config && systemctl restart ssh", True),
            ("install + enable fail2ban  (bans repeat attempts)",
             "apt install -y fail2ban && systemctl enable --now fail2ban && "
             "fail2ban-client status sshd 2>/dev/null || true", True),
        ],
    },
}


class Simplex(QWidget):
    def __init__(self):
        super().__init__()
        self.records = []
        self.setMinimumSize(460, 420)

    def set_records(self, recs):
        self.records = recs
        self.update()

    def _geom(self):
        w, h = self.width(), self.height()
        S = min(w - 2 * PAD, (h - 2 * PAD) / H)
        ox = PAD + (w - 2 * PAD - S) / 2
        return S, ox

    def _pt(self, ws, wo, wf):
        S, ox = self._geom()
        x, y = wo + wf * 0.5, wf * H
        return QPointF(ox + x * S, PAD + S * H - y * S)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_BG))
        S, _ox = self._geom()
        A, B, Cc = self._pt(1, 0, 0), self._pt(0, 1, 0), self._pt(0, 0, 1)
        p.setBrush(QBrush(QColor(C_FILL)))
        p.setPen(QPen(QColor(C_TRI), 1))
        p.drawPolygon(QPolygonF([A, B, Cc]))
        r = EPS / math.sqrt(2) * S
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(C_BLOCK), 1, Qt.DashLine))
        for corner in (A, B):
            p.drawEllipse(corner, r, r)
        p.setPen(QColor(C_MUTED))
        p.setFont(QFont("monospace", getattr(self, "corner_pt", 13)))
        p.drawText(A + QPointF(-6, 16), "NARCISSISTIC")
        p.drawText(B + QPointF(-52, 16), "CODEPENDENT")
        p.drawText(Cc + QPointF(-24, -8), "SCHIZOID")
        by_unit = {}
        for r_ in self.records:
            by_unit.setdefault(r_["unit"], []).append(r_)
        for unit, seq in by_unit.items():
            col = QColor(UNIT_COLORS.get(unit, "#888888"))
            passed = [self._pt(*x["w"]) for x in seq if x["allowed"]]
            trail = QColor(col); trail.setAlpha(90)
            p.setPen(QPen(trail, 1.5))
            for i in range(1, len(passed)):
                p.drawLine(passed[i - 1], passed[i])
            for x in seq:
                pt = self._pt(*x["w"])
                if x["allowed"]:
                    p.setPen(QPen(QColor(C_BG), 1)); p.setBrush(QBrush(col))
                    p.drawEllipse(pt, 5, 5)
                else:
                    c = QColor(C_FLOOR if x.get("floor") else C_BLOCK)
                    p.setBrush(Qt.NoBrush); p.setPen(QPen(c, 2))
                    p.drawEllipse(pt, 7, 7)
                    p.setBrush(QBrush(c)); p.setPen(Qt.NoPen)
                    p.drawEllipse(pt, 2, 2)
        p.end()


# ---- build a LiveEngine from config (or return None for view-only) ---------
def build_engine(backend_spec, execute):
    try:
        from pse_kernel import make_backend, SwappableBackend
        from pse_kernel.engine import assemble
        from pse_kernel.adapters import lab_adapters
        from packs.recon import RECON_PACK
        from packs.password import PASSWORD_PACK
        from packs.sniff import SNIFF_PACK
        from packs.access import ACCESS_PACK

        scope = ["10.10.10.0/24"]
        authz = [{"target_scope": ["10.10.10.0/24"],
                  "tools": ["nmap", "masscan", "hashcat", "john", "tcpdump", "tshark", "ssh"]}]
        gguf_opts = {}
        try:
            import yaml
            cfg = yaml.safe_load(open(os.path.join(REPO, "config.yaml"))) or {}
            scope = cfg.get("scope", scope)
            authz = cfg.get("authorizations", authz)
            gguf_opts = cfg.get("gguf", {})
            backend_spec = backend_spec or cfg.get("backend")
        except Exception:
            pass
        backend_spec = backend_spec or "mock"
        kw = gguf_opts if backend_spec.startswith("gguf") else {}
        raw = make_backend(backend_spec, **({"scripted": []} if backend_spec == "mock" else kw))
        proxy = SwappableBackend(raw, name=backend_spec.split(":")[-1] or backend_spec)
        packs = {"recon": RECON_PACK, "password": PASSWORD_PACK,
                 "sniff": SNIFF_PACK, "access": ACCESS_PACK}
        adapters = lab_adapters(execute=execute)
        goals = {"recon": "map in-scope hosts and services",
                 "password": "audit in-scope credentials",
                 "sniff": "capture in-scope traffic",
                 "access": "gain authorized access and leave an agreed marker"}
        open(AUDIT, "w").close()
        engine, ctx, control, proxy = assemble(packs, adapters, proxy, scope, authz,
                                               goals, AUDIT)
        if execute:
            ctx.add_finding({"kind": "hash", "target": "10.10.10.5",
                             "artifact": "$1$xyz$deadbeef"})
        return engine, control, proxy
    except Exception as e:      # noqa - GUI still runs view-only
        print(f"[engine] not started ({e}); view-only mode")
        return None, None, None


def _hline():
    f = QFrame(); f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"color:{C_LINE};"); return f

def _h3(text):
    l = QLabel(text); l.setStyleSheet(
        f"color:{C_MUTED};font-weight:600;letter-spacing:1px;")
    return l


class Console(QMainWindow):
    def __init__(self, engine, control, proxy):
        super().__init__()
        self.engine, self.control, self.proxy = engine, control, proxy
        self._mtime = -1
        self._escrows = {}     # escalation id -> row widget
        self.setWindowTitle("PSE-Kali · Governed Security Console")
        self.font_pt = 20                 # ~20, adjustable with A− / A+ / Ctrl±
        self._build()
        self._apply_style()
        self._fit_window()
        QShortcut(QKeySequence.ZoomIn, self, activated=lambda: self._bump_font(2))
        QShortcut(QKeySequence.ZoomOut, self, activated=lambda: self._bump_font(-2))
        self._timer = QTimer(self); self._timer.timeout.connect(self._poll)
        self._timer.start(800)
        if self.engine:
            self.engine.start()
        self._poll()

    # ---- font size + window fit --------------------------------------------
    def _apply_style(self):
        b = self.font_pt
        self.setStyleSheet(f"""
            QMainWindow,QWidget{{background:{C_BG};color:{C_INK};
                font-family:'system-ui','Segoe UI',sans-serif;font-size:{b}px;}}
            QLineEdit,QTextEdit,QComboBox,QTableWidget{{background:{C_SURFACE};
                border:1px solid {C_LINE};border-radius:8px;color:{C_INK};}}
            QLineEdit,QComboBox{{padding:{max(6, b//2)}px 12px;}}
            QTextEdit{{font-family:'ui-monospace',monospace;font-size:{b}px;}}
            QPushButton{{background:{C_SURFACE};border:1px solid {C_LINE};
                border-radius:8px;padding:{max(6, b//2)}px 16px;color:{C_INK};font-size:{b}px;}}
            QPushButton:hover{{border-color:{C_ACCENT};}}
            QPushButton#primary{{background:{C_ACCENT};color:#04222a;font-weight:600;border:none;}}
            QPushButton#tiny{{padding:2px 12px;}}
            QHeaderView::section{{background:{C_SURFACE};color:{C_MUTED};border:none;
                border-bottom:1px solid {C_LINE};padding:8px;font-size:{max(11, b - 4)}px;}}
            QTableWidget{{font-size:{max(12, b - 3)}px;}}
        """)
        if hasattr(self, "simplex"):
            self.simplex.corner_pt = max(9, int(b * 0.62))
            self.simplex.update()

    def _bump_font(self, delta):
        self.font_pt = max(12, min(40, self.font_pt + delta))
        self._apply_style()

    def _theta_html(self, recs):
        """θ = the other/w_o share per unit (latest passing action). In this
        security regime low θ is healthy; high θ trends Codependent."""
        latest = {}
        for r in recs:
            if r.get("allowed"):
                latest[r["unit"]] = r["w"][1]
        if not latest:
            return f"<span style='color:{C_MUTED}'>θ per unit — no passing actions yet</span>"
        parts = []
        for u in ("recon", "password", "sniff", "access"):
            if u in latest:
                t = latest[u] * 100
                col = "#34d399" if t < 15 else ("#fbbf24" if t < 30 else "#fb7185")
                parts.append(f"<b style='color:{UNIT_COLORS[u]}'>{u}</b> "
                             f"<span style='color:{col}'>θ={t:.0f}%</span>")
        return (f"<span style='color:{C_MUTED}'>θ (other share):</span> "
                + " &nbsp;·&nbsp; ".join(parts))

    def _fit_window(self):
        scr = QApplication.primaryScreen().availableGeometry()
        # Wide enough for all three columns (left attack/defend · centre simplex ·
        # right 520px) to show at once without a manual drag; still clamped to the screen.
        w = min(1720, int(scr.width() * 0.96))
        h = min(860, int(scr.height() * 0.92))
        self.setMinimumSize(min(820, w), min(520, h))
        self.resize(w, h)
        self.move(scr.x() + (scr.width() - w) // 2, scr.y() + (scr.height() - h) // 2)

    # ---- layout ------------------------------------------------------------
    def _build(self):
        self.simplex = Simplex()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["unit", "tool", "target", "w", "verdict"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMaximumHeight(260)
        centre = QVBoxLayout(); centre.addWidget(self.simplex, 1); centre.addWidget(self.table)
        self.theta_lbl = QLabel("θ per unit — waiting…")
        self.theta_lbl.setTextFormat(Qt.RichText)
        centre.addWidget(self.theta_lbl)
        foot = QLabel("Attractors — Narcissistic (w_s) · Codependent (w_o) · "
                      "Schizoid (w_f) · Borderline (no corner: variance across turns).   "
                      "ε=0.28 membrane;  auth<0.35 = floor (unreachable).")
        foot.setWordWrap(True); foot.setStyleSheet(f"color:{C_MUTED};")
        centre.addWidget(foot)
        cw = QWidget(); cw.setLayout(centre)

        # --- font size controls ---
        aminus = QPushButton("A−"); aminus.setObjectName("tiny")
        aminus.clicked.connect(lambda: self._bump_font(-2))
        aplus = QPushButton("A+"); aplus.setObjectName("tiny")
        aplus.clicked.connect(lambda: self._bump_font(2))
        flbl = QLabel("text size"); flbl.setStyleSheet(f"color:{C_MUTED};")
        fontrow = QHBoxLayout(); fontrow.addWidget(flbl); fontrow.addStretch(1)
        fontrow.addWidget(aminus); fontrow.addWidget(aplus)

        # --- model row ---
        self.model_combo = QComboBox()
        self.switch_btn = QPushButton("Switch")
        self.switch_btn.clicked.connect(self._switch_model)
        self.model_status = QLabel("")
        self.model_status.setStyleSheet(f"color:{C_MUTED};")
        mrow = QHBoxLayout(); mrow.addWidget(self.model_combo, 1); mrow.addWidget(self.switch_btn)

        # --- command panel ---
        self.cmd_log = QTextEdit(); self.cmd_log.setReadOnly(True); self.cmd_log.setMinimumHeight(200)
        self.cmd_in = QLineEdit(); self.cmd_in.setPlaceholderText(
            "command the swarm…  e.g. 'focus recon on .5, turn off the sniffer'")
        self.cmd_in.returnPressed.connect(self._send_cmd)
        send = QPushButton("Send"); send.setObjectName("primary"); send.clicked.connect(self._send_cmd)
        crow = QHBoxLayout(); crow.addWidget(self.cmd_in, 1); crow.addWidget(send)
        prow = QHBoxLayout()
        for lbl, key in (("Full", "full"), ("Recon", "recon"),
                         ("Passive", "passive"), ("Stop all", "stop")):
            pb = QPushButton(lbl); pb.setObjectName("tiny")
            pb.clicked.connect(lambda _=False, k=key: self._preset(k))
            prow.addWidget(pb)

        # --- approvals ---
        self.appro = QVBoxLayout(); self.appro.setSpacing(6)
        self.appro_empty = QLabel("— no pending holds —")
        self.appro_empty.setStyleSheet(f"color:{C_MUTED};")
        self.appro.addWidget(self.appro_empty)

        # --- authorized scope (deliberate, logged widening) ---
        self.scope_lbl = QLabel("—"); self.scope_lbl.setWordWrap(True)
        self.scope_lbl.setStyleSheet(f"color:{C_MUTED};font-family:'ui-monospace',monospace;")
        self.scope_in = QLineEdit()
        self.scope_in.setPlaceholderText("add target e.g. 10.10.10.9/32  (deliberate, logged)")
        authb = QPushButton("Authorize"); authb.clicked.connect(self._authorize_scope)
        srow = QHBoxLayout(); srow.addWidget(self.scope_in, 1); srow.addWidget(authb)

        right = QVBoxLayout(); right.setSpacing(9)
        right.addLayout(fontrow)
        right.addWidget(_h3("LOCAL MODEL")); right.addLayout(mrow); right.addWidget(self.model_status)
        right.addWidget(_hline())
        right.addWidget(_h3("COMMAND — talk to the commander")); right.addWidget(self.cmd_log)
        right.addLayout(crow)
        right.addLayout(prow)
        right.addWidget(_hline())
        right.addWidget(_h3("AUTHORIZED SCOPE")); right.addWidget(self.scope_lbl); right.addLayout(srow)
        right.addWidget(_hline())
        right.addWidget(_h3("APPROVALS (judgment holds)")); right.addLayout(self.appro)
        right.addStretch(1)
        rw = QWidget(); rw.setLayout(right); rw.setFixedWidth(520)

        lw = self._build_left_column()

        root = QHBoxLayout(); root.addWidget(lw); root.addWidget(cw, 1); root.addWidget(rw)
        host = QWidget(); host.setLayout(root)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame); scroll.setWidget(host)
        self.setCentralWidget(scroll)
        self._load_models()
        if not self.engine:
            for w in (self.model_combo, self.switch_btn, self.cmd_in, self.scope_in):
                w.setEnabled(False)
            self.model_status.setText("view-only (no engine)")
        elif self.engine:
            self.scope_lbl.setText(", ".join(self.engine.context.scope))

    # ---- left column: attack / defend per unit -----------------------------
    def _build_left_column(self):
        col = QVBoxLayout(); col.setSpacing(8)
        col.addWidget(_h3("ATTACK / DEFEND"))
        for unit in ("recon", "password", "sniff", "access"):
            dot = QLabel(f"<span style='color:{UNIT_COLORS[unit]}'>●</span> {unit}")
            dot.setTextFormat(Qt.RichText)
            col.addWidget(dot)
            atk = QPushButton("Attack ▾"); atk.setObjectName("tiny")
            dfn = QPushButton("Defend ▾"); dfn.setObjectName("tiny")
            atk.clicked.connect(lambda _=False, u=unit, b=atk: self._show_actions(u, "attack", b))
            dfn.clicked.connect(lambda _=False, u=unit, b=dfn: self._show_actions(u, "defend", b))
            row = QHBoxLayout(); row.setSpacing(6)
            row.addWidget(atk); row.addWidget(dfn)
            col.addLayout(row)
        col.addStretch(1)
        hint = QLabel("Every run opens a terminal and asks for your Ubuntu "
                      "password before anything executes.")
        hint.setWordWrap(True); hint.setStyleSheet(f"color:{C_MUTED};")
        col.addWidget(hint)
        self._left_col = QWidget(); self._left_col.setLayout(col)
        self._left_col.setFixedWidth(210)
        return self._left_col

    def _show_actions(self, unit, kind, btn):
        """Pop a list of concrete commands at the left↔centre boundary."""
        menu = QMenu(self)
        for label, cmd, as_root in UNIT_ACTIONS[unit][kind]:
            act = QAction(label, menu)
            act.triggered.connect(lambda _=False, c=cmd, r=as_root: self._launch_terminal(c, r))
            menu.addAction(act)
        # anchor: right edge of the left column, at the button's height
        x = self._left_col.mapToGlobal(self._left_col.rect().topRight()).x()
        y = btn.mapToGlobal(QPoint(0, btn.height())).y()
        menu.exec(QPoint(x, y))

    def _launch_terminal(self, cmd, as_root):
        """Open a terminal that shows the command and runs it only after the
        operator presses ENTER and types their password. The console itself
        runs nothing."""
        cmd = cmd.replace("<LAB>", LAB).replace("<PEER>", PEER)
        env = dict(os.environ)
        env["PSE_CMD"] = cmd
        env["PSE_ASROOT"] = "1" if as_root else "0"
        env["PSE_REPO"] = REPO
        env["PSE_USER"] = os.environ.get("USER", "")
        term = next((t for t in ("gnome-terminal", "x-terminal-emulator",
                                 "konsole", "xfce4-terminal", "xterm")
                     if shutil.which(t)), None)
        if not term:
            self._toast("No terminal emulator found (try: sudo apt install xterm).")
            return
        if term == "gnome-terminal":
            argv = [term, "--", "bash", APPROVE_SH]
        elif term == "xfce4-terminal":
            argv = [term, "-e", f"bash {APPROVE_SH}"]
        else:
            argv = [term, "-e", "bash", APPROVE_SH]
        try:
            subprocess.Popen(argv, env=env)
            self._toast(f"opened a terminal — approve to run: {cmd[:70]}…")
        except Exception as e:      # noqa
            self._toast(f"could not open terminal: {e}")

    def _toast(self, msg):
        if hasattr(self, "cmd_log") and self.cmd_log is not None:
            self.cmd_log.append(f"· {msg}")
        else:
            print(msg)

    def _load_models(self):
        from pse_kernel import list_local_models
        self.model_combo.clear()
        for m in list_local_models(MODELS_DIR):
            label = f"{m['name']}  ({m['size_gb']} GB){'' if m['fits'] else '  — too big'}"
            self.model_combo.addItem(label, userData=m)
        if self.model_combo.count() == 0:
            self.model_combo.addItem("(no .gguf in ./models)", userData=None)

    # ---- actions -----------------------------------------------------------
    def _send_cmd(self):
        if not self.engine:
            return
        text = self.cmd_in.text().strip()
        if text:
            self.control.say(f"you: {text}")
            self.control.command(text)
            self.cmd_in.clear()

    def _preset(self, name):
        if self.engine:
            self.engine.apply_preset(name)

    def _authorize_scope(self):
        if not self.engine:
            return
        t = self.scope_in.text().strip()
        if t:
            self.engine.authorize_scope(t)
            self.scope_in.clear()
            self.scope_lbl.setText(", ".join(self.engine.context.scope))

    def _switch_model(self):
        if not self.engine:
            return
        m = self.model_combo.currentData()
        if not m:
            return
        self.switch_btn.setEnabled(False)
        self.model_status.setText(f"switching to {m['name']} …")

        def work():
            self.engine.switch_model(m["path"], fits=m["fits"])
        threading.Thread(target=work, daemon=True).start()

    def _approve(self, esc, decision):
        esc.resolve(decision)
        row = self._escrows.pop(esc.id, None)
        if row:
            row.setParent(None)
        if not self._escrows:
            self.appro.addWidget(self.appro_empty); self.appro_empty.show()

    def _add_escalation(self, esc):
        self.appro_empty.hide()
        row = QWidget(); h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0)
        lab = QLabel(f"#{esc.id} {esc.unit} · {esc.kind}\n{esc.action.get('tool')} "
                     f"{esc.action.get('target')}")
        lab.setStyleSheet("font-family:'ui-monospace',monospace;")
        ok = QPushButton("Approve"); ok.setObjectName("primary")
        no = QPushButton("Deny")
        ok.clicked.connect(lambda: self._approve(esc, "approve"))
        no.clicked.connect(lambda: self._approve(esc, "deny"))
        h.addWidget(lab, 1); h.addWidget(ok); h.addWidget(no)
        self.appro.addWidget(row)
        self._escrows[esc.id] = row

    # ---- polling -----------------------------------------------------------
    def _poll(self):
        # simplex + table from the audit log
        try:
            mt = os.path.getmtime(AUDIT)
        except OSError:
            mt = None
        if mt is not None and mt != self._mtime:
            self._mtime = mt
            recs = records_from_audit(open(AUDIT).readlines())
            self.simplex.set_records(recs)
            self.table.setRowCount(len(recs))
            for i, r in enumerate(recs):
                w = ",".join(f"{v:.2f}" for v in r["w"])
                verdict = "pass" if r["allowed"] else f"HELD/{r.get('kind')}"
                for j, val in enumerate([r["unit"], r["tool"], r["target"], w, verdict]):
                    it = QTableWidgetItem(str(val))
                    if j == 0:
                        it.setForeground(QColor(UNIT_COLORS.get(r["unit"], C_INK)))
                    if j == 4:
                        it.setForeground(QColor(C_ACCENT if r["allowed"]
                                         else (C_FLOOR if r.get("floor") else C_BLOCK)))
                    self.table.setItem(i, j, it)
            self.table.scrollToBottom()
            self.theta_lbl.setText(self._theta_html(recs))

        if not self.control:
            return
        # drain the commander/system log
        while not self.control.log.empty():
            self.cmd_log.append(self.control.log.get())
        # drain new escalations into approval rows
        while not self.control.escalations.empty():
            self._add_escalation(self.control.escalations.get())
        # reflect the active model
        if self.proxy:
            busy = self.control.paused.is_set()
            self.model_status.setText(f"active: {self.proxy.name}"
                                      + ("  · swapping…" if busy else ""))
            self.switch_btn.setEnabled(not busy)

    def closeEvent(self, e):
        if self.engine:
            self.engine.stop()
        e.accept()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None,
                    help="gguf:models/..gguf | claude:.. | mistral:.. | mock (default: config/mock)")
    ap.add_argument("--execute", action="store_true", help="run REAL tools against the lab")
    ap.add_argument("--view-only", action="store_true", help="just watch the audit log")
    args = ap.parse_args()

    if args.view_only:
        engine = control = proxy = None
    else:
        engine, control, proxy = build_engine(args.backend, args.execute)

    app = QApplication(sys.argv)
    win = Console(engine, control, proxy); win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

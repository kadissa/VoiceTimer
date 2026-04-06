"""
Minimalist voice timer — tkinter + pyttsx3
Supports count-up and countdown modes.
Speaks every second in English.

Requirements:
    pip install pyttsx3
    sudo apt install espeak-ng  # Linux
"""

import threading
import time
import tkinter as tk

import pyttsx3


class VoiceTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("Voice Timer")
        self.root.resizable(False, False)
        self.root.configure(bg="#0f0f0f")

        self._running = False
        self._elapsed = 0  # seconds, used in count-up
        self._countdown_total = 0  # seconds for countdown
        self._mode = tk.StringVar(value="up")

        # pyttsx3 engine — runs in its own thread
        self._engine = pyttsx3.init()
        self._engine.setProperty("rate", 180)
        self._speak_queue = []
        self._speak_lock = threading.Lock()
        self._speak_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self._speak_thread.start()

        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        PAD = 24
        BG = "#0f0f0f"
        FG = "#f0f0f0"
        ACC = "#00e5ff"
        BTN_BG = "#1e1e1e"

        # Mode selector
        mode_frame = tk.Frame(self.root, bg=BG)
        mode_frame.pack(pady=(PAD, 4))

        for text, val in (("Count Up ↑", "up"), ("Countdown ↓", "down")):
            rb = tk.Radiobutton(
                mode_frame, text=text, variable=self._mode, value=val,
                command=self._on_mode_change,
                bg=BG, fg=FG, selectcolor="#1a1a1a",
                activebackground=BG, activeforeground=ACC,
                font=("Courier New", 11), bd=0, cursor="hand2",
            )
            rb.pack(side=tk.LEFT, padx=12)

        # Countdown input (visible only in countdown mode)
        self._input_frame = tk.Frame(self.root, bg=BG)
        self._input_frame.pack(pady=(0, 8))

        tk.Label(
            self._input_frame, text="seconds:", bg=BG, fg="#888",
            font=("Courier New", 11),
        ).pack(side=tk.LEFT, padx=(0, 6))

        self._seconds_var = tk.StringVar(value="10")
        self._entry = tk.Entry(
            self._input_frame, textvariable=self._seconds_var,
            width=6, bg=BTN_BG, fg=FG, insertbackground=FG,
            font=("Courier New", 13), bd=0, justify="center",
            highlightthickness=1, highlightcolor=ACC, highlightbackground="#333",
        )
        self._entry.pack(side=tk.LEFT)
        self._input_frame.pack_forget()  # hidden initially

        # Big display
        self._display_var = tk.StringVar(value="00:00")
        tk.Label(
            self.root, textvariable=self._display_var,
            bg=BG, fg=ACC, font=("Courier New", 64, "bold"),
        ).pack(padx=PAD * 2)

        # Status label
        self._status_var = tk.StringVar(value="ready")
        tk.Label(
            self.root, textvariable=self._status_var,
            bg=BG, fg="#555", font=("Courier New", 10),
        ).pack(pady=(0, 10))

        # Buttons
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=(0, PAD))

        self._start_btn = self._make_btn(btn_frame, "START", self._start, ACC)
        self._start_btn.pack(side=tk.LEFT, padx=6)

        self._make_btn(btn_frame, "RESET", self._reset, "#ff4081").pack(side=tk.LEFT, padx=6)

    def _make_btn(self, parent, text, cmd, color):
        btn = tk.Button(
            parent, text=text, command=cmd,
            bg="#1e1e1e", fg=color, activebackground="#2a2a2a", activeforeground=color,
            font=("Courier New", 12, "bold"), bd=0, padx=18, pady=8,
            cursor="hand2", relief=tk.FLAT,
            highlightthickness=1, highlightbackground=color,
        )
        return btn

    def _on_mode_change(self):
        if self._running:
            return
        if self._mode.get() == "down":
            self._input_frame.pack(pady=(0, 8))
        else:
            self._input_frame.pack_forget()
        self._reset()

    # ── Timer logic ───────────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            # Pause
            self._running = False
            self._start_btn.config(text="RESUME")
            self._status_var.set("paused")
            return

        if self._mode.get() == "down" and self._elapsed == 0:
            try:
                total = int(self._seconds_var.get())
                if total <= 0:
                    raise ValueError
            except ValueError:
                self._status_var.set("enter a positive integer")
                return
            self._countdown_total = total

        self._running = True
        self._start_btn.config(text="PAUSE")
        self._status_var.set("running")
        threading.Thread(target=self._tick_loop, daemon=True).start()

    def _reset(self):
        self._running = False
        self._elapsed = 0
        self._countdown_total = 0
        self._display_var.set("00:00")
        self._start_btn.config(text="START")
        self._status_var.set("ready")

    def _tick_loop(self):
        import time
        while self._running:
            time.sleep(1)
            if not self._running:
                break

            self._elapsed += 1

            if self._mode.get() == "up":
                seconds = self._elapsed
                display = self._fmt(seconds)
                self._enqueue_speak(str(seconds))
            else:
                remaining = self._countdown_total - self._elapsed
                display = self._fmt(max(remaining, 0))
                if remaining > 0:
                    self._enqueue_speak(str(remaining))
                else:
                    self._running = False
                    self.root.after(0, self._on_countdown_done)

            self._display_var.set(display)

    def _on_countdown_done(self):
        self._display_var.set("00:00")
        self._status_var.set("done ✓")
        self._start_btn.config(text="START")
        self._enqueue_speak("Time is up!")

    @staticmethod
    def _fmt(seconds):
        m, s = divmod(abs(seconds), 60)
        return f"{m:02d}:{s:02d}"

    # ── Speech ────────────────────────────────────────────────────────────────

    def _enqueue_speak(self, text):
        with self._speak_lock:
            self._speak_queue.clear()  # ← добавить эту строку
            self._speak_queue.append(text)

    def _speak_worker(self):
        """Dedicated thread — pyttsx3 is not thread-safe, run it here only."""
        while True:
            text = None
            with self._speak_lock:
                if self._speak_queue:
                    text = self._speak_queue.pop(0)
            if text:
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception:
                    pass
            else:
                time.sleep(0.05)


def main():
    root = tk.Tk()
    VoiceTimer(root)
    root.mainloop()


if __name__ == "__main__":
    main()

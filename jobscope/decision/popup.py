from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

DECISIONS = ("apply", "skip", "bookmark", "quit")


def ask_yes_no(*, title: str, message: str,
               yes_text: str = "Yes", no_text: str = "No") -> bool:
    result: dict[str, bool] = {"value": False}

    root = tk.Tk()
    root.title(title)
    root.geometry("460x200")
    root.attributes("-topmost", True)

    body = ttk.Label(root, text=message, wraplength=420, justify="left",
                     font=("Segoe UI", 10))
    body.pack(padx=20, pady=20, anchor="w")

    btns = ttk.Frame(root)
    btns.pack(pady=10)

    def pick(val: bool):
        result["value"] = val
        root.destroy()

    yes_btn = ttk.Button(btns, text=yes_text, command=lambda: pick(True))
    yes_btn.grid(row=0, column=0, padx=8)
    no_btn = ttk.Button(btns, text=no_text, command=lambda: pick(False))
    no_btn.grid(row=0, column=1, padx=8)
    root.bind("<Return>", lambda e: pick(True))
    root.bind("<Escape>", lambda e: pick(False))
    yes_btn.focus_set()

    root.mainloop()
    return result["value"]


def ask_acknowledge(*, title: str, message: str,
                    button_text: str = "Continue") -> None:
    root = tk.Tk()
    root.title(title)
    root.geometry("460x200")
    root.attributes("-topmost", True)

    body = ttk.Label(root, text=message, wraplength=420, justify="left",
                     font=("Segoe UI", 10))
    body.pack(padx=20, pady=20, anchor="w")

    def close():
        root.destroy()

    btn = ttk.Button(root, text=button_text, command=close)
    btn.pack(pady=12)
    root.bind("<Return>", lambda e: close())
    root.bind("<Escape>", lambda e: close())
    btn.focus_set()

    root.mainloop()

def ask_decision(*, title: str, company: str, fit_score: int,
                 recommendation: str) -> Optional[str]:
    result: dict[str, Optional[str]] = {"value": None}

    root = tk.Tk()
    root.title("JobScope — decide")
    root.geometry("520x340")
    root.attributes("-topmost", True)

    pad = {"padx": 16, "pady": 8}

    header = ttk.Label(root, text=f"{title}\n@ {company}",
                       font=("Segoe UI", 12, "bold"), justify="left")
    header.pack(anchor="w", **pad)

    fit_color = "#2ecc71" if fit_score >= 60 else ("#f1c40f" if fit_score >= 40 else "#e74c3c")
    fit = ttk.Label(root, text=f"Fit: {fit_score} / 100", font=("Segoe UI", 14, "bold"))
    fit.pack(anchor="w", padx=16)
    fit.configure(foreground=fit_color)

    rec = tk.Text(root, height=6, wrap="word", font=("Segoe UI", 10))
    rec.insert("1.0", recommendation or "")
    rec.configure(state="disabled")
    rec.pack(fill="both", expand=False, padx=16, pady=8)

    def choose(value: str):
        result["value"] = value
        root.destroy()

    btns = ttk.Frame(root)
    btns.pack(pady=10)
    ttk.Button(btns, text="Apply",     command=lambda: choose("apply")).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Skip",      command=lambda: choose("skip")).grid(row=0, column=1, padx=6)
    ttk.Button(btns, text="Bookmark",  command=lambda: choose("bookmark")).grid(row=0, column=2, padx=6)
    ttk.Button(btns, text="Quit",      command=lambda: choose("quit")).grid(row=0, column=3, padx=6)

    root.bind("<a>", lambda e: choose("apply"))
    root.bind("<s>", lambda e: choose("skip"))
    root.bind("<b>", lambda e: choose("bookmark"))
    root.bind("<q>", lambda e: choose("quit"))
    root.bind("<Escape>", lambda e: choose("skip"))

    root.mainloop()
    return result["value"]

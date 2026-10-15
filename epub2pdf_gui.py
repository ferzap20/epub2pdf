"""Small Tk window for epub2pdf.py. Defaults match the command-line defaults."""
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import epub2pdf

PAGES = ["A5", "A4", "Letter", "6in 9in"]
FONTS = {
    "Serif (Georgia)": "Georgia, 'Times New Roman', serif",
    "Sans (Arial)": "Arial, Helvetica, sans-serif",
    "Sans (Calibri)": "Calibri, Arial, sans-serif",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EPUB to PDF")
        self.resizable(False, False)
        d = epub2pdf.make_parser().parse_args(["x"])  # defaults from the CLI

        self.epub = tk.StringVar()
        self.pdf = tk.StringVar()
        self.page = tk.StringVar(value=d.page)
        self.margin = tk.StringVar(value=d.margin)
        self.font_size = tk.StringVar(value=d.font_size)
        self.font = tk.StringVar(value=next(k for k, v in FONTS.items() if v == d.font))
        self.justify = tk.BooleanVar(value=d.align == "justify")
        self.keep_css = tk.BooleanVar(value=d.keep_css)
        self.no_images = tk.BooleanVar(value=d.no_images)
        self.status = tk.StringVar(value="Pick an EPUB file.")

        f = ttk.Frame(self, padding=12)
        f.grid()
        ttk.Label(f, text="EPUB:").grid(row=0, column=0, sticky="w")
        ttk.Entry(f, textvariable=self.epub, width=50).grid(row=0, column=1, padx=4)
        ttk.Button(f, text="Browse...", command=self.pick_epub).grid(row=0, column=2)
        ttk.Label(f, text="PDF:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=self.pdf, width=50).grid(row=1, column=1, padx=4)
        ttk.Button(f, text="Save as...", command=self.pick_pdf).grid(row=1, column=2)

        o = ttk.LabelFrame(f, text="Options", padding=8)
        o.grid(row=2, column=0, columnspan=3, sticky="ew", pady=8)
        ttk.Label(o, text="Page size").grid(row=0, column=0, sticky="w")
        ttk.Combobox(o, textvariable=self.page, values=PAGES, width=10).grid(row=0, column=1, padx=6)
        ttk.Label(o, text="Margin").grid(row=0, column=2, sticky="w")
        ttk.Entry(o, textvariable=self.margin, width=8).grid(row=0, column=3, padx=6)
        ttk.Label(o, text="Font size (pt)").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(o, textvariable=self.font_size, width=8).grid(row=1, column=1, padx=6, sticky="w")
        ttk.Label(o, text="Font").grid(row=1, column=2, sticky="w")
        ttk.Combobox(o, textvariable=self.font, values=list(FONTS), width=16, state="readonly").grid(row=1, column=3, padx=6)
        ttk.Checkbutton(o, text="Justify text", variable=self.justify).grid(row=2, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(o, text="Use the book's own styling", variable=self.keep_css).grid(row=2, column=2, columnspan=2, sticky="w")
        ttk.Checkbutton(o, text="Remove images (smaller file)", variable=self.no_images).grid(row=3, column=0, columnspan=2, sticky="w")

        self.btn = ttk.Button(f, text="Convert", command=self.start)
        self.btn.grid(row=3, column=0, columnspan=3, pady=4)
        self.bar = ttk.Progressbar(f, mode="indeterminate", length=300)
        ttk.Label(f, textvariable=self.status).grid(row=5, column=0, columnspan=3)
        self.bar.grid(row=4, column=0, columnspan=3, pady=4)

    def pick_epub(self):
        p = filedialog.askopenfilename(filetypes=[("EPUB books", "*.epub")])
        if p:
            self.epub.set(p)
            self.pdf.set(str(Path(p).with_suffix(".pdf")))

    def pick_pdf(self):
        p = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF", "*.pdf")])
        if p:
            self.pdf.set(p)

    def start(self):
        if not self.epub.get():
            messagebox.showwarning("EPUB to PDF", "Pick an EPUB file first.")
            return
        args = epub2pdf.make_parser().parse_args([self.epub.get()])
        args.pdf = self.pdf.get() or None
        args.page = self.page.get()
        args.margin = self.margin.get()
        args.font_size = self.font_size.get()
        args.font = FONTS[self.font.get()]
        args.align = "justify" if self.justify.get() else "left"
        args.keep_css = self.keep_css.get()
        args.no_images = self.no_images.get()
        self.btn.state(["disabled"])
        self.bar.start(12)
        self.status.set("Converting... this can take a minute.")
        threading.Thread(target=self.work, args=(args,), daemon=True).start()

    def work(self, args):
        try:
            _, n, out = epub2pdf.convert(args)
            self.after(0, self.done, f"Done: {out}", None)
        except Exception as e:  # shown to the user in a dialog
            self.after(0, self.done, "Failed.", str(e))

    def done(self, msg, error):
        self.bar.stop()
        self.btn.state(["!disabled"])
        self.status.set(msg)
        if error:
            messagebox.showerror("EPUB to PDF", error)


if __name__ == "__main__":
    App().mainloop()

"""
wz_icon_viewer_gui.py

MapleStory WZ Icon Viewer

- Dark theme Tkinter GUI
- Works with nested Item JSON from the PNG flattener
- Uses only tkinter + stdlib (PyInstaller-friendly, no Pillow)
"""

import json
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


# ---------------------------------------------------------------------------
#  Dark Theme Constants (match flattener)
# ---------------------------------------------------------------------------

BG_MAIN = "#202124"      # main background
FG_TEXT = "#D1D1D1"      # primary text
BG_INPUT = "#303134"     # entries / combos / buttons background
BG_LIST = "#1F1F22"      # listbox background
BG_BUTTON = "#3C4043"
FG_BUTTON = "#D1D1D1"
BG_HIGHLIGHT = "#5F6368"
BG_PREVIEW = "#202124"


# ---------------------------------------------------------------------------
#  Core logic helpers (JSON + data access)
# ---------------------------------------------------------------------------

def load_icon_db(path):
    """Load icon_db.json from disk and return the parsed dict."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("icon_db.json must contain a top-level JSON object")

    return data


def get_types(icon_db):
    """Return a sorted list of all top-level types."""
    if not isinstance(icon_db, dict):
        return []
    return sorted(str(k) for k in icon_db.keys())


def _is_nested_item(icon_db, type_name):
    """
    Return True if this type appears to use nested categories:
    e.g. Item -> { 'Cash': {id: path}, 'Consume': {...}, ... }
    """
    if type_name not in icon_db:
        return False
    data = icon_db[type_name]
    if not isinstance(data, dict):
        return False
    # If any value is a dict, we treat it as nested
    return any(isinstance(v, dict) for v in data.values())


def get_categories(icon_db, type_name):
    """
    For nested types (Item), return sorted category names.
    For flat types, return [].
    """
    if not _is_nested_item(icon_db, type_name):
        return []
    data = icon_db.get(type_name, {})
    return sorted(str(k) for k in data.keys())


def get_ids(icon_db, type_name, category=None):
    """
    Return mapping {id: relative_path} for a given type/category.

    - For Item with nested categories:
        Item -> category -> {id: path}
    - For flat types:
        type -> {id: path}
    """
    if type_name not in icon_db:
        return {}

    data = icon_db[type_name]

    # Nested Item
    if type_name == "Item" and _is_nested_item(icon_db, "Item"):
        if not category:
            return {}
        sub = data.get(category)
        if isinstance(sub, dict):
            return {str(k): v for k, v in sub.items()}
        return {}

    # Flat type
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items()}

    return {}


# ---------------------------------------------------------------------------
#  GUI Application
# ---------------------------------------------------------------------------

class IconViewerApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("MapleStory WZ Icon Viewer")
        self.geometry("1000x650")
        self.minsize(880, 560)

        # Data
        self.icon_db = {}
        self.png_root = None
        self.current_entries = {}     # id -> rel_path
        self.current_image = None     # keep PhotoImage alive

        # Tk variables
        self.var_json_path = tk.StringVar(value="No icon_db.json loaded")
        self.var_png_root = tk.StringVar(value="No PNG root folder selected")
        self.var_type = tk.StringVar()
        self.var_category = tk.StringVar()
        self.var_filter = tk.StringVar()
        self.var_info = tk.StringVar(value="")
        self.var_status = tk.StringVar(value="Ready")

        self._setup_style()
        self._build_ui()

    # ------------------------------------------------------------------
    #  Styling
    # ------------------------------------------------------------------

    def _setup_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            ".",
            background=BG_MAIN,
            foreground=FG_TEXT,
            fieldbackground=BG_INPUT,
            troughcolor=BG_INPUT,
            bordercolor=BG_HIGHLIGHT,
            lightcolor=BG_MAIN,
            darkcolor=BG_MAIN,
        )

        style.configure("TFrame", background=BG_MAIN)
        style.configure("TLabel", background=BG_MAIN, foreground=FG_TEXT)

        style.configure(
            "TButton",
            background=BG_BUTTON,
            foreground=FG_BUTTON,
            padding=4,
            borderwidth=1,
        )
        style.map(
            "TButton",
            background=[("active", BG_HIGHLIGHT)],
            foreground=[("active", FG_BUTTON)],
        )

        style.configure(
            "TEntry",
            fieldbackground=BG_INPUT,
            foreground=FG_TEXT,
            insertcolor=FG_TEXT,
            padding=3,
        )

        # Combobox: force dark text + dark field even in readonly mode
        style.configure(
            "TCombobox",
            foreground=FG_TEXT,
            background=BG_INPUT,
            fieldbackground=BG_INPUT,
            arrowcolor=FG_TEXT,
        )
        style.map(
            "TCombobox",
            foreground=[("readonly", FG_TEXT)],
            fieldbackground=[("readonly", BG_INPUT)],
            background=[("readonly", BG_INPUT)],
        )

        style.configure(
            "Vertical.TScrollbar",
            background=BG_INPUT,
            troughcolor=BG_MAIN,
            bordercolor=BG_MAIN,
        )

        # Classic widget defaults
        self.option_add("*Listbox.background", BG_LIST)
        self.option_add("*Listbox.foreground", FG_TEXT)
        self.option_add("*Listbox.selectBackground", BG_HIGHLIGHT)
        self.option_add("*Listbox.selectForeground", FG_TEXT)
        self.option_add("*Listbox.font", "TkDefaultFont")

        self.configure(bg=BG_MAIN)

    # ------------------------------------------------------------------
    #  UI Layout
    # ------------------------------------------------------------------

    def _build_ui(self):
        pad = 6

        root_frame = ttk.Frame(self, padding=pad)
        root_frame.pack(fill="both", expand=True)

        # Left panel ----------------------------------------------------
        left = ttk.Frame(root_frame)
        left.pack(side="left", fill="y", padx=(0, pad))

        # JSON & PNG selectors
        file_frame = ttk.Frame(left)
        file_frame.pack(fill="x", pady=(0, pad))

        ttk.Button(
            file_frame,
            text="Load icon_db.json",
            command=self._on_select_json,
            width=18,
        ).pack(side="top", anchor="w", pady=(0, 2))

        ttk.Label(file_frame, textvariable=self.var_json_path, wraplength=260).pack(
            side="top", anchor="w", pady=(0, 4)
        )

        ttk.Button(
            file_frame,
            text="Select PNG root",
            command=self._on_select_png_root,
            width=18,
        ).pack(side="top", anchor="w", pady=(4, 2))

        ttk.Label(file_frame, textvariable=self.var_png_root, wraplength=260).pack(
            side="top", anchor="w", pady=(0, 4)
        )

        # Type / Category / Filter
        controls = ttk.Frame(left)
        controls.pack(fill="x", pady=(pad, pad))

        # Type
        ttk.Label(controls, text="Type:").grid(row=0, column=0, sticky="w")
        self.combo_type = ttk.Combobox(
            controls,
            textvariable=self.var_type,
            state="readonly",
            width=18,
        )
        self.combo_type.grid(row=0, column=1, sticky="we", padx=(4, 0))
        self.combo_type.bind("<<ComboboxSelected>>", self._on_type_changed)

        # Category (Item only) - group label + combo in a frame for easy hide/show
        self.category_frame = ttk.Frame(controls)
        self.category_frame.grid(row=1, column=0, columnspan=2, sticky="we", pady=(4, 0))

        ttk.Label(self.category_frame, text="Category:").grid(row=0, column=0, sticky="w")
        self.combo_category = ttk.Combobox(
            self.category_frame,
            textvariable=self.var_category,
            state="readonly",
            width=18,
        )
        self.combo_category.grid(row=0, column=1, sticky="we", padx=(4, 0))
        self.combo_category.bind("<<ComboboxSelected>>", self._on_category_changed)

        # start hidden
        self.category_frame.grid_remove()

        # Filter
        ttk.Label(controls, text="Search ID:").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )
        self.entry_filter = ttk.Entry(
            controls, textvariable=self.var_filter, width=18
        )
        self.entry_filter.grid(row=2, column=1, sticky="we", padx=(4, 0), pady=(6, 0))
        # Live filtering as you type
        self.entry_filter.bind("<KeyRelease>", lambda _e: self.refresh_id_list())

        # ID list
        list_frame = ttk.Frame(left)
        list_frame.pack(fill="both", expand=True, pady=(pad, 0))

        ttk.Label(list_frame, text="IDs").pack(anchor="w")

        listbox_frame = ttk.Frame(list_frame)
        listbox_frame.pack(fill="both", expand=True, pady=(2, 0))

        self.list_ids = tk.Listbox(
            listbox_frame, width=24, exportselection=False, activestyle="none"
        )
        self.list_ids.pack(side="left", fill="both", expand=True)
        self.list_ids.bind("<<ListboxSelect>>", self._on_id_selected)

        scroll = ttk.Scrollbar(
            listbox_frame, orient="vertical", command=self.list_ids.yview
        )
        scroll.pack(side="right", fill="y")
        self.list_ids.configure(yscrollcommand=scroll.set)

        # Right panel ---------------------------------------------------
        right = ttk.Frame(root_frame)
        right.pack(side="left", fill="both", expand=True)

        self.lbl_preview_title = ttk.Label(
            right, text="No image loaded", anchor="center"
        )
        self.lbl_preview_title.pack(fill="x", pady=(0, 4))

        self.preview_label = tk.Label(
            right,
            bg=BG_PREVIEW,
            bd=1,
            relief="solid",
            anchor="center",
        )
        self.preview_label.pack(fill="both", expand=True)

        info_frame = ttk.Frame(right)
        info_frame.pack(fill="x", pady=(4, 0))
        ttk.Label(info_frame, textvariable=self.var_info, justify="left").pack(
            anchor="w"
        )

        # ---- Copy ID Button ----
        copy_frame = ttk.Frame(right)
        copy_frame.pack(fill="x", pady=(6, 0))

        ttk.Button(
            copy_frame,
            text="Copy ID",
            command=self._copy_selected_id,
        ).pack(side="left", padx=4)

        # Bottom status -------------------------------------------------
        status_frame = ttk.Frame(self, padding=(pad, 0, pad, pad))
        status_frame.pack(side="bottom", fill="x")
        ttk.Label(
            status_frame, textvariable=self.var_status, anchor="w"
        ).pack(side="left", fill="x")

    # ------------------------------------------------------------------
    #  File selection handlers
    # ------------------------------------------------------------------

    def _on_select_json(self):
        path = filedialog.askopenfilename(
            title="Open icon_db.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        self._load_json(path)

    def _load_json(self, path):
        try:
            db = load_icon_db(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Error", f"Failed to load icon_db.json:\n{exc}")
            self.var_status.set("Error loading icon_db.json")
            return

        self.icon_db = db
        self.var_json_path.set(os.path.abspath(path))
        self.var_status.set("icon_db.json loaded")

        types = get_types(self.icon_db)
        self.combo_type["values"] = types
        if types:
            self.var_type.set(types[0])
            self._on_type_changed()
        else:
            self.var_type.set("")
            self._hide_category()
            self._clear_ids()
            self.lbl_preview_title.configure(text="No types in JSON")

    def _on_select_png_root(self):
        folder = filedialog.askdirectory(title="Select PNG root folder")
        if not folder:
            return
        self.png_root = folder
        self.var_png_root.set(folder)
        self.var_status.set(f"PNG root set to: {folder}")

    # ------------------------------------------------------------------
    #  Type / Category handlers
    # ------------------------------------------------------------------

    def _on_type_changed(self, _event=None):
        t = self.var_type.get()

        if not t:
            self._hide_category()
            self._clear_ids()
            return

        # If Item & nested categories -> show Category
        if t == "Item" and get_categories(self.icon_db, "Item"):
            cats = get_categories(self.icon_db, "Item")
            self.combo_category["values"] = cats
            if self.var_category.get() not in cats:
                self.var_category.set(cats[0] if cats else "")
            self._show_category()
        else:
            self._hide_category()
            self.var_category.set("")

        self.refresh_id_list()

    def _on_category_changed(self, _event=None):
        self.refresh_id_list()

    # ------------------------------------------------------------------
    #  List + Preview refresh
    # ------------------------------------------------------------------

    def refresh_id_list(self):
        self._clear_ids()

        t = self.var_type.get()
        if not t:
            self.lbl_preview_title.configure(text="No type selected")
            return

        cat = None
        if t == "Item" and self._category_visible():
            cat = self.var_category.get() or None

        entries = get_ids(self.icon_db, t, category=cat)
        self.current_entries = entries

        if not entries:
            if t == "Item" and cat:
                self.lbl_preview_title.configure(
                    text=f"{t}/{cat}: 0 entries"
                )
            else:
                self.lbl_preview_title.configure(text=f"{t}: 0 entries")
            return

        ids = list(entries.keys())
        filter_text = self.var_filter.get().strip()

        # sort numeric IDs numerically, then others lexicographically
        def sort_key(s):
            return (0, int(s)) if s.isdigit() else (1, s)

        ids.sort(key=sort_key)

        if filter_text:
            ids = [i for i in ids if filter_text in i]

        for i in ids:
            self.list_ids.insert("end", i)

        if t == "Item" and cat:
            label = f"{t}/{cat}: {len(ids)} entries"
        else:
            label = f"{t}: {len(ids)} entries"

        self.lbl_preview_title.configure(text=label)
        self.preview_label.configure(image="", text="")
        self.current_image = None
        self.var_info.set("")

    def _on_id_selected(self, _event=None):
        sel = self.list_ids.curselection()
        if not sel:
            return
        index = sel[0]
        item_id = self.list_ids.get(index)

        rel_path = self.current_entries.get(item_id)
        if not rel_path:
            return

        # Compute full path: PNG root / relative path
        if not self.png_root:
            self.var_status.set("PNG root not set")
            messagebox.showwarning(
                "PNG root not set",
                "Please select the PNG root folder first.",
            )
            return

        full_path = os.path.normpath(os.path.join(self.png_root, rel_path))

        if not os.path.exists(full_path):
            self._show_missing_image(full_path, item_id)
            return

        # Load with PhotoImage
        try:
            img = tk.PhotoImage(file=full_path)

            max_w, max_h = 512, 512
            w, h = img.width(), img.height()
            if w > max_w or h > max_h:
                scale = max(w / max_w, h / max_h)
                scale = int(scale)
                if scale < 1:
                    scale = 1
                img = img.subsample(scale, scale)

            self.current_image = img
            self.preview_label.configure(image=img, text="")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Error",
                f"Failed to load image:\n{full_path}\n\n{exc}",
            )
            self._show_missing_image(full_path, item_id)
            return

        # Info text
        t = self.var_type.get() or "?"
        if t == "Item" and self._category_visible():
            cat = self.var_category.get() or "?"
            prefix = f"Type: {t}    Category: {cat}    ID: {item_id}"
        else:
            prefix = f"Type: {t}    ID: {item_id}"

        self.var_info.set(f"{prefix}\nPath: {full_path}")
        self.var_status.set("Image loaded")

    # ------------------------------------------------------------------
    #  Small helpers
    # ------------------------------------------------------------------

    def _clear_ids(self):
        self.list_ids.delete(0, "end")
        self.current_entries = {}
        self.current_image = None
        self.preview_label.configure(image="", text="")
        self.var_info.set("")

    def _show_missing_image(self, full_path, item_id):
        self.preview_label.configure(
            image="",
            text="Image not found",
            fg=FG_TEXT,
            bg=BG_PREVIEW,
        )
        t = self.var_type.get() or "?"
        if t == "Item" and self._category_visible():
            cat = self.var_category.get() or "?"
            prefix = f"Type: {t}    Category: {cat}    ID: {item_id}"
        else:
            prefix = f"Type: {t}    ID: {item_id}"
        self.var_info.set(f"{prefix}\nMissing file: {full_path}")
        self.var_status.set("Image file not found")

    def _copy_selected_id(self):
        """Copy the currently selected ID to the system clipboard."""
        sel = self.list_ids.curselection()
        if not sel:
            self.var_status.set("No ID selected")
            return

        item_id = self.list_ids.get(sel[0])
        self.clipboard_clear()
        self.clipboard_append(item_id)
        self.update()  # keep it in the clipboard

        self.var_status.set(f"Copied ID: {item_id}")

    def _show_category(self):
        self.category_frame.grid()
        self.category_frame.update_idletasks()

    def _hide_category(self):
        self.category_frame.grid_remove()

    def _category_visible(self):
        return self.category_frame.winfo_ismapped()


def main():
    app = IconViewerApp()
    app.mainloop()


if __name__ == "__main__":
    main()

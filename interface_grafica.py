# -*- coding: utf-8 -*-
"""
Interface grafica para a Avaliacao 3.

Este arquivo mantem a logica numerica concentrada em Avaliacao-3.py e cria
apenas a camada visual para entrada de dados, execucao, plotagem e exportacao.
"""

from __future__ import annotations

import importlib.util
import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

import numpy as np


PROJECT_DIR = Path(__file__).resolve().parent
CORE_PATH = PROJECT_DIR / "Avaliação-3.py"


def load_core_module() -> Any:
    """Carrega o script original mesmo com acento e hifen no nome do arquivo."""
    spec = importlib.util.spec_from_file_location("avaliacao_3_core", CORE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar {CORE_PATH.name}.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


core = load_core_module()


class ValidationError(ValueError):
    """Erro de validacao exibido diretamente ao usuario."""


@dataclass(frozen=True)
class ColumnSpec:
    key: str
    label: str
    width: int = 90


def parse_float(text: str, label: str, *, min_value: float | None = None, allow_equal_min: bool = False) -> float:
    raw = text.strip()
    if not raw:
        raise ValidationError(f"Informe um valor para {label}.")

    try:
        value = float(core.normalize_number(raw))
    except ValueError as exc:
        raise ValidationError(f"Valor invalido em {label}. Use 2.5, 2,5 ou 2e-3.") from exc

    if min_value is not None:
        valid = value >= min_value if allow_equal_min else value > min_value
        if not valid:
            operator = ">=" if allow_equal_min else ">"
            raise ValidationError(f"{label} deve ser {operator} {min_value:g}.")

    return value


def parse_int(text: str, label: str, *, min_value: int | None = None, max_value: int | None = None) -> int:
    raw = text.strip()
    if not raw:
        raise ValidationError(f"Informe um valor para {label}.")

    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError(f"Valor invalido em {label}. Use um numero inteiro.") from exc

    if min_value is not None and value < min_value:
        raise ValidationError(f"{label} deve ser maior ou igual a {min_value}.")
    if max_value is not None and value > max_value:
        raise ValidationError(f"{label} deve ser menor ou igual a {max_value}.")

    return value


def fmt(value: float, unit: str = "") -> str:
    return core.format_value(float(value), unit)


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, background="#f5f7fb")
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="App.TFrame")

        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.inner.bind("<Configure>", self._sync_scroll_region)
        self.canvas.bind("<Configure>", self._sync_width)
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)

    def _sync_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _sync_width(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class NumericRecordDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        title: str,
        columns: list[ColumnSpec],
        initial: dict[str, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.columns = columns
        self.result: dict[str, float] | None = None
        self.vars: dict[str, tk.StringVar] = {}

        frame = ttk.Frame(self, padding=16, style="App.TFrame")
        frame.grid(row=0, column=0, sticky="nsew")

        for row, column in enumerate(columns):
            ttk.Label(frame, text=column.label).grid(row=row, column=0, sticky="w", pady=4)
            value = "" if initial is None else f"{initial[column.key]:.12g}"
            var = tk.StringVar(value=value)
            self.vars[column.key] = var
            entry = ttk.Entry(frame, textvariable=var, width=22)
            entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
            if row == 0:
                entry.focus_set()

        buttons = ttk.Frame(frame, style="App.TFrame")
        buttons.grid(row=len(columns), column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(buttons, text="Cancelar", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text="Salvar", style="Accent.TButton", command=self._accept).grid(row=0, column=1)

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        x = parent_x + max((parent.winfo_width() - self.winfo_width()) // 2, 80)
        y = parent_y + max((parent.winfo_height() - self.winfo_height()) // 2, 80)
        self.geometry(f"+{x}+{y}")
        self.wait_window(self)

    def _accept(self) -> None:
        values: dict[str, float] = {}
        try:
            for column in self.columns:
                values[column.key] = parse_float(self.vars[column.key].get(), column.label)
        except ValidationError as exc:
            messagebox.showerror("Entrada invalida", str(exc), parent=self)
            return

        self.result = values
        self.destroy()


class NumericTable(ttk.Frame):
    def __init__(self, parent: tk.Misc, title: str, columns: list[ColumnSpec], *, height: int = 5) -> None:
        super().__init__(parent, style="App.TFrame")
        self.title = title
        self.columns = columns
        self._records: list[dict[str, float]] = []

        ttk.Label(self, text=title, style="Section.TLabel").grid(row=0, column=0, sticky="w")

        table_frame = ttk.Frame(self, style="App.TFrame")
        table_frame.grid(row=1, column=0, sticky="nsew", pady=(6, 0))
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)

        column_ids = [column.key for column in columns]
        self.tree = ttk.Treeview(
            table_frame,
            columns=column_ids,
            show="headings",
            height=height,
            selectmode="browse",
        )
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)

        for column in columns:
            self.tree.heading(column.key, text=column.label)
            self.tree.column(column.key, width=column.width, stretch=True, anchor="center")

        button_frame = ttk.Frame(self, style="App.TFrame")
        button_frame.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(button_frame, text="Adicionar", command=self.add_record).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(button_frame, text="Editar", command=self.edit_selected).grid(row=0, column=1, padx=(0, 6))
        ttk.Button(button_frame, text="Remover", command=self.remove_selected).grid(row=0, column=2)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    @property
    def records(self) -> list[dict[str, float]]:
        return [record.copy() for record in self._records]

    def set_records(self, records: list[dict[str, float]]) -> None:
        self._records = [record.copy() for record in records]
        self._refresh()

    def clear(self) -> None:
        self._records.clear()
        self._refresh()

    def add_record(self) -> None:
        dialog = NumericRecordDialog(self, f"Adicionar - {self.title}", self.columns)
        if dialog.result is not None:
            self._records.append(dialog.result)
            self._refresh(select_index=len(self._records) - 1)

    def edit_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Edicao", "Selecione uma linha para editar.", parent=self)
            return

        dialog = NumericRecordDialog(self, f"Editar - {self.title}", self.columns, self._records[index])
        if dialog.result is not None:
            self._records[index] = dialog.result
            self._refresh(select_index=index)

    def remove_selected(self) -> None:
        index = self._selected_index()
        if index is None:
            messagebox.showinfo("Remocao", "Selecione uma linha para remover.", parent=self)
            return

        del self._records[index]
        next_index = min(index, len(self._records) - 1)
        self._refresh(select_index=next_index if next_index >= 0 else None)

    def _selected_index(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _refresh(self, *, select_index: int | None = None) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, record in enumerate(self._records):
            values = [f"{record[column.key]:.6g}" for column in self.columns]
            item_id = str(index)
            self.tree.insert("", "end", iid=item_id, values=values)

        if select_index is not None and 0 <= select_index < len(self._records):
            item_id = str(select_index)
            self.tree.selection_set(item_id)
            self.tree.see(item_id)


class BeamGui(tk.Tk):
    SUPPORT_OPTIONS = {
        "Apoio": "apoio",
        "Engaste": "engaste",
        "Livre": "livre",
    }

    SECTION_OPTIONS = ("Retangular", "Circular", "Perfil I")
    MATERIAL_OPTIONS = ("Aço estrutural", "Alumínio estrutural", "Concreto genérico", "Personalizado")

    MATERIAL_PRESETS = {
        "Aço estrutural": (200.0e9, 250.0e6),
        "Alumínio estrutural": (70.0e9, 150.0e6),
        "Concreto genérico": (30.0e9, 30.0e6),
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Avaliação 3 - Análise de Vigas")
        self.geometry("1320x840")
        self.minsize(1100, 720)

        self.result: Any | None = None
        self.figure_canvas: FigureCanvasTkAgg | None = None
        self.toolbar: NavigationToolbar2Tk | None = None

        self._create_variables()
        self._configure_style()
        self._build_layout()
        self._load_defaults()
        self._set_status("Pronto.")

    def _create_variables(self) -> None:
        self.length_var = tk.StringVar()
        self.divisions_var = tk.StringVar()

        self.section_var = tk.StringVar()
        self.rect_b_var = tk.StringVar()
        self.rect_h_var = tk.StringVar()
        self.circle_d_var = tk.StringVar()
        self.i_h_var = tk.StringVar()
        self.i_bf_var = tk.StringVar()
        self.i_tf_var = tk.StringVar()
        self.i_tw_var = tk.StringVar()

        self.material_var = tk.StringVar()
        self.material_name_var = tk.StringVar()
        self.elastic_modulus_var = tk.StringVar()
        self.yield_stress_var = tk.StringVar()
        self.material_hint_var = tk.StringVar()

        self.left_support_var = tk.StringVar()
        self.right_support_var = tk.StringVar()
        self.status_var = tk.StringVar()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(background="#f5f7fb")
        style.configure("App.TFrame", background="#f5f7fb")
        style.configure("Panel.TLabelframe", background="#f5f7fb", bordercolor="#cbd5e1", relief="solid")
        style.configure(
            "Panel.TLabelframe.Label",
            background="#f5f7fb",
            foreground="#1e293b",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TLabel", background="#f5f7fb", foreground="#1f2937", font=("Segoe UI", 9))
        style.configure("Title.TLabel", background="#f5f7fb", foreground="#0f172a", font=("Segoe UI", 15, "bold"))
        style.configure("Subtitle.TLabel", background="#f5f7fb", foreground="#475569", font=("Segoe UI", 9))
        style.configure("Section.TLabel", background="#f5f7fb", foreground="#334155", font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background="#e2e8f0", foreground="#0f172a", padding=(10, 5))
        style.configure("TEntry", fieldbackground="#ffffff", bordercolor="#cbd5e1")
        style.configure("TCombobox", fieldbackground="#ffffff", bordercolor="#cbd5e1")
        style.configure("TButton", font=("Segoe UI", 9), padding=(10, 5))
        style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff")
        style.map(
            "Accent.TButton",
            background=[("active", "#1d4ed8"), ("disabled", "#93c5fd")],
            foreground=[("disabled", "#eff6ff")],
        )
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_layout(self) -> None:
        header = ttk.Frame(self, padding=(16, 12, 16, 8), style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="Análise de Vigas por Diferenças Finitas", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            header,
            text="Entrada parametrica, solucao numerica, resumo, grafico e exportacao nos formatos do script original.",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        actions = ttk.Frame(header, style="App.TFrame")
        actions.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(actions, text="Carregar exemplo", command=self._load_example).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Limpar", command=self._load_defaults).grid(row=0, column=1, padx=(0, 8))
        self.calculate_button = ttk.Button(actions, text="Calcular", style="Accent.TButton", command=self.calculate)
        self.calculate_button.grid(row=0, column=2)

        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 12))

        self.input_scroller = ScrollableFrame(paned)
        self.output_frame = ttk.Frame(paned, style="App.TFrame")
        paned.add(self.input_scroller, weight=1)
        paned.add(self.output_frame, weight=3)

        self._build_input_panel(self.input_scroller.inner)
        self._build_output_panel(self.output_frame)

        status = ttk.Label(self, textvariable=self.status_var, style="Status.TLabel", anchor="w")
        status.grid(row=2, column=0, sticky="ew")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

    def _build_input_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        self._build_geometry_panel(parent).grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self._build_section_panel(parent).grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self._build_material_panel(parent).grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._build_support_panel(parent).grid(row=3, column=0, sticky="ew", pady=(0, 10))
        self._build_load_panel(parent).grid(row=4, column=0, sticky="ew", pady=(0, 14))

    def _build_geometry_panel(self, parent: tk.Misc) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Geometria e malha", padding=12, style="Panel.TLabelframe")
        panel.columnconfigure(1, weight=1)

        self._add_entry(panel, 0, "Comprimento L [m]", self.length_var)
        self._add_entry(panel, 1, "Divisões da malha", self.divisions_var)

        return panel

    def _build_section_panel(self, parent: tk.Misc) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Seção transversal", padding=12, style="Panel.TLabelframe")
        panel.columnconfigure(1, weight=1)

        ttk.Label(panel, text="Tipo").grid(row=0, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(panel, textvariable=self.section_var, values=self.SECTION_OPTIONS, state="readonly")
        combo.grid(row=0, column=1, sticky="ew", pady=4)
        combo.bind("<<ComboboxSelected>>", self._update_section_fields)

        self.section_frames: dict[str, ttk.Frame] = {}

        rect = ttk.Frame(panel, style="App.TFrame")
        rect.columnconfigure(1, weight=1)
        self._add_entry(rect, 0, "Largura b [m]", self.rect_b_var)
        self._add_entry(rect, 1, "Altura h [m]", self.rect_h_var)
        self.section_frames["Retangular"] = rect

        circle = ttk.Frame(panel, style="App.TFrame")
        circle.columnconfigure(1, weight=1)
        self._add_entry(circle, 0, "Diâmetro d [m]", self.circle_d_var)
        self.section_frames["Circular"] = circle

        profile_i = ttk.Frame(panel, style="App.TFrame")
        profile_i.columnconfigure(1, weight=1)
        self._add_entry(profile_i, 0, "Altura total h [m]", self.i_h_var)
        self._add_entry(profile_i, 1, "Largura da mesa bf [m]", self.i_bf_var)
        self._add_entry(profile_i, 2, "Espessura da mesa tf [m]", self.i_tf_var)
        self._add_entry(profile_i, 3, "Espessura da alma tw [m]", self.i_tw_var)
        self.section_frames["Perfil I"] = profile_i

        for frame in self.section_frames.values():
            frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        return panel

    def _build_material_panel(self, parent: tk.Misc) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Material", padding=12, style="Panel.TLabelframe")
        panel.columnconfigure(1, weight=1)

        ttk.Label(panel, text="Tipo").grid(row=0, column=0, sticky="w", pady=4)
        combo = ttk.Combobox(panel, textvariable=self.material_var, values=self.MATERIAL_OPTIONS, state="readonly")
        combo.grid(row=0, column=1, sticky="ew", pady=4)
        combo.bind("<<ComboboxSelected>>", self._update_material_fields)

        ttk.Label(panel, textvariable=self.material_hint_var, style="Subtitle.TLabel", wraplength=350).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )

        self.manual_material_frame = ttk.Frame(panel, style="App.TFrame")
        self.manual_material_frame.columnconfigure(1, weight=1)
        self._add_entry(self.manual_material_frame, 0, "Nome", self.material_name_var)
        self._add_entry(self.manual_material_frame, 1, "E [Pa]", self.elastic_modulus_var)
        self._add_entry(self.manual_material_frame, 2, "sigma_y [Pa]", self.yield_stress_var)
        self.manual_material_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        return panel

    def _build_support_panel(self, parent: tk.Misc) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Vínculos", padding=12, style="Panel.TLabelframe")
        panel.columnconfigure(1, weight=1)

        values = tuple(self.SUPPORT_OPTIONS)
        ttk.Label(panel, text="Extremo x=0").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(panel, textvariable=self.left_support_var, values=values, state="readonly").grid(
            row=0, column=1, sticky="ew", pady=4
        )

        ttk.Label(panel, text="Extremo x=L").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(panel, textvariable=self.right_support_var, values=values, state="readonly").grid(
            row=1, column=1, sticky="ew", pady=4
        )

        self.support_table = NumericTable(
            panel,
            "Apoios internos",
            [ColumnSpec("x", "x [m]", 110)],
            height=4,
        )
        self.support_table.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0))

        return panel

    def _build_load_panel(self, parent: tk.Misc) -> ttk.LabelFrame:
        panel = ttk.LabelFrame(parent, text="Cargas", padding=12, style="Panel.TLabelframe")
        panel.columnconfigure(0, weight=1)

        self.point_table = NumericTable(
            panel,
            "Cargas concentradas",
            [ColumnSpec("value", "P [N]", 100), ColumnSpec("x", "x [m]", 90)],
            height=5,
        )
        self.point_table.grid(row=0, column=0, sticky="nsew")

        self.distributed_table = NumericTable(
            panel,
            "Cargas distribuídas lineares",
            [
                ColumnSpec("x1", "x1 [m]", 80),
                ColumnSpec("q1", "q1 [N/m]", 90),
                ColumnSpec("x2", "x2 [m]", 80),
                ColumnSpec("q2", "q2 [N/m]", 90),
            ],
            height=5,
        )
        self.distributed_table.grid(row=1, column=0, sticky="nsew", pady=(16, 0))

        return panel

    def _build_output_panel(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(parent)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        summary_frame = ttk.Frame(self.notebook, padding=10, style="App.TFrame")
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)
        self.summary_text = tk.Text(
            summary_frame,
            wrap="word",
            relief="solid",
            borderwidth=1,
            font=("Consolas", 10),
            background="#ffffff",
            foreground="#0f172a",
        )
        self.summary_text.grid(row=0, column=0, sticky="nsew")
        summary_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=self.summary_text.yview)
        summary_scroll.grid(row=0, column=1, sticky="ns")
        self.summary_text.configure(yscrollcommand=summary_scroll.set)
        self.summary_text.insert(
            "1.0",
            "Preencha os dados da viga e clique em Calcular.\n\n"
            "Os resultados serao exportados para CSV, PNG e PDF na pasta do projeto.",
        )
        self.summary_text.configure(state="disabled")

        plot_frame = ttk.Frame(self.notebook, padding=8, style="App.TFrame")
        plot_frame.columnconfigure(0, weight=1)
        plot_frame.rowconfigure(1, weight=1)
        self.plot_toolbar_frame = ttk.Frame(plot_frame, style="App.TFrame")
        self.plot_toolbar_frame.grid(row=0, column=0, sticky="ew")
        self.plot_canvas_frame = ttk.Frame(plot_frame, style="App.TFrame")
        self.plot_canvas_frame.grid(row=1, column=0, sticky="nsew")
        self.plot_canvas_frame.columnconfigure(0, weight=1)
        self.plot_canvas_frame.rowconfigure(0, weight=1)

        table_frame = ttk.Frame(self.notebook, padding=8, style="App.TFrame")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self.data_tree = ttk.Treeview(
            table_frame,
            columns=("x", "q", "w", "Q", "M", "sigma", "ratio"),
            show="headings",
        )
        headings = {
            "x": "x [m]",
            "q": "q [N/m]",
            "w": "w [m]",
            "Q": "Q [N]",
            "M": "M [N m]",
            "sigma": "sigma [Pa]",
            "ratio": "sigma/sigma_y",
        }
        for key, label in headings.items():
            self.data_tree.heading(key, text=label)
            self.data_tree.column(key, width=110, stretch=True, anchor="center")
        self.data_tree.grid(row=0, column=0, sticky="nsew")
        table_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_tree.yview)
        table_y.grid(row=0, column=1, sticky="ns")
        table_x = ttk.Scrollbar(table_frame, orient="horizontal", command=self.data_tree.xview)
        table_x.grid(row=1, column=0, sticky="ew")
        self.data_tree.configure(yscrollcommand=table_y.set, xscrollcommand=table_x.set)

        self.notebook.add(summary_frame, text="Resumo")
        self.notebook.add(plot_frame, text="Gráfico")
        self.notebook.add(table_frame, text="Tabela")

    def _add_entry(self, parent: tk.Misc, row: int, label: str, variable: tk.StringVar) -> ttk.Entry:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=4)
        return entry

    def _load_defaults(self) -> None:
        self.length_var.set("6.0")
        self.divisions_var.set("300")

        self.section_var.set("Retangular")
        self.rect_b_var.set("0.20")
        self.rect_h_var.set("0.40")
        self.circle_d_var.set("0.30")
        self.i_h_var.set("0.40")
        self.i_bf_var.set("0.18")
        self.i_tf_var.set("0.02")
        self.i_tw_var.set("0.01")

        self.material_var.set("Aço estrutural")
        self.material_name_var.set("Personalizado")
        self.elastic_modulus_var.set("200e9")
        self.yield_stress_var.set("250e6")

        self.left_support_var.set("Apoio")
        self.right_support_var.set("Apoio")
        self.support_table.clear()
        self.point_table.clear()
        self.distributed_table.clear()

        self._update_section_fields()
        self._update_material_fields()
        self._set_status("Entradas restauradas.")

    def _load_example(self) -> None:
        model = core.create_example_model()
        self.length_var.set(f"{model.length:.12g}")
        self.divisions_var.set(str(model.divisions))

        self.section_var.set("Retangular")
        self.rect_b_var.set(f"{model.section.details['b']:.12g}")
        self.rect_h_var.set(f"{model.section.details['h']:.12g}")

        self.material_var.set("Aço estrutural")
        self.left_support_var.set(self._support_label(model.left_kind))
        self.right_support_var.set(self._support_label(model.right_kind))
        self.support_table.set_records([{"x": support.x} for support in model.internal_supports])
        self.point_table.set_records([{"value": load.value, "x": load.x} for load in model.point_loads])
        self.distributed_table.set_records(
            [{"x1": load.x1, "q1": load.q1, "x2": load.x2, "q2": load.q2} for load in model.distributed_loads]
        )

        self._update_section_fields()
        self._update_material_fields()
        self._set_status("Exemplo carregado.")

    def _update_section_fields(self, _event: tk.Event | None = None) -> None:
        selected = self.section_var.get()
        for name, frame in self.section_frames.items():
            if name == selected:
                frame.grid()
            else:
                frame.grid_remove()

    def _update_material_fields(self, _event: tk.Event | None = None) -> None:
        selected = self.material_var.get()
        if selected == "Personalizado":
            self.manual_material_frame.grid()
            self.material_hint_var.set("Informe E e sigma_y em unidades SI: Pa = N/m².")
            return

        self.manual_material_frame.grid_remove()
        e_modulus, yield_stress = self.MATERIAL_PRESETS[selected]
        self.material_hint_var.set(f"E = {fmt(e_modulus, 'Pa')}    sigma_y = {fmt(yield_stress, 'Pa')}")

    def calculate(self) -> None:
        self._set_busy(True)
        try:
            self._set_status("Montando modelo...")
            model, interface_warnings = self._build_model()

            self._set_status("Resolvendo sistema de diferenças finitas...")
            self.update_idletasks()
            result = core.solve_beam(model)

            self._set_status("Exportando CSV, PNG e PDF...")
            base = PROJECT_DIR
            csv_path = base / "resultados_viga.csv"
            png_path = base / "resultado_viga.png"
            pdf_path = base / "resultado_viga.pdf"
            core.save_csv(result, csv_path)
            core.save_matplotlib_plot(result, png_path, pdf_path, show=False)

            self.result = result
            self._render_summary(result, csv_path, png_path, pdf_path, interface_warnings)
            self._render_plot(result)
            self._render_table(result)
            self.notebook.select(0)
            self._set_status("Calculo concluido e arquivos exportados.")
        except ValidationError as exc:
            messagebox.showerror("Dados invalidos", str(exc), parent=self)
            self._set_status("Corrija os dados de entrada.")
        except Exception as exc:  # noqa: BLE001 - erro numerico precisa chegar claro ao usuario.
            messagebox.showerror(
                "Erro durante a analise",
                f"{exc}\n\nConfira os dados de entrada, a malha, os vinculos e as dependencias.",
                parent=self,
            )
            self._set_status("Erro durante a analise.")
        finally:
            self._set_busy(False)

    def _build_model(self) -> tuple[Any, list[str]]:
        length = parse_float(self.length_var.get(), "Comprimento L", min_value=0.0)
        divisions = parse_int(self.divisions_var.get(), "Divisoes da malha", min_value=20, max_value=5000)

        section = self._build_section()
        material = self._build_material()
        left_kind = self.SUPPORT_OPTIONS[self.left_support_var.get()]
        right_kind = self.SUPPORT_OPTIONS[self.right_support_var.get()]

        warnings: list[str] = []
        internal_supports = self._build_internal_supports(length, divisions, warnings)
        point_loads = self._build_point_loads(length)
        distributed_loads = self._build_distributed_loads(length)

        model = core.BeamModel(
            length=length,
            section=section,
            material=material,
            divisions=divisions,
            left_kind=left_kind,
            right_kind=right_kind,
            internal_supports=internal_supports,
            point_loads=point_loads,
            distributed_loads=distributed_loads,
        )
        return model, warnings

    def _build_section(self) -> Any:
        selected = self.section_var.get()

        if selected == "Retangular":
            b = parse_float(self.rect_b_var.get(), "Largura b", min_value=0.0)
            h = parse_float(self.rect_h_var.get(), "Altura h", min_value=0.0)
            return core.Section(
                name="Retangular",
                area=b * h,
                inertia=b * h**3 / 12.0,
                zmax=h / 2.0,
                details={"b": b, "h": h},
            )

        if selected == "Circular":
            diameter = parse_float(self.circle_d_var.get(), "Diametro d", min_value=0.0)
            return core.Section(
                name="Circular",
                area=np.pi * diameter**2 / 4.0,
                inertia=np.pi * diameter**4 / 64.0,
                zmax=diameter / 2.0,
                details={"d": diameter},
            )

        h = parse_float(self.i_h_var.get(), "Altura total h", min_value=0.0)
        bf = parse_float(self.i_bf_var.get(), "Largura da mesa bf", min_value=0.0)
        tf = parse_float(self.i_tf_var.get(), "Espessura da mesa tf", min_value=0.0)
        tw = parse_float(self.i_tw_var.get(), "Espessura da alma tw", min_value=0.0)

        if h <= 2.0 * tf:
            raise ValidationError("No Perfil I, a altura total h deve ser maior que 2*tf.")
        if tw > bf:
            raise ValidationError("No Perfil I, a espessura da alma tw nao deve exceder bf.")

        web_h = h - 2.0 * tf
        area = 2.0 * bf * tf + tw * web_h
        dist = h / 2.0 - tf / 2.0
        inertia = 2.0 * (bf * tf**3 / 12.0 + bf * tf * dist**2) + tw * web_h**3 / 12.0
        return core.Section(
            name="Perfil I",
            area=area,
            inertia=inertia,
            zmax=h / 2.0,
            details={"h": h, "bf": bf, "tf": tf, "tw": tw},
        )

    def _build_material(self) -> Any:
        selected = self.material_var.get()
        if selected != "Personalizado":
            e_modulus, yield_stress = self.MATERIAL_PRESETS[selected]
            return core.Material(selected, e_modulus, yield_stress)

        name = self.material_name_var.get().strip() or "Personalizado"
        e_modulus = parse_float(self.elastic_modulus_var.get(), "Modulo de elasticidade E", min_value=0.0)
        yield_stress = parse_float(self.yield_stress_var.get(), "Tensao limite sigma_y", min_value=0.0)
        return core.Material(name, e_modulus, yield_stress)

    def _build_internal_supports(self, length: float, divisions: int, warnings: list[str]) -> list[Any]:
        used_nodes = {0, divisions}
        supports: list[Any] = []

        for index, record in enumerate(self.support_table.records, start=1):
            x_value = record["x"]
            if not 0.0 < x_value < length:
                raise ValidationError(f"Apoio interno {index}: x deve estar estritamente entre 0 e L.")

            node = core.nearest_node(length, divisions, x_value)
            snapped = node * length / divisions
            if node in used_nodes:
                raise ValidationError(
                    f"Apoio interno {index}: a posicao cai em um no ja vinculado. "
                    "Ajuste a posicao ou refine a malha."
                )

            used_nodes.add(node)
            if abs(snapped - x_value) > 1e-10:
                warnings.append(f"Apoio interno {index} ajustado para x={fmt(snapped, 'm')}.")

            supports.append(core.Support("apoio", snapped, node))

        return supports

    def _build_point_loads(self, length: float) -> list[Any]:
        loads: list[Any] = []
        for index, record in enumerate(self.point_table.records, start=1):
            x_value = record["x"]
            if not 0.0 <= x_value <= length:
                raise ValidationError(f"Carga concentrada {index}: x deve satisfazer 0 <= x <= L.")
            loads.append(core.PointLoad(record["value"], x_value))
        return loads

    def _build_distributed_loads(self, length: float) -> list[Any]:
        loads: list[Any] = []
        for index, record in enumerate(self.distributed_table.records, start=1):
            x1 = record["x1"]
            q1 = record["q1"]
            x2 = record["x2"]
            q2 = record["q2"]

            if not (0.0 <= x1 <= length and 0.0 <= x2 <= length):
                raise ValidationError(f"Carga distribuida {index}: x1 e x2 devem satisfazer 0 <= x <= L.")
            if abs(x2 - x1) < 1e-14:
                raise ValidationError(f"Carga distribuida {index}: x1 e x2 devem ser diferentes.")

            if x2 < x1:
                x1, x2 = x2, x1
                q1, q2 = q2, q1

            loads.append(core.DistributedLoad(x1, q1, x2, q2))

        return loads

    def _render_summary(
        self,
        result: Any,
        csv_path: Path,
        png_path: Path,
        pdf_path: Path,
        interface_warnings: list[str],
    ) -> None:
        model = result.model
        sec = model.section
        mat = model.material

        max_w_i = int(np.argmax(np.abs(result.w)))
        max_q_i = int(np.argmax(np.abs(result.shear)))
        max_m_i = int(np.argmax(np.abs(result.moment)))
        max_ratio_i = int(np.argmax(result.sigma_ratio))

        flex_status = (
            "Atencao: ha indicacao de escoamento por flexao (razao > 1)."
            if result.sigma_ratio[max_ratio_i] > 1.0
            else "Verificacao de flexao: razao <= 1 em todos os pontos da malha."
        )

        lines = [
            "RESUMO DOS RESULTADOS",
            "=" * 72,
            f"Secao: {sec.name}",
            f"  Area A              = {fmt(sec.area, 'm²')}",
            f"  Inercia Iyy         = {fmt(sec.inertia, 'm^4')}",
            f"  zmax                = {fmt(sec.zmax, 'm')}",
            f"Material: {mat.name}",
            f"  E                   = {fmt(mat.elastic_modulus, 'Pa')}",
            f"  sigma_y             = {fmt(mat.yield_stress, 'Pa')}",
            f"Malha                 = {model.divisions} divisoes",
            f"dx                    = {fmt(model.length / model.divisions, 'm')}",
            f"Condicionamento num.  = {result.condition_number:.3e}",
            "",
            "Extremos numericos:",
            f"  |w|max              = {fmt(abs(result.w[max_w_i]), 'm')} em x={fmt(result.x[max_w_i], 'm')}",
            f"  |Q|max              = {fmt(abs(result.shear[max_q_i]), 'N')} em x={fmt(result.x[max_q_i], 'm')}",
            f"  |M|max              = {fmt(abs(result.moment[max_m_i]), 'N m')} em x={fmt(result.x[max_m_i], 'm')}",
            f"  sigma_max/sigma_y   = {result.sigma_ratio[max_ratio_i]:.6g} em x={fmt(result.x[max_ratio_i], 'm')}",
            f"  {flex_status}",
        ]

        all_warnings = interface_warnings + list(result.warnings)
        if all_warnings:
            lines.extend(["", "Avisos:"])
            lines.extend(f"  - {warning}" for warning in all_warnings)

        lines.extend(
            [
                "",
                "Arquivos gerados:",
                f"  CSV: {csv_path}",
                f"  PNG: {png_path}",
                f"  PDF: {pdf_path}",
            ]
        )

        self.summary_text.configure(state="normal")
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", "\n".join(lines))
        self.summary_text.configure(state="disabled")

    def _render_plot(self, result: Any) -> None:
        for child in self.plot_canvas_frame.winfo_children():
            child.destroy()
        for child in self.plot_toolbar_frame.winfo_children():
            child.destroy()

        fig = Figure(figsize=(10.5, 9.0), dpi=100, constrained_layout=True)
        axes = fig.subplots(
            5,
            1,
            sharex=True,
            gridspec_kw={"height_ratios": [1.2, 1.0, 1.0, 1.0, 1.0]},
        )
        fig.suptitle("Avaliação 3 - Análise de Viga por Diferenças Finitas", fontsize=14, fontweight="bold")

        x = result.x
        core.draw_beam_schema(axes[0], result)

        axes[1].plot(x, result.shear, color="#0ea5e9", lw=1.9)
        core.configure_result_axis(axes[1], "Esforço cortante Q(x)", "Q [N]")

        axes[2].plot(x, result.moment, color="#16a34a", lw=1.9)
        core.configure_result_axis(axes[2], "Momento fletor M(x)", "M [N m]")

        axes[3].plot(x, result.w, color="#7c3aed", lw=1.9)
        core.configure_result_axis(axes[3], "Deslocamento w(x)", "w [m]")

        axes[4].plot(x, result.sigma_ratio, color="#dc2626", lw=1.9)
        axes[4].axhline(1.0, color="#991b1b", ls="--", lw=1.2, label="limite = 1")
        axes[4].fill_between(
            x,
            1.0,
            result.sigma_ratio,
            where=result.sigma_ratio > 1.0,
            color="#fecaca",
            alpha=0.65,
            interpolate=True,
        )
        axes[4].legend(loc="best")
        core.configure_result_axis(axes[4], "Razão sigma_max/sigma_y", "[-]")
        axes[4].set_xlabel("x [m]")

        for axis in axes[1:]:
            ymin, ymax = axis.get_ylim()
            if abs(ymax - ymin) < 1e-14:
                axis.set_ylim(ymin - 1.0, ymax + 1.0)

        self.figure_canvas = FigureCanvasTkAgg(fig, master=self.plot_canvas_frame)
        canvas_widget = self.figure_canvas.get_tk_widget()
        canvas_widget.grid(row=0, column=0, sticky="nsew")
        self.toolbar = NavigationToolbar2Tk(self.figure_canvas, self.plot_toolbar_frame, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.grid(row=0, column=0, sticky="w")
        self.figure_canvas.draw()

    def _render_table(self, result: Any) -> None:
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)

        for index, values in enumerate(
            zip(
                result.x,
                result.q,
                result.w,
                result.shear,
                result.moment,
                result.sigma,
                result.sigma_ratio,
            )
        ):
            self.data_tree.insert("", "end", iid=str(index), values=[f"{float(value):.6e}" for value in values])

    def _support_label(self, kind: str) -> str:
        for label, value in self.SUPPORT_OPTIONS.items():
            if value == kind:
                return label
        return "Apoio"

    def _set_busy(self, busy: bool) -> None:
        self.calculate_button.configure(state="disabled" if busy else "normal")
        self.configure(cursor="watch" if busy else "")
        self.update_idletasks()

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.update_idletasks()


def main() -> None:
    app = BeamGui()
    app.mainloop()


if __name__ == "__main__":
    main()

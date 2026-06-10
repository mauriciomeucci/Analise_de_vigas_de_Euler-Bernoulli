"""
Avaliação 3 - Programação de Métodos Numéricos aplicados à Engenharia Civil

Análise de vigas de Euler-Bernoulli por diferenças finitas.

O programa atende às etapas do enunciado:
  1. Geometria: comprimento L e seção retangular, circular ou Perfil I.
  2. Material: E e sigma_y, por valor manual ou pré-seleção.
  3. Cargas: concentradas P e distribuídas lineares q.
  4. Vínculos: apoios, engastes nos extremos e extremos livres.
  5. Deslocamentos w pelo método das diferenças finitas.
  6. Esforços Q e M por diferenciação numérica de w.
  7. Tensões normais máximas de flexão.
  8. Plotagem única em matplotlib, com gráficos empilhados.

Convenção de sinais adotada:
  - Cargas positivas atuam para baixo.
  - Deslocamentos positivos são para baixo.
  - A equação resolvida é d4w/dx4 = q(x)/(E I).
  - O momento é calculado por M(x) = -E I w''(x).
  - O esforço cortante é calculado por Q(x) = dM/dx.
"""

# Integrantes: Maurício Meucci e Luis Eduardo Aires

from __future__ import annotations

import csv
import math
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_MPL_CACHE_DIR = Path(__file__).resolve().parent / "matplotlib_cache"
_MPL_CACHE_DIR.mkdir(exist_ok=True)
for _LOCK_FILE in _MPL_CACHE_DIR.glob("*.matplotlib-lock"):
    try:
        _LOCK_FILE.unlink()
    except OSError:
        pass
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CACHE_DIR))

try:
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon, Rectangle
except ModuleNotFoundError:
    plt = None
    Polygon = None
    Rectangle = None


# ---------------------------------------------------------------------------
# Estruturas de dados


@dataclass(frozen=True)
class Section:
    name: str
    area: float
    inertia: float
    zmax: float
    details: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Material:
    name: str
    elastic_modulus: float
    yield_stress: float


@dataclass(frozen=True)
class PointLoad:
    value: float
    x: float


@dataclass(frozen=True)
class DistributedLoad:
    x1: float
    q1: float
    x2: float
    q2: float

    def value_at(self, x: float) -> float:
        if self.x1 <= x <= self.x2:
            t = (x - self.x1) / (self.x2 - self.x1)
            return self.q1 + t * (self.q2 - self.q1)
        return 0.0


@dataclass(frozen=True)
class Support:
    kind: str
    x: float
    node: int


@dataclass
class BeamModel:
    length: float
    section: Section
    material: Material
    divisions: int
    left_kind: str
    right_kind: str
    internal_supports: list[Support] = field(default_factory=list)
    point_loads: list[PointLoad] = field(default_factory=list)
    distributed_loads: list[DistributedLoad] = field(default_factory=list)


@dataclass
class BeamResult:
    model: BeamModel
    x: np.ndarray
    q: np.ndarray
    w: np.ndarray
    moment: np.ndarray
    shear: np.ndarray
    sigma: np.ndarray
    sigma_ratio: np.ndarray
    condition_number: float
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Entrada e formatação


def script_dir() -> Path:
    if "__file__" in globals():
        return Path(__file__).resolve().parent
    return Path.cwd()


def normalize_number(text: str) -> str:
    text = text.strip().replace(" ", "")
    if "," in text:
        if "." in text:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", ".")
    return text


def format_value(value: float, unit: str = "") -> str:
    if abs(value) < 1e-14:
        out = "0"
    elif 1e-3 <= abs(value) < 1.0e4:
        out = f"{value:.6g}"
    else:
        out = f"{value:.6e}"
    return f"{out} {unit}".rstrip()


def read_float(
    prompt: str,
    *,
    default: float | None = None,
    min_value: float | None = None,
    allow_equal_min: bool = False,
) -> float:
    while True:
        suffix = f" [{default:g}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            value = float(default)
        else:
            try:
                value = float(normalize_number(raw))
            except ValueError:
                print("Valor inválido. Use formatos como 2.5, 2,5 ou 2e-3.")
                continue

        if min_value is not None:
            ok = value >= min_value if allow_equal_min else value > min_value
            if not ok:
                op = ">=" if allow_equal_min else ">"
                print(f"O valor deve ser {op} {min_value:g}.")
                continue
        return value


def read_int(
    prompt: str,
    *,
    default: int | None = None,
    min_value: int | None = None,
    max_value: int | None = None,
) -> int:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if raw == "" and default is not None:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                print("Valor inválido. Digite um número inteiro.")
                continue
        if min_value is not None and value < min_value:
            print(f"O valor deve ser maior ou igual a {min_value}.")
            continue
        if max_value is not None and value > max_value:
            print(f"O valor deve ser menor ou igual a {max_value}.")
            continue
        return value


def read_menu(title: str, options: list[tuple[str, str]], *, default: int = 1) -> str:
    while True:
        print(f"\n{title}")
        for index, (_, label) in enumerate(options, start=1):
            marker = " [padrão]" if index == default else ""
            print(f"  {index}. {label}{marker}")
        raw = input("Escolha uma opção: ").strip()
        if raw == "":
            return options[default - 1][0]
        try:
            index = int(raw)
        except ValueError:
            print("Opção inválida.")
            continue
        if 1 <= index <= len(options):
            return options[index - 1][0]
        print("Opção inválida.")


def yes_no(prompt: str, *, default: bool = False) -> bool:
    suffix = "S/n" if default else "s/N"
    while True:
        raw = input(f"{prompt} ({suffix}): ").strip().lower()
        if raw == "":
            return default
        if raw in {"s", "sim", "y", "yes"}:
            return True
        if raw in {"n", "nao", "não", "no"}:
            return False
        print("Responda com sim ou não.")


def nearest_node(length: float, divisions: int, x_value: float) -> int:
    return int(np.clip(round(x_value / length * divisions), 0, divisions))


# ---------------------------------------------------------------------------
# Geometria, material, vínculos e cargas


def read_section() -> Section:
    choice = read_menu(
        "ETAPA 1 - Seção transversal",
        [
            ("retangular", "Retangular"),
            ("circular", "Circular"),
            ("perfil_i", "Perfil I simétrico"),
        ],
    )

    if choice == "retangular":
        print("\nSeção retangular.")
        b = read_float("Largura b [m]", min_value=0.0)
        h = read_float("Altura h [m]", min_value=0.0)
        return Section(
            name="Retangular",
            area=b * h,
            inertia=b * h**3 / 12.0,
            zmax=h / 2.0,
            details={"b": b, "h": h},
        )

    if choice == "circular":
        print("\nSeção circular.")
        d = read_float("Diâmetro d [m]", min_value=0.0)
        return Section(
            name="Circular",
            area=math.pi * d**2 / 4.0,
            inertia=math.pi * d**4 / 64.0,
            zmax=d / 2.0,
            details={"d": d},
        )

    print("\nPerfil I simétrico.")
    while True:
        h = read_float("Altura total h [m]", min_value=0.0)
        bf = read_float("Largura da mesa bf [m]", min_value=0.0)
        tf = read_float("Espessura da mesa tf [m]", min_value=0.0)
        tw = read_float("Espessura da alma tw [m]", min_value=0.0)
        if h <= 2.0 * tf:
            print("A altura total deve ser maior que 2*tf.")
            continue
        if tw > bf:
            print("A espessura da alma não deve exceder a largura da mesa.")
            continue
        web_h = h - 2.0 * tf
        area = 2.0 * bf * tf + tw * web_h
        dist = h / 2.0 - tf / 2.0
        inertia = 2.0 * (bf * tf**3 / 12.0 + bf * tf * dist**2) + tw * web_h**3 / 12.0
        return Section(
            name="Perfil I",
            area=area,
            inertia=inertia,
            zmax=h / 2.0,
            details={"h": h, "bf": bf, "tf": tf, "tw": tw},
        )


def read_material() -> Material:
    presets = {
        "aco": Material("Aço estrutural", 200.0e9, 250.0e6),
        "aluminio": Material("Alumínio estrutural", 70.0e9, 150.0e6),
        "concreto": Material("Concreto genérico", 30.0e9, 30.0e6),
    }
    choice = read_menu(
        "ETAPA 2 - Material",
        [
            ("aco", "Aço estrutural: E=200 GPa, sigma_y=250 MPa"),
            ("aluminio", "Alumínio estrutural: E=70 GPa, sigma_y=150 MPa"),
            ("concreto", "Concreto genérico: E=30 GPa, sigma_y=30 MPa"),
            ("manual", "Inserir valores manualmente"),
        ],
    )
    if choice in presets:
        return presets[choice]

    print("\nDigite valores em unidades SI: Pa = N/m².")
    e_modulus = read_float("Módulo de elasticidade E [Pa]", min_value=0.0)
    yield_stress = read_float("Tensão limite sigma_y [Pa]", min_value=0.0)
    name = input("Nome do material [Personalizado]: ").strip() or "Personalizado"
    return Material(name, e_modulus, yield_stress)


def read_supports(length: float, divisions: int) -> tuple[str, str, list[Support]]:
    options = [
        ("apoio", "Apoio: w=0 e w''=0"),
        ("engaste", "Engaste: w=0 e w'=0"),
        ("livre", "Extremo livre: w''=0 e w'''=0"),
    ]
    left_kind = read_menu("ETAPA 4 - Vínculo no extremo x=0", options, default=1)
    right_kind = read_menu("ETAPA 4 - Vínculo no extremo x=L", options, default=1)

    print("\nApoios internos são permitidos. Engastes internos não são usados.")
    count = read_int("Quantidade de apoios internos", default=0, min_value=0)
    supports: list[Support] = []
    used_nodes = {0, divisions}
    for index in range(1, count + 1):
        while True:
            x_value = read_float(f"Posição do apoio interno {index} [m]", min_value=0.0)
            if not 0.0 < x_value < length:
                print("A posição deve estar estritamente entre 0 e L.")
                continue
            node = nearest_node(length, divisions, x_value)
            snapped = node * length / divisions
            if node in used_nodes:
                print("Esse apoio caiu em um nó já vinculado. Escolha outra posição.")
                continue
            used_nodes.add(node)
            if abs(snapped - x_value) > 1e-10:
                print(f"  Posição ajustada ao nó mais próximo: x={snapped:g} m.")
            supports.append(Support("apoio", snapped, node))
            break
    return left_kind, right_kind, supports


def read_loads(length: float) -> tuple[list[PointLoad], list[DistributedLoad]]:
    print("\nETAPA 3 - Cargas")
    print("Convenção: cargas positivas atuam para baixo.")

    point_loads: list[PointLoad] = []
    n_point = read_int("Quantidade de cargas concentradas P", default=0, min_value=0)
    for index in range(1, n_point + 1):
        print(f"\nCarga concentrada {index}")
        value = read_float("Valor P [N]")
        while True:
            x_value = read_float("Posição x [m]", min_value=0.0, allow_equal_min=True)
            if 0.0 <= x_value <= length:
                point_loads.append(PointLoad(value, x_value))
                break
            print("A posição deve satisfazer 0 <= x <= L.")

    distributed_loads: list[DistributedLoad] = []
    n_dist = read_int("Quantidade de cargas distribuídas lineares q", default=0, min_value=0)
    for index in range(1, n_dist + 1):
        print(f"\nCarga distribuída linear {index}")
        while True:
            x1 = read_float("x1 [m]", min_value=0.0, allow_equal_min=True)
            q1 = read_float("q1 [N/m]")
            x2 = read_float("x2 [m]", min_value=0.0, allow_equal_min=True)
            q2 = read_float("q2 [N/m]")
            if not (0.0 <= x1 <= length and 0.0 <= x2 <= length):
                print("As posições devem satisfazer 0 <= x1,x2 <= L.")
                continue
            if abs(x2 - x1) < 1e-14:
                print("x1 e x2 devem ser diferentes.")
                continue
            if x2 < x1:
                x1, x2 = x2, x1
                q1, q2 = q2, q1
            distributed_loads.append(DistributedLoad(x1, q1, x2, q2))
            break

    return point_loads, distributed_loads


def read_model() -> tuple[BeamModel, bool]:
    print("=" * 72)
    print("AVALIAÇÃO 3 - ANÁLISE DE VIGAS POR DIFERENÇAS FINITAS")
    print("=" * 72)
    print("Use unidades SI coerentes: m, N, Pa.")

    length = read_float("\nComprimento L da viga [m]", min_value=0.0)
    section = read_section()
    material = read_material()
    divisions = read_int(
        "\nNúmero de divisões da malha de diferenças finitas",
        default=300,
        min_value=20,
        max_value=5000,
    )
    left_kind, right_kind, supports = read_supports(length, divisions)
    point_loads, distributed_loads = read_loads(length)
    show_plot = yes_no("\nExibir a janela do matplotlib ao final?", default=False)

    model = BeamModel(
        length=length,
        section=section,
        material=material,
        divisions=divisions,
        left_kind=left_kind,
        right_kind=right_kind,
        internal_supports=supports,
        point_loads=point_loads,
        distributed_loads=distributed_loads,
    )
    return model, show_plot


# ---------------------------------------------------------------------------
# Diferenças finitas


def finite_difference_weights(x0: float, nodes: np.ndarray, order: int) -> np.ndarray:
    if len(nodes) <= order:
        raise ValueError("A malha não possui pontos suficientes para a derivada solicitada.")
    offsets = nodes - x0
    matrix = np.vstack([offsets**k for k in range(len(nodes))])
    rhs = np.zeros(len(nodes))
    rhs[order] = math.factorial(order)
    return np.linalg.solve(matrix, rhs)


def derivative_row(x: np.ndarray, node: int, order: int, width: int = 7) -> np.ndarray:
    n = len(x)
    width = min(max(width, order + 1), n)
    start = node - width // 2
    start = max(0, min(start, n - width))
    end = start + width
    weights = finite_difference_weights(x[node], x[start:end], order)
    row = np.zeros(n)
    row[start:end] = weights
    return row


def value_row(size: int, node: int) -> np.ndarray:
    row = np.zeros(size)
    row[node] = 1.0
    return row


def assemble_load_density(model: BeamModel, x: np.ndarray) -> np.ndarray:
    q = np.zeros_like(x)
    dx = model.length / model.divisions

    for load in model.distributed_loads:
        for i, xi in enumerate(x):
            q[i] += load.value_at(float(xi))

    for load in model.point_loads:
        node = nearest_node(model.length, model.divisions, load.x)
        q[node] += load.value / dx

    return q


def add_boundary_condition(
    rows: list[np.ndarray],
    rhs: list[float],
    x: np.ndarray,
    node: int,
    kind: str,
) -> None:
    size = len(x)
    if kind == "apoio":
        rows.append(value_row(size, node))
        rhs.append(0.0)
        rows.append(derivative_row(x, node, 2))
        rhs.append(0.0)
    elif kind == "engaste":
        rows.append(value_row(size, node))
        rhs.append(0.0)
        rows.append(derivative_row(x, node, 1))
        rhs.append(0.0)
    elif kind == "livre":
        rows.append(derivative_row(x, node, 2))
        rhs.append(0.0)
        rows.append(derivative_row(x, node, 3))
        rhs.append(0.0)
    else:
        raise ValueError(f"Tipo de vínculo desconhecido: {kind}")


def choose_pde_nodes(model: BeamModel, row_count: int) -> list[int]:
    n = model.divisions
    needed = (n + 1) - row_count
    if needed < 0:
        raise ValueError(
            "Há condições de contorno demais para a malha escolhida. "
            "Aumente a malha ou reduza os vínculos."
        )

    internal_nodes = {support.node for support in model.internal_supports}
    candidates = [i for i in range(2, n - 1) if i not in internal_nodes]

    if len(candidates) > needed:
        constrained = sorted(internal_nodes) or [0, n]

        def removal_key(node: int) -> tuple[int, int]:
            return (
                min(abs(node - support_node) for support_node in constrained),
                min(node, n - node),
            )

        remove = set(sorted(candidates, key=removal_key)[: len(candidates) - needed])
        candidates = [node for node in candidates if node not in remove]

    if len(candidates) < needed:
        used = set(candidates) | internal_nodes
        extras = [i for i in range(1, n) if i not in used]
        extras.sort(key=lambda node: min(node, n - node), reverse=True)
        candidates.extend(extras[: needed - len(candidates)])

    if len(candidates) != needed:
        raise ValueError("Não foi possível montar um sistema quadrado para essa malha.")

    return sorted(candidates)


def solve_beam(model: BeamModel) -> BeamResult:
    x = np.linspace(0.0, model.length, model.divisions + 1)
    q = assemble_load_density(model, x)
    e_i = model.material.elastic_modulus * model.section.inertia

    rows: list[np.ndarray] = []
    rhs: list[float] = []
    add_boundary_condition(rows, rhs, x, 0, model.left_kind)
    add_boundary_condition(rows, rhs, x, model.divisions, model.right_kind)

    for support in model.internal_supports:
        rows.append(value_row(len(x), support.node))
        rhs.append(0.0)
        rows.append(derivative_row(x, support.node, 2))
        rhs.append(0.0)

    for node in choose_pde_nodes(model, len(rows)):
        rows.append(derivative_row(x, node, 4))
        rhs.append(q[node] / e_i)

    matrix = np.vstack(rows)
    vector = np.array(rhs, dtype=float)

    # Escala linha a linha para reduzir problemas de condicionamento.
    scale = np.maximum(np.max(np.abs(matrix), axis=1), 1.0)
    matrix_scaled = matrix / scale[:, None]
    vector_scaled = vector / scale

    warnings: list[str] = []
    condition_number = float(np.linalg.cond(matrix_scaled))
    if condition_number > 1.0e12:
        warnings.append(
            "A matriz ficou mal condicionada. Refine a malha e confira os vínculos."
        )

    try:
        w = np.linalg.solve(matrix_scaled, vector_scaled)
    except np.linalg.LinAlgError:
        w, residuals, rank, _ = np.linalg.lstsq(matrix_scaled, vector_scaled, rcond=None)
        warnings.append(
            "O sistema não teve solução direta única; foi usada solução de mínimos "
            f"quadrados. Posto numérico: {rank}."
        )
        if residuals.size:
            warnings.append(f"Resíduo quadrático: {float(residuals[0]):.6e}.")

    w_second = np.array([derivative_row(x, i, 2) @ w for i in range(len(x))])
    moment = -e_i * w_second
    shear = np.array([derivative_row(x, i, 1) @ moment for i in range(len(x))])
    sigma = np.abs(moment) * model.section.zmax / model.section.inertia
    sigma_ratio = sigma / model.material.yield_stress

    return BeamResult(
        model=model,
        x=x,
        q=q,
        w=w,
        moment=moment,
        shear=shear,
        sigma=sigma,
        sigma_ratio=sigma_ratio,
        condition_number=condition_number,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Arquivos e resumo


def save_csv(result: BeamResult, output_path: Path) -> None:
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(
            [
                "x_m",
                "q_N_por_m",
                "w_m",
                "Q_N",
                "M_Nm",
                "sigma_Pa",
                "sigma_por_sigma_y",
            ]
        )
        for values in zip(
            result.x,
            result.q,
            result.w,
            result.shear,
            result.moment,
            result.sigma,
            result.sigma_ratio,
        ):
            writer.writerow([f"{float(value):.12e}" for value in values])


def print_summary(result: BeamResult, csv_path: Path, png_path: Path, pdf_path: Path) -> None:
    model = result.model
    sec = model.section
    mat = model.material

    max_w_i = int(np.argmax(np.abs(result.w)))
    max_q_i = int(np.argmax(np.abs(result.shear)))
    max_m_i = int(np.argmax(np.abs(result.moment)))
    max_ratio_i = int(np.argmax(result.sigma_ratio))

    print("\n" + "=" * 72)
    print("RESUMO DOS RESULTADOS")
    print("=" * 72)
    print(f"Seção: {sec.name}")
    print(f"  Área A              = {format_value(sec.area, 'm²')}")
    print(f"  Inércia Iyy         = {format_value(sec.inertia, 'm^4')}")
    print(f"  zmax                = {format_value(sec.zmax, 'm')}")
    print(f"Material: {mat.name}")
    print(f"  E                   = {format_value(mat.elastic_modulus, 'Pa')}")
    print(f"  sigma_y             = {format_value(mat.yield_stress, 'Pa')}")
    print(f"Malha                 = {model.divisions} divisões")
    print(f"dx                    = {format_value(model.length / model.divisions, 'm')}")
    print(f"Condicionamento num.  = {result.condition_number:.3e}")

    print("\nExtremos numéricos:")
    print(
        f"  |w|max              = {format_value(abs(result.w[max_w_i]), 'm')} "
        f"em x={format_value(result.x[max_w_i], 'm')}"
    )
    print(
        f"  |Q|max              = {format_value(abs(result.shear[max_q_i]), 'N')} "
        f"em x={format_value(result.x[max_q_i], 'm')}"
    )
    print(
        f"  |M|max              = {format_value(abs(result.moment[max_m_i]), 'N m')} "
        f"em x={format_value(result.x[max_m_i], 'm')}"
    )
    print(
        f"  sigma_max/sigma_y   = {result.sigma_ratio[max_ratio_i]:.6g} "
        f"em x={format_value(result.x[max_ratio_i], 'm')}"
    )

    if result.sigma_ratio[max_ratio_i] > 1.0:
        print("  Atenção: há indicação de escoamento por flexão (razão > 1).")
    else:
        print("  Verificação de flexão: razão <= 1 em todos os pontos da malha.")

    if result.warnings:
        print("\nAvisos:")
        for warning in result.warnings:
            print(f"  - {warning}")

    print("\nArquivos gerados:")
    print(f"  CSV: {csv_path}")
    print(f"  PNG: {png_path}")
    print(f"  PDF: {pdf_path}")


# ---------------------------------------------------------------------------
# Plotagem em matplotlib


def require_matplotlib() -> None:
    if plt is None:
        raise RuntimeError(
            "O pacote matplotlib não está instalado neste Python. "
            "Instale com: python -m pip install matplotlib"
        )


def draw_support(ax, x_position: float, kind: str, label: str, length: float) -> None:
    if Polygon is None or Rectangle is None:
        return

    support_color = "#b91c1c"
    scale = max(length, 1.0)
    tri_w = 0.035 * scale
    tri_h = 0.26

    if kind == "apoio":
        triangle = Polygon(
            [
                [x_position, 0.0],
                [x_position - tri_w, -tri_h],
                [x_position + tri_w, -tri_h],
            ],
            closed=True,
            facecolor="none",
            edgecolor=support_color,
            linewidth=1.8,
        )
        ax.add_patch(triangle)
        ax.plot([x_position - 1.25 * tri_w, x_position + 1.25 * tri_w], [-tri_h - 0.04, -tri_h - 0.04], color=support_color, lw=1.5)
    elif kind == "engaste":
        wall_w = 0.025 * scale
        left = x_position - wall_w if x_position <= 0.5 * length else x_position
        wall = Rectangle(
            (left, -0.34),
            wall_w,
            0.68,
            facecolor="#fee2e2",
            edgecolor=support_color,
            linewidth=1.4,
            alpha=0.8,
        )
        ax.add_patch(wall)
        for y_value in np.linspace(-0.31, 0.31, 5):
            ax.plot([left, left + wall_w], [y_value - 0.05, y_value + 0.05], color=support_color, lw=0.8)
    else:
        ax.text(x_position, -0.30, "livre", ha="center", va="top", color="#6b7280", fontsize=9)

    ax.text(x_position, -0.50, label, ha="center", va="top", fontsize=9)


def draw_arrow(ax, x_position: float, value: float, y_tip: float, max_abs: float, label: str) -> None:
    if abs(value) < 1e-14:
        return
    length = 0.22 + 0.52 * abs(value) / max_abs
    if value > 0.0:
        y_tail = y_tip + length
        va = "bottom"
        text_y = y_tail + 0.03
    else:
        y_tail = y_tip - length
        va = "top"
        text_y = y_tail - 0.03

    ax.annotate(
        "",
        xy=(x_position, y_tip),
        xytext=(x_position, y_tail),
        arrowprops=dict(arrowstyle="-|>", color="#dc2626", lw=1.4),
    )
    ax.text(x_position, text_y, label, ha="center", va=va, color="#991b1b", fontsize=8)


def draw_beam_schema(ax, result: BeamResult) -> None:
    model = result.model
    length = model.length
    ax.set_title("Carregamento e vinculações", loc="left", fontweight="bold")
    ax.plot([0.0, length], [0.0, 0.0], color="#111827", lw=4.0, solid_capstyle="butt")
    ax.set_xlim(-0.06 * length, 1.06 * length)
    ax.set_ylim(-0.72, 1.08)
    ax.set_yticks([])
    ax.set_ylabel("modelo")
    ax.grid(False)

    draw_support(ax, 0.0, model.left_kind, "x=0", length)
    draw_support(ax, length, model.right_kind, "x=L", length)
    for support in model.internal_supports:
        draw_support(ax, support.x, support.kind, f"x={support.x:.3g}", length)

    max_p = max([abs(load.value) for load in model.point_loads] + [1.0])
    for load in model.point_loads:
        draw_arrow(ax, load.x, load.value, 0.04 if load.value > 0.0 else -0.04, max_p, f"P={load.value:.3g}")

    max_q = max(
        [abs(load.q1) for load in model.distributed_loads]
        + [abs(load.q2) for load in model.distributed_loads]
        + [1.0]
    )
    for load in model.distributed_loads:
        samples = np.linspace(load.x1, load.x2, 9)
        tail_points_x: list[float] = []
        tail_points_y: list[float] = []
        for xi in samples:
            qi = load.value_at(float(xi))
            if abs(qi) < 1e-14:
                continue
            length_arrow = 0.22 + 0.44 * abs(qi) / max_q
            if qi > 0.0:
                y_tip = 0.04
                y_tail = y_tip + length_arrow
            else:
                y_tip = -0.04
                y_tail = y_tip - length_arrow
            ax.annotate(
                "",
                xy=(float(xi), y_tip),
                xytext=(float(xi), y_tail),
                arrowprops=dict(arrowstyle="-|>", color="#ef4444", lw=1.0),
            )
            tail_points_x.append(float(xi))
            tail_points_y.append(y_tail)
        if tail_points_x:
            ax.plot(tail_points_x, tail_points_y, color="#ef4444", lw=1.0)
            ax.text(
                load.x1 + 0.12 * (load.x2 - load.x1),
                max(tail_points_y) + 0.05,
                f"q: {load.q1:.3g} a {load.q2:.3g} N/m",
                ha="left",
                va="bottom",
                fontsize=8,
                color="#991b1b",
            )


def configure_result_axis(ax, title: str, ylabel: str) -> None:
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.axhline(0.0, color="#6b7280", lw=0.9)
    ax.grid(True, color="#d1d5db", linewidth=0.6, alpha=0.7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def save_matplotlib_plot(result: BeamResult, png_path: Path, pdf_path: Path, show: bool = False) -> None:
    require_matplotlib()

    x = result.x
    fig, axes = plt.subplots(
        5,
        1,
        figsize=(12.0, 14.0),
        sharex=True,
        constrained_layout=True,
        gridspec_kw={"height_ratios": [1.2, 1.0, 1.0, 1.0, 1.0]},
    )
    fig.suptitle(
        "Avaliação 3 - Análise de Viga por Diferenças Finitas",
        fontsize=16,
        fontweight="bold",
    )

    draw_beam_schema(axes[0], result)

    axes[1].plot(x, result.shear, color="#0ea5e9", lw=1.9)
    configure_result_axis(axes[1], "Esforço cortante Q(x)", "Q [N]")

    axes[2].plot(x, result.moment, color="#16a34a", lw=1.9)
    configure_result_axis(axes[2], "Momento fletor M(x)", "M [N m]")

    axes[3].plot(x, result.w, color="#7c3aed", lw=1.9)
    configure_result_axis(axes[3], "Deslocamento w(x)", "w [m]")

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
    configure_result_axis(axes[4], "Razão sigma_max/sigma_y", "[-]")
    axes[4].set_xlabel("x [m]")

    for ax in axes[1:]:
        ymin, ymax = ax.get_ylim()
        if abs(ymax - ymin) < 1e-14:
            ax.set_ylim(ymin - 1.0, ymax + 1.0)

    fig.savefig(png_path, dpi=220)
    fig.savefig(pdf_path)
    if show:
        plt.show()
    else:
        plt.close(fig)


# ---------------------------------------------------------------------------
# Execução


def create_example_model() -> BeamModel:
    section = Section(
        name="Retangular",
        area=0.20 * 0.40,
        inertia=0.20 * 0.40**3 / 12.0,
        zmax=0.40 / 2.0,
        details={"b": 0.20, "h": 0.40},
    )
    material = Material("Aço estrutural", 200.0e9, 250.0e6)
    return BeamModel(
        length=6.0,
        section=section,
        material=material,
        divisions=300,
        left_kind="apoio",
        right_kind="apoio",
        point_loads=[PointLoad(10.0e3, 3.0)],
        distributed_loads=[DistributedLoad(0.0, 4.0e3, 6.0, 4.0e3)],
    )


def run(model: BeamModel, *, show_plot: bool = False) -> BeamResult:
    result = solve_beam(model)
    base = script_dir()
    csv_path = base / "resultados_viga.csv"
    png_path = base / "resultado_viga.png"
    pdf_path = base / "resultado_viga.pdf"
    save_csv(result, csv_path)
    save_matplotlib_plot(result, png_path, pdf_path, show=show_plot)
    print_summary(result, csv_path, png_path, pdf_path)
    return result


def main() -> None:
    if "--exemplo" in sys.argv:
        print("Rodando exemplo automático de viga biapoiada.")
        show_plot = "--mostrar" in sys.argv
        run(create_example_model(), show_plot=show_plot)
        return

    try:
        model, show_plot = read_model()
        run(model, show_plot=show_plot)
        if yes_no("\nDeseja analisar outra viga?", default=False):
            print()
            main()
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo usuário.")
    except Exception as exc:
        print("\nErro durante a análise:")
        print(f"  {exc}")
        print("\nConfira os dados de entrada, a malha, os vínculos e as dependências.")


if __name__ == "__main__":
    main()

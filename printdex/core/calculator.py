"""Calculadora de custo e preço de impressões 3D (sem interface).

Modo simples: material + energia + margem.
Modo avançado: soma também máquina, trabalho manual e risco de falha, e
multiplica pela quantidade.
"""

import math
from dataclasses import dataclass

# Código -> (símbolo, separador decimal, separador de milhar)
CURRENCIES = {
    "BRL": ("R$", ",", "."),
    "USD": ("$", ".", ","),
    "EUR": ("€", ",", "."),
    "CNY": ("¥", ".", ","),
}
DEFAULT_CURRENCY = "BRL"


def currency_symbol(code: str) -> str:
    return CURRENCIES.get(code, CURRENCIES[DEFAULT_CURRENCY])[0]


def format_money(value: float, code: str) -> str:
    """13.58 -> "R$ 13,58" / "$ 13.58" / "€ 13,58" / "¥ 13.58" (com milhar)."""
    symbol, decimal, thousands = CURRENCIES.get(code, CURRENCIES[DEFAULT_CURRENCY])
    text = f"{value:,.2f}".translate(str.maketrans({",": thousands, ".": decimal}))
    return f"{symbol} {text}"


def parse_number(text: str) -> float | None:
    """Lê o que o usuário digitou: "2,5", "2.5", "1.234,50", "1,234.50".

    Vazio vale 0. Retorna None se não for um número válido e não negativo.
    """
    text = text.strip().replace(" ", "")
    if not text:
        return 0.0
    if "," in text and "." in text:
        # O separador que aparece por último é o decimal
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    else:
        text = text.replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


@dataclass(frozen=True)
class SimpleResult:
    material: float
    energy: float
    total: float   # custo total = material + energia
    profit: float
    price: float   # preço sugerido = total + lucro


def simple(price_kg: float, weight_g: float, hours: float,
           tariff: float, power_w: float, margin: float) -> SimpleResult:
    material = price_kg / 1000 * weight_g
    energy = power_w / 1000 * hours * tariff
    total = material + energy
    profit = total * margin / 100
    return SimpleResult(material, energy, total, profit, total + profit)


@dataclass(frozen=True)
class AdvancedResult:
    material: float
    energy: float
    machine: float
    labor: float
    failure: float
    unit_cost: float     # custo base + falha
    unit_profit: float
    final_price: float   # (custo unitário + lucro unitário) * quantidade
    quantity: float
    total_hours: float   # (impressão + trabalho manual) * quantidade

    def shares(self) -> dict[str, float]:
        """Fração de cada parte no custo unitário (0 a 1), para as barras."""
        parts = {"material": self.material, "energy": self.energy,
                 "machine": self.machine, "labor": self.labor, "failure": self.failure}
        if self.unit_cost <= 0:
            return dict.fromkeys(parts, 0.0)
        return {name: value / self.unit_cost for name, value in parts.items()}


def advanced(weight_g: float, price_kg: float, hours: float, power_w: float,
             tariff: float, machine_price: float, lifetime_h: float,
             labor_rate: float, labor_hours: float, quantity: float,
             margin: float, risk: float) -> AdvancedResult:
    material = price_kg / 1000 * weight_g
    energy = power_w / 1000 * hours * tariff
    # Vida útil vazia ou zero: sem depreciação (evita dividir por zero)
    machine = machine_price / lifetime_h * hours if lifetime_h > 0 else 0.0
    labor = labor_rate * labor_hours
    base = material + energy + machine + labor
    failure = base * risk / 100
    unit_cost = base + failure
    unit_profit = unit_cost * margin / 100
    return AdvancedResult(
        material=material, energy=energy, machine=machine, labor=labor,
        failure=failure, unit_cost=unit_cost, unit_profit=unit_profit,
        final_price=(unit_cost + unit_profit) * quantity, quantity=quantity,
        total_hours=(hours + labor_hours) * quantity,
    )

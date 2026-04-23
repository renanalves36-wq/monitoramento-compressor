"""Calculos de vazao estimada do compressor TA6000."""

from __future__ import annotations


NORMAL_REFERENCE_TEMPERATURE_K = 273.15


def calculate_vapor_partial_pressure_kpa(
    relative_humidity_pct: float,
    saturation_vapor_pressure_kpa: float,
) -> float:
    """Calcula a pressao parcial de vapor na succao."""

    return (relative_humidity_pct / 100.0) * saturation_vapor_pressure_kpa


def calculate_dry_air_partial_pressure_kpa(
    atmospheric_pressure_kpa: float,
    vapor_partial_pressure_kpa: float,
) -> float:
    """Calcula a pressao parcial do ar seco."""

    return atmospheric_pressure_kpa - vapor_partial_pressure_kpa


def calculate_current_to_normal_factor(
    *,
    dry_air_partial_pressure_kpa: float,
    atmospheric_pressure_kpa: float,
    suction_temperature_c: float,
) -> float:
    """Fator para converter vazao atual de succao para Nm3/h."""

    suction_temperature_k = suction_temperature_c + NORMAL_REFERENCE_TEMPERATURE_K
    return (
        dry_air_partial_pressure_kpa / atmospheric_pressure_kpa
    ) * (NORMAL_REFERENCE_TEMPERATURE_K / suction_temperature_k)


def calculate_qn_m3h(
    *,
    current_a: float | None,
    no_load_current_a: float,
    nominal_current_a: float,
    nominal_flow_nm3h: float,
) -> float | None:
    """Estima vazao normalizada por proporcionalidade com corrente."""

    if current_a is None:
        return None
    denominator = nominal_current_a - no_load_current_a
    if denominator <= 0:
        raise ValueError("A corrente nominal deve ser maior que a corrente sem carga.")

    qn_m3h = nominal_flow_nm3h * ((current_a - no_load_current_a) / denominator)
    return min(nominal_flow_nm3h, max(0.0, qn_m3h))


def calculate_qa_m3h(
    *,
    qn_m3h: float | None,
    current_to_normal_factor: float,
) -> float | None:
    """Converte Qn para volume equivalente na succao.

    Essa grandeza pode ser maior que a vazao nominal normalizada por efeito de
    temperatura/umidade. Ela nao deve ser usada como limite de capacidade util.
    """

    if qn_m3h is None:
        return None
    if current_to_normal_factor <= 0:
        raise ValueError("O fator de conversao de vazao deve ser maior que zero.")
    return qn_m3h / current_to_normal_factor


def calculate_flow_loss_m3h(
    *,
    qn_m3h: float | None,
    nominal_flow_nm3h: float,
) -> float | None:
    """Calcula perda estimada de capacidade frente a vazao nominal."""

    if qn_m3h is None:
        return None
    if nominal_flow_nm3h <= 0:
        raise ValueError("A vazao nominal deve ser maior que zero.")
    effective_qn = min(nominal_flow_nm3h, max(0.0, qn_m3h))
    return max(0.0, nominal_flow_nm3h - effective_qn)


def calculate_flow_utilization_pct(
    *,
    qn_m3h: float | None,
    nominal_flow_nm3h: float,
) -> float | None:
    """Calcula utilizacao da capacidade nominal em percentual."""

    if qn_m3h is None:
        return None
    if nominal_flow_nm3h <= 0:
        raise ValueError("A vazao nominal deve ser maior que zero.")
    effective_qn = min(nominal_flow_nm3h, max(0.0, qn_m3h))
    return (effective_qn / nominal_flow_nm3h) * 100.0

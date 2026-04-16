"""Motor explicavel de influencia da vazao normalizada Qn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.domain.analysis_schemas import (
    AnalysisDataWindow,
    AnalysisQualityFlag,
    InfluenceItem,
    LossOriginClassification,
    ModelQuality,
    QnInfluenceAnalysisResponse,
    QnInfluenceHistoryPoint,
    QnInfluenceHistoryResponse,
)
from app.domain.mappings import SUBSYSTEM_SIGNALS, get_signal_label, get_signal_unit
from app.utils.datetime_utils import utc_now


TARGET_QN = "qn_m3h"
EXPECTED_QN = "qn_esperada_m3h"
DELTA_Q = "delta_q_m3h"

NORMAL_ST_OPER = "EM FUNCIONAMENTO"
NORMAL_ST_CARGA = "CARREGADO"
TRANSITION_STATES = {
    "PARTINDO",
    "PARANDO",
    "DESACELERANDO",
    "INICIALIZANDO PARTIDA",
}

DIRECT_QN_FEATURES = [
    "pv_pos_abert_valv_admissao_pct",
    "pv_pos_valv_bypass_pct",
    "pv_pos_alivio_pct",
    "pv_pres_descarga_bar",
    "pv_pres_sistema_bar",
]

DEGRADATION_FEATURES = [
    "pv_temp_oleo_lubrificacao_c",
    "pv_pres_oleo_bar",
    "pv_vib_estagio_1_mils",
    "pv_vib_estagio_2_mils",
    "pv_vib_estagio_3_mils",
    "pv_temp_fase_a_do_estator_c",
    "pv_temp_fase_b_do_estator_c",
    "pv_temp_fase_c_do_estator_c",
    "pv_temp_rolamento_dianteiro_motor",
    "pv_temp_ar_estagio_3_c",
]

PROCESS_FEATURES = {"pv_pres_descarga_bar", "pv_pres_sistema_bar"}
CONTROL_FEATURES = {
    "pv_pos_abert_valv_admissao_pct",
    "pv_pos_valv_bypass_pct",
    "pv_pos_alivio_pct",
}

# Direcoes fisicas esperadas no modelo direto. Quando o ajuste encontra um sinal
# oposto ao esperado, a classificacao reduz a confianca nessa explicacao direta.
EXPECTED_DIRECT_SIGNS = {
    "pv_pos_abert_valv_admissao_pct": "positivo",
    "pv_pos_valv_bypass_pct": "negativo",
    "pv_pos_alivio_pct": "negativo",
    "pv_pres_descarga_bar": "negativo",
    "pv_pres_sistema_bar": "negativo",
}

DEGRADATION_ADVERSE_DIRECTIONS = {
    "pv_temp_oleo_lubrificacao_c": "high",
    "pv_pres_oleo_bar": "low",
    "pv_vib_estagio_1_mils": "high",
    "pv_vib_estagio_2_mils": "high",
    "pv_vib_estagio_3_mils": "high",
    "pv_temp_fase_a_do_estator_c": "high",
    "pv_temp_fase_b_do_estator_c": "high",
    "pv_temp_fase_c_do_estator_c": "high",
    "pv_temp_rolamento_dianteiro_motor": "high",
    "pv_temp_ar_estagio_3_c": "high",
}

MIN_ANALYSIS_POINTS = 30
MIN_MODEL_POINTS = 20


@dataclass(slots=True)
class PreparedAnalysisDataset:
    frame: pd.DataFrame
    data_window: AnalysisDataWindow
    quality_flags: list[AnalysisQualityFlag]


@dataclass(slots=True)
class LinearInfluenceModel:
    target: str
    features: list[str]
    intercept: float | None
    coefficients: dict[str, float]
    standardized_coefficients: dict[str, float]
    r2: float | None
    mae: float | None
    n_points: int
    removed_features: list[str]
    observations: list[str]

    @property
    def is_fitted(self) -> bool:
        return self.intercept is not None


class AnalysisEngine:
    """Facade pequena para uso pelo HealthService e pelas rotas."""

    def build_analysis_payload(
        self,
        frame: pd.DataFrame,
        *,
        range_value: int,
        range_unit: str,
    ) -> QnInfluenceAnalysisResponse:
        response, _analysis_frame = _run_analysis(
            frame=frame,
            range_value=range_value,
            range_unit=range_unit,
        )
        return response

    def build_history_payload(
        self,
        frame: pd.DataFrame,
        *,
        range_value: int,
        range_unit: str,
        max_points: int = 240,
    ) -> QnInfluenceHistoryResponse:
        response, analysis_frame = _run_analysis(
            frame=frame,
            range_value=range_value,
            range_unit=range_unit,
        )
        points = _build_history_points(analysis_frame, max_points=max_points)
        return QnInfluenceHistoryResponse(
            generated_at=utc_now(),
            range_value=range_value,
            range_unit=range_unit,
            analysis=response,
            points=points,
        )


def prepare_analysis_dataset(df: pd.DataFrame) -> PreparedAnalysisDataset:
    """Prepara o conjunto principal EM FUNCIONAMENTO|CARREGADO para analise."""

    quality_flags: list[AnalysisQualityFlag] = []
    if df.empty:
        return PreparedAnalysisDataset(
            frame=pd.DataFrame(),
            data_window=AnalysisDataWindow(),
            quality_flags=[
                AnalysisQualityFlag(
                    code="empty_dataset",
                    severity="critical",
                    message="Nao ha dados disponiveis para a analise de Qn.",
                )
            ],
        )

    raw_rows = int(len(df))
    clean = df.copy()
    if "timestamp" not in clean.columns:
        return PreparedAnalysisDataset(
            frame=pd.DataFrame(),
            data_window=AnalysisDataWindow(raw_rows=raw_rows),
            quality_flags=[
                AnalysisQualityFlag(
                    code="missing_timestamp",
                    severity="critical",
                    message="A coluna timestamp e obrigatoria para a analise temporal.",
                )
            ],
        )

    clean["timestamp"] = pd.to_datetime(clean["timestamp"], errors="coerce")
    invalid_ts = int(clean["timestamp"].isna().sum())
    if invalid_ts:
        quality_flags.append(
            AnalysisQualityFlag(
                code="invalid_timestamp",
                severity="warning",
                message="Algumas linhas foram descartadas por timestamp invalido.",
                details={"count": invalid_ts},
            )
        )
    clean = clean.dropna(subset=["timestamp"]).sort_values("timestamp")

    duplicate_count = int(clean.duplicated(subset=["timestamp"], keep="last").sum())
    if duplicate_count:
        quality_flags.append(
            AnalysisQualityFlag(
                code="duplicate_timestamp",
                severity="info",
                message="Timestamps duplicados foram consolidados para a analise.",
                details={"count": duplicate_count},
            )
        )
        clean = clean.drop_duplicates(subset=["timestamp"], keep="last")

    for column in [TARGET_QN, *DIRECT_QN_FEATURES, *DEGRADATION_FEATURES, "pv_corr_motor_a"]:
        if column in clean.columns:
            clean[column] = pd.to_numeric(clean[column], errors="coerce")

    transition_count = _count_transition_rows(clean)
    if transition_count:
        quality_flags.append(
            AnalysisQualityFlag(
                code="transition_rows_excluded",
                severity="info",
                message="Pontos em partida, parada ou desaceleracao foram excluidos do modelo principal.",
                details={"count": transition_count},
            )
        )
    no_transition = clean[~_transition_mask(clean)].copy()
    st_oper = no_transition.get("st_oper", pd.Series(index=no_transition.index, dtype="object"))
    st_carga = no_transition.get("st_carga_oper", pd.Series(index=no_transition.index, dtype="object"))
    normal_mask = st_oper.astype("string").eq(NORMAL_ST_OPER) & st_carga.astype("string").eq(NORMAL_ST_CARGA)
    normal = no_transition[normal_mask].copy()
    if normal.empty:
        quality_flags.append(
            AnalysisQualityFlag(
                code="no_normal_operation_rows",
                severity="critical",
                message="Nao ha pontos EM FUNCIONAMENTO|CARREGADO suficientes para o modelo principal.",
            )
        )

    analysis_frame = normal.dropna(subset=[TARGET_QN]).copy() if TARGET_QN in normal.columns else pd.DataFrame()
    if TARGET_QN not in normal.columns:
        quality_flags.append(
            AnalysisQualityFlag(
                code="target_unavailable",
                severity="critical",
                message="A coluna qn_m3h nao esta disponivel. A analise de influencia da Qn nao pode ser ajustada.",
                signal=TARGET_QN,
            )
        )
    else:
        missing_qn = int(normal[TARGET_QN].isna().sum())
        if missing_qn:
            quality_flags.append(
                AnalysisQualityFlag(
                    code="target_nulls",
                    severity="warning",
                    message="Alguns pontos sem Qn foram removidos da analise.",
                    signal=TARGET_QN,
                    details={"count": missing_qn},
                )
            )

    if len(analysis_frame) < MIN_ANALYSIS_POINTS:
        quality_flags.append(
            AnalysisQualityFlag(
                code="low_valid_points",
                severity="critical",
                message="Poucos pontos validos para uma leitura confiavel de influencia.",
                details={"valid_rows": int(len(analysis_frame)), "minimum": MIN_ANALYSIS_POINTS},
            )
        )

    quality_flags.extend(_collect_analysis_quality_flags(analysis_frame))

    if not clean.empty:
        start_ts = pd.to_datetime(clean["timestamp"].min()).to_pydatetime()
        end_ts = pd.to_datetime(clean["timestamp"].max()).to_pydatetime()
    else:
        start_ts = None
        end_ts = None

    data_window = AnalysisDataWindow(
        start_timestamp=start_ts,
        end_timestamp=end_ts,
        raw_rows=raw_rows,
        valid_rows=int(len(analysis_frame)),
        normal_operation_rows=int(len(normal)),
        excluded_transition_rows=transition_count,
    )
    return PreparedAnalysisDataset(
        frame=analysis_frame.reset_index(drop=True),
        data_window=data_window,
        quality_flags=quality_flags,
    )


def fit_qn_influence_model(df: pd.DataFrame) -> LinearInfluenceModel:
    """Ajusta Qn contra variaveis de processo/controle, sem usar corrente."""

    remaining_features = DIRECT_QN_FEATURES.copy()
    removed_by_sign: list[str] = []
    model = _fit_linear_model(
        df=df,
        target=TARGET_QN,
        features=remaining_features,
        min_points=MIN_MODEL_POINTS,
    )
    for _attempt in range(len(DIRECT_QN_FEATURES)):
        inconsistent_features = [
            feature
            for feature in model.features
            if _is_direct_sign_inconsistent(
                feature,
                model.standardized_coefficients.get(feature),
            )
            and abs(model.standardized_coefficients.get(feature, 0.0)) >= 0.005
        ]
        if not inconsistent_features:
            break

        removed_by_sign.extend(
            feature for feature in inconsistent_features if feature not in removed_by_sign
        )
        remaining_features = [
            feature for feature in remaining_features if feature not in inconsistent_features
        ]
        if not remaining_features:
            model = _fit_intercept_only_model(
                df=df,
                target=TARGET_QN,
                removed_features=[*model.removed_features, *removed_by_sign],
                observations=[
                    *model.observations,
                    "modelo direto reduzido a linha-base porque as variaveis de processo/controle ficaram fisicamente incoerentes.",
                ],
            )
            break
        model = _fit_linear_model(
            df=df,
            target=TARGET_QN,
            features=remaining_features,
            min_points=MIN_MODEL_POINTS,
        )

    if removed_by_sign:
        model.removed_features = [
            *model.removed_features,
            *[feature for feature in removed_by_sign if feature not in model.removed_features],
        ]
        model.observations = [
            *model.observations,
            *[
                f"{feature} removida do modelo direto por sinal fisico incoerente."
                for feature in removed_by_sign
            ],
        ]
    return model


def get_standardized_influence_scores(
    model: LinearInfluenceModel,
    feature_names: list[str] | None = None,
    *,
    influence_type: str = "direta",
) -> list[InfluenceItem]:
    """Converte coeficientes padronizados em ranking de influencia 0..1."""

    features = feature_names or model.features
    coefficients = {
        feature: model.standardized_coefficients.get(feature, 0.0)
        for feature in features
        if feature in model.standardized_coefficients
    }
    total_abs = sum(abs(value) for value in coefficients.values())
    if total_abs <= 0:
        return []

    items: list[InfluenceItem] = []
    for feature, standardized_coef in coefficients.items():
        influence = abs(standardized_coef) / total_abs
        if influence < 0.005:
            continue
        signal = "positivo" if standardized_coef >= 0 else "negativo"
        raw_coef = model.coefficients.get(feature)
        items.append(
            InfluenceItem(
                variavel=feature,
                label=get_signal_label(feature),
                unidade=get_signal_unit(feature),
                subsistema=_infer_subsystem(feature),
                influencia=round(float(influence), 4),
                sinal=signal,
                tipo=influence_type,
                coeficiente=None if raw_coef is None else round(float(raw_coef), 6),
                coeficiente_padronizado=round(float(standardized_coef), 6),
                interpretacao_curta=_build_influence_interpretation(
                    feature=feature,
                    signal=signal,
                    influence_type=influence_type,
                ),
            )
        )
    return sorted(items, key=lambda item: item.influencia, reverse=True)


def summarize_qn_influence(model: LinearInfluenceModel) -> list[InfluenceItem]:
    return get_standardized_influence_scores(
        model,
        model.features,
        influence_type="direta",
    )


def calculate_expected_qn(df: pd.DataFrame, model: LinearInfluenceModel) -> pd.Series:
    """Calcula Qn esperada pelo modelo de processo/controle."""

    if df.empty or not model.is_fitted:
        return pd.Series(np.nan, index=df.index, dtype=float)
    if any(feature not in df.columns for feature in model.features):
        return pd.Series(np.nan, index=df.index, dtype=float)
    if not model.features:
        return pd.Series(float(model.intercept), index=df.index, dtype=float)

    x = df.loc[:, model.features].apply(pd.to_numeric, errors="coerce")
    expected = pd.Series(float(model.intercept), index=df.index, dtype=float)
    for feature in model.features:
        expected = expected + x[feature] * model.coefficients.get(feature, 0.0)
    expected[x.isna().any(axis=1)] = np.nan
    return expected


def calculate_delta_q(df: pd.DataFrame) -> pd.Series:
    """Calcula desvio real menos esperado. Delta negativo indica perda residual."""

    if TARGET_QN not in df.columns or EXPECTED_QN not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    qn = pd.to_numeric(df[TARGET_QN], errors="coerce")
    expected = pd.to_numeric(df[EXPECTED_QN], errors="coerce")
    return qn - expected


def fit_performance_loss_model(df: pd.DataFrame) -> LinearInfluenceModel:
    """Ajusta o desvio de Qn contra variaveis termicas e mecanicas."""

    return _fit_linear_model(
        df=df,
        target=DELTA_Q,
        features=DEGRADATION_FEATURES,
        min_points=MIN_MODEL_POINTS,
    )


def summarize_performance_loss(model: LinearInfluenceModel) -> list[InfluenceItem]:
    return get_standardized_influence_scores(
        model,
        model.features,
        influence_type="indireta",
    )


def classify_loss_origin(
    qn_influence_summary: list[InfluenceItem],
    delta_q_summary: list[InfluenceItem],
    context_flags: dict[str, Any],
) -> LossOriginClassification:
    """Classifica a origem provavel da perda com regras simples e auditaveis."""

    valid_points = int(context_flags.get("valid_points", 0))
    direct_r2 = float(context_flags.get("direct_r2") or 0.0)
    loss_r2 = float(context_flags.get("loss_r2") or 0.0)
    delta_q_current = context_flags.get("delta_q_current")
    serious_quality_count = int(context_flags.get("serious_quality_count", 0))
    internal_physical_strength = float(context_flags.get("internal_degradation_strength") or 0.0)
    direct_sign_issue_score = float(context_flags.get("direct_sign_issue_score") or 0.0)
    direct_physical_reliability = max(0.15, 1.0 - direct_sign_issue_score)
    internal_context_variables = [
        str(variable) for variable in context_flags.get("internal_degradation_variables", [])
    ]

    if valid_points < MIN_ANALYSIS_POINTS or serious_quality_count >= 2:
        return LossOriginClassification(
            classificacao="baixa_confianca",
            confianca=0.25,
            explicacao_curta=(
                "A base tem poucos pontos confiaveis ou sinais suspeitos demais para separar "
                "processo, controle e degradacao com seguranca."
            ),
            variaveis_dominantes=[],
            recomendacao_analitica=(
                "Validar qualidade dos dados e repetir a analise com mais pontos em operacao carregada."
            ),
        )

    process_share = sum(
        item.influencia for item in qn_influence_summary if item.variavel in PROCESS_FEATURES
    )
    control_share = sum(
        item.influencia for item in qn_influence_summary if item.variavel in CONTROL_FEATURES
    )
    indirect_negative_share = sum(
        item.influencia for item in delta_q_summary if item.sinal == "negativo"
    )

    direct_evidence = (
        direct_r2 >= 0.30
        and bool(qn_influence_summary)
        and direct_physical_reliability >= 0.35
    )
    internal_evidence = (
        (
            loss_r2 >= 0.30
            and indirect_negative_share >= 0.35
        )
        or internal_physical_strength >= 0.55
    ) and _is_negative_or_unknown_delta(delta_q_current)

    direct_strength = direct_r2 * max(process_share + control_share, 0.1) * direct_physical_reliability
    residual_internal_strength = loss_r2 * max(indirect_negative_share, 0.1)
    internal_strength = max(residual_internal_strength, internal_physical_strength)
    variables = _merge_variables(
        _dominant_variables(qn_influence_summary, delta_q_summary),
        internal_context_variables,
    )

    if direct_evidence and internal_evidence:
        if internal_strength > direct_strength * 1.45 or (
            direct_sign_issue_score >= 0.45 and internal_strength >= 0.65
        ):
            return _classification(
                "dominancia_degradacao_interna",
                valid_points,
                max(loss_r2, internal_strength),
                "A perda residual de Qn e mais explicada por sinais termicos ou mecanicos do compressor.",
                variables,
                "Priorizar investigacao de vibracao, oleo, temperaturas de estator/rolamento e tendencia de degradacao.",
            )
        if loss_r2 >= 0.30 and indirect_negative_share >= 0.50:
            return _classification(
                "dominancia_mista",
                valid_points,
                max(direct_r2, loss_r2),
                "A Qn combina uma parcela explicada por processo/rede com perda residual ligada a variaveis internas.",
                variables,
                "Tratar em paralelo a contrapressao/controle e a tendencia mecanica ou termica indicada no desvio de performance.",
            )
        if direct_strength > internal_strength * 1.75:
            return _classify_direct_dominance(
                valid_points=valid_points,
                direct_r2=direct_r2,
                process_share=process_share,
                control_share=control_share,
                variables=variables,
            )
        return _classification(
            "dominancia_mista",
            valid_points,
            max(direct_r2, loss_r2),
            "A Qn combina efeito de processo/rede/controle com sinais internos de degradacao.",
            variables,
            "Separar a investigacao em duas frentes: restricao/controle de ar e condicao mecanica/termica.",
        )

    if internal_evidence:
        return _classification(
            "dominancia_degradacao_interna",
            valid_points,
            loss_r2,
            "A parte da perda de Qn que o processo nao explica esta associada a variaveis internas.",
            variables,
            "Focar em tendencia de vibracao, temperatura de oleo, pressoes de oleo e temperaturas do motor.",
        )

    if direct_evidence:
        return _classify_direct_dominance(
            valid_points=valid_points,
            direct_r2=direct_r2,
            process_share=process_share,
            control_share=control_share,
            variables=variables,
        )

    return LossOriginClassification(
        classificacao="baixa_confianca",
        confianca=0.35,
        explicacao_curta=(
            "Os modelos nao encontraram relacao estatistica forte o bastante para classificar a origem da perda."
        ),
        variaveis_dominantes=variables[:3],
        recomendacao_analitica=(
            "Acompanhar por uma janela maior e confirmar se a Qn varia de forma coerente com processo e controle."
        ),
    )


def build_analysis_payload(
    df: pd.DataFrame,
    *,
    range_value: int = 24,
    range_unit: str = "hours",
) -> QnInfluenceAnalysisResponse:
    response, _analysis_frame = _run_analysis(
        frame=df,
        range_value=range_value,
        range_unit=range_unit,
    )
    return response


def generate_analysis_summary(
    classification: LossOriginClassification,
    direct_items: list[InfluenceItem],
    indirect_items: list[InfluenceItem],
) -> str:
    """Gera frase curta e legivel para o dashboard."""

    top_direct = direct_items[0] if direct_items else None
    top_indirect = indirect_items[0] if indirect_items else None
    if classification.classificacao == "dominancia_processo_rede":
        return (
            f"A vazao Qn esta sendo principalmente limitada por {top_direct.label if top_direct else 'processo/rede'}. "
            "As variaveis internas aparecem como efeito secundario nesta janela."
        )
    if classification.classificacao == "dominancia_controle":
        return (
            f"A Qn esta mais sensivel ao controle, especialmente {top_direct.label if top_direct else 'atuadores'}. "
            "Verifique admissao, bypass, alivio e a logica de carga."
        )
    if classification.classificacao == "dominancia_degradacao_interna":
        return (
            f"A perda de Qn nao e explicada apenas pelo processo; {top_indirect.label if top_indirect else 'variaveis internas'} "
            "tem influencia relevante no desvio de performance."
        )
    if classification.classificacao == "dominancia_mista":
        direct_label = top_direct.label if top_direct else "processo/controle"
        indirect_label = top_indirect.label if top_indirect else "condicao interna"
        return (
            f"A perda de Qn tem origem mista: {direct_label} explica parte do comportamento e "
            f"{indirect_label} explica parte da perda residual."
        )
    return "A analise ainda nao tem confianca suficiente; valide qualidade dos dados e amplie a janela operacional."


def _run_analysis(
    *,
    frame: pd.DataFrame,
    range_value: int,
    range_unit: str,
) -> tuple[QnInfluenceAnalysisResponse, pd.DataFrame]:
    prepared = prepare_analysis_dataset(frame)
    analysis_frame = prepared.frame.copy()

    direct_model = fit_qn_influence_model(analysis_frame)
    analysis_frame[EXPECTED_QN] = calculate_expected_qn(analysis_frame, direct_model)
    analysis_frame[DELTA_Q] = calculate_delta_q(analysis_frame)
    loss_model = fit_performance_loss_model(analysis_frame)

    direct_items = summarize_qn_influence(direct_model)
    indirect_items = summarize_performance_loss(loss_model)
    latest = analysis_frame.iloc[-1] if not analysis_frame.empty else None

    qn_current = _safe_float(None if latest is None else latest.get(TARGET_QN))
    qn_expected = _safe_float(None if latest is None else latest.get(EXPECTED_QN))
    delta_q = _safe_float(None if latest is None else latest.get(DELTA_Q))
    delta_q_pct = (
        None
        if qn_expected is None or qn_expected == 0 or delta_q is None
        else round((delta_q / qn_expected) * 100.0, 3)
    )

    context_flags = _build_classification_context(
        prepared=prepared,
        direct_model=direct_model,
        loss_model=loss_model,
        delta_q_current=delta_q,
    )
    classification = classify_loss_origin(direct_items, indirect_items, context_flags)
    summary = generate_analysis_summary(classification, direct_items, indirect_items)

    response = QnInfluenceAnalysisResponse(
        generated_at=utc_now(),
        range_value=range_value,
        range_unit=range_unit,
        data_window=prepared.data_window,
        contexto_operacional=_build_operational_context(latest),
        qn_atual=None if qn_current is None else round(qn_current, 3),
        qn_esperada=None if qn_expected is None else round(qn_expected, 3),
        delta_q=None if delta_q is None else round(delta_q, 3),
        delta_q_percentual=delta_q_pct,
        influencia_direta=direct_items,
        influencia_indireta=indirect_items,
        qualidade_modelo_direto=_model_quality(direct_model),
        qualidade_modelo_desvio=_model_quality(loss_model),
        classificacao_origem=classification,
        resumo_textual=summary,
        qualidade_dados=prepared.quality_flags,
    )
    return response, analysis_frame


def _fit_linear_model(
    *,
    df: pd.DataFrame,
    target: str,
    features: list[str],
    min_points: int,
) -> LinearInfluenceModel:
    removed_features: list[str] = []
    observations: list[str] = []
    if df.empty or target not in df.columns:
        return _empty_model(
            target=target,
            features=[],
            removed_features=features,
            observations=[f"alvo {target} indisponivel para ajuste."],
        )

    available_features = []
    for feature in features:
        if feature not in df.columns:
            removed_features.append(feature)
            continue
        available_features.append(feature)

    if not available_features:
        return _empty_model(
            target=target,
            features=[],
            removed_features=removed_features,
            observations=["nenhuma variavel explicativa disponivel."],
        )

    fit_frame = df.loc[:, [target, *available_features]].copy()
    for column in [target, *available_features]:
        fit_frame[column] = pd.to_numeric(fit_frame[column], errors="coerce")
    fit_frame = fit_frame.dropna(subset=[target, *available_features])

    if len(fit_frame) < min_points:
        observations.append(
            f"pontos validos insuficientes para ajuste robusto: {len(fit_frame)} de {min_points}."
        )
        return _empty_model(
            target=target,
            features=[],
            removed_features=[*removed_features, *available_features],
            observations=observations,
            n_points=int(len(fit_frame)),
        )

    usable_features: list[str] = []
    for feature in available_features:
        std = float(fit_frame[feature].std(ddof=0))
        if std <= 1e-9:
            removed_features.append(feature)
            continue
        usable_features.append(feature)

    if not usable_features:
        observations.append("todas as variaveis explicativas ficaram constantes na janela.")
        return _empty_model(
            target=target,
            features=[],
            removed_features=removed_features,
            observations=observations,
            n_points=int(len(fit_frame)),
        )

    fit_frame = fit_frame.loc[:, [target, *usable_features]].dropna()
    x = fit_frame.loc[:, usable_features].to_numpy(dtype=float)
    y = fit_frame[target].to_numpy(dtype=float)
    if len(y) < min_points or float(np.std(y)) <= 1e-9:
        observations.append("o alvo ficou constante ou com poucos pontos apos limpeza.")
        return _empty_model(
            target=target,
            features=[],
            removed_features=[*removed_features, *usable_features],
            observations=observations,
            n_points=int(len(y)),
        )

    x_augmented = np.column_stack([np.ones(len(x)), x])
    raw_solution = np.linalg.lstsq(x_augmented, y, rcond=None)[0]
    intercept = float(raw_solution[0])
    coefficients = {
        feature: float(raw_solution[index + 1])
        for index, feature in enumerate(usable_features)
    }
    predictions = x_augmented @ raw_solution
    residuals = y - predictions
    total_sum = float(np.sum((y - np.mean(y)) ** 2))
    residual_sum = float(np.sum(residuals**2))
    r2 = None if total_sum <= 0 else max(0.0, min(1.0, 1.0 - residual_sum / total_sum))
    mae = float(np.mean(np.abs(residuals)))

    x_means = np.mean(x, axis=0)
    x_stds = np.std(x, axis=0)
    y_mean = float(np.mean(y))
    y_std = float(np.std(y))
    x_standardized = (x - x_means) / np.where(x_stds <= 1e-9, 1.0, x_stds)
    y_standardized = (y - y_mean) / y_std
    std_solution = np.linalg.lstsq(
        np.column_stack([np.ones(len(x_standardized)), x_standardized]),
        y_standardized,
        rcond=None,
    )[0]
    standardized_coefficients = {
        feature: float(std_solution[index + 1])
        for index, feature in enumerate(usable_features)
    }

    observations.extend(_collinearity_observations(fit_frame, usable_features))
    if target == TARGET_QN:
        observations.extend(_direct_sign_observations(standardized_coefficients))
    return LinearInfluenceModel(
        target=target,
        features=usable_features,
        intercept=intercept,
        coefficients=coefficients,
        standardized_coefficients=standardized_coefficients,
        r2=None if r2 is None else float(r2),
        mae=mae,
        n_points=int(len(y)),
        removed_features=removed_features,
        observations=observations,
    )


def _empty_model(
    *,
    target: str,
    features: list[str],
    removed_features: list[str],
    observations: list[str],
    n_points: int = 0,
) -> LinearInfluenceModel:
    return LinearInfluenceModel(
        target=target,
        features=features,
        intercept=None,
        coefficients={},
        standardized_coefficients={},
        r2=None,
        mae=None,
        n_points=n_points,
        removed_features=removed_features,
        observations=observations,
    )


def _fit_intercept_only_model(
    *,
    df: pd.DataFrame,
    target: str,
    removed_features: list[str],
    observations: list[str],
) -> LinearInfluenceModel:
    if df.empty or target not in df.columns:
        return _empty_model(
            target=target,
            features=[],
            removed_features=removed_features,
            observations=observations,
        )

    y = pd.to_numeric(df[target], errors="coerce").dropna()
    if len(y) < MIN_MODEL_POINTS:
        return _empty_model(
            target=target,
            features=[],
            removed_features=removed_features,
            observations=[
                *observations,
                f"pontos validos insuficientes para linha-base: {len(y)} de {MIN_MODEL_POINTS}.",
            ],
            n_points=int(len(y)),
        )

    intercept = float(y.mean())
    residuals = y.to_numpy(dtype=float) - intercept
    return LinearInfluenceModel(
        target=target,
        features=[],
        intercept=intercept,
        coefficients={},
        standardized_coefficients={},
        r2=0.0,
        mae=float(np.mean(np.abs(residuals))),
        n_points=int(len(y)),
        removed_features=list(dict.fromkeys(removed_features)),
        observations=observations,
    )


def _collect_analysis_quality_flags(frame: pd.DataFrame) -> list[AnalysisQualityFlag]:
    flags: list[AnalysisQualityFlag] = []
    if frame.empty:
        return flags

    analysis_columns = [TARGET_QN, *DIRECT_QN_FEATURES, *DEGRADATION_FEATURES]
    for signal in analysis_columns:
        if signal not in frame.columns:
            flags.append(
                AnalysisQualityFlag(
                    code="missing_analysis_signal",
                    severity="warning",
                    message="Variavel esperada nao esta disponivel para a analise.",
                    signal=signal,
                )
            )
            continue
        null_ratio = float(pd.to_numeric(frame[signal], errors="coerce").isna().mean())
        if null_ratio >= 0.2:
            flags.append(
                AnalysisQualityFlag(
                    code="high_null_ratio",
                    severity="warning",
                    message="Variavel com muitos nulos na janela de analise.",
                    signal=signal,
                    details={"null_ratio": round(null_ratio, 3)},
                )
            )

    if "pv_temp_ar_estagio_3_c" in frame.columns:
        values = pd.to_numeric(frame["pv_temp_ar_estagio_3_c"], errors="coerce").dropna()
        if len(values) >= 10:
            zero_ratio = float((values == 0).mean())
            if zero_ratio >= 0.75:
                flags.append(
                    AnalysisQualityFlag(
                        code="persistent_zero_critical_signal",
                        severity="warning",
                        message="Temperatura do ar do 3o estagio esta zerada de forma persistente.",
                        signal="pv_temp_ar_estagio_3_c",
                        details={"zero_ratio": round(zero_ratio, 3)},
                    )
                )

    if "pv_pres_vacuo_cx_engran_inh2o" in frame.columns:
        values = pd.to_numeric(frame["pv_pres_vacuo_cx_engran_inh2o"], errors="coerce").dropna()
        if len(values) >= 5:
            outside_ratio = float(((values < 2.0) | (values > 20.0)).mean())
            if outside_ratio >= 0.5:
                flags.append(
                    AnalysisQualityFlag(
                        code="engineering_inconsistent_signal",
                        severity="warning",
                        message="Vacuo da caixa de engrenagem esta fora da faixa esperada de engenharia.",
                        signal="pv_pres_vacuo_cx_engran_inh2o",
                        details={"outside_ratio": round(outside_ratio, 3)},
                    )
                )

    for signal in [*DIRECT_QN_FEATURES, *DEGRADATION_FEATURES]:
        if signal not in frame.columns or len(frame) < 45:
            continue
        values = pd.to_numeric(frame[signal], errors="coerce").dropna()
        if len(values) < 45:
            continue
        value_range = float(values.max() - values.min())
        std = float(values.std(ddof=0))
        last_value = float(values.iloc[-1])
        threshold = max(abs(last_value) * 0.001, 0.01)
        if value_range <= threshold and std <= threshold / 2.0:
            flags.append(
                AnalysisQualityFlag(
                    code="possible_stuck_signal",
                    severity="info",
                    message="Variavel praticamente constante na janela; pode reduzir a leitura de influencia.",
                    signal=signal,
                    details={
                        "observed_range": round(value_range, 6),
                        "observed_std": round(std, 6),
                    },
                )
            )

    return flags


def _build_classification_context(
    *,
    prepared: PreparedAnalysisDataset,
    direct_model: LinearInfluenceModel,
    loss_model: LinearInfluenceModel,
    delta_q_current: float | None,
) -> dict[str, Any]:
    serious_codes = {
        "low_valid_points",
        "target_unavailable",
        "missing_timestamp",
        "empty_dataset",
        "no_normal_operation_rows",
    }
    data_suspicion_codes = {
        "persistent_zero_critical_signal",
        "engineering_inconsistent_signal",
    }
    serious_count = sum(1 for flag in prepared.quality_flags if flag.code in serious_codes)
    suspicion_count = sum(1 for flag in prepared.quality_flags if flag.code in data_suspicion_codes)
    internal_context = _build_internal_degradation_context(prepared.frame)
    return {
        "valid_points": prepared.data_window.valid_rows,
        "direct_r2": direct_model.r2,
        "loss_r2": loss_model.r2,
        "delta_q_current": delta_q_current,
        "serious_quality_count": serious_count + suspicion_count,
        "direct_sign_issue_score": _direct_sign_inconsistency_score(direct_model),
        "internal_degradation_strength": internal_context["strength"],
        "internal_degradation_variables": internal_context["variables"],
    }


def _model_quality(model: LinearInfluenceModel) -> ModelQuality:
    return ModelQuality(
        target=model.target,
        r2=None if model.r2 is None else round(model.r2, 4),
        erro_medio_abs=None if model.mae is None else round(model.mae, 3),
        pontos_validos=model.n_points,
        features_usadas=model.features,
        features_removidas=model.removed_features,
        observacoes=model.observations,
    )


def _classification(
    classification: str,
    valid_points: int,
    fit_strength: float,
    explanation: str,
    variables: list[str],
    recommendation: str,
) -> LossOriginClassification:
    points_factor = min(1.0, valid_points / 120.0)
    confidence = max(0.0, min(0.95, 0.32 + fit_strength * 0.48 + points_factor * 0.20))
    return LossOriginClassification(
        classificacao=classification,
        confianca=round(confidence, 3),
        explicacao_curta=explanation,
        variaveis_dominantes=variables[:5],
        recomendacao_analitica=recommendation,
    )


def _classify_direct_dominance(
    *,
    valid_points: int,
    direct_r2: float,
    process_share: float,
    control_share: float,
    variables: list[str],
) -> LossOriginClassification:
    if control_share > process_share * 1.15:
        return _classification(
            "dominancia_controle",
            valid_points,
            direct_r2,
            "A Qn esta mais associada a atuadores e logica de controle do que a sinais internos.",
            variables,
            "Verificar abertura da admissao, bypass, alivio, modo de carga e resposta da malha de controle.",
        )
    return _classification(
        "dominancia_processo_rede",
        valid_points,
        direct_r2,
        "A Qn esta mais associada a pressao de descarga/sistema e condicoes externas de rede.",
        variables,
        "Verificar secador, linha de descarga, valvulas downstream, demanda da rede e contrapressao.",
    )


def _dominant_variables(
    direct_items: list[InfluenceItem],
    indirect_items: list[InfluenceItem],
) -> list[str]:
    combined = [
        *[(item.variavel, item.influencia) for item in direct_items[:3]],
        *[(item.variavel, item.influencia) for item in indirect_items[:3]],
    ]
    seen: set[str] = set()
    output: list[str] = []
    for variable, _score in sorted(combined, key=lambda item: item[1], reverse=True):
        if variable in seen:
            continue
        seen.add(variable)
        output.append(variable)
    return output


def _merge_variables(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for variable in [*primary, *secondary]:
        if variable in seen:
            continue
        seen.add(variable)
        merged.append(variable)
    return merged


def _direct_sign_inconsistency_score(model: LinearInfluenceModel) -> float:
    if not model.standardized_coefficients:
        return 0.0
    total_weight = 0.0
    inconsistent_weight = 0.0
    for feature, coefficient in model.standardized_coefficients.items():
        expected = EXPECTED_DIRECT_SIGNS.get(feature)
        if expected is None:
            continue
        weight = abs(float(coefficient))
        total_weight += weight
        actual = "positivo" if coefficient >= 0 else "negativo"
        if actual != expected:
            inconsistent_weight += weight
    if total_weight <= 0:
        return 0.0
    return round(float(inconsistent_weight / total_weight), 4)


def _is_direct_sign_inconsistent(feature: str, coefficient: float | None) -> bool:
    expected = EXPECTED_DIRECT_SIGNS.get(feature)
    if expected is None or coefficient is None:
        return False
    actual = "positivo" if coefficient >= 0 else "negativo"
    return actual != expected


def _direct_sign_observations(standardized_coefficients: dict[str, float]) -> list[str]:
    observations: list[str] = []
    for feature, expected in EXPECTED_DIRECT_SIGNS.items():
        if feature not in standardized_coefficients:
            continue
        actual = "positivo" if standardized_coefficients[feature] >= 0 else "negativo"
        if actual == expected:
            continue
        observations.append(
            f"sinal fisico inesperado em {feature}: esperado {expected}, modelo indicou {actual}."
        )
    return observations


def _build_internal_degradation_context(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or TARGET_QN not in frame.columns:
        return {"strength": 0.0, "variables": []}

    scores: list[tuple[str, float]] = []
    qn = pd.to_numeric(frame[TARGET_QN], errors="coerce")
    for signal, adverse_direction in DEGRADATION_ADVERSE_DIRECTIONS.items():
        if signal not in frame.columns:
            continue
        series = pd.to_numeric(frame[signal], errors="coerce")
        aligned = pd.concat([qn.rename(TARGET_QN), series.rename(signal)], axis=1).dropna()
        if len(aligned) < MIN_MODEL_POINTS:
            continue
        if float(aligned[signal].std(ddof=0)) <= 1e-9 or float(aligned[TARGET_QN].std(ddof=0)) <= 1e-9:
            continue

        correlation = float(aligned[TARGET_QN].corr(aligned[signal]))
        if not np.isfinite(correlation):
            continue

        segment_size = max(5, int(len(aligned) * 0.2))
        initial_value = float(aligned[signal].head(segment_size).median())
        final_value = float(aligned[signal].tail(segment_size).median())
        delta_signal = final_value - initial_value
        std_signal = float(aligned[signal].std(ddof=0))
        trend_strength = min(1.0, abs(delta_signal) / max(std_signal * 2.0, 1e-9))

        if adverse_direction == "high":
            adverse_evidence = delta_signal > 0 and correlation <= -0.35
        else:
            adverse_evidence = delta_signal < 0 and correlation >= 0.35
        if not adverse_evidence:
            continue

        score = abs(correlation) * max(0.35, trend_strength)
        scores.append((signal, min(0.95, float(score))))

    if not scores:
        return {"strength": 0.0, "variables": []}

    scores = sorted(scores, key=lambda item: item[1], reverse=True)
    top_score = scores[0][1]
    second_score = scores[1][1] if len(scores) > 1 else 0.0
    strength = min(0.95, top_score * 0.72 + second_score * 0.28)
    return {
        "strength": round(float(strength), 4),
        "variables": [signal for signal, _score in scores[:5]],
    }


def _build_history_points(
    analysis_frame: pd.DataFrame,
    *,
    max_points: int,
) -> list[QnInfluenceHistoryPoint]:
    if analysis_frame.empty or "timestamp" not in analysis_frame.columns:
        return []
    frame = analysis_frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    if len(frame) > max_points:
        indices = np.linspace(0, len(frame) - 1, num=max_points, dtype=int)
        frame = frame.iloc[np.unique(indices)]

    points: list[QnInfluenceHistoryPoint] = []
    for _, row in frame.iterrows():
        qn_expected = _safe_float(row.get(EXPECTED_QN))
        delta = _safe_float(row.get(DELTA_Q))
        delta_pct = (
            None
            if qn_expected is None or qn_expected == 0 or delta is None
            else round((delta / qn_expected) * 100.0, 3)
        )
        points.append(
            QnInfluenceHistoryPoint(
                timestamp=pd.to_datetime(row["timestamp"]).to_pydatetime(),
                qn_real=_round_optional(_safe_float(row.get(TARGET_QN)), 3),
                qn_esperada=_round_optional(qn_expected, 3),
                delta_q=_round_optional(delta, 3),
                delta_q_percentual=delta_pct,
            )
        )
    return points


def _build_operational_context(latest: pd.Series | None) -> dict[str, Any]:
    if latest is None:
        return {}
    keys = [
        "timestamp",
        "mode_key",
        "st_oper",
        "st_carga_oper",
        "pv_corr_motor_a",
        "qa_m3h",
    ]
    context: dict[str, Any] = {}
    for key in keys:
        value = latest.get(key)
        if value is None or pd.isna(value):
            continue
        if hasattr(value, "isoformat"):
            context[key] = value.isoformat()
        elif isinstance(value, (float, int, np.floating, np.integer)):
            context[key] = round(float(value), 3)
        else:
            context[key] = str(value)
    context["observacao_corrente"] = (
        "pv_corr_motor_a nao foi usada como explicativa direta da Qn porque a Qn e derivada da corrente."
    )
    return context


def _collinearity_observations(frame: pd.DataFrame, features: list[str]) -> list[str]:
    if len(features) < 2:
        return []
    corr = frame.loc[:, features].corr(numeric_only=True).abs()
    observations: list[str] = []
    for idx, left in enumerate(features):
        for right in features[idx + 1 :]:
            value = corr.loc[left, right]
            if pd.isna(value) or value < 0.85:
                continue
            observations.append(
                f"possivel colinearidade entre {left} e {right} (correlacao {value:.2f})."
            )
    return observations


def _count_transition_rows(frame: pd.DataFrame) -> int:
    return int(_transition_mask(frame).sum()) if "st_oper" in frame.columns else 0


def _transition_mask(frame: pd.DataFrame) -> pd.Series:
    if "st_oper" not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame["st_oper"].astype("string").isin(TRANSITION_STATES)


def _build_influence_interpretation(
    *,
    feature: str,
    signal: str,
    influence_type: str,
) -> str:
    label = get_signal_label(feature)
    if influence_type == "direta":
        if signal == "negativo":
            return f"Quando {label} aumenta, a Qn tende a reduzir na janela analisada."
        return f"Quando {label} aumenta, a Qn tende a aumentar na janela analisada."
    if signal == "negativo":
        return f"Quando {label} aumenta, o desvio residual de Qn tende a piorar."
    return f"Quando {label} aumenta, o desvio residual de Qn tende a melhorar ou acompanhar recuperacao."


def _is_negative_or_unknown_delta(value: Any) -> bool:
    numeric = _safe_float(value)
    return numeric is None or numeric <= 0.0


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if pd.isna(value):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


def _round_optional(value: float | None, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _infer_subsystem(signal: str) -> str:
    for subsystem, signals in SUBSYSTEM_SIGNALS.items():
        if signal in signals:
            return subsystem
    if signal in CONTROL_FEATURES:
        return "controle"
    return "operacao"

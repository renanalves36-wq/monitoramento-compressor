"""Motor prescritivo pragmatico para o compressor TA6000."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd

from app.domain.mappings import CALIBRATION_HINTS, TARGET_SIGNAL_BY_SIGNAL
from app.domain.prescriptive_matrix import PRESCRIPTIVE_MATRIX
from app.domain.schemas import PrescriptiveDiagnosis, PrescriptiveHypothesis


TRANSITION_STATES = {
    "PARTINDO",
    "PARANDO",
    "DESACELERANDO",
    "INICIALIZANDO PARTIDA",
}

CRITICAL_ANALOG_SIGNALS = {
    "pv_temp_ar_estagio_3_c",
    "pv_temp_oleo_lubrificacao_c",
    "pv_pres_oleo_bar",
    "pv_pres_oleo_antes_filtro_bar",
    "pv_corr_motor_a",
    "pv_pres_sistema_bar",
    "pv_pres_descarga_bar",
    "pv_pres_vacuo_cx_engran_inh2o",
}


class PrescriptiveService:
    """Ranqueia hipoteses e prescreve acoes a partir de flags simples."""

    def __init__(self) -> None:
        self.matrix = PRESCRIPTIVE_MATRIX
        self.signal_matrix = dict(self.matrix.get("signals", {}))
        self.global_rules = list(self.matrix.get("global_rules", []))

    def supports(self, variavel_principal: str) -> bool:
        return variavel_principal in self.signal_matrix

    def build_context_flags(
        self,
        snapshot: Mapping[str, Any] | pd.Series,
        features: Mapping[str, Any] | pd.Series,
        contexto_operacional: Mapping[str, Any] | None = None,
    ) -> dict[str, bool]:
        snapshot_map = self._to_mapping(snapshot)
        feature_map = self._to_mapping(features)
        context_map = self._to_mapping(contexto_operacional)

        st_oper = self._get_text(snapshot_map, feature_map, context_map, "st_oper")
        st_carga_oper = self._get_text(snapshot_map, feature_map, context_map, "st_carga_oper")

        estator_a = self._get_numeric(snapshot_map, feature_map, "pv_temp_fase_a_do_estator_c")
        estator_b = self._get_numeric(snapshot_map, feature_map, "pv_temp_fase_b_do_estator_c")
        estator_c = self._get_numeric(snapshot_map, feature_map, "pv_temp_fase_c_do_estator_c")

        vib_1 = self._get_numeric(snapshot_map, feature_map, "pv_vib_estagio_1_mils")
        vib_2 = self._get_numeric(snapshot_map, feature_map, "pv_vib_estagio_2_mils")
        vib_3 = self._get_numeric(snapshot_map, feature_map, "pv_vib_estagio_3_mils")

        delta_descarga = self._safe_diff(
            self._get_numeric(snapshot_map, feature_map, "pv_pres_descarga_bar"),
            self._get_numeric(snapshot_map, feature_map, "pv_pres_sistema_bar"),
        )
        delta_filtro = self._get_numeric(snapshot_map, feature_map, "delta_filtro_oleo_bar")
        if delta_filtro is None:
            delta_filtro = self._safe_diff(
                self._get_numeric(snapshot_map, feature_map, "pv_pres_oleo_antes_filtro_bar"),
                self._get_numeric(snapshot_map, feature_map, "pv_pres_oleo_bar"),
            )

        assimetria_a = self._phase_dominant(estator_a, estator_b, estator_c)
        assimetria_b = self._phase_dominant(estator_b, estator_a, estator_c)
        assimetria_c = self._phase_dominant(estator_c, estator_a, estator_b)

        flags = {
            "pv_corr_motor_a_alta": self._gt(snapshot_map, feature_map, "pv_corr_motor_a", 180.0),
            "pv_corr_motor_a_estavel": self._is_stable(snapshot_map, feature_map, "pv_corr_motor_a"),
            "vibracao_alta": any(
                value is not None and value > 1.3 for value in (vib_1, vib_2, vib_3)
            ),
            "vibracao_estavel": self._is_vibration_stable(snapshot_map, feature_map),
            "pv_temp_oleo_lubrificacao_c_alta": self._gt(
                snapshot_map, feature_map, "pv_temp_oleo_lubrificacao_c", 54.0
            ),
            "oleo_estavel": self._is_stable(snapshot_map, feature_map, "pv_temp_oleo_lubrificacao_c"),
            "delta_descarga_sistema_alto": delta_descarga is not None and delta_descarga > 0.7,
            "delta_filtro_oleo_relevante": delta_filtro is not None and delta_filtro > 2.0,
            "bypass_anormal": self._gt(snapshot_map, feature_map, "pv_pos_valv_bypass_pct", 20.0),
            "admissao_anormal": self._gt(
                snapshot_map, feature_map, "pv_pos_abert_valv_admissao_pct", 85.0
            ),
            "alivio_anormal": self._gt(snapshot_map, feature_map, "pv_pos_alivio_pct", 20.0),
            "temperatura_estator_alta": any(
                value is not None and value > 130.0
                for value in (estator_a, estator_b, estator_c)
            ),
            "assimetria_estator": any((assimetria_a, assimetria_b, assimetria_c)),
            "fase_a_assimetrica": assimetria_a,
            "fase_b_assimetrica": assimetria_b,
            "fase_c_assimetrica": assimetria_c,
            "fases_estator_altas_sem_assimetria": all(
                value is not None and value > 130.0 for value in (estator_a, estator_b, estator_c)
            )
            and not any((assimetria_a, assimetria_b, assimetria_c)),
            "rolamento_motor_alto": self._gt(
                snapshot_map, feature_map, "pv_temp_rolamento_dianteiro_motor", 90.0
            ),
            "temp_ar_estagio_3_alta": self._gt(snapshot_map, feature_map, "pv_temp_ar_estagio_3_c", 54.0),
            "temp_ar_estagio_3_zerada": self._is_zero_suspect(snapshot_map, feature_map, "pv_temp_ar_estagio_3_c"),
            "vacuo_cx_engran_inconsistente": self._is_vacuum_inconsistent(snapshot_map, feature_map),
            "nivel_oleo_estado_anormal": self._is_oil_level_abnormal(snapshot_map, feature_map, st_oper, st_carga_oper),
            "modo_transicao": st_oper in TRANSITION_STATES,
            "modo_funcionamento_normal": st_oper == "EM FUNCIONAMENTO",
            "modo_carregado": st_carga_oper == "CARREGADO",
            "modo_baixa_demanda": st_carga_oper in {"DESCARREGANDO", "SEM CARGA"},
            "somente_estagio_1_alto": self._only_stage_high(1, vib_1, vib_2, vib_3),
            "somente_estagio_2_alto": self._only_stage_high(2, vib_1, vib_2, vib_3),
            "somente_estagio_3_alto": self._only_stage_high(3, vib_1, vib_2, vib_3),
            "estagio_2_mais_critico": self._is_stage_2_most_critical(vib_1, vib_2, vib_3),
            "pressao_sistema_baixa": self._is_system_pressure_low(snapshot_map, feature_map),
            "pressao_descarga_alta": self._is_discharge_pressure_high(snapshot_map, feature_map),
            "oscilacao_pressao_sistema": self._is_pressure_oscillating(feature_map, "pv_pres_sistema_bar"),
            "vibracao_externa_sugerida": self._suggest_external_vibration(snapshot_map, feature_map),
        }

        anomalias_lubrificacao = sum(
            int(bool(flags[key]))
            for key in (
                "pv_temp_oleo_lubrificacao_c_alta",
                "delta_filtro_oleo_relevante",
                "nivel_oleo_estado_anormal",
            )
        )
        flags["anomalias_lubrificacao_convergentes"] = anomalias_lubrificacao >= 2
        flags["pressao_oleo_problematica"] = any(
            self._is_pressure_problem(snapshot_map, feature_map, signal)
            for signal in ("pv_pres_oleo_bar", "pv_pres_oleo_antes_filtro_bar")
        )
        flags["instrumentacao_suspeita"] = any(
            self._is_sensor_stuck(snapshot_map, feature_map, signal)
            for signal in CRITICAL_ANALOG_SIGNALS
        ) or flags["temp_ar_estagio_3_zerada"] or flags["vacuo_cx_engran_inconsistente"]
        flags["sem_convergencia_fisica_relevante"] = not any(
            flags.get(key, False)
            for key in (
                "pv_corr_motor_a_alta",
                "vibracao_alta",
                "pv_temp_oleo_lubrificacao_c_alta",
                "temperatura_estator_alta",
                "rolamento_motor_alto",
                "delta_descarga_sistema_alto",
                "delta_filtro_oleo_relevante",
            )
        )
        flags["modo_principal_diagnostico"] = (
            flags["modo_funcionamento_normal"] and flags["modo_carregado"]
        )

        return flags

    def generate_prescriptive_diagnosis(
        self,
        variavel_principal: str,
        snapshot: Mapping[str, Any] | pd.Series,
        features: Mapping[str, Any] | pd.Series,
        contexto_operacional: Mapping[str, Any] | None = None,
    ) -> PrescriptiveDiagnosis:
        matrix_entry = self.signal_matrix.get(variavel_principal)
        if matrix_entry is None:
            return PrescriptiveDiagnosis(
                variavel_principal=variavel_principal,
                subsistema="indefinido",
                criticidade_base="media",
                observacoes=["nao ha matriz prescritiva cadastrada para esta variavel."],
            )

        flags = self.build_context_flags(snapshot, features, contexto_operacional)
        internal_scores = {
            causa: 1 for causa in matrix_entry.get("internal_hypotheses", [])
        }
        peripheral_scores = {
            causa: 1 for causa in matrix_entry.get("peripheral_hypotheses", [])
        }
        observations: list[str] = []
        actions = list(matrix_entry.get("recommended_actions", []))

        self._apply_matrix_rules(
            rules=list(matrix_entry.get("correlation_rules", [])),
            variavel_principal=variavel_principal,
            flags=flags,
            internal_scores=internal_scores,
            peripheral_scores=peripheral_scores,
            observations=observations,
            actions=actions,
        )
        self._apply_global_rules(
            variavel_principal=variavel_principal,
            flags=flags,
            internal_scores=internal_scores,
            peripheral_scores=peripheral_scores,
            observations=observations,
            actions=actions,
        )

        if flags.get("modo_transicao"):
            self._reduce_confidence(internal_scores)
            self._reduce_confidence(peripheral_scores)

        if not flags.get("modo_principal_diagnostico"):
            observations.append(
                "o diagnostico esta fora do contexto principal EM FUNCIONAMENTO|CARREGADO e deve ser interpretado com cautela."
            )

        if flags.get("instrumentacao_suspeita"):
            actions.insert(0, "validar instrumentacao antes de priorizar intervencao fisica invasiva")
            vacuum_hint = CALIBRATION_HINTS.get("pv_pres_vacuo_cx_engran_inh2o")
            if flags.get("vacuo_cx_engran_inconsistente") and vacuum_hint:
                observations.append(vacuum_hint)

        if flags.get("assimetria_estator"):
            observations.append(
                "foi detectada assimetria entre as fases do estator, aumentando a suspeita de causa localizada."
            )

        ranked_hypotheses = self._build_ranked_hypotheses(
            internal_scores=internal_scores,
            peripheral_scores=peripheral_scores,
        )

        return PrescriptiveDiagnosis(
            variavel_principal=variavel_principal,
            subsistema=str(matrix_entry["subsystem"]),
            flags_ativas=sorted(flag for flag, active in flags.items() if active is True),
            score_interno=sum(internal_scores.values()),
            score_periferico=sum(peripheral_scores.values()),
            hipoteses=ranked_hypotheses,
            acoes_recomendadas=self._deduplicate(actions),
            criticidade_base=str(matrix_entry["base_criticality"]),
            observacoes=self._deduplicate(observations),
        )

    def _apply_matrix_rules(
        self,
        rules: list[dict[str, Any]],
        variavel_principal: str,
        flags: dict[str, bool],
        internal_scores: dict[str, int],
        peripheral_scores: dict[str, int],
        observations: list[str],
        actions: list[str],
    ) -> None:
        for rule in rules:
            if not self._rule_matches(rule, flags):
                continue
            self._apply_rule_effect(
                rule=rule,
                variavel_principal=variavel_principal,
                internal_scores=internal_scores,
                peripheral_scores=peripheral_scores,
                observations=observations,
                actions=actions,
            )

    def _apply_global_rules(
        self,
        variavel_principal: str,
        flags: dict[str, bool],
        internal_scores: dict[str, int],
        peripheral_scores: dict[str, int],
        observations: list[str],
        actions: list[str],
    ) -> None:
        for rule in self.global_rules:
            applies_to = rule.get("applies_to")
            if applies_to != "__all__" and variavel_principal not in applies_to:
                continue
            if not self._rule_matches(rule, flags):
                continue
            self._apply_rule_effect(
                rule=rule,
                variavel_principal=variavel_principal,
                internal_scores=internal_scores,
                peripheral_scores=peripheral_scores,
                observations=observations,
                actions=actions,
            )

    @staticmethod
    def _apply_rule_effect(
        rule: dict[str, Any],
        variavel_principal: str,
        internal_scores: dict[str, int],
        peripheral_scores: dict[str, int],
        observations: list[str],
        actions: list[str],
    ) -> None:
        favor = rule.get("favor")
        weight = int(rule.get("weight", 0))
        causes = list(rule.get("causes", []))

        if favor == "interno" and weight:
            PrescriptiveService._increment_scores(internal_scores, weight, causes)
        if favor == "periferico" and weight:
            PrescriptiveService._increment_scores(peripheral_scores, weight, causes)

        observation = rule.get("observation")
        if observation:
            observations.append(str(observation))

        if rule.get("reduce_confidence"):
            observations.append(
                f"foi aplicada reducao de confianca diagnostica para {variavel_principal}."
            )

        if rule.get("reduce_physical_invasive_actions"):
            actions.insert(
                0,
                "priorizar validacao de instrumentacao e sinais antes de abrir equipamento ou executar inspecao invasiva",
            )

    @staticmethod
    def _increment_scores(score_map: dict[str, int], weight: int, causes: list[str]) -> None:
        targets = causes or list(score_map.keys())
        for cause in targets:
            if cause in score_map:
                score_map[cause] += weight

    @staticmethod
    def _reduce_confidence(score_map: dict[str, int]) -> None:
        for cause, score in list(score_map.items()):
            score_map[cause] = max(1, int(round(score * 0.7)))

    @staticmethod
    def _build_ranked_hypotheses(
        internal_scores: dict[str, int],
        peripheral_scores: dict[str, int],
    ) -> list[PrescriptiveHypothesis]:
        hypotheses: list[PrescriptiveHypothesis] = []
        for cause, score in internal_scores.items():
            hypotheses.append(PrescriptiveHypothesis(causa=cause, tipo="interno", score=score))
        for cause, score in peripheral_scores.items():
            hypotheses.append(PrescriptiveHypothesis(causa=cause, tipo="periferico", score=score))
        return sorted(
            hypotheses,
            key=lambda item: (item.score, 1 if item.tipo == "interno" else 0, item.causa),
            reverse=True,
        )

    @staticmethod
    def _rule_matches(rule: dict[str, Any], flags: dict[str, bool]) -> bool:
        when_all = list(rule.get("when_all", []))
        when_any = list(rule.get("when_any", []))

        if when_all and not all(flags.get(flag, False) for flag in when_all):
            return False
        if when_any and not any(flags.get(flag, False) for flag in when_any):
            return False
        return bool(when_all or when_any or rule.get("observation"))

    @staticmethod
    def _deduplicate(values: list[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            normalized = str(value).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append(normalized)
        return output

    @staticmethod
    def _to_mapping(value: Mapping[str, Any] | pd.Series | None) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, pd.Series):
            return value.to_dict()
        return dict(value)

    @staticmethod
    def _safe_float(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(value)
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_numeric(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        key: str,
    ) -> float | None:
        if key in feature_map:
            value = self._safe_float(feature_map.get(key))
            if value is not None:
                return value
        return self._safe_float(snapshot_map.get(key))

    @staticmethod
    def _get_text(
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        context_map: dict[str, Any],
        key: str,
    ) -> str | None:
        for source in (context_map, feature_map, snapshot_map):
            value = source.get(key)
            if value is None or (not isinstance(value, str) and pd.isna(value)):
                continue
            text = str(value).strip()
            if text:
                return text
        return None

    def _gt(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        key: str,
        threshold: float,
    ) -> bool:
        value = self._get_numeric(snapshot_map, feature_map, key)
        return value is not None and value > threshold

    def _is_stable(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        signal: str,
    ) -> bool:
        current = self._get_numeric(snapshot_map, feature_map, signal)
        mean_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__ma_1h")
        if current is None or mean_1h is None:
            return False
        tolerance = max(abs(mean_1h) * 0.05, 0.05)
        return abs(current - mean_1h) <= tolerance

    def _is_vibration_stable(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
    ) -> bool:
        candidates = []
        for signal in (
            "pv_vib_estagio_1_mils",
            "pv_vib_estagio_2_mils",
            "pv_vib_estagio_3_mils",
            "pv_vib_max_mils",
        ):
            current = self._get_numeric(snapshot_map, feature_map, signal)
            mean_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__ma_1h")
            if current is None or mean_1h is None:
                continue
            tolerance = max(abs(mean_1h) * 0.05, 0.03)
            candidates.append(abs(current - mean_1h) <= tolerance)
        return bool(candidates) and all(candidates)

    @staticmethod
    def _safe_diff(first: float | None, second: float | None) -> float | None:
        if first is None or second is None:
            return None
        return first - second

    @staticmethod
    def _phase_dominant(
        reference: float | None,
        other_a: float | None,
        other_b: float | None,
        margin: float = 10.0,
    ) -> bool:
        if reference is None or other_a is None or other_b is None:
            return False
        return reference - max(other_a, other_b) > margin

    def _is_zero_suspect(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        signal: str,
    ) -> bool:
        current = self._get_numeric(snapshot_map, feature_map, signal)
        if current is None or current != 0:
            return False
        std_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__std_1h")
        max_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__max_1h")
        return std_1h is None or std_1h < 0.01 or max_1h == 0

    def _is_sensor_stuck(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        signal: str,
    ) -> bool:
        current = self._get_numeric(snapshot_map, feature_map, signal)
        if current is None:
            return False
        std_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__std_1h")
        min_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__min_1h")
        max_1h = self._get_numeric(snapshot_map, feature_map, f"{signal}__max_1h")
        dynamic_range = self._safe_diff(max_1h, min_1h)
        range_threshold = max(abs(current) * 0.005, 0.01)
        if std_1h is not None and std_1h <= range_threshold:
            return True
        return dynamic_range is not None and dynamic_range <= range_threshold

    def _is_vacuum_inconsistent(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
    ) -> bool:
        value = self._get_numeric(snapshot_map, feature_map, "pv_pres_vacuo_cx_engran_inh2o")
        return value is not None and (value < 2.0 or value > 20.0)

    def _is_oil_level_abnormal(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        st_oper: str | None,
        st_carga_oper: str | None,
    ) -> bool:
        value = feature_map.get("pv_niv_interruptor_oleo_bar", snapshot_map.get("pv_niv_interruptor_oleo_bar"))
        if value is None or pd.isna(value):
            return False
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "normal", "ok"}:
            return False
        return st_oper == "EM FUNCIONAMENTO" or st_carga_oper == "CARREGADO"

    @staticmethod
    def _only_stage_high(
        stage: int,
        vib_1: float | None,
        vib_2: float | None,
        vib_3: float | None,
    ) -> bool:
        values = {1: vib_1, 2: vib_2, 3: vib_3}
        target = values[stage]
        if target is None or target <= 1.3:
            return False
        return all(
            values[idx] is None or values[idx] <= 1.3
            for idx in values
            if idx != stage
        )

    @staticmethod
    def _is_stage_2_most_critical(
        vib_1: float | None,
        vib_2: float | None,
        vib_3: float | None,
    ) -> bool:
        if vib_2 is None or vib_2 <= 1.3:
            return False
        comparisons = [value for value in (vib_1, vib_3) if value is not None]
        return bool(comparisons) and all(vib_2 - value > 0.15 for value in comparisons)

    def _is_system_pressure_low(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
    ) -> bool:
        current = self._get_numeric(snapshot_map, feature_map, "pv_pres_sistema_bar")
        target_signal = TARGET_SIGNAL_BY_SIGNAL.get("pv_pres_sistema_bar")
        target = (
            self._get_numeric(snapshot_map, feature_map, target_signal)
            if target_signal
            else None
        )
        if current is None:
            return False
        if target is not None:
            return current < target * 0.95
        return current < 5.0

    def _is_discharge_pressure_high(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
    ) -> bool:
        current = self._get_numeric(snapshot_map, feature_map, "pv_pres_descarga_bar")
        target_signal = TARGET_SIGNAL_BY_SIGNAL.get("pv_pres_descarga_bar")
        target = (
            self._get_numeric(snapshot_map, feature_map, target_signal)
            if target_signal
            else None
        )
        if current is None:
            return False
        if target is not None:
            return current > target + 0.5
        return current > 7.8

    def _is_pressure_oscillating(self, feature_map: dict[str, Any], signal: str) -> bool:
        std_15m = self._safe_float(feature_map.get(f"{signal}__std_15m"))
        min_15m = self._safe_float(feature_map.get(f"{signal}__min_15m"))
        max_15m = self._safe_float(feature_map.get(f"{signal}__max_15m"))
        dynamic_range = self._safe_diff(max_15m, min_15m)
        return (std_15m is not None and std_15m > 0.15) or (
            dynamic_range is not None and dynamic_range > 0.4
        )

    def _suggest_external_vibration(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
    ) -> bool:
        vib_1 = self._get_numeric(snapshot_map, feature_map, "pv_vib_estagio_1_mils")
        vib_2 = self._get_numeric(snapshot_map, feature_map, "pv_vib_estagio_2_mils")
        vib_3 = self._get_numeric(snapshot_map, feature_map, "pv_vib_estagio_3_mils")
        current = [value for value in (vib_1, vib_2, vib_3) if value is not None]
        if not current or max(current) <= 1.3:
            return False
        return self._is_stable(snapshot_map, feature_map, "pv_corr_motor_a") and self._is_stable(
            snapshot_map, feature_map, "pv_temp_oleo_lubrificacao_c"
        )

    def _is_pressure_problem(
        self,
        snapshot_map: dict[str, Any],
        feature_map: dict[str, Any],
        signal: str,
    ) -> bool:
        value = self._get_numeric(snapshot_map, feature_map, signal)
        if value is None:
            return False
        if signal == "pv_pres_oleo_bar":
            return value < 6.89 or value > 12.0
        return value > 12.0

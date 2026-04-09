"""Mapeamentos de colunas, subsistemas e faixas basicas."""

from __future__ import annotations


RAW_TO_FRIENDLY = {
    "012CPA0008_ST_PLC": "st_plc",
    "012CPA0008_SP_PRES_SISTEMA_BAR": "sp_pres_sistema_bar",
    "012CPA0008_PV_PRES_SISTEMA_BAR": "pv_pres_sistema_bar",
    "012CPA0008_SP_PRES_SETPOINT_DESCARGA_BAR": "sp_pres_setpoint_descarga_bar",
    "012CPA0008_PV_PRES_DESCARGA_BAR": "pv_pres_descarga_bar",
    "012CPA0008_PV_PRES_OLEO_ANTES_FILTRO_BAR": "pv_pres_oleo_antes_filtro_bar",
    "012CPA0008_PV_PRES_OLEO_BAR": "pv_pres_oleo_bar",
    "012CPA0008_PV_TEMP_OLEO_LUBRIFICACAO_C": "pv_temp_oleo_lubrificacao_c",
    "012CPA0008_PV_VIB_ESTAGIO_1_MILS": "pv_vib_estagio_1_mils",
    "012CPA0008_PV_VIB_ESTAGIO_2_MILS": "pv_vib_estagio_2_mils",
    "012CPA0008_PV_VIB_ESTAGIO_3_MILS": "pv_vib_estagio_3_mils",
    "012CPA0008_PV_TEMP_AR_ESTAGIO_3_C": "pv_temp_ar_estagio_3_c",
    "012CPA0008_PV_NIV_INTERRUPTOR_OLEO_BAR": "pv_niv_interruptor_oleo_bar",
    "012CPA0008_PV_PRES_VACUO_CX_ENGRAN_inH2O": "pv_pres_vacuo_cx_engran_inh2o",
    "012CPA0008_PV_TEMP_FASE_A_DO_ESTATOR_C": "pv_temp_fase_a_do_estator_c",
    "012CPA0008_PV_TEMP_FASE_B_DO_ESTATOR_C": "pv_temp_fase_b_do_estator_c",
    "012CPA0008_PV_TEMP_FASE_C_DO_ESTATOR_C": "pv_temp_fase_c_do_estator_c",
    "012CPA0008_PV_TEMP_ROLAMENTO_DIANTEIRO_MOTOR": "pv_temp_rolamento_dianteiro_motor",
    "012CPA0008_PV_CORR_MOTOR_A": "pv_corr_motor_a",
    "012CPA0008_PV_POS_ABERT_VALV_ADMISSAO_%": "pv_pos_abert_valv_admissao_pct",
    "012CPA0008_PV_POS_VALV_BYPASS_%": "pv_pos_valv_bypass_pct",
    "012CPA0008_PV_POSIÇÃO_ALIVIO%": "pv_pos_alivio_pct",
    "012CPA0008_ST_OPER": "st_oper",
    "012CPA0008_PV_HOR_OPERACAO": "pv_hor_operacao",
    "012CPA0008_PV_HOR_CARREGADA": "pv_hor_carregada",
    "012CPA0008_PV_NUM_PARTIDAS": "pv_num_partidas",
    "012CPA0008_ST_CARGA_OPER": "st_carga_oper",
}

SUBSYSTEM_SIGNALS = {
    "ar_processo": [
        "sp_pres_sistema_bar",
        "pv_pres_sistema_bar",
        "sp_pres_setpoint_descarga_bar",
        "pv_pres_descarga_bar",
        "pv_temp_ar_estagio_3_c",
        "pv_pos_abert_valv_admissao_pct",
        "pv_pos_valv_bypass_pct",
        "pv_pos_alivio_pct",
    ],
    "lubrificacao": [
        "pv_pres_oleo_antes_filtro_bar",
        "pv_pres_oleo_bar",
        "pv_temp_oleo_lubrificacao_c",
        "pv_niv_interruptor_oleo_bar",
        "pv_pres_vacuo_cx_engran_inh2o",
        "delta_filtro_oleo_bar",
    ],
    "vibracao": [
        "pv_vib_estagio_1_mils",
        "pv_vib_estagio_2_mils",
        "pv_vib_estagio_3_mils",
        "pv_vib_max_mils",
    ],
    "motor": [
        "pv_temp_fase_a_do_estator_c",
        "pv_temp_fase_b_do_estator_c",
        "pv_temp_fase_c_do_estator_c",
        "pv_temp_rolamento_dianteiro_motor",
        "pv_corr_motor_a",
        "pv_temp_estator_max_c",
    ],
    "operacao": [
        "st_plc",
        "st_oper",
        "st_carga_oper",
        "pv_hor_operacao",
        "pv_hor_carregada",
        "pv_num_partidas",
        "status",
    ],
}

NUMERIC_SIGNALS = sorted(
    {
        signal
        for signals in SUBSYSTEM_SIGNALS.values()
        for signal in signals
        if signal not in {"st_oper", "st_carga_oper", "status", "st_plc"}
    }
)

DERIVED_SIGNALS = ["delta_filtro_oleo_bar", "pv_vib_max_mils", "pv_temp_estator_max_c"]

ZERO_ABNORMAL_SIGNALS = {
    "pv_temp_ar_estagio_3_c",
    "pv_hor_operacao",
    "pv_hor_carregada",
    "pv_num_partidas",
}

STUCK_SENSOR_SIGNALS = {
    "pv_pres_sistema_bar",
    "pv_pres_descarga_bar",
    "pv_pres_oleo_antes_filtro_bar",
    "pv_pres_oleo_bar",
    "pv_temp_oleo_lubrificacao_c",
    "pv_vib_estagio_1_mils",
    "pv_vib_estagio_2_mils",
    "pv_vib_estagio_3_mils",
    "pv_temp_ar_estagio_3_c",
    "pv_pres_vacuo_cx_engran_inh2o",
    "pv_temp_fase_a_do_estator_c",
    "pv_temp_fase_b_do_estator_c",
    "pv_temp_fase_c_do_estator_c",
    "pv_temp_rolamento_dianteiro_motor",
    "pv_corr_motor_a",
}

PLAUSIBLE_RANGES = {
    "pv_pres_sistema_bar": {"min": 0.0, "max": 12.0},
    "pv_pres_descarga_bar": {"min": 0.0, "max": 15.0},
    "pv_pres_oleo_antes_filtro_bar": {"min": 0.0, "max": 20.0},
    "pv_pres_oleo_bar": {"min": 0.0, "max": 20.0},
    "pv_temp_oleo_lubrificacao_c": {"min": -5.0, "max": 120.0},
    "pv_vib_estagio_1_mils": {"min": 0.0, "max": 10.0},
    "pv_vib_estagio_2_mils": {"min": 0.0, "max": 10.0},
    "pv_vib_estagio_3_mils": {"min": 0.0, "max": 10.0},
    "pv_temp_ar_estagio_3_c": {"min": 0.0, "max": 150.0},
    "pv_pres_vacuo_cx_engran_inh2o": {"min": -50.0, "max": 300.0},
    "pv_temp_fase_a_do_estator_c": {"min": 0.0, "max": 220.0},
    "pv_temp_fase_b_do_estator_c": {"min": 0.0, "max": 220.0},
    "pv_temp_fase_c_do_estator_c": {"min": 0.0, "max": 220.0},
    "pv_temp_rolamento_dianteiro_motor": {"min": 0.0, "max": 150.0},
    "pv_corr_motor_a": {"min": 0.0, "max": 400.0},
    "pv_pos_abert_valv_admissao_pct": {"min": 0.0, "max": 100.0},
    "pv_pos_valv_bypass_pct": {"min": 0.0, "max": 100.0},
    "pv_pos_alivio_pct": {"min": 0.0, "max": 100.0},
}

CALIBRATION_HINTS = {
    "pv_pres_vacuo_cx_engran_inh2o": (
        "Valor fora da faixa operacional esperada. Conferir unidade, sinal "
        "e escala de engenharia do transmissor."
    )
}

NORMAL_OPERATION = {
    "st_oper": "EM FUNCIONAMENTO",
    "st_carga_oper": "CARREGADO",
}

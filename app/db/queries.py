"""Queries SQL explicitas para leitura do compressor."""

from __future__ import annotations

from datetime import datetime


FRIENDLY_SELECT = """
    [Id] AS id,
    [TimeStamp] AS timestamp,
    [Hora] AS hora,
    [Data] AS data,
    [dsTurno] AS ds_turno,
    [Status] AS status,
    [012CPA0008_ST_PLC] AS st_plc,
    [012CPA0008_SP_PRES_SISTEMA_BAR] AS sp_pres_sistema_bar,
    [012CPA0008_PV_PRES_SISTEMA_BAR] AS pv_pres_sistema_bar,
    [012CPA0008_SP_PRES_SETPOINT_DESCARGA_BAR] AS sp_pres_setpoint_descarga_bar,
    [012CPA0008_PV_PRES_DESCARGA_BAR] AS pv_pres_descarga_bar,
    [012CPA0008_PV_PRES_OLEO_ANTES_FILTRO_BAR] AS pv_pres_oleo_antes_filtro_bar,
    [012CPA0008_PV_PRES_OLEO_BAR] AS pv_pres_oleo_bar,
    [012CPA0008_PV_TEMP_OLEO_LUBRIFICACAO_C] AS pv_temp_oleo_lubrificacao_c,
    [012CPA0008_PV_VIB_ESTAGIO_1_MILS] AS pv_vib_estagio_1_mils,
    [012CPA0008_PV_VIB_ESTAGIO_2_MILS] AS pv_vib_estagio_2_mils,
    [012CPA0008_PV_VIB_ESTAGIO_3_MILS] AS pv_vib_estagio_3_mils,
    [012CPA0008_PV_TEMP_AR_ESTAGIO_3_C] AS pv_temp_ar_estagio_3_c,
    [012CPA0008_PV_NIV_INTERRUPTOR_OLEO_BAR] AS pv_niv_interruptor_oleo_bar,
    [012CPA0008_PV_PRES_VACUO_CX_ENGRAN_inH2O] AS pv_pres_vacuo_cx_engran_inh2o,
    [012CPA0008_PV_TEMP_FASE_A_DO_ESTATOR_C] AS pv_temp_fase_a_do_estator_c,
    [012CPA0008_PV_TEMP_FASE_B_DO_ESTATOR_C] AS pv_temp_fase_b_do_estator_c,
    [012CPA0008_PV_TEMP_FASE_C_DO_ESTATOR_C] AS pv_temp_fase_c_do_estator_c,
    [012CPA0008_PV_TEMP_ROLAMENTO_DIANTEIRO_MOTOR] AS pv_temp_rolamento_dianteiro_motor,
    [012CPA0008_PV_CORR_MOTOR_A] AS pv_corr_motor_a,
    [012CPA0008_PV_POS_ABERT_VALV_ADMISSAO_%] AS pv_pos_abert_valv_admissao_pct,
    [012CPA0008_PV_POS_VALV_BYPASS_%] AS pv_pos_valv_bypass_pct,
    [012CPA0008_PV_POSIÇÃO_ALIVIO%] AS pv_pos_alivio_pct,
    [012CPA0008_ST_OPER] AS st_oper,
    [012CPA0008_PV_HOR_OPERACAO] AS pv_hor_operacao,
    [012CPA0008_PV_HOR_CARREGADA] AS pv_hor_carregada,
    [012CPA0008_PV_NUM_PARTIDAS] AS pv_num_partidas,
    [012CPA0008_ST_CARGA_OPER] AS st_carga_oper,
    [stIntegracao] AS st_integracao,
    [dtIntegracao] AS dt_integracao,
    [dsErro] AS ds_erro,
    [stPontoDeControle] AS st_ponto_de_controle
""".strip()


def build_incremental_query(limit: int | None = None) -> str:
    """Monta a query incremental por timestamp."""

    top_clause = f"TOP ({int(limit)}) " if limit else ""
    return f"""
        SELECT {top_clause}
            {FRIENDLY_SELECT}
        FROM [dbo].[TREND_012CPA0008]
        WHERE [TimeStamp] > ?
        ORDER BY [TimeStamp] ASC;
    """.strip()


def build_recent_window_query(since: datetime, limit: int | None = None) -> str:
    """Monta a query de janela inicial ou recarga de historico."""

    _ = since
    top_clause = f"TOP ({int(limit)}) " if limit else ""
    return f"""
        SELECT {top_clause}
            {FRIENDLY_SELECT}
        FROM [dbo].[TREND_012CPA0008]
        WHERE [TimeStamp] >= ?
        ORDER BY [TimeStamp] ASC;
    """.strip()

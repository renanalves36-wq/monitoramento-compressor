"""Matriz prescritiva simplificada e manutencivel para o TA6000."""

from __future__ import annotations


PRESCRIPTIVE_MATRIX: dict[str, object] = {
    "signals": {
        "pv_temp_oleo_lubrificacao_c": {
            "subsystem": "lubrificacao",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "baixa_eficiencia_oil_cooler",
                "degradacao_oleo",
                "circulacao_oleo_reduzida",
                "inicio_de_problema_em_lubrificacao",
            ],
            "peripheral_hypotheses": [
                "trocador_de_placas_sujo",
                "torre_de_resfriamento_ineficiente",
                "baixa_vazao_de_agua",
                "agua_quente_na_entrada",
                "valvula_de_agua_parcialmente_fechada",
            ],
            "correlation_rules": [
                {
                    "when_all": ["pv_corr_motor_a_estavel", "vibracao_estavel"],
                    "favor": "periferico",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_corr_motor_a_alta", "vibracao_alta"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["temp_ar_estagio_3_alta"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "verificar circuito de agua",
                "verificar trocador de placas e torre de resfriamento",
                "verificar vazao de agua e temperatura de entrada/saida",
                "se persistir, inspecionar oil cooler",
                "avaliar condicao do oleo",
            ],
        },
        "pv_pres_oleo_bar": {
            "subsystem": "lubrificacao",
            "base_criticality": "critica",
            "internal_hypotheses": [
                "falha_na_circulacao_de_oleo",
                "restricao_no_filtro_de_oleo",
                "problema_na_bomba_de_oleo",
                "degradacao_da_lubrificacao",
            ],
            "peripheral_hypotheses": [
                "sensor_descalibrado",
                "erro_de_instrumentacao",
                "problema_eletrico_de_comando_da_bomba",
            ],
            "correlation_rules": [
                {
                    "when_all": ["pv_temp_oleo_lubrificacao_c_alta"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["vibracao_alta"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["delta_filtro_oleo_relevante"],
                    "favor": "interno",
                    "weight": 3,
                },
                {
                    "when_all": ["sem_convergencia_fisica_relevante"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "comparar pressao antes e depois do filtro",
                "verificar filtro de oleo",
                "verificar bomba de oleo",
                "validar sensor e instrumentacao",
                "elevar prioridade se houver vibracao ou aumento de temperatura",
            ],
        },
        "pv_pres_oleo_antes_filtro_bar": {
            "subsystem": "lubrificacao",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "restricao_no_filtro_de_oleo",
                "anomalia_na_bomba_de_oleo",
                "perda_de_carga_anormal_no_circuito",
            ],
            "peripheral_hypotheses": [
                "sensor_inconsistente",
            ],
            "correlation_rules": [
                {
                    "when_all": ["delta_filtro_oleo_relevante"],
                    "favor": "interno",
                    "weight": 3,
                },
                {
                    "when_all": ["pv_temp_oleo_lubrificacao_c_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["sem_convergencia_fisica_relevante"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "calcular diferencial do filtro",
                "verificar data da ultima troca do elemento",
                "programar inspecao/troca do filtro",
                "validar sensor se o comportamento for isolado",
            ],
        },
        "pv_temp_ar_estagio_3_c": {
            "subsystem": "ar_processo",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "baixa_eficiencia_intercooler_aftercooler",
                "drenagem_de_condensado_deficiente",
                "sensor_com_desvio",
            ],
            "peripheral_hypotheses": [
                "agua_quente_no_circuito_externo",
                "baixa_vazao_de_agua",
                "torre_de_resfriamento_ineficiente",
                "trocador_de_placas_sujo",
            ],
            "correlation_rules": [
                {
                    "when_all": ["pv_temp_oleo_lubrificacao_c_alta"],
                    "favor": "periferico",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_corr_motor_a_estavel", "vibracao_estavel"],
                    "favor": "periferico",
                    "weight": 1,
                },
                {
                    "when_all": ["temp_ar_estagio_3_zerada"],
                    "favor": "periferico",
                    "weight": 3,
                    "observation": "tag zerada sugere instrumentacao antes de concluir falha termica real.",
                },
            ],
            "recommended_actions": [
                "verificar temperatura e vazao do coolant",
                "verificar drenos de condensado",
                "verificar circuito externo de resfriamento",
                "validar sensor da temperatura",
                "programar inspecao/limpeza de intercooler/aftercooler se persistir",
            ],
        },
        "pv_vib_estagio_1_mils": {
            "subsystem": "vibracao",
            "base_criticality": "critica",
            "internal_hypotheses": [
                "inicio_de_problema_rotativo",
                "mancal",
                "desalinhamento_interno",
                "efeito_secundario_de_lubrificacao",
            ],
            "peripheral_hypotheses": [
                "vibracao_transmitida_pela_base",
                "problema_no_motor_ou_acoplamento",
                "vibracao_ambiental",
            ],
            "correlation_rules": [
                {
                    "when_all": ["pv_temp_oleo_lubrificacao_c_alta"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_corr_motor_a_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["somente_estagio_1_alto"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["sem_convergencia_fisica_relevante", "vibracao_externa_sugerida"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "comparar vibracoes entre os 3 estagios",
                "correlacionar com temperatura de oleo e corrente",
                "verificar fundacao, alinhamento e acoplamento",
                "abrir inspecao mecanica se a tendencia persistir",
            ],
        },
        "pv_vib_estagio_2_mils": {
            "subsystem": "vibracao",
            "base_criticality": "critica",
            "internal_hypotheses": [
                "problema_rotativo_estagio_2",
                "mancal",
                "desbalanceamento",
                "efeito_de_lubrificacao",
            ],
            "peripheral_hypotheses": [
                "vibracao_externa",
                "acoplamento",
                "fundacao",
            ],
            "correlation_rules": [
                {
                    "when_all": ["pv_temp_oleo_lubrificacao_c_alta", "pv_corr_motor_a_alta"],
                    "favor": "interno",
                    "weight": 3,
                },
                {
                    "when_all": ["oleo_estavel", "pv_corr_motor_a_estavel"],
                    "favor": "periferico",
                    "weight": 1,
                },
                {
                    "when_all": ["estagio_2_mais_critico"],
                    "favor": "interno",
                    "weight": 2,
                },
            ],
            "recommended_actions": [
                "comparar vibracao entre estagios",
                "verificar acoplamento e base",
                "se tendencia persistir, abrir inspecao mecanica",
                "elevar criticidade se crescer rapidamente",
            ],
        },
        "pv_vib_estagio_3_mils": {
            "subsystem": "vibracao",
            "base_criticality": "critica",
            "internal_hypotheses": [
                "problema_rotativo_estagio_3",
                "mancal_relacionado",
                "efeito_termico_local",
            ],
            "peripheral_hypotheses": [
                "vibracao_externa",
                "motor_ou_acoplamento",
            ],
            "correlation_rules": [
                {
                    "when_all": ["temp_ar_estagio_3_alta"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_temp_oleo_lubrificacao_c_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["sem_convergencia_fisica_relevante"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "correlacionar com temperatura do ar do estagio 3",
                "comparar com os outros estagios",
                "validar sensor se o comportamento for isolado",
            ],
        },
        "pv_corr_motor_a": {
            "subsystem": "motor",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "sobrecarga_mecanica_do_compressor",
                "perda_de_eficiencia_interna",
                "problema_em_mancais_ou_atrito",
            ],
            "peripheral_hypotheses": [
                "pressao_de_sistema_elevada",
                "restricao_na_linha_de_descarga",
                "secador_restritivo",
                "problema_eletrico_no_motor",
            ],
            "correlation_rules": [
                {
                    "when_all": ["delta_descarga_sistema_alto"],
                    "favor": "periferico",
                    "weight": 2,
                    "causes": ["pressao_de_sistema_elevada", "restricao_na_linha_de_descarga", "secador_restritivo"],
                },
                {
                    "when_all": ["vibracao_alta"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["bypass_anormal"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["admissao_anormal"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["temperatura_estator_alta"],
                    "favor": "periferico",
                    "weight": 1,
                    "causes": ["problema_eletrico_no_motor"],
                },
            ],
            "recommended_actions": [
                "comparar corrente com pressao de sistema e descarga",
                "verificar secador e linha de descarga",
                "verificar motor, mancais e atrito se houver vibracao associada",
                "avaliar controle/admissao/bypass",
            ],
        },
        "pv_temp_fase_a_do_estator_c": {
            "subsystem": "motor",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "aquecimento_do_motor",
                "sobrecarga",
                "problema_localizado_de_enrolamento",
                "ventilacao_interna_deficiente",
            ],
            "peripheral_hypotheses": [
                "alta_temperatura_ambiente",
                "ventilacao_deficiente_da_sala",
                "problema_eletrico_externo",
            ],
            "correlation_rules": [
                {
                    "when_all": ["fase_a_assimetrica"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_corr_motor_a_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["fases_estator_altas_sem_assimetria"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "comparar A/B/C",
                "verificar ventilacao do ambiente",
                "verificar sobrecarga eletrica",
                "acionar manutencao eletrica se houver assimetria",
            ],
        },
        "pv_temp_fase_b_do_estator_c": {
            "subsystem": "motor",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "aquecimento_do_motor",
                "sobrecarga",
                "problema_localizado_de_enrolamento",
                "ventilacao_interna_deficiente",
            ],
            "peripheral_hypotheses": [
                "alta_temperatura_ambiente",
                "ventilacao_deficiente_da_sala",
                "problema_eletrico_externo",
            ],
            "correlation_rules": [
                {
                    "when_all": ["fase_b_assimetrica"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_corr_motor_a_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["fases_estator_altas_sem_assimetria"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "comparar A/B/C",
                "verificar ventilacao do ambiente",
                "verificar sobrecarga eletrica",
                "acionar manutencao eletrica se houver assimetria",
            ],
        },
        "pv_temp_fase_c_do_estator_c": {
            "subsystem": "motor",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "aquecimento_do_motor",
                "sobrecarga",
                "problema_localizado_de_enrolamento",
                "ventilacao_interna_deficiente",
            ],
            "peripheral_hypotheses": [
                "alta_temperatura_ambiente",
                "ventilacao_deficiente_da_sala",
                "problema_eletrico_externo",
            ],
            "correlation_rules": [
                {
                    "when_all": ["fase_c_assimetrica"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["pv_corr_motor_a_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["fases_estator_altas_sem_assimetria"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "comparar A/B/C",
                "verificar ventilacao do ambiente",
                "verificar sobrecarga eletrica",
                "acionar manutencao eletrica se houver assimetria",
            ],
        },
        "pv_temp_rolamento_dianteiro_motor": {
            "subsystem": "motor",
            "base_criticality": "critica",
            "internal_hypotheses": [
                "problema_no_rolamento",
                "lubrificacao_inadequada_do_motor",
                "desalinhamento",
            ],
            "peripheral_hypotheses": [
                "ventilacao_ambiente_deficiente",
                "sobrecarga_por_processo_externo",
            ],
            "correlation_rules": [
                {
                    "when_all": ["vibracao_alta"],
                    "favor": "interno",
                    "weight": 3,
                },
                {
                    "when_all": ["pv_corr_motor_a_alta"],
                    "favor": "interno",
                    "weight": 1,
                },
                {
                    "when_all": ["temperatura_estator_alta"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "abrir inspecao de rolamento/alinhamento",
                "verificar sobrecarga e ventilacao",
                "elevar prioridade se houver vibracao associada",
            ],
        },
        "pv_pres_sistema_bar": {
            "subsystem": "ar_processo",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "controle_igv_bypass_inadequado",
                "problema_de_logica_de_controle",
                "resposta_anormal_do_compressor",
            ],
            "peripheral_hypotheses": [
                "demanda_da_rede_alterada",
                "restricao_no_secador",
                "restricao_na_linha_de_descarga",
                "check_valve_ou_block_valve_com_problema",
            ],
            "correlation_rules": [
                {
                    "when_all": ["delta_descarga_sistema_alto"],
                    "favor": "periferico",
                    "weight": 3,
                },
                {
                    "when_all": ["bypass_anormal", "admissao_anormal"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["oscilacao_pressao_sistema"],
                    "observation": "ha indicio de instabilidade de rede ou de controle na pressao do sistema.",
                },
            ],
            "recommended_actions": [
                "comparar com pressao de descarga",
                "verificar secador, linha e valvulas downstream",
                "avaliar logica de controle, admissao e bypass",
                "verificar check valve e block valve",
            ],
        },
        "pv_pres_descarga_bar": {
            "subsystem": "ar_processo",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "controle_de_descarga_anormal",
                "atuacao_inadequada_do_bypass",
                "problema_de_logica_de_controle",
            ],
            "peripheral_hypotheses": [
                "secador_restritivo",
                "linha_de_descarga_obstruida",
                "check_valve_com_problema",
                "block_valve_parcialmente_fechada",
            ],
            "correlation_rules": [
                {
                    "when_all": ["delta_descarga_sistema_alto"],
                    "favor": "periferico",
                    "weight": 3,
                },
                {
                    "when_all": ["bypass_anormal", "admissao_anormal"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["alivio_anormal"],
                    "favor": "interno",
                    "weight": 1,
                    "observation": "alivio fora do normal sugere descarregamento, controle ou condicao de rede fora do ponto.",
                },
            ],
            "recommended_actions": [
                "verificar secador e linha de descarga",
                "verificar check valve e block valve",
                "avaliar logica de controle e bypass",
                "comparar com pressao do sistema",
            ],
        },
        "pv_pos_abert_valv_admissao_pct": {
            "subsystem": "controle",
            "base_criticality": "media",
            "internal_hypotheses": [
                "igv_operando_fora_do_padrao",
                "problema_de_atuacao",
                "controle_compensando_condicao_anormal",
            ],
            "peripheral_hypotheses": [
                "filtro_de_admissao_restrito",
                "demanda_externa_anormal",
                "condicao_de_rede",
            ],
            "correlation_rules": [
                {
                    "when_all": ["admissao_anormal", "pressao_sistema_baixa"],
                    "favor": "periferico",
                    "weight": 2,
                },
                {
                    "when_all": ["admissao_anormal", "bypass_anormal"],
                    "favor": "interno",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "comparar com pressoes de sistema e descarga",
                "avaliar filtro de admissao",
                "verificar comportamento do controle/IGV",
            ],
        },
        "pv_pos_valv_bypass_pct": {
            "subsystem": "controle",
            "base_criticality": "media",
            "internal_hypotheses": [
                "bypass_compensando_excesso_de_capacidade",
                "problema_no_atuador",
                "problema_de_logica_de_controle",
            ],
            "peripheral_hypotheses": [
                "demanda_baixa_da_rede",
                "instabilidade_no_sistema_de_ar",
            ],
            "correlation_rules": [
                {
                    "when_all": ["bypass_anormal", "pressao_sistema_baixa"],
                    "favor": "interno",
                    "weight": 2,
                },
                {
                    "when_all": ["modo_baixa_demanda"],
                    "observation": "o modo de carga indica descarregamento ou sem carga, entao a severidade diagnostica deve ser reduzida.",
                },
                {
                    "when_all": ["oscilacao_pressao_sistema"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "inspecionar atuacao do bypass",
                "avaliar logica de unload",
                "verificar demanda da rede",
            ],
        },
        "pv_pos_alivio_pct": {
            "subsystem": "controle",
            "base_criticality": "media",
            "internal_hypotheses": [
                "controle_descarregando_fora_do_ponto",
                "atuacao_anormal",
            ],
            "peripheral_hypotheses": [
                "rede_com_baixa_demanda",
                "restricao_downstream",
                "instabilidade_no_sistema_de_ar",
            ],
            "correlation_rules": [
                {
                    "when_all": ["alivio_anormal", "pressao_descarga_alta"],
                    "favor": "periferico",
                    "weight": 2,
                },
                {
                    "when_all": ["modo_baixa_demanda"],
                    "observation": "ha baixa demanda esperada para o sistema; interpretar alivio com menor severidade.",
                },
                {
                    "when_all": ["alivio_anormal", "bypass_anormal"],
                    "favor": "interno",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "avaliar modo de carga",
                "comparar com bypass e pressao de descarga",
                "verificar rede e downstream",
            ],
        },
        "pv_pres_vacuo_cx_engran_inh2o": {
            "subsystem": "venting_lubrificacao",
            "base_criticality": "alta",
            "internal_hypotheses": [
                "problema_no_venting_do_reservatorio_gearbox",
                "falha_no_ejetor",
                "restricao_no_respiro",
            ],
            "peripheral_hypotheses": [
                "baixa_pressao_do_ar_do_ejetor",
                "falha_no_ar_de_instrumento",
                "erro_de_escala_ou_sensor",
            ],
            "correlation_rules": [
                {
                    "when_all": ["vacuo_cx_engran_inconsistente"],
                    "favor": "periferico",
                    "weight": 3,
                    "causes": ["erro_de_escala_ou_sensor"],
                },
                {
                    "when_all": ["anomalias_lubrificacao_convergentes"],
                    "favor": "interno",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "validar unidade e escala da tag",
                "verificar sensor",
                "verificar alimentacao do ejetor",
                "verificar ar de instrumento",
                "so sugerir inspecao fisica do venting apos validacao da instrumentacao",
            ],
        },
        "pv_niv_interruptor_oleo_bar": {
            "subsystem": "lubrificacao",
            "base_criticality": "critica",
            "internal_hypotheses": [
                "nivel_de_oleo_inadequado",
                "problema_no_sistema_de_lubrificacao",
            ],
            "peripheral_hypotheses": [
                "sensor_chave_defeituoso",
            ],
            "correlation_rules": [
                {
                    "when_all": ["nivel_oleo_estado_anormal", "pv_temp_oleo_lubrificacao_c_alta"],
                    "favor": "interno",
                    "weight": 3,
                },
                {
                    "when_all": ["nivel_oleo_estado_anormal", "pressao_oleo_problematica"],
                    "favor": "interno",
                    "weight": 3,
                },
                {
                    "when_all": ["nivel_oleo_estado_anormal", "sem_convergencia_fisica_relevante"],
                    "favor": "periferico",
                    "weight": 1,
                },
            ],
            "recommended_actions": [
                "verificar status do nivel/interruptor",
                "comparar com pressao e temperatura do oleo",
                "validar sensor/chave",
                "priorizar inspecao do sistema de oleo se houver convergencia de evidencias",
            ],
        },
    },
    "global_rules": [
        {
            "rule_id": "global_temperatura_oleo_periferico",
            "applies_to": ["pv_temp_oleo_lubrificacao_c"],
            "when_all": ["pv_corr_motor_a_estavel", "vibracao_estavel"],
            "favor": "periferico",
            "weight": 2,
            "observation": "corrente e vibracao estaveis deslocam a suspeita para perifericos termicos.",
        },
        {
            "rule_id": "global_vibracao_interno",
            "applies_to": [
                "pv_vib_estagio_1_mils",
                "pv_vib_estagio_2_mils",
                "pv_vib_estagio_3_mils",
            ],
            "when_all": ["pv_temp_oleo_lubrificacao_c_alta", "pv_corr_motor_a_alta"],
            "favor": "interno",
            "weight": 3,
            "observation": "oleo e corrente altos junto com vibracao sugerem mecanismo interno mecanico/lubrificacao.",
        },
        {
            "rule_id": "global_restricao_downstream",
            "applies_to": ["pv_pres_descarga_bar", "pv_pres_sistema_bar"],
            "when_all": ["delta_descarga_sistema_alto"],
            "favor": "periferico",
            "weight": 3,
            "causes": [
                "restricao_na_linha_de_descarga",
                "secador_restritivo",
                "restricao_no_secador",
                "linha_de_descarga_obstruida",
                "check_valve_ou_block_valve_com_problema",
                "check_valve_com_problema",
                "block_valve_parcialmente_fechada",
            ],
        },
        {
            "rule_id": "global_modo_transicao",
            "applies_to": "__all__",
            "when_all": ["modo_transicao"],
            "reduce_confidence": True,
            "observation": "o compressor esta em transicao operacional; manter diagnostico com menor confiabilidade.",
        },
        {
            "rule_id": "global_instrumentacao_suspeita",
            "applies_to": "__all__",
            "when_any": [
                "instrumentacao_suspeita",
                "vacuo_cx_engran_inconsistente",
                "temp_ar_estagio_3_zerada",
            ],
            "reduce_physical_invasive_actions": True,
            "observation": "ha indicios de instrumentacao inconsistente; validar a medicao antes de prescrever intervencao fisica invasiva.",
        },
    ],
}

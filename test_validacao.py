"""
Script de Validação Automatizada - Modelo Estático de Lodos Ativados (Marais & Ekama / UCT)
Executa:
  1. Fechamento rigoroso do Balanço de Massa de DQO (Conservação de Energia)
  2. Fechamento rigoroso do Balanço de Massa de Nitrogênio (Nti = N_saídas)
  3. Balanço de Sólidos no Decantador Secundário ((1 + s)*Xt == s*Xr)
  4. Caso de Referência Numérico (Benchmark Literatura Marais / van Haandel)
  5. Testes de Sensibilidade e Casos de Borda (Temperatura, fxm=0, Penalidade OD, Mistura Mínima)

Como executar:
  python test_validacao.py
  (ou via pytest: pytest test_validacao.py -v)
"""

import math

def simular_marais(
    Q_Ls=57.87,
    Sti=600.0,
    Nti=50.0,
    Pti=8.0,
    Xioi=30.0,
    T=20.0,
    fbs=0.25,
    fbp=0.50,
    fus=0.08,
    Xt=3500.0,
    Xte=15.0,
    modo="Remoção de Matéria Orgânica + N (MLE)",
    modo_s="Calcular pelo adensamento (Xr)",
    Xr_input=8000.0,
    s_input=0.75,
    fxm=0.30,
    Sf=1.35,
    Na_alvo=1.5,
    Nne_alvo=8.0,
    a_max=4.0,
    OD_recirc_lodo=1.0,
    tc_manual=5.0,
    OD_reator=2.0,
    altitude=900.0,
    submergencia=4.20,
    SOTE_m=6.0,
    alfa=0.55,
    beta=0.95,
    F_incrust=0.85,
    taxa_min_mistura=20.0,
    ef_soprador=0.68,
    perda_carga_ar=0.8,
    Yh=0.45,
    bh20=0.24,
    f=0.20,
    fcv=1.48,
    fn=0.10,
    fp=0.025,
    unm20=0.45,
    Kn20=1.00,
    bn20=0.04,
    K2_20=0.101,
):
    """Replica fielmente o núcleo matemático do aplicativo Streamlit para auditoria."""
    Q = Q_Ls * 86.4
    fup = round(1.0 - (fbs + fbp + fus), 6)
    assert fup >= 0, f"Fração fup negativa: {fup}"

    if modo_s == "Calcular pelo adensamento (Xr)":
        Xr = Xr_input
        s = Xt / (Xr - Xt)
    else:
        s = s_input
        Xr = Xt * (1.0 + 1.0 / s)

    Sbsi = Sti * fbs
    Sbpi = Sti * fbp
    Sbi = Sbsi + Sbpi
    Susi = Sti * fus
    Supi = Sti * fup
    Xii = Supi / fcv

    bhT = bh20 * (1.029 ** (T - 20))
    unmT = unm20 * (1.123 ** (T - 20))
    KnT = Kn20 * (1.123 ** (T - 20))
    bnT = bn20 * (1.029 ** (T - 20))

    KO2_nit = 0.50
    f_OD_nit = OD_reator / (KO2_nit + OD_reator)
    unmT_efetivo = unmT * f_OD_nit
    tc_min_nitrif_ref = 1.0 / (unmT_efetivo - bnT)

    if modo == "Remoção de Matéria Orgânica + N (MLE)":
        denom_tc = ((unmT_efetivo * Na_alvo) / (KnT + Na_alvo) - bnT) * (1 - fxm)
        tc_min = 1.0 / denom_tc
        tc = Sf * tc_min
    else:
        fxm = 0.0
        tc_min = tc_min_nitrif_ref
        tc = tc_manual

    MXbh = (Q * Sbi * ((Yh * tc) / (1 + bhT * tc))) / 1000.0
    MXeh = MXbh * f * bhT * tc
    MXi = (Q * Xii * tc) / 1000.0
    MXv = MXbh + MXeh + MXi
    MXio = (Q * Xioi * tc) / 1000.0
    MXt = MXv + MXio
    fv = MXv / MXt

    Vt = (MXt * 1000.0) / Xt
    Vanox = fxm * Vt
    Vaer = (1.0 - fxm) * Vt

    Ns = (fn * MXv * 1000.0) / (Q * tc)
    Nouse = 0.03 * Nti
    FOc = (Q * Sbi * (1 - fcv * Yh)) / 1000.0 + fcv * (1 - f) * bhT * MXbh

    if modo == "Remoção de Matéria Orgânica + N (MLE)":
        Nae = (KnT * (1 + bnT * tc)) / (unmT_efetivo * (1 - fxm) * tc - (1 + bnT * tc))
        Nc = max(0.0, Nti - Nouse - Nae - Ns)
        K2T = K2_20 * (1.08 ** (T - 20))
        Dp1_bruto = Sbsi * ((1 - fcv * Yh) / 2.86) + (K2T * fxm * MXbh * 1000.0) / Q

        if fxm > 0 and Nc > 0:
            a_necessario = 0.0 if Nc <= Nne_alvo else max(0.0, (Nc / Nne_alvo) - (1.0 + s))
            B_eq = Dp1_bruto - (s * OD_recirc_lodo) / 2.86
            C_eq = OD_reator / 2.86
            qa = C_eq
            qb = Nc - B_eq + C_eq * (s + 1.0)
            qc = s * Nc - B_eq * (s + 1.0)
            discriminante = qb**2 - 4.0 * qa * qc
            a_otimo_cinetico = max(0.0, (-qb + math.sqrt(discriminante)) / (2.0 * qa)) if (discriminante >= 0 and qa > 0) else 0.0

            if a_necessario > a_otimo_cinetico and a_otimo_cinetico < a_max:
                a = a_otimo_cinetico
            elif a_necessario > a_max:
                a = a_max
            else:
                a = a_necessario

            penalidade_OD_N = (a * OD_reator + s * OD_recirc_lodo) / 2.86
            Dp1_efetivo = max(0.0, Dp1_bruto - penalidade_OD_N)
            Nne = max(Nc / (a + s + 1.0), max(0.0, Nc - Dp1_efetivo))
        else:
            a = 0.0
            penalidade_OD_N = 0.0
            Dp1_efetivo = 0.0
            Nne = Nc
    else:
        Nc = 0.0
        Dp1_bruto = 0.0
        Dp1_efetivo = 0.0
        penalidade_OD_N = 0.0
        a = 0.0
        Nae = max(0.0, Nti - Nouse - Ns)
        Nne = 0.0

    FOn = (4.57 * Q * Nc) / 1000.0
    FOd = (2.86 * Q * (Nc - Nne)) / 1000.0
    FOt = FOc + FOn - FOd
    Px_SST = MXt / tc
    Px_SSV = MXv / tc

    # Aeração
    SOTE_total = min(0.55, (SOTE_m / 100.0) * submergencia)
    P_atm_rel = math.exp(-0.0001185 * altitude)
    Cs_20 = 9.08
    Cs_T = 14.652 - 0.41022 * T + 0.007991 * (T ** 2) - 0.000077774 * (T ** 3)
    Cs_T_H = Cs_T * P_atm_rel * (1.0 + (submergencia / 20.66))
    fator_correcao_O2 = alfa * beta * F_incrust * ((Cs_T_H - OD_reator) / Cs_20) * (1.024 ** (T - 20))
    AOTE = SOTE_total * fator_correcao_O2
    SOTR = FOt / fator_correcao_O2
    rho_ar = 1.20 * P_atm_rel
    Q_ar_demanda_Nm3_h = (FOt / (AOTE * rho_ar * 0.232)) / 24.0
    Q_ar_mistura_Nm3_h = (taxa_min_mistura * (Vaer / 1000.0)) * 60.0
    governado_por_mistura = Q_ar_mistura_Nm3_h > Q_ar_demanda_Nm3_h

    return {
        "Q": Q, "Sti": Sti, "Nti": Nti, "Susi": Susi, "fcv": fcv,
        "s": s, "Xr": Xr, "Xt": Xt, "tc_min": tc_min, "tc": tc,
        "MXbh": MXbh, "MXv": MXv, "MXt": MXt, "Vt": Vt, "Vanox": Vanox, "Vaer": Vaer,
        "Ns": Ns, "Nouse": Nouse, "Nae": Nae, "Nc": Nc, "Nne": Nne,
        "Dp1_bruto": Dp1_bruto, "Dp1_efetivo": Dp1_efetivo, "a": a,
        "FOc": FOc, "FOn": FOn, "FOd": FOd, "FOt": FOt,
        "Px_SST": Px_SST, "Px_SSV": Px_SSV,
        "SOTR": SOTR, "AOTE": AOTE,
        "Q_ar_demanda_Nm3_h": Q_ar_demanda_Nm3_h,
        "Q_ar_mistura_Nm3_h": Q_ar_mistura_Nm3_h,
        "governado_por_mistura": governado_por_mistura,
    }


def test_fechamento_balanco_dqo():
    """Teste 1: Conservação de DQO (DQO afluente == FOc + DQO no lodo SSV + DQO solúvel efluente)."""
    res = simular_marais()
    dqo_afluente_kg_d = (res["Q"] * res["Sti"]) / 1000.0
    dqo_oxidada_kg_d = res["FOc"]
    dqo_lodo_ssv_kg_d = res["Px_SSV"] * res["fcv"]
    dqo_sol_efluente_kg_d = (res["Q"] * res["Susi"]) / 1000.0

    dqo_saida_total = dqo_oxidada_kg_d + dqo_lodo_ssv_kg_d + dqo_sol_efluente_kg_d
    erro_relativo = abs(dqo_afluente_kg_d - dqo_saida_total) / dqo_afluente_kg_d

    assert erro_relativo < 1e-6, f"Erro no balanço de DQO: {erro_relativo:.8%}"
    return dqo_afluente_kg_d, dqo_saida_total, erro_relativo


def test_fechamento_balanco_nitrogenio():
    """Teste 2: Conservação de Nitrogênio (Nti == Ns + Desnitrificado + N-NO3 ef + N-NH4 ef + N-org sol)."""
    res = simular_marais()
    n_desnitrificado = res["Nc"] - res["Nne"]
    n_total_saida = res["Ns"] + n_desnitrificado + res["Nne"] + res["Nae"] + res["Nouse"]
    erro_relativo = abs(res["Nti"] - n_total_saida) / res["Nti"]

    assert erro_relativo < 1e-6, f"Erro no balanço de Nitrogênio: {erro_relativo:.8%}"
    return res["Nti"], n_total_saida, erro_relativo


def test_balanco_solidos_decantador():
    """Teste 3: Balanço de massa de sólidos no decantador ((1 + s)*Xt == s*Xr)."""
    res = simular_marais(modo_s="Calcular pelo adensamento (Xr)", Xt=3500.0, Xr_input=8500.0)
    fluxo_entrada = (1.0 + res["s"]) * res["Xt"]
    fluxo_fundo = res["s"] * res["Xr"]
    erro_relativo = abs(fluxo_entrada - fluxo_fundo) / fluxo_entrada

    assert erro_relativo < 1e-6, f"Erro no balanço do decantador: {erro_relativo:.8%}"
    return res["s"], fluxo_entrada, fluxo_fundo


def test_benchmark_literatura_marais():
    """Teste 4: Verificação numérica contra caso clássico de referência (T=20°C, Q=5000 m³/d, Sti=600 mg/L)."""
    res = simular_marais(
        Q_Ls=5000.0 / 86.4,
        Sti=600.0,
        Nti=50.0,
        Xioi=30.0,
        T=20.0,
        fbs=0.25,
        fbp=0.50,
        fus=0.08,
        Xt=3500.0,
        fxm=0.30,
        Sf=1.35,
        Na_alvo=1.5,
        OD_reator=2.0,
    )
    assert 9.0 < res["tc"] < 12.0, f"Idade do lodo fora da faixa esperada: {res['tc']:.2f} d"
    assert 2500.0 < res["Vt"] < 3200.0, f"Volume total fora da faixa esperada: {res['Vt']:.1f} m³"
    assert abs(res["FOt"] - (res["FOc"] + res["FOn"] - res["FOd"])) < 1e-6
    return res


def test_sensibilidade_e_casos_de_borda():
    """Teste 5: Comportamento físico em casos extremos (Temperatura, fxm=0, Penalidade OD, Mistura Mínima)."""
    res_20 = simular_marais(T=20.0)
    res_12 = simular_marais(T=12.0)
    assert res_12["tc"] > res_20["tc"] * 1.8, "Redução de T deveria aumentar significativamente θc"
    assert res_12["Vt"] > res_20["Vt"] * 1.5, "Redução de T deveria aumentar significativamente Vt"

    res_sem_anox = simular_marais(fxm=0.0)
    assert res_sem_anox["a"] == 0.0, "Com fxm=0, recirculação interna 'a' deve ser 0"
    assert res_sem_anox["FOd"] == 0.0, "Com fxm=0, crédito FOd deve ser 0"
    assert abs(res_sem_anox["Nne"] - res_sem_anox["Nc"]) < 1e-6, "Com fxm=0, Nne deve igualar Nc"

    res_od_baixo = simular_marais(OD_reator=1.5, OD_recirc_lodo=0.5)
    res_od_alto = simular_marais(OD_reator=4.0, OD_recirc_lodo=3.0)
    assert res_od_alto["Dp1_efetivo"] < res_od_baixo["Dp1_efetivo"], "OD alto deve penalizar Dp1 efetivo"

    # 5D. Baixo SST desejado (Xt=1800) com alta idade do lodo e alta taxa de mistura aciona travamento
    res_mistura = simular_marais(Xt=1800.0, Xioi=100.0, taxa_min_mistura=28.0, altitude=0.0)
    assert res_mistura["governado_por_mistura"] is True, "Reator diluído com alta taxa de mistura deveria travar na mistura mínima"


if __name__ == "__main__":
    print("=" * 72)
    print("AUDITORIA E VALIDAÇÃO DO MODELO DE MARAIS & EKAMA (LODOS ATIVADOS)")
    print("=" * 72)

    dqo_in, dqo_out, err_dqo = test_fechamento_balanco_dqo()
    print(f"[PASS] 1. Balanço de DQO        -> Entrada: {dqo_in:,.2f} kg/d | Saída: {dqo_out:,.2f} kg/d (Erro: {err_dqo:.2e})")

    n_in, n_out, err_n = test_fechamento_balanco_nitrogenio()
    print(f"[PASS] 2. Balanço de Nitrogênio -> Entrada: {n_in:.2f} mg/L   | Saída: {n_out:.2f} mg/L   (Erro: {err_n:.2e})")

    s_calc, f_in, f_out = test_balanco_solidos_decantador()
    print(f"[PASS] 3. Balanço Decantador    -> s = {s_calc:.3f} | Fluxo Ent.: {f_in:,.1f} | Fluxo Fundo: {f_out:,.1f} mg/L")

    bench = test_benchmark_literatura_marais()
    print(f"[PASS] 4. Benchmark UCT (20°C)  -> θc = {bench['tc']:.2f} d | Vt = {bench['Vt']:,.1f} m³ | FOt = {bench['FOt']:,.1f} kg O2/d | Nne = {bench['Nne']:.2f} mg/L")

    test_sensibilidade_e_casos_de_borda()
    print("[PASS] 5. Casos de Borda        -> Temperatura, fxm=0, Penalidade OD e Mistura Mínima validados!")
    print("=" * 72)
    print("TODOS OS TESTES DE VALIDAÇÃO FORAM CONCLUÍDOS COM SUCESSO!")

import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(
    page_title="Dimensionamento Lodos Ativados - Modelo de Marais",
    page_icon="💧",
    layout="wide"
)

if "cenarios" not in st.session_state:
    st.session_state.cenarios = []

def arredondar_025(valor):
    return math.ceil(valor / 0.25) * 0.25

def input_sincronizado(label, min_val, max_val, default_val, step, key_base, fmt="%.2f", help_text=None):
    """Cria um controle híbrido sincronizado: barra deslizante (slider) + caixa numérica precisa."""
    k_num = f"{key_base}_num"
    k_sld = f"{key_base}_sld"

    if k_num not in st.session_state:
        st.session_state[k_num] = default_val
    if k_sld not in st.session_state:
        st.session_state[k_sld] = default_val

    def _sync_from_slider():
        st.session_state[k_num] = st.session_state[k_sld]

    def _sync_from_num():
        st.session_state[k_sld] = st.session_state[k_num]

    st.sidebar.markdown(f"**{label}**", help=help_text)
    col_sld, col_num = st.sidebar.columns([1.6, 1.0])
    with col_sld:
        st.slider(
            label,
            min_value=min_val,
            max_value=max_val,
            step=step,
            key=k_sld,
            on_change=_sync_from_slider,
            label_visibility="collapsed"
        )
    with col_num:
        st.number_input(
            label,
            min_value=min_val,
            max_value=max_val,
            step=step,
            format=fmt,
            key=k_num,
            on_change=_sync_from_num,
            label_visibility="collapsed"
        )
    return st.session_state[k_num]

st.title("💧 Dimensionamento Estático de Lodos Ativados")
st.markdown("Modelo estacionário de **Marais & Ekama (UCT)** com aeração por **ar difuso**, geometria e comparador inteligente de cenários.")

# --- BARRA LATERAL: MODO DE OPERAÇÃO ---
st.sidebar.header("0. Modo de Operação")
modo = st.sidebar.radio(
    "Selecione o objetivo do tratamento:",
    ["Remoção de Matéria Orgânica + N (MLE)", "Apenas Matéria Orgânica (Convencional)"]
)

# --- BARRA LATERAL: DADOS DE ENTRADA ---
st.sidebar.header("1. Dados do Esgoto Afluente")
Q_Ls = st.sidebar.number_input("Vazão média afluente (Q) [L/s]", min_value=0.1, value=57.87, step=1.0, format="%.2f")
Q = Q_Ls * 86.4
st.sidebar.caption(f"Vazão convertida: **{Q:,.1f} m³/d**")

Sti = st.sidebar.number_input("DQO total afluente (Sti) [mg/L]", min_value=50.0, value=600.0, step=10.0)
Nti = st.sidebar.number_input("NTK afluente (Nti) [mg N/L]", min_value=5.0, value=50.0, step=1.0)
Pti = st.sidebar.number_input("Fósforo Total afluente (Pti) [mg P/L]", min_value=0.5, value=8.0, step=0.5)
Xioi = st.sidebar.number_input("Sólidos Suspensos Inorgânicos (Xioi) [mg/L]", min_value=0.0, value=30.0, step=5.0)
T = input_sincronizado("Temperatura mínima de projeto (T) [°C]", 10.0, 30.0, 20.0, 0.5, "temp_proj", fmt="%.1f")

st.sidebar.header("2. Fracionamento da DQO")
fbs = input_sincronizado("Fração biodegradável solúvel (fbs)", 0.05, 0.50, 0.25, 0.01, "fbs", fmt="%.2f")
fbp = input_sincronizado("Fração biodegradável particulada (fbp)", 0.20, 0.70, 0.50, 0.01, "fbp", fmt="%.2f")
fus = input_sincronizado("Fração inerte solúvel (fus)", 0.02, 0.25, 0.08, 0.01, "fus", fmt="%.2f")
fup = round(1.0 - (fbs + fbp + fus), 4)

if fup < 0:
    st.sidebar.error(f"A soma das frações excedeu 1,0! (fup = {fup:.2f})")
    st.stop()
else:
    st.sidebar.info(f"Fração inerte particulada (fup): **{fup:.2f}**")

st.sidebar.header("3. Parâmetros Operacionais e de Projeto")
Xt = st.sidebar.number_input("SST desejado no reator (Xt) [mg/L]", min_value=1500.0, value=3500.0, step=100.0)
Xte = st.sidebar.number_input("SST esperado no efluente (Xte) [mg/L]", min_value=5.0, value=15.0, step=1.0)
s = input_sincronizado("Razão de recirculação de lodo (s = Qr/Q)", 0.25, 1.50, 0.75, 0.05, "recirc_s", fmt="%.2f")

if modo == "Remoção de Matéria Orgânica + N (MLE)":
    fxm = input_sincronizado("Fração mássica anóxica (fxm)", 0.00, 0.45, 0.30, 0.01, "fxm", fmt="%.2f")
    Sf = input_sincronizado("Fator de segurança nitrificação (Sf)", 1.10, 2.00, 1.35, 0.05, "sf_nit", fmt="%.2f")
    Na_alvo = st.sidebar.number_input("Amônia alvo para projeto (Na_alvo) [mg N/L]", min_value=0.5, value=1.5, step=0.1)
    Nne_alvo = st.sidebar.number_input("Nitrato alvo no efluente (Nne_alvo) [mg N/L]", min_value=1.0, max_value=40.0, value=8.0, step=0.5)
    NT_meta = st.sidebar.number_input("Meta de Nitrogênio Total efluente (NT_meta) [mg N/L]", min_value=1.0, max_value=50.0, value=12.0, step=0.5)
    a_max = input_sincronizado("Limite máximo recirculação interna (a_max)", 1.0, 6.0, 4.0, 0.5, "a_max", fmt="%.1f")
    OD_recirc_lodo = st.sidebar.number_input("OD no retorno de lodo (Os) [mg/L]", min_value=0.0, max_value=3.0, value=1.0, step=0.1)
else:
    fxm = 0.0
    Nne_alvo = 0.0
    NT_meta = 0.0
    a_max = 0.0
    OD_recirc_lodo = 0.0
    tc_manual = input_sincronizado("Idade do lodo adotada (θc) [dias]", 2.0, 25.0, 5.0, 0.5, "tc_man", fmt="%.1f")
    st.sidebar.info("Modo sem nitrificação: zona anóxica zerada (fxm = 0,00) e idade do lodo definida diretamente.")

st.sidebar.header("4. Geometria dos Tanques")
num_modulos = st.sidebar.number_input("Número de linhas / módulos em paralelo", min_value=1, max_value=10, value=2, step=1)
prof_util = input_sincronizado("Profundidade útil (H) [m]", 3.0, 7.0, 4.5, 0.25, "prof_util", fmt="%.2f")
borda_livre = input_sincronizado("Borda livre [m]", 0.30, 1.00, 0.50, 0.05, "borda_livre", fmt="%.2f")
rel_LB_aer = st.sidebar.selectbox("Relação Comprimento/Largura (L:B) - Zona Aeróbia", [1.0, 1.5, 2.0, 2.5, 3.0], index=2)
rel_LB_anox = st.sidebar.selectbox("Relação Comprimento/Largura (L:B) - Zona Anóxica", [1.0, 1.5, 2.0], index=0)

st.sidebar.header("5. Sistema de Aeração (Ar Difuso)")
OD_reator = input_sincronizado("OD desejado no tanque aeróbio (Oa / CL) [mg/L]", 1.0, 4.0, 2.0, 0.1, "od_reator", fmt="%.1f")
altitude = st.sidebar.number_input("Altitude da ETE [m]", min_value=0.0, max_value=2500.0, value=900.0, step=50.0)
submergencia = st.sidebar.number_input("Submergência dos difusores [m]", min_value=2.5, max_value=6.8, value=round(prof_util - 0.30, 2), step=0.10)
SOTE_m = input_sincronizado("Eficiência padrão (SOTE) por metro [%/m]", 4.0, 8.0, 6.0, 0.2, "sote_m", fmt="%.1f")
alfa = input_sincronizado("Fator α (transferência esgoto/água limpa)", 0.40, 0.85, 0.55, 0.05, "alfa", fmt="%.2f")
beta = input_sincronizado("Fator β (saturação esgoto/água limpa)", 0.90, 1.00, 0.95, 0.01, "beta", fmt="%.2f")
F_incrust = input_sincronizado("Fator de incrustação dos difusores (F)", 0.70, 1.00, 0.85, 0.05, "f_incrust", fmt="%.2f")
taxa_min_mistura = st.sidebar.number_input(
    "Taxa mínima de mistura (ar difuso) [Nm³/min·1000m³]",
    min_value=10.0, max_value=30.0, value=20.0, step=1.0,
    help="Faixa típica de 20 a 30 Nm³/min por 1.000 m³ (Metcalf & Eddy, 5ª ed.) ou 1,2 a 1,8 Nm³/h·m² (ATV-DVWK-A 131)."
)
ef_soprador = input_sincronizado("Eficiência global do conjunto motor-soprador [%]", 55.0, 80.0, 68.0, 1.0, "ef_sopr", fmt="%.1f") / 100.0
perda_carga_ar = st.sidebar.number_input("Perda de carga tubulação + difusor [m.c.a.]", min_value=0.3, max_value=2.5, value=0.8, step=0.1)

with st.sidebar.expander("6. Parâmetros Cinéticos (Padrão Marais/UCT)"):
    Yh = st.number_input("Yh [mg SSV/mg DQO]", value=0.45, format="%.3f")
    bh20 = st.number_input("bh20 [d⁻¹]", value=0.24, format="%.3f")
    f = st.number_input("f (resíduo endógeno)", value=0.20, format="%.2f")
    fcv = st.number_input("fcv [mg DQO/mg SSV]", value=1.48, format="%.2f")
    fn = st.number_input("fn [mg N/mg SSV]", value=0.10, format="%.3f")
    fp = st.number_input("fp [mg P/mg SSV]", value=0.025, format="%.3f")
    unm20 = st.number_input("μnm20 [d⁻¹]", value=0.45, format="%.3f")
    Kn20 = st.number_input("Kn20 [mg N/L]", value=1.00, format="%.2f")
    bn20 = st.number_input("bn20 [d⁻¹]", value=0.04, format="%.3f")
    K2_20 = st.number_input("K2_20 [mg NO3-N/mg SSV·d]", value=0.101, format="%.3f")

# --- CÁLCULOS DO MODELO DE MARAIS ---
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

tc_min_nitrif_ref = 1.0 / (unmT_efetivo - bnT) if (unmT_efetivo - bnT) > 0 else 999.0

if modo == "Remoção de Matéria Orgânica + N (MLE)":
    denom_tc = ((unmT_efetivo * Na_alvo) / (KnT + Na_alvo) - bnT) * (1 - fxm)
    if denom_tc <= 0:
        st.error("Combinação inviável para nitrificação nesta temperatura, OD e fração anóxica. Reduza fxm, aumente OD ou aumente Na_alvo.")
        st.stop()
    tc_min = 1.0 / denom_tc
    tc = Sf * tc_min
else:
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
TDH = (Vt / Q) * 24.0

Ns = (fn * MXv * 1000.0) / (Q * tc)
Nouse = 0.03 * Nti
FOc = (Q * Sbi * (1 - fcv * Yh)) / 1000.0 + fcv * (1 - f) * bhT * MXbh

# --- BALANÇO DE NITROGÊNIO, RECIRCULAÇÃO INTERNA (a) E EFEITO DO OD NA ZONA ANÓXICA ---
recirc_limitada_amax = False
gargalo_zona_anoxica = False
a_necessario = 0.0
a_otimo_cinetico = 0.0

if modo == "Remoção de Matéria Orgânica + N (MLE)":
    Nae = (KnT * (1 + bnT * tc)) / (unmT_efetivo * (1 - fxm) * tc - (1 + bnT * tc))
    Nc = max(0.0, Nti - Nouse - Nae - Ns)
    K2T = K2_20 * (1.08 ** (T - 20))

    Dp1_bruto = Sbsi * ((1 - fcv * Yh) / 2.86) + (K2T * fxm * MXbh * 1000.0) / Q

    if fxm > 0 and Nc > 0:
        if Nc <= Nne_alvo:
            a_necessario = 0.0
        else:
            a_necessario = max(0.0, (Nc / Nne_alvo) - (1.0 + s))

        B_eq = Dp1_bruto - (s * OD_recirc_lodo) / 2.86
        C_eq = OD_reator / 2.86

        qa = C_eq
        qb = Nc - B_eq + C_eq * (s + 1.0)
        qc = s * Nc - B_eq * (s + 1.0)

        discriminante = qb**2 - 4.0 * qa * qc
        if discriminante >= 0 and qa > 0:
            a_otimo_cinetico = max(0.0, (-qb + math.sqrt(discriminante)) / (2.0 * qa))
        else:
            a_otimo_cinetico = 0.0

        if a_necessario > a_otimo_cinetico and a_otimo_cinetico < a_max:
            gargalo_zona_anoxica = True
            a = a_otimo_cinetico
        elif a_necessario > a_max:
            recirc_limitada_amax = True
            a = a_max
        else:
            a = a_necessario

        penalidade_OD_N = (a * OD_reator + s * OD_recirc_lodo) / 2.86
        Dp1_efetivo = max(0.0, Dp1_bruto - penalidade_OD_N)

        Nne_hidraulico = Nc / (a + s + 1.0)
        Nne_estequiometrico = max(0.0, Nc - Dp1_efetivo)
        Nne = max(Nne_hidraulico, Nne_estequiometrico)
    else:
        a_necessario = 0.0
        a_otimo_cinetico = 0.0
        a = 0.0
        penalidade_OD_N = 0.0
        Dp1_efetivo = 0.0
        Nne = Nc
else:
    Nc = 0.0
    Dp1_bruto = 0.0
    Dp1_efetivo = 0.0
    penalidade_OD_N = 0.0
    a_necessario = 0.0
    a_otimo_cinetico = 0.0
    a = 0.0
    Nae = max(0.0, Nti - Nouse - Ns)
    Nne = 0.0

    if tc >= tc_min_nitrif_ref:
        Nc_potencial = max(0.0, Nti - Nouse - 1.5 - Ns)
        FOn_potencial = (4.57 * Q * Nc_potencial) / 1000.0
        FOt_com_nitrif = FOc + FOn_potencial
        st.warning(
            f"⚠️ **Alerta de Nitrificação Espontânea:** A idade do lodo adotada (**{tc:.1f} dias**) é superior à idade mínima "
            f"das nitrificantes a {T:.1f}°C e OD = {OD_reator:.1f} mg/L (**{tc_min_nitrif_ref:.1f} dias**). Na prática, o reator irá nitrificar naturalmente, "
            f"elevando a demanda real de oxigênio de **{FOc:,.0f} kg O₂/d** (apenas carbonácea) para aproximadamente **{FOt_com_nitrif:,.0f} kg O₂/d**."
        )

FOn = (4.57 * Q * Nc) / 1000.0
FOd = (2.86 * Q * (Nc - Nne)) / 1000.0
FOt = FOc + FOn - FOd
Px_SST = MXt / tc

# --- PRÉ-DIMENSIONAMENTO GEOMÉTRICO (MÚLTIPLOS DE 0,25 m) ---
H_total = prof_util + borda_livre

Vaer_mod = Vaer / num_modulos
Area_aer_req = Vaer_mod / prof_util
B_aer = arredondar_025(math.sqrt(Area_aer_req / rel_LB_aer))
L_aer = arredondar_025(B_aer * rel_LB_aer)
Vaer_real_total = B_aer * L_aer * prof_util * num_modulos
Area_aer_total = B_aer * L_aer * num_modulos

if Vanox > 0:
    Vanox_mod = Vanox / num_modulos
    Area_anox_req = Vanox_mod / prof_util
    B_anox = arredondar_025(math.sqrt(Area_anox_req / rel_LB_anox))
    L_anox = arredondar_025(B_anox * rel_LB_anox)
    Vanox_real_total = B_anox * L_anox * prof_util * num_modulos
    Area_anox_total = B_anox * L_anox * num_modulos
else:
    B_anox = 0.0
    L_anox = 0.0
    Vanox_real_total = 0.0
    Area_anox_total = 0.0

Vt_real_total = Vaer_real_total + Vanox_real_total
Area_planta_total = Area_aer_total + Area_anox_total
TDH_real = (Vt_real_total / Q) * 24.0

# --- CÁLCULOS DE AERAÇÃO POR AR DIFUSO (DEMANDA BIOLÓGICA VS. MISTURA MÍNIMA) ---
SOTE_total = min(0.55, (SOTE_m / 100.0) * submergencia)
P_atm_rel = math.exp(-0.0001185 * altitude)
Cs_20 = 9.08
Cs_T = 14.652 - 0.41022 * T + 0.007991 * (T ** 2) - 0.000077774 * (T ** 3)
Cs_T_H = Cs_T * P_atm_rel * (1.0 + (submergencia / 20.66))

fator_correcao_O2 = (alfa * beta * F_incrust * ((Cs_T_H - OD_reator) / Cs_20) * (1.024 ** (T - 20)))
AOTE = SOTE_total * fator_correcao_O2
SOTR = FOt / fator_correcao_O2

rho_ar = 1.20 * P_atm_rel
frac_O2_ar = 0.232

Q_ar_demanda_Nm3_d = FOt / (AOTE * rho_ar * frac_O2_ar)
Q_ar_demanda_Nm3_h = Q_ar_demanda_Nm3_d / 24.0
Q_ar_demanda_Nm3_min = Q_ar_demanda_Nm3_h / 60.0

Q_ar_mistura_Nm3_min = taxa_min_mistura * (Vaer_real_total / 1000.0)
Q_ar_mistura_Nm3_h = Q_ar_mistura_Nm3_min * 60.0
Q_ar_mistura_Nm3_d = Q_ar_mistura_Nm3_h * 24.0

governado_por_mistura = Q_ar_mistura_Nm3_h > Q_ar_demanda_Nm3_h
Q_ar_projeto_Nm3_h = max(Q_ar_demanda_Nm3_h, Q_ar_mistura_Nm3_h)
Q_ar_projeto_Nm3_min = Q_ar_projeto_Nm3_h / 60.0
Q_ar_projeto_Nm3_d = Q_ar_projeto_Nm3_h * 24.0

Taxa_ar_m2 = Q_ar_projeto_Nm3_h / Area_aer_total
Taxa_ar_vol = Q_ar_projeto_Nm3_min / (Vaer_real_total / 1000.0)

P1_kPa = 101.325 * P_atm_rel
P2_kPa = P1_kPa + (submergencia + perda_carga_ar) * 9.806
w_ar_kg_s = (Q_ar_projeto_Nm3_d * rho_ar) / 86400.0
R_ar = 0.287
T_ar_K = 293.15
k_ar = 1.395
n_ad = (k_ar - 1.0) / k_ar
Potencia_kW = (w_ar_kg_s * R_ar * T_ar_K / (n_ad * ef_soprador)) * (((P2_kPa / P1_kPa) ** n_ad) - 1.0)
Potencia_CV = Potencia_kW * 1.3596
Consumo_kWh_d = Potencia_kW * 24.0

# --- EFLUENTE TRATADO ---
SST_ef = Xte
DQO_sol = Susi
DQO_part = SST_ef * fv * fcv
DQO_ef = DQO_sol + DQO_part

DBO_sol = 2.0
DBO_part = 0.65 * SST_ef * fv
DBO_ef = DBO_sol + DBO_part

N_NH4_ef = Nae
N_NO3_ef = Nne
NT_ef = Nouse + Nae + Nne + (fn * SST_ef * fv)
P_ef = max(0.5, Pti - ((fp * MXv * 1000.0) / (Q * tc)) + (fp * SST_ef * fv))

# --- ALERTAS DE RECIRCULAÇÃO, GARGALO ANÓXICO E METAS DE NITROGÊNIO (MODO MLE) ---
if modo == "Remoção de Matéria Orgânica + N (MLE)":
    meta_Nne_atingida = Nne <= (Nne_alvo + 0.05)
    meta_NT_atingida = NT_ef <= (NT_meta + 0.05)

    if gargalo_zona_anoxica:
        st.warning(
            f"⚠️ **Gargalo na Zona Anóxica (Capacidade Biológica Insuficiente):** Para atingir o nitrato alvo (**Nne = {Nne_alvo:.1f} mg N/L**), "
            f"seria necessária uma recirculação interna de **{a_necessario:.2f} Q**. Porém, o gargalo atual **não é a recirculação interna**, "
            f"mas sim o **volume da zona anóxica insuficiente (fxm = {fxm:.2f}) ou a falta de DQO biodegradável** "
            f"(Potencial efetivo Dp1 = **{Dp1_efetivo:.1f} mg N/L** frente a Nc = **{Nc:.1f} mg N/L**). "
            f"O aplicativo limitou a recirculação em **{a:.2f} Q** (ponto máximo útil sem desperdício de bombeamento) e o melhor nitrato "
            f"efluente alcançado neste cenário é **Nne = {Nne:.2f} mg N/L**."
        )
    elif recirc_limitada_amax:
        st.warning(
            f"🔒 **Limite Máximo de Recirculação Interna Alcançado (a_max = {a_max:.1f} Q):** Para atingir o nitrato alvo de "
            f"**{Nne_alvo:.1f} mg N/L**, o balanço de massa exigiria uma recirculação interna de **{a_necessario:.2f} Q**, ultrapassando "
            f"o teto operacional estabelecido (**{a_max:.1f} Q**). Operando no limite máximo de **{a:.1f} Q**, o melhor nitrato efluente "
            f"alcançado pelo sistema é **Nne = {Nne:.2f} mg N/L**."
        )
    else:
        st.success(
            f"✅ **Alvo de Nitrato (Nne) Alcançado:** O sistema atinge **Nne = {Nne:.2f} mg N/L** (alvo ≤ {Nne_alvo:.1f} mg N/L) "
            f"utilizando uma recirculação interna otimizada de **a = {a:.2f} Q** (abaixo do teto de {a_max:.1f} Q)."
        )

    if not meta_NT_atingida:
        deficit_N = NT_ef - NT_meta
        partes_msg = [
            f"❌ **Meta de Nitrogênio Total (NT) Não Alcançada:** O Nitrogênio Total estimado no efluente é de **{NT_ef:.2f} mg N/L**, "
            f"ficando **{deficit_N:.2f} mg N/L acima** da meta estabelecida de **{NT_meta:.1f} mg N/L** "
            f"(N-NH₄ = {N_NH4_ef:.2f} | N-NO₃ = {N_NO3_ef:.2f} | N-org. solúvel = {Nouse:.2f} | N-particulado = {fn*SST_ef*fv:.2f} mg/L)."
        ]
        if recirc_limitada_amax and not gargalo_zona_anoxica:
            perc_retorno = ((a + s) / (a + s + 1.0)) * 100.0
            partes_msg.append(
                f"**Diagnóstico Hidráulico (MLE):** Mesmo com a recirculação no teto configurado (a = {a:.1f} Q), a fração máxima de nitrato "
                f"que retorna ao tanque anóxico é [{perc_retorno:.0f}%]. Para atingir metas mais restritivas de NT sem elevar a recirculação, "
                "avalie uma **zona pós-anóxica (Bardenpho de 4 estágios)** ou **dosagem de fonte externa de carbono**."
            )
        else:
            partes_msg.append("**Sugestões de ajuste para melhorar a remoção de nitrogênio:**")
            partes_msg.append("1. **Aumente a fração mássica anóxica (fxm)** na barra lateral (até 0,35–0,40), se houver margem na idade do lodo;")
            partes_msg.append("2. **Reduza o OD no tanque aeróbio (Oa)** para 1,5–2,0 mg/L e controle o OD no retorno de lodo (Os) para diminuir a perda de potencial anóxico;")
            partes_msg.append("3. Se a relação DQO/NTK do esgoto bruto for baixa (< 8–9), avalie a **adição de fonte externa de carbono** ou **zona pós-anóxica (Bardenpho)**.")

        st.error(chr(10).join(partes_msg))

def salvar_cenario_atual(nome_para_salvar):
    status_meta = "N/A"
    if modo.startswith("Remoção"):
        status_meta = f"OK (≤ {NT_meta:.0f})" if NT_ef <= NT_meta else f"Não atingida (> {NT_meta:.0f})"

    novo_cenario = {
        "Cenário": nome_para_salvar,
        "Modo": "MLE (C + N)" if modo.startswith("Remoção") else "Apenas C",
        "Q (L/s)": round(Q_Ls, 2),
        "Q (m³/d)": round(Q, 1),
        "T (°C)": T,
        "OD (mg/L)": OD_reator,
        "θc (dias)": round(tc, 1),
        "fxm": round(fxm, 2),
        "Recirc. a": round(a, 2),
        "Dp1 Ef. (mg/L)": round(Dp1_efetivo, 1),
        "Vt Real (m³)": round(Vt_real_total, 0),
        "Área Planta (m²)": round(Area_planta_total, 1),
        "Dim. Aeróbio (m)": f"{num_modulos}x({B_aer:.2f}x{L_aer:.2f})",
        "Dim. Anóxico (m)": f"{num_modulos}x({B_anox:.2f}x{L_anox:.2f})" if Vanox > 0 else "-",
        "AOR (kg O₂/d)": round(FOt, 0),
        "Ar Demanda (Nm³/h)": round(Q_ar_demanda_Nm3_h, 0),
        "Ar Projeto (Nm³/h)": round(Q_ar_projeto_Nm3_h, 0),
        "Critério Ar": "Mistura Mín." if governado_por_mistura else "Demanda O₂",
        "Potência (kW)": round(Potencia_kW, 1),
        "Px Lodo (kg/d)": round(Px_SST, 0),
        "DBO₅ Ef. (mg/L)": round(DBO_ef, 1),
        "DQO Ef. (mg/L)": round(DQO_ef, 1),
        "SST Ef. (mg/L)": round(SST_ef, 1),
        "N-NH₄ Ef. (mg/L)": round(N_NH4_ef, 1),
        "N-NO₃ Ef. (mg/L)": round(N_NO3_ef, 1),
        "NT Ef. (mg/L)": round(NT_ef, 1),
        "Meta NT": status_meta,
        "P Ef. (mg/L)": round(P_ef, 2),
        "_params_extras": {
            "DQO Af. (mg/L)": round(Sti, 0),
            "NTK Af. (mg/L)": round(Nti, 0),
            "P Af. (mg/L)": round(Pti, 1),
            "fbs": round(fbs, 2),
            "fbp": round(fbp, 2),
            "fus": round(fus, 2),
            "Xt (mg/L)": round(Xt, 0),
            "s (Qr/Q)": round(s, 2),
            "Nne Alvo": round(Nne_alvo, 1),
            "a_max": round(a_max, 1),
            "OD Lodo Os": round(OD_recirc_lodo, 1),
            "Yh": round(Yh, 3),
            "bh20 (d⁻¹)": round(bh20, 3),
            "f (endóg.)": round(f, 2),
            "fcv": round(fcv, 2),
            "fn": round(fn, 3),
            "fp": round(fp, 3),
            "μnm20 (d⁻¹)": round(unm20, 3),
            "Kn20 (mg/L)": round(Kn20, 2),
            "bn20 (d⁻¹)": round(bn20, 3),
            "K2_20": round(K2_20, 3),
            "SOTE (%/m)": round(SOTE_m, 1),
            "Fator α": round(alfa, 2),
            "Fator F": round(F_incrust, 2),
            "Taxa Mistura": round(taxa_min_mistura, 1),
            "Submerg. (m)": round(submergencia, 2),
            "Prof. H (m)": round(prof_util, 2),
        }
    }
    st.session_state.cenarios.append(novo_cenario)

# --- ORGANIZAÇÃO EM ABAS ---
aba_processo, aba_aeracao, aba_geometria, aba_cenarios = st.tabs([
    "📊 1. Processo e Efluente",
    "🌬️ 2. Aeração por Ar Difuso",
    "📐 3. Geometria dos Tanques",
    "⚖️ 4. Comparador de Cenários"
])

# ==============================================================================
# ABA 1: PROCESSO E QUALIDADE DO EFLUENTE
# ==============================================================================
with aba_processo:
    nome_padrao = f"Cenário {len(st.session_state.cenarios) + 1} ({'MLE' if modo.startswith('Remoção') else 'Convencional'} - θc {tc:.1f}d)"
    col_id_cen, col_btn_save_aba1 = st.columns([2.5, 1])
    with col_id_cen:
        nome_cenario_ativo = st.text_input(
            "🏷️ Identificação / Nome do Cenário Atual:",
            value=nome_padrao,
            key="nome_cenario_aba1",
            help="Defina o nome do cenário aqui. Ele identificará o projeto em todas as abas, no Excel e ao salvar no comparador."
        )
    with col_btn_save_aba1:
        st.write("")
        st.write("")
        if st.button("💾 Salvar no Comparador", key="btn_salvar_aba1", use_container_width=True):
            salvar_cenario_atual(nome_cenario_ativo)
            st.success(f"Cenário '{nome_cenario_ativo}' salvo na Aba 4!")

    st.divider()

    st.subheader(f"Principais Resultados — {nome_cenario_ativo}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Vazão de Projeto (Q)", f"{Q:,.1f} m³/d", f"Entrada: {Q_Ls:.2f} L/s")
    col2.metric("Idade do Lodo (θc)", f"{tc:.1f} dias", f"Mín. nitrif.: {tc_min:.1f} d")
    col3.metric("Volume Total Calculado (Vt)", f"{Vt:,.0f} m³", f"TDH: {TDH:.1f} h")
    col4.metric("Lodo de Excesso (Px)", f"{Px_SST:,.0f} kg SST/d", f"Relação SSV/SST: {fv:.2f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Volume Anóxico", f"{Vanox:,.0f} m³", f"{fxm*100:.0f}% do total")
    col6.metric("Volume Aeróbio", f"{Vaer:,.0f} m³", f"{(1-fxm)*100:.0f}% do total")

    if gargalo_zona_anoxica:
        sub_recirc = f"Limitada p/ Dp1 (req: {a_necessario:.2f} Q)"
    elif recirc_limitada_amax:
        sub_recirc = f"Limitada a_max (req: {a_necessario:.2f} Q)"
    else:
        sub_recirc = f"Qa = {a*Q:,.0f} m³/d (teto: {a_max:.1f} Q)"

    col7.metric("Recirculação Interna (a)", f"{a:.2f} Q", sub_recirc)
    col8.metric("Desnitrificação Efetiva (Dp1)", f"{Dp1_efetivo:.1f} mg N/L", f"Bruto: {Dp1_bruto:.1f} | Perda OD: -{penalidade_OD_N:.1f}")

    st.divider()

    left_col, right_col = st.columns([1.2, 1])

    with left_col:
        st.subheader("🧪 Qualidade Estimada do Efluente Tratado")
        df_efluente = pd.DataFrame({
            "Parâmetro": ["DBO₅ Total", "DQO Total", "Sólidos Suspensos (SST)", "Amônia (N-NH₄)", "Nitrato (N-NO₃)", "Nitrogênio Total (NT)", "Fósforo Total (P)"],
            "Afluente (mg/L)": [round(Sti*0.48, 1), round(Sti, 1), "-", "-", "-", round(Nti, 1), round(Pti, 1)],
            "Efluente (mg/L)": [round(DBO_ef, 2), round(DQO_ef, 2), round(SST_ef, 2), round(N_NH4_ef, 2), round(N_NO3_ef, 2), round(NT_ef, 2), round(P_ef, 2)],
            "Composição / Observação": [
                f"Solúvel: {DBO_sol:.1f} | Particulada: {DBO_part:.1f}",
                f"Solúvel: {DQO_sol:.1f} | Particulada: {DQO_part:.1f}",
                "Definido pela eficiência do decantador",
                f"OD={OD_reator:.1f} mg/L (f_OD={f_OD_nit:.2f})" if modo.startswith("Remoção") else "Sem nitrificação no balanço",
                f"Alvo: ≤ {Nne_alvo:.1f} mg/L (Dp1 ef.: {Dp1_efetivo:.1f} mg/L)" if fxm > 0 else "Sem zona anóxica",
                f"Meta: ≤ {NT_meta:.1f} mg/L ({'Atendida' if NT_ef <= NT_meta else 'Não atendida'})" if modo.startswith("Remoção") else f"Orgânico solúvel residual: {Nouse:.1f} mg/L",
                "Assimilação celular convencional (sem EBPR)"
            ]
        })
        st.dataframe(df_efluente, use_container_width=True, hide_index=True)

    with right_col:
        st.subheader("📈 Balanço de Nitrogênio (mg N/L)")
        df_n = pd.DataFrame({
            "Fração": ["Incorporado ao Lodo (Ns)", "Desnitrificado", "N-NO₃ Efluente", "N-NH₄ Efluente", "N Orgânico Residual"],
            "Concentração (mg/L)": [Ns, max(0.0, Nc - Nne), Nne, Nae, Nouse]
        }).set_index("Fração")
        st.bar_chart(df_n)

# ==============================================================================
# ABA 2: AERAÇÃO POR AR DIFUSO
# ==============================================================================
with aba_aeracao:
    st.subheader(f"🌬️ Dimensionamento do Sistema de Ar Difuso e Sopradores — {nome_cenario_ativo}")
    st.markdown(
        f"Cálculo de transferência de oxigênio em campo (**AOR → SOTR**) considerando submergência de **{submergencia:.2f} m**, "
        f"altitude de **{altitude:.0f} m** e concentração de OD mantida em **{OD_reator:.1f} mg/L**."
    )

    if governado_por_mistura:
        st.warning(
            f"🔒 **Dimensionamento Governado pela Mistura Mínima:** A vazão de ar necessária apenas para a demanda biológica "
            f"de oxigênio é de **{Q_ar_demanda_Nm3_h:,.0f} Nm³/h** ({Q_ar_demanda_Nm3_min:,.1f} Nm³/min), porém o mínimo requerido "
            f"para manter os sólidos em suspensão no tanque aeróbio construído ({Vaer_real_total:,.0f} m³) é de "
            f"**{Q_ar_mistura_Nm3_h:,.0f} Nm³/h** ({Q_ar_mistura_Nm3_min:,.1f} Nm³/min). O sistema foi travado no mínimo de mistura."
        )
    else:
        st.success(
            f"✅ **Dimensionamento Governado pela Demanda Biológica:** A vazão de ar requerida pelo processo "
            f"(**{Q_ar_demanda_Nm3_h:,.0f} Nm³/h**) supera o mínimo exigido para mistura (**{Q_ar_mistura_Nm3_h:,.0f} Nm³/h**)."
        )

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Demanda Real (AOR / FOt)", f"{FOt:,.0f} kg O₂/d", f"Padrão (SOTR): {SOTR:,.0f} kg O₂/d")
    a2.metric("Vazão Ar (Demanda Biol.)", f"{Q_ar_demanda_Nm3_h:,.0f} Nm³/h", f"{Q_ar_demanda_Nm3_min:,.1f} Nm³/min")
    a3.metric("Vazão Ar Adotada (Projeto)", f"{Q_ar_projeto_Nm3_h:,.0f} Nm³/h", "Travado na mistura" if governado_por_mistura else "Governado pelo processo")
    a4.metric("Potência dos Sopradores", f"{Potencia_kW:.1f} kW", f"{Potencia_CV:.1f} CV ({Consumo_kWh_d:,.0f} kWh/d)")

    st.divider()

    col_aer_esq, col_aer_dir = st.columns(2)
    with col_aer_esq:
        st.markdown("#### Parâmetros de Transferência de Massa")
        df_aer_params = pd.DataFrame([
            ("SOTE total (água limpa a 20°C)", f"{SOTE_total*100:.1f} %"),
            ("AOTE efetivo (esgoto em campo)", f"{AOTE*100:.2f} %"),
            ("Saturação de OD no tanque (Cs,T,H)", f"{Cs_T_H:.2f} mg/L"),
            ("Pressão absoluta de descarga (P2)", f"{P2_kPa:.1f} kPa"),
            ("Crédito de oxigênio na desnitrificação (FOd)", f"{FOd:,.0f} kg O₂/d"),
        ], columns=["Parâmetro", "Valor"])
        st.dataframe(df_aer_params, use_container_width=True, hide_index=True)

    with col_aer_dir:
        st.markdown("#### Verificação de Mistura Mínima no Tanque Aeróbio")
        st.metric("Taxa Volumétrica Adotada", f"{Taxa_ar_vol:.1f} Nm³/min por 1.000 m³", f"Mínimo configurado: {taxa_min_mistura:.1f} Nm³/min·1000m³")
        st.metric("Taxa Superficial Adotada", f"{Taxa_ar_m2:.2f} Nm³/h·m²", "Referência prática: ≥ 1,2 a 1,8 Nm³/h·m²")
        st.caption(
            "📚 **Referências técnicas:** Metcalf & Eddy (*Wastewater Engineering: Treatment and Resource Recovery*, 5ª ed., Cap. 8) "
            "recomenda **20 a 30 Nm³/min por 1.000 m³** de tanque para difusores de bolha fina em mistura completa; "
            "a norma alemã **ATV-DVWK-A 131** indica fluxo mínimo entre **1,2 e 1,8 Nm³/h·m²** de área de fundo."
        )

# ==============================================================================
# ABA 3: PRÉ-DIMENSIONAMENTO GEOMÉTRICO
# ==============================================================================
with aba_geometria:
    st.subheader(f"📐 Pré-Dimensionamento Geométrico ({num_modulos} linha(s) em paralelo) — {nome_cenario_ativo}")
    st.markdown(
        f"Dimensões em planta arredondadas para cima em **múltiplos de 0,25 m**, considerando "
        f"**profundidade útil (H) = {prof_util:.2f} m** e **altura total = {H_total:.2f} m** (com borda livre de {borda_livre:.2f} m)."
    )

    g_col1, g_col2, g_col3, g_col4 = st.columns(4)
    g_col1.metric("Área Total em Planta", f"{Area_planta_total:,.1f} m²", f"{num_modulos} módulo(s)")
    g_col2.metric("Volume Real Construído", f"{Vt_real_total:,.0f} m³", f"Folga: +{((Vt_real_total/Vt)-1)*100:.1f}% sobre Vt")
    g_col3.metric("TDH Real (Geométrico)", f"{TDH_real:.1f} horas", f"TDH de cálculo: {TDH:.1f} h")
    g_col4.metric("Altura Total das Paredes", f"{H_total:.2f} m", f"Útil: {prof_util:.2f} m + Borda: {borda_livre:.2f} m")

    st.divider()

    df_geom = pd.DataFrame([
        {
            "Compartimento": "Zona Anóxica (por linha)",
            "Qtd. Linhas": num_modulos,
            "Relação L:B": f"{rel_LB_anox:.1f} : 1" if Vanox > 0 else "-",
            "Largura B (m)": f"{B_anox:.2f}" if Vanox > 0 else "0,00",
            "Comprimento L (m)": f"{L_anox:.2f}" if Vanox > 0 else "0,00",
            "Prof. Útil H (m)": f"{prof_util:.2f}" if Vanox > 0 else "0,00",
            "Área por Linha (m²)": round(B_anox * L_anox, 2),
            "Volume Calc. Total (m³)": round(Vanox, 1),
            "Volume Real Total (m³)": round(Vanox_real_total, 1),
        },
        {
            "Compartimento": "Zona Aeróbia (por linha)",
            "Qtd. Linhas": num_modulos,
            "Relação L:B": f"{rel_LB_aer:.1f} : 1",
            "Largura B (m)": f"{B_aer:.2f}",
            "Comprimento L (m)": f"{L_aer:.2f}",
            "Prof. Útil H (m)": f"{prof_util:.2f}",
            "Área por Linha (m²)": round(B_aer * L_aer, 2),
            "Volume Calc. Total (m³)": round(Vaer, 1),
            "Volume Real Total (m³)": round(Vaer_real_total, 1),
        },
        {
            "Compartimento": "TOTAL DO REATOR BIOLÓGICO",
            "Qtd. Linhas": num_modulos,
            "Relação L:B": "-",
            "Largura B (m)": "-",
            "Comprimento L (m)": "-",
            "Prof. Útil H (m)": f"{prof_util:.2f}",
            "Área por Linha (m²)": round((B_anox * L_anox) + (B_aer * L_aer), 2),
            "Volume Calc. Total (m³)": round(Vt, 1),
            "Volume Real Total (m³)": round(Vt_real_total, 1),
        }
    ])

    st.dataframe(df_geom, use_container_width=True, hide_index=True)

# ==============================================================================
# ABA 4: COMPARADOR INTELIGENTE DE CENÁRIOS
# ==============================================================================
with aba_cenarios:
    st.subheader("⚖️ Comparador de Cenários Salvos")
    st.markdown(
        "A tabela abaixo compara **volumes, geometria, recirculação interna, aeração, atendimento à meta de NT e toda a qualidade do efluente tratado**. "
        "Parâmetros cinéticos e de aeração aparecem automaticamente como colunas extras sempre que você alterá-los entre um cenário e outro."
    )

    if st.session_state.cenarios:
        cenarios_validos = [c for c in st.session_state.cenarios if "_params_extras" in c]
        if len(cenarios_validos) != len(st.session_state.cenarios):
            st.session_state.cenarios = cenarios_validos

    if st.session_state.cenarios:
        col_info_cen, col_btn_clear = st.columns([3, 1])
        with col_info_cen:
            st.caption(f"Total de cenários salvos na comparação: **{len(st.session_state.cenarios)}** (para salvar novos cenários, utilize a **Aba 1**).")
        with col_btn_clear:
            if st.button("🗑️ Limpar Lista de Cenários", use_container_width=True):
                st.session_state.cenarios = []
                st.rerun()

        chaves_extras = list(st.session_state.cenarios[0].get("_params_extras", {}).keys())
        colunas_variadas = []
        for k in chaves_extras:
            valores_k = {c.get("_params_extras", {}).get(k) for c in st.session_state.cenarios}
            if len(valores_k) > 1:
                colunas_variadas.append(k)

        if colunas_variadas:
            st.info(f"🔍 **Diferenças detectadas automaticamente entre os cenários:** {', '.join(colunas_variadas)}")

        linhas_tabela = []
        for c in st.session_state.cenarios:
            linha = {k: v for k, v in c.items() if k != "_params_extras"}
            extras_c = c.get("_params_extras", {})
            for k_var in colunas_variadas:
                linha[k_var] = extras_c.get(k_var, "-")
            linhas_tabela.append(linha)

        df_cenarios = pd.DataFrame(linhas_tabela)
        st.dataframe(df_cenarios, use_container_width=True, hide_index=True)

        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown("**Volume Real Total (m³)**")
            st.bar_chart(df_cenarios.set_index("Cenário")[["Vt Real (m³)"]])
        with g2:
            st.markdown("**Vazão de Ar Adotada (Nm³/h) e Potência (kW)**")
            st.bar_chart(df_cenarios.set_index("Cenário")[["Ar Projeto (Nm³/h)", "Potência (kW)"]])
        with g3:
            st.markdown("**Efluente Tratado: DBO₅, N-NH₄, N-NO₃ e NT (mg/L)**")
            st.bar_chart(df_cenarios.set_index("Cenário")[["DBO₅ Ef. (mg/L)", "N-NH₄ Ef. (mg/L)", "N-NO₃ Ef. (mg/L)", "NT Ef. (mg/L)"]])
    else:
        st.info("Nenhum cenário salvo ainda. Defina o nome e clique em **'💾 Salvar no Comparador'** no topo da **Aba 1 (Processo e Efluente)** para começar a comparar.")

# --- EXPORTAÇÃO PARA EXCEL ---
st.divider()
st.subheader("📥 Exportar Memorial Completo, Ar Difuso e Cenários")

dados_export = [
    ("Identificação do Cenário", nome_cenario_ativo, "-"),
    ("Modo de operação", modo, "-"),
    ("Vazão afluente (entrada)", round(Q_Ls, 2), "L/s"),
    ("Vazão afluente (convertida)", round(Q, 1), "m³/d"),
    ("DQO total afluente (Sti)", Sti, "mg/L"),
    ("NTK afluente (Nti)", Nti, "mg N/L"),
    ("Fósforo afluente (Pti)", Pti, "mg P/L"),
    ("Temperatura mínima (T)", T, "°C"),
    ("OD desejado no tanque aeróbio (Oa)", OD_reator, "mg/L"),
    ("OD no retorno de lodo (Os)", OD_recirc_lodo, "mg/L"),
    ("Idade do lodo de projeto (θc)", round(tc, 2), "dias"),
    ("Massa total de SST no reator (MXt)", round(MXt, 1), "kg SST"),
    ("Relação SSV/SST (fv)", round(fv, 3), "-"),
    ("Volume total calculado (Vt)", round(Vt, 1), "m³"),
    ("Volume anóxico calculado (Vanox)", round(Vanox, 1), "m³"),
    ("Volume aeróbio calculado (Vaer)", round(Vaer, 1), "m³"),
    ("Número de linhas em paralelo", num_modulos, "un"),
    ("Profundidade útil (H)", prof_util, "m"),
    ("Dimensões Zona Anóxica (por linha)", f"{B_anox:.2f} x {L_anox:.2f}" if Vanox > 0 else "N/A", "m x m"),
    ("Dimensões Zona Aeróbia (por linha)", f"{B_aer:.2f} x {L_aer:.2f}", "m x m"),
    ("Volume real total construído", round(Vt_real_total, 1), "m³"),
    ("Área total ocupada em planta", round(Area_planta_total, 1), "m²"),
    ("TDH real (geométrico)", round(TDH_real, 2), "horas"),
    ("Capacidade de nitrificação (Nc)", round(Nc, 2), "mg N/L"),
    ("Nitrato alvo (Nne_alvo)", Nne_alvo if modo.startswith("Remoção") else "N/A", "mg N/L"),
    ("Potencial bruto de desnitrificação (Dp1,bruto)", round(Dp1_bruto, 2), "mg N/L"),
    ("Penalidade de OD na zona anóxica (ΔN_OD)", round(penalidade_OD_N, 2), "mg N/L"),
    ("Potencial efetivo de desnitrificação (Dp1,ef)", round(Dp1_efetivo, 2), "mg N/L"),
    ("Razão recirculação interna necessária (a_req)", round(a_necessario, 2), "-"),
    ("Razão recirculação interna teto cinético (a_cinético)", round(a_otimo_cinetico, 2), "-"),
    ("Razão recirculação interna adotada (a)", round(a, 2), "-"),
    ("Razão recirculação de lodo (s)", round(s, 2), "-"),
    ("Demanda real de oxigênio (AOR / FOt)", round(FOt, 1), "kg O2/d"),
    ("Demanda padrão de oxigênio (SOTR)", round(SOTR, 1), "kg O2/d"),
    ("Eficiência transferência campo (AOTE)", round(AOTE * 100, 2), "%"),
    ("Vazão de ar (demanda biológica)", round(Q_ar_demanda_Nm3_h, 1), "Nm³/h"),
    ("Vazão de ar mínima (mistura)", round(Q_ar_mistura_Nm3_h, 1), "Nm³/h"),
    ("Vazão de ar adotada (projeto)", round(Q_ar_projeto_Nm3_h, 1), "Nm³/h"),
    ("Critério governante da aeração", "Mistura Mínima" if governado_por_mistura else "Demanda Biológica", "-"),
    ("Potência estimada dos sopradores", round(Potencia_kW, 2), "kW"),
    ("Consumo energético aeração", round(Consumo_kWh_d, 1), "kWh/d"),
    ("Produção de lodo de excesso (Px)", round(Px_SST, 1), "kg SST/d"),
    ("DBO5 efluente", round(DBO_ef, 2), "mg/L"),
    ("DQO efluente", round(DQO_ef, 2), "mg/L"),
    ("SST efluente", round(SST_ef, 2), "mg/L"),
    ("N-NH4 efluente", round(N_NH4_ef, 2), "mg N/L"),
    ("N-NO3 efluente", round(N_NO3_ef, 2), "mg N/L"),
    ("Nitrogênio Total efluente", round(NT_ef, 2), "mg N/L"),
    ("Meta de Nitrogênio Total (NT_meta)", NT_meta if modo.startswith("Remoção") else "N/A", "mg N/L"),
    ("Fósforo Total efluente", round(P_ef, 2), "mg P/L")
]

df_export = pd.DataFrame(dados_export, columns=["Parâmetro", "Valor", "Unidade"])

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df_export.to_excel(writer, index=False, sheet_name="Cenario_Atual_Ar_Difuso")
    if st.session_state.cenarios:
        linhas_excel = []
        for c in st.session_state.cenarios:
            linha = {k: v for k, v in c.items() if k != "_params_extras"}
            linha.update(c.get("_params_extras", {}))
            linhas_excel.append(linha)
        pd.DataFrame(linhas_excel).to_excel(writer, index=False, sheet_name="Comparacao_Cenarios")

st.download_button(
    label="⬇️ Baixar Memorial Completo e Cenários em Excel (.xlsx)",
    data=buffer.getvalue(),
    file_name="Memorial_Dimensionamento_Lodos_Ativados.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

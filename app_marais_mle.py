import streamlit as st
import pandas as pd
import math
import io

st.set_page_config(
    page_title="Dimensionamento Lodos Ativados - Modelo de Marais",
    page_icon="💧",
    layout="wide"
)

# Inicializa memória da sessão para comparação de cenários
if "cenarios" not in st.session_state:
    st.session_state.cenarios = []

def arredondar_025(valor):
    return math.ceil(valor / 0.25) * 0.25

st.title("💧 Dimensionamento Estático de Lodos Ativados")
st.markdown("Modelo estacionário de **Marais & Ekama (UCT)** para remoção de matéria orgânica, nitrogênio e pré-dimensionamento geométrico.")

# --- BARRA LATERAL: MODO DE OPERAÇÃO ---
st.sidebar.header("0. Modo de Operação")
modo = st.sidebar.radio(
    "Selecione o objetivo do tratamento:",
    ["Remoção de Matéria Orgânica + N (MLE)", "Apenas Matéria Orgânica (Convencional)"]
)

# --- BARRA LATERAL: DADOS DE ENTRADA ---
st.sidebar.header("1. Dados do Esgoto Afluente")
Q = st.sidebar.number_input("Vazão média afluente (Q) [m³/d]", min_value=10.0, value=5000.0, step=100.0)
Sti = st.sidebar.number_input("DQO total afluente (Sti) [mg/L]", min_value=50.0, value=600.0, step=10.0)
Nti = st.sidebar.number_input("NTK afluente (Nti) [mg N/L]", min_value=5.0, value=50.0, step=1.0)
Pti = st.sidebar.number_input("Fósforo Total afluente (Pti) [mg P/L]", min_value=0.5, value=8.0, step=0.5)
Xioi = st.sidebar.number_input("Sólidos Suspensos Inorgânicos (Xioi) [mg/L]", min_value=0.0, value=30.0, step=5.0)
T = st.sidebar.slider("Temperatura mínima de projeto (T) [°C]", min_value=10.0, max_value=30.0, value=20.0, step=0.5)

st.sidebar.header("2. Fracionamento da DQO")
fbs = st.sidebar.slider("Fração biodegradável solúvel (fbs)", 0.05, 0.50, 0.25, 0.01)
fbp = st.sidebar.slider("Fração biodegradável particulada (fbp)", 0.20, 0.70, 0.50, 0.01)
fus = st.sidebar.slider("Fração inerte solúvel (fus)", 0.02, 0.25, 0.08, 0.01)
fup = round(1.0 - (fbs + fbp + fus), 4)

if fup < 0:
    st.sidebar.error(f"A soma das frações excedeu 1,0! (fup = {fup:.2f})")
    st.stop()
else:
    st.sidebar.info(f"Fração inerte particulada (fup): **{fup:.2f}**")

st.sidebar.header("3. Parâmetros Operacionais e de Projeto")
Xt = st.sidebar.number_input("SST desejado no reator (Xt) [mg/L]", min_value=1500.0, value=3500.0, step=100.0)
Xte = st.sidebar.number_input("SST esperado no efluente (Xte) [mg/L]", min_value=5.0, value=15.0, step=1.0)
s = st.sidebar.slider("Razão de recirculação de lodo (s = Qr/Q)", 0.25, 1.50, 0.75, 0.05)

if modo == "Remoção de Matéria Orgânica + N (MLE)":
    fxm = st.sidebar.slider("Fração mássica anóxica (fxm)", 0.00, 0.45, 0.30, 0.01)
    Sf = st.sidebar.slider("Fator de segurança nitrificação (Sf)", 1.10, 2.00, 1.35, 0.05)
    Na_alvo = st.sidebar.number_input("Amônia alvo para projeto (Na_alvo) [mg N/L]", min_value=0.5, value=1.5, step=0.1)
else:
    fxm = 0.0
    tc_manual = st.sidebar.slider("Idade do lodo adotada (θc) [dias]", 2.0, 25.0, 5.0, 0.5)
    st.sidebar.info("Modo sem nitrificação: zona anóxica zerada (fxm = 0,00) e idade do lodo definida diretamente.")

st.sidebar.header("4. Geometria dos Tanques")
num_modulos = st.sidebar.number_input("Número de linhas / módulos em paralelo", min_value=1, max_value=10, value=2, step=1)
prof_util = st.sidebar.slider("Profundidade útil (H) [m]", min_value=3.0, max_value=7.0, value=4.5, step=0.25)
borda_livre = st.sidebar.slider("Borda livre [m]", min_value=0.30, max_value=1.00, value=0.50, step=0.05)
rel_LB_aer = st.sidebar.selectbox("Relação Comprimento/Largura (L:B) - Zona Aeróbia", [1.0, 1.5, 2.0, 2.5, 3.0], index=2)
rel_LB_anox = st.sidebar.selectbox("Relação Comprimento/Largura (L:B) - Zona Anóxica", [1.0, 1.5, 2.0], index=0)

with st.sidebar.expander("Parâmetros Cinéticos (Padrão Marais/UCT)"):
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

tc_min_nitrif_ref = 1.0 / (unmT - bnT) if (unmT - bnT) > 0 else 999.0

if modo == "Remoção de Matéria Orgânica + N (MLE)":
    denom_tc = ((unmT * Na_alvo) / (KnT + Na_alvo) - bnT) * (1 - fxm)
    if denom_tc <= 0:
        st.error("Combinação inviável para nitrificação nesta temperatura e fração anóxica. Reduza fxm ou aumente Na_alvo.")
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

if modo == "Remoção de Matéria Orgânica + N (MLE)":
    Nae = (KnT * (1 + bnT * tc)) / (unmT * (1 - fxm) * tc - (1 + bnT * tc))
    Nc = max(0.0, Nti - Nouse - Nae - Ns)
    K2T = K2_20 * (1.08 ** (T - 20))
    Dp1 = Sbsi * ((1 - fcv * Yh) / 2.86) + (K2T * fxm * MXbh * 1000.0) / Q
    if fxm > 0:
        a_calc = (Nc / max(2.0, Nc - Dp1)) - (1.0 + s)
        a = min(4.0, max(1.0, a_calc))
        Nne = Nc / (a + s + 1.0)
    else:
        a = 0.0
        Nne = Nc
else:
    Nc = 0.0
    Dp1 = 0.0
    a = 0.0
    Nae = max(0.0, Nti - Nouse - Ns)
    Nne = 0.0

    if tc >= tc_min_nitrif_ref:
        Nc_potencial = max(0.0, Nti - Nouse - 1.5 - Ns)
        FOn_potencial = (4.57 * Q * Nc_potencial) / 1000.0
        FOt_com_nitrif = FOc + FOn_potencial
        st.warning(
            f"⚠️ **Alerta de Nitrificação Espontânea:** A idade do lodo adotada (**{tc:.1f} dias**) é superior à idade mínima "
            f"das nitrificantes a {T:.1f}°C (**{tc_min_nitrif_ref:.1f} dias**). Na prática, o reator irá nitrificar naturalmente, "
            f"elevando a demanda real de oxigênio de **{FOc:,.0f} kg O₂/d** (apenas carbonácea) para aproximadamente "
            f"**{FOt_com_nitrif:,.0f} kg O₂/d** (com nitrificação). Considere esse valor ao dimensionar os aeradores."
        )

FOn = (4.57 * Q * Nc) / 1000.0
FOd = (2.86 * Q * (Nc - Nne)) / 1000.0
FOt = FOc + FOn - FOd
Px_SST = MXt / tc

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

# --- PRÉ-DIMENSIONAMENTO GEOMÉTRICO (MÚLTIPLOS DE 0,25 m) ---
H_total = prof_util + borda_livre

# Zona Aeróbia por módulo
Vaer_mod = Vaer / num_modulos
Area_aer_req = Vaer_mod / prof_util
B_aer_calc = math.sqrt(Area_aer_req / rel_LB_aer)
B_aer = arredondar_025(B_aer_calc)
L_aer = arredondar_025(B_aer * rel_LB_aer)
Vaer_real_mod = B_aer * L_aer * prof_util
Vaer_real_total = Vaer_real_mod * num_modulos
Area_aer_total = B_aer * L_aer * num_modulos

# Zona Anóxica por módulo
if Vanox > 0:
    Vanox_mod = Vanox / num_modulos
    Area_anox_req = Vanox_mod / prof_util
    B_anox_calc = math.sqrt(Area_anox_req / rel_LB_anox)
    B_anox = arredondar_025(B_anox_calc)
    L_anox = arredondar_025(B_anox * rel_LB_anox)
    Vanox_real_mod = B_anox * L_anox * prof_util
    Vanox_real_total = Vanox_real_mod * num_modulos
    Area_anox_total = B_anox * L_anox * num_modulos
else:
    Vanox_mod = 0.0
    B_anox = 0.0
    L_anox = 0.0
    Vanox_real_mod = 0.0
    Vanox_real_total = 0.0
    Area_anox_total = 0.0

Vt_real_total = Vaer_real_total + Vanox_real_total
Area_planta_total = Area_aer_total + Area_anox_total
TDH_real = (Vt_real_total / Q) * 24.0

# --- ORGANIZAÇÃO EM ABAS ---
aba_processo, aba_geometria, aba_cenarios = st.tabs([
    "📊 1. Processo e Qualidade do Efluente",
    "📐 2. Pré-Dimensionamento Geométrico",
    "⚖️ 3. Comparador de Cenários"
])

# ==============================================================================
# ABA 1: PROCESSO E QUALIDADE DO EFLUENTE
# ==============================================================================
with aba_processo:
    st.subheader("Principais Resultados do Dimensionamento Biológico")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Idade do Lodo (θc)", f"{tc:.1f} dias", f"Mín. nitrif.: {tc_min:.1f} d")
    col2.metric("Volume Total Calculado (Vt)", f"{Vt:,.0f} m³", f"TDH: {TDH:.1f} h")
    col3.metric("Demanda Total O₂ (FOt)", f"{FOt:,.0f} kg/d", f"Crédito Desnit: {FOd:,.0f} kg/d")
    col4.metric("Lodo de Excesso (Px)", f"{Px_SST:,.0f} kg SST/d", f"Relação SSV/SST: {fv:.2f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Volume Anóxico", f"{Vanox:,.0f} m³", f"{fxm*100:.0f}% do total")
    col6.metric("Volume Aeróbio", f"{Vaer:,.0f} m³", f"{(1-fxm)*100:.0f}% do total")
    col7.metric("Recirculação Interna (a)", f"{a:.2f} Q", f"Vazão Qa: {a*Q:,.0f} m³/d")
    col8.metric("Recirculação de Lodo (s)", f"{s:.2f} Q", f"Vazão Qr: {s*Q:,.0f} m³/d")

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
                "Equilíbrio cinético" if modo.startswith("Remoção") else "Sem nitrificação no balanço",
                f"Potencial desnitrificação Dp1: {Dp1:.1f} mg/L" if fxm > 0 else "Sem zona anóxica",
                f"Orgânico solúvel residual: {Nouse:.1f} mg/L",
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
# ABA 2: PRÉ-DIMENSIONAMENTO GEOMÉTRICO
# ==============================================================================
with aba_geometria:
    st.subheader(f"📐 Pré-Dimensionamento Geométrico ({num_modulos} linha(s) em paralelo)")
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

    st.info(
        f"💡 **Resumo construtivo por linha:** Cada uma das **{num_modulos} linha(s)** terá "
        + (f"um tanque anóxico de **{B_anox:.2f} m × {L_anox:.2f} m** seguido de " if Vanox > 0 else "")
        + f"um tanque aeróbio de **{B_aer:.2f} m × {L_aer:.2f} m**, totalizando **{Area_planta_total:,.1f} m²** de área útil ocupada."
    )

# ==============================================================================
# ABA 3: COMPARADOR DE CENÁRIOS
# ==============================================================================
with aba_cenarios:
    st.subheader("⚖️ Salvar e Comparar Diferentes Cenários de Projeto")
    st.markdown("Configure os parâmetros na barra lateral e salve cada simulação abaixo para comparar volumes, área ocupada, demanda de oxigênio e efluente.")

    col_nome, col_btn_add, col_btn_clear = st.columns([2, 1, 1])
    with col_nome:
        nome_padrao = f"Cenário {len(st.session_state.cenarios) + 1} ({'MLE' if modo.startswith('Remoção') else 'Convencional'} - θc {tc:.1f}d)"
        nome_cenario = st.text_input("Nome do cenário para salvar:", value=nome_padrao)

    with col_btn_add:
        st.write("")
        st.write("")
        if st.button("➕ Adicionar Cenário", use_container_width=True):
            novo_cenario = {
                "Cenário": nome_cenario,
                "Modo": "MLE (C + N)" if modo.startswith("Remoção") else "Apenas C",
                "Q (m³/d)": round(Q, 0),
                "T (°C)": T,
                "θc (dias)": round(tc, 1),
                "fxm": round(fxm, 2),
                "Vt Calc. (m³)": round(Vt, 0),
                "Vt Real (m³)": round(Vt_real_total, 0),
                "Área Planta (m²)": round(Area_planta_total, 1),
                "Dim. Aeróbio (m)": f"{num_modulos}x({B_aer:.2f}x{L_aer:.2f})",
                "Dim. Anóxico (m)": f"{num_modulos}x({B_anox:.2f}x{L_anox:.2f})" if Vanox > 0 else "-",
                "FOt O₂ (kg/d)": round(FOt, 0),
                "Px Lodo (kg/d)": round(Px_SST, 0),
                "DBO₅ Ef. (mg/L)": round(DBO_ef, 1),
                "N-NH₄ Ef. (mg/L)": round(N_NH4_ef, 1),
                "N-NO₃ Ef. (mg/L)": round(N_NO3_ef, 1),
                "NT Ef. (mg/L)": round(NT_ef, 1),
            }
            st.session_state.cenarios.append(novo_cenario)
            st.success(f"'{nome_cenario}' adicionado à comparação!")

    with col_btn_clear:
        st.write("")
        st.write("")
        if st.button("🗑️ Limpar Lista", use_container_width=True):
            st.session_state.cenarios = []
            st.rerun()

    if st.session_state.cenarios:
        df_cenarios = pd.DataFrame(st.session_state.cenarios)
        st.dataframe(df_cenarios, use_container_width=True, hide_index=True)

        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown("**Volume Real Total (m³)**")
            st.bar_chart(df_cenarios.set_index("Cenário")[["Vt Real (m³)"]])
        with g2:
            st.markdown("**Área Ocupada em Planta (m²)**")
            st.bar_chart(df_cenarios.set_index("Cenário")[["Área Planta (m²)"]])
        with g3:
            st.markdown("**Demanda de Oxigênio (kg O₂/d)**")
            st.bar_chart(df_cenarios.set_index("Cenário")[["FOt O₂ (kg/d)"]])
    else:
        st.info("Nenhum cenário salvo ainda. Clique em **'➕ Adicionar Cenário'** acima para começar a comparar.")

# --- EXPORTAÇÃO PARA EXCEL (SEMPRE VISÍVEL NO RODAPÉ) ---
st.divider()
st.subheader("📥 Exportar Memorial de Cálculo, Geometria e Cenários")

dados_export = [
    ("Modo de operação", modo, "-"),
    ("Vazão afluente (Q)", Q, "m³/d"),
    ("DQO total afluente (Sti)", Sti, "mg/L"),
    ("NTK afluente (Nti)", Nti, "mg N/L"),
    ("Fósforo afluente (Pti)", Pti, "mg P/L"),
    ("Temperatura mínima (T)", T, "°C"),
    ("Idade do lodo de projeto (θc)", round(tc, 2), "dias"),
    ("Massa total de SST no reator (MXt)", round(MXt, 1), "kg SST"),
    ("Relação SSV/SST (fv)", round(fv, 3), "-"),
    ("Volume total calculado (Vt)", round(Vt, 1), "m³"),
    ("Volume anóxico calculado (Vanox)", round(Vanox, 1), "m³"),
    ("Volume aeróbio calculado (Vaer)", round(Vaer, 1), "m³"),
    ("Número de linhas em paralelo", num_modulos, "un"),
    ("Profundidade útil (H)", prof_util, "m"),
    ("Altura total com borda livre", H_total, "m"),
    ("Dimensões Zona Anóxica (por linha)", f"{B_anox:.2f} x {L_anox:.2f}" if Vanox > 0 else "N/A", "m x m"),
    ("Dimensões Zona Aeróbia (por linha)", f"{B_aer:.2f} x {L_aer:.2f}", "m x m"),
    ("Volume real total construído", round(Vt_real_total, 1), "m³"),
    ("Área total ocupada em planta", round(Area_planta_total, 1), "m²"),
    ("TDH real (geométrico)", round(TDH_real, 2), "horas"),
    ("Capacidade de nitrificação (Nc)", round(Nc, 2), "mg N/L"),
    ("Potencial de desnitrificação (Dp1)", round(Dp1, 2), "mg N/L"),
    ("Razão recirculação interna (a)", round(a, 2), "-"),
    ("Razão recirculação de lodo (s)", round(s, 2), "-"),
    ("Demanda total de oxigênio (FOt)", round(FOt, 1), "kg O2/d"),
    ("Produção de lodo de excesso (Px)", round(Px_SST, 1), "kg SST/d"),
    ("DBO5 efluente", round(DBO_ef, 2), "mg/L"),
    ("DQO efluente", round(DQO_ef, 2), "mg/L"),
    ("SST efluente", round(SST_ef, 2), "mg/L"),
    ("N-NH4 efluente", round(N_NH4_ef, 2), "mg N/L"),
    ("N-NO3 efluente", round(N_NO3_ef, 2), "mg N/L"),
    ("Nitrogênio Total efluente", round(NT_ef, 2), "mg N/L"),
    ("Fósforo Total efluente", round(P_ef, 2), "mg P/L")
]

df_export = pd.DataFrame(dados_export, columns=["Parâmetro", "Valor", "Unidade"])

buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df_export.to_excel(writer, index=False, sheet_name="Cenario_Atual_e_Geometria")
    if st.session_state.cenarios:
        pd.DataFrame(st.session_state.cenarios).to_excel(writer, index=False, sheet_name="Comparacao_Cenarios")

st.download_button(
    label="⬇️ Baixar Memorial Completo e Cenários em Excel (.xlsx)",
    data=buffer.getvalue(),
    file_name="Memorial_Dimensionamento_Lodos_Ativados.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

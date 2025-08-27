import streamlit as st
import requests
import re
from pathlib import Path
import time
import datetime
import io
import csv

URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/"
URL_OPEN_CNPJA = "https://open.cnpja.com/office/"

st.set_page_config(page_title="Consulta CNPJ - Adapta", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    .stApp { background-color: #1A1A1A; color: #EEEEEE; }
    h1, h2, h3, h4, h5, h6 { color: #FFC300; }
    .stTextInput label { color: #FFC300; }
    .stTextInput div[data-baseweb="input"] > div { background-color: #333333; color: #EEEEEE; border: 1px solid #FFC300; }
    .stTextInput div[data-baseweb="input"] > div:focus-within { border-color: #FFD700; box-shadow: 0 0 0 0.1rem rgba(255,195,0,.25); }
    .stButton > button { background-color: #FFC300; color: #1A1A1A; border:none; padding:10px 20px; border-radius:5px; font-weight:700; }
    .stButton > button:hover { background-color:#FFD700; color:#000000; }
    .stExpander { background-color:#333333; border:1px solid #FFC300; border-radius:5px; padding:10px; margin-bottom:10px; }
    hr { border-top:1px solid #444444; }
</style>
""", unsafe_allow_html=True)

IMAGE_DIR = Path(__file__).resolve().parent.parent / "images"

def only_digits(s: str) -> str:
    return re.sub(r'[^0-9]', '', s or "")

def format_currency_brl(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return "N/A"

def format_phone(ddd, num):
    return f"({ddd}) {num}" if ddd and num else "N/A"

def format_cnpj_mask(cnpj: str) -> str:
    c = only_digits(cnpj)
    return f"{c[0:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:14]}" if len(c) == 14 else cnpj

# ---------- matriz utils ----------
def calcular_digitos_verificadores_cnpj(cnpj_base_12_digitos: str) -> str:
    pesos_12 = [5,4,3,2,9,8,7,6,5,4,3,2]
    pesos_13 = [6,5,4,3,2,9,8,7,6,5,4,3,2]
    def dv(base, pesos):
        s = sum(int(base[i]) * pesos[i] for i in range(len(base)))
        r = s % 11
        return '0' if r < 2 else str(11 - r)
    d13 = dv(cnpj_base_12_digitos[:12], pesos_12)
    d14 = dv(cnpj_base_12_digitos[:12] + d13, pesos_13)
    return d13 + d14

def to_matriz_if_filial(cnpj_clean: str) -> str:
    if len(cnpj_clean) != 14:
        return cnpj_clean
    if cnpj_clean[8:12] != "0001":
        raiz = cnpj_clean[:8]
        base12 = raiz + "0001"
        dvs = calcular_digitos_verificadores_cnpj(base12)
        return base12 + dvs
    return cnpj_clean

# ---------- consultas (white-label) ----------
@st.cache_data(ttl=3600, show_spinner=False)
def consulta_brasilapi_cnpj(cnpj_limpo: str):
    try:
        r = requests.get(f"{URL_BRASILAPI_CNPJ}{cnpj_limpo}", timeout=15)
        if r.status_code in (400, 404):
            return {"__error": "not_found"}
        if r.status_code in (429, 500, 502, 503, 504):
            return {"__error": "unavailable"}
        r.raise_for_status()
        return r.json()
    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
        return {"__error": "unavailable"}
    except requests.exceptions.HTTPError:
        return {"__error": "unavailable"}
    except Exception:
        return {"__error": "unavailable"}

@st.cache_data(ttl=3600, show_spinner=False)
def consulta_ie_open_cnpja(cnpj_limpo: str, max_retries: int = 2):
    url = f"{URL_OPEN_CNPJA}{cnpj_limpo}"
    attempt = 0
    while True:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                regs = data.get("registrations", []) if isinstance(data, dict) else []
                ies = []
                for reg in regs:
                    ies.append({
                        "uf": (reg or {}).get("state"),
                        "numero": (reg or {}).get("number"),
                        "habilitada": (reg or {}).get("enabled"),
                        "status_texto": ((reg or {}).get("status") or {}).get("text"),
                        "tipo_texto": ((reg or {}).get("type") or {}).get("text"),
                    })
                return ies
            if resp.status_code == 404:
                return []
            if resp.status_code == 429 and attempt < max_retries:
                time.sleep(2 * (attempt + 1)); attempt += 1; continue
            return None
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            return None
        except Exception:
            return None

# ---------- regime unificado + badges ----------
def determinar_regime_unificado(dados_cnpj: dict) -> str:
    is_mei = dados_cnpj.get("opcao_pelo_mei")
    if is_mei: return "MEI"
    is_simples = dados_cnpj.get("opcao_pelo_simples")
    if is_simples: return "SIMPLES NACIONAL"
    regimes = dados_cnpj.get("regime_tributario") or []
    if regimes:
        current_year = datetime.date.today().year
        anos = [r.get("ano") for r in regimes if isinstance(r.get("ano"), int)]
        if anos:
            candidatos = [a for a in anos if a <= current_year]
            alvo = max(candidatos) if candidatos else max(anos)
            regime_alvo = next((r for r in reversed(regimes) if r.get("ano") == alvo), regimes[-1])
            forma = (regime_alvo or {}).get("forma_de_tributacao", "N/A")
            return str(forma).upper()
        forma = (regimes[-1] or {}).get("forma_de_tributacao", "N/A")
        return str(forma).upper()
    return "N/A"

def badge_cor_regime(regime: str):
    r = (regime or "").upper()
    if "MEI" in r: return "#FB923C", "#111111"        # laranja
    if "SIMPLES" in r: return "#FACC15", "#111111"    # amarelo
    if "LUCRO REAL" in r: return "#3B82F6", "#FFFFFF" # azul
    if "LUCRO PRESUMIDO" in r: return "#22C55E", "#111111" # verde
    return "#EF4444", "#FFFFFF"                       # vermelho

def render_badge(texto: str, bg: str, fg: str):
    st.markdown(
        f"""<div style="display:inline-block;padding:8px 12px;border-radius:999px;font-weight:800;letter-spacing:.3px;background:{bg};color:{fg};">
            {texto}
        </div>""",
        unsafe_allow_html=True
    )

def render_regime_badge(regime: str):
    bg, fg = badge_cor_regime(regime)
    render_badge(regime, bg, fg)

# ---------- Situação Cadastral (normalizada + bolinhas) ----------
def normalizar_situacao_cadastral(txt: str) -> str:
    """
    Normaliza para: ATIVO / INAPTO / SUSPENSO / BAIXADO / N/A
    Aceita variações 'ATIVA', 'SUSPENSA', etc.
    """
    s = (txt or "").strip().upper()
    if not s:
        return "N/A"
    if "ATIV" in s:       return "ATIVO"
    if "INAPT" in s:      return "INAPTO"
    if "SUSP" in s:       return "SUSPENSO"
    if "BAIX" in s:       return "BAIXADO"
    return s

def render_situacao_badge(label: str, valor: str):
    s = (valor or "N/A").upper()
    if s == "ATIVO":
        icon, txt = "🟢", "Ativo"
    elif s == "INAPTO":
        icon, txt = "🟡", "Inapto"
    elif s == "SUSPENSO":
        icon, txt = "🟠", "Suspenso"
    elif s == "BAIXADO":
        icon, txt = "🔴", "Baixado"
    else:
        icon, txt = "⚪", (valor.title() if valor else "N/A")
    st.write(f"**{label}:** {icon} {txt}")

# ---------- Helpers CSV ----------
def join_ies_for_csv(ies_list):
    """
    Concatena IEs em uma única string amigável para CSV.
    Formato de cada bloco: "UF: XX | IE: 123 | Habilitada: Sim/Não | Status: ... | Tipo: ..."
    Separador entre blocos: " || "
    """
    if not ies_list:
        return ""
    blocks = []
    for ie in ies_list:
        uf = ie.get("uf") or ""
        numero = ie.get("numero") or ""
        habil = "Sim" if ie.get("habilitada") else "Não"
        status_txt = ie.get("status_texto") or ""
        tipo_txt = ie.get("tipo_texto") or ""
        blocks.append(f"UF: {uf} | IE: {numero} | Habilitada: {habil} | Status: {status_txt} | Tipo: {tipo_txt}")
    return " || ".join(blocks)

def build_csv_bytes(row_dict: dict, field_order: list) -> bytes:
    """
    Gera um CSV (em bytes) com uma única linha usando os campos na ordem especificada.
    """
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=field_order, extrasaction="ignore")
    writer.writeheader()
    writer.writerow({k: ("" if row_dict.get(k) is None else str(row_dict.get(k))) for k in field_order})
    return buf.getvalue().encode("utf-8-sig")  # BOM p/ Excel PT-BR

# ---------- UI ----------
st.image(str(IMAGE_DIR / "logo_main.png"), width=150)
st.markdown("<h1 style='text-align: center;'>Consulta de CNPJ</h1>", unsafe_allow_html=True)

cnpj_input = st.text_input(
    "Digite o CNPJ (apenas números, ou com pontos, barras e traços):",
    placeholder="Ex: 00.000.000/0000-00 ou 00000000000000",
    help="Serão aceitos CNPJs com ou sem formatação. Ex: 21746980000146 ou 21.746.980/0001-46"
)

if st.button("Consultar CNPJ"):
    if not cnpj_input:
        st.warning("Por favor, digite um CNPJ para consultar.")
    else:
        cnpj_limpo = only_digits(cnpj_input)
        if len(cnpj_limpo) != 14:
            st.error("CNPJ inválido. Um CNPJ deve conter exatamente 14 dígitos numéricos.")
        else:
            with st.spinner(f"Consultando CNPJ {format_cnpj_mask(cnpj_limpo)}..."):
                dados_cnpj = consulta_brasilapi_cnpj(cnpj_limpo)

                if isinstance(dados_cnpj, dict) and dados_cnpj.get("__error") == "not_found":
                    st.error("CNPJ inválido ou não encontrado. Verifique os dígitos e tente novamente.")
                    st.stop()
                if isinstance(dados_cnpj, dict) and dados_cnpj.get("__error") == "unavailable":
                    st.error("Serviço temporariamente indisponível. Tente novamente em alguns instantes.")
                    st.stop()
                if not isinstance(dados_cnpj, dict) or "cnpj" not in dados_cnpj:
                    st.error("Não foi possível concluir a consulta no momento.")
                    st.stop()

                st.success(f"Dados encontrados para o CNPJ: {format_cnpj_mask(dados_cnpj.get('cnpj','N/A'))}")
                st.image(str(IMAGE_DIR / "logo_resultado.png"), width=100)

                # ======== Situação Cadastral (normaliza já aqui p/ uso no título) ========
                sit_raw = dados_cnpj.get('descricao_situacao_cadastral', 'N/A')
                sit_norm = normalizar_situacao_cadastral(sit_raw)

                # ======== RAZÃO SOCIAL – destaque acima do regime (com BAIXADO no título) ========
                razao = dados_cnpj.get('razao_social', 'N/A')
                if sit_norm == "BAIXADO":
                    razao_exibida = f"{razao} - (BAIXADO)"
                else:
                    razao_exibida = razao

                st.markdown(
                    f"<div style='text-align:center; font-size: 1.6rem; font-weight: 800; color: #FFC300; margin: 6px 0 2px 0;'>{razao_exibida}</div>",
                    unsafe_allow_html=True
                )

                # ======== 1) REGIME TRIBUTÁRIO via MATRIZ ========
                st.markdown("---")
                st.markdown("## Regime Tributário")

                cnpj_matriz = to_matriz_if_filial(cnpj_limpo)
                regime_source = dados_cnpj
                if cnpj_matriz != cnpj_limpo:
                    dados_matriz = consulta_brasilapi_cnpj(cnpj_matriz)
                    if isinstance(dados_matriz, dict) and not dados_matriz.get("__error") and "cnpj" in dados_matriz:
                        regime_source = dados_matriz

                regime_final = determinar_regime_unificado(regime_source)
                render_regime_badge(regime_final)

                # ======== 1.1) REFORMA TRIBUTÁRIA — badges em construção ========
                st.write("")
                render_badge("Situação do Fornecedor para crédito de CBS e IBS: Em construção", "#FACC15", "#111111")
                if regime_final.upper() == "SIMPLES NACIONAL":
                    st.write("")
                    render_badge("Regime do Simples (Regular ou Normal): Em construção", "#FACC15", "#111111")

                # ======== 2) DADOS DA EMPRESA ========
                st.markdown("---")
                st.markdown("## Dados da Empresa")
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Razão Social:** {razao}")
                    st.write(f"**Nome Fantasia:** {dados_cnpj.get('nome_fantasia', 'N/A')}")
                    st.write(f"**CNPJ:** {format_cnpj_mask(dados_cnpj.get('cnpj', 'N/A'))}")

                    # Situação Cadastral (bolinhas)
                    render_situacao_badge("Situação Cadastral", sit_norm)

                    st.write(f"**Data Início Atividade:** {dados_cnpj.get('data_inicio_atividade', 'N/A')}")
                    st.write(f"**CNAE Fiscal:** {dados_cnpj.get('cnae_fiscal_descricao', 'N/A')} ({dados_cnpj.get('cnae_fiscal', 'N/A')})")
                    st.write(f"**Porte:** {dados_cnpj.get('porte', 'N/A')}")
                with col2:
                    st.write(f"**Natureza Jurídica:** {dados_cnpj.get('natureza_juridica', 'N/A')}")
                    st.write(f"**Capital Social:** {format_currency_brl(dados_cnpj.get('capital_social', 0))}")
                    st.write(f"**Telefone:** {format_phone(dados_cnpj.get('ddd_telefone_1'), dados_cnpj.get('telefone_1'))}")
                    tel2 = format_phone(dados_cnpj.get('ddd_telefone_2'), dados_cnpj.get('telefone_2'))
                    if tel2 != "N/A":
                        st.write(f"**Telefone 2:** {tel2}")
                    st.write(f"**Email:** {dados_cnpj.get('email', 'N/A')}")

                # ======== 3) ENDEREÇO ========
                st.markdown("---")
                st.markdown("## Endereço")
                st.write(f"**Logradouro:** {dados_cnpj.get('descricao_tipo_de_logradouro', '')} {dados_cnpj.get('logradouro', 'N/A')}, {dados_cnpj.get('numero', 'N/A')}")
                if dados_cnpj.get('complemento'):
                    st.write(f"**Complemento:** {dados_cnpj.get('complemento', 'N/A')}")
                st.write(f"**Bairro:** {dados_cnpj.get('bairro', 'N/A')}")
                st.write(f"**Município:** {dados_cnpj.get('municipio', 'N/A')}")
                st.write(f"**UF:** {dados_cnpj.get('uf', 'N/A')}")
                st.write(f"**CEP:** {dados_cnpj.get('cep', 'N/A')}")

                # ======== 4) QSA ========
                if dados_cnpj.get('qsa'):
                    st.markdown("---")
                    st.markdown("## Quadro de Sócios e Administradores (QSA)")
                    for i, socio in enumerate(dados_cnpj['qsa']):
                        with st.expander(f"Sócio/Adm {i+1}: {socio.get('nome_socio', 'N/A')}"):
                            st.write(f"**Nome:** {socio.get('nome_socio', 'N/A')}")
                            st.write(f"**Qualificação:** {socio.get('qualificacao_socio', 'N/A')}")
                            st.write(f"**Data de Entrada:** {socio.get('data_entrada_sociedade', 'N/A')}")
                            st.write(f"**CNPJ/CPF do Sócio:** {socio.get('cnpj_cpf_do_socio', 'N/A')}")
                            if socio.get('nome_representante_legal'):
                                st.write(f"**Representante Legal:** {socio.get('nome_representante_legal', 'N/A')}")
                                st.write(f"**CPF do Representante Legal:** {socio.get('cpf_representante_legal', 'N/A')}")
                                st.write(f"**Qualificação do Representante:** {socio.get('qualificacao_representante_legal', 'N/A')}")
                else:
                    st.info("Não há informações de QSA disponíveis.")

                # ======== 5) CNAEs Secundários ========
                st.markdown("---")
                st.markdown("## CNAEs Secundários")
                if dados_cnpj.get('cnaes_secundarios'):
                    for cnae in dados_cnpj['cnaes_secundarios']:
                        st.markdown(f"- **{cnae.get('codigo', 'N/A')}**: {cnae.get('descricao', 'N/A')}")
                else:
                    st.info("Nenhum CNAE secundário encontrado para este CNPJ.")

                # ======== 6) Inscrições Estaduais (open.cnpja) ========
                st.markdown("---")
                st.markdown("## Inscrições Estaduais")
                ies = consulta_ie_open_cnpja(cnpj_limpo)
                if ies is None:
                    st.warning("Não foi possível recuperar as Inscrições Estaduais no momento.")
                elif len(ies) == 0:
                    st.info("Nenhuma Inscrição Estadual encontrada para este CNPJ.")
                else:
                    for idx, ie in enumerate(ies, start=1):
                        titulo = f"IE {idx} - {ie.get('uf') or 'UF N/A'}"
                        with st.expander(titulo):
                            st.write(f"**UF:** {ie.get('uf', 'N/A')}")
                            st.write(f"**Inscrição Estadual:** {ie.get('numero', 'N/A')}")
                            habilitada = ie.get('habilitada', False)
                            st.write(f"**Habilitada:** {'Sim' if habilitada else 'Não'}")
                            st.write(f"**Status:** {ie.get('status_texto', 'N/A')}")
                            st.write(f"**Tipo:** {ie.get('tipo_texto', 'N/A')}")

                # ======== 7) EXPORTAÇÃO CSV ========
                st.markdown("---")
                st.subheader("Exportação")
                # monta linha para CSV com nomes de colunas legíveis
                cnae_cod = dados_cnpj.get('cnae_fiscal', '')
                cnae_desc = dados_cnpj.get('cnae_fiscal_descricao', '')
                tel1 = format_phone(dados_cnpj.get('ddd_telefone_1'), dados_cnpj.get('telefone_1'))
                tel2 = format_phone(dados_cnpj.get('ddd_telefone_2'), dados_cnpj.get('telefone_2'))
                csv_row = {
                    "CNPJ": format_cnpj_mask(dados_cnpj.get('cnpj', '')),
                    "Razão Social": razao,
                    "Nome Fantasia": dados_cnpj.get('nome_fantasia', ''),
                    "Situação Cadastral": sit_norm.title() if sit_norm != "N/A" else "",
                    "Regime Tributário": regime_final,
                    "Data Início Atividade": dados_cnpj.get('data_inicio_atividade', ''),
                    "CNAE Fiscal Código": cnae_cod if cnae_cod is not None else "",
                    "CNAE Fiscal Descrição": cnae_desc if cnae_desc is not None else "",
                    "Porte": dados_cnpj.get('porte', ''),
                    "Natureza Jurídica": dados_cnpj.get('natureza_juridica', ''),
                    "Capital Social": dados_cnpj.get('capital_social', ''),  # valor bruto p/ CSV
                    "Email": dados_cnpj.get('email', ''),
                    "Telefone 1": "" if tel1 == "N/A" else tel1,
                    "Telefone 2": "" if tel2 == "N/A" else tel2,
                    "Logradouro": f"{dados_cnpj.get('descricao_tipo_de_logradouro','') or ''} {dados_cnpj.get('logradouro','') or ''}".strip(),
                    "Número": dados_cnpj.get('numero', ''),
                    "Complemento": dados_cnpj.get('complemento', ''),
                    "Bairro": dados_cnpj.get('bairro', ''),
                    "Município": dados_cnpj.get('municipio', ''),
                    "UF": dados_cnpj.get('uf', ''),
                    "CEP": dados_cnpj.get('cep', ''),
                    "Inscrições Estaduais": join_ies_for_csv(ies) if ies else "",
                    "Data/Hora da Consulta": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                csv_cols = [
                    "CNPJ","Razão Social","Nome Fantasia","Situação Cadastral","Regime Tributário",
                    "Data Início Atividade","CNAE Fiscal Código","CNAE Fiscal Descrição","Porte",
                    "Natureza Jurídica","Capital Social","Email","Telefone 1","Telefone 2",
                    "Logradouro","Número","Complemento","Bairro","Município","UF","CEP",
                    "Inscrições Estaduais","Data/Hora da Consulta"
                ]
                csv_bytes = build_csv_bytes(csv_row, csv_cols)
                st.download_button(
                    label="📤 Exportar CSV",
                    data=csv_bytes,
                    file_name=f"CNPJ_{only_digits(dados_cnpj.get('cnpj',''))}.csv",
                    mime="text/csv",
                    help="Baixa um CSV com todas as informações principais deste CNPJ"
                )

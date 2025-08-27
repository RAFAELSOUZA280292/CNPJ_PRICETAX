import streamlit as st
import requests
import re
from pathlib import Path
import time
import datetime  # <— novo

# =========================
# Config da página / tema
# =========================
URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/"
URL_OPEN_CNPJA = "https://open.cnpja.com/office/"

st.set_page_config(
    page_title="Consulta CNPJ - Adapta",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# =========================
# CSS (igual ao primeiro app)
# =========================
st.markdown("""
<style>
    .stApp { background-color: #1A1A1A; color: #EEEEEE; }
    h1, h2, h3, h4, h5, h6 { color: #FFC300; }
    .stTextInput label { color: #FFC300; }
    .stTextInput div[data-baseweb="input"] > div {
        background-color: #333333; color: #EEEEEE; border: 1px solid #FFC300;
    }
    .stTextInput div[data-baseweb="input"] > div:focus-within {
        border-color: #FFD700; box-shadow: 0 0 0 0.1rem rgba(255, 195, 0, 0.25);
    }
    .stButton > button {
        background-color: #FFC300; color: #1A1A1A; border: none; padding: 10px 20px;
        border-radius: 5px; font-weight: bold; transition: background-color .3s ease;
    }
    .stButton > button:hover { background-color: #FFD700; color: #000000; }
    .stExpander { background-color: #333333; border: 1px solid #FFC300; border-radius: 5px;
        padding: 10px; margin-bottom: 10px; }
    hr { border-top: 1px solid #444444; }
</style>
""", unsafe_allow_html=True)

# =========================
# Caminho de imagens (mesmo padrão)
# =========================
IMAGE_DIR = Path(__file__).resolve().parent.parent / "images"

# =========================
# Utilidades
# =========================
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

# =========================
# BrasilAPI (dados principais)
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def consulta_brasilapi_cnpj(cnpj_limpo: str):
    r = requests.get(f"{URL_BRASILAPI_CNPJ}{cnpj_limpo}", timeout=15)
    r.raise_for_status()
    return r.json()

# =========================
# open.cnpja (SOMENTE IE)
# =========================
@st.cache_data(ttl=3600, show_spinner=False)
def consulta_ie_open_cnpja(cnpj_limpo: str, max_retries: int = 2):
    """
    Busca SOMENTE as inscrições estaduais no open.cnpja.
    Retorna lista de dicts padronizada, [] se não houver, ou None em falha.
    """
    url = f"{URL_OPEN_CNPJA}{cnpj_limpo}"
    attempt = 0
    while True:
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
        elif resp.status_code == 429 and attempt < max_retries:
            time.sleep(2 * (attempt + 1))
            attempt += 1
            continue
        elif resp.status_code == 404:
            return []
        else:
            return None

# =========================
# Cabeçalho
# =========================
st.image(str(IMAGE_DIR / "logo_main.png"), width=150)
st.markdown("<h1 style='text-align: center;'>Consulta de CNPJ</h1>", unsafe_allow_html=True)

# =========================
# Entrada
# =========================
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
                try:
                    dados_cnpj = consulta_brasilapi_cnpj(cnpj_limpo)

                    if not isinstance(dados_cnpj, dict) or "cnpj" not in dados_cnpj:
                        st.error("CNPJ não encontrado ou resposta inesperada da BrasilAPI.")
                    else:
                        st.success(f"Dados encontrados para o CNPJ: {format_cnpj_mask(dados_cnpj.get('cnpj','N/A'))}")
                        st.image(str(IMAGE_DIR / "logo_resultado.png"), width=100)

                        # ======== 1) REGIME TRIBUTÁRIO (no topo, só o ano mais recente) ========
                        st.markdown("---")
                        st.markdown("## Regime Tributário")
                        regimes = dados_cnpj.get('regime_tributario') or []
                        if not regimes:
                            st.info("Não há informações de Regime Tributário disponíveis para este CNPJ.")
                        else:
                            # pega o ano mais recente disponível (de preferência <= ano atual)
                            current_year = datetime.date.today().year
                            anos = [r.get("ano") for r in regimes if isinstance(r.get("ano"), int)]
                            if not anos:
                                # fallback: mostra a primeira forma se não tiver ano válido
                                forma = (regimes[-1] or {}).get("forma_de_tributacao", "N/A")
                                st.write(f"**Forma de Tributação:** {str(forma).upper()} (BASEADO EM N/A)")
                            else:
                                candidatos = [a for a in anos if a <= current_year]
                                alvo = max(candidatos) if candidatos else max(anos)
                                # pega o último regime que tenha esse ano
                                regime_alvo = next((r for r in reversed(regimes) if r.get("ano") == alvo), regimes[-1])
                                forma = (regime_alvo or {}).get("forma_de_tributacao", "N/A")
                                st.write(f"**Forma de Tributação:** {str(forma).upper()} (BASEADO EM {alvo})")

                        # ======== 2) DADOS DA EMPRESA ========
                        st.markdown("---")
                        st.markdown("## Dados da Empresa")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Razão Social:** {dados_cnpj.get('razao_social', 'N/A')}")
                            st.write(f"**Nome Fantasia:** {dados_cnpj.get('nome_fantasia', 'N/A')}")
                            st.write(f"**CNPJ:** {format_cnpj_mask(dados_cnpj.get('cnpj', 'N/A'))}")
                            st.write(f"**Situação Cadastral:** {dados_cnpj.get('descricao_situacao_cadastral', 'N/A')}")
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
                            st.write(f"**Opção pelo Simples:** {'Sim' if dados_cnpj.get('opcao_pelo_simples') else ('Não' if dados_cnpj.get('opcao_pelo_simples') is False else 'N/A')}")
                            st.write(f"**Opção pelo MEI:** {'Sim' if dados_cnpj.get('opcao_pelo_mei') else ('Não' if dados_cnpj.get('opcao_pelo_mei') is False else 'N/A')}")

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
                        if dados_cnpj.get('cnaes_secundarios'):
                            st.markdown("---")
                            st.markdown("## CNAEs Secundários")
                            for cnae in dados_cnpj['cnaes_secundarios']:
                                st.markdown(f"- **{cnae.get('codigo', 'N/A')}**: {cnae.get('descricao', 'N/A')}")
                        else:
                            st.info("Não há CNAEs secundários informados.")

                        # ======== 6) Inscrições Estaduais ========
                        st.markdown("---")
                        st.markdown("## Inscrições Estaduais")
                        ies = consulta_ie_open_cnpja(cnpj_limpo)
                        if ies is None:
                            st.warning("Não foi possível consultar as IEs no momento.")
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

                except requests.exceptions.Timeout:
                    st.error("Tempo limite da requisição excedido. Tente novamente mais tarde.")
                except requests.exceptions.ConnectionError:
                    st.error("Erro de conexão: verifique sua internet ou a disponibilidade das APIs.")
                except requests.exceptions.HTTPError as e:
                    st.error(f"Erro HTTP: {e}.")
                except Exception as e:
                    st.error(f"Ocorreu um erro inesperado: {e}")

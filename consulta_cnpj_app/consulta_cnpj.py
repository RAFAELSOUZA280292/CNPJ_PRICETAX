import streamlit as st
import requests
import re # Usado para limpar o CNPJ de caracteres não numéricos

# --- Configuração da Aplicação ---
SENHA_ACESSO = "Ivana_2025"
URL_BRASILAPI_CNPJ = "https://brasilapi.com.br/api/cnpj/v1/"

# --- Configuração da Página e Estilo (Cores Personalizadas) ---
st.set_page_config(
    page_title="Consulta CNPJ - Adapta",
    layout="centered", # Centraliza o conteúdo para melhor visualização
    initial_sidebar_state="collapsed" # Não exibe a sidebar inicialmente
)

# Injeção de CSS personalizado para as cores: Amarelo Riqueza, Cinza e Preto
st.markdown(f"""
<style>
    /* Cor de Fundo Principal da Aplicação - Muito Escuro / Quase Preto */
    .stApp {{
        background-color: #1A1A1A; /* Quase preto */
        color: #EEEEEE; /* Cinza claro para o texto principal */
    }}

    /* Títulos (h1 a h6) */
    h1, h2, h3, h4, h5, h6 {{
        color: #FFC300; /* Amarelo Riqueza */
    }}

    /* Estilo dos Labels e Inputs de Texto */
    .stTextInput label {{
        color: #FFC300; /* Amarelo Riqueza para os labels */
    }}
    .stTextInput div[data-baseweb="input"] > div {{
        background-color: #333333; /* Cinza escuro para o fundo do input */
        color: #EEEEEE; /* Cinza claro para o texto digitado */
        border: 1px solid #FFC300; /* Borda Amarelo Riqueza */
    }}
    /* Estilo do input quando focado */
    .stTextInput div[data-baseweb="input"] > div:focus-within {{
        border-color: #FFD700; /* Amarelo ligeiramente mais claro no foco */
        box-shadow: 0 0 0 0.1rem rgba(255, 195, 0, 0.25); /* Sombra sutil */
    }}

    /* Estilo dos Botões */
    .stButton > button {{
        background-color: #FFC300; /* Amarelo Riqueza */
        color: #1A1A1A; /* Texto escuro no botão amarelo */
        border: none;
        padding: 10px 20px;
        border-radius: 5px;
        font-weight: bold;
        transition: background-color 0.3s ease; /* Transição suave no hover */
    }}
    /* Estilo do botão ao passar o mouse */
    .stButton > button:hover {{
        background-color: #FFD700; /* Amarelo ligeiramente mais claro no hover */
        color: #000000; /* Preto total no texto para contraste */
    }}

    /* Estilo dos Expanders (usado para QSA, por exemplo) */
    .stExpander {{
        background-color: #333333; /* Cinza escuro para o fundo do expander */
        border: 1px solid #FFC300; /* Borda Amarelo Riqueza */
        border-radius: 5px;
        padding: 10px;
        margin-bottom: 10px;
    }}
    .stExpander > div > div > div > p {{
        color: #EEEEEE; /* Cinza claro para o título do expander */
    }}

    /* Estilo para st.info, st.warning, st.error */
    .stAlert {{
        background-color: #333333; /* Cinza escuro para o fundo dos alertas */
        color: #EEEEEE; /* Cinza claro para o texto */
        border-left: 5px solid #FFC300; /* Borda esquerda Amarelo Riqueza */
        border-radius: 5px;
    }}
    .stAlert > div > div > div > div > span {{
        color: #EEEEEE !important; /* Garante que o texto dentro do alerta seja claro */
    }}
    .stAlert > div > div > div > div > svg {{
        color: #FFC300 !important; /* Garante que o ícone do alerta seja amarelo */
    }}

    /* Linhas divisórias */
    hr {{
        border-top: 1px solid #444444; /* Cinza para divisórias */
    }}
</style>
""", unsafe_allow_html=True) # Permite a interpretação do HTML/CSS

# --- Lógica de Autenticação ---
# Inicializa o estado de autenticação na sessão, se ainda não existir
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# Se o usuário não está autenticado, mostra a tela de login
if not st.session_state["authenticated"]:
    # IMAGEM NA PÁGINA DE LOGIN
    # O caminho da imagem deve ser relativo à raiz do seu repositório no GitHub
    st.image('images/logo_login.png', width=200) # Ajuste a largura conforme necessário
    st.markdown("<h1 style='text-align: center;'>Bem-vindo à Consulta CNPJ</h1>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>Acesso Restrito</h2>", unsafe_allow_html=True)

    password_input = st.text_input("Por favor, digite a senha para continuar:", type="password", help="A senha é Ivana_2025")

    if st.button("Entrar"):
        if password_input == SENHA_ACESSO:
            st.session_state["authenticated"] = True
            st.success("Acesso liberado! Redirecionando...")
            st.rerun() # Recarrega a página para exibir o conteúdo principal
        else:
            st.error("Senha incorreta. Tente novamente.")
else:
    # --- Aplicação Principal (Após Autenticação) ---
    # IMAGEM NA PÁGINA DE CONSULTA (Topo)
    st.image('images/logo_main.png', width=150) # Ajuste a largura conforme necessário
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
            # Limpa o CNPJ: remove todos os caracteres não numéricos
            cnpj_limpo = re.sub(r'[^0-9]', '', cnpj_input)

            if len(cnpj_limpo) != 14:
                st.error("CNPJ inválido. Um CNPJ deve conter exatamente 14 dígitos numéricos.")
            else:
                with st.spinner(f"Consultando CNPJ {cnpj_limpo}..."):
                    try:
                        # Realiza a requisição à BrasilAPI
                        response = requests.get(f"{URL_BRASILAPI_CNPJ}{cnpj_limpo}", timeout=15)
                        response.raise_for_status() # Lança um HTTPError para respostas 4xx/5xx
                        dados_cnpj = response.json()

                        # Verifica se a API retornou um erro específico no JSON (ex: CNPJ não encontrado)
                        if "message" in dados_cnpj and "erros" in dados_cnpj:
                            st.error(f"Erro ao consultar CNPJ: {dados_cnpj['message']}")
                            if 'erros' in dados_cnpj and isinstance(dados_cnpj['erros'], list):
                                for erro_detalhe in dados_cnpj['erros']:
                                    st.error(f"- {erro_detalhe}")
                            st.info("Verifique se o CNPJ digitado está correto.")
                        elif "cnpj" not in dados_cnpj:
                             st.error("CNPJ não encontrado ou houve um problema inesperado na resposta da API. Tente novamente mais tarde ou verifique o CNPJ.")
                        else:
                            st.success(f"Dados encontrados para o CNPJ: {dados_cnpj.get('cnpj', 'N/A')}")
                            # IMAGEM NA PÁGINA DE RESULTADO (Após o sucesso da consulta)
                            st.image('images/logo_resultado.png', width=100) # Ajuste a largura conforme necessário

                            st.markdown("---")
                            st.markdown("## Dados da Empresa")

                            # Organiza os dados em colunas para melhor visualização
                            col1, col2 = st.columns(2)
                            with col1:
                                st.write(f"**Razão Social:** {dados_cnpj.get('razao_social', 'N/A')}")
                                st.write(f"**Nome Fantasia:** {dados_cnpj.get('nome_fantasia', 'N/A')}")
                                st.write(f"**CNPJ:** {dados_cnpj.get('cnpj', 'N/A')}")
                                st.write(f"**Situação Cadastral:** {dados_cnpj.get('descricao_situacao_cadastral', 'N/A')}")
                                st.write(f"**Data Início Atividade:** {dados_cnpj.get('data_inicio_atividade', 'N/A')}")
                                st.write(f"**CNAE Fiscal:** {dados_cnpj.get('cnae_fiscal_descricao', 'N/A')} ({dados_cnpj.get('cnae_fiscal', 'N/A')})")
                                st.write(f"**Porte:** {dados_cnpj.get('porte', 'N/A')}")
                            with col2:
                                st.write(f"**Natureza Jurídica:** {dados_cnpj.get('natureza_juridica', 'N/A')}")
                                # Formatação de moeda para o Capital Social (padrão brasileiro)
                                capital_social = dados_cnpj.get('capital_social', 0)
                                if isinstance(capital_social, (int, float)):
                                    st.write(f"**Capital Social:** R\$ {capital_social:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
                                else:
                                    st.write(f"**Capital Social:** N/A")

                                # Exibe telefones, concatenando DDD e número
                                telefone1_ddd = dados_cnpj.get('ddd_telefone_1')
                                telefone1_num = dados_cnpj.get('telefone_1')
                                if telefone1_ddd and telefone1_num:
                                    st.write(f"**Telefone:** ({telefone1_ddd}) {telefone1_num}")
                                else:
                                    st.write(f"**Telefone:** N/A")

                                telefone2_ddd = dados_cnpj.get('ddd_telefone_2')
                                telefone2_num = dados_cnpj.get('telefone_2')
                                if telefone2_ddd and telefone2_num:
                                    st.write(f"**Telefone 2:** ({telefone2_ddd}) {telefone2_num}")

                                st.write(f"**Email:** {dados_cnpj.get('email', 'N/A')}")
                                # Trata os campos booleanos de Simples e MEI
                                st.write(f"**Opção pelo Simples:** {'Sim' if dados_cnpj.get('opcao_pelo_simples') else ('Não' if dados_cnpj.get('opcao_pelo_simples') is False else 'N/A')}")
                                st.write(f"**Opção pelo MEI:** {'Sim' if dados_cnpj.get('opcao_pelo_mei') else ('Não' if dados_cnpj.get('opcao_pelo_mei') is False else 'N/A')}")

                            st.markdown("---")
                            st.markdown("## Endereço")
                            st.write(f"**Logradouro:** {dados_cnpj.get('descricao_tipo_de_logradouro', '')} {dados_cnpj.get('logradouro', 'N/A')}, {dados_cnpj.get('numero', 'N/A')}")
                            if dados_cnpj.get('complemento'):
                                st.write(f"**Complemento:** {dados_cnpj.get('complemento', 'N/A')}")
                            st.write(f"**Bairro:** {dados_cnpj.get('bairro', 'N/A')}")
                            st.write(f"**Município:** {dados_cnpj.get('municipio', 'N/A')}")
                            st.write(f"**UF:** {dados_cnpj.get('uf', 'N/A')}")
                            st.write(f"**CEP:** {dados_cnpj.get('cep', 'N/A')}")

                            st.markdown("---")
                            if dados_cnpj.get('qsa'):
                                st.markdown("## Quadro de Sócios e Administradores (QSA)")
                                # Utiliza st.expander para cada sócio, mantendo a organização
                                for i, socio in enumerate(dados_cnpj['qsa']):
                                    with st.expander(f"**Sócio/Administrador {i+1}:** {socio.get('nome_socio', 'N/A')}"):
                                        st.write(f"**Nome:** {socio.get('nome_socio', 'N/A')}")
                                        st.write(f"**Qualificação:** {socio.get('qualificacao_socio', 'N/A')}")
                                        st.write(f"**Data de Entrada:** {socio.get('data_entrada_sociedade', 'N/A')}")
                                        st.write(f"**CNPJ/CPF do Sócio:** {socio.get('cnpj_cpf_do_socio', 'N/A')}")
                                        if socio.get('nome_representante_legal'):
                                            st.write(f"**Nome do Representante Legal:** {socio.get('nome_representante_legal', 'N/A')}")
                                            st.write(f"**CPF do Representante Legal:** {socio.get('cpf_representante_legal', 'N/A')}")
                                            st.write(f"**Qualificação do Representante Legal:** {socio.get('qualificacao_representante_legal', 'N/A')}")
                            else:
                                st.info("Não há informações de Quadro de Sócios e Administradores (QSA) disponíveis para este CNPJ.")

                            st.markdown("---")
                            if dados_cnpj.get('cnaes_secundarios'):
                                st.markdown("## CNAEs Secundários")
                                cnaes_list_formatted = []
                                for cnae in dados_cnpj['cnaes_secundarios']:
                                    cnaes_list_formatted.append(f"- **{cnae.get('codigo', 'N/A')}**: {cnae.get('descricao', 'N/A')}")
                                st.markdown("\n".join(cnaes_list_formatted)) # Exibe como lista Markdown
                            else:
                                st.info("Não há CNAEs secundários informados para este CNPJ.")

                            st.markdown("---") # Adiciona uma nova linha divisória
                            if dados_cnpj.get('regime_tributario'):
                                st.markdown("## Regime Tributário (Histórico)")
                                for i, regime in enumerate(dados_cnpj['regime_tributario']):
                                    st.write(f"**Ano:** {regime.get('ano', 'N/A')}")
                                    st.write(f"**Forma de Tributação:** {regime.get('forma_de_tributacao', 'N/A')}")
                                    st.write(f"**Qtd. Escriturações:** {regime.get('quantidade_de_escrituracoes', 'N/A')}")
                                    if i < len(dados_cnpj['regime_tributario']) - 1: # Adiciona uma linha entre os regimes
                                        st.markdown("---")
                            else:
                                st.info("Não há informações de Regime Tributário disponíveis para este CNPJ.")


                    except requests.exceptions.Timeout:
                        st.error("Tempo limite da requisição excedido. A API não respondeu a tempo. Tente novamente mais tarde.")
                    except requests.exceptions.ConnectionError:
                        st.error("Erro de conexão: Não foi possível acessar a API. Verifique sua conexão com a internet ou se a BrasilAPI está online.")
                    except requests.exceptions.HTTPError as e:
                        st.error(f"Erro na requisição HTTP: {e}. Isso pode indicar um problema com o CNPJ ou com o servidor da API.")
                    except ValueError:
                        st.error("Erro ao processar a resposta da API. O formato dos dados recebidos é inválido.")
                    except Exception as e:
                        st.error(f"Ocorreu um erro inesperado: {e}")

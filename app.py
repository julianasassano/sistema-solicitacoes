import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from pathlib import Path

# ----------------------------
# CONFIGURAÇÃO DA PÁGINA
# ----------------------------
st.set_page_config(
    page_title="Emogis - Requisições Internas",
    page_icon="🏗️",
    layout="wide"
)

# CSS personalizado — Emogis Design System
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Fundo geral */
    .stApp { background-color: #f0f4f8; }

    /* Esconder header padrão do Streamlit */
    #MainMenu, header, footer { visibility: hidden; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1f35 0%, #1a3a5c 100%);
        border-right: 1px solid #1e4976;
    }
    [data-testid="stSidebar"] * { color: #cbd5e1 !important; }
    [data-testid="stSidebar"] .stButton button {
        background-color: rgba(239,68,68,0.15) !important;
        color: #fca5a5 !important;
        border: 1px solid rgba(239,68,68,0.3) !important;
        border-radius: 8px;
        width: 100%;
        margin-top: 8px;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: rgba(239,68,68,0.3) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #1a3a5c;
        border-radius: 10px;
        padding: 4px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #7eb3d8 !important;
        border-radius: 7px;
        font-weight: 500;
        font-size: 0.85rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2196f3 !important;
        color: white !important;
        font-weight: 600;
    }

    /* Botão primário */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2196f3, #1565c0);
        color: white !important;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 2rem;
        font-weight: 600;
        font-size: 0.95rem;
        box-shadow: 0 4px 12px rgba(33,150,243,0.35);
        transition: all 0.2s;
    }
    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 20px rgba(33,150,243,0.5);
        transform: translateY(-1px);
    }

    /* Botões normais */
    .stButton > button {
        border-radius: 8px;
        border: 1px solid #90caf9;
        color: #2196f3;
        transition: all 0.2s;
    }

    /* Métricas */
    [data-testid="metric-container"] {
        background: white;
        border-radius: 14px;
        padding: 1.2rem;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #2196f3;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background-color: white;
        border-radius: 10px;
        border-left: 3px solid #2196f3;
        font-weight: 500;
    }

    /* Inputs */
    .stTextInput input, .stTextArea textarea {
        border-radius: 10px;
        border: 1.5px solid #e2e8f0;
        font-family: 'Inter', sans-serif;
        transition: border 0.2s;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #2196f3;
        box-shadow: 0 0 0 3px rgba(33,150,243,0.15);
    }

    /* Login — fundo escuro full page */
    .login-bg {
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        background: linear-gradient(135deg, #0d1f35 0%, #0a3055 50%, #0d1f35 100%);
        z-index: -1;
    }
    .login-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 20px;
        padding: 2.5rem;
        box-shadow: 0 24px 64px rgba(0,0,0,0.4);
    }
    .login-title {
        color: white;
        text-align: center;
        font-size: 1.1rem;
        font-weight: 400;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
        opacity: 0.7;
    }
    .login-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(33,150,243,0.6), transparent);
        margin: 1.2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ----------------------------
# CONEXÃO COM O BANCO
# ----------------------------
@st.cache_resource
def get_conn():
    return psycopg2.connect(st.secrets["DB_URL"], sslmode="require")

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            area TEXT NOT NULL,
            perfil TEXT NOT NULL DEFAULT 'usuario',
            email TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS solicitacoes (
            id SERIAL PRIMARY KEY,
            titulo TEXT NOT NULL,
            descricao TEXT,
            solicitante TEXT NOT NULL,
            area_origem TEXT NOT NULL,
            area_destino TEXT NOT NULL,
            obra TEXT,
            pf TEXT,
            prioridade TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            atribuido_a TEXT,
            data_criacao TIMESTAMP NOT NULL,
            data_atualizacao TIMESTAMP NOT NULL,
            observacoes TEXT
        )
    """)

    # Adicionar colunas novas se não existirem (bases já criadas)
    for col_sql in [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN IF NOT EXISTS obra TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN IF NOT EXISTS pf TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN IF NOT EXISTS atribuido_a TEXT",
    ]:
        try:
            c.execute(col_sql)
            conn.commit()
        except Exception:
            conn.rollback()

    conn.commit()

    # Usuários reais da Emogis
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        usuarios_iniciais = [
            # (nome, login, senha, area, perfil, email)
            ("Juliana Moreto",   "juliana",  "emogis2024", "Logística",    "admin",   "juliana@emogis.pt"),
            ("Nuno Santos",      "nuno",     "emogis2024", "Direção Obra", "usuario", "nuno@emogis.pt"),
            ("Rafael Silva",     "rafael",   "emogis2024", "Direção Obra", "usuario", "rafael@emogis.pt"),
            ("Jorge Veiga",      "jorge",    "emogis2024", "Direção Obra", "usuario", "jorge@emogis.pt"),
            ("Catarina Meireles","catarina", "emogis2024", "Produção",     "usuario", "catarina@emogis.pt"),
            ("Pedro Pereira",    "pedro",    "emogis2024", "Compras",      "usuario", "pedro@emogis.pt"),
        ]
        for nome, login, senha, area, perfil, email in usuarios_iniciais:
            c.execute(
                "INSERT INTO usuarios (nome, login, senha, area, perfil, email) VALUES (%s,%s,%s,%s,%s,%s)",
                (nome, login, hash_senha(senha), area, perfil, email)
            )
        conn.commit()

    c.close()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_login(login, senha):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nome, area, perfil, senha, email FROM usuarios WHERE login=%s", (login,))
    row = c.fetchone()
    c.close()
    if row and row[4] == hash_senha(senha):
        return {"id": row[0], "nome": row[1], "area": row[2], "perfil": row[3], "email": row[5]}
    return None

def listar_usuarios_area(area):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT nome, email FROM usuarios WHERE area=%s ORDER BY nome", (area,))
    rows = c.fetchall()
    c.close()
    return rows  # [(nome, email), ...]

def listar_todos_usuarios():
    conn = get_conn()
    df = pd.read_sql_query("SELECT id, nome, login, area, perfil, email FROM usuarios ORDER BY area, nome", conn)
    return df

def criar_solicitacao(titulo, descricao, solicitante, area_origem, area_destino, prioridade, obra="", pf="", atribuido_a=""):
    conn = get_conn()
    c = conn.cursor()
    agora = datetime.now()
    c.execute("""
        INSERT INTO solicitacoes
        (titulo, descricao, solicitante, area_origem, area_destino, obra, pf, prioridade, status, atribuido_a, data_criacao, data_atualizacao)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (titulo, descricao, solicitante, area_origem, area_destino, obra, pf, prioridade, "Pendente", atribuido_a, agora, agora))
    conn.commit()
    c.close()

def buscar_solicitacoes(area=None, status=None, somente_minhas=None, solicitante=None):
    conn = get_conn()
    query = "SELECT * FROM solicitacoes WHERE 1=1"
    params = []
    if area and area != "Todas":
        query += " AND area_destino = %s"
        params.append(area)
    if status and status != "Todos":
        query += " AND status = %s"
        params.append(status)
    if somente_minhas and solicitante:
        query += " AND solicitante = %s"
        params.append(solicitante)
    query += " ORDER BY data_criacao DESC"
    df = pd.read_sql_query(query, conn, params=params)
    return df

def atualizar_status(id_solicitacao, novo_status, observacoes="", atribuido_a=""):
    conn = get_conn()
    c = conn.cursor()
    agora = datetime.now()
    c.execute("""
        UPDATE solicitacoes
        SET status=%s, data_atualizacao=%s, observacoes=%s, atribuido_a=%s
        WHERE id=%s
    """, (novo_status, agora, observacoes, atribuido_a, id_solicitacao))
    conn.commit()
    c.close()

# ----------------------------
# NOTIFICAÇÕES POR EMAIL
# ----------------------------
def enviar_email(destinatario, assunto, corpo_html):
    try:
        smtp_host = st.secrets.get("SMTP_HOST", "")
        smtp_port = int(st.secrets.get("SMTP_PORT", 587))
        smtp_user = st.secrets.get("SMTP_USER", "")
        smtp_pass = st.secrets.get("SMTP_PASS", "")

        if not smtp_host or not smtp_user:
            return False  # Email não configurado, ignora silenciosamente

        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = f"Emogis Requisições <{smtp_user}>"
        msg["To"] = destinatario

        msg.attach(MIMEText(corpo_html, "html"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, destinatario, msg.as_string())
        return True
    except Exception:
        return False

def notificar_nova_solicitacao(titulo, solicitante, area_destino, obra, prioridade, emails_destino):
    assunto = f"[Emogis] Nova requisição: {titulo}"
    cor_prioridade = {"Urgente": "#ef4444", "Alta": "#f59e0b", "Média": "#3b82f6", "Baixa": "#10b981"}.get(prioridade, "#3b82f6")
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#1a3a5c,#2196f3);padding:20px;border-radius:12px 12px 0 0;">
        <h2 style="color:white;margin:0;">🏗️ Emogis — Nova Requisição</h2>
      </div>
      <div style="background:white;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
        <p style="color:#64748b;">Foi submetida uma nova requisição para a sua área.</p>
        <table style="width:100%;border-collapse:collapse;">
          <tr><td style="padding:8px;color:#64748b;font-weight:600;">Título</td><td style="padding:8px;color:#1a3a5c;font-weight:700;">{titulo}</td></tr>
          <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;font-weight:600;">Solicitante</td><td style="padding:8px;">{solicitante}</td></tr>
          <tr><td style="padding:8px;color:#64748b;font-weight:600;">Área destino</td><td style="padding:8px;">{area_destino}</td></tr>
          <tr style="background:#f8fafc;"><td style="padding:8px;color:#64748b;font-weight:600;">Obra</td><td style="padding:8px;">{obra or '-'}</td></tr>
          <tr><td style="padding:8px;color:#64748b;font-weight:600;">Prioridade</td><td style="padding:8px;"><span style="background:{cor_prioridade};color:white;padding:2px 10px;border-radius:20px;font-size:0.85rem;">{prioridade}</span></td></tr>
        </table>
        <div style="margin-top:20px;text-align:center;">
          <a href="https://sistema-solicitacoes-mor4pc9vk2pqrwjrxnvblo.streamlit.app" style="background:#2196f3;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Ver Requisição →</a>
        </div>
        <p style="color:#94a3b8;font-size:0.8rem;margin-top:20px;text-align:center;">Emogis — Construção Industrial</p>
      </div>
    </div>
    """
    for email in emails_destino:
        if email:
            enviar_email(email, assunto, corpo)

def notificar_atualizacao(titulo, solicitante, novo_status, observacoes, email_solicitante):
    if not email_solicitante:
        return
    cor_status = {"Concluído": "#10b981", "Recusado": "#ef4444", "Em andamento": "#3b82f6", "Pendente": "#f59e0b"}.get(novo_status, "#3b82f6")
    assunto = f"[Emogis] Requisição atualizada: {titulo} → {novo_status}"
    corpo = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#1a3a5c,#2196f3);padding:20px;border-radius:12px 12px 0 0;">
        <h2 style="color:white;margin:0;">🏗️ Emogis — Requisição Atualizada</h2>
      </div>
      <div style="background:white;padding:24px;border-radius:0 0 12px 12px;border:1px solid #e2e8f0;">
        <p>A sua requisição <strong>{titulo}</strong> foi atualizada.</p>
        <p>Novo estado: <span style="background:{cor_status};color:white;padding:2px 12px;border-radius:20px;font-weight:600;">{novo_status}</span></p>
        {f'<p style="background:#f8fafc;padding:12px;border-radius:8px;border-left:3px solid #2196f3;"><strong>Observações:</strong> {observacoes}</p>' if observacoes else ''}
        <div style="margin-top:20px;text-align:center;">
          <a href="https://sistema-solicitacoes-mor4pc9vk2pqrwjrxnvblo.streamlit.app" style="background:#2196f3;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Ver Requisição →</a>
        </div>
        <p style="color:#94a3b8;font-size:0.8rem;margin-top:20px;text-align:center;">Emogis — Construção Industrial</p>
      </div>
    </div>
    """
    enviar_email(email_solicitante, assunto, corpo)

# ----------------------------
# TEMPLATES DE DESCRIÇÃO
# ----------------------------
TEMPLATES_LOGISTICA = {
    "Transporte": "Tipo de Camião: \nComprimento máximo: \nPeso total: \nComo está acondicionado? (Se em palete, informar dimensões): ",
    "Consumíveis": "Tipo: \nQuantidade: \nQuem recolhe: \nData de recolha: ",
    "Locação de equipamentos": "Tipo: \nData de início: \nPeríodo previsto: "
}

STATUS_OPCOES = ["Pendente", "Em andamento", "Concluído", "Recusado"]
PRIORIDADE_OPCOES = ["Baixa", "Média", "Alta", "Urgente"]
AREAS_DESTINO = ["Logística", "Compras", "Produção", "Qualidade"]
TITULOS_LOGISTICA = list(TEMPLATES_LOGISTICA.keys())
AREAS_COM_PF = ["Produção", "Compras", "Direção Obra"]

ICONE_STATUS = {"Pendente": "🟡", "Em andamento": "🔵", "Concluído": "🟢", "Recusado": "🔴"}

# ----------------------------
# INICIALIZAÇÃO
# ----------------------------
init_db()

if "usuario" not in st.session_state:
    st.session_state.usuario = None

# ----------------------------
# LOGO NO HEADER
# ----------------------------
def mostrar_header(titulo_pagina="Requisições Internas"):
    logo_path = Path("logo.png")
    col_logo, col_titulo = st.columns([1, 6])
    with col_logo:
        if logo_path.exists():
            st.image(str(logo_path), width=90)
        else:
            st.markdown("🏗️")
    with col_titulo:
        st.markdown(f"<h2 style='color:#1a3a5c;margin:0;padding-top:12px;font-weight:700;'>{titulo_pagina}</h2><p style='color:#64748b;margin:0;font-size:0.85rem;letter-spacing:1px;text-transform:uppercase;'>Emogis — Construção Industrial</p>", unsafe_allow_html=True)
    st.divider()

# ----------------------------
# TELA DE LOGIN
# ----------------------------
def tela_login():
    # Fundo escuro full-page
    st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #0a1628 0%, #0d2645 50%, #0a1628 100%) !important; }
        [data-testid="stSidebar"] { display: none; }
        .block-container { padding-top: 2rem !important; }

        /* Inputs no login — texto branco */
        .stTextInput input {
            background: rgba(255,255,255,0.07) !important;
            border: 1.5px solid rgba(255,255,255,0.15) !important;
            color: white !important;
            border-radius: 10px !important;
        }
        .stTextInput input:focus {
            border-color: #2196f3 !important;
            box-shadow: 0 0 0 3px rgba(33,150,243,0.2) !important;
        }
        .stTextInput label { color: rgba(255,255,255,0.6) !important; font-size:0.85rem !important; }

        /* Botão login */
        .stFormSubmitButton button {
            background: linear-gradient(135deg, #2196f3, #1565c0) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
            padding: 0.65rem !important;
            width: 100% !important;
            box-shadow: 0 4px 20px rgba(33,150,243,0.4) !important;
            letter-spacing: 1px;
        }
        .stFormSubmitButton button:hover {
            box-shadow: 0 6px 28px rgba(33,150,243,0.6) !important;
            transform: translateY(-1px);
        }
    </style>
    """, unsafe_allow_html=True)

    # Partículas decorativas de fundo
    st.markdown("""
    <div style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;overflow:hidden;z-index:0;">
      <div style="position:absolute;width:300px;height:300px;background:radial-gradient(circle,rgba(33,150,243,0.15),transparent);top:-50px;right:-50px;border-radius:50%;"></div>
      <div style="position:absolute;width:200px;height:200px;background:radial-gradient(circle,rgba(33,150,243,0.1),transparent);bottom:100px;left:-30px;border-radius:50%;"></div>
      <div style="position:absolute;width:150px;height:150px;background:radial-gradient(circle,rgba(21,101,192,0.2),transparent);bottom:-30px;right:200px;border-radius:50%;"></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        # Logo com mix-blend-mode para remover fundo
        logo_path_jpg = Path("logo.jpg")
        logo_path_png = Path("logo.png")
        # Preferir PNG (fundo escuro) para mix-blend-mode:lighten remover o fundo preto
        logo_usado = logo_path_png if logo_path_png.exists() else (logo_path_jpg if logo_path_jpg.exists() else None)
        if logo_usado:
            import base64
            with open(str(logo_usado), "rb") as f:
                logo_b64 = base64.b64encode(f.read()).decode()
            ext = "jpeg" if str(logo_usado).endswith(".jpg") else "png"
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:0.5rem;">
              <img src="data:image/{ext};base64,{logo_b64}"
                   style="width:80%;max-width:300px;mix-blend-mode:lighten;filter:brightness(1.1) contrast(1.05);" />
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("<h1 style='text-align:center;color:white;font-size:2.5rem;'>🏗️</h1>", unsafe_allow_html=True)

        # Linha divisória
        st.markdown("<div style='height:1px;background:linear-gradient(90deg,transparent,rgba(33,150,243,0.5),transparent);margin:1rem 0 1.5rem;'></div>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:rgba(255,255,255,0.45);font-size:0.8rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:1.5rem;'>Requisições Internas</p>", unsafe_allow_html=True)

        with st.form("login_form"):
            login = st.text_input("Utilizador")
            senha = st.text_input("Palavra-passe", type="password")
            entrar = st.form_submit_button("ENTRAR", use_container_width=True)

        if entrar:
            usuario = verificar_login(login, senha)
            if usuario:
                st.session_state.usuario = usuario
                st.rerun()
            else:
                st.markdown("<p style='text-align:center;color:#f87171;font-size:0.9rem;margin-top:0.5rem;'>⚠️ Utilizador ou palavra-passe inválidos.</p>", unsafe_allow_html=True)

        st.markdown("<p style='text-align:center;color:rgba(255,255,255,0.2);font-size:0.75rem;margin-top:2rem;'>© 2024 Emogis — Construção Industrial</p>", unsafe_allow_html=True)

        st.markdown("<p style='text-align:center;color:#94a3b8;font-size:0.8rem;margin-top:1rem;'>Emogis © 2024 — Construção Industrial</p>", unsafe_allow_html=True)

# ----------------------------
# NOVA SOLICITAÇÃO
# ----------------------------
def aba_nova_solicitacao(usuario):
    mostrar_header("➕ Nova Requisição")

    area_destino = st.selectbox("📍 Área de destino", AREAS_DESTINO)
    obra = st.text_input("🏗️ Obra")

    pf = ""
    if usuario["area"] in AREAS_COM_PF:
        pf = st.text_input("📋 Nº PF")

    if area_destino == "Logística":
        titulo = st.selectbox("📌 Tipo de solicitação", TITULOS_LOGISTICA)
    else:
        titulo = st.text_input("📌 Título da solicitação")

    if area_destino == "Logística" and titulo in TEMPLATES_LOGISTICA:
        descricao = st.text_area("📝 Descrição", value=TEMPLATES_LOGISTICA[titulo], height=180)
    else:
        descricao = st.text_area("📝 Descrição / Detalhes", height=150)

    prioridade = st.selectbox("⚡ Prioridade", PRIORIDADE_OPCOES, index=1)

    # Atribuição
    usuarios_destino = listar_usuarios_area(area_destino)
    nomes_destino = ["Não atribuído"] + [u[0] for u in usuarios_destino]
    atribuido_nome = st.selectbox("👤 Atribuir a", nomes_destino)
    atribuido_a = "" if atribuido_nome == "Não atribuído" else atribuido_nome

    if st.button("📤 Enviar Requisição", type="primary"):
        if area_destino != "Logística" and titulo.strip() == "":
            st.warning("Informe um título.")
        elif obra.strip() == "":
            st.warning("Informe a obra.")
        else:
            criar_solicitacao(
                titulo=titulo, descricao=descricao,
                solicitante=usuario["nome"], area_origem=usuario["area"],
                area_destino=area_destino, prioridade=prioridade,
                obra=obra, pf=pf, atribuido_a=atribuido_a
            )
            # Notificar por email os responsáveis da área destino
            emails_destino = [u[1] for u in usuarios_destino if u[1]]
            notificar_nova_solicitacao(titulo, usuario["nome"], area_destino, obra, prioridade, emails_destino)
            st.success("✅ Requisição enviada com sucesso!")
            if emails_destino:
                st.info(f"📧 Notificação enviada para {area_destino}.")

# ----------------------------
# MINHAS SOLICITAÇÕES
# ----------------------------
def aba_minhas_solicitacoes(usuario):
    mostrar_header("📤 Minhas Requisições")

    status_filtro = st.selectbox("Filtrar por status", ["Todos"] + STATUS_OPCOES, key="filtro_minhas")
    df = buscar_solicitacoes(status=status_filtro, somente_minhas=True, solicitante=usuario["nome"])

    if df.empty:
        st.info("Nenhuma requisição encontrada.")
        return

    for _, row in df.iterrows():
        icone = ICONE_STATUS.get(row['status'], "⚪")
        with st.expander(f"{icone} #{row['id']} — {row['titulo']} → {row['area_destino']} | {row['status']}"):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**🏗️ Obra:** {row.get('obra','') or '-'}")
            col1.write(f"**📋 PF:** {row.get('pf','') or '-'}")
            col2.write(f"**⚡ Prioridade:** {row['prioridade']}")
            col2.write(f"**👤 Atribuído a:** {row.get('atribuido_a','') or 'Não atribuído'}")
            col3.write(f"**📅 Criado:** {str(row['data_criacao'])[:16]}")
            col3.write(f"**🔄 Atualizado:** {str(row['data_atualizacao'])[:16]}")
            st.write("**📝 Descrição:**")
            st.code(row['descricao'] or "", language=None)
            if row['observacoes']:
                st.info(f"💬 **Resposta:** {row['observacoes']}")

# ----------------------------
# SOLICITAÇÕES RECEBIDAS
# ----------------------------
def aba_recebidas(usuario):
    mostrar_header(f"📥 Requisições Recebidas — {usuario['area']}")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        status_filtro = st.selectbox("Filtrar por status", ["Todos"] + STATUS_OPCOES, key="filtro_recebidas")
    with col_f2:
        filtro_atrib = st.selectbox("Filtrar por atribuição", ["Todas", "Atribuídas a mim"], key="filtro_atrib")

    df = buscar_solicitacoes(area=usuario["area"], status=status_filtro)

    if filtro_atrib == "Atribuídas a mim":
        df = df[df["atribuido_a"] == usuario["nome"]]

    if df.empty:
        st.info("Nenhuma requisição encontrada.")
        return

    # Buscar utilizadores da área para atribuição
    usuarios_area = listar_usuarios_area(usuario["area"])
    nomes_area = ["Não atribuído"] + [u[0] for u in usuarios_area]

    for _, row in df.iterrows():
        icone = ICONE_STATUS.get(row['status'], "⚪")
        with st.expander(f"{icone} #{row['id']} — {row['titulo']} | {row['solicitante']} ({row['area_origem']}) | ⚡ {row['prioridade']}"):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**🏗️ Obra:** {row.get('obra','') or '-'}")
            col1.write(f"**📋 PF:** {row.get('pf','') or '-'}")
            col2.write(f"**👤 Atribuído a:** {row.get('atribuido_a','') or 'Não atribuído'}")
            col3.write(f"**📅 Criado:** {str(row['data_criacao'])[:16]}")

            st.write("**📝 Descrição:**")
            st.code(row['descricao'] or "", language=None)

            st.markdown("---")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                novo_status = st.selectbox(
                    "Atualizar status",
                    STATUS_OPCOES,
                    index=STATUS_OPCOES.index(row['status']) if row['status'] in STATUS_OPCOES else 0,
                    key=f"status_{row['id']}"
                )
                atrib_atual = row.get('atribuido_a', '') or "Não atribuído"
                idx_atrib = nomes_area.index(atrib_atual) if atrib_atual in nomes_area else 0
                novo_atrib = st.selectbox("Atribuir a", nomes_area, index=idx_atrib, key=f"atrib_{row['id']}")
            with col_s2:
                obs = st.text_area("💬 Observações / Resposta",
                    value=row['observacoes'] if row['observacoes'] else "",
                    key=f"obs_{row['id']}", height=120)

            if st.button("💾 Guardar", key=f"salvar_{row['id']}", type="primary"):
                atribuido_final = "" if novo_atrib == "Não atribuído" else novo_atrib
                atualizar_status(row['id'], novo_status, obs, atribuido_final)
                # Notificar solicitante por email
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT email FROM usuarios WHERE nome=%s", (row['solicitante'],))
                r = c.fetchone()
                c.close()
                if r and r[0]:
                    notificar_atualizacao(row['titulo'], row['solicitante'], novo_status, obs, r[0])
                st.success("✅ Atualizado com sucesso!")
                st.rerun()

# ----------------------------
# DASHBOARD
# ----------------------------
def aba_dashboard(usuario):
    mostrar_header("📊 Dashboard")

    df = buscar_solicitacoes()

    if df.empty:
        st.info("Ainda não há requisições registadas.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📋 Total", len(df))
    col2.metric("🟡 Pendentes", len(df[df["status"] == "Pendente"]))
    col3.metric("🔵 Em andamento", len(df[df["status"] == "Em andamento"]))
    col4.metric("🟢 Concluídas", len(df[df["status"] == "Concluído"]))

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Por status")
        st.bar_chart(df["status"].value_counts())
    with col_b:
        st.markdown("#### Por área de destino")
        st.bar_chart(df["area_destino"].value_counts())

    st.markdown("#### Tabela completa")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        area_filtro = st.selectbox("Área", ["Todas"] + AREAS_DESTINO, key="dash_area")
    with col_f2:
        status_filtro = st.selectbox("Status", ["Todos"] + STATUS_OPCOES, key="dash_status")
    with col_f3:
        obra_filtro = st.text_input("Obra (pesquisar)", key="dash_obra")

    df_f = buscar_solicitacoes(area=area_filtro, status=status_filtro)
    if obra_filtro:
        df_f = df_f[df_f["obra"].str.contains(obra_filtro, case=False, na=False)]

    colunas = [c for c in ["id", "titulo", "solicitante", "area_origem", "area_destino", "obra", "pf", "prioridade", "status", "atribuido_a", "data_criacao"] if c in df_f.columns]
    st.dataframe(df_f[colunas], use_container_width=True)

# ----------------------------
# ADMINISTRAÇÃO
# ----------------------------
def aba_admin():
    mostrar_header("⚙️ Administração")

    df_usuarios = listar_todos_usuarios()
    st.markdown("#### Utilizadores")
    st.dataframe(df_usuarios, use_container_width=True)

    st.markdown("#### Adicionar novo utilizador")
    col1, col2 = st.columns(2)
    with col1:
        nome = st.text_input("Nome completo")
        login = st.text_input("Login")
        senha = st.text_input("Palavra-passe", type="password")
    with col2:
        area_opcoes = AREAS_DESTINO + ["Direção Obra", "TI", "Outra"]
        area = st.selectbox("Área", area_opcoes)
        area_custom = st.text_input("Se 'Outra', especifique:")
        email = st.text_input("Email")
        perfil = st.selectbox("Perfil", ["usuario", "admin"])

    if st.button("➕ Criar utilizador", type="primary"):
        area_final = area_custom if area == "Outra" and area_custom else area
        if not (nome and login and senha):
            st.warning("Preencha todos os campos obrigatórios.")
        else:
            try:
                conn = get_conn()
                c = conn.cursor()
                c.execute(
                    "INSERT INTO usuarios (nome, login, senha, area, perfil, email) VALUES (%s,%s,%s,%s,%s,%s)",
                    (nome, login, hash_senha(senha), area_final, perfil, email)
                )
                conn.commit()
                c.close()
                st.success(f"✅ Utilizador {nome} criado com sucesso!")
                st.rerun()
            except psycopg2.IntegrityError:
                conn.rollback()
                st.error("Esse login já existe.")

    st.markdown("---")
    st.markdown("#### ℹ️ Configuração de Email (opcional)")
    st.info("""Para ativar notificações por email, adicione no Streamlit Cloud → Settings → Secrets:
    
```toml
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USER = "seuemail@gmail.com"
SMTP_PASS = "sua-app-password"
```
Com Gmail, use uma **App Password** (não a senha normal). Crie em: myaccount.google.com → Segurança → Palavras-passe de aplicações.""")

# ----------------------------
# APP PRINCIPAL
# ----------------------------
if st.session_state.usuario is None:
    tela_login()
else:
    usuario = st.session_state.usuario

    with st.sidebar:
        logo_path = Path("logo.png")
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        st.markdown("---")
        st.markdown(f"**{usuario['nome']}**")
        st.markdown(f"🏢 {usuario['area']}")
        st.markdown("---")
        if st.button("🚪 Sair"):
            st.session_state.usuario = None
            st.rerun()

    abas = ["📊 Dashboard", "➕ Nova Requisição", "📤 Minhas Requisições", "📥 Recebidas"]
    if usuario["perfil"] == "admin":
        abas.append("⚙️ Administração")

    tab_objs = st.tabs(abas)
    with tab_objs[0]: aba_dashboard(usuario)
    with tab_objs[1]: aba_nova_solicitacao(usuario)
    with tab_objs[2]: aba_minhas_solicitacoes(usuario)
    with tab_objs[3]: aba_recebidas(usuario)
    if usuario["perfil"] == "admin":
        with tab_objs[4]: aba_admin()

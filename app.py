import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
from datetime import datetime
import hashlib

# ----------------------------
# CONEXÃO COM O BANCO (Supabase / PostgreSQL)
# ----------------------------
@st.cache_resource
def get_conn():
    return psycopg2.connect(
        st.secrets["DB_URL"],
        sslmode="require"
    )

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
            perfil TEXT NOT NULL DEFAULT 'usuario'
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
            prioridade TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pendente',
            data_criacao TIMESTAMP NOT NULL,
            data_atualizacao TIMESTAMP NOT NULL,
            observacoes TEXT
        )
    """)

    conn.commit()

    # Usuários iniciais (só cria se a tabela estiver vazia)
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        areas_iniciais = [
            ("Administrador", "admin", "admin123", "TI", "admin"),
            ("Usuário Logística", "logistica", "1234", "Logística", "usuario"),
            ("Usuário Compras", "compras", "1234", "Compras", "usuario"),
            ("Usuário Qualidade", "qualidade", "1234", "Qualidade", "usuario"),
            ("Usuário Manutenção", "manutencao", "1234", "Manutenção", "usuario"),
        ]
        for nome, login, senha, area, perfil in areas_iniciais:
            c.execute(
                "INSERT INTO usuarios (nome, login, senha, area, perfil) VALUES (%s,%s,%s,%s,%s)",
                (nome, login, hash_senha(senha), area, perfil)
            )
        conn.commit()

    c.close()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

def verificar_login(login, senha):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, nome, area, perfil, senha FROM usuarios WHERE login=%s", (login,))
    row = c.fetchone()
    c.close()
    if row and row[4] == hash_senha(senha):
        return {"id": row[0], "nome": row[1], "area": row[2], "perfil": row[3]}
    return None

def listar_areas():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT DISTINCT area FROM usuarios ORDER BY area")
    areas = [r[0] for r in c.fetchall()]
    c.close()
    return areas

def criar_solicitacao(titulo, descricao, solicitante, area_origem, area_destino, prioridade):
    conn = get_conn()
    c = conn.cursor()
    agora = datetime.now()
    c.execute("""
        INSERT INTO solicitacoes
        (titulo, descricao, solicitante, area_origem, area_destino, prioridade, status, data_criacao, data_atualizacao)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (titulo, descricao, solicitante, area_origem, area_destino, prioridade, "Pendente", agora, agora))
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

def atualizar_status(id_solicitacao, novo_status, observacoes=""):
    conn = get_conn()
    c = conn.cursor()
    agora = datetime.now()
    c.execute("""
        UPDATE solicitacoes
        SET status = %s, data_atualizacao = %s, observacoes = %s
        WHERE id = %s
    """, (novo_status, agora, observacoes, id_solicitacao))
    conn.commit()
    c.close()

# ----------------------------
# INTERFACE
# ----------------------------
st.set_page_config(page_title="Sistema de Solicitações", layout="wide")
init_db()

STATUS_OPCOES = ["Pendente", "Em andamento", "Concluído", "Recusado"]
PRIORIDADE_OPCOES = ["Baixa", "Média", "Alta", "Urgente"]

if "usuario" not in st.session_state:
    st.session_state.usuario = None

# ----------------------------
# TELA DE LOGIN
# ----------------------------
def tela_login():
    st.title("🔐 Login - Sistema de Solicitações")
    st.caption("Use seu login e senha cadastrados pela área de TI.")

    with st.form("login_form"):
        login = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")
        entrar = st.form_submit_button("Entrar")

    if entrar:
        usuario = verificar_login(login, senha)
        if usuario:
            st.session_state.usuario = usuario
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos.")

    with st.expander("ℹ️ Usuários de exemplo (alterar depois)"):
        st.write("""
        - **admin / admin123** (Administrador, área TI)
        - **logistica / 1234** (área Logística)
        - **compras / 1234** (área Compras)
        - **qualidade / 1234** (área Qualidade)
        - **manutencao / 1234** (área Manutenção)
        """)

# ----------------------------
# NOVA SOLICITAÇÃO
# ----------------------------
def aba_nova_solicitacao(usuario):
    st.subheader("➕ Nova Solicitação")

    areas = [a for a in listar_areas() if a != usuario["area"]]

    with st.form("nova_solicitacao"):
        titulo = st.text_input("Título da solicitação")
        descricao = st.text_area("Descrição / Detalhes")
        area_destino = st.selectbox("Área de destino", areas)
        prioridade = st.selectbox("Prioridade", PRIORIDADE_OPCOES, index=1)
        enviar = st.form_submit_button("Enviar solicitação")

    if enviar:
        if titulo.strip() == "":
            st.warning("Informe um título.")
        else:
            criar_solicitacao(
                titulo=titulo,
                descricao=descricao,
                solicitante=usuario["nome"],
                area_origem=usuario["area"],
                area_destino=area_destino,
                prioridade=prioridade
            )
            st.success("Solicitação enviada com sucesso!")

# ----------------------------
# MINHAS SOLICITAÇÕES (enviadas por mim)
# ----------------------------
def aba_minhas_solicitacoes(usuario):
    st.subheader("📤 Minhas Solicitações Enviadas")

    status_filtro = st.selectbox("Filtrar por status", ["Todos"] + STATUS_OPCOES, key="filtro_minhas")
    df = buscar_solicitacoes(status=status_filtro, somente_minhas=True, solicitante=usuario["nome"])

    if df.empty:
        st.info("Nenhuma solicitação encontrada.")
    else:
        for _, row in df.iterrows():
            with st.expander(f"#{row['id']} - {row['titulo']} → {row['area_destino']} [{row['status']}]"):
                st.write(f"**Descrição:** {row['descricao']}")
                st.write(f"**Prioridade:** {row['prioridade']}")
                st.write(f"**Criado em:** {row['data_criacao']}")
                st.write(f"**Última atualização:** {row['data_atualizacao']}")
                if row['observacoes']:
                    st.write(f"**Observações da área:** {row['observacoes']}")

# ----------------------------
# SOLICITAÇÕES RECEBIDAS (para minha área tratar)
# ----------------------------
def aba_recebidas(usuario):
    st.subheader(f"📥 Solicitações para minha área ({usuario['area']})")

    status_filtro = st.selectbox("Filtrar por status", ["Todos"] + STATUS_OPCOES, key="filtro_recebidas")
    df = buscar_solicitacoes(area=usuario["area"], status=status_filtro)

    if df.empty:
        st.info("Nenhuma solicitação encontrada.")
        return

    for _, row in df.iterrows():
        with st.expander(f"#{row['id']} - {row['titulo']} (de {row['solicitante']} - {row['area_origem']}) [{row['status']}] - Prioridade: {row['prioridade']}"):
            st.write(f"**Descrição:** {row['descricao']}")
            st.write(f"**Criado em:** {row['data_criacao']}")
            st.write(f"**Última atualização:** {row['data_atualizacao']}")

            novo_status = st.selectbox(
                "Atualizar status",
                STATUS_OPCOES,
                index=STATUS_OPCOES.index(row['status']),
                key=f"status_{row['id']}"
            )
            obs = st.text_area(
                "Observações / Resposta",
                value=row['observacoes'] if row['observacoes'] else "",
                key=f"obs_{row['id']}"
            )

            if st.button("Salvar atualização", key=f"salvar_{row['id']}"):
                atualizar_status(row['id'], novo_status, obs)
                st.success("Atualizado com sucesso!")
                st.rerun()

# ----------------------------
# DASHBOARD
# ----------------------------
def aba_dashboard(usuario):
    st.subheader("📊 Dashboard Geral")

    df = buscar_solicitacoes()

    if df.empty:
        st.info("Ainda não há solicitações registradas.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", len(df))
    col2.metric("Pendentes", len(df[df["status"] == "Pendente"]))
    col3.metric("Em andamento", len(df[df["status"] == "Em andamento"]))
    col4.metric("Concluídas", len(df[df["status"] == "Concluído"]))

    st.markdown("### Por status")
    st.bar_chart(df["status"].value_counts())

    st.markdown("### Por área de destino")
    st.bar_chart(df["area_destino"].value_counts())

    st.markdown("### Tabela completa")

    col_a, col_b = st.columns(2)
    with col_a:
        area_filtro = st.selectbox("Área de destino", ["Todas"] + listar_areas(), key="dash_area")
    with col_b:
        status_filtro = st.selectbox("Status", ["Todos"] + STATUS_OPCOES, key="dash_status")

    df_filtrado = buscar_solicitacoes(area=area_filtro, status=status_filtro)
    st.dataframe(
        df_filtrado[["id", "titulo", "solicitante", "area_origem", "area_destino", "prioridade", "status", "data_criacao", "data_atualizacao"]],
        use_container_width=True
    )

# ----------------------------
# ADMIN - GERENCIAR USUÁRIOS
# ----------------------------
def aba_admin():
    st.subheader("⚙️ Administração - Usuários e Áreas")

    conn = get_conn()
    df_usuarios = pd.read_sql_query("SELECT id, nome, login, area, perfil FROM usuarios", conn)

    st.dataframe(df_usuarios, use_container_width=True)

    st.markdown("### Adicionar novo usuário")
    with st.form("novo_usuario"):
        nome = st.text_input("Nome")
        login = st.text_input("Login")
        senha = st.text_input("Senha", type="password")
        area = st.text_input("Área (ex: Logística, Compras, Qualidade...)")
        perfil = st.selectbox("Perfil", ["usuario", "admin"])
        criar = st.form_submit_button("Criar usuário")

    if criar:
        if not (nome and login and senha and area):
            st.warning("Preencha todos os campos.")
        else:
            try:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO usuarios (nome, login, senha, area, perfil) VALUES (%s,%s,%s,%s,%s)",
                    (nome, login, hash_senha(senha), area, perfil)
                )
                conn.commit()
                c.close()
                st.success("Usuário criado com sucesso!")
                st.rerun()
            except psycopg2.IntegrityError:
                conn.rollback()
                st.error("Esse login já existe.")

# ----------------------------
# APP PRINCIPAL
# ----------------------------
if st.session_state.usuario is None:
    tela_login()
else:
    usuario = st.session_state.usuario

    with st.sidebar:
        st.write(f"👤 **{usuario['nome']}**")
        st.write(f"🏢 Área: {usuario['area']}")
        st.write(f"🔑 Perfil: {usuario['perfil']}")
        if st.button("Sair"):
            st.session_state.usuario = None
            st.rerun()

    abas = ["📊 Dashboard", "➕ Nova Solicitação", "📤 Minhas Solicitações", "📥 Recebidas"]
    if usuario["perfil"] == "admin":
        abas.append("⚙️ Administração")

    tab_objs = st.tabs(abas)

    with tab_objs[0]:
        aba_dashboard(usuario)
    with tab_objs[1]:
        aba_nova_solicitacao(usuario)
    with tab_objs[2]:
        aba_minhas_solicitacoes(usuario)
    with tab_objs[3]:
        aba_recebidas(usuario)
    if usuario["perfil"] == "admin":
        with tab_objs[4]:
            aba_admin()

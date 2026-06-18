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

st.set_page_config(page_title="Emogis — Requisições Internas", page_icon="🏗️", layout="wide")

# ─── CSS GLOBAL ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif;}
#MainMenu,footer{visibility:hidden;}
.stApp{background:#f0f4f8;}

[data-testid="stSidebar"]{
  background:linear-gradient(160deg,#0a1628 0%,#0d2645 60%,#1a3a5c 100%);
  border-right:1px solid rgba(33,150,243,0.15);
}
[data-testid="stSidebar"] *{color:#cbd5e1 !important;}
[data-testid="stSidebar"] hr{border-color:rgba(255,255,255,0.08)!important;}
[data-testid="stSidebar"] .stButton button{
  background:rgba(239,68,68,0.12)!important;color:#fca5a5!important;
  border:1px solid rgba(239,68,68,0.25)!important;border-radius:8px;width:100%;
}

.stTabs [data-baseweb="tab-list"]{
  background:linear-gradient(90deg,#0d2645,#1a3a5c);border-radius:10px;padding:4px;gap:2px;
}
.stTabs [data-baseweb="tab"]{color:#7eb3d8!important;border-radius:7px;font-weight:500;font-size:.85rem;}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#2196f3,#1565c0)!important;color:#fff!important;font-weight:600;}

.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#2196f3,#1565c0);color:#fff!important;border:none;
  border-radius:10px;padding:.6rem 2rem;font-weight:700;
  box-shadow:0 4px 14px rgba(33,150,243,.35);transition:all .2s;
}
.stButton>button[kind="primary"]:hover{box-shadow:0 6px 20px rgba(33,150,243,.55);transform:translateY(-1px);}
.stButton>button{border-radius:8px;border:1px solid #90caf9;color:#2196f3;}

[data-testid="metric-container"]{
  background:#fff;border-radius:14px;padding:1.2rem;
  border:1px solid #e2e8f0;border-left:4px solid #2196f3;
  box-shadow:0 2px 12px rgba(0,0,0,.06);
}
.streamlit-expanderHeader{background:#fff;border-radius:10px;border-left:3px solid #2196f3;font-weight:500;}
.stTextInput input,.stTextArea textarea{border-radius:10px;border:1.5px solid #e2e8f0;transition:border .2s;}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:#2196f3;box-shadow:0 0 0 3px rgba(33,150,243,.15);}

/* Métricas coloridas */
.metric-pendente [data-testid="metric-container"]{border-left:4px solid #f59e0b!important;}
.metric-andamento [data-testid="metric-container"]{border-left:4px solid #3b82f6!important;}
.metric-concluido [data-testid="metric-container"]{border-left:4px solid #10b981!important;}
.metric-recusado [data-testid="metric-container"]{border-left:4px solid #ef4444!important;}
</style>
""", unsafe_allow_html=True)

# ─── CONEXÃO ───────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return psycopg2.connect(st.secrets["DB_URL"], sslmode="require")

def init_db():
    conn = get_conn(); c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios(
        id SERIAL PRIMARY KEY,nome TEXT NOT NULL,login TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,area TEXT NOT NULL,perfil TEXT NOT NULL DEFAULT 'usuario',email TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS solicitacoes(
        id SERIAL PRIMARY KEY,titulo TEXT NOT NULL,descricao TEXT,
        solicitante TEXT NOT NULL,area_origem TEXT NOT NULL,area_destino TEXT NOT NULL,
        obra TEXT,pf TEXT,prioridade TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Pendente',
        data_criacao TIMESTAMP NOT NULL,data_atualizacao TIMESTAMP NOT NULL,observacoes TEXT)""")
    for sql in [
        "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN IF NOT EXISTS obra TEXT",
        "ALTER TABLE solicitacoes ADD COLUMN IF NOT EXISTS pf TEXT",
        "ALTER TABLE solicitacoes DROP COLUMN IF EXISTS atribuido_a",
    ]:
        try: c.execute(sql); conn.commit()
        except: conn.rollback()
    conn.commit()

    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        for row in [
            ("Juliana Sassano","juliana","emogis2024","Logística","admin","juliana.sassano@emogis.pt"),
            ("Nuno Santos","nuno","emogis2024","Direção Obra","usuario","nuno.santos@emogis.pt"),
            ("Rafael Silva","rafael","emogis2024","Direção Obra","usuario","rafael.silva@emogis.pt"),
            ("Jorge Veiga","jorge","emogis2024","Direção Obra","usuario","jorge.veiga@emogis.pt"),
            ("Catarina Meireles","catarina","emogis2024","Produção","usuario","catarina.meireles@emogis.pt"),
            ("Pedro Pereira","pedro","emogis2024","Compras","usuario","pedro.pereira@emogis.pt"),
        ]:
            c.execute("INSERT INTO usuarios(nome,login,senha,area,perfil,email) VALUES(%s,%s,%s,%s,%s,%s)",
                      (row[0],row[1],_hash(row[2]),row[3],row[4],row[5]))
        conn.commit()
    c.close()

def _hash(s): return hashlib.sha256(s.encode()).hexdigest()

def verificar_login(login, senha):
    c = get_conn().cursor()
    c.execute("SELECT id,nome,area,perfil,senha,email FROM usuarios WHERE login=%s",(login,))
    r = c.fetchone(); c.close()
    if r and r[4]==_hash(senha): return {"id":r[0],"nome":r[1],"area":r[2],"perfil":r[3],"email":r[5]}
    return None

def listar_usuarios_area(area):
    c = get_conn().cursor()
    c.execute("SELECT nome,email FROM usuarios WHERE area=%s ORDER BY nome",(area,))
    r = c.fetchall(); c.close(); return r

def criar_solicitacao(titulo,descricao,solicitante,area_origem,area_destino,prioridade,obra="",pf=""):
    conn=get_conn(); c=conn.cursor(); agora=datetime.now()
    c.execute("""INSERT INTO solicitacoes(titulo,descricao,solicitante,area_origem,area_destino,
        obra,pf,prioridade,status,data_criacao,data_atualizacao)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (titulo,descricao,solicitante,area_origem,area_destino,obra,pf,prioridade,"Pendente",agora,agora))
    conn.commit(); c.close()

def buscar_solicitacoes(area=None,status=None,somente_minhas=None,solicitante=None):
    conn=get_conn(); q="SELECT * FROM solicitacoes WHERE 1=1"; p=[]
    if area and area!="Todas": q+=" AND area_destino=%s"; p.append(area)
    if status and status!="Todos": q+=" AND status=%s"; p.append(status)
    if somente_minhas and solicitante: q+=" AND solicitante=%s"; p.append(solicitante)
    return pd.read_sql_query(q+" ORDER BY data_criacao DESC",conn,params=p)

def atualizar_status(id_sol,novo_status,obs=""):
    conn=get_conn(); c=conn.cursor()
    c.execute("UPDATE solicitacoes SET status=%s,data_atualizacao=%s,observacoes=%s WHERE id=%s",
              (novo_status,datetime.now(),obs,id_sol))
    conn.commit(); c.close()

def get_email_solicitante(nome):
    c = get_conn().cursor()
    c.execute("SELECT email FROM usuarios WHERE nome=%s",(nome,))
    r = c.fetchone(); c.close()
    return r[0] if r else None

# ─── EMAIL ─────────────────────────────────────────────────────────────────────
def _enviar(dest, assunto, html):
    try:
        host=st.secrets.get("SMTP_HOST",""); port=int(st.secrets.get("SMTP_PORT",587))
        user=st.secrets.get("SMTP_USER",""); pwd=st.secrets.get("SMTP_PASS","")
        if not host or not user: return False, "SMTP não configurado"
        msg=MIMEMultipart("alternative"); msg["Subject"]=assunto
        msg["From"]=f"Emogis Requisições <{user}>"; msg["To"]=dest
        msg.attach(MIMEText(html,"html"))
        with smtplib.SMTP(host,port) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(user,pwd)
            s.sendmail(user,dest,msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)

def _email_base(inner):
    return f"""<div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;background:#f8fafc;border-radius:16px;overflow:hidden;">
  <div style="background:linear-gradient(135deg,#0d2645,#2196f3);padding:28px 32px;">
    <h2 style="color:#fff;margin:0;font-size:1.2rem;font-weight:700;">🏗️ Emogis — Requisições Internas</h2>
  </div>
  <div style="padding:28px 32px;background:#fff;">{inner}</div>
  <div style="padding:16px 32px;background:#f0f4f8;text-align:center;">
    <p style="color:#94a3b8;font-size:.75rem;margin:0;">© 2024 Emogis — Construção Industrial</p>
  </div>
</div>"""

def notificar_nova(titulo,solicitante,area_destino,obra,prioridade,emails_destino,email_solicitante):
    cores={"Urgente":"#ef4444","Alta":"#f59e0b","Média":"#3b82f6","Baixa":"#10b981"}
    cor=cores.get(prioridade,"#3b82f6")
    inner=f"""<p style="color:#475569;margin-top:0;">Nova requisição submetida para <strong>{area_destino}</strong>.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0;border-radius:10px;overflow:hidden;">
      <tr><td style="padding:10px 14px;background:#f8fafc;color:#64748b;font-weight:600;width:38%;">Título</td><td style="padding:10px 14px;background:#f8fafc;color:#0d2645;font-weight:700;">{titulo}</td></tr>
      <tr><td style="padding:10px 14px;color:#64748b;font-weight:600;">Solicitante</td><td style="padding:10px 14px;">{solicitante}</td></tr>
      <tr><td style="padding:10px 14px;background:#f8fafc;color:#64748b;font-weight:600;">Obra</td><td style="padding:10px 14px;background:#f8fafc;">{obra or '—'}</td></tr>
      <tr><td style="padding:10px 14px;color:#64748b;font-weight:600;">Prioridade</td><td style="padding:10px 14px;"><span style="background:{cor};color:#fff;padding:3px 12px;border-radius:20px;font-size:.8rem;font-weight:600;">{prioridade}</span></td></tr>
    </table>
    <div style="text-align:center;margin-top:24px;">
      <a href="https://sistema-solicitacoes-mor4pc9vk2pqrwjrxnvblo.streamlit.app" style="background:linear-gradient(135deg,#2196f3,#1565c0);color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:700;">Ver Requisição →</a>
    </div>"""
    html = _email_base(inner)
    todos = list(set(emails_destino + ([email_solicitante] if email_solicitante else [])))
    for e in todos:
        if e: _enviar(e, f"[Emogis] Nova requisição: {titulo}", html)  # retorna (ok, err) mas ignoramos aqui

def notificar_atualizacao(titulo,novo_status,obs,email_solicitante):
    if not email_solicitante: return
    cores={"Concluído":"#10b981","Recusado":"#ef4444","Em andamento":"#3b82f6","Pendente":"#f59e0b"}
    cor=cores.get(novo_status,"#3b82f6")
    obs_html=f'<div style="background:#f0f7ff;padding:14px;border-radius:8px;border-left:3px solid #2196f3;margin-top:16px;"><p style="margin:0;color:#1e40af;"><strong>Observações:</strong> {obs}</p></div>' if obs else ""
    inner=f"""<p style="color:#475569;margin-top:0;">A sua requisição foi atualizada.</p>
    <p style="font-size:1.1rem;color:#0d2645;font-weight:700;margin:8px 0;">{titulo}</p>
    <p>Estado: <span style="background:{cor};color:#fff;padding:4px 16px;border-radius:20px;font-weight:700;">{novo_status}</span></p>
    {obs_html}
    <div style="text-align:center;margin-top:24px;">
      <a href="https://sistema-solicitacoes-mor4pc9vk2pqrwjrxnvblo.streamlit.app" style="background:linear-gradient(135deg,#2196f3,#1565c0);color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:700;">Ver Requisição →</a>
    </div>"""
    _enviar(email_solicitante, f"[Emogis] Requisição atualizada: {titulo} -> {novo_status}", _email_base(inner))

# ─── CONSTANTES ────────────────────────────────────────────────────────────────
STATUS_OPCOES    = ["Pendente","Em andamento","Concluído","Recusado"]
PRIORIDADE_OPCOES= ["Baixa","Média","Alta","Urgente"]
AREAS_DESTINO    = ["Logística","Compras","Produção","Qualidade"]
TITULOS_LOGISTICA= ["Transporte","Consumíveis","Locação de equipamentos"]
AREAS_COM_PF     = ["Produção","Compras","Direção Obra"]
ICONE_STATUS     = {"Pendente":"🟡","Em andamento":"🔵","Concluído":"🟢","Recusado":"🔴"}
COR_STATUS       = {"Pendente":"#f59e0b","Em andamento":"#3b82f6","Concluído":"#10b981","Recusado":"#ef4444"}

init_db()
if "usuario" not in st.session_state: st.session_state.usuario = None

# ─── HELPERS VISUAIS ───────────────────────────────────────────────────────────
def _logo_sidebar():
    for f in ["logo.png","logo.jpg"]:
        p=Path(f)
        if p.exists():
            ext="jpeg" if f.endswith(".jpg") else "png"
            b64=base64.b64encode(p.read_bytes()).decode()
            st.markdown(f"""
            <div style="overflow:hidden;height:88px;display:flex;align-items:center;justify-content:center;margin-bottom:4px;">
              <img src="data:image/{ext};base64,{b64}"
                   style="width:110px;mix-blend-mode:lighten;object-fit:cover;object-position:top center;
                          filter:brightness(1.2) drop-shadow(0 0 8px rgba(33,150,243,.4));" />
            </div>""", unsafe_allow_html=True)
            return

def _logo_login():
    for f in ["logo.jpg","logo.png"]:
        p=Path(f)
        if p.exists():
            ext="jpeg" if f.endswith(".jpg") else "png"
            b64=base64.b64encode(p.read_bytes()).decode()
            blend="multiply" if f.endswith(".jpg") else "lighten"
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:8px;">
              <img src="data:image/{ext};base64,{b64}"
                   style="width:75%;max-width:280px;mix-blend-mode:{blend};filter:brightness(1.05) contrast(1.05);" />
            </div>""", unsafe_allow_html=True)
            return
    st.markdown("<h1 style='text-align:center;color:#fff;'>🏗️</h1>", unsafe_allow_html=True)

def mostrar_header(titulo):
    emoji = titulo.split()[0]
    resto = ' '.join(titulo.split()[1:])
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0d2645 0%,#1565c0 50%,#2196f3 100%);
                padding:1.2rem 1.8rem;border-radius:14px;margin-bottom:1.2rem;
                box-shadow:0 4px 20px rgba(13,38,69,.25);display:flex;align-items:center;gap:12px;">
      <span style="font-size:1.5rem;">{emoji}</span>
      <div>
        <h2 style="color:#fff;margin:0;font-size:1.25rem;font-weight:700;">{resto}</h2>
        <p style="color:rgba(255,255,255,.5);margin:0;font-size:.72rem;letter-spacing:1.5px;text-transform:uppercase;">Emogis — Construção Industrial</p>
      </div>
    </div>""", unsafe_allow_html=True)

def badge_status(s):
    cor=COR_STATUS.get(s,"#64748b")
    return f'<span style="background:{cor};color:#fff;padding:3px 12px;border-radius:20px;font-size:.78rem;font-weight:700;">{ICONE_STATUS.get(s,"")} {s}</span>'

# ─── LOGIN ─────────────────────────────────────────────────────────────────────
def tela_login():
    st.markdown("""
    <style>
      .stApp{background:linear-gradient(135deg,#060e1a 0%,#0a1e38 40%,#0d2d50 70%,#0a1e38 100%)!important;}
      [data-testid="stSidebar"]{display:none;}
      .block-container{padding-top:1.5rem!important;}
      .stTextInput input{background:rgba(255,255,255,.92)!important;border:1.5px solid rgba(255,255,255,.2)!important;color:#0d2137!important;border-radius:10px!important;}
      .stTextInput input:focus{border-color:#2196f3!important;box-shadow:0 0 0 3px rgba(33,150,243,.25)!important;}
      .stTextInput label{color:rgba(255,255,255,.65)!important;font-size:.82rem!important;font-weight:500!important;letter-spacing:.5px!important;}
      .stFormSubmitButton button{background:linear-gradient(135deg,#2196f3,#1565c0)!important;color:#fff!important;border:none!important;border-radius:10px!important;font-weight:700!important;font-size:.95rem!important;padding:.65rem!important;width:100%!important;box-shadow:0 4px 18px rgba(33,150,243,.45)!important;letter-spacing:1.5px!important;}
    </style>""", unsafe_allow_html=True)
    st.markdown("""
    <div style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;">
      <div style="position:absolute;width:500px;height:500px;background:radial-gradient(circle,rgba(33,150,243,.12),transparent 70%);top:-100px;right:-100px;border-radius:50%;"></div>
      <div style="position:absolute;width:350px;height:350px;background:radial-gradient(circle,rgba(21,101,192,.1),transparent 70%);bottom:50px;left:-80px;border-radius:50%;"></div>
    </div>""", unsafe_allow_html=True)
    _, col, _ = st.columns([1,1.1,1])
    with col:
        _logo_login()
        st.markdown('<div style="height:1px;background:linear-gradient(90deg,transparent,rgba(33,150,243,.5),transparent);margin:.8rem 0 1.4rem;"></div><p style="text-align:center;color:rgba(255,255,255,.4);font-size:.75rem;letter-spacing:3px;text-transform:uppercase;margin-bottom:1.6rem;">Requisições Internas</p>', unsafe_allow_html=True)
        with st.form("login_form"):
            login = st.text_input("Utilizador")
            senha = st.text_input("Palavra-passe", type="password")
            entrar = st.form_submit_button("ENTRAR", use_container_width=True)
        if entrar:
            u=verificar_login(login,senha)
            if u: st.session_state.usuario=u; st.rerun()
            else: st.markdown("<p style='text-align:center;color:#f87171;font-size:.88rem;margin-top:.5rem;'>⚠️ Utilizador ou palavra-passe inválidos.</p>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center;color:rgba(255,255,255,.15);font-size:.7rem;margin-top:2rem;'>© 2024 Emogis — Construção Industrial</p>", unsafe_allow_html=True)

# ─── NOVA REQUISIÇÃO ───────────────────────────────────────────────────────────
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

    descricao = ""
    if area_destino == "Logística" and titulo == "Transporte":
        st.markdown("**📝 Detalhes do Transporte**")
        c1,c2 = st.columns(2)
        with c1:
            local_r = st.text_input("📍 Local de recolha")
            data_r  = st.date_input("📅 Data de recolha")
        with c2:
            local_e = st.text_input("📍 Local de entrega")
            data_e  = st.date_input("📅 Data de entrega")
        tipo_c = st.text_input("🚛 Tipo de Camião")
        c3,c4 = st.columns(2)
        with c3: peso = st.text_input("⚖️ Peso total")
        with c4: dims = st.text_input("📐 Dimensões")
        st.markdown("**📦 Como está acondicionado?**")
        acond = st.radio("", ["Caixas","Paletes","Tubos / Vigas","Outro"], horizontal=True, label_visibility="collapsed")
        obs_a = ""
        if acond=="Paletes": obs_a = st.text_input("📏 Dimensões das paletes")
        elif acond=="Outro": obs_a = st.text_input("Descreva o acondicionamento")
        descricao=(f"Local de recolha: {local_r}\nData de recolha: {data_r}\n"
                   f"Local de entrega: {local_e}\nData de entrega: {data_e}\n"
                   f"Tipo de Camião: {tipo_c}\nPeso total: {peso}\nDimensões: {dims}\n"
                   f"Acondicionamento: {acond}"+( f" — {obs_a}" if obs_a else ""))

    elif area_destino == "Logística" and titulo == "Consumíveis":
        st.markdown("**📝 Detalhes**")
        tipo=st.text_input("Tipo"); qtd=st.text_input("Quantidade"); quem=st.text_input("Quem recolhe")
        c1,c2=st.columns(2)
        with c1: local_r=st.text_input("Local de recolha")
        with c2: data_r=st.date_input("Data de recolha")
        descricao=f"Tipo: {tipo}\nQuantidade: {qtd}\nQuem recolhe: {quem}\nLocal de recolha: {local_r}\nData de recolha: {data_r}"

    elif area_destino == "Logística" and titulo == "Locação de equipamentos":
        st.markdown("**📝 Detalhes**")
        tipo_eq=st.text_input("Tipo de equipamento")
        c1,c2=st.columns(2)
        with c1: data_i=st.date_input("Data de início")
        with c2: periodo=st.text_input("Período previsto")
        descricao=f"Tipo: {tipo_eq}\nData de início: {data_i}\nPeríodo previsto: {periodo}"
    else:
        descricao=st.text_area("📝 Descrição / Detalhes", height=150)

    prioridade=st.selectbox("⚡ Prioridade", PRIORIDADE_OPCOES, index=1)

    if st.button("📤 Enviar Requisição", type="primary"):
        if area_destino!="Logística" and titulo.strip()=="":
            st.warning("Informe um título.")
        elif obra.strip()=="":
            st.warning("Informe a obra.")
        else:
            criar_solicitacao(titulo,descricao,usuario["nome"],usuario["area"],area_destino,prioridade,obra,pf)
            users_dest=listar_usuarios_area(area_destino)
            emails_dest=[u[1] for u in users_dest if u[1]]
            notificar_nova(titulo,usuario["nome"],area_destino,obra,prioridade,emails_dest,usuario["email"])
            st.success("✅ Requisição enviada com sucesso!")

# ─── MINHAS REQUISIÇÕES ────────────────────────────────────────────────────────
def aba_minhas_solicitacoes(usuario):
    mostrar_header("📤 Minhas Requisições")
    sf=st.selectbox("Filtrar por status",["Todos"]+STATUS_OPCOES,key="filtro_minhas")
    df=buscar_solicitacoes(status=sf,somente_minhas=True,solicitante=usuario["nome"])
    if df.empty: st.info("Nenhuma requisição encontrada."); return
    for _,row in df.iterrows():
        ic=ICONE_STATUS.get(row['status'],"⚪")
        with st.expander(f"{ic} #{row['id']} — {row['titulo']} → {row['area_destino']} | {row['status']}"):
            c1,c2,c3=st.columns(3)
            c1.write(f"**🏗️ Obra:** {row.get('obra','') or '—'}")
            c1.write(f"**📋 PF:** {row.get('pf','') or '—'}")
            c2.write(f"**⚡ Prioridade:** {row['prioridade']}")
            c3.write(f"**📅 Criado:** {str(row['data_criacao'])[:16]}")
            c3.write(f"**🔄 Atualizado:** {str(row['data_atualizacao'])[:16]}")
            st.write("**📝 Descrição:**"); st.code(row['descricao'] or "",language=None)
            if row['observacoes']:
                st.markdown(f'<div style="background:#f0f7ff;padding:12px;border-radius:8px;border-left:3px solid #2196f3;margin-top:8px;"><strong>💬 Resposta:</strong> {row["observacoes"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="margin-top:8px;">{badge_status(row["status"])}</div>', unsafe_allow_html=True)

# ─── RECEBIDAS ─────────────────────────────────────────────────────────────────
def aba_recebidas(usuario):
    mostrar_header(f"📥 Recebidas — {usuario['area']}")
    sf=st.selectbox("Filtrar por status",["Todos"]+STATUS_OPCOES,key="filtro_rec")
    df=buscar_solicitacoes(area=usuario["area"],status=sf)
    if df.empty: st.info("Nenhuma requisição encontrada."); return
    for _,row in df.iterrows():
        ic=ICONE_STATUS.get(row['status'],"⚪")
        with st.expander(f"{ic} #{row['id']} — {row['titulo']} | {row['solicitante']} ({row['area_origem']}) | ⚡{row['prioridade']}"):
            c1,c2,c3=st.columns(3)
            c1.write(f"**🏗️ Obra:** {row.get('obra','') or '—'}")
            c1.write(f"**📋 PF:** {row.get('pf','') or '—'}")
            c2.write(f"**📅 Criado:** {str(row['data_criacao'])[:16]}")
            c3.write(f"**🔄 Atualizado:** {str(row['data_atualizacao'])[:16]}")
            st.write("**📝 Descrição:**"); st.code(row['descricao'] or "",language=None)
            st.markdown("---")
            ca,cb=st.columns(2)
            with ca:
                novo_s=st.selectbox("Atualizar status",STATUS_OPCOES,
                    index=STATUS_OPCOES.index(row['status']) if row['status'] in STATUS_OPCOES else 0,
                    key=f"s_{row['id']}")
            with cb:
                obs=st.text_area("💬 Observações / Resposta",value=row['observacoes'] or "",key=f"o_{row['id']}",height=100)
            if st.button("💾 Guardar",key=f"g_{row['id']}",type="primary"):
                atualizar_status(row['id'],novo_s,obs)
                email_sol=get_email_solicitante(row['solicitante'])
                notificar_atualizacao(row['titulo'],novo_s,obs,email_sol)
                st.success("✅ Atualizado e notificação enviada!"); st.rerun()

# ─── DASHBOARD ─────────────────────────────────────────────────────────────────
def aba_dashboard(usuario):
    mostrar_header("📊 Dashboard")
    df=buscar_solicitacoes()
    if df.empty: st.info("Ainda não há requisições registadas."); return

    # Métricas coloridas
    c1,c2,c3,c4=st.columns(4)
    with c1:
        st.markdown('<div class="metric-pendente">', unsafe_allow_html=True)
        st.metric("🟡 Pendentes", len(df[df["status"]=="Pendente"]))
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-andamento">', unsafe_allow_html=True)
        st.metric("🔵 Em andamento", len(df[df["status"]=="Em andamento"]))
        st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric-concluido">', unsafe_allow_html=True)
        st.metric("🟢 Concluídas", len(df[df["status"]=="Concluído"]))
        st.markdown('</div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="metric-recusado">', unsafe_allow_html=True)
        st.metric("🔴 Recusadas", len(df[df["status"]=="Recusado"]))
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    ca,cb=st.columns(2)
    with ca:
        st.markdown("#### Por status")
        vc=df["status"].value_counts().reset_index()
        vc.columns=["status","count"]
        cores_map={"Pendente":"#f59e0b","Em andamento":"#3b82f6","Concluído":"#10b981","Recusado":"#ef4444"}
        try:
            import plotly.express as px
            fig=px.bar(vc,x="status",y="count",color="status",
                       color_discrete_map=cores_map,
                       labels={"status":"","count":"Nº"},
                       template="plotly_white")
            fig.update_layout(showlegend=False,margin=dict(t=10,b=10))
            st.plotly_chart(fig,use_container_width=True)
        except:
            st.bar_chart(df["status"].value_counts())
    with cb:
        st.markdown("#### Por área")
        try:
            import plotly.express as px
            vc2=df["area_destino"].value_counts().reset_index()
            vc2.columns=["area","count"]
            fig2=px.bar(vc2,x="area",y="count",color="area",template="plotly_white",
                        labels={"area":"","count":"Nº"})
            fig2.update_layout(showlegend=False,margin=dict(t=10,b=10))
            st.plotly_chart(fig2,use_container_width=True)
        except:
            st.bar_chart(df["area_destino"].value_counts())

    st.markdown("#### Todas as requisições")
    f1,f2,f3=st.columns(3)
    with f1: af=st.selectbox("Área",["Todas"]+AREAS_DESTINO,key="da")
    with f2: sf=st.selectbox("Status",["Todos"]+STATUS_OPCOES,key="ds")
    with f3: ob=st.text_input("🔍 Pesquisar obra",key="do")
    dff=buscar_solicitacoes(area=af,status=sf)
    if ob: dff=dff[dff["obra"].str.contains(ob,case=False,na=False)]

    # Tabela com badge de status colorido
    if not dff.empty:
        cols=[c for c in ["id","titulo","solicitante","area_origem","area_destino","obra","pf","prioridade","status","data_criacao"] if c in dff.columns]
        st.dataframe(
            dff[cols].style.apply(lambda row: [
                f"background-color:{COR_STATUS.get(row['status'],'#fff')}22;color:{COR_STATUS.get(row['status'],'#000')};font-weight:600"
                if col=="status" else "" for col in cols
            ], axis=1),
            use_container_width=True
        )

# ─── ADMIN ─────────────────────────────────────────────────────────────────────
def aba_admin():
    mostrar_header("⚙️ Administração")
    df=pd.read_sql_query("SELECT id,nome,login,area,perfil,email FROM usuarios ORDER BY area,nome",get_conn())
    st.dataframe(df,use_container_width=True)
    st.markdown("#### Adicionar utilizador")
    c1,c2=st.columns(2)
    with c1:
        nome=st.text_input("Nome completo"); login=st.text_input("Login"); senha=st.text_input("Senha",type="password")
    with c2:
        area_op=AREAS_DESTINO+["Direção Obra","TI","Outra"]
        area=st.selectbox("Área",area_op); area_c=st.text_input("Se 'Outra':"); email=st.text_input("Email"); perfil=st.selectbox("Perfil",["usuario","admin"])
    if st.button("➕ Criar utilizador",type="primary"):
        af=area_c if area=="Outra" and area_c else area
        if not(nome and login and senha): st.warning("Preencha nome, login e senha.")
        else:
            try:
                c=get_conn().cursor()
                c.execute("INSERT INTO usuarios(nome,login,senha,area,perfil,email) VALUES(%s,%s,%s,%s,%s,%s)",(nome,login,_hash(senha),af,perfil,email))
                get_conn().commit(); c.close(); st.success(f"✅ {nome} criado!"); st.rerun()
            except psycopg2.IntegrityError: get_conn().rollback(); st.error("Login já existe.")

    st.markdown("---")
    st.markdown("#### 📧 Estado das notificações de email")
    host=st.secrets.get("SMTP_HOST","")
    if host:
        st.success(f"✅ Email configurado — a enviar via `{st.secrets.get('SMTP_USER','')}`")
        st.markdown("**Testar envio de email:**")
        email_teste = st.text_input("Endereço de teste", value=st.secrets.get("SMTP_USER",""))
        if st.button("📧 Enviar email de teste"):
            ok, err = _enviar(email_teste, "[Emogis] Teste de email", _email_base("<p>Este é um email de teste do sistema Emogis.</p>"))
            if ok:
                st.success(f"✅ Email enviado com sucesso para {email_teste}!")
            else:
                st.error(f"❌ Erro ao enviar: {err}")
                if "534" in err or "535" in err or "Username and Password" in err:
                    st.warning("💡 Erro de autenticação — verifique se a App Password está correta nas Secrets.")
                elif "SSL" in err or "TLS" in err:
                    st.warning("💡 Erro de SSL — tente mudar SMTP_PORT para 465 nas Secrets.")
                elif "getaddrinfo" in err or "Name or service" in err:
                    st.warning("💡 Erro de rede — o servidor SMTP não está acessível.")
    else:
        st.warning("⚠️ Email não configurado. Adicione nas Secrets do Streamlit Cloud:")
        st.code("""SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USER = "juliana.sassano@emogis.pt"
SMTP_PASS = "xxxx xxxx xxxx xxxx"  # App Password do Gmail""", language="toml")

# ─── APP PRINCIPAL ─────────────────────────────────────────────────────────────
if st.session_state.usuario is None:
    tela_login()
else:
    u=st.session_state.usuario
    with st.sidebar:
        _logo_sidebar()
        st.markdown(f"""
        <div style="padding:12px 8px 4px;">
          <p style="color:#e2e8f0;font-weight:700;font-size:.95rem;margin:0;">{u['nome']}</p>
          <p style="color:#64a0c8;font-size:.78rem;margin:4px 0 0;text-transform:uppercase;letter-spacing:1px;">{u['area']}</p>
          <p style="color:#4a7fa8;font-size:.72rem;margin:2px 0 0;">{u['email'] or ''}</p>
        </div>""", unsafe_allow_html=True)
        st.markdown("<hr style='border-color:rgba(255,255,255,.08);margin:12px 0;'/>", unsafe_allow_html=True)
        if st.button("🚪 Sair"): st.session_state.usuario=None; st.rerun()

    abas=["📊 Dashboard","➕ Nova Requisição","📤 Minhas Requisições","📥 Recebidas"]
    if u["perfil"]=="admin": abas.append("⚙️ Administração")
    tabs=st.tabs(abas)
    with tabs[0]: aba_dashboard(u)
    with tabs[1]: aba_nova_solicitacao(u)
    with tabs[2]: aba_minhas_solicitacoes(u)
    with tabs[3]: aba_recebidas(u)
    if u["perfil"]=="admin":
        with tabs[4]: aba_admin()

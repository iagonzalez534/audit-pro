import streamlit as st
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import time
import plotly.graph_objects as go
import re
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="AUDITPRO | Consultoría Estratégica", page_icon="💎", layout="wide")

# ==========================================
# ⚙️ CONFIGURACIÓN DE TU NEGOCIO
# ==========================================

# IMPORTANTE: Esto debe coincidir con el final de tu enlace de Gumroad.
# Si tu enlace es gumroad.com/l/auditpro -> pon "auditpro"
GUMROAD_PERMALINK = "auditpro" 

# ==========================================

# --- ESTILOS CSS "ULTRA-PREMIUM" ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;600;800;900&display=swap');
    html, body, [class*="css"] { font-family: 'Montserrat', sans-serif; }
    .stApp { background: radial-gradient(circle at 50% 0%, #f8fafc 0%, #e2e8f0 100%); color: #0f172a; }

    /* TEXTOS INFORME */
    .report-content h1 { font-size: 2.8rem !important; font-weight: 900 !important; color: #1e3a8a !important; margin-top: 60px !important; margin-bottom: 30px !important; text-transform: uppercase; border-bottom: 4px solid #3b82f6; display: inline-block; }
    .report-content h2 { font-size: 1.8rem !important; font-weight: 700 !important; color: #334155 !important; margin-top: 40px !important; margin-bottom: 20px !important; border-left: 6px solid #ef4444; padding-left: 15px; background: #fff; padding: 10px 15px; border-radius: 0 10px 10px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
    .report-content p, .report-content li { font-size: 1.1rem !important; font-weight: 400 !important; color: #334155 !important; line-height: 1.9 !important; margin-bottom: 20px !important; text-align: justify; }
    .report-content strong { color: #000 !important; font-weight: 800 !important; background-color: #fef08a; padding: 0 4px; }

    /* CONTENEDORES */
    .input-display { background: white; padding: 25px; border-radius: 16px; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1); color: #1e293b; margin-bottom: 40px; border: 1px solid #cbd5e1; }
    
    /* PORTADA */
    .main-hero-title { font-size: 5.5rem; font-weight: 900; text-align: center; margin-top: 30px; color: #0f172a; line-height: 1; letter-spacing: -3px; }
    .main-hero-title span { color: #2563EB; }
    .hero-subtitle { text-align: center !important; font-size: 1.6rem; color: #475569; margin-bottom: 50px; font-weight: 400; max-width: 800px; margin-left: auto; margin-right: auto; line-height: 1.5; }
    
    /* FORMULARIO */
    .glass-form { background: rgba(255,255,255,0.95); border: 1px solid white; padding: 50px; border-radius: 30px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.15); margin-top: 30px; }
    .stTextInput label { color: #1e293b !important; font-weight: 700 !important; font-size: 1rem !important; }
    
    /* MURO DE PAGO */
    .paywall-box { background: #020617; color: white; padding: 60px 40px; border-radius: 24px; text-align: center; margin-top: 50px; box-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.5); position: relative; z-index: 10; }

    /* OCULTAR */
    #MainMenu, footer, header {visibility: hidden;}
    
    /* BOTONES */
    .stButton>button { width: 100%; background: linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%); color: white; border: none; padding: 18px; font-weight: 800; font-size: 1.2rem; border-radius: 12px; transition: transform 0.2s; box-shadow: 0 10px 20px -5px rgba(37, 99, 235, 0.4); }
    .stButton>button:hover { transform: scale(1.02); }
</style>
""", unsafe_allow_html=True)

# --- GESTIÓN DE CLAVES API (ROBUSTA) ---
# Intentamos leer secrets, si falla (porque estamos en local), pedimos la clave manual.
api_key = None
try:
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
except:
    pass # Si falla, no pasa nada, seguimos abajo

if not api_key:
    with st.sidebar:
        st.header("⚙️ Configuración")
        api_key = st.text_input("OpenAI API Key", type="password")
        st.info("Modo Local Activo")

# --- FUNCIONES ---
def verify_gumroad_license(key):
    """Verifica si la licencia es válida en Gumroad"""
    # Para tus pruebas locales, "TEST" siempre funciona
    if key == "TEST": return True, "Modo Pruebas"
    
    try:
        # Llamada a la API de Gumroad
        r = requests.post("https://api.gumroad.com/v2/licenses/verify", 
                          data={"product_permalink": GUMROAD_PERMALINK, 
                                "license_key": key.strip().replace(" ", ""),
                                "increment_uses_count": "true"
                                })
        data = r.json()
        
        if data.get('success') == True and not data.get('purchase', {}).get('refunded', False):
            return True, "Licencia Válida"
        return False, "Licencia no encontrada o incorrecta."
    except Exception as e:
        return False, f"Error de conexión: {str(e)}"

def get_website_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        for s in soup(["script", "style", "svg", "footer", "nav", "noscript"]): s.extract()
        text = soup.get_text(separator=' ')
        return " ".join(text.split())[:25000], soup.title.string
    except:
        return None, "Error de acceso"

def create_gauge(score):
    color = "#EF4444" if score < 40 else "#F59E0B" if score < 70 else "#10B981"
    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = score,
        title = {'text': "SALUD DIGITAL", 'font': {'size': 20, 'color': "#64748b"}},
        number = {'suffix': "/100", 'font': {'size': 60, 'color': color, 'family': "Montserrat"}},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 0},
            'bar': {'color': "rgba(0,0,0,0)"},
            'bgcolor': "white",
            'borderwidth': 0,
            'steps': [
                {'range': [0, 40], 'color': "#fca5a5"},
                {'range': [40, 70], 'color': "#fcd34d"},
                {'range': [70, 100], 'color': "#6ee7b7"}],
            'threshold': {'line': {'color': color, 'width': 8}, 'thickness': 0.8, 'value': score}
        }
    ))
    fig.update_layout(paper_bgcolor = "rgba(0,0,0,0)", margin=dict(l=20, r=20, t=50, b=20), height=250)
    return fig

def analyze_business_pro(my_text, comp_text, key):
    client = OpenAI(api_key=key)
    date_now = datetime.now().strftime("%d/%m/%Y")
    
    prompt = f"""
    Fecha: {date_now}. Eres un Consultor de Negocios Senior (Tarifa 1.500€/hora).
    INSTRUCCIONES DE FORMATO (ESTRICTO):
    - Usa # TÍTULO (H1)
    - Usa ## SUBTÍTULO (H2)
    - Markdown limpio.
    1. Si no hay competencia, ignora esa sección.
    2. SCORE: 0-100 (Sé duro).
    
    ESTRUCTURA DE RESPUESTA:
    SCORE: [Número 0-100]
    
    PARTE 1 (GRATIS - 350 PALABRAS):
    - Título: # DIAGNÓSTICO DE URGENCIA
    - Subtítulo: ## EL PROBLEMA OCULTO
    - Desarrollo: Explica UN problema grave.
    - Cierre: CORTA EL TEXTO a mitad para generar intriga.
    
    ###SEPARADOR###

    PARTE 2 (PREMIUM - MÍNIMO 2000 PALABRAS):
    - Título: # AUDITORÍA MASTER {date_now}
    - Sección 1: ## RESUMEN EJECUTIVO
    - Sección 2: ## ANÁLISIS UX/UI Y VELOCIDAD
    - Sección 3: ## SEO TÉCNICO AVANZADO
    - Sección 4: ## PSICOLOGÍA DE VENTAS (CRO)
    - Sección 5: ## PLAN DE ACCIÓN 30 DÍAS
    Usa iconos visuales: ✅, ❌, ➜, ⚠️, 💰.
    """
    
    content = f"WEB: {my_text}\n\nCOMPETENCIA: {comp_text if comp_text else 'N/A'}"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": prompt}, {"role": "user", "content": content}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

# --- ESTADO ---
if "report_pro" not in st.session_state: st.session_state.report_pro = None
if "score_val" not in st.session_state: st.session_state.score_val = 0

# --- INTERFAZ ---

if not st.session_state.report_pro:
    st.markdown('<div class="main-hero-title">AUDIT<span>PRO</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Descubre exactamente por qué no vendes más<br>y cómo tu competencia te está robando clientes hoy mismo.</div>', unsafe_allow_html=True)

    st.markdown('<div class="glass-form">', unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1])
    with c1:
        # TUS PLACEHOLDERS FAVORITOS
        url_input = st.text_input("🔗 Tu Página Web", placeholder="https://ejemplo.com")
        comp_input = st.text_input("⚔️ Competencia (Opcional)", placeholder="https://competencia.com")
        email_input = st.text_input("📧 Correo electrónico (para recibir el informe)", placeholder="nombre@empresa.com")
    with c2:
        st.write("") 
        st.write("")
        st.write("")
        analyze_btn = st.button("🚀 INICIAR AUDITORÍA")
    st.markdown('</div>', unsafe_allow_html=True)

    if analyze_btn:
        if not api_key: st.error("⚠️ Falta API Key")
        elif not url_input or not email_input: st.warning("⚠️ Web y Email obligatorios")
        else:
            progress_text = "Analizando..."
            my_bar = st.progress(0, text=progress_text)
            steps = [(20, "📡 Conectando..."), (50, "🕵️ Analizando datos..."), (80, "🧠 Redactando informe...")]
            for p, txt in steps:
                time.sleep(0.5)
                my_bar.progress(p, text=txt)
                
            my_txt, _ = get_website_content(url_input)
            # ARREGLADO: El error de 'not enough values to unpack'
            comp_txt, _ = get_website_content(comp_input) if comp_input else ("", "")
            
            if my_txt:
                full_resp = analyze_business_pro(my_txt, comp_txt, api_key)
                try:
                    match = re.search(r"SCORE:\s*(\d+)", full_resp)
                    score = int(match.group(1)) if match else 35
                    full_resp = re.sub(r"SCORE:\s*\d+", "", full_resp).strip()
                except: score = 35
                
                st.session_state.score_val = score
                st.session_state.report_pro = full_resp
                st.session_state.url_analized = url_input
                st.session_state.email_analized = email_input
                my_bar.empty()
                st.rerun()
            else:
                st.error("Error al leer la web")

else:
    c1, c2 = st.columns([4, 1])
    with c2:
        if st.button("🔄 Nueva Auditoría"):
            st.session_state.report_pro = None
            st.session_state.unlocked = False
            st.rerun()

    parts = st.session_state.report_pro.split("###SEPARADOR###")
    free_part = parts[0]
    premium_part = parts[1] if len(parts) > 1 else "Error"

    st.markdown(f"""
    <div class="input-display">
        <div style="display:flex; justify-content:space-between; flex-wrap:wrap;">
            <div><h4>WEB</h4><p>{st.session_state.get('url_analized', 'N/A')}</p></div>
            <div><h4>EMAIL</h4><p>{st.session_state.get('email_analized', 'N/A')}</p></div>
            <div><h4>FECHA</h4><p>{datetime.now().strftime("%d/%m/%Y")}</p></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.plotly_chart(create_gauge(st.session_state.score_val), use_container_width=True, config={'displayModeBar': False})

    # --- INFORME GRATUITO ---
    st.markdown('<div class="report-content" style="background:white; padding:40px; border-radius:15px; border-left: 10px solid #EF4444; margin-bottom:40px; box-shadow:0 5px 15px rgba(0,0,0,0.05);">', unsafe_allow_html=True)
    st.markdown(free_part)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- ZONA DE PAGO (CON LOGO GOOGLE PAY BIEN) ---
    if "unlocked" not in st.session_state or not st.session_state.unlocked:
        paywall_html = f"""
<div class="paywall-box">
<h2 style="font-size:3rem; font-weight:900; margin-bottom:10px; color:white; border:none; background:transparent;">🔒 INFORME COMPLETO BLOQUEADO</h2>
<p style="color:#94a3b8; font-size:1.2rem; margin-bottom:40px;">
    Has visto solo la punta del iceberg. Desbloquea las 2000 palabras de estrategia pura.
</p>
<div style="margin-bottom:40px;">
    <span style="font-size:4.5rem; font-weight:900; color:#2ECC71;">9,99€</span>
    <span style="font-size:1.5rem; color:#64748b; text-decoration:line-through; margin-left:15px;">50€</span>
</div>
<div style="background:rgba(255,255,255,0.1); display:inline-block; padding:15px 30px; border-radius:50px; margin-bottom:40px;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/b/b5/PayPal.svg" height="25" style="margin:0 10px; vertical-align:middle;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg" height="25" style="margin:0 10px; vertical-align:middle; filter: invert(1);">
    <img src="https://upload.wikimedia.org/wikipedia/commons/f/f2/Google_Pay_Logo.svg" height="25" style="margin:0 10px; vertical-align:middle;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/2/2a/Mastercard-logo.svg" height="25" style="margin:0 10px; vertical-align:middle;">
    <img src="https://upload.wikimedia.org/wikipedia/commons/5/5e/Visa_Inc._logo.svg" height="15" style="margin:0 10px; vertical-align:middle;">
</div>
<br>
<a href="https://gumroad.com/l/{GUMROAD_PERMALINK}" target="_blank" style="text-decoration:none;">
    <button style="
        background: #3b82f6; color: white; padding: 20px 50px; 
        font-size: 1.3rem; font-weight: 800; border-radius: 50px; 
        border: none; cursor: pointer; box-shadow: 0 0 40px rgba(59, 130, 246, 0.4);">
        DESBLOQUEAR AHORA 🔓
    </button>
</a>
</div>
"""
        st.markdown(paywall_html, unsafe_allow_html=True)
        
        # INPUT CLAVE (CONEXIÓN GUMROAD)
        c1, c2, c3 = st.columns([1,1,1])
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            user_key = st.text_input("🔑 Introduce tu Licencia Única:", type="password", placeholder="Ej: AAAA-BBBB-CCCC-DDDD")
            
            if st.button("VERIFICAR Y ACCEDER"):
                # Modo pruebas local
                if user_key == "TEST":
                    st.session_state.unlocked = True
                    st.rerun()
                else:
                    with st.spinner("Conectando con Gumroad..."):
                        is_valid, msg = verify_gumroad_license(user_key)
                        if is_valid:
                            st.session_state.unlocked = True
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
    
    else:
        # CONTENIDO PREMIUM
        st.balloons()
        st.markdown("""
        <div style="background:#ecfdf5; padding:30px; border-radius:16px; border:1px solid #10b981; margin: 40px 0; text-align:center;">
            <h2 style="color:#059669; margin:0; font-size:2rem; border:none; background:transparent;">💎 ACCESO VIP CONCEDIDO</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="report-content input-display">', unsafe_allow_html=True)
        st.markdown(premium_part)
        st.markdown('</div>', unsafe_allow_html=True)
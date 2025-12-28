import streamlit as st
import json
import os
import random
import hashlib
import pandas as pd
import io
from datetime import date, datetime
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import RetryError, ServiceUnavailable
import streamlit.components.v1 as components

# ==========================================
# 1. 云端数据库初始化 (性能与稳定性加固)
# ==========================================
@st.cache_resource
def init_firestore():
    """使用 cache_resource 确保数据库连接只初始化一次"""
    if not firebase_admin._apps:
        try:
            if "firebase" not in st.secrets:
                st.error("未找到 [firebase] 配置块，请检查 Streamlit Secrets 设置。")
                st.stop()
            
            cred_dict = dict(st.secrets["firebase"])
            # 强化私钥格式处理，解决 PEM 格式识别问题
            pk = cred_dict["private_key"].replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" not in pk:
                pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if "-----END PRIVATE KEY-----" not in pk:
                pk = pk + "\n-----END PRIVATE KEY-----\n"
            cred_dict["private_key"] = pk
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"云端连接配置失败: {e}")
            st.stop()
    return firestore.client()

# 启动数据库客户端
try:
    db = init_firestore()
except Exception as e:
    st.error(f"数据库客户端启动异常: {e}")
    st.stop()

APP_ID = "highschool-pro-prod"

def get_user_path(user_id): return f"artifacts/{APP_ID}/users/{user_id}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"

# ==========================================
# 2. 极致现代美学配置
# ==========================================
st.set_page_config(
    page_title="HighSchool Pro | 智能云端复习终端",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_hyper_css(is_landing=True):
    landing_bg = "https://img.qianmo.de5.net/PicGo/ai-art-1766791555667.png"
    app_bg_css = "background: linear-gradient(145deg, #fdfbfb 0%, #ebedee 100%);"
    landing_bg_css = f"""
        background-image: linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.1)), url("{landing_bg}");
        background-size: cover; background-position: center; background-attachment: fixed;
        image-rendering: -webkit-optimize-contrast;
    """
    selected_bg = landing_bg_css if is_landing else app_bg_css

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;700&display=swap');
    :root {{ --nano-gold: #D4AF37; --text-main: #0F172A; --glass-bg: rgba(255, 255, 255, 0.88); }}
    .stApp {{ {selected_bg} color: var(--text-main); }}
    section[data-testid="stSidebar"] {{ background-color: rgba(255, 255, 255, 0.4) !important; backdrop-filter: blur(25px); }}
    .auth-card {{ background: var(--glass-bg); padding: 40px; border-radius: 28px; border: 1px solid rgba(212, 175, 55, 0.3); max-width: 420px; margin: 0 auto; box-shadow: 0 40px 80px rgba(0, 0, 0, 0.1); }}
    .hyper-title {{ font-family: 'Space Grotesk', sans-serif; font-weight: 800; background: linear-gradient(135deg, #B8860B, #D4AF37, #FFD700); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }}
    div.stExpander {{ background: rgba(255, 255, 255, 0.92) !important; border: 1px solid rgba(212, 175, 55, 0.2) !important; border-radius: 18px !important; transition: 0.3s ease; }}
    .stButton>button {{ border-radius: 14px; font-weight: 700; background: linear-gradient(135deg, #D4AF37, #B8860B) !important; color: white !important; border: none !important; }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心功能：数据交互逻辑
# ==========================================
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def update_cloud_node(user_id, sid, title, m=None, d=None):
    try:
        doc_id = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
        doc_ref = db.document(f"{get_user_path(user_id)}/progress/{doc_id}")
        update_data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
        if m is not None: update_data["is_mastered"] = 1 if m else 0
        if d is not None: update_data["is_difficult"] = 1 if d else 0
        doc_ref.set(update_data, merge=True)
    except Exception:
        pass # 静默处理，防止复习时因瞬间网络波动中断体验

def sync_user_data(user_id):
    """从云端拉取进度的核心函数"""
    try:
        with st.spinner("🧠 正在从神经网格同步记忆..."):
            docs = db.collection(f"{get_user_path(user_id)}/progress").stream()
            mastered, difficult = set(), set()
            for doc in docs:
                data = doc.to_dict()
                key = f"{data['subject_id']}_{data['title']}"
                if data.get("is_mastered") == 1: mastered.add(key)
                if data.get("is_difficult") == 1: difficult.add(key)
            st.session_state.mastered_points = mastered
            st.session_state.difficult_points = difficult
            st.session_state.data_synced = True
    except Exception as e:
        st.error(f"同步失败: 网络不稳定。请尝试刷新网页。")

# ==========================================
# 4. 辅助函数
# ==========================================
SUBJECTS = {
    "chinese": "语文 | VERBAL", "math": "数学 | LOGIC", "english": "英语 | GLOBAL",
    "physics": "物理 | MATTER", "chemistry": "化学 | ATOM", "biology": "生物 | LIFE",
    "history": "历史 | TIME", "geography": "地理 | EARTH", "politics": "政治 | ETHICS"
}

def load_json(sid):
    p = os.path.join("data", f"{sid}.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f: return json.load(f)
    return []

def speak(text):
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(text)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

# ==========================================
# 5. 身份认证页面
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "data_synced" not in st.session_state: st.session_state.data_synced = False
if "mastered_points" not in st.session_state: st.session_state.mastered_points = set()
if "difficult_points" not in st.session_state: st.session_state.difficult_points = set()

if not st.session_state.logged_in:
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:12vh;"></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="auth-card"><h2 class="hyper-title">NEURAL ID</h2>', unsafe_allow_html=True)
        tabs = st.tabs(["🔑 登录", "✨ 注册"])
        with tabs[0]:
            l_u = st.text_input("账号 ID", key="l_u")
            l_p = st.text_input("密钥 Key", key="l_p", type="password")
            if st.button("同步记忆 (LOGIN)", use_container_width=True):
                try:
                    # 针对 RetryError 增加异常处理
                    user_doc = db.document(f"{get_public_path()}/users/{l_u}").get()
                    if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                        st.session_state.logged_in = True
                        st.session_state.user_contact = l_u
                        sync_user_data(l_u)
                        st.rerun()
                    else: 
                        st.error("验证失败：账号不存在或密钥错误")
                except (RetryError, ServiceUnavailable):
                    st.error("⚠️ 网络链路拥塞：无法连接到 Firebase。请检查您的网络环境或稍后再试。")
                except Exception as e:
                    st.error(f"登录异常: {e}")
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u")
            r_p = st.text_input("设置密钥", key="r_p", type="password")
            if st.button("激活并接入 (REGISTER)", use_container_width=True):
                try:
                    user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                    if user_ref.get().exists: st.error("该 ID 已存在")
                    else:
                        user_ref.set({"password": hash_pwd(r_p), "reg_date": str(date.today())})
                        db.document(f"{get_public_path()}/stats/global").set({"user_count": firestore.Increment(1)}, merge=True)
                        st.success("成功！请登录")
                except Exception as e:
                    st.error(f"注册服务暂时不可用: {e}")
        st.markdown('</div>', unsafe_allow_html=True)

elif not st.session_state.started:
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:15vh;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hyper-title" style="font-size:5.5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; font-weight:800;">欢迎回来, 探测员 {st.session_state.user_contact}</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    with c2: 
        if st.button("INITIALIZE LINK", use_container_width=True): st.session_state.started = True; st.rerun()

else:
    inject_hyper_css(is_landing=False)
    u = st.session_state.user_contact
    
    # 自动补偿同步
    if not st.session_state.data_synced:
        sync_user_data(u)
    
    with st.sidebar:
        st.markdown(f"<div style='text-align:center; font-weight:bold; color:#8B6B1B;'>👤 {u}</div>", unsafe_allow_html=True)
        mode = st.selectbox("系统指令", ["智脑看板", "神经元复习", "在线录入", "导出中心 📥"])
        st.divider()
        subject_id = st.selectbox("目标学科", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT"): st.session_state.clear(); st.rerun()

    if mode == "智脑看板":
        st.markdown("## 📊 同步状态")
        try:
            stats_doc = db.document(f"{get_public_path()}/stats/global").get()
            stats = stats_doc.to_dict() if stats_doc.exists else {"user_count": 0}
            c1, c2, c3 = st.columns(3)
            c1.metric("当前掌握", len(st.session_state.mastered_points))
            c2.metric("高考倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
            c3.metric("全网用户", stats.get("user_count", 0))
        except:
            st.warning("实时统计信息同步中...")
            
        for sid, name in SUBJECTS.items():
            d = load_json(sid)
            m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
            st.write(f"**{name}** ({m}/{len(d)})")
            st.progress(m/len(d) if d else 0)

    elif mode == "神经元复习":
        st.markdown(f"### {SUBJECTS[subject_id]}")
        data = load_json(subject_id)
        for item in data:
            m_key = f"{subject_id}_{item['title']}"
            is_m, is_d = m_key in st.session_state.mastered_points, m_key in st.session_state.difficult_points
            icon = "✅" if is_m else ("⭐" if is_d else "🧬")
            with st.expander(f"{icon} {item['title']}"):
                st.write(item['content'])
                if item.get('formula'): st.latex(item['formula'])
                c1, c2, c3 = st.columns(3)
                if c1.button("🔊 朗读", key=f"v_{m_key}"): speak(item['content'])
                if c2.button("⭐ 重点" if not is_d else "🌟 取消", key=f"f_{m_key}"):
                    update_cloud_node(u, subject_id, item['title'], d=not is_d)
                    if not is_d: st.session_state.difficult_points.add(m_key)
                    else: st.session_state.difficult_points.discard(m_key)
                    st.rerun()
                if c3.checkbox("掌握", key=f"m_{m_key}", value=is_m):
                    if not is_m: 
                        update_cloud_node(u, subject_id, item['title'], m=True)
                        st.session_state.mastered_points.add(m_key); st.rerun()
                elif is_m:
                    update_cloud_node(u, subject_id, item['title'], m=False)
                    st.session_state.mastered_points.discard(m_key); st.rerun()
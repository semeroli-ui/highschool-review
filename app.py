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
import streamlit.components.v1 as components

# ==========================================
# 1. 云端数据库初始化 (Firebase Firestore)
# ==========================================
def init_firestore():
    """从 Streamlit Secrets 安全初始化 Firebase，针对 PEM 格式错误进行了加固"""
    if not firebase_admin._apps:
        try:
            # 1. 获取 Secrets 字典
            if "firebase" not in st.secrets:
                st.error("未找到 [firebase] 配置块，请检查 Streamlit Secrets 设置。")
                st.stop()
            
            # 将 Secret 对象转换为真正的字典
            cred_dict = {}
            for key, value in st.secrets["firebase"].items():
                cred_dict[key] = value

            # 2. 核心修复：处理私钥格式 (PEM 证书)
            if "private_key" in cred_dict:
                # 兼容性处理：防止用户粘贴时丢失了 BEGIN/END 标签或换行符转义错误
                pk = cred_dict["private_key"]
                
                # 修复可能存在的双重转义
                pk = pk.replace("\\n", "\n")
                
                # 确保私钥具有正确的 PEM 头部和尾部
                if "-----BEGIN PRIVATE KEY-----" not in pk:
                    pk = "-----BEGIN PRIVATE KEY-----\n" + pk
                if "-----END PRIVATE KEY-----" not in pk:
                    pk = pk + "\n-----END PRIVATE KEY-----\n"
                
                cred_dict["private_key"] = pk

            # 3. 初始化
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"云端数据库配置错误: {e}")
            st.warning("💡 解决建议：")
            st.write("1. 确保在 Streamlit Secrets 中使用的是三个引号包裹私钥：`private_key = \"\"\"-----BEGIN...\"\"\"`")
            st.write("2. 确保粘贴的内容完整包含 `-----BEGIN PRIVATE KEY-----` 和 `-----END PRIVATE KEY-----`。")
            st.stop()
    return firestore.client()

db = init_firestore()
APP_ID = "highschool-pro-prod"  # 应用云端唯一标识

# 遵循规范的路径结构
def get_user_path(user_id): return f"artifacts/{APP_ID}/users/{user_id}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"

# ==========================================
# 2. 极致现代美学配置 (V6.0 旗舰视觉方案)
# ==========================================
st.set_page_config(
    page_title="HighSchool Pro | 智能云端复习终端",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_hyper_css(is_landing=True):
    """注入基于原图配色的极致 UI 样式"""
    landing_bg = "https://img.qianmo.de5.net/PicGo/ai-art-1766791555667.png"
    app_bg_css = "background: linear-gradient(145deg, #fdfbfb 0%, #ebedee 100%);"
    
    landing_bg_css = f"""
        background-image: linear-gradient(rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.1)), url("{landing_bg}");
        background-size: cover; 
        background-position: center; 
        background-attachment: fixed;
        image-rendering: -webkit-optimize-contrast;
    """
    selected_bg = landing_bg_css if is_landing else app_bg_css

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;700&family=Noto+Sans+SC:wght@300;400;700&display=swap');
    
    :root {{
        --nano-gold: #D4AF37;
        --nano-accent: #FF8C00;
        --text-main: #0F172A;
        --glass-bg: rgba(255, 255, 255, 0.88);
        --glass-border: rgba(212, 175, 55, 0.3);
    }}

    .stApp {{
        {selected_bg}
        color: var(--text-main);
    }}

    section[data-testid="stSidebar"] {{
        background-color: rgba(255, 255, 255, 0.4) !important;
        backdrop-filter: blur(25px);
        border-right: 1px solid rgba(212, 175, 55, 0.1);
    }}

    .auth-card {{
        background: var(--glass-bg);
        padding: 40px;
        border-radius: 28px;
        border: 1px solid var(--glass-border);
        max-width: 420px;
        margin: 0 auto;
        box-shadow: 0 40px 80px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(20px);
    }}

    .hyper-title {{
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 800;
        background: linear-gradient(135deg, #B8860B, #D4AF37, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        letter-spacing: -2px;
    }}

    div.stExpander {{
        background: rgba(255, 255, 255, 0.92) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 18px !important;
        box-shadow: 0 10px 30px rgba(212, 175, 55, 0.05) !important;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        margin-bottom: 1.2rem;
    }}
    div.stExpander:hover {{
        border: 1px solid #D4AF37 !important;
        transform: translateY(-4px);
        box-shadow: 0 15px 45px rgba(212, 175, 55, 0.15) !important;
    }}

    .chapter-badge {{
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 20px;
        background: rgba(212, 175, 55, 0.12);
        color: #8B6B1B;
        font-size: 0.8rem;
        font-weight: 700;
        margin-right: 12px;
        border: 1px solid rgba(212, 175, 55, 0.2);
    }}

    .stButton>button {{
        border-radius: 14px;
        font-weight: 700;
        background: linear-gradient(135deg, #D4AF37, #B8860B) !important;
        color: white !important;
        border: none !important;
        box-shadow: 0 8px 16px rgba(184, 134, 11, 0.2);
    }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心功能：数据交互逻辑 (云端 Firestore 版)
# ==========================================
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def update_cloud_node(user_id, sid, title, m=None, d=None):
    """异步同步掌握进度到云端"""
    doc_id = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
    doc_ref = db.document(f"{get_user_path(user_id)}/progress/{doc_id}")
    update_data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
    if m is not None: update_data["is_mastered"] = 1 if m else 0
    if d is not None: update_data["is_difficult"] = 1 if d else 0
    doc_ref.set(update_data, merge=True)

def sync_user_data(user_id):
    """从云端拉取用户所有进度并注入 Session"""
    docs = db.collection(f"{get_user_path(user_id)}/progress").stream()
    mastered, difficult = set(), set()
    for doc in docs:
        data = doc.to_dict()
        key = f"{data['subject_id']}_{data['title']}"
        if data.get("is_mastered") == 1: mastered.add(key)
        if data.get("is_difficult") == 1: difficult.add(key)
    st.session_state.mastered_points = mastered
    st.session_state.difficult_points = difficult

# ==========================================
# 4. 辅助工具函数
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

def save_json(sid, data):
    if not os.path.exists("data"): os.makedirs("data")
    p = os.path.join("data", f"{sid}.json")
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def speak(text):
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(text)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

# ==========================================
# 5. 页面渲染逻辑
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
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
                user_doc = db.document(f"{get_public_path()}/users/{l_u}").get()
                if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                    st.session_state.logged_in = True
                    st.session_state.user_contact = l_u
                    sync_user_data(l_u)
                    st.rerun()
                else: st.error("验证失败")
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u")
            r_p = st.text_input("设置密钥", key="r_p", type="password")
            if st.button("激活并接入 (REGISTER)", use_container_width=True):
                user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                if user_ref.get().exists: st.error("账号已存在")
                elif len(r_p) < 5: st.error("过短")
                else:
                    user_ref.set({"password": hash_pwd(r_p), "reg_date": str(date.today())})
                    db.document(f"{get_public_path()}/stats/global").set({"user_count": firestore.Increment(1)}, merge=True)
                    st.success("成功！请登录")
        st.markdown('</div>', unsafe_allow_html=True)

elif not st.session_state.started:
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:15vh;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hyper-title" style="font-size:5.5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; font-weight:800;">欢迎, 探测员 {st.session_state.user_contact}</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    with c2: 
        if st.button("INITIALIZE LINK", use_container_width=True): st.session_state.started = True; st.rerun()

else:
    inject_hyper_css(is_landing=False)
    u = st.session_state.user_contact
    
    with st.sidebar:
        st.markdown(f"<div style='text-align:center; font-weight:bold; color:#8B6B1B;'>👤 {u}</div>", unsafe_allow_html=True)
        mode = st.selectbox("系统指令", ["智脑看板", "神经元复习", "在线录入", "批量导入 📤", "导出中心 📥"])
        st.divider()
        subject_id = st.selectbox("目标学科", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT"): st.session_state.clear(); st.rerun()

    if mode == "智脑看板":
        st.markdown("## 📊 同步状态")
        stats_doc = db.document(f"{get_public_path()}/stats/global").get()
        stats = stats_doc.to_dict() if stats_doc.exists else {"user_count": 0}
        c1, c2, c3 = st.columns(3)
        c1.metric("当前掌握", len(st.session_state.mastered_points))
        c2.metric("高考倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
        c3.metric("全网用户", stats.get("user_count", 0))
        for sid, name in SUBJECTS.items():
            d = load_json(sid)
            m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
            st.write(f"**{name}** ({m}/{len(d)})")
            st.progress(m/len(d) if d else 0)

    elif mode == "神经元复习":
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
                        st.session_state.mastered_points.add(m_key)
                        st.rerun()
                elif is_m:
                    update_cloud_node(u, subject_id, item['title'], m=False)
                    st.session_state.mastered_points.discard(m_key)
                    st.rerun()
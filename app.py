import streamlit as st
import json
import os
import random
import hashlib
import pandas as pd
import io
import time
from datetime import date, datetime
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import RetryError, ServiceUnavailable, DeadlineExceeded
import streamlit.components.v1 as components

# ==========================================
# 1. 云端数据库初始化 (最高级别韧性配置)
# ==========================================
@st.cache_resource
def init_firestore():
    """使用 cache_resource 确保数据库连接只初始化一次，降低握手频率"""
    if not firebase_admin._apps:
        try:
            if "firebase" not in st.secrets:
                st.error("Secrets 中未找到 [firebase] 配置块")
                st.stop()
            
            cred_dict = dict(st.secrets["firebase"])
            # 解决多行私钥解析问题
            pk = cred_dict["private_key"].replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" not in pk:
                pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if "-----END PRIVATE KEY-----" not in pk:
                pk = pk + "\n-----END PRIVATE KEY-----\n"
            cred_dict["private_key"] = pk
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"初始化驱动失败: {e}")
            st.stop()
    return firestore.client()

db = init_firestore()
APP_ID = "highschool-pro-prod"

# --- 核心：强韧数据库交互函数 (解决超时与重试) ---
def safe_db_op(func, *args, **kwargs):
    """通用重试包装器，采用指数退避算法"""
    max_retries = 4
    for i in range(max_retries):
        try:
            # 统一设置 60 秒超长超时，应对跨国延迟
            kwargs['timeout'] = 60
            return func(*args, **kwargs)
        except (RetryError, ServiceUnavailable, DeadlineExceeded) as e:
            if i < max_retries - 1:
                wait_time = (2 ** i) + random.random()
                time.sleep(wait_time)
                continue
            else:
                raise e

def safe_get(doc_ref): return safe_db_op(doc_ref.get)
def safe_set(doc_ref, data, merge=True): return safe_db_op(doc_ref.set, data, merge=merge)

# ==========================================
# 2. 极致现代美学配置 (全功能视觉方案)
# ==========================================
st.set_page_config(page_title="HighSchool Pro", page_icon="🧬", layout="wide")

def inject_hyper_css(is_landing=True):
    landing_bg = "https://img.qianmo.de5.net/PicGo/ai-art-1766791555667.png"
    app_bg = "background: linear-gradient(145deg, #fdfbfb 0%, #ebedee 100%);"
    landing_bg_css = f'background-image: url("{landing_bg}"); background-size: cover; background-attachment: fixed;'
    selected_bg = landing_bg_css if is_landing else app_bg

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Noto+Sans+SC:wght@400;700&display=swap');
    :root {{ --nano-gold: #D4AF37; --text-main: #0F172A; --glass: rgba(255, 255, 255, 0.9); }}
    .stApp {{ {selected_bg} color: var(--text-main); font-family: 'Noto Sans SC', sans-serif; }}
    .auth-card {{ background: var(--glass); padding: 40px; border-radius: 28px; border: 1px solid rgba(212, 175, 55, 0.3); max-width: 450px; margin: 0 auto; box-shadow: 0 30px 60px rgba(0,0,0,0.1); backdrop-filter: blur(15px); }}
    .hyper-title {{ font-family: 'Space Grotesk', sans-serif; font-weight: 800; background: linear-gradient(135deg, #B8860B, #FFD700); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }}
    div.stExpander {{ background: rgba(255, 255, 255, 0.95) !important; border: 1px solid rgba(212, 175, 55, 0.2) !important; border-radius: 18px !important; margin-bottom: 15px; transition: 0.3s; }}
    div.stExpander:hover {{ transform: translateY(-3px); border-color: var(--nano-gold) !important; }}
    .stButton>button {{ border-radius: 12px; background: linear-gradient(135deg, #D4AF37, #B8860B) !important; color: white !important; font-weight: 700; border: none !important; }}
    .chapter-badge {{ display: inline-flex; padding: 2px 10px; border-radius: 12px; background: rgba(212, 175, 55, 0.1); color: #8B6B1B; font-size: 0.75rem; font-weight: 700; border: 1px solid rgba(212, 175, 55, 0.2); }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 数据处理与辅助逻辑
# ==========================================
SUBJECTS = {"chinese":"语文", "math":"数学", "english":"英语", "physics":"物理", "chemistry":"化学", "biology":"生物", "history":"历史", "geography":"地理", "politics":"政治"}
def get_user_path(uid): return f"artifacts/{APP_ID}/users/{uid}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def load_json(sid):
    p = os.path.join("data", f"{sid}.json")
    return json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else []

def save_json(sid, data):
    if not os.path.exists("data"): os.makedirs("data")
    with open(os.path.join("data", f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def speak(text):
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(text)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

def update_node_cloud(uid, sid, title, m=None, d=None):
    try:
        did = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
        ref = db.document(f"{get_user_path(uid)}/progress/{did}")
        data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
        if m is not None: data["is_mastered"] = 1 if m else 0
        if d is not None: data["is_difficult"] = 1 if d else 0
        safe_set(ref, data)
    except: pass

def sync_data(uid):
    try:
        with st.spinner("🧬 正在同步神经网格..."):
            docs = db.collection(f"{get_user_path(uid)}/progress").stream(timeout=60)
            mastered, difficult = set(), set()
            for d in docs:
                v = d.to_dict()
                key = f"{v['subject_id']}_{v['title']}"
                if v.get("is_mastered") == 1: mastered.add(key)
                if v.get("is_difficult") == 1: difficult.add(key)
            st.session_state.mastered_points = mastered
            st.session_state.difficult_points = difficult
            st.session_state.data_synced = True
    except:
        st.warning("⚠️ 同步不完全，请尝试手动刷新。")

# ==========================================
# 4. 核心页面逻辑
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "data_synced" not in st.session_state: st.session_state.data_synced = False
if "test_queue" not in st.session_state: st.session_state.test_queue = []

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
                    user_ref = db.document(f"{get_public_path()}/users/{l_u}")
                    user_doc = safe_get(user_ref)
                    # 管理员初始化逻辑
                    if l_u == "admin" and not user_doc.exists and l_p == "admin":
                        safe_set(user_ref, {"password": hash_pwd("admin"), "reg_date": str(date.today())})
                        user_doc = safe_get(user_ref)
                    
                    if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                        st.session_state.logged_in = True
                        st.session_state.user_contact = l_u
                        sync_data(l_u)
                        st.rerun()
                    else: st.error("验证未通过：账号不存在或密钥错误")
                except Exception: st.error("🛰️ 网络链路中断。请开启加速器或检查 Firebase 位置。")
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u")
            r_p = st.text_input("设置密钥", key="r_p", type="password")
            if st.button("激活并注册", use_container_width=True):
                try:
                    user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                    if safe_get(user_ref).exists: st.error("ID 已占用")
                    else:
                        safe_set(user_ref, {"password": hash_pwd(r_p), "reg_date": str(date.today())})
                        db.document(f"{get_public_path()}/stats/global").set({"user_count": firestore.Increment(1)}, merge=True)
                        st.success("成功！请登录")
                except: st.error("云端响应超时")
        st.markdown('</div>', unsafe_allow_html=True)

elif not st.session_state.started:
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:15vh;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hyper-title" style="font-size:5.5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; font-weight:800; font-size:1.2rem;">探测员 {st.session_state.user_contact}，连接已就绪</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    with c2: 
        if st.button("INITIALIZE LINK", use_container_width=True): st.session_state.started = True; st.rerun()

else:
    inject_hyper_css(is_landing=False)
    u = st.session_state.user_contact
    if not st.session_state.data_synced: sync_data(u)
    
    with st.sidebar:
        st.markdown(f"<div style='padding:10px; border-radius:15px; background:rgba(212,175,55,0.1); text-align:center; color:#8B6B1B; font-weight:bold;'>👤 {u}</div>", unsafe_allow_html=True)
        mode = st.selectbox("功能指令", ["智脑看板", "神经元复习", "闪念卡片", "全科闯关", "在线录入", "数据管理", "安全设置"])
        st.divider()
        subject_id = st.selectbox("当前学科", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT"): st.session_state.clear(); st.rerun()

    # --- 功能分发逻辑 (完美保留旧版功能) ---
    if mode == "智脑看板":
        st.markdown("## 📊 学习进度状态")
        stats_doc = db.document(f"{get_public_path()}/stats/global").get()
        user_count = stats_doc.to_dict().get("user_count", 0) if stats_doc.exists else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("已掌握", len(st.session_state.mastered_points))
        c2.metric("高考倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
        c3.metric("云端总用户", user_count)
        for sid, name in SUBJECTS.items():
            d = load_json(sid); m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
            st.write(f"**{name}** ({m}/{len(d)})"); st.progress(m/len(d) if d else 0)

    elif mode == "神经元复习":
        data = load_json(subject_id)
        for item in data:
            m_key = f"{subject_id}_{item['title']}"
            is_m, is_d = m_key in st.session_state.mastered_points, m_key in st.session_state.difficult_points
            with st.expander(f"{'✅' if is_m else ('⭐' if is_d else '🧬')} {item['title']}"):
                st.write(item['content'])
                if item.get('formula'): st.latex(item['formula'])
                c1, c2, c3 = st.columns(3)
                if c1.button("🔊 朗读", key=f"v_{m_key}"): speak(item['content'])
                if c2.button("⭐ 难点" if not is_d else "🌟 取消", key=f"f_{m_key}"):
                    update_node_cloud(u, subject_id, item['title'], d=not is_d)
                    st.session_state.difficult_points.add(m_key) if not is_d else st.session_state.difficult_points.discard(m_key)
                    st.rerun()
                if c3.checkbox("已掌握", key=f"m_{m_key}", value=is_m):
                    if not is_m: update_node_cloud(u, subject_id, item['title'], m=True); st.session_state.mastered_points.add(m_key); st.rerun()
                elif is_m: update_node_cloud(u, subject_id, item['title'], m=False); st.session_state.mastered_points.discard(m_key); st.rerun()

    elif mode == "全科闯关":
        st.markdown("### 🏁 随机 10 题神经元挑战")
        if not st.session_state.test_queue:
            if st.button("🚀 开始挑战"):
                all_data = []
                for s in SUBJECTS.keys():
                    for i in load_json(s): i['sid'] = s; all_data.append(i)
                st.session_state.test_queue = random.sample(all_data, min(10, len(all_data)))
                st.session_state.test_idx = 0; st.rerun()
        elif st.session_state.test_idx < len(st.session_state.test_queue):
            idx = st.session_state.test_idx; item = st.session_state.test_queue[idx]
            st.write(f"**第 {idx+1} 题 / 共 {len(st.session_state.test_queue)} 题**")
            with st.container(border=True):
                st.title(item['title'])
                if st.checkbox("🔍 揭晓答案"): 
                    st.info(item['content'])
                    if item.get('formula'): st.latex(item['formula'])
            if st.button("NEXT"): st.session_state.test_idx += 1; st.rerun()
        else:
            st.success("闯关完成！"); st.balloons()
            if st.button("重新开始"): st.session_state.test_queue = []; st.rerun()

    elif mode == "在线录入":
        t = st.text_input("标题"); c = st.text_area("内容"); f = st.text_input("公式 (LaTeX)")
        if st.button("💾 保存考点"):
            if t and c:
                curr = load_json(subject_id); curr.append({"title": t, "content": c, "formula": f})
                save_json(subject_id, curr); st.success("同步至虚拟磁盘成功")

    elif mode == "安全设置":
        st.title("⚙️ 安全中心")
        with st.form("pwd"):
            np = st.text_input("新密钥 Key", type="password")
            if st.form_submit_button("UPDATE"):
                if len(np) >= 5:
                    db.document(f"{get_public_path()}/users/{u}").update({"password": hash_pwd(np)})
                    st.success("云端密钥已同步")
                else: st.error("过短")
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
from google.api_core.exceptions import RetryError, ServiceUnavailable, DeadlineExceeded, PermissionDenied
import streamlit.components.v1 as components

# ==========================================
# 1. 云端数据库初始化 (高韧性加速配置)
# ==========================================
@st.cache_resource
def init_firestore():
    if not firebase_admin._apps:
        try:
            if "firebase" not in st.secrets:
                st.error("未发现 [firebase] 密钥配置，请检查 Streamlit Secrets。")
                st.stop()
            cred_dict = dict(st.secrets["firebase"])
            pk = cred_dict["private_key"].replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" not in pk: pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if "-----END PRIVATE KEY-----" not in pk: pk = pk + "\n-----END PRIVATE KEY-----\n"
            cred_dict["private_key"] = pk
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"驱动加载失败: {e}")
            st.stop()
    return firestore.client()

db = init_firestore()
APP_ID = "highschool-pro-prod"

def safe_db_op(func, *args, **kwargs):
    max_retries = 3
    kwargs['timeout'] = 60 # 60秒超长超时，应对跨境网络
    for i in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (RetryError, ServiceUnavailable, DeadlineExceeded) as e:
            if i < max_retries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise e

def safe_get(doc_ref): return safe_db_op(doc_ref.get)
def safe_set(doc_ref, data, merge=True): return safe_db_op(doc_ref.set, data, merge=merge)

# ==========================================
# 2. 视觉美学注入
# ==========================================
st.set_page_config(page_title="HighSchool Pro | 云端终极版", page_icon="🧬", layout="wide")

def inject_ui():
    bg_url = "https://img.qianmo.de5.net/PicGo/ai-art-1766791555667.png"
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Noto+Sans+SC:wght@400;700&display=swap');
    :root {{ --gold: #D4AF37; --dark: #1E293B; }}
    .stApp {{ background-image: url("{bg_url}"); background-size: cover; background-attachment: fixed; font-family: 'Noto Sans SC', sans-serif; }}
    section[data-testid="stSidebar"] {{ background: rgba(255,255,255,0.35) !important; backdrop-filter: blur(20px); }}
    .auth-card {{ background: rgba(255, 255, 255, 0.92); padding: 40px; border-radius: 28px; border: 1px solid rgba(212, 175, 55, 0.3); max-width: 450px; margin: 0 auto; box-shadow: 0 30px 60px rgba(0,0,0,0.15); }}
    .hyper-title {{ font-family: 'Space Grotesk', sans-serif; font-weight: 800; background: linear-gradient(135deg, #B8860B, #FFD700); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; }}
    div.stExpander {{ background: rgba(255, 255, 255, 0.95) !important; border-radius: 15px !important; border: 1px solid rgba(212,175,55,0.2) !important; margin-bottom: 12px; transition: 0.3s; }}
    div.stExpander:hover {{ transform: translateY(-3px); border-color: var(--gold) !important; }}
    .stButton>button {{ border-radius: 12px; background: linear-gradient(135deg, #D4AF37, #B8860B) !important; color: white !important; font-weight: 700; border: none !important; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; background: rgba(212,175,55,0.1); color: #8B6B1B; font-size: 0.75rem; font-weight: bold; margin-right: 5px; }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心业务逻辑
# ==========================================
SUBJECTS = {"chinese":"语文", "math":"数学", "english":"英语", "physics":"物理", "chemistry":"化学", "biology":"生物", "history":"历史", "geography":"地理", "politics":"政治"}
def get_user_path(uid): return f"artifacts/{APP_ID}/users/{uid}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"
def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()

def load_json(sid):
    p = os.path.join("data", f"{sid}.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f: return json.load(f)
    return []

def save_json(sid, data):
    if not os.path.exists("data"): os.makedirs("data")
    with open(os.path.join("data", f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def sync_data(uid):
    try:
        with st.spinner("🧠 正在同步云端记忆网格..."):
            docs = db.collection(f"{get_user_path(uid)}/progress").stream(timeout=60)
            mastered, difficult = set(), set()
            for d in docs:
                v = d.to_dict()
                key = f"{v['subject_id']}_{v['title']}"
                if v.get("is_mastered") == 1: mastered.add(key)
                if v.get("is_difficult") == 1: difficult.add(key)
            st.session_state.mastered_points, st.session_state.difficult_points = mastered, difficult
            st.session_state.data_synced = True
    except: st.warning("⚠️ 网络拥塞，进度加载不完全，建议刷新页面。")

def update_node(uid, sid, title, m=None, d=None):
    try:
        did = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
        ref = db.document(f"{get_user_path(uid)}/progress/{did}")
        data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
        if m is not None: data["is_mastered"] = 1 if m else 0
        if d is not None: data["is_difficult"] = 1 if d else 0
        safe_set(ref, data)
    except: pass

def speak(t):
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(t)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

# ==========================================
# 4. 身份认证模块
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "data_synced" not in st.session_state: st.session_state.data_synced = False
if "test_queue" not in st.session_state: st.session_state.test_queue = []

def auth_page():
    inject_ui()
    st.markdown('<div style="height:10vh;"></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="auth-card"><h1 class="hyper-title">NEURAL ID</h1>', unsafe_allow_html=True)
        tabs = st.tabs(["🔒 登录系统", "✨ 账号激活"])
        with tabs[0]:
            l_u = st.text_input("探测员 ID", key="l_u")
            l_p = st.text_input("密钥 Key", key="l_p", type="password")
            if st.button("建立连接 (LOGIN)", use_container_width=True):
                try:
                    user_ref = db.document(f"{get_public_path()}/users/{l_u}")
                    user_doc = safe_get(user_ref)
                    if l_u == "admin" and not user_doc.exists and l_p == "admin":
                        safe_set(user_ref, {"password": hash_pwd("admin"), "reg_date": str(date.today())})
                        user_doc = safe_get(user_ref)
                    if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                        st.session_state.logged_in, st.session_state.user_contact = True, l_u
                        sync_data(l_u); st.rerun()
                    else: st.error("账号或密钥错误")
                except: st.error("🛰️ 连接超时，请检查加速器状态。")
        with tabs[1]:
            r_u = st.text_input("新 ID", key="r_u"); r_p = st.text_input("设置密钥", key="r_p", type="password")
            r_v = st.text_input("验证码", placeholder="点击右侧获取")
            if st.button("获取验证码"):
                st.session_state.code = str(random.randint(1000,9999))
                st.toast(f"【验证码】您的代码是：{st.session_state.code}", icon="📩")
            if st.button("激活并接入", use_container_width=True):
                if r_v != st.session_state.get('code'): st.error("验证码错误")
                elif len(r_p) < 5: st.error("密钥太短")
                else:
                    try:
                        user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                        if safe_get(user_ref).exists: st.error("ID 已占用")
                        else:
                            safe_set(user_ref, {"password": hash_pwd(r_p), "reg_date": str(date.today())})
                            db.document(f"{get_public_path()}/stats/global").set({"user_count": firestore.Increment(1)}, merge=True)
                            st.success("✅ 激活成功！请登录。")
                    except: st.error("云端响应超时。")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 5. 主程序控制流
# ==========================================
if not st.session_state.logged_in:
    auth_page()
elif not st.session_state.started:
    inject_ui()
    st.markdown('<div style="height:15vh;"></div><h1 class="hyper-title" style="font-size:5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; font-weight:800;">欢迎, 探测员 {st.session_state.user_contact}</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    if c2.button("INITIALIZE LINK", use_container_width=True): st.session_state.started = True; st.rerun()
else:
    inject_ui(); u = st.session_state.user_contact
    if not st.session_state.data_synced: sync_data(u)
    with st.sidebar:
        st.markdown(f"<div style='padding:12px; border-radius:15px; background:rgba(212,175,55,0.1); text-align:center; color:#8B6B1B; font-weight:bold;'>👤 {u}</div>", unsafe_allow_html=True)
        mode = st.selectbox("系统指令", ["智脑看板", "神经元复习", "闪念卡片模式", "全科挑战", "在线录入预览", "导出资料包", "安全设置"])
        st.divider(); subject_id = st.selectbox("目标学科对照", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT"): st.session_state.clear(); st.rerun()

    if mode == "智脑看板":
        st.markdown("## 📊 同步状态监控")
        try:
            stats = db.document(f"{get_public_path()}/stats/global").get().to_dict() or {"user_count": 0}
            c1, c2, c3 = st.columns(3)
            c1.metric("已掌握", len(st.session_state.mastered_points))
            c2.metric("高考倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
            c3.metric("总探测员", stats.get("user_count", 0))
            st.divider()
            for sid, name in SUBJECTS.items():
                d = load_json(sid); m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
                st.write(f"**{name}** ({m}/{len(d)})"); st.progress(m/len(d) if d else 0)
        except: st.error("数据加载延迟...")

    elif mode == "神经元复习":
        data = load_json(subject_id)
        chaps = sorted(list(set(i.get("chapter", "未分类") for i in data)))
        sel_ch = st.selectbox("📚 章节过滤", ["全部"] + chaps)
        srch = st.text_input("🔍 搜索关键词")
        for item in data:
            if (sel_ch != "全部" and item.get("chapter", "未分类") != sel_ch) or (srch and srch.lower() not in item['title'].lower()): continue
            m_key = f"{subject_id}_{item['title']}"
            is_m, is_d = m_key in st.session_state.mastered_points, m_key in st.session_state.difficult_points
            with st.expander(f"{'✅' if is_m else ('⭐' if is_d else '🧬')} {item['title']}"):
                st.markdown(f"<span class='badge'>📚 {item.get('chapter','未分类')}</span>", unsafe_allow_html=True)
                st.write(item['content'])
                if item.get('formula'): st.latex(item['formula'])
                if item.get('image'): st.image(item['image'], use_container_width=True)
                ca, cb, cc = st.columns(3)
                if ca.button("🔊 朗读", key=f"v_{m_key}"): speak(item['content'])
                if cb.button("⭐ 重点" if not is_d else "🌟 取消", key=f"f_{m_key}"):
                    update_node(u, subject_id, item['title'], d=not is_d)
                    st.session_state.difficult_points.add(m_key) if not is_d else st.session_state.difficult_points.discard(m_key); st.rerun()
                if cc.checkbox("掌握", key=f"m_{m_key}", value=is_m):
                    if not is_m: update_node(u, subject_id, item['title'], m=True); st.session_state.mastered_points.add(m_key); st.rerun()
                elif is_m: update_node(u, subject_id, item['title'], m=False); st.session_state.mastered_points.discard(m_key); st.rerun()

    elif mode == "闪念卡片模式":
        data = load_json(subject_id)
        if data:
            if "fl_idx" not in st.session_state: st.session_state.fl_idx = 0
            it = data[st.session_state.fl_idx % len(data)]
            st.markdown(f"### ⚡ 闪念速记: {SUBJECTS[subject_id]}")
            with st.container(border=True):
                st.caption(f"考点 {st.session_state.fl_idx+1}/{len(data)}")
                st.title(it['title'])
                if st.button("🔍 点击揭晓核心解析"): st.info(it['content'])
            bc1, bc2 = st.columns(2)
            if bc1.button("PREV"): st.session_state.fl_idx -= 1; st.rerun()
            if bc2.button("NEXT"): st.session_state.fl_idx += 1; st.rerun()

    elif mode == "全科挑战":
        st.markdown("### 🏁 跨学科随机挑战 (10题)")
        if not st.session_state.test_queue:
            if st.button("🚀 开始闯关"):
                all_pts = []
                for s in SUBJECTS.keys():
                    for i in load_json(s): i['sid'] = s; all_pts.append(i)
                st.session_state.test_queue = random.sample(all_pts, min(10, len(all_pts))); st.session_state.t_idx = 0; st.rerun()
        elif st.session_state.t_idx < len(st.session_state.test_queue):
            it = st.session_state.test_queue[st.session_state.t_idx]
            st.progress((st.session_state.t_idx+1)/10)
            with st.container(border=True):
                st.caption(f"学科：{SUBJECTS[it['sid']]} | 考点 {st.session_state.t_idx+1}")
                st.title(it['title'])
                if st.checkbox("查看解析"): st.write(it['content'])
            if st.button("NEXT"): st.session_state.t_idx += 1; st.rerun()
        else:
            st.success("闯关成功！"); st.balloons()
            if st.button("重新开始"): st.session_state.test_queue = []; st.rerun()

    elif mode == "在线录入预览":
        st.markdown("## ✏️ 实时同步录入")
        ce1, ce2 = st.columns(2)
        with ce1:
            t_in = st.text_input("考点标题"); c_in = st.text_area("详细解析内容"); f_in = st.text_input("LaTeX公式")
            if st.button("✅ 物理同步至磁盘"):
                if t_in and c_in:
                    curr = load_json(subject_id); curr.append({"title":t_in, "content":c_in, "formula":f_in})
                    save_json(subject_id, curr); st.success("同步成功")
        with ce2:
            if t_in: 
                with st.container(border=True): st.markdown(f"### {t_in}\n{c_in}"); st.latex(f_in)

    elif mode == "导出资料包":
        st.markdown("## 📥 定制资料包导出")
        sel = st.multiselect("选择学科", options=list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("🚀 生成 Markdown"):
            res = f"# 🎓 复习笔记 - {date.today()}\n\n"
            for s in sel:
                res += f"## 【{SUBJECTS[s]}】\n"
                for i in load_json(s): res += f"### {i['title']}\n{i['content']}\n\n"
            st.download_button("💾 点击下载", res, file_name="review.md")

    elif mode == "安全设置":
        st.title("⚙️ 密钥管理")
        with st.form("pwd"):
            np = st.text_input("新神经密钥", type="password")
            if st.form_submit_button("UPDATE"):
                if len(np) >= 5:
                    db.document(f"{get_public_path()}/users/{u}").update({"password": hash_pwd(np)})
                    st.success("密钥同步成功，下次登录生效。")
                else: st.error("过短")
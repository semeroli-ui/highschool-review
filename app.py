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
# 1. 云端数据库初始化 (高韧性配置)
# ==========================================
@st.cache_resource
def init_firestore():
    if not firebase_admin._apps:
        try:
            if "firebase" not in st.secrets:
                st.error("Secrets 中缺失 [firebase] 配置")
                st.stop()
            
            cred_dict = dict(st.secrets["firebase"])
            pk = cred_dict["private_key"].replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" not in pk:
                pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if "-----END PRIVATE KEY-----" not in pk:
                pk = pk + "\n-----END PRIVATE KEY-----\n"
            cred_dict["private_key"] = pk
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"初始化失败: {e}")
            st.stop()
    return firestore.client()

db = init_firestore()
APP_ID = "highschool-pro-prod"

# --- 核心修复：高韧性数据库读取函数 ---
def safe_db_get(doc_ref, max_retries=3):
    """带重试机制的数据库读取，应对 RetryError"""
    for i in range(max_retries):
        try:
            # 显式增加 timeout 参数（单位：秒）
            return doc_ref.get(timeout=30)
        except (RetryError, ServiceUnavailable, DeadlineExceeded) as e:
            if i < max_retries - 1:
                time.sleep(1.5) # 等待网络抖动恢复
                continue
            else:
                raise e # 最终还是失败则抛出

# ==========================================
# 2. 路径与辅助函数
# ==========================================
def get_user_path(user_id): return f"artifacts/{APP_ID}/users/{user_id}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def update_cloud_node(user_id, sid, title, m=None, d=None):
    try:
        doc_id = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
        doc_ref = db.document(f"{get_user_path(user_id)}/progress/{doc_id}")
        update_data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
        if m is not None: update_data["is_mastered"] = 1 if m else 0
        if d is not None: update_data["is_difficult"] = 1 if d else 0
        doc_ref.set(update_data, merge=True, timeout=20)
    except: pass

def sync_user_data(user_id):
    try:
        with st.spinner("🧠 正在从云端网格同步记忆..."):
            # stream 同样增加超时控制
            docs = db.collection(f"{get_user_path(user_id)}/progress").stream(timeout=30)
            mastered, difficult = set(), set()
            for doc in docs:
                data = doc.to_dict()
                key = f"{data['subject_id']}_{data['title']}"
                if data.get("is_mastered") == 1: mastered.add(key)
                if data.get("is_difficult") == 1: difficult.add(key)
            st.session_state.mastered_points = mastered
            st.session_state.difficult_points = difficult
            st.session_state.data_synced = True
    except:
        st.warning("⚠️ 部分数据同步延迟，请尝试重新刷新页面。")

# --- 视觉与数据加载略过 (与 V6.4 一致) ---
st.set_page_config(page_title="HighSchool Pro", page_icon="🧬", layout="wide")
def inject_hyper_css(is_landing=True):
    # (保留之前的 CSS 代码...)
    st.markdown("<style>/* CSS 内容 */</style>", unsafe_allow_html=True)

SUBJECTS = {"chinese":"语文", "math":"数学", "english":"英语", "physics":"物理", "chemistry":"化学", "biology":"生物", "history":"历史", "geography":"地理", "politics":"政治"}
def load_json(sid):
    p = os.path.join("data", f"{sid}.json")
    return json.load(open(p, "r", encoding="utf-8")) if os.path.exists(p) else []

# ==========================================
# 3. 身份认证页面 (修复 RetryError)
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "data_synced" not in st.session_state: st.session_state.data_synced = False

def auth_page():
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
                    # 使用 safe_db_get 代替直接 get()
                    user_doc = safe_db_get(user_ref)
                    
                    if l_u == "admin" and not user_doc.exists and l_p == "admin":
                        user_ref.set({"password": hash_pwd("admin"), "reg_date": str(date.today())})
                        user_doc = safe_db_get(user_ref)

                    if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                        st.session_state.logged_in = True
                        st.session_state.user_contact = l_u
                        sync_user_data(l_u)
                        st.rerun()
                    else: st.error("验证失败")
                except Exception as e:
                    st.error("🛰️ 云端链路超时。请开启加速器或尝试刷新网页。")
        
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u")
            r_p = st.text_input("设置密钥", key="r_p", type="password")
            if st.button("激活注册", use_container_width=True):
                try:
                    user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                    # 使用 safe_db_get 进行冲突检查
                    if safe_db_get(user_ref).exists: 
                        st.error("账号已被占用")
                    else:
                        user_ref.set({"password": hash_pwd(r_p), "reg_date": str(date.today())}, timeout=20)
                        st.success("注册成功！请登录")
                except Exception:
                    st.error("注册请求超时，请稍后再试。")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 4. 主程序 (保持 V6.4 功能逻辑)
# ==========================================
if not st.session_state.logged_in:
    auth_page()
else:
    # (此处承接 V6.4 的所有功能模块：智脑看板、复习、挑战等...)
    # 记得在所有 db 操作中参考上述 safe_db_get 的逻辑
    st.sidebar.write(f"已登录: {st.session_state.user_contact}")
    if st.sidebar.button("LOGOUT"): st.session_state.clear(); st.rerun()
    st.info("进入系统成功，请选择侧边栏功能。")
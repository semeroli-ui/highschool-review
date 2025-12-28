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
# 1. 云端数据库初始化 (GCP 内部链路与韧性优化)
# ==========================================
@st.cache_resource
def init_firestore():
    """初始化 Firebase 客户端，适配 GCP 本地 Secrets 与云端环境"""
    if not firebase_admin._apps:
        try:
            # 兼容 Streamlit Cloud Secrets 和本地 .streamlit/secrets.toml
            if "firebase" in st.secrets:
                cred_dict = dict(st.secrets["firebase"])
            else:
                st.error("❌ 配置文件缺失：请确保项目根目录下存在 .streamlit/secrets.toml 且配置了 [firebase] 块。")
                st.stop()
            
            # 私钥换行符与 PEM 头部加固处理
            pk = cred_dict["private_key"].replace("\\n", "\n")
            if "-----BEGIN PRIVATE KEY-----" not in pk:
                pk = "-----BEGIN PRIVATE KEY-----\n" + pk
            if "-----END PRIVATE KEY-----" not in pk:
                pk = pk + "\n-----END PRIVATE KEY-----\n"
            cred_dict["private_key"] = pk
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"❌ 数据库驱动加载失败: {e}")
            st.stop()
    return firestore.client()

# 实例化数据库客户端
db = init_firestore()
APP_ID = "highschool-pro-prod"

# --- 核心：高级重试包装装饰器 (应对网络抖动) ---
def robust_op(func):
    """带指数退避算法的数据库重试逻辑"""
    def wrapper(*args, **kwargs):
        max_retries = 4
        # GCP 内部到 Firebase 延迟较低，初始超时设为 25s
        kwargs['timeout'] = 25 
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except (RetryError, ServiceUnavailable, DeadlineExceeded) as e:
                if i < max_retries - 1:
                    # 指数退避：1s, 2s, 4s...
                    time.sleep((2 ** i) + random.random())
                    continue
                raise e
    return wrapper

@robust_op
def safe_get(doc_ref, **kwargs): return doc_ref.get(**kwargs)

@robust_op
def safe_set(doc_ref, data, **kwargs): return doc_ref.set(data, **kwargs)

# ==========================================
# 2. 极致现代美学配置 (V6.9 生产级视觉方案)
# ==========================================
st.set_page_config(
    page_title="HighSchool Pro | GCP 强韧加速版",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_ui_styles():
    """注入基于原图配色的极致磨砂玻璃 UI"""
    bg_url = "https://img.qianmo.de5.net/PicGo/ai-art-1766791555667.png"
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700&family=Noto+Sans+SC:wght@400;700&display=swap');
    :root {{ --gold: #D4AF37; --accent: #FF8C00; --bg-glass: rgba(255, 255, 255, 0.94); }}
    
    .stApp {{ 
        background-image: linear-gradient(rgba(255,255,255,0.05), rgba(255,255,255,0.05)), url("{bg_url}"); 
        background-size: cover; background-attachment: fixed; 
        font-family: 'Noto Sans SC', sans-serif; 
    }}
    
    section[data-testid="stSidebar"] {{ 
        background: rgba(255,255,255,0.4) !important; 
        backdrop-filter: blur(25px); 
        border-right: 1px solid rgba(212,175,55,0.2); 
    }}
    
    .auth-card {{ 
        background: var(--bg-glass); padding: 40px; border-radius: 32px; 
        border: 1px solid rgba(212, 175, 55, 0.3); max-width: 460px; margin: 0 auto; 
        box-shadow: 0 50px 100px rgba(0,0,0,0.15); backdrop-filter: blur(20px);
    }}
    
    .hyper-title {{ 
        font-family: 'Space Grotesk', sans-serif; font-weight: 800; 
        background: linear-gradient(135deg, #B8860B, #D4AF37, #FFD700); 
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; 
        text-align: center; letter-spacing: -1px;
    }}
    
    div.stExpander {{ 
        background: rgba(255, 255, 255, 0.98) !important; border-radius: 18px !important; 
        border: 1px solid rgba(212,175,55,0.15) !important; margin-bottom: 15px; 
        transition: 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
    }}
    div.stExpander:hover {{ transform: translateY(-3px); border-color: var(--gold) !important; box-shadow: 0 10px 40px rgba(212,175,55,0.1) !important; }}
    
    .stButton>button {{ 
        border-radius: 14px; background: linear-gradient(135deg, #D4AF37, #B8860B) !important; 
        color: white !important; font-weight: 700; border: none !important; 
        box-shadow: 0 4px 15px rgba(184,134,11,0.2); 
    }}
    
    .badge {{ display: inline-block; padding: 2px 12px; border-radius: 12px; background: rgba(212,175,55,0.12); color: #8B6B1B; font-size: 0.75rem; font-weight: 800; margin-right: 8px; border: 1px solid rgba(212,175,55,0.1); }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心业务逻辑与辅助函数
# ==========================================
SUBJECTS = {"chinese":"语文", "math":"数学", "english":"英语", "physics":"物理", "chemistry":"化学", "biology":"生物", "history":"历史", "geography":"地理", "politics":"政治"}
def get_user_path(uid): return f"artifacts/{APP_ID}/users/{uid}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"
def hash_pwd(p): return hashlib.sha256(p.encode()).hexdigest()

def load_json(sid):
    """从本地 data/ 文件夹加载学科知识点"""
    p = os.path.join("data", f"{sid}.json")
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_json(sid, data):
    """保存考点到磁盘 (仅在 GCP/本地持久化环境中有效)"""
    if not os.path.exists("data"): os.makedirs("data")
    with open(os.path.join("data", f"{sid}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def sync_user_data(uid):
    """从 Firestore 云端拉取同步用户进度"""
    try:
        with st.spinner("🧠 正在从云端神经网格同步记忆..."):
            # 增加 GCP 优化后的超长时间 stream 等待
            docs = db.collection(f"{get_user_path(uid)}/progress").stream(timeout=45)
            mastered, difficult = set(), set()
            for d in docs:
                v = d.to_dict()
                key = f"{v['subject_id']}_{v['title']}"
                if v.get("is_mastered") == 1: mastered.add(key)
                if v.get("is_difficult") == 1: difficult.add(key)
            st.session_state.mastered_points, st.session_state.difficult_points = mastered, difficult
            st.session_state.data_synced = True
    except Exception:
        st.warning("⚠️ 部分云端进度载入延迟，请稍后刷新。")

def update_cloud_point(uid, sid, title, m=None, d=None):
    """同步单一知识点状态到云端"""
    try:
        did = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
        ref = db.document(f"{get_user_path(uid)}/progress/{did}")
        data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
        if m is not None: data["is_mastered"] = 1 if m else 0
        if d is not None: data["is_difficult"] = 1 if d else 0
        safe_set(ref, data)
    except: pass

def speak_text(text):
    """浏览器端文本转语音"""
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(text)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

# ==========================================
# 4. 身份认证模块 (全量 Admin 功能保留)
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "data_synced" not in st.session_state: st.session_state.data_synced = False
if "test_queue" not in st.session_state: st.session_state.test_queue = []

def auth_interface():
    inject_ui_styles()
    st.markdown('<div style="height:10vh;"></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.markdown('<div class="auth-card"><h1 class="hyper-title">NEURAL ID</h1>', unsafe_allow_html=True)
        tabs = st.tabs(["🔒 极速登录", "✨ 账号激活"])
        
        with tabs[0]:
            l_u = st.text_input("探测员 ID", key="l_u", placeholder="admin 或 注册 ID")
            l_p = st.text_input("神经密钥 Key", key="l_p", type="password")
            if st.button("建立物理连接", use_container_width=True):
                try:
                    user_ref = db.document(f"{get_public_path()}/users/{l_u}")
                    user_doc = safe_get(user_ref)
                    
                    # 管理员初始化逻辑
                    if l_u == "admin" and not user_doc.exists and l_p == "admin":
                        safe_set(user_ref, {"password": hash_pwd("admin"), "reg_date": str(date.today())})
                        user_doc = safe_get(user_ref)
                        st.info("检测到初始部署，已激活 Admin 权限。")

                    if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                        st.session_state.logged_in, st.session_state.user_contact = True, l_u
                        sync_user_data(l_u); st.rerun()
                    else: st.error("❌ 验证未通过：ID 或密钥错误")
                except (DeadlineExceeded, RetryError):
                    st.error("🛰️ 网络链路拥塞：建议使用 Watt 加速器连接香港/日本节点。")
                except Exception as e:
                    st.error(f"⚠️ 系统异常: {e}")
        
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u"); r_p = st.text_input("设置密钥", key="r_p", type="password")
            r_v = st.text_input("验证码", placeholder="点击右侧按钮获取")
            if st.button("获取激活代码"):
                st.session_state.code = str(random.randint(1000, 9999))
                st.toast(f"【验证码】您的代码是：{st.session_state.code}", icon="📩")
            if st.button("确认激活接入", use_container_width=True):
                if r_v != st.session_state.get('code'): st.error("验证码错误")
                elif len(r_p) < 5: st.error("密钥长度不足 5 位")
                else:
                    try:
                        user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                        if safe_get(user_ref).exists: st.error("该 ID 已在网格中")
                        else:
                            safe_set(user_ref, {"password": hash_pwd(r_p), "reg_date": str(date.today())})
                            db.document(f"{get_public_path()}/stats/global").set({"user_count": firestore.Increment(1)}, merge=True)
                            st.success("✅ 激活成功！请返回登录。")
                    except: st.error("云端注册服务超时。")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 5. 主程序控制流
# ==========================================
if not st.session_state.logged_in:
    auth_interface()
elif not st.session_state.started:
    inject_ui_styles()
    st.markdown('<div style="height:15vh;"></div><h1 class="hyper-title" style="font-size:5.5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; font-weight:800; font-size:1.4rem;">探测员 {st.session_state.user_contact}，连接已就绪</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    if c2.button("INITIALIZE LINK", use_container_width=True): st.session_state.started = True; st.rerun()
else:
    inject_ui_styles(); u = st.session_state.user_contact
    if not st.session_state.data_synced: sync_user_data(u)
    
    with st.sidebar:
        st.markdown(f"<div style='padding:14px; border-radius:18px; background:rgba(212,175,55,0.1); border:1px solid rgba(212,175,55,0.4); text-align:center; color:#8B6B1B; font-weight:bold;'>👤 {u}</div>", unsafe_allow_html=True)
        st.write("")
        mode = st.selectbox("系统指令", ["智脑看板", "神经元复习", "闪念卡片模式", "全科大挑战", "在线录入预览", "资料管理中心", "安全中心"])
        st.divider()
        subject_id = st.selectbox("学科对照", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT (断开链路)", use_container_width=True): st.session_state.clear(); st.rerun()

    # --- 功能分发 ---
    
    if mode == "智脑看板":
        st.markdown("## 📊 神经网络状态监测")
        try:
            stats = db.document(f"{get_public_path()}/stats/global").get().to_dict() or {"user_count": 0}
            c1, c2, c3 = st.columns(3)
            c1.metric("云端已掌握", len(st.session_state.mastered_points))
            c2.metric("高考倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
            c3.metric("网格总人数", stats.get("user_count", 0))
            st.divider()
            for sid, name in SUBJECTS.items():
                d = load_json(sid); m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
                st.write(f"**{name}** ({m}/{len(d)})"); st.progress(m/len(d) if d else 0)
        except: st.error("看板数据加载延迟，请稍后...")

    elif mode == "神经元复习":
        st.markdown(f"### {SUBJECTS[subject_id]} 系统")
        data = load_json(subject_id)
        chaps = sorted(list(set(i.get("chapter", "未分类") for i in data)))
        sel_ch = st.selectbox("📚 章节过滤", ["全部"] + chaps)
        srch = st.text_input("🔍 搜索考点标题")
        
        for item in data:
            if (sel_ch != "全部" and item.get("chapter", "未分类") != sel_ch) or (srch and srch.lower() not in item['title'].lower()): continue
            m_key = f"{subject_id}_{item['title']}"
            is_m, is_d = m_key in st.session_state.mastered_points, m_key in st.session_state.difficult_points
            
            with st.expander(f"{'✅' if is_m else ('⭐' if is_d else '🧬')} {item['title']}"):
                st.markdown(f"<span class='badge'>📚 {item.get('chapter','未分类')}</span>", unsafe_allow_html=True)
                st.write(item['content'])
                if item.get('formula'): st.latex(item['formula'])
                if item.get('image'): st.image(item['image'], use_container_width=True)
                st.write("")
                ca, cb, cc = st.columns(3)
                if ca.button("🔊 朗读", key=f"v_{m_key}"): speak_text(item['content'])
                if cb.button("⭐ 重点" if not is_d else "🌟 取消", key=f"f_{m_key}"):
                    update_cloud_point(u, subject_id, item['title'], d=not is_d)
                    st.session_state.difficult_points.add(m_key) if not is_d else st.session_state.difficult_points.discard(m_key); st.rerun()
                if cc.checkbox("我已掌握", key=f"m_{m_key}", value=is_m):
                    if not is_m: 
                        update_cloud_point(u, subject_id, item['title'], m=True)
                        st.session_state.mastered_points.add(m_key); st.rerun()
                elif is_m:
                    update_cloud_point(u, subject_id, item['title'], m=False)
                    st.session_state.mastered_points.discard(m_key); st.rerun()

    elif mode == "闪念卡片模式":
        data = load_json(subject_id)
        if data:
            if "f_idx" not in st.session_state: st.session_state.f_idx = 0
            it = data[st.session_state.f_idx % len(data)]
            st.markdown(f"### ⚡ 快速神经脉冲: {SUBJECTS[subject_id]}")
            with st.container(border=True):
                st.caption(f"考点序号 {st.session_state.f_idx+1}/{len(data)}")
                st.title(it['title'])
                if st.button("🔍 揭晓解析中心", use_container_width=True): 
                    st.info(it['content'])
                    if it.get('formula'): st.latex(it['formula'])
            bc1, bc2 = st.columns(2)
            if bc1.button("← PREV", use_container_width=True): st.session_state.f_idx -= 1; st.rerun()
            if bc2.button("NEXT →", use_container_width=True): st.session_state.f_idx += 1; st.rerun()

    elif mode == "全科大挑战":
        st.markdown("### 🏁 跨学科随机自测 (10题)")
        if not st.session_state.test_queue:
            if st.button("🚀 开始闯关挑战", use_container_width=True):
                all_pts = []
                for s in SUBJECTS.keys():
                    for i in load_json(s): i['sid'] = s; all_pts.append(i)
                if len(all_pts) >= 10:
                    st.session_state.test_queue = random.sample(all_pts, 10); st.session_state.ti = 0; st.rerun()
                else: st.error("考点数据不足 10 条")
        elif st.session_state.ti < len(st.session_state.test_queue):
            it = st.session_state.test_queue[st.session_state.ti]
            st.progress((st.session_state.ti+1)/10)
            with st.container(border=True):
                st.caption(f"学科：{SUBJECTS[it['sid']]} | 第 {st.session_state.ti+1} 题")
                st.title(it['title'])
                if st.checkbox("查看核心解析"): 
                    st.success(it['content'])
                    if it.get('formula'): st.latex(it['formula'])
                tc1, tc2 = st.columns(2)
                if tc1.button("✅ 记住了", use_container_width=True): st.session_state.ti += 1; st.rerun()
                if tc2.button("❌ 没记住，设为难点", use_container_width=True):
                    update_cloud_point(u, it['sid'], it['title'], d=True); st.session_state.ti += 1; st.rerun()
        else:
            st.success("🎉 挑战完成！全部掌握。"); st.balloons()
            if st.button("重新开始挑战", use_container_width=True): st.session_state.test_queue = []; st.rerun()

    elif mode == "在线录入预览":
        st.markdown("## ✏️ 实时考点写入同步")
        ce1, ce2 = st.columns(2)
        with ce1:
            t_in = st.text_input("考点标题"); ch_in = st.text_input("章节名称")
            c_in = st.text_area("详细解析内容 (支持 Markdown)"); f_in = st.text_input("LaTeX 公式")
            if st.button("✅ 同步至物理磁盘", use_container_width=True):
                if t_in and c_in:
                    curr = load_json(subject_id)
                    curr.append({"title":t_in, "chapter":ch_in or "通用", "content":c_in, "formula":f_in})
                    save_json(subject_id, curr); st.success("同步成功，重启服务后永久生效")
        with ce2:
            st.caption("✨ 实时神经元渲染预览")
            if t_in: 
                with st.container(border=True): 
                    st.markdown(f"### {t_in}"); st.write(c_in)
                    if f_in: st.latex(f_in)

    elif mode == "资料管理中心":
        st.markdown("## 📥 资料包导出与数据同步")
        sel = st.multiselect("勾选目标学科", options=list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("🚀 生成 Markdown 资料包"):
            res = f"# 🎓 高中复习笔记精选 - {date.today()}\n\n"
            for s in sel:
                res += f"## 【{SUBJECTS[s]}】\n"
                for i in load_json(s): res += f"### {i['title']}\n{i['content']}\n\n"
            st.download_button("💾 点击下载 MD 文件", res, file_name=f"review_{date.today()}.md")

    elif mode == "安全中心":
        st.title("⚙️ 密钥管理中心")
        with st.form("pwd_form"):
            np = st.text_input("设置新神经密钥 Key (至少5位)", type="password")
            if st.form_submit_button("UPDATE CLOUD KEY"):
                if len(np) >= 5:
                    db.document(f"{get_public_path()}/users/{u}").update({"password": hash_pwd(np)})
                    st.success("✅ 云端同步成功，下次登录生效。")
                else: st.error("密钥过短，系统拒绝更新。")
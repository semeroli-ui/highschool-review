import streamlit as st
import json
import os
import random
import hashlib
import pandas as pd
import io
from datetime import date
import firebase_admin
from firebase_admin import credentials, firestore
import streamlit.components.v1 as components

# ==========================================
# 1. 云端数据库初始化 (Firebase Firestore)
# ==========================================
def init_firestore():
    """从 Streamlit Secrets 安全初始化 Firebase"""
    if not firebase_admin._apps:
        try:
            # 这里的 firebase 对应 Streamlit Secrets 中的配置键
            cred_dict = dict(st.secrets["firebase"])
            # 处理私钥中的换行符问题
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"云端数据库配置错误: {e}。请确保已在 Streamlit Secrets 中配置 [firebase] 块。")
            st.stop()
    return firestore.client()

db = init_firestore()
APP_ID = "highschool-pro-prod"  # 应用唯一标识

# 遵循 Firestore 路径规范
def get_user_path(user_id): return f"artifacts/{APP_ID}/users/{user_id}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"

# ==========================================
# 2. 极致现代美学配置 (V6.0 高清生产版)
# ==========================================
st.set_page_config(
    page_title="HighSchool Pro | 智能云端复习终端",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def inject_hyper_css(is_landing=True):
    """注入基于原图配色的极致 UI"""
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
    div.stExpander {{ background: rgba(255, 255, 255, 0.92) !important; border: 1px solid rgba(212, 175, 55, 0.2) !important; border-radius: 18px !important; transition: 0.3s ease; margin-bottom: 1.2rem; }}
    div.stExpander:hover {{ border: 1px solid #D4AF37 !important; transform: translateY(-4px); }}
    .chapter-badge {{ display: inline-flex; padding: 4px 12px; border-radius: 20px; background: rgba(212, 175, 55, 0.12); color: #8B6B1B; font-size: 0.8rem; font-weight: 700; margin-right: 12px; border: 1px solid rgba(212, 175, 55, 0.2); }}
    .stButton>button {{ border-radius: 14px; font-weight: 700; background: linear-gradient(135deg, #D4AF37, #B8860B) !important; color: white !important; border: none !important; }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心功能：数据交互逻辑 (云端适配版)
# ==========================================
def hash_pwd(pwd): return hashlib.sha256(pwd.encode()).hexdigest()

def update_cloud_node(user_id, sid, title, m=None, d=None):
    """同步掌握进度到 Firestore"""
    doc_id = hashlib.md5(f"{sid}_{title}".encode()).hexdigest()
    doc_ref = db.document(f"{get_user_path(user_id)}/progress/{doc_id}")
    update_data = {"subject_id": sid, "title": title, "update_at": str(date.today())}
    if m is not None: update_data["is_mastered"] = 1 if m else 0
    if d is not None: update_data["is_difficult"] = 1 if d else 0
    doc_ref.set(update_data, merge=True)

def sync_user_data(user_id):
    """从云端拉取用户所有进度"""
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

def save_json(sid, data):
    p = os.path.join("data", f"{sid}.json")
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def speak(text):
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(text)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

# ==========================================
# 5. 身份认证页面 (Firestore 核心版)
# ==========================================
def auth_page():
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:12vh;"></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="auth-card"><div class="auth-header"><h2 class="hyper-title">NEURAL ID</h2></div>', unsafe_allow_html=True)
        tabs = st.tabs(["🔑 登录", "✨ 注册"])
        with tabs[0]:
            l_u = st.text_input("账号 ID", key="l_u")
            l_p = st.text_input("密钥 Key", key="l_p", type="password")
            if st.button("同步记忆 (LOGIN)", use_container_width=True):
                user_doc = db.document(f"{get_public_path()}/users/{l_u}").get()
                if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                    st.session_state.logged_in = True
                    st.session_state.user_contact = l_u
                    st.rerun()
                else: st.error("密钥验证不通过")
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u", placeholder="邮箱或手机号")
            r_p = st.text_input("设置密钥", key="r_p", type="password")
            if st.button("激活并接入 (REGISTER)", use_container_width=True):
                user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                if user_ref.get().exists: st.error("该 ID 已在网格中")
                elif len(r_p) < 5: st.error("密钥强度不足")
                else:
                    user_ref.set({"password": hash_pwd(r_p), "reg_date": str(date.today())})
                    # 更新全局用户统计
                    stats_ref = db.document(f"{get_public_path()}/stats/global")
                    stats_ref.set({"user_count": firestore.Increment(1)}, merge=True)
                    st.success("激活成功！请执行登录")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 6. 主程序控制器
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "test_queue" not in st.session_state: st.session_state.test_queue = []

if not st.session_state.logged_in:
    auth_page()
elif not st.session_state.started:
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:15vh;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hyper-title" style="font-size:5.5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; color:#1a1a2e; font-weight:800; font-size:1.4rem;">探测员 {st.session_state.user_contact}，云端链路已就绪</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    with c2:
        if st.button("INITIALIZE LINK", use_container_width=True):
            st.session_state.started = True; st.rerun()
else:
    inject_hyper_css(is_landing=False)
    u = st.session_state.user_contact
    # 自动同步云端进度到 Session
    if "mastered_points" not in st.session_state:
        sync_user_data(u)
    
    with st.sidebar:
        st.markdown(f"<div style='padding:12px; border-radius:18px; background:rgba(212,175,55,0.1); border:1px solid rgba(212,175,55,0.4); text-align:center; color:#8B6B1B; font-weight:bold;'>👤 {u}</div>", unsafe_allow_html=True)
        mode = st.selectbox("系统指令", ["智脑看板", "神经元复习", "闪念卡片", "全科挑战", "在线录入", "批量导入 📤", "导出中心 📥", "安全设置"])
        st.divider()
        subject_id = st.selectbox("目标学科", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT (断开连接)", use_container_width=True):
            st.session_state.clear(); st.rerun()

    # --- 各功能模块逻辑 ---
    
    if mode == "智脑看板":
        st.markdown("<h2 style='color:#B8860B;'>📊 神经网络同步状态</h2>", unsafe_allow_html=True)
        global_stats = db.document(f"{get_public_path()}/stats/global").get().to_dict() or {}
        user_count = global_stats.get("user_count", 0)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("当前已掌握", len(st.session_state.mastered_points))
        c2.metric("高考倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
        c3.metric("全网总用户", user_count)
        
        st.divider()
        for sid, name in SUBJECTS.items():
            d = load_json(sid)
            m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
            st.write(f"**{name}** ({m}/{len(d)})")
            st.progress(m/len(d) if d else 0)

    elif mode == "神经元复习":
        st.markdown(f"<h2 style='color:#B8860B;'>{SUBJECTS[subject_id]}</h2>", unsafe_allow_html=True)
        data = load_json(subject_id)
        chaps = sorted(list(set(i.get("chapter", "未分类") for i in data)))
        sel_chap = st.selectbox("📚 章节过滤", ["全部"] + chaps)
        
        for item in data:
            if sel_chap != "全部" and item.get("chapter", "未分类") != sel_chap: continue
            m_key = f"{subject_id}_{item['title']}"
            is_m, is_d = m_key in st.session_state.mastered_points, m_key in st.session_state.difficult_points
            icon = "✅" if is_m else ("⭐" if is_d else "🧬")
            
            with st.expander(f"{icon} {item['title']}"):
                st.markdown(f"<span class='chapter-badge'>📚 {item.get('chapter','未分类')}</span>", unsafe_allow_html=True)
                if item.get('image'): st.image(item['image'], use_container_width=True)
                st.markdown(f"<div style='color:#333; line-height:1.6;'>{item['content']}</div>", unsafe_allow_html=True)
                if item.get('formula'): st.latex(item['formula'])
                st.write("")
                ca, cb, cc = st.columns(3)
                if ca.button("🔊 朗读", key=f"v_{m_key}"): speak(item['content'])
                if cb.button("⭐ 重点" if not is_d else "🌟 取消重点", key=f"f_{m_key}"):
                    update_cloud_node(u, subject_id, item['title'], d=not is_d)
                    st.session_state.difficult_points.add(m_key) if not is_d else st.session_state.difficult_points.remove(m_key)
                    st.rerun()
                if cc.checkbox("掌握", key=f"m_chk_{m_key}", value=is_m):
                    if not is_m:
                        update_cloud_node(u, subject_id, item['title'], m=True)
                        st.session_state.mastered_points.add(m_key); st.rerun()
                elif is_m:
                    update_cloud_node(u, subject_id, item['title'], m=False)
                    st.session_state.mastered_points.remove(m_key); st.rerun()

    elif mode == "在线录入":
        st.markdown("## ✏️ 实时考点录入")
        col1, col2 = st.columns(2)
        with col1:
            t_in = st.text_input("标题", key="t_in")
            c_in = st.text_area("内容", key="c_in")
            ch_in = st.text_input("章节", key="ch_in")
            f_in = st.text_input("LaTeX 公式", key="f_in")
            img_in = st.text_input("图片链接", key="img_in")
            if st.button("✅ 物理保存到服务器"):
                if t_in and c_in:
                    curr = load_json(subject_id)
                    curr.append({"title": t_in, "content": c_in, "chapter": ch_in or "通用", "formula": f_in, "image": img_in})
                    save_json(subject_id, curr); st.success("保存成功")
        with col2:
            st.caption("✨ 实时预览")
            if t_in:
                st.markdown(f"### {t_in}")
                if img_in: st.image(img_in)
                st.write(c_in)
                if f_in: st.latex(f_in)

    elif mode == "批量导入 📤":
        st.markdown("## 📥 批量导入 (CSV)")
        template_df = pd.DataFrame(columns=["title", "chapter", "content", "formula", "image"])
        template_df.loc[0] = ["示例", "第一章", "解析", "E=mc^2", "https://img.jpg"]
        csv_buf = io.BytesIO()
        template_df.to_csv(csv_buf, index=False, encoding='utf-8-sig')
        st.download_button("💾 下载模板", csv_buf.getvalue(), "template.csv", "text/csv")
        
        up_file = st.file_uploader("上传已填写的 CSV", type="csv")
        if up_file:
            df = pd.read_csv(up_file, encoding='utf-8-sig')
            st.dataframe(df.head())
            if st.button("🔥 开始同步"):
                curr = load_json(subject_id)
                for _, r in df.iterrows():
                    curr.append({"title": str(r['title']), "chapter": str(r.get('chapter','通用')), "content": str(r['content']), "formula": str(r.get('formula','')), "image": str(r.get('image',''))})
                save_json(subject_id, curr); st.success("同步成功")

    elif mode == "导出中心 📥":
        st.markdown("## 📥 资料包导出")
        sel_ids = st.multiselect("勾选学科", options=list(SUBJECTS.keys()), default=[subject_id], format_func=lambda x: SUBJECTS[x])
        if st.button("🚀 生成 Markdown 预览"):
            final_c = f"# 🎓 定制复习包 - {date.today()}\n\n"
            for sid in sel_ids:
                data = load_json(sid)
                final_c += f"# 【{SUBJECTS[sid]}】\n"
                for p in data:
                    final_c += f"## {p['title']}\n{p['content']}\n\n---\n\n"
            st.text_area("预览", final_c, height=300)
            st.download_button("💾 点击下载", final_c, file_name="review.md")

    # (其他模式逻辑... 保持 V5.3 的完整结构)
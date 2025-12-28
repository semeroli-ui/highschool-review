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
            # 处理私钥格式，解决 PEM 识别问题
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

db = init_firestore()
APP_ID = "highschool-pro-prod"

def get_user_path(user_id): return f"artifacts/{APP_ID}/users/{user_id}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"

# ==========================================
# 2. 极致现代美学配置 (V6.4 视觉方案)
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
        background-size: cover; background-position: center; background-attachment: fixed;
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

    .stApp {{ {selected_bg} color: var(--text-main); }}

    section[data-testid="stSidebar"] {{
        background-color: rgba(255, 255, 255, 0.4) !important;
        backdrop-filter: blur(25px);
        border-right: 1px solid rgba(212, 175, 55, 0.1);
    }}

    .auth-card {{
        background: var(--glass-bg);
        padding: 40px; border-radius: 28px; border: 1px solid var(--glass-border);
        max-width: 420px; margin: 0 auto; box-shadow: 0 40px 80px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(20px);
    }}

    .hyper-title {{
        font-family: 'Space Grotesk', sans-serif; font-weight: 800;
        background: linear-gradient(135deg, #B8860B, #D4AF37, #FFD700);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-align: center; letter-spacing: -2px;
    }}

    div.stExpander {{
        background: rgba(255, 255, 255, 0.92) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 18px !important; margin-bottom: 1.2rem;
        box-shadow: 0 10px 30px rgba(212, 175, 55, 0.05) !important;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }}
    div.stExpander:hover {{
        border: 1px solid #D4AF37 !important;
        transform: translateY(-4px);
    }}

    .chapter-badge {{
        display: inline-flex; align-items: center; padding: 4px 12px; border-radius: 20px;
        background: rgba(212, 175, 55, 0.12); color: #8B6B1B; font-size: 0.8rem;
        font-weight: 700; margin-right: 12px; border: 1px solid rgba(212, 175, 55, 0.2);
    }}

    .stButton>button {{
        border-radius: 14px; font-weight: 700;
        background: linear-gradient(135deg, #D4AF37, #B8860B) !important;
        color: white !important; border: none !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. 核心逻辑：数据交互 (Firestore)
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
    except Exception: pass

def sync_user_data(user_id):
    """从云端拉取进度的核心函数"""
    try:
        with st.spinner("🧠 正在同步云端记忆网格..."):
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
    except Exception:
        st.error("同步失败，请检查网络并刷新。")

# ==========================================
# 4. 辅助函数与数据加载
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
    if not os.path.exists("data"): os.makedirs("data")
    with open(p, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def load_all_data():
    all_d = []
    for sid, sname in SUBJECTS.items():
        for item in load_json(sid):
            if isinstance(item, dict):
                item['subject_name'], item['subject_id'] = sname, sid
                all_d.append(item)
    return all_d

def speak(text):
    js = f"""<script>window.speechSynthesis.cancel(); var m=new SpeechSynthesisUtterance({json.dumps(text)}); m.lang='zh-CN'; window.speechSynthesis.speak(m);</script>"""
    components.html(js, height=0)

# ==========================================
# 5. 初始化状态
# ==========================================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "started" not in st.session_state: st.session_state.started = False
if "data_synced" not in st.session_state: st.session_state.data_synced = False
if "mastered_points" not in st.session_state: st.session_state.mastered_points = set()
if "difficult_points" not in st.session_state: st.session_state.difficult_points = set()
if "test_queue" not in st.session_state: st.session_state.test_queue = []
if "test_index" not in st.session_state: st.session_state.test_index = 0
if "test_results" not in st.session_state: st.session_state.test_results = []

# ==========================================
# 6. 身份认证页面
# ==========================================
def auth_page():
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:10vh;"></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('<div class="auth-card"><h2 class="hyper-title">NEURAL ID</h2>', unsafe_allow_html=True)
        tabs = st.tabs(["🔑 登录", "✨ 注册"])
        
        with tabs[0]:
            l_u = st.text_input("账号 ID", key="l_u", placeholder="admin 或 注册账号")
            l_p = st.text_input("密钥 Key", key="l_p", type="password")
            if st.button("同步记忆 (LOGIN)", use_container_width=True):
                try:
                    user_ref = db.document(f"{get_public_path()}/users/{l_u}")
                    user_doc = user_ref.get()
                    # 管理员特殊处理：如果 admin 不存在，自动使用 admin/admin 初始化
                    if l_u == "admin" and not user_doc.exists and l_p == "admin":
                        user_ref.set({"password": hash_pwd("admin"), "reg_date": str(date.today())})
                        user_doc = user_ref.get()
                        st.info("检测到初始连接，已激活管理员账号。")

                    if user_doc.exists and user_doc.to_dict().get("password") == hash_pwd(l_p):
                        st.session_state.logged_in = True
                        st.session_state.user_contact = l_u
                        sync_user_data(l_u)
                        st.rerun()
                    else: st.error("账号验证失败")
                except (RetryError, ServiceUnavailable):
                    st.error("⚠️ 云端握手超时，请检查网络。")
        
        with tabs[1]:
            r_u = st.text_input("新账号 ID", key="r_u")
            r_p = st.text_input("设置密钥", key="r_p", type="password")
            r_p2 = st.text_input("重复密钥", key="r_p2", type="password")
            v_c1, v_c2 = st.columns([1.2, 1])
            with v_c1: v_in = st.text_input("验证码", key="r_v", placeholder="输入代码")
            with v_c2:
                st.write('<div style="margin-top:28px;"></div>', unsafe_allow_html=True)
                if st.button("获取"):
                    if r_u:
                        code = str(random.randint(1000, 9999))
                        st.session_state.sent_code = code
                        st.toast(f"【验证码】您的注册代码是：{code}", icon="📩")
                    else: st.error("请填账号")
            if st.button("激活接入 (REGISTER)", use_container_width=True):
                if r_p != r_p2: st.error("密码不一致")
                elif v_in != st.session_state.get('sent_code'): st.error("验证码错")
                elif len(r_p) < 5: st.error("密钥太短")
                else:
                    user_ref = db.document(f"{get_public_path()}/users/{r_u}")
                    if user_ref.get().exists: st.error("账号已占用")
                    else:
                        user_ref.set({"password": hash_pwd(r_p), "reg_date": str(date.today())})
                        db.document(f"{get_public_path()}/stats/global").set({"user_count": firestore.Increment(1)}, merge=True)
                        st.success("成功！请登录")
        st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 7. 主程序控制器
# ==========================================
if not st.session_state.logged_in:
    auth_page()
elif not st.session_state.started:
    inject_hyper_css(is_landing=True)
    st.markdown('<div style="height:15vh;"></div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hyper-title" style="font-size:5.5rem;">NEURAL HUB</h1>', unsafe_allow_html=True)
    st.markdown(f'<p style="text-align:center; font-weight:800; font-size:1.4rem;">探测员 {st.session_state.user_contact}，连接已就绪</p>', unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1, 1])
    with c2:
        if st.button("INITIALIZE LINK", use_container_width=True):
            st.session_state.started = True; st.rerun()
else:
    inject_hyper_css(is_landing=False)
    u = st.session_state.user_contact
    if not st.session_state.data_synced: sync_user_data(u)
    
    with st.sidebar:
        st.markdown(f"<div style='padding:12px; border-radius:18px; background:rgba(212,175,55,0.1); border:1px solid rgba(212,175,55,0.4); text-align:center; color:#8B6B1B; font-weight:bold;'>👤 {u}</div>", unsafe_allow_html=True)
        st.write("")
        mode = st.selectbox("系统指令", ["智脑看板", "神经元复习", "闪念卡片模式", "全科闯关挑战", "在线录入预览", "批量数据导入 📤", "资料导出包 📥", "安全设置"])
        st.divider()
        subject_id = st.selectbox("目标学科对照", list(SUBJECTS.keys()), format_func=lambda x: SUBJECTS[x])
        if st.button("LOGOUT"): st.session_state.clear(); st.rerun()

    # --- 各模块分发 ---

    if mode == "智脑看板":
        st.markdown("## 📊 神经网络同步状态")
        stats = db.document(f"{get_public_path()}/stats/global").get().to_dict() or {"user_count": 0}
        c1, c2, c3 = st.columns(3)
        c1.metric("当前已掌握", len(st.session_state.mastered_points))
        c2.metric("决战倒计时", f"{(date(2026, 6, 7) - date.today()).days}D")
        c3.metric("全网总用户", stats.get("user_count", 0))
        st.divider()
        for sid, name in SUBJECTS.items():
            d = load_json(sid)
            m = len([x for x in d if f"{sid}_{x['title']}" in st.session_state.mastered_points])
            st.write(f"**{name}** ({m}/{len(d)})")
            st.progress(m/len(d) if d else 0)

    elif mode == "神经元复习":
        st.markdown(f"### {SUBJECTS[subject_id]}")
        data = load_json(subject_id)
        chaps = sorted(list(set(i.get("chapter", "未分类") for i in data)))
        sel_ch = st.selectbox("📚 章节过滤", ["全部"] + chaps)
        search = st.text_input("🔍 搜索考点")
        for item in data:
            if (sel_ch != "全部" and item.get("chapter", "未分类") != sel_ch) or (search and search.lower() not in item['title'].lower()): continue
            m_key = f"{subject_id}_{item['title']}"
            is_m, is_d = m_key in st.session_state.mastered_points, m_key in st.session_state.difficult_points
            with st.expander(f"{'✅' if is_m else ('⭐' if is_d else '🧬')} {item['title']}"):
                st.markdown(f"<span class='chapter-badge'>📚 {item.get('chapter','未分类')}</span>", unsafe_allow_html=True)
                if item.get('image'): st.image(item['image'], use_container_width=True)
                st.write(item['content'])
                if item.get('formula'): st.latex(item['formula'])
                ca, cb, cc = st.columns(3)
                if ca.button("🔊 朗读", key=f"v_{m_key}"): speak(item['content'])
                if cb.button("⭐ 重点" if not is_d else "🌟 取消", key=f"f_{m_key}"):
                    update_cloud_node(u, subject_id, item['title'], d=not is_d)
                    st.session_state.difficult_points.add(m_key) if not is_d else st.session_state.difficult_points.discard(m_key)
                    st.rerun()
                if cc.checkbox("掌握", key=f"m_{m_key}", value=is_m):
                    if not is_m: 
                        update_cloud_node(u, subject_id, item['title'], m=True)
                        st.session_state.mastered_points.add(m_key); st.rerun()
                elif is_m:
                    update_cloud_node(u, subject_id, item['title'], m=False)
                    st.session_state.mastered_points.discard(m_key); st.rerun()

    elif mode == "闪念卡片模式":
        data = load_json(subject_id)
        if data:
            if "flash_idx" not in st.session_state: st.session_state.flash_idx = 0
            idx = st.session_state.flash_idx % len(data); item = data[idx]
            st.markdown(f"### ⚡ 闪念加速: {SUBJECTS[subject_id]}")
            with st.container(border=True):
                st.caption(f"NODE {idx+1}/{len(data)} | {item.get('chapter', '未分类')}")
                st.title(item['title'])
                if st.checkbox("🔍 揭晓内容", key=f"rev_{idx}"):
                    st.info(item['content'])
                    if item.get('formula'): st.latex(item['formula'])
            ba, bb = st.columns(2)
            if ba.button("PREV"): st.session_state.flash_idx -= 1; st.rerun()
            if bb.button("NEXT"): st.session_state.flash_idx += 1; st.rerun()

    elif mode == "全科闯关挑战":
        st.title("🏁 随机神经元大挑战")
        all_pts = load_all_data()
        if not st.session_state.test_queue:
            if st.button("🚀 开始 10 题自测", use_container_width=True):
                if len(all_pts) >= 10:
                    st.session_state.test_queue = random.sample(all_pts, 10); st.session_state.test_index = 0; st.session_state.test_results = []; st.rerun()
                else: st.error("数据不足")
        elif st.session_state.test_index < 10:
            idx = st.session_state.test_index; item = st.session_state.test_queue[idx]
            st.write(f"**进度: {idx+1}/10**"); st.progress((idx+1)/10)
            with st.container(border=True):
                st.caption(f"学科：{item.get('subject_name')} | 章节：{item.get('chapter','通用')}")
                st.title(item['title'])
                if st.checkbox("🔍 揭晓解析", key=f"t_rev_{idx}"):
                    st.info(item['content'])
                    if item.get("formula"): st.latex(item["formula"])
                tc1, tc2 = st.columns(2)
                if tc1.button("✅ 记住了", key=f"ok_{idx}", use_container_width=True):
                    st.session_state.test_results.append({"t": item['title'], "s": item['subject_name'], "status": "passed"})
                    st.session_state.test_index += 1; st.rerun()
                if tc2.button("❌ 设为难点", key=f"fail_{idx}", use_container_width=True):
                    update_cloud_node(u, item['subject_id'], item['title'], d=True)
                    st.session_state.test_results.append({"t": item['title'], "s": item['subject_name'], "status": "failed"})
                    st.session_state.test_index += 1; st.rerun()
        else:
            st.success("🎉 完成！"); st.balloons()
            for res in st.session_state.test_results:
                st.write(f"{'🟢' if res['status'] == 'passed' else '🔴'} 【{res['s']}】 {res['t']}")
            if st.button("重来"): st.session_state.test_queue = []; st.rerun()

    elif mode == "在线录入预览":
        st.markdown("## ✏️ 实时考点录入")
        ce1, ce2 = st.columns(2)
        with ce1:
            t_in = st.text_input("标题", key="t_in")
            ch_in = st.text_input("章节", key="ch_in")
            c_in = st.text_area("内容", key="c_in")
            f_in = st.text_input("LaTeX 公式", key="f_in")
            img_in = st.text_input("图片 URL", key="img_in")
            if st.button("✅ 保存同步"):
                if t_in and c_in:
                    curr = load_json(subject_id)
                    curr.append({"title": t_in, "chapter": ch_in or "通用", "content": c_in, "formula": f_in, "image": img_in})
                    save_json(subject_id, curr); st.success("已保存到虚拟磁盘")
        with ce2:
            st.caption("✨ 实时预览")
            if t_in:
                with st.container(border=True):
                    st.markdown(f"### {t_in}")
                    if img_in: st.image(img_in)
                    st.write(c_in)
                    if f_in: st.latex(f_in)

    elif mode == "批量数据导入 📤":
        st.markdown("## 📥 批量同步 (CSV)")
        template_df = pd.DataFrame(columns=["title", "chapter", "content", "formula", "image"])
        template_df.loc[0] = ["示例", "第一章", "内容", "E=mc^2", "https://img.jpg"]
        csv_buf = io.BytesIO()
        template_df.to_csv(csv_buf, index=False, encoding='utf-8-sig')
        st.download_button("💾 下载模板", csv_buf.getvalue(), "template.csv", "text/csv")
        up_file = st.file_uploader("上传 CSV", type="csv")
        if up_file:
            df = pd.read_csv(up_file, encoding='utf-8-sig')
            st.dataframe(df.head())
            if st.button("🔥 同步数据"):
                curr = load_json(subject_id)
                for _, r in df.iterrows():
                    curr.append({"title": str(r['title']), "chapter": str(r.get('chapter','通用')), "content": str(r['content']), "formula": str(r.get('formula','')), "image": str(r.get('image',''))})
                save_json(subject_id, curr); st.success("成功")

    elif mode == "资料导出包 📥":
        st.markdown("## 📥 资料下载")
        sel_ids = st.multiselect("勾选学科", options=list(SUBJECTS.keys()), default=[subject_id], format_func=lambda x: SUBJECTS[x])
        if st.button("🚀 生成复习包"):
            final_c = f"# 🎓 复习资料 - {date.today()}\n\n"
            for sid in sel_ids:
                data = load_json(sid)
                final_c += f"## 【{SUBJECTS[sid]}】\n"
                for p in data:
                    final_c += f"### {p['title']}\n{p['content']}\n\n"
            st.text_area("预览", final_c, height=300)
            st.download_button("💾 点击下载", final_c, file_name="review.md")

    elif mode == "安全设置":
        st.title("⚙️ 账户安全")
        with st.form("pwd_form"):
            np = st.text_input("设置新密钥 Key", type="password")
            if st.form_submit_button("UPDATE PASSWORD"):
                if len(np) >= 5:
                    db.document(f"{get_public_path()}/users/{u}").update({"password": hash_pwd(np)})
                    st.success("同步成功，下次生效")
                else: st.error("过短")
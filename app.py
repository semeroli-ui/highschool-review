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
    """从 Streamlit Secrets 安全初始化 Firebase"""
    if not firebase_admin._apps:
        try:
            # 这里的 firebase 对应 Streamlit Secrets 中的配置键 [firebase]
            cred_dict = dict(st.secrets["firebase"])
            # 处理私钥中的换行符转义问题
            cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
        except Exception as e:
            st.error(f"云端数据库配置错误: {e}。请确保已在 Streamlit Secrets 中配置 [firebase] 块。")
            st.stop()
    return firestore.client()

db = init_firestore()
APP_ID = "highschool-pro-prod"  # 应用云端唯一标识

# 遵循规范的路径结构
def get_user_path(user_id): return f"artifacts/{APP_ID}/users/{user_id}"
def get_public_path(): return f"artifacts/{APP_ID}/public/data"

# ==========================================
# 2. 极致现代美学配置 (视觉方案同步自 V5.3)
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
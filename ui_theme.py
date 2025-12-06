# ui_theme.py
import streamlit as st

PRIMARY = "#2563EB"
PRIMARY_DARK = "#1D4ED8"
BG = "#F3F4F6"
SIDEBAR_BG = "#F9FAFB"
CARD_BG = "#FFFFFF"
TEXT = "#111827"

def apply_theme(theme_name: str = "paper-light"):
    css = f"""
    <style>
    :root {{
        --primary: {PRIMARY};
        --primary-dark: {PRIMARY_DARK};
        --bg: {BG};
        --sidebar-bg: {SIDEBAR_BG};
        --card-bg: {CARD_BG};
        --text-color: {TEXT};
    }}

    /* ===== 전체 배경 / 텍스트 ===== */
    .stApp {{
        background-color: var(--bg) !important;
        color: var(--text-color) !important;
    }}
    .stApp, .stApp p, .stApp span, .stApp label, .stApp li,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
        color: var(--text-color) !important;
    }}

    /* 상단 헤더 (검정 띠 제거 느낌) */
    header[data-testid="stHeader"] {{
        background-color: var(--bg) !important;
        color: var(--text-color) !important;
    }}
    header[data-testid="stHeader"] * {{
        color: var(--text-color) !important;
    }}

    /* ===== 사이드바 ===== */
    section[data-testid="stSidebar"] {{
        background-color: var(--sidebar-bg) !important;
        color: var(--text-color) !important;
    }}
    section[data-testid="stSidebar"] * {{
        color: var(--text-color) !important;
    }}

    /* ===== 공통 카드 스타일 (metric, 컨테이너 등) ===== */
    div[data-testid="stMetric"], .stApp .card-like {{
        background-color: var(--card-bg) !important;
        border-radius: 16px !important;
        border: 1px solid #E5E7EB !important;
        padding: 0.75rem 1rem !important;
        box-shadow: 0 4px 10px rgba(15, 23, 42, 0.04);
    }}

    /* ===== 입력 위젯들 박스 느낌 통일 ===== */

    /* Selectbox / Multiselect / Number input 등 공통 외곽 */
    div[data-testid="stSelectbox"],
    div[data-testid="stMultiSelect"],
    div[data-testid="stNumberInput"],
    div[data-testid="stTextInput"],
    div[data-testid="stSlider"],
    div[data-testid="stDateInput"] {{
        background-color: var(--card-bg) !important;
        border-radius: 12px !important;
        border: 1px solid #E5E7EB !important;
        padding: 4px 8px !important;
    }}

    /* BaseWeb select 내부 배경 */
    div[data-baseweb="select"],
    div[data-baseweb="input"] {{
        background-color: transparent !important;
        color: var(--text-color) !important;
    }}

    /* ===== 멀티셀렉트 토큰: 파란 pill ===== */
    div[data-baseweb="tag"] {{
        background-color: var(--primary) !important;
        border-radius: 999px !important;
        border: none !important;
        padding-top: 2px !important;
        padding-bottom: 2px !important;
    }}
    div[data-baseweb="tag"] span {{
        color: #FFFFFF !important;
        font-weight: 500 !important;
    }}
    div[data-baseweb="tag"] svg {{
        fill: #FFFFFF !important;
    }}

    /* ===== 버튼 (기본/primary 둘 다) ===== */
    .stButton > button, button[kind="primary"] {{
        background-color: var(--primary) !important;
        color: #FFFFFF !important;
        border-radius: 999px !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.3rem !important;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.25);
    }}
    .stButton > button:hover, button[kind="primary"]:hover {{
        background-color: var(--primary-dark) !important;
    }}

    /* 체크박스 / 라디오 버튼 텍스트 색상 */
    div[role="radiogroup"] label, div[role="checkbox"] label {{
        color: var(--text-color) !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# -*- coding: utf-8 -*-
# 전공별 자격증 대시보드 — 합격률 없음 분리 + 난이도 등분 보정 + NCS 3단 필터 + 토글 표시

import re, io, qrcode
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

# -------------------------------------------------
# 기본 설정
# -------------------------------------------------
BASE_URL = "https://certificationapp-brnj3ctcykqixb9uyz9fb2.streamlit.app"
st.set_page_config(page_title="전공별 자격증 대시보드", layout="wide", page_icon="🎓")

def get_query_params():
    try:
        return dict(st.query_params)
    except Exception:
        return {k: (v[0] if isinstance(v, list) else v)
                for k, v in st.experimental_get_query_params().items()}

def use_korean_font():
    candidates = ["Malgun Gothic","AppleGothic","NanumGothic","Noto Sans CJK KR","DejaVu Sans"]
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for f in candidates:
        if f in installed:
            rcParams["font.family"] = f
            break
    rcParams["axes.unicode_minus"] = False

def apply_pretty_style():
    plt.rcParams.update({
        "axes.titleweight": "bold",
        "axes.titlesize": 15,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "grid.linestyle": "--",
        "grid.alpha": 0.35,
    })

def _force_light_theme():
    # 모든 환경에서 라이트 테마 강제: LocalStorage + URL(?theme=light) + 1회 새로고침
    st.markdown("""
    <script>
    (function(){
      try{
        const LS_KEY = "streamlitTheme";
        const desired = { base: "light" };
        let cur = {};
        try { cur = JSON.parse(localStorage.getItem(LS_KEY) || "{}"); } catch(e) {}
        const url = new URL(window.location.href);
        const qsTheme = (url.searchParams.get("theme") || "").toLowerCase();
        const needLs = (cur.base || "").toLowerCase() !== "light";
        const needQs = qsTheme !== "light";
        if (needLs || needQs) {
          localStorage.setItem(LS_KEY, JSON.stringify(Object.assign({}, cur, desired)));
          if (needQs) url.searchParams.set("theme","light");
          if (!sessionStorage.getItem("forcedLightOnce")) {
            sessionStorage.setItem("forcedLightOnce","1");
            window.location.replace(url.toString());
            return;
          }
        }
      }catch(e){}
    })();
    </script>
    """, unsafe_allow_html=True)

# URL에 ?theme=light 선제 세팅
try:
    st.query_params.update({"theme":"light"})
except Exception:
    st.experimental_set_query_params(theme="light")

# 시스템 다크 선호 무시하고 라이트로 고정
st.markdown("<style>:root{ color-scheme: light; }</style>", unsafe_allow_html=True)

use_korean_font(); apply_pretty_style()

# -------------------------------------------------
# 공통 유틸
# -------------------------------------------------
def hide_spines(ax):
    for s in ("top","right"):
        if s in ax.spines: ax.spines[s].set_visible(False)

def _to_key(series): return pd.Series(series, dtype="object").astype(str).str.strip()
def badge(t): return f"<span class='pill'>{t}</span>"

def fmt_int(x):
    if pd.isna(x): return "-"
    try: return f"{int(round(float(x))):,}"
    except Exception: return "-"

def _num_in_text(x):
    s = "" if x is None else str(x)
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return float(m.group(0)) if m else np.nan

def _emit_scroll_to_top_if_needed():
    if st.session_state.pop("_scroll_to_top", False):
        st.markdown("""
        <script>
        (function(){
          function goTop(){
            try{
              window.scrollTo({top:0, left:0, behavior:'smooth'});
              const main = document.querySelector('section.main');
              if (main && main.scrollTo) main.scrollTo({top:0, left:0, behavior:'smooth'});
              if (window.parent && window.parent !== window) {
                try { window.parent.scrollTo({top:0,left:0,behavior:'smooth'}); } catch(e){}
              }
            }catch(e){}
          }
          setTimeout(goTop, 0); setTimeout(goTop, 150); setTimeout(goTop, 300);
        })();
        </script>
        """, unsafe_allow_html=True)

def _safe_rerun():
    if hasattr(st, "rerun"): st.rerun()
    else: st.experimental_rerun()

def _st_image_compat(img_bytes_or_array):
    try: st.image(img_bytes_or_array, use_container_width=True)
    except TypeError: st.image(img_bytes_or_array, use_column_width=True)

def render_employ_donut_svg(male_pct, female_pct) -> str:
    def clamp(x):
        try: x = float(x)
        except Exception: x = 0.0
        return max(0.0, min(100.0, x))
    m = clamp(male_pct); f = clamp(female_pct)
    track = "#e5e7eb"; male = "#2563eb"; female = "#ef4444"
    cx, cy = 60, 60; r_outer, w_outer = 48, 8; r_inner, w_inner = 36, 8
    C_outer = 2*np.pi*r_outer; C_inner = 2*np.pi*r_inner
    dash_m = f"{C_outer*m/100:.3f} {C_outer:.3f}"
    dash_f = f"{C_inner*f/100:.3f} {C_inner:.3f}"
    return f"""
<div style="width:100%;display:block;">
  <svg viewBox="0 0 120 120" preserveAspectRatio="xMidYMid meet" style="width:100%;height:auto;display:block;">
    <g transform="rotate(-90 {cx} {cy})">
      <circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="{track}" stroke-width="{w_outer}" />
      <circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="none" stroke="{track}" stroke-width="{w_inner}" />
      <circle cx="{cx}" cy="{cy}" r="{r_outer}" fill="none" stroke="{male}" stroke-width="{w_outer}" stroke-linecap="round" stroke-dasharray="{dash_m}" />
      <circle cx="{cx}" cy="{cy}" r="{r_inner}" fill="none" stroke="{female}" stroke-width="{w_inner}" stroke-linecap="round" stroke-dasharray="{dash_f}" />
    </g>
  </svg>
</div>
"""

def render_detail_html(text: str) -> str:
    if not text: return ""
    lines = [ln.strip() for ln in str(text).splitlines()]
    cleaned = []
    for ln in lines:
        if ln == "" and (not cleaned or cleaned[-1] == ""): continue
        cleaned.append(ln)
    html, ul_open = [], False
    def open_ul():
        nonlocal ul_open
        if not ul_open: html.append("<ul style='margin:.25rem 0 .25rem 1.1rem;'>"); ul_open = True
    def close_ul():
        nonlocal ul_open
        if ul_open: html.append("</ul>"); ul_open = False
    for ln in cleaned:
        if re.match(r"^[-•·‣]\s*", ln):
            open_ul(); item = re.sub(r"^[-•·‣]\s*", "", ln); html.append(f"<li>{item}</li>")
        elif ln:
            close_ul(); html.append(f"<p style='margin:.2rem 0;'>{ln}</p>")
    close_ul()
    return "<div class='detail-box'>" + "".join(html) + "</div>"

# -------------------------------------------------
# 스타일 / CSS
# -------------------------------------------------
st.title("🎓 전공별 자격증 난이도·합격률 대시보드")
st.markdown("""
<style>
.detail-box{white-space:pre-wrap;line-height:1.7;background:#f8fbff;border:1px solid #e9ecef;border-radius:10px;padding:12px;margin:6px 0 16px 0;color:#111827;}
.pill{display:inline-block;padding:4px 10px;border-radius:999px;background:rgba(248,249,250,.95);border:1px solid #dee2e6;font-size:11px;color:#111827;margin-right:6px;margin-bottom:6px;}
.pill-row{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:2px;}
@media (max-width:480px){.pill{font-size:12px;padding:4px 12px;}}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# 데이터 경로 / 키
# -------------------------------------------------
CERT_PATHS    = ["1010자격증데이터_통합.xlsx", "data/data_cert.xlsx"]
MAJOR_PATHS   = ["1013전공정보통합_final.xlsx", "data/data_major.xlsx"]
JOBS_PATHS    = ["직무분류데이터_병합완_with_ID_v3.xlsx", "data/data_jobs.xlsx"]
JOBINFO_PATHS = ["직업정보_데이터.xlsx", "data/job_info.xlsx"]
NO_PASS_PATHS = ["합격률이 나오지 않는 자격증.xlsx", "data/no_pass.xlsx"]
# ★ NCS 직무 분류 파일 (CSV)
NCS_PATHS     = ["NCS직무상세분류_자격증_ID완전매핑.csv", "data/ncs_mapping.csv"]

YEARS  = [2022, 2023, 2024]
PHASES = ["1차","2차","3차"]
GRADE_LABELS = {100:"기술사(100)",200:"기능장(200)",300:"기사(300)",400:"산업기사(400)",500:"기능사(500)"}
NAME_COL, ID_COL, CLS_COL = "자격증명","자격증ID","자격증_분류"
GRADE_COL, GRADE_TYPE_COL = "자격증_등급_코드","등급_분류"
FREQ_COL, STRUCT_COL = "검정 횟수","시험종류"
W_COL, P_COL, I_COL = "필기","실기","면접"
JOB_ID_COL, JOB_SEQ_COL = "자격증ID","jobdicSeq"

PASS_RATE_COLS = {
    2022: {"1차":"2022년 1차 합격률","2차":"2022년 2차 합격률","3차":"2022년 3차 합격률"},
    2023: {"1차":"2023년 1차 합격률","2차":"2023년 2차 합격률","3차":"2023년 3차 합격률"},
    2024: {"1차":"2024년 1차 합격률","2차":"2024년 2차 합격률","3차":"2024년 3차 합격률"},
}
APPL_COLS = {
    2022: {"1차":"2022년 1차 응시자 수","2차":"2022년 2차 응시자수","3차":"2022년 3차 응시자수"},
    2023: {"1차":"2023년 1차 응시자 수","2차":"2023년 2차 응시자 수","3차":"2023년 3차 응시자 수"},
    2024: {"1차":"2024년 1차 응시자 수","2차":"2024년 2차 응시자 수","3차":"2024년 3차 응시자 수"},
}
num = lambda s: pd.to_numeric(s, errors="coerce")

# -------------------------------------------------
# 모바일 감지
# -------------------------------------------------
IS_MOBILE = (str(get_query_params().get("m","0")) == "1")
_force_light_theme()

# -------------------------------------------------
# 사이드바 (필터 + QR)
# -------------------------------------------------
with st.sidebar:
    st.header("전공 필터")
    selected_ids = None
    use_major = st.toggle("전공으로 필터", value=False)
    if "last_selected_major" not in st.session_state:
        st.session_state["last_selected_major"] = None

def render_qr_home():
    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(BASE_URL); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO(); img.save(buf, format="PNG")
    st.sidebar.image(buf.getvalue(), caption="앱 홈으로 연결", width=110)

# -------------------------------------------------
# 데이터 로드
# -------------------------------------------------
def read_first(paths):
    for p in paths:
        try:
            return pd.read_excel(p)
        except Exception:
            continue
    return None

def read_first_csv(paths):
    for p in paths:
        try:
            return pd.read_csv(p)              # utf-8 가정
        except Exception:
            try:
                return pd.read_csv(p, encoding="cp949")  # 한글 윈도우 폴백
            except Exception:
                continue
    return None

df = read_first(CERT_PATHS)
if df is None:
    st.error("자격증 엑셀을 찾지 못했습니다."); st.stop()

df_major   = read_first(MAJOR_PATHS)
df_jobs    = read_first(JOBS_PATHS)
df_jobinfo = read_first(JOBINFO_PATHS)
df_no      = read_first(NO_PASS_PATHS)
df_ncs     = read_first_csv(NCS_PATHS)

# 합격률 없음 목록 → 플래그
EXCLUDE_IDS, EXCLUDE_NAMES = set(), set()
if df_no is not None and not df_no.empty:
    cols = [str(c) for c in df_no.columns]
    id_col_guess = next((c for c in cols if "자격증ID" in c or c.lower() in ["id","license_id","cert_id"]), None)
    name_col_guess = next((c for c in cols if "자격증명" in c or "명" in c or c.lower() in ["name","license_name","cert_name"]), None)
    if id_col_guess and id_col_guess in df_no.columns:
        EXCLUDE_IDS = set(_to_key(df_no[id_col_guess]).dropna())
    if name_col_guess and name_col_guess in df_no.columns:
        EXCLUDE_NAMES = set(_to_key(df_no[name_col_guess]).dropna())

df["NO_PASS_DATA"] = (
    _to_key(df[ID_COL]).isin(EXCLUDE_IDS) |
    _to_key(df[NAME_COL]).isin(EXCLUDE_NAMES)
)

if df_jobs is not None:
    if JOB_ID_COL in df_jobs.columns:  df_jobs[JOB_ID_COL]  = _to_key(df_jobs[JOB_ID_COL])
    if JOB_SEQ_COL in df_jobs.columns: df_jobs[JOB_SEQ_COL] = _to_key(df_jobs[JOB_SEQ_COL])
if df_jobinfo is not None and JOB_SEQ_COL in df_jobinfo.columns:
    df_jobinfo[JOB_SEQ_COL] = _to_key(df_jobinfo[JOB_SEQ_COL])

def read_ncs(paths):
    for p in paths:
        try:
            if str(p).lower().endswith((".csv", ".txt")):
                return pd.read_csv(p, encoding="utf-8-sig")
            else:
                return pd.read_excel(p)
        except Exception:
            continue
    return None

df_ncs = read_ncs(NCS_PATHS)

# 컬럼 alias 고정
NCS_L_CODE, NCS_L_NAME = "대직무코드", "대직무분류"
NCS_M_CODE, NCS_M_NAME = "중직무코드", "중직무분류"
NCS_S_CODE, NCS_S_NAME = "소직무코드", "소직무분류"
NCS_LIC_ID              = "자격증ID"

if df_ncs is not None and not df_ncs.empty:
    # 문자열/숫자 혼재 방지: 이름은 문자열, 코드는 문자열로 통일(표시엔 이름만 씀)
    for c in [NCS_L_NAME, NCS_M_NAME, NCS_S_NAME, NCS_LIC_ID]:
        if c in df_ncs.columns:
            df_ncs[c] = df_ncs[c].astype(str).str.strip()
    for c in [NCS_L_CODE, NCS_M_CODE, NCS_S_CODE]:
        if c in df_ncs.columns:
            df_ncs[c] = pd.to_numeric(df_ncs[c], errors="coerce")

    # 옵션 리스트 생성용 중복 제거 (코드+이름 페어로 유일화)
    ncs_large_opts = (
        df_ncs[[NCS_L_CODE, NCS_L_NAME]]
        .dropna()
        .drop_duplicates()
        .sort_values([NCS_L_NAME, NCS_L_CODE], kind="stable")
    )
else:
    ncs_large_opts = pd.DataFrame(columns=[NCS_L_CODE, NCS_L_NAME])


# -------------------------------------------------
# 사이드바 계속 (전공 필터)
# -------------------------------------------------
with st.sidebar:
    if use_major:
        if df_major is None:
            st.error("전공 엑셀을 찾지 못했습니다.")
        else:
            major_name_col, major_id_col = "학과명","자격증ID"
            majors_all = sorted(df_major[major_name_col].astype(str).unique().tolist())

            def _on_major_query_change():
                st.session_state["major_select"] = "(선택)"

            qmaj = st.text_input(
                "전공 검색",
                value=st.session_state.get("maj_q",""),
                key="maj_q", placeholder="전공명을 입력하세요",
                on_change=_on_major_query_change
            )
            majors_view = [m for m in majors_all if (qmaj.strip()=="" or qmaj.lower() in m.lower())]
            sel_major = st.selectbox("학과명", ["(선택)"] + majors_view, index=0, key="major_select")

            if sel_major != st.session_state["last_selected_major"]:
                for k in ("selected_license","selected_job_seq","selected_job_title"):
                    st.session_state.pop(k, None)
                st.session_state["last_selected_major"] = sel_major

            if sel_major != "(선택)":
                selected_ids = (df_major.loc[df_major[major_name_col].astype(str)==sel_major, major_id_col]
                                    .astype(str).unique().tolist())

                rate_cols = ["취업률_전체","취업률_남","취업률_여"]
                if all(c in df_major.columns for c in rate_cols):
                    _row = (df_major.loc[df_major[major_name_col].astype(str)==sel_major, rate_cols]
                                    .apply(pd.to_numeric, errors="coerce").dropna(how="all"))
                    if not _row.empty:
                        r_all = float(_row.iloc[0]["취업률_전체"]) if pd.notna(_row.iloc[0]["취업률_전체"]) else np.nan
                        r_m   = float(_row.iloc[0]["취업률_남"])   if pd.notna(_row.iloc[0]["취업률_남"])   else np.nan
                        r_f   = float(_row.iloc[0]["취업률_여"])   if pd.notna(_row.iloc[0]["취업률_여"])   else np.nan
                        with st.container(border=True):
                            st.caption("전공 취업률"); st.markdown(f"**취업률(전체)** : {r_all:.1f}%  \n")
                            if pd.notna(r_m) or pd.notna(r_f):
                                st.markdown(render_employ_donut_svg(r_m, r_f), unsafe_allow_html=True)
                                st.markdown(
                                    f"""
                                    <div style="margin-top:-6px; line-height:1.6;">
                                      <div style="display:flex; align-items:center; gap:.5rem;">
                                        <span style="width:10px;height:10px;border-radius:50%;background:#2563eb;display:inline-block;"></span>
                                        <span style="color:#2563eb;font-weight:700;">남:</span>
                                        <span style="font-weight:700;color:#334155;">{r_m:.1f}%</span>
                                      </div>
                                      <div style="display:flex; align-items:center; gap:.5rem;">
                                        <span style="width:10px;height:10px;border-radius:50%;background:#ef4444;display:inline-block;"></span>
                                        <span style="color:#ef4444;font-weight:700;">여:</span>
                                        <span style="font-weight:700;color:#334155;">{r_f:.1f}%</span>
                                      </div>
                                    </div>
                                    """, unsafe_allow_html=True
                                )

    st.divider()
    st.header("검색 / 필터")
    q = st.text_input("자격증명 검색", value="")
    cls_all = sorted(df[CLS_COL].dropna().astype(str).unique().tolist())
    whitelist = [o for o in cls_all if any(k in o for k in ("국가기술","국가전문","국가민간"))]
    cls_options = whitelist if whitelist else cls_all
    sel_cls = st.selectbox("자격증 분류", options=["(전체)"]+cls_options, index=0, key="cls_single")

    # 등급코드 필터(국가기술일 때만)
    grade_nums = pd.to_numeric(df[GRADE_COL], errors="coerce")
    grade_buckets = [b for b in [100,200,300,400,500] if (grade_nums.round(-2)==b).any()]
    show_grade_filter = ("국가기술" in sel_cls)
    if show_grade_filter:
        sel_buckets = st.multiselect(
            "등급코드(100단위)",
            options=grade_buckets or [100,200,300,400,500],
            format_func=lambda x: GRADE_LABELS.get(x, str(x)),
            default=grade_buckets or [100,200,300,400,500]
        )
    else:
        sel_buckets = None
        st.caption("등급코드는 ‘국가기술자격’ 선택 시 활성화됩니다.")

    # 시험구성
    c1,c2,c3 = st.columns(3)
    want_w = c1.toggle("필기", value=False)
    want_p = c2.toggle("실기", value=False)
    want_i = c3.toggle("면접", value=False)

    # 난이도
    sel_lv  = st.multiselect("난이도 등급(1~5)", options=[1,2,3,4,5], default=[1,2,3,4,5])

    # ─────────────────────────────────────────────
    # ★ NCS 직무 필터 (대 → 중 → 소, 이름으로 표시)
    # ─────────────────────────────────────────────
    ncs_license_ids = None  # 이 집합이 나중에 결과 필터에 사용됨

    with st.container(border=True):
        st.caption("NCS 직무 필터")

        # 1) 대직무 (이름으로 노출)
        large_choices = ["(전체)"] + ncs_large_opts[NCS_L_NAME].tolist() if not ncs_large_opts.empty else ["(전체)"]
        sel_ncs_large = st.selectbox("대직무", large_choices, index=0, key="ncs_large_name")

        # 2) 중직무 (선택된 대직무의 하위만 이름으로)
        if df_ncs is not None and sel_ncs_large and sel_ncs_large != "(전체)":
            mid_df = (
                df_ncs.loc[df_ncs[NCS_L_NAME] == sel_ncs_large, [NCS_M_CODE, NCS_M_NAME]]
                .dropna()
                .drop_duplicates()
                .sort_values([NCS_M_NAME, NCS_M_CODE], kind="stable")
            )
            mid_choices = ["(전체)"] + mid_df[NCS_M_NAME].tolist()
        else:
            mid_df = pd.DataFrame(columns=[NCS_M_CODE, NCS_M_NAME])
            mid_choices = ["(전체)"]

        sel_ncs_mid = st.selectbox("중직무", mid_choices, index=0, key="ncs_mid_name")

        # 3) 소직무 (선택된 대/중 하위만 이름으로)
        if df_ncs is not None and sel_ncs_large != "(전체)" and sel_ncs_mid != "(전체)":
            small_df = (
                df_ncs.loc[
                    (df_ncs[NCS_L_NAME] == sel_ncs_large) &
                    (df_ncs[NCS_M_NAME] == sel_ncs_mid),
                    [NCS_S_CODE, NCS_S_NAME]
                ]
                .dropna()
                .drop_duplicates()
                .sort_values([NCS_S_NAME, NCS_S_CODE], kind="stable")
            )
            small_choices = ["(전체)"] + small_df[NCS_S_NAME].tolist()
        elif df_ncs is not None and sel_ncs_large != "(전체)":
            small_df = (
                df_ncs.loc[df_ncs[NCS_L_NAME] == sel_ncs_large, [NCS_S_CODE, NCS_S_NAME]]
                .dropna()
                .drop_duplicates()
                .sort_values([NCS_S_NAME, NCS_S_CODE], kind="stable")
            )
            small_choices = ["(전체)"] + small_df[NCS_S_NAME].tolist()
        else:
            small_df = pd.DataFrame(columns=[NCS_S_CODE, NCS_S_NAME])
            small_choices = ["(전체)"]

        sel_ncs_small = st.selectbox("소직무", small_choices, index=0, key="ncs_small_name")

    # 선택된 NCS 조합으로 자격증ID 집합 만들기 (소→중→대 우선)
    if df_ncs is not None:
        any_selected = (
            (sel_ncs_large and sel_ncs_large != "(전체)") or
            (sel_ncs_mid   and sel_ncs_mid   != "(전체)") or
            (sel_ncs_small and sel_ncs_small != "(전체)")
        )

        if any_selected:
            mask = pd.Series(True, index=df_ncs.index)
            if sel_ncs_large and sel_ncs_large != "(전체)":
                mask &= (df_ncs[NCS_L_NAME] == sel_ncs_large)
            if sel_ncs_mid and sel_ncs_mid != "(전체)":
                mask &= (df_ncs[NCS_M_NAME] == sel_ncs_mid)
            if sel_ncs_small and sel_ncs_small != "(전체)":
                mask &= (df_ncs[NCS_S_NAME] == sel_ncs_small)

            filtered_ncs = df_ncs.loc[mask]
            if not filtered_ncs.empty and (NCS_LIC_ID in filtered_ncs.columns):
                ncs_license_ids = set(_to_key(filtered_ncs[NCS_LIC_ID]).dropna())
    # ─────────────────────────────────────────────


    # 합격률 없는 자격증 토글
    def _on_toggle_no_pass():
        st.session_state.page = 1
        for k in ("selected_license","selected_job_seq","selected_job_title"):
            st.session_state.pop(k, None)

    show_only_no_pass = st.toggle(
        "합격률 없는 자격증만 보기",
        value=st.session_state.get("show_only_no_pass", False),
        key="show_only_no_pass",
        help="ON이면 합격률 데이터가 없는 자격증만 목록에 표시합니다.",
        on_change=_on_toggle_no_pass,
    )

    st.divider()
    render_qr_home()

# -------------------------------------------------
# 난이도/합격률 계산
# -------------------------------------------------
SCORING = {"trust_floor":0.5,"trust_span":0.5,"bonus_prac":0.15,"bonus_intv":0.10,
           "bonus_grade_max":0.20,"bonus_freq_max":0.10,"bonus_prof":0.20,"bonus_tech":0.10,"bonus_priv":0.00}

def class_bonus(label):
    s=str(label)
    if "전문" in s: return SCORING["bonus_prof"]
    if "기술" in s: return SCORING["bonus_tech"]
    if "민간" in s: return SCORING["bonus_priv"]
    return 0.0

def trust_weight(avg_app, all_avg_apps):
    if pd.notna(avg_app) and all_avg_apps.notna().any():
        norm = np.log1p(avg_app) / np.nanmax(np.log1p(all_avg_apps))
        return SCORING["trust_floor"] + SCORING["trust_span"] * float(norm)
    return 1.0

def grade_bonus(code):
    c = num(code)
    if pd.isna(c): return 0.0
    return max(0.0, min(1.0, (500.0 - float(c)) / 400.0)) * SCORING["bonus_grade_max"]

def freq_to_num(x):
    if x is None: return np.nan
    if isinstance(x,(int,float)) and not np.isnan(x): return float(x)
    s=str(x).strip()
    if s=="" or s.lower()=="nan": return np.nan
    if "상시" in s or "연중" in s: return 12.0
    if "수시" in s: return 6.0
    m=re.search(r"(\d+)", s)
    return float(m.group(1)) if m else np.nan

def freq_bonus(v, all_freq_series):
    f = pd.to_numeric(v, errors="coerce")
    if pd.isna(f) or all_freq_series.notna().sum()==0: return 0.0
    fmin, fmax = float(np.nanmin(all_freq_series)), float(np.nanmax(all_freq_series))
    if fmax==fmin: return 0.0
    return ((fmax - float(f)) / (fmax - fmin)) * SCORING["bonus_freq_max"]

def qcut_1to5(s:pd.Series)->pd.Series:
    s=s.replace([np.inf,-np.inf],np.nan); valid=s.dropna()
    if valid.nunique()>=5:
        try:
            bins=pd.qcut(valid,5,labels=[1,2,3,4,5]); out=pd.Series(index=s.index,dtype="float")
            out.loc[valid.index]=bins.astype(float); return out
        except Exception: pass
    mn=float(np.nanmin(valid)) if len(valid) else 0.0
    mx=float(np.nanmax(valid)) if len(valid) else 1.0
    def band(x):
        if pd.isna(x): return np.nan
        if mx==mn: return 3.0
        r=(x-mn)/(mx-mn+1e-12); return float(np.clip(np.floor(r*5)+1,1,5))
    return s.apply(band)

# 평균 합격률/응시자수
for ph in PHASES:
    cols = [PASS_RATE_COLS[y][ph] for y in YEARS if PASS_RATE_COLS[y][ph] in df.columns]
    df[f"PASS_{ph}_AVG(22-24)"] = df[cols].apply(num).mean(axis=1, skipna=True) if cols else np.nan
df["OVERALL_PASS(%)"] = df[[f"PASS_{ph}_AVG(22-24)" for ph in PHASES]].mean(axis=1, skipna=True)
app_cols = [APPL_COLS[y][ph] for y in YEARS for ph in PHASES if APPL_COLS[y][ph] in df.columns]
df["APPLICANTS_AVG"] = df[app_cols].apply(num).mean(axis=1, skipna=True) if app_cols else np.nan

# 구조 파싱
def parse_structure(r):
    t=str(r.get(STRUCT_COL,"") or "")
    has_w=("필기" in t) or (num(r.get(W_COL,0))>0)
    has_p=("실기" in t) or (num(r.get(P_COL,0))>0)
    has_i=("면접" in t) or (num(r.get(I_COL,0))>0)
    txt="+".join([x for x,b in (("필기",has_w),("실기",has_p),("면접",has_i)) if b])
    return has_w,has_p,has_i,txt
df[["HAS_W","HAS_P","HAS_I","STRUCT_TXT"]] = df.apply(parse_structure, axis=1, result_type="expand")

# 점수 계산
freq_numeric = df[FREQ_COL].apply(freq_to_num) if FREQ_COL in df.columns else pd.Series([np.nan]*len(df))
inv_overall  = (100.0 - df["OVERALL_PASS(%)"]) / 100.0
trust_w      = df["APPLICANTS_AVG"].apply(lambda a: trust_weight(a, df["APPLICANTS_AVG"]))
bonus_freq   = freq_numeric.apply(lambda v: freq_bonus(v, freq_numeric))
df["DIFF_SCORE_RAW"] = (
    inv_overall.fillna(0)*trust_w
    + df[CLS_COL].apply(class_bonus).fillna(0.0)
    + df[GRADE_COL].apply(grade_bonus).fillna(0.0)
    + bonus_freq.fillna(0.0)
    + df.apply(lambda r: (SCORING["bonus_prac"] if r["HAS_P"] else 0.0)
                         + (SCORING["bonus_intv"] if r["HAS_I"] else 0.0), axis=1)
)

# 난이도 등급: 합격률 없음 제외한 표본으로만 등분
valid_mask = ~df["NO_PASS_DATA"]
levels = qcut_1to5(df.loc[valid_mask, "DIFF_SCORE_RAW"])
df["DIFF_LEVEL(1-5)"] = np.nan
df.loc[valid_mask, "DIFF_LEVEL(1-5)"] = levels
df["DIFF_SCORE"] = df["DIFF_SCORE_RAW"]
df.loc[~valid_mask, "DIFF_SCORE"] = np.nan
df.drop(columns=["DIFF_SCORE_RAW"], inplace=True)

# -------------------------------------------------
# 차트(절반 크기)
# -------------------------------------------------
BASE_CHART_W, BASE_CHART_H = (3.2, 1.6)
LINE_W, MARKER_S  = 1.8, 5.0
TITLE_FSIZE, TICK_FSIZE, LABEL_FSIZE = 12, 9, 10

def plot_yearly_pass_rates(row: pd.Series, lic_name: str):
    years = [y for y in YEARS if all(PASS_RATE_COLS[y][ph] in df.columns for ph in PHASES)]
    if not years: return
    x = np.arange(len(years))
    fig, ax = plt.subplots(figsize=(BASE_CHART_W, BASE_CHART_H), dpi=160)
    for ph, label in zip(PHASES, ["1차","2차","3차"]):
        y = [pd.to_numeric(row.get(PASS_RATE_COLS[y][ph]), errors="coerce") for y in years]
        yv = [float(v) if pd.notna(v) else np.nan for v in y]
        ax.plot(x, yv, marker="o", linewidth=LINE_W, markersize=MARKER_S, label=label, solid_capstyle="round")
    ax.set_xticks(x); ax.set_xticklabels([str(y) for y in years])
    ax.set_ylim(0, 100); ax.set_yticks(np.arange(0, 101, 20))
    ax.tick_params(axis="both", labelsize=TICK_FSIZE)
    ax.set_ylabel("합격률(%)", fontsize=LABEL_FSIZE, labelpad=3)
    ax.set_title(f"{lic_name} · 연도별 합격률 (1·2·3차)", pad=4, fontsize=TITLE_FSIZE, fontweight="bold")
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0.02, 1.02), frameon=False, fontsize=9, handlelength=2.0, columnspacing=1.0)
    ax.grid(True, which="major", linestyle="--", alpha=.35); hide_spines(ax)
    fig.tight_layout(pad=0.4)
    _, mid, _ = st.columns([1,2,1])
    with mid: st.pyplot(fig, use_container_width=True)
    def _row_txt(part: str):
        chunks = []
        for y in years:
            v = pd.to_numeric(row.get(PASS_RATE_COLS[y][part]), errors="coerce")
            chunks.append(f"{y}년 {part} 합격률 : {v:.1f}%" if pd.notna(v) else f"{y}년 {part} 합격률 : -")
        return " · ".join(chunks)
    centered_html = """
        <div style="font-size:12px; line-height:1.55; color:#334155; margin:6px 0 0; text-align:center;">
            <div style="margin-bottom:2px;">{r1}</div>
            <div style="margin-bottom:2px;">{r2}</div>
            <div>{r3}</div>
        </div>
    """.format(r1=_row_txt("1차"), r2=_row_txt("2차"), r3=_row_txt("3차"))
    with mid: st.markdown(centered_html, unsafe_allow_html=True)

# -------------------------------------------------
# 필터 적용 + 결과 목록
# -------------------------------------------------
page_size = 6
if st.session_state.get("page") is None:
    st.session_state.page = 1

# 합격률 없는 자격증 모드
show_only_no_pass = st.session_state.get("show_only_no_pass", False)

# 결과 집합(합/무에 따라 분기)
if show_only_no_pass:
    f = df[df["NO_PASS_DATA"]].copy()
else:
    f = df[~df["NO_PASS_DATA"]].copy()

# 공통 필터
if selected_ids: f = f[f[ID_COL].astype(str).isin([str(x) for x in selected_ids])]
if q:            f = f[f[NAME_COL].astype(str).str.contains(q, case=False, na=False)]
if sel_cls != "(전체)": f = f[f[CLS_COL].astype(str) == sel_cls]
if sel_buckets is not None: f = f[pd.to_numeric(f[GRADE_COL], errors="coerce").round(-2).isin(sel_buckets)]
if want_w: f = f[f["HAS_W"]==True]
if want_p: f = f[f["HAS_P"]==True]
if want_i: f = f[f["HAS_I"]==True]

# NCS 선택이 있을 때만 교집합 (전체,전체,전체이면 None이므로 패스)
if ncs_license_ids is not None:
    f = f[_to_key(f[ID_COL]).isin(ncs_license_ids)]



# 정렬/난이도 필터
if not show_only_no_pass:
    f = f[f["DIFF_LEVEL(1-5)"].isin(sel_lv)]
    f = f.sort_values(["DIFF_SCORE","OVERALL_PASS(%)"], ascending=[False, True])
else:
    f = f.sort_values([NAME_COL])  # 보기 편하게 이름순

total = len(f)
max_pages = max(1, int(np.ceil(total / page_size)))
st.session_state.page = int(np.clip(st.session_state.get("page",1), 1, max_pages))
page = st.session_state.page
start, end = (page-1)*page_size, (page-1)*page_size + page_size
page_df = f.iloc[start:end]

mode_txt = " (합격률 없는 자격증)" if show_only_no_pass else ""
st.markdown(f"#### 결과: {total:,}건 (페이지 {page}/{max_pages}){mode_txt}")
if not show_only_no_pass:
    st.caption("정렬: 난이도 점수 내림차순 → 합격률 오름차순")

# 모바일이면 1열, 아니면 3열
ncol = 1 if IS_MOBILE else 3

def license_card(row):
    title, rid = str(row[NAME_COL]), str(row[ID_COL])
    cls = str(row.get(CLS_COL, "")); grade = row.get(GRADE_COL, "")
    freq_disp = row.get(FREQ_COL, ""); struct = row.get("STRUCT_TXT", "")
    diff_lv = row.get("DIFF_LEVEL(1-5)", np.nan); diff_sc = row.get("DIFF_SCORE", np.nan)
    apps = row.get("APPLICANTS_AVG", np.nan)
    with st.container(border=True):
        st.markdown(f"##### {title}  <small style='color:#868e96'>[{rid}]</small>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class='pill-row'>{badge(f"분류: {cls}")}{badge(f"등급코드: {grade}")}</div>
        <div class='pill-row'>{badge(f"검정횟수: {freq_disp}")}{badge(f"구조: {struct}")}</div>
        """, unsafe_allow_html=True)
        c1,c2,c3 = st.columns(3)
        with c1:
            if pd.notna(diff_lv):
                st.metric("난이도 등급", f"{int(diff_lv)} / 5", help=(f"점수 {diff_sc:.3f}" if pd.notna(diff_sc) else None))
            else:
                st.metric("난이도 등급", "-", help="합격률 데이터가 없어 난이도 등분에서 제외되었습니다.")
        with c2: st.metric("평균 응시자수", fmt_int(apps))
        with c3:
            ov = row.get("OVERALL_PASS(%)", np.nan)
            st.metric("전체 합격률(평균)", f"{ov:.1f}%" if pd.notna(ov) else "-")
        p1,p2,p3 = st.columns(3)
        with p1: v=row.get("PASS_1차_AVG(22-24)", np.nan); st.metric("1차 합격률(3년평균)", f"{v:.1f}%" if pd.notna(v) else "-")
        with p2: v=row.get("PASS_2차_AVG(22-24)", np.nan); st.metric("2차 합격률(3년평균)", f"{v:.1f}%" if pd.notna(v) else "-")
        with p3: v=row.get("PASS_3차_AVG(22-24)", np.nan); st.metric("3차 합격률(3년평균)", f"{v:.1f}%" if pd.notna(v) else "-")
        if (df_jobs is not None) and (JOB_ID_COL in df_jobs.columns):
            if st.button("관련 직무 보기", key=f"jobbtn_{rid}", use_container_width=True):
                st.session_state["selected_license"] = rid
                st.session_state.pop("selected_job_seq", None)
                st.session_state.pop("selected_job_title", None)
                st.session_state["_scroll_to_top"] = True

rows = list(page_df.to_dict(orient="records"))
if not rows:
    st.info("조건에 맞는 결과가 없습니다. 필터를 조정해 보세요.")
else:
    for i in range(0, len(rows), ncol):
        cols = st.columns(ncol)
        for j in range(ncol):
            if i+j < len(rows):
                with cols[j]:
                    license_card(rows[i+j])

# -------------------------------------------------
# 선택된 자격증 상세(그래프 + 직무 + 직업정보)
# -------------------------------------------------
sel_license = st.session_state.get("selected_license")

if sel_license is not None:
    lic_row = df[df[ID_COL].astype(str) == str(sel_license)]
    if not lic_row.empty:
        st.subheader("합격률")
        with st.container(border=True):
            plot_yearly_pass_rates(lic_row.iloc[0], lic_row.iloc[0][NAME_COL])

if df_jobs is not None and (JOB_ID_COL in df_jobs.columns) and sel_license:
    mask = df_jobs[JOB_ID_COL].astype(str).str.strip() == str(sel_license).strip()
    jobs = df_jobs.loc[mask].copy()
    st.subheader("관련 직무")
    if jobs.empty:
        st.info("연결된 직무 데이터가 없습니다.")
    else:
        if "학과명" in jobs.columns:
            jobs = (jobs.assign(학과명=jobs["학과명"].astype(str).str.strip())
                         .groupby([JOB_SEQ_COL,"직업명"], as_index=False)["학과명"]
                         .agg(lambda s: ", ".join(pd.Series(s).dropna().unique())))
        ncol2 = 2
        job_rows = list(jobs.to_dict(orient="records"))
        for i in range(0, len(job_rows), ncol2):
            cols = st.columns(ncol2)
            for j in range(ncol2):
                if i+j >= len(job_rows): break
                jr = job_rows[i+j]
                seq   = str(jr.get(JOB_SEQ_COL, "")).strip()
                title = str(jr.get("직업명", "(직업명 미상)"))
                major = str(jr.get("학과명", "")).strip()
                with cols[j]:
                    with st.container(border=True):
                        st.markdown(f"**{title}**  <small style='color:#868e96'>[{seq}]</small>", unsafe_allow_html=True)
                        if major: st.caption(f"관련 학과: {major}")
                        if st.button("상세 정보", key=f"jobinfo_btn__{sel_license}__{seq}", use_container_width=True):
                            st.session_state["selected_job_seq"]   = seq
                            st.session_state["selected_job_title"] = title
                            st.session_state["_scroll_to_top"] = True

sel_job = st.session_state.get("selected_job_seq")
if sel_license is not None:
    st.divider(); st.subheader("직업 상세 정보")
    if (sel_job is None) or (df_jobinfo is None) or (JOB_SEQ_COL not in (df_jobinfo.columns if df_jobinfo is not None else [])):
        st.info("상세 보기를 선택하면 이곳에 표시됩니다.")
    else:
        detail = df_jobinfo[df_jobinfo[JOB_SEQ_COL] == str(sel_job).strip()]
        if detail.empty:
            st.warning("직업정보 데이터가 없습니다(키 불일치).")
        else:
            r = detail.iloc[0].astype(str).str.strip().to_dict()
            title = st.session_state.get("selected_job_title") or r.get("직업명","")
            with st.container(border=True):
                st.markdown(f"### {title}  <small style='color:#868e96'>[{str(sel_job).strip()}]</small>", unsafe_allow_html=True)
                score_keys = ["보상","고용안정","발전가능성","근무여건","직업전문성","고용평등"]
                cols = st.columns(3); k=0
                for sk in score_keys:
                    val = r.get(sk,"")
                    if val and val.lower() not in ["nan","none"]:
                        with cols[k%3]: st.metric(sk, val); k+=1

                radar_keys = ["보상","고용안정","발전가능성","근무여건","직업전문성","고용평등"]
                radar_vals = [_num_in_text(r.get(k,"")) for k in radar_keys]
                if any(pd.notna(v) for v in radar_vals):
                    vals = [0.0 if pd.isna(v) else float(v) for v in radar_vals]
                    angles = np.linspace(0, 2*np.pi, len(vals), endpoint=False)
                    _, mid, _ = st.columns([1,2,1])
                    with mid:
                        fig = plt.figure(figsize=(5.2,5.2))
                        ax = plt.subplot(111, polar=True)
                        ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
                        angles_c = np.concatenate([angles, angles[:1]])
                        vals_c   = np.concatenate([vals,   vals[:1]])
                        ax.plot(angles_c, vals_c, linewidth=2.4); ax.fill(angles_c, vals_c, alpha=0.12)
                        ax.set_thetagrids(np.degrees(angles), radar_keys)
                        ax.set_ylim(0,100); ax.set_rgrids([20,40,60,80,100], angle=90, fontsize=9)
                        ax.set_title("직업 지표 레이더", pad=12)
                        ax.grid(True, linestyle="--", alpha=0.35); ax.spines["polar"].set_linewidth(0.9)
                        for ang, val in zip(angles, vals):
                            ax.annotate(f"{val:.0f}", (ang, val), textcoords="offset points", xytext=(0,6), ha="center")
                        fig.tight_layout(); st.pyplot(fig, use_container_width=True)

                st.divider()
                sections=[("직업전망요약","직업전망요약"),("취업방법","취업방법"),("준비과정","준비과정"),
                          ("교육과정","교육과정"),("적성","적성"),("고용형태","고용형태"),
                          ("고용분류","고용분류"),("표준분류","표준분류"),("직무구분","직무구분"),
                          ("초임","초임"),("유사직업명","유사직업명")]
                for key,label in sections:
                    val=(r.get(key) or "").strip()
                    if not val or val.lower() in ["nan","none"]: continue
                    st.markdown(f"**{label}**"); st.markdown(render_detail_html(val), unsafe_allow_html=True)

                c1,c2 = st.columns([1,1])
                with c1:
                    if st.button("상세 보기 닫기", key="close_jobinfo", use_container_width=True):
                        st.session_state.pop("selected_job_seq", None)
                        st.session_state.pop("selected_job_title", None)
                        st.session_state["_scroll_to_top"] = True
                        _safe_rerun()
                with c2:
                    if st.button("관련 직무 선택 해제", key="clear_jobs", use_container_width=True):
                        st.session_state.pop("selected_license", None)
                        st.session_state.pop("selected_job_seq", None)
                        st.session_state.pop("selected_job_title", None)
                        st.session_state["_scroll_to_top"] = True
                        _safe_rerun()

# -------------------------------------------------
# 페이지네이션 + 스크롤-투-탑
# -------------------------------------------------
def _sync_page_from_input():
    st.session_state.page = int(st.session_state.page_input)
    for k in ("selected_license","selected_job_seq","selected_job_title"):
        st.session_state.pop(k, None)
    st.session_state["_scroll_to_top"] = True
    _emit_scroll_to_top_if_needed()

def _prev_page():
    st.session_state.page = max(1, st.session_state.page - 1)
    for k in ("selected_license","selected_job_seq","selected_job_title"):
        st.session_state.pop(k, None)
    st.session_state["_scroll_to_top"] = True
    _emit_scroll_to_top_if_needed()

def _next_page():
    st.session_state.page = min(max_pages, st.session_state.page + 1)
    for k in ("selected_license","selected_job_seq","selected_job_title"):
        st.session_state.pop(k, None)
    st.session_state["_scroll_to_top"] = True
    _emit_scroll_to_top_if_needed()

st.session_state.setdefault("page_input", st.session_state.page)
st.session_state.page_input = st.session_state.page

c_prev, c_info, c_next = st.columns([1,2,1])
with c_prev:
    st.button("◀ 이전", use_container_width=True,
              disabled=(st.session_state.page <= 1), on_click=_prev_page)
with c_info:
    st.number_input("페이지", min_value=1, max_value=max_pages, step=1,
                    key="page_input", on_change=_sync_page_from_input)
with c_next:
    st.button("다음 ▶", use_container_width=True,
              disabled=(st.session_state.page >= max_pages), on_click=_next_page)

_emit_scroll_to_top_if_needed()

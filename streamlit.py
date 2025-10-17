# -*- coding: utf-8 -*-
# 전공별 자격증 대시보드 — 내부 난이도 계산 + 하단 페이지네이션
# '국가기술자격' 선택 시에만 등급코드 필터 노출
# 라이선스 카드 → [관련 직무 보기] → 직무 카드 목록(학과명 표시) → [상세 정보] → 직업정보 상세 패널

import re
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from matplotlib.patches import Wedge, Circle


# ── Matplotlib 한글 + 공통 스타일 ─────────────────────────
from matplotlib import font_manager, rcParams

def use_korean_font():
    candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR", "DejaVu Sans"]
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

from matplotlib.patches import Wedge, Circle
import numpy as np

def draw_dual_ring(ax, male_pct, female_pct,
                   start_angle: float = 90,      # 12시
                   clockwise: bool = True,
                   show_start_tick: bool = True,
                   inside_labels: bool = False):

    def _clamp(x):
        try: x = float(x)
        except Exception: x = 0.0
        return max(0.0, min(100.0, x))

    m = _clamp(male_pct); f = _clamp(female_pct)

    r_outer, w_outer = 1.05, 0.18   # 남(바깥)
    r_inner, w_inner = 0.75, 0.18   # 여(안쪽)
    c_male, c_female, c_track = "#2563eb", "#ef4444", "#e5e7eb"

    # ✅ 방향/길이 수정: 시계방향이면 [start - span → start] 로 그린다
    def _arc(r, w, pct, color, z=1):
        span = 360.0 * pct / 100.0
        if clockwise:
            t1, t2 = start_angle - span, start_angle
        else:
            t1, t2 = start_angle, start_angle + span
        ax.add_patch(Wedge((0,0), r, t1, t2, width=w,
                           facecolor=color, edgecolor="none", zorder=z))

    # 트랙
    _arc(r_outer, w_outer, 100, c_track, z=0)
    _arc(r_inner, w_inner, 100, c_track, z=0)

    # 값
    _arc(r_outer, w_outer, m, c_male, z=2)     # 남(파랑)
    _arc(r_inner, w_inner, f, c_female, z=2)   # 여(빨강)

    # 중앙 구멍
    ax.add_patch(Circle((0,0), r_inner-0.22, facecolor="white", edgecolor="none", zorder=3))

    # 시작 틱
    if show_start_tick:
        th = np.deg2rad(start_angle)
        def _tick(r, w, color):
            x0, y0 = (r - w - 0.01) * np.cos(th), (r - w - 0.01) * np.sin(th)
            x1, y1 = (r + 0.01)     * np.cos(th), (r + 0.01)     * np.sin(th)
            ax.plot([x0, x1], [y0, y1], color=color, linewidth=2.4, solid_capstyle="round", zorder=4)
        _tick(r_outer, w_outer, c_male)
        _tick(r_inner, w_inner, c_female)

    ax.set_xlim(-1.35, 1.35); ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal"); ax.axis("off")


def hide_spines(ax):
    for s in ["top", "right"]:
        if s in ax.spines: ax.spines[s].set_visible(False)

def _clear_related_selections():
    # 관련 직무/자격증/상세 선택 상태 초기화
    st.session_state.pop("selected_license", None)
    st.session_state.pop("selected_job_seq", None)
    st.session_state.pop("selected_job_title", None)
    # 페이지도 처음으로
    st.session_state.page = 1




use_korean_font()
apply_pretty_style()


# ───────────────── 기본 ─────────────────
st.set_page_config(page_title="전공별 자격증 대시보드", layout="wide", page_icon="🎓")
st.title("🎓 전공별 자격증 난이도·합격률 대시보드")

st.markdown("""
<style>
.detail-box{
  white-space:pre-wrap; line-height:1.7;
  background:#f8fbff; border:1px solid #e9ecef; border-radius:10px;
  padding:12px; margin:6px 0 16px 0;
  color:#111827;
}
/* ⬇ 배지(라벨) 공통 스타일 — 모바일/다크모드에서도 선명하게 보이도록 */
.pill{
  display:inline-block;
  padding:4px 10px;
  border-radius:999px;
  background:rgba(248,249,250,.95);
  border:1px solid #dee2e6;
  font-size:11px;
  color:#111827;   /* 다크모드에서도 글자색 유지 */
  margin-right:6px;
  margin-bottom:6px;
}
.pill-row{
  display:flex;
  flex-wrap:wrap;
  gap:6px;
  margin-bottom:2px;
}
@media (max-width:480px){
  .pill{ font-size:12px; padding:4px 12px; }  /* 모바일 가독성 */
}
</style>
""", unsafe_allow_html=True)




CERT_PATHS  = ["1010자격증데이터_통합.xlsx", "data/data_cert.xlsx"]
MAJOR_PATHS = ["1013전공정보통합_final.xlsx", "data/data_major.xlsx"]
JOBS_PATHS  = ["직무분류데이터_병합완_with_ID_v3.xlsx", "data/data_jobs.xlsx"]     # 자격증ID ↔ jobdicSeq 매핑
JOBINFO_PATHS = ["직업정보_데이터.xlsx", "data/job_info.xlsx"]                     # jobdicSeq 상세 정보

YEARS  = [2022, 2023, 2024]
PHASES = ["1차", "2차", "3차"]
GRADE_LABELS = {100:"기술사(100)", 200:"기능장(200)", 300:"기사(300)", 400:"산업기사(400)", 500:"기능사(500)"}

# 난이도 가중치
SCORING = {
    "trust_floor":0.5, "trust_span":0.5,   # 응시자수 신뢰가중
    "bonus_prac":0.15, "bonus_intv":0.10,  # 구조 가산
    "bonus_grade_max":0.20,                # (500-등급)/400 × max
    "bonus_freq_max":0.10,                 # 검정횟수(적을수록 +)
    "bonus_prof":0.20, "bonus_tech":0.10, "bonus_priv":0.00  # 분류 가산
}

# ──────────────── 데이터 로드 ────────────────
def read_first(paths):
    for p in paths:
        try:
            return pd.read_excel(p)
        except Exception:
            continue
    return None

df        = read_first(CERT_PATHS)
df_major  = read_first(MAJOR_PATHS)
df_jobs   = read_first(JOBS_PATHS)
df_jobinfo= read_first(JOBINFO_PATHS)

if df is None:
    st.error("자격증 엑셀을 찾지 못했습니다.")
    st.stop()

# 공통 키
NAME_COL, ID_COL, CLS_COL = "자격증명", "자격증ID", "자격증_분류"
GRADE_COL, GRADE_TYPE_COL = "자격증_등급_코드", "등급_분류"
FREQ_COL, STRUCT_COL      = "검정 횟수", "시험종류"
W_COL, P_COL, I_COL       = "필기", "실기", "면접"

# 직무/직업 정보 키 정규화
# ── 키 정규화(문자열 + strip) ─────────────────────────
JOB_ID_COL  = "자격증ID"
JOB_SEQ_COL = "jobdicSeq"

def _to_key(series):
    return pd.Series(series, dtype="object").astype(str).str.strip()

if df_jobs is not None:
    if JOB_ID_COL  in df_jobs.columns:
        df_jobs[JOB_ID_COL] = _to_key(df_jobs[JOB_ID_COL])
    if JOB_SEQ_COL in df_jobs.columns:
        df_jobs[JOB_SEQ_COL] = _to_key(df_jobs[JOB_SEQ_COL])

if df_jobinfo is not None and JOB_SEQ_COL in df_jobinfo.columns:
    df_jobinfo[JOB_SEQ_COL] = _to_key(df_jobinfo[JOB_SEQ_COL])

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

def class_bonus(label:str)->float:
    s=str(label)
    if "전문" in s: return SCORING["bonus_prof"]
    if "기술" in s: return SCORING["bonus_tech"]
    if "민간" in s: return SCORING["bonus_priv"]
    return 0.0

def trust_weight(avg_app, all_avg_apps)->float:
    if pd.notna(avg_app) and all_avg_apps.notna().any():
        norm = np.log1p(avg_app) / np.nanmax(np.log1p(all_avg_apps))
        return SCORING["trust_floor"] + SCORING["trust_span"] * float(norm)
    return 1.0

def grade_bonus(code)->float:
    c = num(code)
    if pd.isna(c): return 0.0
    return max(0.0, min(1.0, (500.0 - float(c)) / 400.0)) * SCORING["bonus_grade_max"]

# “상시/수시” 등 텍스트 → 계산용 숫자(표시는 원문 그대로)
def freq_to_num(x):
    if x is None: return np.nan
    if isinstance(x, (int, float)) and not np.isnan(x): return float(x)
    s = str(x).strip()
    if s == "" or s.lower() == "nan": return np.nan
    # 합리적 기본값: 상시=12회/년, 수시=6회/년, 연중=12회
    if "상시" in s: return 12.0
    if "수시" in s: return 6.0
    if "연중" in s: return 12.0
    m = re.search(r"(\d+)", s)
    return float(m.group(1)) if m else np.nan

def freq_bonus(v, all_freq_series)->float:
    f = pd.to_numeric(v, errors="coerce")
    if pd.isna(f) or all_freq_series.notna().sum()==0: return 0.0
    fmin, fmax = float(np.nanmin(all_freq_series)), float(np.nanmax(all_freq_series))
    if fmax == fmin: return 0.0
    # 횟수 적을수록 어려움 보정(+)
    return ((fmax - float(f)) / (fmax - fmin)) * SCORING["bonus_freq_max"]

def qcut_1to5(s:pd.Series)->pd.Series:
    s = s.replace([np.inf, -np.inf], np.nan)
    valid = s.dropna()
    if valid.nunique() >= 5:
        try:
            bins = pd.qcut(valid, 5, labels=[1,2,3,4,5])
            out = pd.Series(index=s.index, dtype="float")
            out.loc[valid.index] = bins.astype(float)
            return out
        except Exception:
            pass
    mn = float(np.nanmin(valid)) if len(valid) else 0.0
    mx = float(np.nanmax(valid)) if len(valid) else 1.0
    def band(x):
        if pd.isna(x): return np.nan
        if mx == mn:   return 3.0
        r=(x-mn)/(mx-mn+1e-12)
        return float(np.clip(np.floor(r*5)+1,1,5))
    return s.apply(band)

def fmt_int(x):
    if pd.isna(x): return "-"
    try: return f"{int(round(float(x))):,}"
    except Exception: return "-"

def badge(t):
    return f"<span class='pill'>{t}</span>"

def _num_in_text(x):
    s = "" if x is None else str(x)
    m = re.search(r"[-+]?\d*\.?\d+", s)  # 문자열 속 첫 숫자만 추출
    return float(m.group(0)) if m else np.nan

def _clear_job_selection_only():
    # 페이지는 유지하고, 선택 상태만 리셋
    for k in ("selected_license", "selected_job_seq", "selected_job_title"):
        st.session_state.pop(k, None)



# ─────────── 합격률/응시자 계산 ───────────
for ph in PHASES:
    cols = [PASS_RATE_COLS[y][ph] for y in YEARS if PASS_RATE_COLS[y][ph] in df.columns]
    df[f"PASS_{ph}_AVG(22-24)"] = df[cols].apply(num).mean(axis=1, skipna=True) if cols else np.nan

df["OVERALL_PASS(%)"] = df[[f"PASS_{ph}_AVG(22-24)" for ph in PHASES]].mean(axis=1, skipna=True)

app_cols = [APPL_COLS[y][ph] for y in YEARS for ph in PHASES if APPL_COLS[y][ph] in df.columns]
df["APPLICANTS_AVG"] = df[app_cols].apply(num).mean(axis=1, skipna=True) if app_cols else np.nan

# 구조 플래그/텍스트
def parse_structure(r):
    t = str(r.get(STRUCT_COL, "") or "")
    has_w = ("필기" in t) or (num(r.get(W_COL, 0)) > 0)
    has_p = ("실기" in t) or (num(r.get(P_COL, 0)) > 0)
    has_i = ("면접" in t) or (num(r.get(I_COL, 0)) > 0)
    txt   = "+".join([x for x,b in (("필기",has_w),("실기",has_p),("면접",has_i)) if b])
    return has_w, has_p, has_i, txt

df[["HAS_W","HAS_P","HAS_I","STRUCT_TXT"]] = df.apply(parse_structure, axis=1, result_type="expand")

# ─────────── 난이도(내부 계산) ───────────
# 검정횟수: 표시용은 원문, 계산용은 숫자화
freq_numeric = df[FREQ_COL].apply(freq_to_num) if FREQ_COL in df.columns else pd.Series([np.nan]*len(df))
inv_overall  = (100.0 - df["OVERALL_PASS(%)"]) / 100.0
trust_w      = df["APPLICANTS_AVG"].apply(lambda a: trust_weight(a, df["APPLICANTS_AVG"]))
bonus_freq   = freq_numeric.apply(lambda v: freq_bonus(v, freq_numeric))
score = (inv_overall.fillna(0)*trust_w
         + df[CLS_COL].apply(class_bonus).fillna(0.0)
         + df[GRADE_COL].apply(grade_bonus).fillna(0.0)
         + bonus_freq.fillna(0.0)
         + df.apply(lambda r: (SCORING["bonus_prac"] if r["HAS_P"] else 0.0)
                              + (SCORING["bonus_intv"] if r["HAS_I"] else 0.0), axis=1))
df["DIFF_SCORE"]      = score
df["DIFF_LEVEL(1-5)"] = qcut_1to5(df["DIFF_SCORE"])

# 등급코드 후보(100단위)
grade_nums     = pd.to_numeric(df[GRADE_COL], errors="coerce")
grade_buckets  = [b for b in [100,200,300,400,500] if (grade_nums.round(-2)==b).any()]

# ───────── 사이드바 ─────────
with st.sidebar:
    st.header("전공 필터")
    use_major     = st.toggle("전공으로 필터", value=False)
    selected_ids  = None

    # 이전에 선택한 학과 기억용
    if "last_selected_major" not in st.session_state:
        st.session_state["last_selected_major"] = None

    if use_major:
        if df_major is None:
            st.error("전공 엑셀을 찾지 못했습니다.")
        else:
            major_name_col, major_id_col = "학과명", "자격증ID"
            majors_all = sorted(df_major[major_name_col].astype(str).unique().tolist())
            qmaj       = st.text_input("전공 검색", value="")
            majors_view= [m for m in majors_all if qmaj.strip()=="" or qmaj.lower() in m.lower()]
             # 학과 선택
            sel_major = st.selectbox("학과명", ["(선택)"]+majors_view, index=0, key="major_select")

            # 학과가 바뀌면 관련 선택 상태 초기화
            if sel_major != st.session_state["last_selected_major"]:
                _clear_related_selections()
                st.session_state["last_selected_major"] = sel_major
                # if hasattr(st, "rerun"): st.rerun()
            if sel_major != "(선택)":
                selected_ids = (
                    df_major.loc[df_major[major_name_col].astype(str)==sel_major, major_id_col]
                           .astype(str).unique().tolist()
                )

                # 선택한 전공의 취업률 표시 + 도넛 차트
                rate_cols = ["취업률_전체", "취업률_남", "취업률_여"]
                if all(c in df_major.columns for c in rate_cols):
                    _row = (
                        df_major.loc[df_major[major_name_col].astype(str)==sel_major, rate_cols]
                                .apply(pd.to_numeric, errors="coerce")
                                .dropna(how="all")
                    )
                    if not _row.empty:
                        r_all = float(_row.iloc[0]["취업률_전체"]) if pd.notna(_row.iloc[0]["취업률_전체"]) else np.nan
                        r_m   = float(_row.iloc[0]["취업률_남"])   if pd.notna(_row.iloc[0]["취업률_남"])   else np.nan
                        r_f   = float(_row.iloc[0]["취업률_여"])   if pd.notna(_row.iloc[0]["취업률_여"])   else np.nan

                        with st.container(border=True):
                            st.caption("전공 취업률")
                            st.markdown(
                                f"**취업률(전체)** : {r_all:.1f}%  \n"
                            )

                            # 남·여 이중 링 게이지 (남=바깥 파랑, 여=안쪽 빨강)
                            if pd.notna(r_m) or pd.notna(r_f):
                                fig, ax = plt.subplots(figsize=(3.2, 3.2))
                                draw_dual_ring(ax, male_pct=r_m, female_pct=r_f,
                                            start_angle=90, clockwise=True, show_start_tick=True, inside_labels=False)
                                ax.set_title("남·여 취업률", fontsize=12, pad=6)
                                st.pyplot(fig, use_container_width=True)

                                st.markdown(
                                    f"""
                                    <div style="margin-top:-4px; line-height:1.6;">
                                    <div style="display:flex; align-items:center; gap:.5rem;">
                                        <span style="width:10px; height:10px; border-radius:50%; background:#2563eb; display:inline-block;"></span>
                                        <span style="color:#2563eb; font-weight:700;">남:</span>
                                        <span style="font-weight:700; color:#334155;">{r_m:.1f}%</span>
                                    </div>
                                    <div style="display:flex; align-items:center; gap:.5rem;">
                                        <span style="width:10px; height:10px; border-radius:50%; background:#ef4444; display:inline-block;"></span>
                                        <span style="color:#ef4444; font-weight:700;">여:</span>
                                        <span style="font-weight:700; color:#334155;">{r_f:.1f}%</span>
                                    </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
        st.divider()

    st.header("검색 / 필터")
    q = st.text_input("자격증명 검색", value="")

    # 변경
    cls_all = sorted(df[CLS_COL].dropna().astype(str).unique().tolist())
    # 국가기술/전문/민간만 보여줌, 없으면 전체 옵션 그대로 사용
    whitelist = [o for o in cls_all if any(k in o for k in ("국가기술", "국가전문", "국가민간"))]
    cls_options = whitelist if whitelist else cls_all

    sel_cls = st.selectbox(
        "자격증 분류",
        options=["(전체)"] + cls_options,
        index=0,
        key="cls_single",
    )


    # '국가기술자격' 포함 시에만 등급코드 필터
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

    c1, c2, c3 = st.columns(3)
    want_w = c1.toggle("필기", value=False)
    want_p = c2.toggle("실기", value=False)
    want_i = c3.toggle("면접", value=False)

    sel_lv    = st.multiselect("난이도 등급(1~5)", options=[1,2,3,4,5], default=[1,2,3,4,5])
    page_size = st.slider("페이지당 카드 수", 6, 60, 12, step=6)

# ─────────── 필터 적용 ───────────
f = df.copy()
if selected_ids:
    f = f[f[ID_COL].astype(str).isin([str(x) for x in selected_ids])]
if q:
    f = f[f[NAME_COL].astype(str).str.contains(q, case=False, na=False)]
if sel_cls != "(전체)":
    f = f[f[CLS_COL].astype(str) == sel_cls]
if sel_buckets:
    f = f[pd.to_numeric(f[GRADE_COL], errors="coerce").round(-2).isin(sel_buckets)]
if want_w: f = f[f["HAS_W"]==True]
if want_p: f = f[f["HAS_P"]==True]
if want_i: f = f[f["HAS_I"]==True]
f = f[f["DIFF_LEVEL(1-5)"].isin(sel_lv)]
f = f.sort_values(["DIFF_SCORE","OVERALL_PASS(%)"], ascending=[False, True])

# ─────────── 페이지네이션(하단) ───────────
total = len(f)
max_pages = max(1, int(np.ceil(total / page_size)))
if "page" not in st.session_state: st.session_state.page = 1
if st.session_state.page > max_pages: st.session_state.page = 1
if st.session_state.page < 1: st.session_state.page = 1
page = st.session_state.page
start, end = (page-1)*page_size, (page-1)*page_size + page_size
page_df = f.iloc[start:end]

st.markdown(f"#### 결과: {total:,}건 (페이지 {page}/{max_pages})")
st.caption("정렬: 난이도 점수 내림차순 → 합격률 오름차순")
top_area = st.container()

# ─────────── 카드 렌더링 ───────────
def license_card(row):
    title, rid = str(row[NAME_COL]), str(row[ID_COL])
    cls        = str(row.get(CLS_COL, ""))
    grade      = row.get(GRADE_COL, "")
    freq_disp  = row.get(FREQ_COL, "")       # 표시는 원문
    struct     = row.get("STRUCT_TXT", "")
    diff_lv    = row.get("DIFF_LEVEL(1-5)", np.nan)
    diff_sc    = row.get("DIFF_SCORE", np.nan)
    apps       = row.get("APPLICANTS_AVG", np.nan)

    with st.container(border=True):
        st.markdown(f"##### {title}  <small style='color:#868e96'>[{rid}]</small>", unsafe_allow_html=True)

            # ⬇ 두 줄 배지
        st.markdown(
            f"""
            <div class='pill-row'>
                {badge(f"분류: {cls}")}{badge(f"등급코드: {grade}")}
            </div>
            <div class='pill-row'>
                {badge(f"검정횟수: {freq_disp}")}{badge(f"구조: {struct}")}
            </div>
            """,
            unsafe_allow_html=True
        )

        c1, c2, c3 = st.columns(3)
        with c1: st.metric("난이도 등급", f"{int(diff_lv) if pd.notna(diff_lv) else '-'} / 5",
                           help=(f"점수 {diff_sc:.3f}" if pd.notna(diff_sc) else None))
        with c2: st.metric("평균 응시자수", fmt_int(apps))
        with c3:
            ov = row.get("OVERALL_PASS(%)", np.nan)
            st.metric("전체 합격률(평균)", f"{ov:.1f}%" if pd.notna(ov) else "-")

        p1, p2, p3 = st.columns(3)
        with p1:
            v = row.get("PASS_1차_AVG(22-24)", np.nan)
            st.metric("1차 합격률(3년평균)", f"{v:.1f}%" if pd.notna(v) else "-")
        with p2:
            v = row.get("PASS_2차_AVG(22-24)", np.nan)
            st.metric("2차 합격률(3년평균)", f"{v:.1f}%" if pd.notna(v) else "-")
        with p3:
            v = row.get("PASS_3차_AVG(22-24)", np.nan)
            st.metric("3차 합격률(3년평균)", f"{v:.1f}%" if pd.notna(v) else "-")

        # 관련 직무 보기
        if (df_jobs is not None) and (JOB_ID_COL in df_jobs.columns):
            if st.button("관련 직무 보기", key=f"jobbtn_{rid}", use_container_width=True):
                st.session_state["selected_license"] = rid
                # 직무 상세 선택은 초기화
                st.session_state.pop("selected_job_seq", None)

rows = list(page_df.to_dict(orient="records"))
if not rows:
    st.info("조건에 맞는 결과가 없습니다. 필터를 조정해 보세요.")
else:
    ncol = 3
    for i in range(0, len(rows), ncol):
        cols = st.columns(ncol)
        for j in range(ncol):
            if i+j < len(rows):
                with cols[j]:
                    license_card(rows[i+j])

# ─────────── 관련 직무(카드) & 상세 패널 — 결과 **위쪽**에 출력 ───────────
with top_area:
    sel_license = st.session_state.get("selected_license")

    # 선택한 자격증의 3년 평균 합격률(1·2·3차) 라인차트 — 선택 시 함께 위쪽에 표시(선택사항)
    if sel_license is not None:
        lic = df[df[ID_COL].astype(str) == str(sel_license)]
        if not lic.empty:
            row = lic.iloc[0]
            x_labels = ["1차", "2차", "3차"]
            y_vals   = [
                pd.to_numeric(row.get("PASS_1차_AVG(22-24)"), errors="coerce"),
                pd.to_numeric(row.get("PASS_2차_AVG(22-24)"), errors="coerce"),
                pd.to_numeric(row.get("PASS_3차_AVG(22-24)"), errors="coerce"),
            ]
            x_plot = [l for l, v in zip(x_labels, y_vals) if pd.notna(v)]
            y_plot = [float(v) for v in y_vals if pd.notna(v)]

            if len(y_plot) > 0:
                _, mid, _ = st.columns([1, 2, 1])
                with mid:
                    x_idx = np.arange(len(x_plot))
                    fig, ax = plt.subplots(figsize=(7, 3.6))
                    ax.plot(x_idx, y_plot, marker="o", linewidth=2.6, markersize=6, solid_capstyle="round")
                    ax.fill_between(x_idx, y_plot, 0, alpha=0.10)
                    ax.set_xticks(x_idx, x_plot)
                    ax.set_ylim(0, 100)
                    ax.set_yticks(np.arange(0, 101, 20))
                    ax.set_ylabel("합격률(%)", labelpad=6)
                    ax.set_title("3년 평균 합격률 (1·2·3차)", pad=6)
                    ax.grid(True, which="major")
                    hide_spines(ax)
                    for xi, yi in zip(x_idx, y_plot):
                        ax.annotate(f"{yi:.1f}%", (xi, yi),
                                    textcoords="offset points", xytext=(0, 8), ha="center")
                    fig.tight_layout()
                    st.pyplot(fig, use_container_width=True)

    # ── 관련 직무 카드들(학과명 표기)
    if df_jobs is not None and (JOB_ID_COL in df_jobs.columns) and sel_license:
        jobs = df_jobs[df_jobs[JOB_ID_COL] == str(sel_license).strip()].copy()

        st.subheader("관련 직무")
        if jobs.empty:
            st.info("연결된 직무 데이터가 없습니다.")
        else:
            if "학과명" in jobs.columns:
                jobs = (
                    jobs.assign(학과명=jobs["학과명"].astype(str).str.strip())
                        .groupby([JOB_SEQ_COL, "직업명"], as_index=False)["학과명"]
                        .agg(lambda s: ", ".join(pd.Series(s).dropna().unique()))
                )

            ncol = 2
            job_rows = list(jobs.to_dict(orient="records"))
            for i in range(0, len(job_rows), ncol):
                cols = st.columns(ncol)
                for j in range(ncol):
                    if i + j >= len(job_rows):
                        break
                    jr = job_rows[i + j]
                    seq   = str(jr.get(JOB_SEQ_COL, "")).strip()
                    title = str(jr.get("직업명", "(직업명 미상)"))
                    major = str(jr.get("학과명", "")).strip()

                    with cols[j]:
                        with st.container(border=True):
                            st.markdown(
                                f"**{title}**  <small style='color:#868e96'>[{seq}]</small>",
                                unsafe_allow_html=True
                            )
                            if major:
                                st.caption(f"관련 학과: {major}")

                            if st.button("상세 정보", key=f"jobinfo_btn__{sel_license}__{seq}",
                                         use_container_width=True):
                                st.session_state["selected_job_seq"]   = seq
                                st.session_state["selected_job_title"] = title

    # ── 상세 패널
    sel_job = st.session_state.get("selected_job_seq")
    st.divider()
    st.subheader("직업 상세 정보")

    if (sel_job is None) or (df_jobinfo is None) or (JOB_SEQ_COL not in (df_jobinfo.columns if df_jobinfo is not None else [])):
        st.info("상세 보기를 선택하면 이곳에 표시됩니다.")
    else:
        detail = df_jobinfo[df_jobinfo[JOB_SEQ_COL] == str(sel_job).strip()]
        if detail.empty:
            st.warning("직업정보 데이터가 없습니다(키 불일치). 아래 '디버그'에서 키를 확인해 보세요.")
        else:
            r = detail.iloc[0].astype(str).str.strip().to_dict()
            title = st.session_state.get("selected_job_title") or r.get("직업명", "")

            with st.container(border=True):
                st.markdown(
                    f"### {title}  <small style='color:#868e96'>[{str(sel_job).strip()}]</small>",
                    unsafe_allow_html=True
                )

                score_keys = ["보상","고용안정","발전가능성","근무여건","직업전문성","고용평등"]
                cols = st.columns(3); k = 0
                for sk in score_keys:
                    val = r.get(sk, "")
                    if val and val.lower() not in ["nan", "none"]:
                        with cols[k % 3]:
                            st.metric(sk, val)
                        k += 1

                # 레이더차트(그대로 유지)
                radar_keys   = ["보상","고용안정","발전가능성","근무여건","직업전문성","고용평등"]
                radar_labels = radar_keys[:]
                radar_vals   = [_num_in_text(r.get(k, "")) for k in radar_keys]

                if any(pd.notna(v) for v in radar_vals):
                    vals = [0.0 if pd.isna(v) else float(v) for v in radar_vals]
                    angles = np.linspace(0, 2*np.pi, len(vals), endpoint=False)

                    _, mid, _ = st.columns([1, 2, 1])
                    with mid:
                        fig = plt.figure(figsize=(5.2, 5.2))
                        ax = plt.subplot(111, polar=True)
                        ax.set_theta_offset(np.pi / 2)
                        ax.set_theta_direction(-1)
                        angles_c = np.concatenate([angles, angles[:1]])
                        vals_c   = np.concatenate([vals,   vals[:1]])
                        ax.plot(angles_c, vals_c, linewidth=2.4)
                        ax.fill(angles_c, vals_c, alpha=0.12)
                        ax.set_thetagrids(np.degrees(angles), radar_labels)
                        ax.set_ylim(0, 100)
                        ax.set_rgrids([20, 40, 60, 80, 100], angle=90, fontsize=9)
                        ax.set_title("직업 지표 레이더", pad=12)
                        ax.grid(True, linestyle="--", alpha=0.35)
                        ax.spines["polar"].set_linewidth(0.9)
                        for ang, val in zip(angles, vals):
                            ax.annotate(f"{val:.0f}", (ang, val),
                                        textcoords="offset points", xytext=(0, 6), ha="center")
                        fig.tight_layout()
                        st.pyplot(fig, use_container_width=True)

                st.divider()

                sections = [
                    ("직업전망요약","직업전망요약"),
                    ("취업방법","취업방법"),
                    ("준비과정","준비과정"),
                    ("교육과정","교육과정"),
                    ("적성","적성"),
                    ("고용형태","고용형태"),
                    ("고용분류","고용분류"),
                    ("표준분류","표준분류"),
                    ("직무구분","직무구분"),
                    ("초임","초임"),
                    ("유사직업명","유사직업명"),
                ]
                for key, label in sections:
                    val = (r.get(key) or "").strip()
                    if not val or val.lower() in ["nan", "none"]:
                        continue
                    st.markdown(f"**{label}**")
                    # 👉 다크모드에서도 읽히도록 글자색을 강제한다.
                    st.markdown(
                        "<div class='detail-box'>" + val + "</div>",
                        unsafe_allow_html=True
                    )

                c1, c2 = st.columns([1,1])
                with c1:
                    if st.button("상세 보기 닫기", key="close_jobinfo", use_container_width=True):
                        st.session_state.pop("selected_job_seq", None)
                        st.session_state.pop("selected_job_title", None)
                        if hasattr(st, "rerun"): st.rerun()
                with c2:
                    if st.button("관련 직무 선택 해제", key="clear_jobs", use_container_width=True):
                        st.session_state.pop("selected_license", None)
                        st.session_state.pop("selected_job_seq", None)
                        st.session_state.pop("selected_job_title", None)
                        if hasattr(st, "rerun"): st.rerun()


# ─────────── 하단 페이지 컨트롤 ───────────
if "page" not in st.session_state:
    st.session_state.page = 1
st.session_state.page = int(np.clip(st.session_state.page, 1, max_pages))

st.session_state.setdefault("page_input", st.session_state.page)
st.session_state.page_input = st.session_state.page

def _sync_page_from_input():
    st.session_state.page = int(st.session_state.page_input)
    _clear_job_selection_only()   # ← 입력으로 페이지 바꾸면 초기화

def _prev_page():
    st.session_state.page = max(1, st.session_state.page - 1)
    _clear_job_selection_only()   # ← 이전 버튼 클릭 시 초기화

def _next_page():
    st.session_state.page = min(max_pages, st.session_state.page + 1)
    _clear_job_selection_only()   # ← 다음 버튼 클릭 시 초기화

c_prev, c_info, c_next = st.columns([1, 2, 1])

with c_prev:
    st.button("◀ 이전", use_container_width=True,
              disabled=(st.session_state.page <= 1), on_click=_prev_page)

with c_info:
    st.number_input("페이지", min_value=1, max_value=max_pages, step=1,
                    key="page_input", on_change=_sync_page_from_input)

with c_next:
    st.button("다음 ▶", use_container_width=True,
              disabled=(st.session_state.page >= max_pages), on_click=_next_page)

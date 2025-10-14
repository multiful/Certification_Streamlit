# -*- coding: utf-8 -*-
# 전공별 자격증 대시보드 — 내부 난이도 계산 + 하단 페이지네이션
# '국가기술자격' 선택 시에만 등급코드 필터 노출
# 라이선스 카드 → [관련 직무 보기] → 직무 카드 목록(학과명 표시) → [상세 정보] → 직업정보 상세 패널

import re
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

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

def hide_spines(ax):
    for s in ["top", "right"]:
        if s in ax.spines: ax.spines[s].set_visible(False)

use_korean_font()
apply_pretty_style()


# ───────────────── 기본 ─────────────────
st.set_page_config(page_title="전공별 자격증 대시보드", layout="wide", page_icon="🎓")
st.title("🎓 전공별 자격증 난이도·합격률 대시보드")

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
    return f"<span style='padding:2px 8px;border-radius:999px;background:#f8f9fa;border:1px solid #dee2e6;font-size:11px;margin-right:6px;'>{t}</span>"

def _num_in_text(x):
    s = "" if x is None else str(x)
    m = re.search(r"[-+]?\d*\.?\d+", s)  # 문자열 속 첫 숫자만 추출
    return float(m.group(0)) if m else np.nan


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

# ─────────── 사이드바 ───────────
with st.sidebar:
    st.header("전공 필터")
    use_major     = st.toggle("전공으로 필터", value=False)
    selected_ids  = None

    if use_major:
        if df_major is None:
            st.error("전공 엑셀을 찾지 못했습니다.")
        else:
            major_name_col, major_id_col = "학과명", "자격증ID"
            majors_all = sorted(df_major[major_name_col].astype(str).unique().tolist())
            qmaj       = st.text_input("전공 검색", value="")
            majors_view= [m for m in majors_all if qmaj.strip()=="" or qmaj.lower() in m.lower()]
            sel_major  = st.selectbox("학과명", ["(선택)"]+majors_view, index=0)
            if sel_major != "(선택)":
                selected_ids = (
                    df_major.loc[df_major[major_name_col].astype(str)==sel_major, major_id_col]
                           .astype(str).unique().tolist()
                )
        st.divider()

    st.header("검색 / 필터")
    q = st.text_input("자격증명 검색", value="")
    cls_options = sorted(df[CLS_COL].dropna().astype(str).unique().tolist())
    sel_cls     = st.multiselect("자격증 분류", options=cls_options, default=cls_options)

    # '국가기술자격' 포함 시에만 등급코드 필터
    show_grade_filter = any(("국가기술" in c) or ("기술" in c) for c in sel_cls)
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
if sel_cls:
    f = f[f[CLS_COL].astype(str).isin(sel_cls)]
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
        st.markdown(
            badge(f"분류: {cls}") +
            badge(f"등급코드: {grade}") +
            badge(f"검정횟수: {freq_disp}") +
            badge(f"구조: {struct}"),
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

# ─────────── 관련 직무(카드) & 상세 패널(페이지 하단) ───────────
sel_license = st.session_state.get("selected_license")

# ── 선택한 자격증의 3년 평균 합격률(1·2·3차) 라인차트 ──
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
            _, mid, _ = st.columns([1, 2, 1])   # 가운데 정렬 & 폭 안정
            with mid:
                x_idx = np.arange(len(x_plot))
                fig, ax = plt.subplots(figsize=(7, 3.6))
                line, = ax.plot(x_idx, y_plot, marker="o", linewidth=2.6, markersize=6, solid_capstyle="round")
                # 라인 아래 은은한 영역
                ax.fill_between(x_idx, y_plot, 0, alpha=0.10)
                ax.set_xticks(x_idx, x_plot)
                ax.set_ylim(0, 100)
                ax.set_yticks(np.arange(0, 101, 20))
                ax.set_ylabel("합격률(%)", labelpad=6)
                ax.set_title("3년 평균 합격률 (1·2·3차)", pad=6)
                ax.grid(True, which="major")
                hide_spines(ax)
                # 값 라벨
                for xi, yi in zip(x_idx, y_plot):
                    ax.annotate(f"{yi:.1f}%", (xi, yi), textcoords="offset points", xytext=(0, 8), ha="center")
                fig.tight_layout()
                st.pyplot(fig, use_container_width=True)

# 1) 관련 직무 카드들 (학과명 표기)
if df_jobs is not None and (JOB_ID_COL in df_jobs.columns) and sel_license:
    jobs = df_jobs[df_jobs[JOB_ID_COL] == str(sel_license).strip()].copy()

    st.subheader("관련 직무")
    if jobs.empty:
        st.info("연결된 직무 데이터가 없습니다.")
    else:
        # 동일 jobdicSeq 묶어서 학과명 합치기
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

                        # 상세 패널은 페이지 '맨 하단'에 렌더 → 여기서는 선택만 저장
                        if st.button("상세 정보", key=f"jobinfo_btn__{sel_license}__{seq}",
                                     use_container_width=True):
                            st.session_state["selected_job_seq"]   = seq
                            st.session_state["selected_job_title"] = title

# 2) 상세 패널(페이지 하단 고정 렌더)
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

            # 점수 요약(있을 때만)
            score_keys = ["보상","고용안정","발전가능성","근무여건","직업전문성","고용평등"]
            cols = st.columns(3)
            k = 0
            for sk in score_keys:
                val = r.get(sk, "")
                if val and val.lower() not in ["nan", "none"]:
                    with cols[k % 3]:
                        st.metric(sk, val)
                    k += 1
            # ── 6개 지표 레이더차트 ──
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
                    # 위쪽(12시)에서 시작 & 시계방향
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

                    # 꼭짓점 값 표시
                    for ang, val in zip(angles, vals):
                        ax.annotate(f"{val:.0f}", (ang, val), textcoords="offset points", xytext=(0, 6), ha="center")

                    fig.tight_layout()
                    st.pyplot(fig, use_container_width=True)

            st.divider()

            # 긴 텍스트 섹션
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
                st.markdown(
                    "<div style='white-space:pre-wrap; line-height:1.7; "
                    "background:#f8fbff; border:1px solid #e9ecef; border-radius:10px; "
                    "padding:12px; margin:6px 0 16px 0;'>"
                    f"{val}</div>",
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
c_prev, c_info, c_next = st.columns([1, 2, 1])
def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

with c_prev:
    if st.button("◀ 이전", use_container_width=True, disabled=(page <= 1), key="prev_btn"):
        st.session_state.page = max(1, page - 1); _safe_rerun()
with c_info:
    new_page = st.number_input("페이지", min_value=1, max_value=max_pages, value=page, step=1, key="page_num")
    if new_page != page:
        st.session_state.page = int(new_page); _safe_rerun()
with c_next:
    if st.button("다음 ▶", use_container_width=True, disabled=(page >= max_pages), key="next_btn"):
        st.session_state.page = min(max_pages, page + 1); _safe_rerun()

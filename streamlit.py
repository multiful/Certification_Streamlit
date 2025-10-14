# -*- coding: utf-8 -*-
# 전공별 자격증 대시보드 — 내부 난이도 계산 + 하단 페이지네이션
# '국가기술자격' 선택 시에만 등급코드 필터 노출
# 카드 클릭(버튼) 시 해당 자격증과 연결된 직무 표를 하단에 표시

import numpy as np
import pandas as pd
import streamlit as st

# ───────────────── 기본 ─────────────────
st.set_page_config(page_title="전공별 자격증 대시보드", layout="wide", page_icon="🎓")
st.title("🎓 전공별 자격증 난이도·합격률 대시보드")

CERT_PATHS  = ["data_cert.xlsx"]
MAJOR_PATHS = ["data_major.xlsx"]
JOBS_PATHS  = ["data_jobs.xlsx"]

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

if df is None:
    st.error("자격증 엑셀을 찾지 못했습니다.")
    st.stop()

# 직무 파일 키 컬럼 통일
JOB_ID_COL = "자격증ID"
if df_jobs is not None and JOB_ID_COL in df_jobs.columns:
    df_jobs[JOB_ID_COL] = df_jobs[JOB_ID_COL].astype(str)

# 고정 컬럼명
NAME_COL, ID_COL, CLS_COL = "자격증명", "자격증ID", "자격증_분류"
GRADE_COL, GRADE_TYPE_COL = "자격증_등급_코드", "등급_분류"
FREQ_COL, STRUCT_COL      = "검정 횟수", "시험종류"
W_COL, P_COL, I_COL       = "필기", "실기", "면접"

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

def freq_bonus(v, all_freq)->float:
    f = num(v)
    if pd.isna(f) or all_freq.notna().sum()==0: return 0.0
    fmin, fmax = float(np.nanmin(all_freq)), float(np.nanmax(all_freq))
    if fmax == fmin: return 0.0
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
    return f"<span style='padding:2px 8px;border-radius:999px;background:#f1f3f5;border:1px solid #dee2e6;font-size:11px;margin-right:6px;'>{t}</span>"

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
inv_overall  = (100.0 - df["OVERALL_PASS(%)"]) / 100.0
trust_w      = df["APPLICANTS_AVG"].apply(lambda a: trust_weight(a, df["APPLICANTS_AVG"]))
freq_series  = num(df[FREQ_COL]) if FREQ_COL in df.columns else pd.Series([np.nan]*len(df))
score = (inv_overall.fillna(0)*trust_w
         + df[CLS_COL].apply(class_bonus).fillna(0.0)
         + df[GRADE_COL].apply(grade_bonus).fillna(0.0)
         + freq_series.apply(lambda v: freq_bonus(v, num(freq_series))).fillna(0.0)
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

    st.header("검색/필터")
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
    page_size = st.slider("페이지당 카드 수", 6, 60, 12, step=6, help="한 번에 몇 개의 카드를 볼지")

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
if "page" not in st.session_state:
    st.session_state.page = 1
if st.session_state.page > max_pages:
    st.session_state.page = 1
if st.session_state.page < 1:
    st.session_state.page = 1
page = st.session_state.page

start, end = (page-1)*page_size, (page-1)*page_size + page_size
page_df = f.iloc[start:end]

st.markdown(f"#### 결과: {total:,}건 (페이지 {page}/{max_pages})")
st.caption("정렬: 난이도 점수 내림차순 → 합격률 오름차순")

# ─────────── 카드 렌더링 ───────────
def card(row):
    title, rid = str(row[NAME_COL]), str(row[ID_COL])
    cls        = str(row.get(CLS_COL, ""))
    grade      = row.get(GRADE_COL, "")
    freq       = row.get(FREQ_COL, "")
    struct     = row.get("STRUCT_TXT", "")
    diff_lv    = row.get("DIFF_LEVEL(1-5)", np.nan)
    diff_sc    = row.get("DIFF_SCORE", np.nan)
    apps       = row.get("APPLICANTS_AVG", np.nan)

    st.markdown(f"##### {title}  <small style='color:#868e96'>[{rid}]</small>", unsafe_allow_html=True)
    st.markdown(
        badge(f"분류: {cls}") + badge(f"등급코드: {grade}") + badge(f"검정횟수: {fmt_int(freq)}") + badge(f"구조: {struct}"),
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

    # ▶ 관련 직무 보기 버튼(선택 시 세션에 자격증ID 저장)
    if df_jobs is not None and (JOB_ID_COL in df_jobs.columns):
        if st.button("관련 직무 보기", key=f"job_{rid}", use_container_width=True):
            st.session_state["selected_license"] = rid

    st.divider()

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
                    card(rows[i+j])

# ▶ 카드 목록 아래: 선택된 자격증의 관련 직무 표시
sel = st.session_state.get("selected_license")
if df_jobs is not None and (JOB_ID_COL in df_jobs.columns) and sel:
    st.subheader("관련 직무")
    jj = df_jobs[df_jobs[JOB_ID_COL] == str(sel)]
    if jj.empty:
        st.info("연결된 직무 데이터가 없습니다.")
    else:
        show_cols = [c for c in ["직무명","소개","링크","근무지역","연봉","고용형태"] if c in jj.columns]
        st.dataframe(jj[show_cols] if show_cols else jj, use_container_width=True)
        if st.button("선택 해제", key="clear_job"):
            st.session_state.pop("selected_license", None)

# ─────────── 하단 페이지 컨트롤 ───────────
c_prev, c_info, c_next = st.columns([1, 2, 1])

def _safe_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    elif hasattr(st, "experimental_rerun"):
        st.experimental_rerun()

with c_prev:
    if st.button("◀ 이전", use_container_width=True, disabled=(page <= 1), key="prev_btn"):
        st.session_state.page = max(1, page - 1)
        _safe_rerun()

with c_info:
    new_page = st.number_input("페이지", min_value=1, max_value=max_pages, value=page, step=1, key="page_num")
    if new_page != page:
        st.session_state.page = int(new_page)
        _safe_rerun()

with c_next:
    if st.button("다음 ▶", use_container_width=True, disabled=(page >= max_pages), key="next_btn"):
        st.session_state.page = min(max_pages, page + 1)
        _safe_rerun()

# ─────────── 다운로드 ───────────
with st.expander("다운로드"):
    keep = [
        ID_COL, NAME_COL, CLS_COL, GRADE_COL, GRADE_TYPE_COL, FREQ_COL, STRUCT_COL,
        "PASS_1차_AVG(22-24)", "PASS_2차_AVG(22-24)", "PASS_3차_AVG(22-24)",
        "OVERALL_PASS(%)", "APPLICANTS_AVG", "DIFF_SCORE", "DIFF_LEVEL(1-5)"
    ]
    keep = [c for c in keep if c in f.columns]
    st.dataframe(f[keep], use_container_width=True)
    st.download_button(
        "CSV 다운로드",
        data=f[keep].to_csv(index=False).encode("utf-8-sig"),
        file_name="license_filtered.csv",
        mime="text/csv",
    )



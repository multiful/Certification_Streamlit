# app.py — 전공 선택 → 자격증 카드(난이도/합격률/구조/검정횟수) 스트림릿 대시보드
# 요구 패키지: streamlit, pandas, numpy, altair, plotly
# 터미널: streamlit run app.py

import re
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
import plotly.express as px

# ==============================
# 페이지 설정
# ==============================
st.set_page_config(page_title="전공별 자격증 탐색 대시보드", layout="wide", page_icon="🎓")
st.title("🎓 전공별 자격증 난이도·합격률 대시보드")
st.caption("좌측에서 전공/검색/필터를 고르고, 오른쪽 카드로 자격증 정보를 확인하세요.")

# ==============================
# 파일 경로(필요시 수정)
# ==============================
CERT_PATH_CANDIDATES = [
    "/mnt/data/1010자격증데이터_통합.xlsx",
    "1010자격증데이터_통합.xlsx",
    "./data/1010자격증데이터_통합.xlsx",
]
MAJOR_PATH_CANDIDATES = [
    "/mnt/data/1013전공정보통합_final.xlsx",
    "1013전공정보통합_final.xlsx",
    "./data/1013전공정보통합_final.xlsx",
]

# ==============================
# 컬럼 힌트(이름이 다르면 여기서 고정 매핑 가능)
# ==============================
COLUMN_HINTS = {
    "id": ["자격증ID", "license_id", "ID", "자격증_id"],
    "name": ["자격증명", "license_name", "이름", "종목명", "자격명"],
    "cls": ["분류", "자격증_분류", "classification"],
    "grade_code": ["등급코드", "자격증_등급_코드", "grade_code", "등급"],
    "freq": ["검정횟수", "연간검정횟수", "시험횟수", "연간시험횟수"],
    "structure": ["시험구조", "시험_구조", "structure"],
    "has_written": ["필기", "필기여부", "필기_여부"],
    "has_practical": ["실기", "실기여부", "실기_여부"],
    "has_interview": ["면접", "면접여부", "면접_여부"],
    # 연도별 합격률·응시자 수는 패턴 검색(아래)로 처리
}

YEARS = [2022, 2023, 2024]

# 난이도 가중치(슬라이드 기준값, 필요시 조정)
SCORING_WEIGHTS = {
    "w_invpass": 1.0,          # 역합격률 가중(기본축)
    "w_trust_floor": 0.5,       # 신뢰가중 하한
    "w_trust_span": 0.5,        # 신뢰가중 상한(하한+span*w)
    "add_practical": 0.15,      # 실기 가산
    "add_interview": 0.10,      # 면접 가산
    "add_extra_component": 0.05,# (필수 외 구성요소 있을 때) 선택적 가산
    "add_cls_prof": 0.20,       # 국가전문
    "add_cls_tech": 0.10,       # 국가기술
    "add_cls_private": 0.00,    # 국가민간
    "add_grade_code_max": 0.20, # (500-등급)/400 * 0.20
    "add_freq_max": 0.10,       # (횟수 적을수록 +) 정규화 상한
}

CLASS_MAP = {
    "국가전문": SCORING_WEIGHTS["add_cls_prof"],
    "국가기술": SCORING_WEIGHTS["add_cls_tech"],
    "국가민간": SCORING_WEIGHTS["add_cls_private"],
}

# ==============================
# 유틸
# ==============================
def pick_first_col(cols, df_cols):
    for c in cols:
        if c in df_cols:
            return c
    return None

def find_col_by_hint(df, key):
    col = pick_first_col(COLUMN_HINTS.get(key, []), df.columns)
    return col

def find_year_cols(df, year, kind):
    """
    kind: '합격률' or '응시자' or '필기합격률'/'실기합격률'
    규칙: 'YYYY' in col and kind token in col
    """
    y = str(year)
    mask = df.columns.str.contains(y)
    cols = df.columns[mask]
    if "합격률" in kind:
        cols = [c for c in cols if "합격" in c and "률" in c]
    elif kind == "응시자":
        cols = [c for c in cols if ("응시" in c and "수" in c) or ("응시자" in c)]
    return cols

def coalesce_numeric(s):
    """문자/결측 섞여도 숫자만 최대한 뽑아냄"""
    return pd.to_numeric(s, errors="coerce")

def parse_structure_flags(row, col_struct, col_w, col_p, col_i):
    """시험구조 문자열 또는 개별 컬럼에서 필기/실기/면접 flag 추출"""
    has_w = False
    has_p = False
    has_i = False
    if col_struct and pd.notna(row.get(col_struct, np.nan)):
        txt = str(row[col_struct])
        has_w |= bool(re.search("필기", txt))
        has_p |= bool(re.search("실기", txt))
        has_i |= bool(re.search("면접", txt))
    if col_w:
        has_w |= (coalesce_numeric(row.get(col_w, 0)) > 0)
    if col_p:
        has_p |= (coalesce_numeric(row.get(col_p, 0)) > 0)
    if col_i:
        has_i |= (coalesce_numeric(row.get(col_i, 0)) > 0)
    return has_w, has_p, has_i

def weighted_inverse_passrate(overall_rate, total_applicants, all_applicants):
    """
    overall_rate: 0~100 가정. 없으면 NaN.
    total_applicants: 표본 응시자수 합
    all_applicants: 전체 데이터 응시자수 시리즈(정규화용)
    """
    if pd.isna(overall_rate):
        return np.nan
    inv = (100.0 - overall_rate) / 100.0
    # 신뢰가중: log1p(응시자) 정규화
    if total_applicants is not None and total_applicants > 0 and all_applicants.notna().any():
        norm = np.log1p(total_applicants) / np.nanmax(np.log1p(all_applicants))
        w = SCORING_WEIGHTS["w_trust_floor"] + SCORING_WEIGHTS["w_trust_span"] * float(norm)
    else:
        w = 1.0  # 응시자 정보가 없으면 중립
    return inv * SCORING_WEIGHTS["w_invpass"] * w

def grade_code_bonus(code):
    # (500 - code)/400 * 0.20, code가 작을수록 난이도↑
    c = coalesce_numeric(code)
    if pd.isna(c):
        return 0.0
    return max(0.0, min(1.0, (500.0 - float(c)) / 400.0)) * SCORING_WEIGHTS["add_grade_code_max"]

def freq_bonus(freq_value, all_freq):
    # 횟수 적을수록 +, 0~1로 역정규화하여 add_freq_max 스케일
    f = coalesce_numeric(freq_value)
    if pd.isna(f) or f < 0:
        return 0.0
    if all_freq.notna().sum() == 0:
        return 0.0
    # 낮을수록 가산 → (max - f) / (max - min)
    fmin = float(np.nanmin(all_freq))
    fmax = float(np.nanmax(all_freq))
    if fmax == fmin:
        return 0.0
    score01 = (fmax - float(f)) / (fmax - fmin)
    return score01 * SCORING_WEIGHTS["add_freq_max"]

def class_bonus(cls_label):
    if pd.isna(cls_label):
        return 0.0
    return CLASS_MAP.get(str(cls_label).strip(), 0.0)

def structure_bonus(has_w, has_p, has_i, extra_components=0):
    s = 0.0
    if has_p: s += SCORING_WEIGHTS["add_practical"]
    if has_i: s += SCORING_WEIGHTS["add_interview"]
    if extra_components and extra_components > 0:
        s += SCORING_WEIGHTS["add_extra_component"] * float(extra_components)
    return s

def qcut_1to5(series):
    # 값이 적으면 qcut 실패 → 등간분할 대체
    s = series.copy()
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
    # fallback: 등간분할
    mn, mx = float(np.nanmin(valid)) if valid.size else 0.0, float(np.nanmax(valid)) if valid.size else 1.0
    def to_band(x):
        if pd.isna(x): return np.nan
        if mx == mn: return 3.0
        r = (x - mn) / (mx - mn + 1e-12)
        return float(np.clip(np.floor(r*5)+1, 1, 5))
    return s.apply(to_band)

@st.cache_data(show_spinner=False)
def read_excel_first(paths):
    for p in paths:
        if Path(p).exists():
            try:
                return pd.read_excel(p)
            except Exception:
                pass
    return None

# ==============================
# 데이터 로드
# ==============================
df_cert = read_excel_first(CERT_PATH_CANDIDATES)
df_major = read_excel_first(MAJOR_PATH_CANDIDATES)

with st.sidebar:
    st.subheader("데이터 소스")
    c1, c2 = st.columns(2)
    c1.write("자격증 파일:")
    c1.code(next((p for p in CERT_PATH_CANDIDATES if Path(p).exists()), CERT_PATH_CANDIDATES[0]), language="bash")
    c2.write("전공 파일:")
    c2.code(next((p for p in MAJOR_PATH_CANDIDATES if Path(p).exists()), MAJOR_PATH_CANDIDATES[0]), language="bash")

if df_cert is None:
    st.error("자격증 엑셀을 찾지 못했습니다. 상단 경로를 확인하거나 업로더로 올려주세요.")
    up = st.file_uploader("자격증 엑셀 업로드(.xlsx)", type=["xlsx"])
    if up:
        df_cert = pd.read_excel(up)
if df_major is None:
    st.warning("전공 엑셀을 찾지 못했습니다. 전공 필터 없이 전체 자격증을 보여줍니다.")
    up2 = st.file_uploader("전공 엑셀 업로드(.xlsx)", type=["xlsx"])
    if up2:
        df_major = pd.read_excel(up2)

if df_cert is None:
    st.stop()

# ==============================
# 핵심 컬럼 탐색/매핑
# ==============================
cid_col = find_col_by_hint(df_cert, "id")
name_col = find_col_by_hint(df_cert, "name")
cls_col = find_col_by_hint(df_cert, "cls")
grade_col = find_col_by_hint(df_cert, "grade_code")
freq_col = find_col_by_hint(df_cert, "freq")
struct_col = find_col_by_hint(df_cert, "structure")
w_col = find_col_by_hint(df_cert, "has_written")
p_col = find_col_by_hint(df_cert, "has_practical")
i_col = find_col_by_hint(df_cert, "has_interview")

# 필수: 자격증명/ID는 되도록 있어야 카드가 깔끔
if name_col is None:
    # 이름이 없으면 어떤 첫 컬럼으로라도 대체
    name_col = df_cert.columns[0]
if cid_col is None:
    # ID가 없으면 이름으로 대체 ID
    cid_col = name_col

df = df_cert.copy()

# ==============================
# 연도별 합격률/응시자 탐색 → OVERALL 합격률·총 응시자 계산
# ==============================
overall_by_year = {}
applicants_by_year = {}
for y in YEARS:
    # 우선순위: (OVERALL 합격률) → (필기/실기 평균)
    cand_rate_overall = [c for c in find_year_cols(df, y, "합격률") if re.search("OVERALL|종합|전체", c, re.IGNORECASE)]
    if cand_rate_overall:
        overall_by_year[y] = coalesce_numeric(df[cand_rate_overall[0]])
    else:
        # 필기/실기 평균 시도
        cand_written = [c for c in find_year_cols(df, y, "합격률") if "필기" in c]
        cand_prac    = [c for c in find_year_cols(df, y, "합격률") if "실기" in c]
        wr = coalesce_numeric(df[cand_written[0]]) if cand_written else np.nan
        pr = coalesce_numeric(df[cand_prac[0]]) if cand_prac else np.nan
        overall_by_year[y] = pd.Series(np.nanmean(np.vstack([wr, pr]), axis=0))

    cand_apps = find_year_cols(df, y, "응시자")
    if cand_apps:
        # 연도 내 응시자 합
        apps = df[cand_apps].apply(coalesce_numeric).sum(axis=1, skipna=True)
    else:
        apps = pd.Series([np.nan]*len(df))
    applicants_by_year[y] = apps

# 3개 연도 평균(있는 값만)
overall_cols = []
for y, s in overall_by_year.items():
    coln = f"{y}_OVERALL"
    df[coln] = s
    overall_cols.append(coln)

df["OVERALL_PASS(%)"] = df[overall_cols].apply(lambda r: np.nanmean([v for v in r if pd.notna(v)]), axis=1)

# 총 응시자 합
app_cols = []
for y, s in applicants_by_year.items():
    coln = f"{y}_APPLICANTS"
    df[coln] = s
    app_cols.append(coln)
df["APPLICANTS_TOTAL"] = df[app_cols].sum(axis=1, skipna=True)

# ==============================
# 구조 플래그/텍스트
# ==============================
flags = df.apply(lambda row: parse_structure_flags(row, struct_col, w_col, p_col, i_col), axis=1, result_type="expand")
df[["HAS_WRIT","HAS_PRAC","HAS_INTV"]] = flags

def build_struct_label(row):
    parts = []
    if row["HAS_WRIT"]: parts.append("필기")
    if row["HAS_PRAC"]: parts.append("실기")
    if row["HAS_INTV"]: parts.append("면접")
    return "+".join(parts) if parts else ("(미상)" if pd.isna(row.get(struct_col, np.nan)) else str(row.get(struct_col)))

df["STRUCT_TXT"] = df.apply(build_struct_label, axis=1)

# ==============================
# 난이도 점수 계산
# ==============================
# (1) 역합격률×신뢰가중
df["_invpass_trust"] = df.apply(
    lambda r: weighted_inverse_passrate(r["OVERALL_PASS(%)"], r["APPLICANTS_TOTAL"], df["APPLICANTS_TOTAL"]),
    axis=1
)

# (2) 구조/등급/분류/검정횟수 가산
if freq_col is None:
    # 검정횟수 없으면 0 보너스
    freq_series = pd.Series([np.nan]*len(df))
else:
    freq_series = coalesce_numeric(df[freq_col])

df["_bonus_freq"] = freq_series.apply(lambda v: freq_bonus(v, coalesce_numeric(freq_series)))
df["_bonus_grade"] = df[grade_col].apply(grade_code_bonus) if grade_col else 0.0
df["_bonus_class"] = df[cls_col].apply(class_bonus) if cls_col else 0.0

# 구조 보너스
df["_bonus_struct"] = df.apply(
    lambda r: structure_bonus(r["HAS_WRIT"], r["HAS_PRAC"], r["HAS_INTV"], extra_components=0),
    axis=1
)

# 최종 표본 점수
df["DIFF_SCORE"] = df[["_invpass_trust","_bonus_freq","_bonus_grade","_bonus_class","_bonus_struct"]].sum(axis=1, skipna=True)

# 5분위 등급화(1=쉬움~5=어려움)
df["DIFF_LEVEL(1-5)"] = qcut_1to5(df["DIFF_SCORE"])

# ==============================
# 전공 매핑(선택)
# ==============================
major_name_cols = []
if df_major is not None:
    # 전공명 후보
    for c in ["전공명","전공","학과","전공(통합)","major","dept"]:
        if c in df_major.columns: major_name_cols.append(c)
    major_id_col = pick_first_col(["자격증ID","license_id","자격증_id","ID"], df_major.columns)
else:
    major_id_col = None

with st.sidebar:
    st.header("검색/필터")
    # 전공 선택
    if df_major is not None and major_name_cols and major_id_col:
        major_col = major_name_cols[0]
        major_list = ["(전체)"] + sorted(pd.Series(df_major[major_col].astype(str).unique()).dropna().tolist())
        sel_major = st.selectbox("전공 선택", major_list, index=0)
        if sel_major != "(전체)":
            major_ids = df_major.loc[df_major[major_col].astype(str)==sel_major, major_id_col].astype(str).unique().tolist()
        else:
            major_ids = None
    else:
        sel_major = "(전공 파일 미지정)"
        major_ids = None

    # 키워드
    q = st.text_input("자격증명 키워드", value="")

    # 분류
    cls_opts = sorted(df[cls_col].dropna().astype(str).unique().tolist()) if cls_col else []
    sel_cls = st.multiselect("분류(국가전문/국가기술/국가민간)", options=cls_opts, default=cls_opts[:])

    # 등급코드 범위
    if grade_col and coalesce_numeric(df[grade_col]).notna().any():
        gmin = int(np.nanmin(coalesce_numeric(df[grade_col])))
        gmax = int(np.nanmax(coalesce_numeric(df[grade_col])))
        gmin = min(gmin,100); gmax = max(gmax,500)
        sel_g = st.slider("등급코드 범위(낮을수록 고난도)", min_value=100, max_value=500, value=(max(100,gmin), min(500,gmax)), step=50)
    else:
        sel_g = (100, 500)

    # 구조 필터(선택 시 해당 요소 포함)
    fcol1, fcol2, fcol3 = st.columns(3)
    want_w = fcol1.toggle("필기", value=False)
    want_p = fcol2.toggle("실기", value=False)
    want_i = fcol3.toggle("면접", value=False)

    # 난이도 등급 필터
    sel_lv = st.multiselect("난이도 등급(1=쉬움~5=어려움)", options=[1,2,3,4,5], default=[1,2,3,4,5])

    # 표시 개수
    topk = st.slider("표시 개수", min_value=6, max_value=60, value=18, step=6)

# ==============================
# 필터 적용
# ==============================
f = df.copy()

# 전공 필터
if major_ids:
    f = f[f[cid_col].astype(str).isin([str(x) for x in major_ids])]

# 키워드
if q:
    f = f[f[name_col].astype(str).str.contains(q, case=False, na=False)]

# 분류
if cls_col and sel_cls:
    f = f[f[cls_col].astype(str).isin(sel_cls)]

# 등급코드
if grade_col:
    gv = coalesce_numeric(f[grade_col])
    f = f[(gv>=sel_g[0]) & (gv<=sel_g[1])]

# 구조
if want_w: f = f[f["HAS_WRIT"]==True]
if want_p: f = f[f["HAS_PRAC"]==True]
if want_i: f = f[f["HAS_INTV"]==True]

# 난이도 등급
f = f[f["DIFF_LEVEL(1-5)"].isin(sel_lv)]

# 정렬: 어려운 순(점수 desc) → 합격률 asc
f = f.sort_values(["DIFF_SCORE","OVERALL_PASS(%)"], ascending=[False, True])

st.markdown(f"#### 결과: {len(f):,}건")
st.caption("정렬: 난이도 점수 내림차순 → 합격률 오름차순")

# ==============================
# 카드 렌더러
# ==============================
def mini_passrate_chart(row):
    data = []
    for y in YEARS:
        v = row.get(f"{y}_OVERALL", np.nan)
        if not pd.isna(v):
            data.append({"연도": int(y), "합격률(%)": float(v)})
    if not data:
        return None
    cdf = pd.DataFrame(data)
    chart = (
        alt.Chart(cdf)
        .mark_line(point=True)
        .encode(
            x=alt.X("연도:O", title=None),
            y=alt.Y("합격률(%):Q", scale=alt.Scale(domain=[0,100])),
            tooltip=["연도","합격률(%)"]
        )
        .properties(height=120)
    )
    return chart

def badge(text):
    return f'<span style="padding:2px 8px;border-radius:999px;background:#f1f3f5;border:1px solid #dee2e6;font-size:11px;margin-right:6px;">{text}</span>'

def render_card(row):
    title = str(row.get(name_col, ""))
    cid = str(row.get(cid_col, ""))
    cls_ = str(row.get(cls_col, "")) if cls_col else ""
    grade_v = row.get(grade_col, "")
    freq_v = row.get(freq_col, "")
    struct_txt = str(row.get("STRUCT_TXT",""))
    pass_overall = row.get("OVERALL_PASS(%)", np.nan)
    diff_lv = row.get("DIFF_LEVEL(1-5)", np.nan)
    diff_sc = row.get("DIFF_SCORE", np.nan)

    # 상단
    st.markdown(f"##### {title}  <small style='color:#868e96'>[{cid}]</small>", unsafe_allow_html=True)
    st.markdown(
        badge(f"분류: {cls_}") + 
        badge(f"등급코드: {grade_v}") +
        badge(f"검정횟수: {freq_v}") +
        badge(f"구조: {struct_txt}"),
        unsafe_allow_html=True
    )

    # 지표 2열
    c1, c2, c3 = st.columns([1,1,1])
    with c1:
        st.metric("난이도 등급", f"{int(diff_lv) if not pd.isna(diff_lv) else '-'} / 5", help=f"점수 {diff_sc:.3f}" if not pd.isna(diff_sc) else None)
    with c2:
        st.metric("합격률(평균)", f"{pass_overall:.1f}%" if not pd.isna(pass_overall) else "-")
    with c3:
        apps = row.get("APPLICANTS_TOTAL", np.nan)
        st.metric("총 응시자수(합)", f"{int(apps):,}" if not pd.isna(apps) else "-")

    # 미니 라인차트
    ch = mini_passrate_chart(row)
    if ch is not None:
        st.altair_chart(ch, use_container_width=True)

    st.divider()

# ==============================
# 카드 그리드 출력
# ==============================
# 행 단위로 3열 카드
rows = list(f.head(topk).to_dict(orient="records"))
if not rows:
    st.info("조건에 맞는 결과가 없습니다. 필터를 조정해 보세요.")
else:
    ncol = 3
    for i in range(0, len(rows), ncol):
        cols = st.columns(ncol)
        for j in range(ncol):
            if i+j < len(rows):
                with cols[j]:
                    render_card(rows[i+j])

# ==============================
# 다운로드
# ==============================
with st.expander("다운로드"):
    dl_cols = [cid_col, name_col, cls_col, grade_col, freq_col, "STRUCT_TXT", "OVERALL_PASS(%)", "APPLICANTS_TOTAL", "DIFF_SCORE", "DIFF_LEVEL(1-5)"]
    dl_cols = [c for c in dl_cols if (c in f.columns)]
    st.dataframe(f[dl_cols], use_container_width=True)
    st.download_button(
        "CSV 다운로드",
        data=f[dl_cols].to_csv(index=False).encode("utf-8-sig"),
        file_name="license_filtered.csv",
        mime="text/csv"
    )

# ==============================
# 도움말
# ==============================
with st.expander("난이도 산출 로직(요약)"):
    st.markdown(
        """
- **역합격률(1 - 합격률/100)**을 기본 축으로, **응시자수 log1p 정규화**로 신뢰가중.
- 구조 가산: **실기 +0.15, 면접 +0.10** (추가 구성요소가 있다면 +0.05/개 옵션).
- 분류 가산: **국가전문 +0.20, 국가기술 +0.10, 국가민간 0**.
- 등급코드: **(500-등급)/400 × 0.20** (코드가 낮을수록 가산).
- 검정횟수: **횟수 적을수록 +**, 0~0.10 범위로 정규화.
- 종합점수를 **5분위(qcut)**로 나눠 **1(쉬움)~5(어려움)** 등급화.
- 상단 `SCORING_WEIGHTS`에서 수치를 바로 조정할 수 있습니다.
        """
    )

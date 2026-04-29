"""
㈜비나우 환급실적명세서 갑지 추출 (Streamlit 앱)

외국인관광객 부가가치세 환급실적명세서(즉시환급 / 사후환급) 통합 PDF에서
매장·월별 '시작 서식'(갑지) 페이지만 추출해 새 PDF로 만들어 줍니다.
또한 각 갑지의 ⑧ 판매금액과 ⑨ 부가가치세를 자동 인식해
공급가액(= 판매금액 − 부가가치세)을 계산·합산해 표시합니다.
"""

import datetime
import re
from io import BytesIO

import streamlit as st
from pypdf import PdfReader, PdfWriter

# ─────────────────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────────────────

PRIMARY_MARKER = "1. 제출자 인적사항"

DOC_TYPES = {
    "즉시환급": "외국인관광객 즉시환급 물품 판매 실적명세서",
    "사후환급": "외국인관광객 면세물품 판매 및 환급실적명세서",
}

# 매장 정보. 새 매장이 생기면 여기에 추가하세요.
STORES = {
    "21401175": {"name": "노크 아카이브 성수", "addr_keyword": "연무장길"},
    "21401131": {"name": "퓌 아지트 성수",   "addr_keyword": "성수이로7가길"},
    "21401130": {"name": "퓌 아지트 부산",   "addr_keyword": "서전로37번길"},
    "21401129": {"name": "퓌 아지트 연남",   "addr_keyword": "월드컵북로4길"},
}


# ─────────────────────────────────────────────────────────────────────────────
# 핵심 로직 (UI와 분리)
# ─────────────────────────────────────────────────────────────────────────────

def _extract_amounts(text: str):
    """페이지 텍스트에서 합계 행의 (판매금액, 부가세, 공급가액) 추출.

    원리: 판매금액 = 공급가액 + 부가세, 부가세 ≈ 공급가액 × 10%
         즉, 판매금액 ≈ 부가세 × 11.
    이 관계를 만족하는 가장 큰 숫자 쌍 = 합계 행으로 식별.
    """
    raw = re.findall(r'(?<!\d)\d{1,3}(?:,\d{3})+(?!\d)|(?<!\d)\d{4,}(?!\d)', text)
    nums = sorted(
        {int(s.replace(',', '')) for s in raw if int(s.replace(',', '')) >= 1000},
        reverse=True,
    )
    for big in nums:
        for small in nums:
            if small >= big or small == 0:
                continue
            supply = big - small
            if supply <= 0:
                continue
            tol = max(2, small * 0.005)  # 0.5% 또는 2원
            if abs(supply / 10 - small) <= tol:
                return (big, small, supply)
    return None


def _extract_desig_no(text: str):
    """면세판매장 지정번호. 사후/즉시 양쪽 레이아웃 + 취소 명세서까지 커버."""
    # 1) 사후환급: '면세판매장 지정번호 NNNNNNNN'
    m = re.search(r'면세판매장\s*지정번호\s*(\d{8})\b', text)
    if m: return m.group(1)
    # 2) 즉시환급 A: 'NNNNNNNN' 직후 'YYYY년 MM월'
    m = re.search(r'\b(\d{8})\d{4}년\s*\d{2}월\s*\d{2}일\s*~', text)
    if m: return m.group(1)
    # 3) 즉시환급 B: '사업장소재지' 직후 8자리
    m = re.search(r'사업장소재지\s+(\d{8})\b', text)
    if m: return m.group(1)
    # 4) Fallback: 주소 키워드로 매장 매칭 (취소 명세서 등)
    for desig, info in STORES.items():
        if info["addr_keyword"] in text:
            return desig
    return None


def _extract_metadata(text: str):
    info = {}
    m = re.search(r'(\d{4})년\s*(\d{2})월\s*\d{2}일\s*~\s*\d{4}년\s*\d{2}월\s*\d{2}일', text)
    if m:
        info["year"] = int(m.group(1))
        info["month"] = int(m.group(2))
    desig = _extract_desig_no(text)
    if desig:
        info["desig_no"] = desig
        info["store_name"] = STORES.get(desig, {}).get("name")
    if "(취소)" in text:
        info["is_cancel"] = True
    return info


def extract_form_pages(pdf_bytes: bytes) -> dict:
    """입력 PDF bytes에서 시작 서식 페이지만 모아 새 PDF + 페이지별 정보 반환."""
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)

    page_data = []  # 시작 서식 페이지별 정보
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if PRIMARY_MARKER not in text:
            continue
        meta = _extract_metadata(text)
        amts = _extract_amounts(text)
        page_data.append({
            "page_no": i + 1,
            **meta,
            "sales": amts[0] if amts else None,
            "vat": amts[1] if amts else None,
            "supply": amts[2] if amts else None,
        })

    writer = PdfWriter()
    for d in page_data:
        writer.add_page(reader.pages[d["page_no"] - 1])
    out_buf = BytesIO()
    writer.write(out_buf)

    return {
        "bytes": out_buf.getvalue(),
        "total_pages": total,
        "page_data": page_data,
        # 하위 호환용
        "extracted_pages": [d["page_no"] for d in page_data],
    }


def build_output_filename(year: int, half: int, status: str, doc_kind: str) -> str:
    """출력 파일명 규칙: '{연도}년 {기}기 {예정|확정}_{문서제목}_갑지.pdf'."""
    title = DOC_TYPES[doc_kind]
    return f"{year}년 {half}기 {status}_{title}_갑지.pdf"


def _fmt_period(d: dict) -> str:
    if d.get("month"):
        return f"{d.get('year', '?')}-{d['month']:02d}"
    return "?"


def _fmt_store(d: dict) -> str:
    name = d.get("store_name") or d.get("desig_no") or "?"
    if d.get("is_cancel"):
        name += " (취소)"
    return name


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="㈜비나우 환급실적명세서 갑지 추출",
    page_icon="📄",
    layout="wide",
)

# ── 상단 헤더 박스 ──
st.markdown(
    """
    <div style="
        background: linear-gradient(135deg, #1e3a5f 0%, #3d6db4 100%);
        padding: 2rem 2.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        color: white;
    ">
        <h1 style="color: white; margin: 0 0 0.6rem 0; font-size: 1.85rem; font-weight: 700; letter-spacing: -0.5px;">
            📄 ㈜비나우 환급실적명세서 갑지 추출
        </h1>
        <p style="color: rgba(255,255,255,0.92); margin: 0; font-size: 0.95rem; line-height: 1.6;">
            외국인관광객 부가가치세 환급실적명세서(즉시환급 · 사후환급) 통합 PDF에서
            매장·월별 시작 서식(갑지) 페이지만 추출하고, 각 갑지의 판매금액·부가가치세·공급가액을 계산해 줍니다.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab_guide, tab_home = st.tabs(["📖 사용 가이드", "🏠 홈"])

# ─────────────────────────────────────────────────────────────────────────────
# 사용 가이드
# ─────────────────────────────────────────────────────────────────────────────
with tab_guide:
    st.markdown("# 📖 사용 가이드")
    st.markdown("##### 3단계로 끝납니다")

    st.markdown(
        """
        #### 1️⃣ 신고 기간 입력
        **홈** 탭 상단에서 **연도 · 기수(1·2) · 구분(예정·확정)** 을 선택하세요.
        선택한 값이 그대로 출력 파일명에 들어갑니다.

        #### 2️⃣ PDF 업로드
        매장·월별로 합쳐진 **즉시환급 / 사후환급 통합본 PDF** 를 업로드하세요.
        둘 다 올려도 되고, 하나만 올려도 됩니다.

        #### 3️⃣ 결과 확인 & 다운로드
        **🔍 시작 서식(갑지) 페이지 추출** 버튼을 누르면 결과 카드가 나타납니다.
        - 매장·월별 **판매금액 · 부가가치세 · 공급가액(=판매−VAT)** 표 자동 계산
        - **⬇️ 다운로드** 버튼으로 갑지만 모인 PDF 받기
        """
    )

    st.divider()
    st.caption(
        "💡 같은 매장·같은 월에 시작 서식이 여러 장 있어도 (예: 본 명세서 + 취소분) 모두 자동으로 모아 줍니다."
    )

# ─────────────────────────────────────────────────────────────────────────────
# 홈
# ─────────────────────────────────────────────────────────────────────────────
with tab_home:
    st.markdown("# 🏠 홈")
    st.caption("아래 단계를 차례로 진행하세요.")

    st.divider()

    # ── 1. 신고 기간 ──
    st.markdown("### 1️⃣ 신고 기간")

    this_year = datetime.date.today().year
    col_y, col_h, col_s, _ = st.columns([1, 1, 1, 3])
    with col_y:
        year = st.number_input(
            "연도", min_value=2020, max_value=this_year + 1,
            value=this_year, step=1,
        )
    with col_h:
        half = st.selectbox("기", options=[1, 2], index=0)
    with col_s:
        status = st.selectbox("구분", options=["예정", "확정"], index=0)

    st.info(f"선택된 신고 기간: **{year}년 {half}기 {status}**")

    st.markdown("")

    # ── 2. PDF 업로드 ──
    st.markdown("### 2️⃣ PDF 업로드")
    st.caption("즉시환급·사후환급 중 가지고 계신 파일만 올려도 됩니다 (둘 다 가능).")

    col_a, col_b = st.columns(2)
    with col_a:
        file_jeuksi = st.file_uploader(
            "즉시환급 통합본 PDF", type=["pdf"], key="upload_jeuksi",
        )
    with col_b:
        file_sahu = st.file_uploader(
            "사후환급 통합본 PDF", type=["pdf"], key="upload_sahu",
        )

    st.divider()

    # ── 3. 처리 버튼 ──
    run = st.button(
        "🔍 시작 서식(갑지) 페이지 추출",
        type="primary",
        use_container_width=True,
    )

    if run:
        if not file_jeuksi and not file_sahu:
            st.error("PDF 파일을 최소 1개 업로드해주세요.")
            st.session_state.pop("results", None)
        else:
            results = []
            with st.spinner("추출 중..."):
                for uploaded, kind in [(file_jeuksi, "즉시환급"), (file_sahu, "사후환급")]:
                    if not uploaded:
                        continue
                    try:
                        r = extract_form_pages(uploaded.getvalue())
                    except Exception as e:
                        st.error(f"{kind} PDF 처리 중 오류: {e}")
                        continue
                    r["doc_kind"] = kind
                    r["output_name"] = build_output_filename(year, half, status, kind)
                    results.append(r)
            st.session_state["results"] = results

    # ── 4. 결과 ──
    results = st.session_state.get("results", [])
    if results:
        st.markdown("### 3️⃣ 결과")
        for r in results:
            with st.container(border=True):
                st.markdown(f"#### {r['doc_kind']}")

                m1, m2, _ = st.columns([1, 1, 2])
                m1.metric("입력 PDF 총 페이지", f"{r['total_pages']}p")
                m2.metric("추출된 갑지 페이지", f"{len(r['page_data'])}p")

                if not r["page_data"]:
                    st.warning(
                        "이 PDF에서 시작 서식 페이지를 찾지 못했습니다. "
                        "올바른 환급실적명세서 PDF인지 확인해주세요."
                    )
                    continue

                # 페이지별 표
                st.markdown("##### 📊 매장·월별 합계")
                st.caption("공급가액 = 판매금액 − 부가가치세 (부가세 신고 검증용)")

                table_rows = []
                for d in r["page_data"]:
                    table_rows.append({
                        "원본 페이지": d["page_no"],
                        "거래월": _fmt_period(d),
                        "매장": _fmt_store(d),
                        "판매금액": d["sales"],
                        "부가가치세": d["vat"],
                        "공급가액": d["supply"],
                    })

                st.dataframe(
                    table_rows,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "원본 페이지": st.column_config.NumberColumn(width="small"),
                        "판매금액":   st.column_config.NumberColumn(format="%,d 원"),
                        "부가가치세": st.column_config.NumberColumn(format="%,d 원"),
                        "공급가액":   st.column_config.NumberColumn(format="%,d 원"),
                    },
                )

                # 합계 메트릭
                total_sales  = sum((d["sales"]  or 0) for d in r["page_data"])
                total_vat    = sum((d["vat"]    or 0) for d in r["page_data"])
                total_supply = sum((d["supply"] or 0) for d in r["page_data"])

                t1, t2, t3 = st.columns(3)
                t1.metric("판매금액 합계",   f"{total_sales:,} 원")
                t2.metric("부가가치세 합계", f"{total_vat:,} 원")
                t3.metric("공급가액 합계",   f"{total_supply:,} 원")

                st.markdown("")  # spacer

                # 다운로드 버튼
                st.download_button(
                    label=f"⬇️  {r['output_name']}",
                    data=r["bytes"],
                    file_name=r["output_name"],
                    mime="application/pdf",
                    use_container_width=True,
                )

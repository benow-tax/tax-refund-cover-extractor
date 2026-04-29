"""
환급실적명세서 갑지 추출기 (Streamlit 앱)

외국인관광객 부가가치세 환급실적명세서(즉시환급 / 사후환급) 통합 PDF에서
매장·월별 '시작 서식'(갑지) 페이지만 추출해 새 PDF로 만들어 줍니다.
"""

import datetime
from io import BytesIO

import streamlit as st
from pypdf import PdfReader, PdfWriter

# ─────────────────────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────────────────────

# 시작 서식 페이지에만 들어있는 머리글 (첫 회차에서 검증된 마커)
PRIMARY_MARKER = "1. 제출자 인적사항"

DOC_TYPES = {
    "즉시환급": "외국인관광객 즉시환급 물품 판매 실적명세서",
    "사후환급": "외국인관광객 면세물품 판매 및 환급실적명세서",
}


# ─────────────────────────────────────────────────────────────────────────────
# 핵심 로직 (UI와 분리)
# ─────────────────────────────────────────────────────────────────────────────

def find_form_page_indices(reader: PdfReader) -> list[int]:
    """페이지 텍스트에 시작 서식 마커가 있는 인덱스(0-based) 리스트."""
    indices = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if PRIMARY_MARKER in text:
            indices.append(i)
    return indices


def extract_form_pages(pdf_bytes: bytes) -> dict:
    """입력 PDF bytes에서 시작 서식 페이지만 모아 새 PDF bytes를 반환."""
    reader = PdfReader(BytesIO(pdf_bytes))
    total = len(reader.pages)
    indices = find_form_page_indices(reader)

    writer = PdfWriter()
    for idx in indices:
        writer.add_page(reader.pages[idx])

    out_buf = BytesIO()
    writer.write(out_buf)

    return {
        "bytes": out_buf.getvalue(),
        "extracted_pages": [i + 1 for i in indices],  # 사용자에게는 1-based
        "total_pages": total,
    }


def build_output_filename(year: int, half: int, status: str, doc_kind: str) -> str:
    """출력 파일명 규칙: '{연도}년 {기}기 {예정|확정}_{문서제목}_갑지.pdf'."""
    title = DOC_TYPES[doc_kind]
    return f"{year}년 {half}기 {status}_{title}_갑지.pdf"


# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="환급실적명세서 갑지 추출기",
    page_icon="📄",
    layout="centered",
)

st.title("📄 환급실적명세서 갑지 추출기")
st.caption(
    "외국인관광객 부가가치세 환급실적명세서(즉시환급 / 사후환급) 통합 PDF에서 "
    "매장·월별 시작 서식(갑지) 페이지만 추출합니다."
)

st.divider()

# ── 1. 신고 기간 입력 ──
st.subheader("1. 신고 기간")

this_year = datetime.date.today().year
col_y, col_h, col_s = st.columns([2, 1, 1])
with col_y:
    year = st.number_input(
        "연도",
        min_value=2020,
        max_value=this_year + 1,
        value=this_year,
        step=1,
    )
with col_h:
    half = st.selectbox("기", options=[1, 2], index=0)
with col_s:
    status = st.selectbox("구분", options=["예정", "확정"], index=0)

st.info(f"선택된 신고 기간: **{year}년 {half}기 {status}**")

# ── 2. PDF 업로드 ──
st.subheader("2. PDF 업로드")
st.caption("즉시환급·사후환급 중 가지고 계신 파일만 올려도 됩니다 (둘 다 가능).")

col_a, col_b = st.columns(2)
with col_a:
    file_jeuksi = st.file_uploader(
        "즉시환급 통합본 PDF",
        type=["pdf"],
        key="upload_jeuksi",
    )
with col_b:
    file_sahu = st.file_uploader(
        "사후환급 통합본 PDF",
        type=["pdf"],
        key="upload_sahu",
    )

st.divider()

# ── 3. 처리 ──
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

# ── 4. 결과 표시 ──
results = st.session_state.get("results", [])
if results:
    st.subheader("3. 결과")
    for r in results:
        with st.container(border=True):
            st.markdown(f"#### {r['doc_kind']}")

            m1, m2 = st.columns(2)
            m1.metric("입력 PDF 총 페이지", f"{r['total_pages']}p")
            m2.metric("추출된 갑지 페이지", f"{len(r['extracted_pages'])}p")

            if r["extracted_pages"]:
                with st.expander("추출된 페이지 번호 보기"):
                    st.write(r["extracted_pages"])

                st.download_button(
                    label=f"⬇️  {r['output_name']}",
                    data=r["bytes"],
                    file_name=r["output_name"],
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.warning(
                    "이 PDF에서 시작 서식 페이지를 찾지 못했습니다. "
                    "올바른 환급실적명세서 PDF인지 확인해주세요."
                )

# ── 푸터 ──
with st.expander("ℹ️ 동작 방식"):
    st.markdown(
        """
        - 페이지 본문에 **`1. 제출자 인적사항`** 머리글이 있으면 그 페이지를 시작 서식(갑지)으로 판정합니다.
        - 같은 매장·같은 월에 시작 서식이 여러 장 있어도(예: 본 명세서 + 취소분, 1건짜리 + 본 버전) 모두 추출합니다.
        - 출력 파일명 규칙
          - 즉시환급: `{연도}년 {기}기 {예정|확정}_외국인관광객 즉시환급 물품 판매 실적명세서_갑지.pdf`
          - 사후환급: `{연도}년 {기}기 {예정|확정}_외국인관광객 면세물품 판매 및 환급실적명세서_갑지.pdf`
        """
    )

# 환급실적명세서 갑지 추출기

외국인관광객 부가가치세 환급실적명세서(즉시환급 / 사후환급) 통합 PDF에서
매장·월별 **시작 서식(갑지)** 페이지만 자동으로 추출하는 Streamlit 웹앱입니다.

## 기능

- 즉시환급 / 사후환급 두 종류의 PDF 모두 지원 (둘 중 하나만 업로드해도 동작)
- 신고 기간(연도·기수·예정/확정)을 사용자가 직접 선택
- 페이지 본문에 `1. 제출자 인적사항` 머리글이 있는 페이지만 모아 새 PDF로 출력
- 같은 매장·같은 월에 시작 서식이 여러 장 있어도 (예: 본 명세서 + 취소분) 모두 추출
- 출력 파일명 자동 생성
  - 즉시환급: `{연도}년 {기}기 {예정|확정}_외국인관광객 즉시환급 물품 판매 실적명세서_갑지.pdf`
  - 사후환급: `{연도}년 {기}기 {예정|확정}_외국인관광객 면세물품 판매 및 환급실적명세서_갑지.pdf`

## 로컬에서 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 로 접속.

## Streamlit Community Cloud 배포 (무료)

1. 이 코드를 본인 GitHub 계정의 **공개(public)** 저장소로 push
   ```bash
   git init
   git add app.py requirements.txt README.md .gitignore
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/<사용자명>/<저장소명>.git
   git push -u origin main
   ```
2. <https://share.streamlit.io> 접속 → GitHub 계정으로 로그인
3. **New app** 버튼 → Repository / Branch / Main file path(`app.py`) 지정 → **Deploy**
4. 1~2분 후 `https://<앱이름>.streamlit.app` URL로 접근 가능

> 배포 후 코드를 push하면 자동으로 재배포됩니다.

## 파일 구성

```
.
├── app.py              # Streamlit 앱 (UI + 추출 로직)
├── requirements.txt    # 의존성 (streamlit, pypdf)
├── README.md           # 본 문서
└── .gitignore          # Python 표준 ignore
```

## 동작 원리

PDF의 각 페이지에서 텍스트를 추출해 머리글 `1. 제출자 인적사항`이 들어있는지 확인합니다.
이 머리글은 시작 서식 페이지에만 존재하며, 일련번호만 이어지는 세부내역
연속 페이지에는 나타나지 않으므로 두 종류를 깔끔하게 구분할 수 있습니다.

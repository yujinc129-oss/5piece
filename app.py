import streamlit as st
import time
import json
from PIL import Image
from yolo_detector import run_yolo_model

# ergonomics_analyzer.py 파일에서 ErgonomicsAnalyzer 클래스를 가져옵니다.
# 중요: 이 파일을 실행하려면 같은 폴더에 ergonomics_analyzer.py 파일이 있어야 합니다.
from ergonomics_analyzer import ErgonomicsAnalyzer

# --------------------------------------------------------------------------
# Streamlit UI 구성
# --------------------------------------------------------------------------

# 페이지 기본 설정
st.set_page_config(
    page_title="인체공학 자세 분석 서비스",
    page_icon="🦾",
    layout="centered"
)

# --- 사이드바 (사용자 입력) ---
with st.sidebar:
    st.header("👤 사용자 정보 입력")
    user_height = st.number_input("키(cm)", min_value=100, max_value=250, value=175)
    gender = st.selectbox("성별", ["male", "female"])
    handedness = st.radio("주 사용 손", ["오른손잡이", "왼손잡이"])

    st.header("🖥️ 스크린 정보 입력")
    main_screen_inch = st.text_input("메인 스크린 크기 (인치)", value="27인치")

# --- 메인 페이지 ---
st.title("인체공학 자세 분석 서비스 🦾")
st.write("작업 환경 사진을 업로드하여 인체공학적 문제점을 분석하고 해결책을 받아보세요.")

uploaded_file = st.file_uploader(
    "분석할 사진을 여기에 업로드하세요.",
    type=['png', 'jpg', 'jpeg']
)

if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption="업로드된 이미지", use_column_width=True)

    # --- 1. YOLO 객체 감지 (시뮬레이션) ---
    with st.spinner("YOLO 모델로 객체를 감지하는 중... (현재는 예시 데이터 사용)"):
        time.sleep(2)  # YOLO 모델 실행 시간 시뮬레이션
        # 실제 구현:
        yolo_output = run_yolo_model(image)
        # yolo_output = [
        #     {'class': 'screen', 'box': {'x': 450, 'y': 450, 'width': 750, 'height': 422}},
        #     {'class': 'laptop', 'box': {'x': 1050, 'y': 650, 'width': 400, 'height': 250}},
        #     {'class': 'screen support', 'box': {'x': 450, 'y': 650, 'width': 300, 'height': 150}},
        #     {'class': 'keyboard', 'box': {'x': 550, 'y': 750, 'width': 450, 'height': 150}},
        #     {'class': 'mouse', 'box': {'x': 950, 'y': 780, 'width': 70, 'height': 100}},
        # ]
    st.success("객체 감지가 완료되었습니다. 분석할 메인 스크린을 선택해주세요.")

    # --- 2. 분석기 초기화 및 스크린 목록 가져오기 ---
    user_inputs = {
        "user_height_cm": user_height,
        "gender": gender,
        "handedness": handedness,
    }
    analyzer = ErgonomicsAnalyzer(yolo_output, user_inputs)
    available_screens = analyzer.detect_screens()

    if not available_screens:
        st.error("분석할 수 있는 스크린(screen, laptop)이 감지되지 않았습니다.")
    else:
        # --- 3. 사용자에게 메인 스크린 선택 UI 제공 ---
        st.subheader("🖥️ 메인 스크린 선택")
        # 선택 옵션 생성 (예: 'screen (screen_0)', 'laptop (screen_1)')
        screen_options = {f"{s['class']} (ID: {s['id']})": s['id'] for s in available_screens}
        selected_option = st.selectbox(
            "감지된 스크린 목록에서 주 사용 스크린을 선택하세요.",
            options=list(screen_options.keys())
        )

        # --- 4. 분석 시작 버튼 ---
        if st.button("선택한 스크린으로 자세 분석 시작하기"):
            with st.spinner("선택된 스크린을 기준으로 자세를 분석 중입니다..."):
                # 4-1. 사용자가 선택한 스크린을 메인 스크린으로 설정
                selected_id = screen_options[selected_option]
                analyzer.set_main_screen_by_id(selected_id, main_screen_inch)

                # 4-2. 실제 분석 실행
                report = analyzer.run_all_analyses()

                # 4-3. (가상) GPT에게 솔루션 요청
                # 실제 구현: solution_text = ask_gpt_for_solution(report)
                solution_text = f"""
                ###  종합 분석 결과 (메인 스크린: {selected_option})
                분석이 완료되었습니다. 주요 문제점과 해결책은 다음과 같습니다.

                (이 부분은 실제 GPT가 분석 리포트를 바탕으로 생성할 동적 결과입니다.)

                - **문제점 1**: ...
                - **문제점 2**: ...
                """

            # 4-4. 최종 결과 출력
            st.success("분석이 완료되었습니다!")
            st.markdown(solution_text)

            with st.expander("자세한 분석 리포트 보기 (JSON)"):
                st.json(report)


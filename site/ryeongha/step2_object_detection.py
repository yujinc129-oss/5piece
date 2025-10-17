# steps/step2_object_detection.py
import streamlit as st
from PIL import Image, ImageDraw
import time
from yolo_detector import run_yolo_model
from ergonomics_analyzer import ErgonomicsAnalyzer


def step2_object_detection(uploaded_file):
    """
    2단계: 사용자가 이미지를 업로드하고 YOLO로 객체 인식.
    - 감지된 객체들을 이미지 위에 표시
    - 스크린이 여러 개면 사용자에게 선택 UI 제공
    - 인치 입력란은 비워둔 상태로 제공
    """
    st.header("2️⃣ 책상 이미지 업로드 및 객체 인식")

    if uploaded_file is not None:
        # 원본 이미지 열기
        image = Image.open(uploaded_file)

        # --- YOLO 모델 실행 ---
        with st.spinner("YOLO 모델로 객체 인식 중입니다..."):
            time.sleep(2)
            yolo_output = run_yolo_model(uploaded_file)

        st.success("✅ 객체 인식이 완료되었습니다!")

        # --- 감지된 객체 시각화 ---
        vis_image = image.copy()
        draw = ImageDraw.Draw(vis_image)

        for i, obj in enumerate(yolo_output):
            x, y, w, h = obj['box']['x'], obj['box']['y'], obj['box']['width'], obj['box']['height']
            left = x - w / 2
            top = y - h / 2
            right = x + w / 2
            bottom = y + h / 2
            label = f"{obj['class']} ({i})"

            # 박스 그리기 (빨간색)
            draw.rectangle([left, top, right, bottom], outline="red", width=3)
            draw.text((left, top - 15), label, fill="red")

        st.image(vis_image, caption="🔍 감지된 객체 (번호 포함)", use_column_width=True)

        # --- 감지된 객체 리스트 출력 ---
        st.markdown("### 감지된 객체 목록")
        for i, obj in enumerate(yolo_output):
            st.write(f"**{i+1}. {obj['class']}** — 좌표(x:{obj['box']['x']}, y:{obj['box']['y']})")

        # --- 스크린 감지 및 선택 ---
        analyzer = ErgonomicsAnalyzer(yolo_output, user_inputs={})
        screens = analyzer.detect_screens()

        if not screens:
            st.error("❌ 스크린(모니터 또는 노트북)이 감지되지 않았습니다.")
            return None

        # 스크린 여러 개 감지된 경우 선택
        if len(screens) == 1:
            selected_screen = screens[0]
            st.info(f"🖥️ 하나의 스크린({selected_screen['class']})이 감지되어 자동으로 선택됩니다.")
            selected_id = selected_screen["id"]
        else:
            st.subheader("🖥️ 메인 스크린 선택")
            screen_options = {f"{s['class']} (ID: {s['id']})": s['id'] for s in screens}
            selected_option = st.selectbox("감지된 스크린 중 메인 스크린을 선택하세요.", list(screen_options.keys()))
            selected_id = screen_options[selected_option]

        # --- 인치 입력 (기본값 없이 비어 있음) ---
        main_screen_inch = st.text_input("📏 메인 스크린 크기 (예: 27)", value="", placeholder="예: 24, 27 등 숫자만 입력")

        # --- 분석 시작 ---
        if st.button("선택 완료 후 분석 시작"):
            if not main_screen_inch.strip():
                st.warning("⚠️ 인치 크기를 입력해주세요.")
                return None

            st.success(f"✅ {main_screen_inch}인치 메인 스크린 선택 완료!")
            return {
                "screen_id": selected_id,
                "inch": main_screen_inch,
                "yolo_output": yolo_output
            }

    return None

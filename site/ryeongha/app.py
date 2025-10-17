import streamlit as st
import time
from PIL import Image, ImageDraw
from yolo_detector import run_yolo_model
from ergonomics_analyzer import ErgonomicsAnalyzer

# --------------------------------------------------------------------------
# Streamlit UI 구성
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="인체공학 자세 분석 서비스",
    page_icon="🦾",
    layout="centered"
)

# --- 사이드바 ---
with st.sidebar:
    st.header("👤 사용자 정보 입력")
    user_height = st.number_input("키(cm)", min_value=100, max_value=250, value=175)
    gender = st.selectbox("성별", ["male", "female"])
    handedness = st.radio("주 사용 손", ["오른손잡이", "왼손잡이"])

st.title("🦾 인체공학 자세 분석 서비스")
st.write("책상 사진을 업로드하면 YOLO 모델이 객체를 인식하고 인체공학적 분석 결과를 제공합니다.")

# --- 1️⃣ 파일 업로드 ---
uploaded_file = st.file_uploader("📸 분석할 책상 사진을 업로드하세요.", type=["png", "jpg", "jpeg"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="업로드된 이미지", use_container_width=True)

    # --- 2️⃣ YOLO 탐지 ---
    with st.spinner("YOLO 모델로 객체를 감지 중입니다..."):
        time.sleep(1)
        yolo_output = run_yolo_model(uploaded_file.getvalue())

    if not yolo_output:
        st.error("객체를 감지하지 못했습니다. 다른 이미지를 시도해주세요.")
        st.stop()

    # --- 3️⃣ YOLO 결과 시각화 ---
    image_with_boxes = image.copy()
    draw = ImageDraw.Draw(image_with_boxes)
    screen_objects = []

    for i, obj in enumerate(yolo_output):
        cls = obj.get("class", "").lower()
        if "screen" in cls or "laptop" in cls:
            box = obj["box"]
            x, y, w, h = box["x"], box["y"], box["width"], box["height"]
            x1, y1 = x - w / 2, y - h / 2
            x2, y2 = x + w / 2, y + h / 2

            draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=4)
            label = f"screen_{len(screen_objects)}"
            draw.text((x1 + 5, y1 + 5), label, fill="white")

            obj["id"] = label
            screen_objects.append(obj)

    if not screen_objects:
        st.error("스크린(screen/laptop)이 감지되지 않았습니다.")
        st.stop()

    st.image(image_with_boxes, caption="감지된 스크린 위치", use_container_width=True)
    st.info("이미지에서 빨간 박스를 참고하여 메인 스크린을 선택하세요.")

    # --- 4️⃣ 스크린 선택 ---
    screen_options = {f"{obj['id']} ({obj['class']})": obj['id'] for obj in screen_objects}
    selected_option = st.selectbox("🖥️ 메인 스크린 선택", list(screen_options.keys()))
    selected_id = screen_options[selected_option]

    # --- 5️⃣ 인치 입력 ---
    main_screen_inch = st.number_input("메인 스크린 인치 입력 (예: 27)", min_value=10.0, max_value=60.0, step=0.5)

    # --- 6️⃣ 분석 시작 버튼 ---
    if st.button("✅ 종합 분석 시작"):
        with st.spinner("선택된 스크린을 기준으로 자세를 분석 중입니다..."):
            time.sleep(1)

            user_inputs = {
                "user_height_cm": user_height,
                "gender": gender,
                "handedness": handedness,
            }

            analyzer = ErgonomicsAnalyzer(yolo_output, user_inputs)
            analyzer.set_main_screen_by_id(selected_id, main_screen_inch)
            report = analyzer.run_all_analyses()

        # --- 7️⃣ 결과 출력 ---
        st.success("🎯 종합 분석이 완료되었습니다!")

        solution_text = f"""
        ### 🧠 종합 분석 결과  
        **선택된 메인 스크린:** {selected_option}  
        **크기:** {main_screen_inch} 인치  

        주요 문제점과 개선 방향은 아래와 같습니다.
        (이 부분은 실제 GPT 분석 결과로 대체될 수 있습니다.)

        - **문제점 1:** 모니터 높이가 눈높이보다 낮음  
          👉 받침대 또는 높이 조절 스탠드 권장  
        - **문제점 2:** 조명 반사로 인한 시야 피로  
          👉 간접 조명 사용 및 모니터 각도 조정 권장
        """

        st.markdown(solution_text)

        with st.expander("📋 자세한 분석 리포트 보기 (JSON)"):
            st.json(report)

else:
    st.info("📸 책상 사진을 업로드하면 인체공학 분석을 시작할 수 있습니다.")

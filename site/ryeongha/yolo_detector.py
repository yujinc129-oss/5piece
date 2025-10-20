import streamlit as st
from inference_sdk import InferenceHTTPClient
import tempfile
import os
from PIL import Image, ImageDraw, ImageFont
import base64

st.set_page_config(page_title="🖼️ Roboflow 워크플로우 실행기", page_icon="🧠")
st.title("🖼️ Roboflow 워크플로우 실행기")

uploaded_file = st.file_uploader("분석할 이미지를 업로드하세요.", type=["jpg", "jpeg", "png"])

if uploaded_file:
    image = Image.open(uploaded_file).convert("RGB")
    st.image(image, caption="업로드된 이미지", use_column_width=True)

    client = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=st.secrets["ROBOFLOW_API_KEY"]
    )

    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
        temp_file.write(uploaded_file.getvalue())
        temp_path = temp_file.name

    st.info("✨ 객체를 감지하는 중입니다...")
    try:
        result = client.run_workflow(
            workspace_name="yujin-qkjrt",
            workflow_id="detect-count-and-visualize-14",
            images={"image": temp_path},
            use_cache=True
        )

        data = result[0]
        detections = data["predictions"]["predictions"]
        output_b64 = data.get("output_image")

        # 스크린 감지 결과 필터링
        screens = [obj for obj in detections if obj.get("class") in ["screen", "monitor", "laptop"]]

        if len(screens) > 1:
            st.warning(f"🖥️ 스크린이 {len(screens)}개 감지되었습니다. 메인 스크린을 선택해주세요.")

            # 이미지 복사
            draw_img = image.copy()
            draw = ImageDraw.Draw(draw_img, "RGBA")

            # 폰트 설정 (시스템 기본)
            try:
                font = ImageFont.truetype("arial.ttf", 40)
            except:
                font = ImageFont.load_default()

            # 각 스크린 번호 시각화
            for idx, obj in enumerate(screens):
                x, y, w, h = obj["x"], obj["y"], obj["width"], obj["height"]
                left, top = x - w / 2, y - h / 2
                right, bottom = x + w / 2, y + h / 2

                # 빨간 테두리
                draw.rectangle([left, top, right, bottom], outline="red", width=4)

                # 중앙 번호 표시
                num = str(idx + 1)
                # ✅ textbbox()로 텍스트 크기 계산 (버전 호환)
                try:
                    bbox = draw.textbbox((0, 0), num, font=font)
                    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                except AttributeError:
                    text_w, text_h = font.getsize(num)

                cx, cy = (left + right) / 2, (top + bottom) / 2
                bg_padding = 10
                draw.rectangle(
                    [cx - text_w/2 - bg_padding, cy - text_h/2 - bg_padding,
                     cx + text_w/2 + bg_padding, cy + text_h/2 + bg_padding],
                    fill=(255, 0, 0, 160)
                )
                draw.text((cx - text_w/2, cy - text_h/2), num, font=font, fill="white")

            st.image(draw_img, caption="감지된 스크린 번호 표시", use_column_width=True)

            selected_idx = st.radio(
                "메인 스크린 번호를 선택하세요:",
                options=[i + 1 for i in range(len(screens))],
                horizontal=True
            )
            main_screen = screens[selected_idx - 1]

        elif len(screens) == 1:
            main_screen = screens[0]
            st.info("✅ 스크린이 1개 감지되어 자동으로 선택되었습니다.")
        else:
            st.error("❌ 스크린 또는 랩탑 객체가 감지되지 않았습니다.")
            main_screen = None

        # ---------------------------------------------------------
        # 2️⃣ 메인 스크린 인치 입력
        # ---------------------------------------------------------
        if main_screen:
            monitor_inch = st.number_input(
                "메인 스크린의 인치를 입력하세요 (예: 27)",
                min_value=5.0,
                max_value=60.0,
                value=27.0,
                step=0.5
            )
            st.success(f"📏 선택된 스크린 인치: {monitor_inch} inch")

        # ---------------------------------------------------------
        # 3️⃣ 결과 숨김 (GPT 분석용 내부 저장)
        # ---------------------------------------------------------
        if st.button("👉 다음 단계로 진행 (GPT 분석 준비)"):
            st.session_state["workflow_result"] = result
            st.session_state["main_screen"] = main_screen
            st.session_state["monitor_inch"] = monitor_inch
            st.success("✅ 내부 데이터 저장 완료 (GPT 분석 준비 완료)")
            st.info("(JSON 결과는 화면에 표시되지 않습니다.)")

        # ---------------------------------------------------------
        # 4️⃣ (선택) Roboflow 시각화 결과 표시
        # ---------------------------------------------------------
        if output_b64:
            st.image(base64.b64decode(output_b64), caption="📊 Roboflow 시각화 결과", use_column_width=True)

    except Exception as e:
        st.error(f"🚨 오류가 발생했습니다: {e}")
    finally:
        os.remove(temp_path)

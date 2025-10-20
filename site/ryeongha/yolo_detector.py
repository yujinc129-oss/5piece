import streamlit as st
from inference_sdk import InferenceHTTPClient
import tempfile  # 임시 파일을 만들기 위해 import 합니다.
import os
from PIL import Image

# 1. Streamlit UI 설정
st.title("🖼️ Roboflow 워크플로우 실행기")

# 사용자가 이미지를 업로드할 수 있는 UI 생성
uploaded_file = st.file_uploader("분석할 이미지를 업로드하세요.", type=["jpg", "jpeg", "png"])

# 파일이 업로드 되었을 경우에만 아래 로직 실행
if uploaded_file is not None:
    # 업로드한 이미지 보여주기
    image = Image.open(uploaded_file)
    st.image(image, caption="업로드된 이미지", use_column_width=True)

    # 2. Roboflow 클라이언트 연결
    # 실제 API 키로 바꿔주세요.
    # st.secrets를 사용하는 것을 권장합니다.
    API_KEY = "vaDWLHeVR12STEpWlcpB"

    client = InferenceHTTPClient(
        api_url="https://serverless.roboflow.com",
        api_key=API_KEY
    )

    # 3. 업로드된 파일을 임시 파일로 저장하고 경로 얻기
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
        # 업로드된 파일의 내용을 바이트로 읽어서 임시 파일에 씁니다.
        temp_file.write(uploaded_file.getvalue())
        temp_file_path = temp_file.name  # 임시 파일의 경로를 저장합니다.

    # 4. 워크플로우 실행
    st.write("✨ 모델을 실행하여 분석 중입니다...")
    try:
        result = client.run_workflow(
            workspace_name="yujin-qkjrt",
            workflow_id="detect-count-and-visualize-14",
            images={
                # image 경로에 하드코딩된 파일 이름 대신 임시 파일 경로를 사용합니다.
                "image": temp_file_path
            },
            use_cache=True
        )

        # 5. 결과 출력
        st.success("분석이 완료되었습니다!")
        st.json(result)  # 결과를 깔끔한 JSON 형태로 출력

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")

    finally:
        # 6. 임시 파일 삭제
        # 작업이 끝나면 서버에 임시 파일이 남지 않도록 삭제합니다.
        os.remove(temp_file_path)
else:
    st.info("📸 책상 사진을 업로드하면 인체공학 분석을 시작할 수 있습니다.")

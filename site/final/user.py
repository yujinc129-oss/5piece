import streamlit as st


def user_info_form():
    """
    Streamlit 앱에 사용자 정보 입력 폼을 표시하고,
    제출된 정보를 딕셔너리로 반환하는 함수.
    정보가 아직 제출되지 않았으면 None을 반환합니다.
    """
    # session_state에 사용자 정보가 없으면 None으로 초기화합니다.
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None

    # 1. 정보가 이미 제출된 경우, 결과를 표시합니다.
    if st.session_state.user_info:
        st.success("정보가 성공적으로 제출되었습니다!")
        st.subheader("📊 입력된 정보 요약")

        # 대시보드 카드 형태로 결과 표시
        col1, col2, col3 = st.columns(3)
        col1.metric("성별", st.session_state.user_info['gender'])
        col2.metric("키", f"{st.session_state.user_info['height']} cm")
        col3.metric("주 사용 손", st.session_state.user_info['dominant_hand'])

        st.markdown("---")
        # 정보를 다시 입력할 수 있는 버튼 제공
        if st.button("정보 다시 입력하기"):
            st.session_state.user_info = None
            st.rerun()

    # 2. 아직 정보가 제출되지 않은 초기 상태에서는 입력 폼을 바로 표시합니다.
    else:
        with st.form(key='user_info_form'):
            st.subheader("📄 사용자 정보를 입력해주세요")

            # --- 입력 항목 ---
            col1, col2 = st.columns(2)
            with col1:
                gender = st.radio(
                    label="**성별**",
                    options=('여성', '남성'),
                    horizontal=True,
                    key='gender_dialog'
                )
            with col2:
                height = st.number_input(
                    label="**키 (신장)**",
                    min_value=100,
                    max_value=250,
                    value=165,
                    step=1,
                    key='height_dialog'
                )

            st.subheader("⚙️ 작업 환경")
            dominant_hand = st.radio(
                label="**주 사용 손**",
                options=('오른손', '왼손'),
                horizontal=True,
                key='hand_dialog'
            )

            # 폼 제출 버튼
            submitted = st.form_submit_button('제출하기')

            if submitted:
                # 제출 버튼이 눌리면, 입력된 정보를 session_state에 저장합니다.
                st.session_state.user_info = {
                    "gender": gender,
                    "height": height,
                    "dominant_hand": dominant_hand
                }
                st.rerun()  # 화면을 즉시 새로고침하여 결과를 표시합니다.

    # 최종적으로 저장된 사용자 정보를 반환합니다.
    return st.session_state.user_info


# --- 이 파일을 직접 실행했을 때만 아래 코드가 동작합니다 ---
# 다른 파일에서 이 파일을 import할 때는 아래 부분이 실행되지 않습니다.
if __name__ == "__main__":
    st.set_page_config(layout="wide")
    st.title("사용자 정보 입력 모듈 테스트")

    # 함수를 호출하여 UI를 렌더링하고 사용자 정보를 받습니다.
    user_data = user_info_form()

    # # 함수가 정보를 반환했을 때 (제출 완료 후) 추가 로직을 실행할 수 있습니다.
    # if user_data:
    #     st.markdown("---")
    #     st.write("메인 앱에서 반환된 사용자 정보를 확인합니다:")
    #     st.json(user_data)

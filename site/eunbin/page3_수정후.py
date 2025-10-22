# pages/page3.py
import streamlit as st


def user_info_form():
    # user_info 세션이 없으면 None으로 초기화
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None

    if st.session_state.user_info:
        # --- 2. 정보 요약 화면 (user_info가 있을 때) ---
        st.success("정보가 확인되었습니다.")
        st.subheader("📊 입력된 정보 요약")

        col1, col2, col3 = st.columns(3)
        col1.metric("성별", st.session_state.user_info.get('gender', "-"))
        col2.metric("키", f"{st.session_state.user_info.get('height', '-')} cm")
        col3.metric("주 사용 손", st.session_state.user_info.get('dominant_hand', "-"))
        st.markdown("---")

        st.info("입력된 정보가 맞다면, 하단의 '인체공학 보고서 받기' 버튼을 눌러 분석을 시작하세요.")

        if st.button("정보 다시 입력하기"):
            st.session_state.user_info = None
            # 위젯에 남아있는 값도 초기화
            st.session_state.pop("gender_input", None)
            st.session_state.pop("height_input", None)
            st.session_state.pop("hand_input", None)
            st.rerun()
    else:
        # --- 1. 정보 입력 화면 (user_info가 없을 때) ---
        st.subheader("📄 사용자 정보를 입력해주세요")

        col1, col2 = st.columns(2)
        with col1:
            # `key`를 지정하여 final_app.py에서 값을 읽을 수 있게 함
            st.radio("성별",
                     options=('여성', '남성'),
                     horizontal=True,
                     key="gender_input")  # key 추가
        with col2:
            st.number_input("키 (신장, cm)",
                            min_value=100,
                            max_value=250,
                            value=165,  # 기본값
                            step=1,
                            key="height_input")  # key 추가

        st.radio("주 사용 손",
                 options=('오른손', '왼손'),
                 horizontal=True,
                 key="hand_input")  # key 추가

        st.info("정보를 입력한 뒤, 하단의 '입력 완료' 버튼을 눌러주세요.")

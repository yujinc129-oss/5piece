# steps/screen_selector.py
import streamlit as st

def select_main_screen(analyzer):
    """
    감지된 화면 목록 중 메인 스크린을 선택하고 인치를 입력받는 UI 함수.

    Args:
        analyzer (ErgonomicsAnalyzer): YOLO 감지 결과로 초기화된 분석기 객체

    Returns:
        dict: 사용자가 선택한 스크린 정보 및 인치값 { "screen_id": ..., "screen_label": ..., "inch": ... }
              선택 완료 전에는 None 반환
    """

    available_screens = analyzer.detect_screens()

    if not available_screens:
        st.error("화면(screen, laptop)이 감지되지 않았습니다.")
        return None

    st.subheader("🖥️ 메인 스크린 선택")

    # 선택박스 구성
    screen_options = {
        f"{s['class']} (ID: {s['id']})": s['id']
        for s in available_screens
    }

    selected_option = st.selectbox(
        "감지된 화면 중에서 메인 스크린을 선택하세요:",
        options=list(screen_options.keys())
    )
    selected_id = screen_options[selected_option]

    # 인치 입력
    main_screen_inch = st.number_input(
        "선택한 스크린의 인치 크기를 입력하세요 (예: 27)",
        min_value=10.0,
        max_value=60.0,
        step=0.5
    )

    # 선택 완료
    if st.button("✅ 메인 스크린 선택 완료"):
        st.session_state["main_screen"] = selected_option
        st.session_state["screen_inch"] = main_screen_inch
        st.success(f"메인 스크린이 설정되었습니다: {selected_option} ({main_screen_inch}인치)")
        return {
            "screen_id": selected_id,
            "screen_label": selected_option,
            "inch": main_screen_inch
        }

    return None

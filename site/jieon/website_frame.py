# -*- coding: utf-8 -*-
"""
인체공학적 책상 개선 가이드 서비스 (Streamlit 기반)
작성자: Copilot
설명: 사용자 입력 기반 분석 파이프라인을 시뮬레이션하고 결과를 출력합니다.
실행 방법: PyCharm에서 'streamlit run <파일명.py>' 명령어로 실행
"""

import streamlit as st
import time
import json

# ==============================================================================
# 1. 사용자 입력 클래스 정의
# ==============================================================================

class UserAnalysis:
    def __init__(self, monitor_size=24, height_cm=170):
        self.monitor_size = monitor_size
        self.height_cm = height_cm

    def to_dict(self):
        return {
            "monitor_size": self.monitor_size,
            "height_cm": self.height_cm
        }

# ==============================================================================
# 2. MOCKING 및 HELPER 함수
# ==============================================================================

def mock_run_analysis_pipeline(user_analysis: UserAnalysis):
    monitor_size = user_analysis.monitor_size
    height_cm = user_analysis.height_cm

    if monitor_size >= 27 and height_cm >= 175:
        result = "✅ 현재 책상 구성은 대체로 인체공학적 기준에 적합합니다."
    else:
        result = "⚠️ 책상 높이 또는 모니터 크기 조정이 필요할 수 있습니다."

    report = {
        "monitor_size": monitor_size,
        "height_cm": height_cm,
        "recommendation": result,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    return result, report

def go_to_page(page_num):
    st.session_state['current_page'] = page_num
    st.rerun()

def handle_retry():
    st.session_state['current_page'] = 1
    st.session_state['user_analysis'] = UserAnalysis()
    st.session_state['analysis_result'] = None
    st.session_state['detailed_report'] = None
    st.rerun()

# ==============================================================================
# 3. 페이지 콘텐츠 구현
# ==============================================================================

def page1_content():
    st.image("https://via.placeholder.com/600x200.png?text=Ergonomic+Desk+Guide")
    st.subheader("📐 인체공학적 책상 개선 가이드")
    st.markdown("""
        이 서비스는 사용자의 책상 환경과 신체 정보를 기반으로
        인체공학적 개선 가이드를 제공합니다.
    """)

def page2_content():
    st.subheader("🖥️ 책상 및 모니터 정보 입력")
    monitor_size = st.slider("모니터 크기 (inch)", 19, 49, 27)
    st.session_state['user_analysis'].monitor_size = monitor_size

def page3_content():
    st.subheader("🧍 사용자 신체 정보 입력")
    height_cm = st.number_input("신장 (cm)", min_value=100, max_value=220, value=175)
    st.session_state['user_analysis'].height_cm = height_cm

def page5_content(final_result, detailed_report):
    st.subheader("📊 분석 결과")
    st.success(final_result)
    st.markdown("### 📋 상세 리포트")
    st.json(detailed_report)

# ==============================================================================
# 4. 페이지 흐름 제어
# ==============================================================================

def page1_opening():
    page1_content()
    st.markdown("---")
    if st.button("Start Analysis (P2로 이동)", key="start_p1", use_container_width=True):
        go_to_page(2)

def page2_input_desk_info():
    page2_content()
    st.markdown("---")
    if st.button("Next > (P3로 이동)", key="next_p2", use_container_width=True):
        go_to_page(3)

def page3_input_user_info():
    page3_content()
    st.markdown("---")
    col_return, col_next = st.columns(2)
    with col_return:
        if st.button("< Return (P2로 회귀)", key="return_p3", use_container_width=True):
            go_to_page(2)
    with col_next:
        if st.button("Analyze Desk > (P4로 이동)", key="next_p3", use_container_width=True):
            go_to_page(4)

def page4_analysis_in_progress():
    st.header("Page 4: ⏱️ 분석 진행 중...")
    st.info("분석 파이프라인 실행 중입니다. 완료 시 P5로 자동 전환됩니다.")
    st.image("https://via.placeholder.com/600x200.png?text=Analyzing...")

    with st.spinner("분석 중..."):
        time.sleep(2)
        final_solution_text, analysis_report = mock_run_analysis_pipeline(st.session_state['user_analysis'])
        st.success("분석이 완료되었습니다!")
        time.sleep(1)

    st.session_state['analysis_result'] = final_solution_text
    st.session_state['detailed_report'] = analysis_report
    go_to_page(5)

def page5_result():
    final_result = st.session_state.get('analysis_result', "분석 결과를 불러올 수 없습니다.")
    detailed_report = st.session_state.get('detailed_report', {"error": "No report found"})
    page5_content(final_result, detailed_report)
    st.markdown("---")
    if st.button("Retry Service (P1로 초기화)", key="retry_p5", use_container_width=True):
        handle_retry()

# ==============================================================================
# 5. Streamlit 초기 설정 및 메인 루프
# ==============================================================================

st.set_page_config(
    page_title="인체공학적 책상 개선 가이드",
    page_icon="🦾",
    layout="centered"
)

st.title("🦾 인체공학적 책상 개선 가이드 서비스")
st.markdown("---")

if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 1
if 'user_analysis' not in st.session_state:
    st.session_state['user_analysis'] = UserAnalysis()
if 'analysis_result' not in st.session_state:
    st.session_state['analysis_result'] = None
if 'detailed_report' not in st.session_state:
    st.session_state['detailed_report'] = None

def display_page():
    page = st.session_state['current_page']
    if page == 1:
        page1_opening()
    elif page == 2:
        page2_input_desk_info()
    elif page == 3:
        page3_input_user_info()
    elif page == 4:
        page4_analysis_in_progress()
    elif page == 5:
        page5_result()

display_page()

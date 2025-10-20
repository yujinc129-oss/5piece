import streamlit as st
import json
import time
import openai  # GPT API 사용을 위해 추가


# -------------------------------------------------------------------
# 1. 인체공학 규칙 엔진 및 프롬프트 생성기
# -------------------------------------------------------------------

def apply_ergonomic_guidelines(analysis_result):
    """
    YOLO가 분석한 이미지 결과(JSON)를 입력받아,
    인체공학적 문제점 리스트를 반환하는 함수 (규칙 엔진).

    참고: 원본 코드를 그대로 사용하되, 입력 형식을
    st.session_state['user_analysis']['yolo_result']에 맞게 가정합니다.
    """
    problems = []

    try:
        # JSON 데이터 파싱 (입력 형식이 리스트라고 가정)
        image_info = analysis_result[0]
        predictions = image_info['predictions']['predictions']
        image_width = image_info['predictions']['image']['width']

        # 감지된 객체들을 클래스별로 정리
        detected_objects = {}
        for obj in predictions:
            class_name = obj['class']
            if class_name not in detected_objects:
                detected_objects[class_name] = []

            # 정규화된 x 좌표 계산
            obj['x_center_norm'] = obj['x'] / image_width
            detected_objects[class_name].append(obj)

        # --- 규칙 적용 ---

        # 규칙 1: 모니터(screen)가 중앙에 있는가?
        if 'screen' in detected_objects:
            for screen in detected_objects['screen']:
                if not (0.4 < screen['x_center_norm'] < 0.6):
                    problems.append("일부 모니터가 중앙에 배치되지 않음")
                    break

        # 규칙 2: 듀얼 모니터를 사용하는가?
        if 'screen' in detected_objects and len(detected_objects['screen']) > 1:
            problems.append("듀얼 모니터 사용 중")

        # 규칙 3: 손목 받침대(wrist rest)가 있는가?
        if 'wrist rest' in detected_objects:
            problems.append("손목 받침대가 감지됨")

        # (여기에 KOSHA 가이드라인을 바탕으로 더 많은 규칙을 추가할 수 있습니다)

    except (KeyError, IndexError, TypeError) as e:
        st.error(f"YOLO 결과 파싱 오류: {e}. 입력 데이터 형식을 확인하세요.")
        return [f"분석 결과(JSON)의 형식이 잘못되었습니다: {e}"]

    return problems if problems else ["발견된 문제점 없음"]


def generate_gpt_prompt(user_data, problems):
    """
    사용자 정보(user_data)와 분석된 문제점(problems)을 결합하여
    GPT에게 전달할 최종 프롬프트를 생성하는 함수.
    """
    # GPT가 더 잘 이해할 수 있도록 정보를 문자열로 변환
    user_data_str = json.dumps(user_data, ensure_ascii=False, indent=2)
    problems_str = str(problems)

    prompt = f"""
    # ROLE (역할)
    너는 세계 최고의 인체공학 컨설턴트다. 너의 임무는 사용자의 건강과 생산성을 높이기 위해, 데이터를 기반으로 한 개인 맞춤형 책상 배치 솔루션을 제공하는 것이다.

    # CONTEXT (맥락)
    아래 [사용자 정보]와 AI가 사진을 분석하여 찾아낸 [발견된 문제점]을 반드시 참고해야 한다.

    [사용자 정보]:
    {user_data_str}

    [발견된 문제점]:
    {problems_str}

    # TASK (임무)
    위 정보를 종합하여, 이 사용자만을 위한 종합적인 개선 방안을 단계별로 작성해줘.
    각 문제점에 대해 아래 3가지 내용을 반드시 포함해서 설명해줘.
    1. **왜 문제인가?**: 이 배치가 어떤 나쁜 자세(예: 거북목)를 유발하고 건강에 왜 안 좋은지 설명.
    2. **어떻게 해결해야 하는가?**: 사용자가 즉시 따라 할 수 있는 구체적인 행동 지침을 제시.
    3. **기대 효과는 무엇인가?**: 해결책을 따랐을 때 어떤 좋은 자세가 되며 어떤 통증이 예방되는지 설명.

    '듀얼 모니터 사용 중' 이라는 문제점에는 두 모니터의 높이와 간격을 맞추는 방법에 대해 조언하고,
    '손목 받침대가 감지됨' 이라는 정보에는 손목 받침대의 올바른 사용법에 대해 조언해줘.

    # FORMAT (형식)
    - 전체적으로 친절하고 격려하는 전문가의 톤을 유지해줘.
    - Markdown을 사용해서 제목, 부제목, 글머리 기호로 가독성 좋게 정리해줘.
    """
    return prompt


# -------------------------------------------------------------------
# 2. Streamlit 페이지 전환 및 분석 로직
# -------------------------------------------------------------------

def go_to_page(page_number):
    """Streamlit 페이지 전환을 위한 예시 함수"""
    st.session_state['page'] = page_number
    st.rerun()  # 페이지 즉시 새로고침


def handle_retry():
    """서비스 재시작(초기화)을 위한 예시 함수"""
    # 세션 상태의 주요 값들을 초기화합니다.
    keys_to_clear = ['user_analysis', 'analysis_result', 'detailed_report']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    go_to_page(1)  # 1번 페이지로 이동


def call_gpt_api_with_prompt(prompt):
    """
    생성된 프롬프트를 바탕으로 실제 OpenAI API를 호출하는 함수 (예시)
    """
    try:
        # Streamlit Secrets에서 API 키 가져오기
        api_key = st.secrets["OPENAI_API_KEY"]
        if not api_key:
            return "오류: OpenAI API 키가 설정되지 않았습니다. (st.secrets)"

        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4-turbo",  # 또는 "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a helpful ergonomic consultant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    except openai.AuthenticationError:
        st.error("OpenAI API 키가 유효하지 않습니다.")
        return "오류: OpenAI API 키 인증에 실패했습니다."
    except Exception as e:
        st.error(f"GPT API 호출 중 오류 발생: {e}")
        return f"오류: AI 권장사항 생성에 실패했습니다. ({e})"


def run_analysis_pipeline(user_analysis_data):
    """
    Mock 함수를 대체하는 실제 분석 파이프라인.
    YOLO 결과로 규칙 엔진을 돌리고, 기본 리포트를 생성합니다.
    """
    # 1. 입력 데이터 분리
    user_data = user_analysis_data.get('user_data', {})
    yolo_result = user_analysis_data.get('yolo_result', [])

    if not yolo_result:
        return "분석 오류", {"error": "YOLO 결과가 없습니다."}

    # 2. 인체공학 규칙 엔진 실행
    identified_problems = apply_ergonomic_guidelines(yolo_result)

    # 3. 최종 리포트 생성 (Page 5에서 JSON으로 표시될 내용)
    analysis_report = {
        "userInfo": user_data,
        "problemsFound": identified_problems,
        "rawYoloData": yolo_result[0] if yolo_result else {}
    }

    # 4. 기본 결과 텍스트 생성 (GPT를 건너뛸 경우 표시될 내용)
    if identified_problems == ["발견된 문제점 없음"]:
        final_solution_text = "🎉 기본 인체공학 분석 결과, 특별한 문제점이 발견되지 않았습니다. 좋은 자세를 유지하고 계십니다!"
    else:
        problems_str = ", ".join(identified_problems)
        final_solution_text = f"기본 인체공학 분석이 완료되었습니다. 총 {len(identified_problems)}개의 개선점을 발견했습니다: [ {problems_str} ]. AI 권장사항을 통해 자세한 해결책을 확인해 보세요."

    return final_solution_text, analysis_report


def get_gpt_recommendation_from_report(detailed_report):
    """
    Mock 함수를 대체하는 실제 GPT 호출 함수.
    상세 리포트를 바탕으로 프롬프트를 생성하고 API를 호출합니다.
    """
    # 1. 리포트에서 GPT 프롬프트 생성에 필요한 정보 추출
    user_data = detailed_report.get('userInfo', {})
    problems = detailed_report.get('problemsFound', [])

    if not problems:
        return "AI 권장사항을 생성할 필요가 없습니다. 발견된 문제점이 없습니다."

    # 2. GPT 프롬프트 생성
    final_prompt = generate_gpt_prompt(user_data, problems)

    # 3. GPT API 호출
    gpt_response = call_gpt_api_with_prompt(final_prompt)

    return gpt_response


# -------------------------------------------------------------------
# 3. Streamlit 페이지 정의
# -------------------------------------------------------------------

def page4_analysis_in_progress():
    st.header("Page 4: ⏱️ 분석 진행 중...")
    st.info("분석 파이프라인 실행 중입니다. 완료 시 P5로 자동 전환됩니다.")
    st.image("https://via.placeholder.com/600x200.png?text=Analyzing...")

    # st.session_state에 'analysis_result'가 이미 있으면 이 페이지를 스킵
    if 'analysis_result' in st.session_state:
        st.warning("이미 분석이 완료되었습니다. 결과 페이지(P5)로 이동합니다.")
        time.sleep(1)
        go_to_page(5)
        return

    with st.spinner("기본 인체공학 분석 중... (규칙 엔진 실행)"):
        time.sleep(1)  # 시각적 효과를 위한 최소 대기

        # 'user_analysis' 세션 데이터가 있는지 확인
        if 'user_analysis' not in st.session_state:
            st.error("분석할 데이터가 없습니다. P1부터 다시 시작해주세요.")
            if st.button("P1으로 돌아가기"):
                handle_retry()
            return

        # ★★★ 핵심 실행 ★★★
        # 실제 분석 파이프라인 (run_analysis_pipeline) 호출
        final_solution_text, analysis_report = run_analysis_pipeline(st.session_state['user_analysis'])

        st.success("기본 분석이 완료되었습니다!")
        time.sleep(0.5)

    # 세션 상태에 결과 저장
    st.session_state['analysis_result'] = final_solution_text  # 기본 결과 (GPT 건너뛸 시 사용)
    st.session_state['detailed_report'] = analysis_report  # 상세 리포트 (GPT 생성 및 P5 표시에 사용)

    st.markdown("---")
    st.info("원하면 AI(GPT) 권장사항을 생성할 수 있습니다. API 키가 설정되어 있어야 작동합니다.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("생성: AI 권장사항 받기 (P5로 이동)", key="gpt_generate", use_container_width=True):
            with st.spinner("AI 권장사항 생성 중... (GPT API 호출)"):
                
                # ★★★ 핵심 실행 ★★★
                # 실제 GPT 호출 (get_gpt_recommendation_from_report)
                gpt_text = get_gpt_recommendation_from_report(st.session_state['detailed_report'])

                # AI가 생성한 텍스트로 'analysis_result'를 덮어씁니다.
                st.session_state['analysis_result'] = gpt_text

            st.success("AI 권장사항 생성 완료!")
            time.sleep(0.5)
            go_to_page(5)

    with col2:
        if st.button("건너뛰기: 기본 결과만 보기 (P5로 이동)", key="skip_gpt", use_container_width=True):
            # 'analysis_result'에는 이미 기본 분석 결과가 저장되어 있으므로
            # 아무것도 할 필요 없이 5페이지로 이동합니다.
            go_to_page(5)


def page5_content():
    st.header("Page 5: 🔬 최종 분석 결과")

    # 세션 상태에서 결과 불러오기
    final_result = st.session_state.get('analysis_result', "분석 결과를 불러올 수 없습니다. P4에서 분석을 먼저 실행해주세요.")
    detailed_report = st.session_state.get('detailed_report', {"error": "상세 리포트를 찾을 수 없습니다."})

    st.subheader("📊 종합 솔루션")
    # AI 권장사항 또는 기본 분석 결과를 Markdown으로 표시
    st.markdown(final_result)

    st.markdown("---")

    # 상세 리포트 (JSON)는 확장기(expander) 안에 표시
    with st.expander("📋 상세 분석 리포트 보기 (JSON)"):
        st.json(detailed_report)

    st.markdown("---")

    if st.button("서비스 다시 이용하기 (P1로 초기화)", key="retry_p5", use_container_width=True):
        handle_retry()  # 세션 상태 초기화 및 P1로 이동


# -------------------------------------------------------------------
# 4. Streamlit 앱 실행 (메인 로직)
# -------------------------------------------------------------------

# 세션 상태 초기화 (페이지 관리용)
if 'page' not in st.session_state:
    st.session_state['page'] = 1  # 1페이지에서 앱 시작

# --- 테스트 데이터 블록 제거됨 ---
# P1, P2, P3 등 다른 페이지에서
# st.session_state['user_analysis'] = {'user_data': ..., 'yolo_result': ...}
# 와 같이 데이터를 채워주는 로직이 필요합니다.


# 페이지 라우팅
# (실제 앱에서는 P1, P2, P3에 대한 함수도 필요합니다)
if st.session_state['page'] == 1:
    # 예시: page1_content()
    st.title("Page 1: 사용자 정보 입력 (예시)")
    st.write("이곳에 P1 로직을 구현하세요.")
    if st.button("다음 (P2로 이동)"):
        go_to_page(2)
        
elif st.session_state['page'] == 2:
    # 예시: page2_content()
    st.title("Page 2: (예시)")
    st.write("이곳에 P2 로직을 구현하세요.")
    if st.button("다음 (P3로 이동)"):
        go_to_page(3)

elif st.session_state['page'] == 3:
    # 예시: page3_content()
    st.title("Page 3: 이미지 업로드 (예시)")
    st.write("이곳에 P3 로직 (이미지 업로드 및 YOLO 분석)을 구현하세요.")
    st.write("분석 완료 후 st.session_state['user_analysis']에 데이터를 저장해야 합니다.")
    if st.button("분석 시작 (P4로 이동)"):
        # P3에서 user_analysis 데이터가 준비되었다고 가정
        if 'user_analysis' not in st.session_state:
             st.session_state['user_analysis'] = {"user_data": {}, "yolo_result": []} # 임시 데이터
        go_to_page(4)

elif st.session_state['page'] == 4:
    page4_analysis_in_progress()

elif st.session_state['page'] == 5:
    page5_content()

else:
    st.error("알 수 없는 페이지입니다.")
    if st.button("P1으로 돌아가기"):
        go_to_page(1)

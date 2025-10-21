# -*- coding: utf-8 -*-
"""
인체공학적 책상 개선 가이드 (Streamlit) - 단일 파일 버전

- 모든 분석 로직과 Streamlit UI가 하나의 파일에 포함되어 있습니다.
- [수정] 5단계의 상세 분석 리포트를 사용자 친화적인 한글로 번역하여 보여줍니다.
- 4단계 분석 후 AI 조언까지 자동으로 생성하여 5단계에서 통합된 결과를 보여줍니다.
- 메타데이터 기반 페이지 로딩
- OpenAI GPT 연동 (환경변수 OPENAI_API_KEY 필요)
- 실행: streamlit run app.py
"""

# --------------------------------------------------------------------------
# 1. 기본 설정 및 라이브러리 임포트
# --------------------------------------------------------------------------
import os
import time
import logging
import json
import importlib
import math
import re
from typing import Optional, Tuple, Dict

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# 로깅 설정
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Streamlit secrets를 os.environ으로 복사
try:
    if "OPENAI_API_KEY" not in os.environ and st.secrets.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass


# --------------------------------------------------------------------------
# 2. OpenAI 연동 유틸리티
# --------------------------------------------------------------------------

def make_openai_client() -> Optional[OpenAI]:
    """OpenAI 클라이언트를 안전하게 생성합니다."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        logger.info("OPENAI_API_KEY가 설정되어 있지 않습니다.")
        return None
    try:
        return OpenAI(api_key=key)
    except Exception:
        logger.exception("OpenAI 클라이언트 생성 실패")
        return None


def extract_text_from_response(resp) -> str:
    """OpenAI 응답 객체에서 텍스트를 추출합니다."""
    try:
        if hasattr(resp, "choices") and len(resp.choices) > 0:
            return resp.choices[0].message.content.strip()
    except Exception:
        logger.exception("응답 파싱 중 오류")
    return "응답을 파싱할 수 없습니다."


# 전역 OpenAI 클라이언트
client: Optional[OpenAI] = make_openai_client()


# --------------------------------------------------------------------------
# 3. 인체공학 분석 엔진 (Ergonomics Analysis Engine)
# --------------------------------------------------------------------------

# 👤 3-1. 공통 헬퍼 함수 (Helper Functions)
def find_object(yolo_output, class_name):
    """YOLO 결과에서 특정 클래스의 첫 번째 객체를 반환 (없으면 None)"""
    return next((obj for obj in yolo_output if obj['class'] == class_name), None)


def get_object_side(obj_x, image_width):
    """객체의 X 좌표를 기준으로 화면 내 위치(왼쪽/오른쪽/중앙) 판단"""
    if obj_x < image_width / 3:
        return "left"
    elif obj_x > image_width * 2 / 3:
        return "right"
    else:
        return "center"


def _monitor_real_height_cm(inch, aspect_w=16, aspect_h=9):
    """모니터 인치와 화면비로 실제 모니터 세로 길이(cm)를 계산"""
    diag_cm = inch * 2.54
    return diag_cm * (aspect_h / math.sqrt(aspect_w ** 2 + aspect_h ** 2))


def parse_inch_from_string(size_str):
    """문자열에서 숫자(인치)를 파싱합니다. (예: "15.6인치" -> 15.6)"""
    size_str = str(size_str)  # 숫자형이 들어올 경우를 대비해 문자열로 변환
    if not isinstance(size_str, str): return None
    numbers = re.findall(r"(\d+\.?\d*)", size_str)
    return float(numbers[0]) if numbers else None


def calculate_ideal_screen_height(user_height_cm, user_gender):
    """사용자 키와 성별 기반 이상적인 화면 상단 높이(cm) 계산"""
    if user_gender == 'male':
        return ((3.32 * user_height_cm) - 25.50) / 10
    elif user_gender == 'female':
        return ((2.61 * user_height_cm) + 93.84) / 10
    else:
        return ((2.96 * user_height_cm) + 34.17) / 10


def check_proximity(upper_box, lower_box, threshold_px=100):
    """위쪽 객체가 아래쪽 객체 바로 위에 있는지 Y축 및 X축 기준으로 확인"""
    upper_bottom_y = upper_box['y'] + upper_box['height'] / 2
    lower_top_y = lower_box['y'] - lower_box['height'] / 2
    horizontal_distance = abs(upper_box['x'] - lower_box['x'])
    horizontal_alignment_threshold = (upper_box['width'] + lower_box['width']) / 4
    is_vertically_close = abs(upper_bottom_y - lower_top_y) < threshold_px
    is_horizontally_aligned = horizontal_distance < horizontal_alignment_threshold
    return is_vertically_close and is_horizontally_aligned


# 🧐 3-2. 인체공학 진단 분석 클래스 (ErgonomicsAnalyzer Class)
class ErgonomicsAnalyzer:
    def __init__(self, yolo_output, user_inputs, image_width_px=1280):
        self.yolo_output = yolo_output
        self.user_inputs = user_inputs
        self.image_width_px = image_width_px
        self.report = []
        self.severity_map = {"High": "High", "Moderate": "Moderate", "Low": "Low"}
        self.main_screen = None
        self.px_to_cm_ratio = None

    def _estimate_desk_y(self):
        """키보드, 마우스 등 책상 위 객체들의 하단 좌표 평균으로 책상 높이를 추정"""
        bottom_y_coords = []
        for class_name in ['keyboard', 'mouse', 'wrist_rest', 'monitor support']:
            obj = find_object(self.yolo_output, class_name)
            if obj:
                bottom_y_coords.append(obj['box']['y'] + obj['box']['height'] / 2)
        laptop = find_object(self.yolo_output, 'laptop')
        support = find_object(self.yolo_output, 'monitor support')
        if laptop and not (support and check_proximity(laptop['box'], support['box'])):
            bottom_y_coords.append(laptop['box']['y'] + laptop['box']['height'] / 2)
        return sum(bottom_y_coords) / len(bottom_y_coords) if bottom_y_coords else None

    def _analyze_screen_height(self, screen_obj, details={}):
        """스크린 객체의 높이를 분석하는 공통 로직"""
        if self.px_to_cm_ratio is None: return
        user_height_cm = self.user_inputs.get("user_height_cm")
        gender = self.user_inputs.get("gender")
        if not all([user_height_cm, gender]): return

        desk_y = self._estimate_desk_y() or (screen_obj['box']['y'] + screen_obj['box']['height'] / 2.0)
        ideal_height_cm = calculate_ideal_screen_height(user_height_cm, gender)
        screen_top_y = screen_obj['box']['y'] - screen_obj['box']['height'] / 2.0
        distance_px = desk_y - screen_top_y
        estimated_actual_height_cm = round(distance_px * self.px_to_cm_ratio, 1)
        delta = round(estimated_actual_height_cm - ideal_height_cm, 1)
        abs_delta = abs(delta)

        severity = self.severity_map["Low"]
        if abs_delta > 15:
            severity = self.severity_map["High"]
        elif abs_delta > 5:
            severity = self.severity_map["Moderate"]

        details.update({
            "delta_cm": delta, "ideal_height_cm": ideal_height_cm,
            "estimated_actual_height_cm": estimated_actual_height_cm
        })
        self.report.append(
            {"problem_id": f"{screen_obj['class'].upper()}_HEIGHT", "severity": severity, "details": details})

    def detect_screens(self):
        """감지된 모든 스크린 객체에 고유 ID를 부여하여 리스트로 반환"""
        screens = [obj for obj in self.yolo_output if obj['class'] in ['screen', 'laptop', 'monitor']]
        for i, screen in enumerate(screens):
            if 'id' not in screen:  # ID가 이미 부여되었다면 그대로 사용
                screen['id'] = f"screen_{i}"
        return screens

    def set_main_screen_by_id(self, screen_id, main_screen_inch_str):
        """ID와 인치 정보로 메인 스크린을 설정하고, px_to_cm_ratio를 계산"""
        screens = self.detect_screens()
        selected_screen = next((s for s in screens if s.get('id') == screen_id), None)

        if selected_screen and selected_screen.get('box'):
            self.main_screen = selected_screen
            self.user_inputs['main_screen_inch'] = main_screen_inch_str
            main_screen_inch = parse_inch_from_string(main_screen_inch_str)
            if main_screen_inch and self.main_screen['box']['height'] > 0:
                real_h_cm = _monitor_real_height_cm(main_screen_inch)
                self.px_to_cm_ratio = real_h_cm / self.main_screen['box']['height']
            return True
        return False

    def analyze_screen_setup(self):
        screen = find_object(self.yolo_output, "screen") or find_object(self.yolo_output, "monitor")
        if screen:
            support = find_object(self.yolo_output, 'monitor support')
            has_support = support and check_proximity(screen.get('box', {}), support.get('box', {}))
            self._analyze_screen_height(screen, {"has_support": bool(has_support)})

    def analyze_laptop_setup(self):
        laptop = find_object(self.yolo_output, "laptop")
        if laptop:
            support = find_object(self.yolo_output, 'monitor support')
            details = {
                "has_support": support and check_proximity(laptop.get('box', {}), support.get('box', {})),
                "has_external_keyboard": find_object(self.yolo_output, 'keyboard') is not None
            }
            self._analyze_screen_height(laptop, details)

    def analyze_wrist_rest(self):
        has_wrist_rest = find_object(self.yolo_output, "wrist_rest") is not None
        severity = self.severity_map["Low"] if has_wrist_rest else self.severity_map["High"]
        self.report.append(
            {"problem_id": "WRIST_REST_PRESENCE", "severity": severity, "details": {"has_wrist_rest": has_wrist_rest}})

    def analyze_light_position(self):
        lamp = find_object(self.yolo_output, "desk lamp")
        if not lamp: return
        handedness = self.user_inputs.get("handedness", "오른손잡이")
        lamp_side = get_object_side(lamp['box']['x'], self.image_width_px)
        is_misaligned = (handedness == "왼손잡이" and lamp_side == "left") or (
                handedness == "오른손잡이" and lamp_side == "right")
        severity = self.severity_map["Moderate"] if is_misaligned else self.severity_map["Low"]
        self.report.append({"problem_id": "LIGHT_POSITION", "severity": severity,
                            "details": {"handedness": handedness, "lamp_side": lamp_side}})

    def analyze_keyboard_mouse_distance(self):
        if self.px_to_cm_ratio is None: return
        keyboard = find_object(self.yolo_output, "keyboard")
        mouse = find_object(self.yolo_output, "mouse")
        gender = self.user_inputs.get("gender")
        if not all([keyboard, mouse, gender]): return
        distance_cm = abs(keyboard['box']['x'] - mouse['box']['x']) * self.px_to_cm_ratio
        threshold_cm = 15 if gender == 'male' else 10
        severity = self.severity_map["High"] if distance_cm > threshold_cm else self.severity_map["Low"]
        self.report.append({"problem_id": "KEYBOARD_MOUSE_DISTANCE", "severity": severity,
                            "details": {"actual_distance_cm": round(distance_cm, 1), "threshold_cm": threshold_cm}})

    def analyze_keyboard_mouse_alignment(self):
        keyboard = find_object(self.yolo_output, "keyboard")
        mouse = find_object(self.yolo_output, "mouse")
        if not all([keyboard, mouse]): return
        kbd_box = keyboard['box']
        mouse_center_y = mouse['box']['y']
        ky_min = kbd_box['y'] - kbd_box['height'] / 2
        ky_max = kbd_box['y'] + kbd_box['height'] / 2
        is_vertically_aligned = (ky_min <= mouse_center_y <= ky_max)
        severity = self.severity_map["Moderate"] if not is_vertically_aligned else self.severity_map["Low"]
        self.report.append({"problem_id": "KEYBOARD_MOUSE_ALIGNMENT", "severity": severity,
                            "details": {"is_vertically_aligned": is_vertically_aligned}})

    def analyze_window_position(self):
        if self.main_screen is None or self.px_to_cm_ratio is None: return
        window = find_object(self.yolo_output, "window")
        if not window: return
        horizontal_distance_px = abs(self.main_screen['box']['x'] - window['box']['x'])
        horizontal_distance_cm = round(horizontal_distance_px * self.px_to_cm_ratio, 1)
        severity = self.severity_map["Moderate"] if horizontal_distance_cm <= 50 else self.severity_map["Low"]
        self.report.append({"problem_id": "WINDOW_POSITION", "severity": severity,
                            "details": {"horizontal_distance_cm": horizontal_distance_cm}})

    def analyze_viewing_distance_by_ratio(self):
        if not self.main_screen: return
        ratio = self.main_screen['box']['width'] / self.image_width_px
        severity = self.severity_map["Low"]
        if ratio > 0.50:
            severity = self.severity_map["High"]
        elif ratio < 0.40:
            severity = self.severity_map["Moderate"]
        self.report.append({"problem_id": "VIEWING_DISTANCE", "severity": severity,
                            "details": {"main_screen_type": self.main_screen['class'],
                                        "screen_width_ratio": f"{ratio:.1%}"}})

    def run_all_analyses(self):
        """모든 분석을 순차적으로 실행합니다."""
        if not self.main_screen:
            raise ValueError("메인 스크린이 설정되지 않았습니다. set_main_screen_by_id()를 먼저 호출해주세요.")

        self.analyze_screen_setup()
        self.analyze_laptop_setup()
        self.analyze_wrist_rest()
        self.analyze_light_position()
        self.analyze_keyboard_mouse_distance()
        self.analyze_keyboard_mouse_alignment()
        self.analyze_window_position()
        self.analyze_viewing_distance_by_ratio()

        return self.report


# --------------------------------------------------------------------------
# 4. GPT 연동 및 프롬프트
# --------------------------------------------------------------------------
def get_gpt_recommendation(report: list) -> str:
    """분석 리포트를 바탕으로 GPT에게 상세 조언을 요청합니다."""
    global client
    if not client:
        client = make_openai_client()
    if not client:
        return "⚠️ OpenAI 클라이언트가 초기화되지 않았습니다. OPENAI_API_KEY를 확인하세요."

    report_str = json.dumps(report, indent=2, ensure_ascii=False)
    prompt_text = (
        f"다음은 사용자의 책상 환경에 대한 인체공학 분석 결과(JSON 형식)입니다:\n"
        f"```json\n{report_str}\n```\n\n"
        "당신은 세계 최고의 인체공학 전문가입니다. 위 분석 결과를 해석하여, 사용자에게 매우 구체적이고 실용적인 책상 환경 개선 방안을 한국어로 친절하게 설명해주세요.\n"
        "번호 목록 형식을 사용하여 다음 내용을 반드시 포함하여 조언해주세요:\n"
        "1. **종합 진단**: 현재 상황에 대한 긍정적인 점과 가장 시급하게 개선해야 할 점을 요약해주세요.\n"
        "2. **상세 개선 방안**: 분석 결과에서 'severity'가 'High' 또는 'Moderate'인 문제점들을 중심으로, 각각에 대한 구체적인 해결책을 제시해주세요. (예: 모니터 높이 조절 방법, 손목 받침대 추천 등)\n"
        "3. **추가적인 팁**: 분석 리포트에 나타나지 않았더라도, 건강한 컴퓨터 작업을 위한 일반적인 인체공학 팁(예: 스트레칭, 휴식 시간)을 2-3가지 제안해주세요."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a world-class ergonomics expert providing advice in Korean."},
                {"role": "user", "content": prompt_text}
            ],
            temperature=0.7,
            max_tokens=1024,
            timeout=45
        )
        return extract_text_from_response(response)
    except Exception as e:
        logger.exception("GPT 호출 실패")
        return f"GPT API 호출 중 오류가 발생했습니다: {type(e).__name__}: {e}"


# --------------------------------------------------------------------------
# 5. Streamlit 페이지 흐름 제어 및 UI
# --------------------------------------------------------------------------
def go_to_page(page_num: int):
    st.session_state['current_page'] = page_num
    st.rerun()


def handle_retry():
    keys_to_reset = [
        'current_page', 'user_analysis', 'analysis_result', 'detailed_report',
        'yolo_output', 'user_inputs', 'selected_screen_id', 'selected_screen_inch', 'image_width_px',
        'workflow_result', 'main_screen', 'monitor_inch'
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state['current_page'] = 1
    st.rerun()


# --------------------------------------------------------------------------
# 6. [신규] 결과 포맷팅 유틸리티 (한글 번역)
# --------------------------------------------------------------------------

# 각 problem_id와 severity를 한글로 변환하기 위한 딕셔너리
PROBLEM_ID_MAP = {
    "SCREEN_HEIGHT": "모니터 높이",
    "LAPTOP_HEIGHT": "노트북 화면 높이",
    "WRIST_REST_PRESENCE": "손목 받침대 유무",
    "LIGHT_POSITION": "조명 위치",
    "KEYBOARD_MOUSE_DISTANCE": "키보드-마우스 거리",
    "KEYBOARD_MOUSE_ALIGNMENT": "키보드-마우스 정렬",
    "WINDOW_POSITION": "창문과의 거리 및 방향",
    "VIEWING_DISTANCE": "시야 거리"
}

SEVERITY_MAP = {
    "High": "높음 🩸",
    "Moderate": "중간 ⚠️",
    "Low": "낮음 ✅"
}


def format_details_korean(problem_id: str, details: dict) -> str:
    """각 문제 항목의 상세 내용을 한글로 풀어 설명합니다."""
    if problem_id == "WRIST_REST_PRESENCE":
        return "손목 받침대가 없습니다. 장시간 사용 시 손목 터널 증후군의 위험이 있습니다." if not details.get(
            "has_wrist_rest") else "손목 받침대를 올바르게 사용하고 있습니다."

    elif "HEIGHT" in problem_id:
        delta = details.get('delta_cm', 0)
        ideal = details.get('ideal_height_cm', 0)
        actual = details.get('estimated_actual_height_cm', 0)
        if delta > 0:
            return f"화면이 이상적인 높이({ideal}cm)보다 약 {delta}cm 높습니다. 화면을 낮춰주세요."
        else:
            return f"화면이 이상적인 높이({ideal}cm)보다 약 {abs(delta)}cm 낮습니다. 받침대를 사용해 높여주세요."

    elif problem_id == "VIEWING_DISTANCE":
        ratio = details.get('screen_width_ratio', '0%')
        return f"화면이 시야에서 차지하는 비율이 {ratio}입니다. 너무 가깝거나 멀 경우 눈에 피로를 줄 수 있습니다. 팔 길이 정도의 거리를 유지하는 것이 좋습니다."

    elif problem_id == "LIGHT_POSITION":
        hand = details.get("handedness", "")
        side = details.get("lamp_side", "")
        if "왼손" in hand and side == "left":
            return "왼손잡이 사용자의 조명이 왼쪽에 있어 글씨를 쓸 때 그림자가 생길 수 있습니다. 조명을 오른쪽으로 옮겨주세요."
        if "오른손" in hand and side == "right":
            return "오른손잡이 사용자의 조명이 오른쪽에 있어 글씨를 쓸 때 그림자가 생길 수 있습니다. 조명을 왼쪽으로 옮겨주세요."
        return "조명이 올바른 위치에 있습니다."

    elif problem_id == "KEYBOARD_MOUSE_DISTANCE":
        actual = details.get('actual_distance_cm', 0)
        return f"키보드와 마우스 사이의 거리가 약 {actual}cm로, 어깨 너비보다 넓어 보입니다. 어깨에 부담을 줄 수 있으니 간격을 좁혀주세요."

    # 다른 모든 케이스에 대한 기본 설명
    return json.dumps(details, ensure_ascii=False)


# --- Streamlit 앱 메인 ---
st.set_page_config(page_title="인체공학적 책상 개선 가이드", page_icon="🦾", layout="centered")
st.title("🦾 인체공학적 책상 개선 가이드 서비스")
st.markdown("---")

if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 1


def display_page():
    page_id = st.session_state.get('current_page', 1)
    if not os.path.exists("pages"):
        st.warning("`pages` 디렉토리를 찾을 수 없습니다. 페이지를 동적으로 로드할 수 없습니다.")
        return

    meta_path = os.path.join("pages", "metadata.json")
    if not os.path.exists(meta_path):
        st.error("pages/metadata.json 파일을 찾을 수 없습니다.")
        return
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        page_info = next((p for p in metadata.get("pages", []) if p.get("id") == page_id), None)
        if page_info:
            module = importlib.import_module(f"pages.{page_info['module']}")
            func = getattr(module, page_info['function'])
            func()
    except Exception as e:
        logger.exception("페이지 로딩 실패")
        st.error(f"🚨 페이지 로딩 중 오류 발생: {e}")


# --- 페이지별 네비게이션 및 로직 ---
page = st.session_state.get('current_page', 1)
display_page()
st.markdown("---")

if page == 1:
    if st.button("Start Analysis", key="start_p1", use_container_width=True):
        go_to_page(2)
elif page == 2:
    cols = st.columns(3)
    with cols[0]:
        if st.button("< Back", key="back_p2", use_container_width=True): go_to_page(1)
    with cols[2]:
        if st.button("Next >", key="next_p3", use_container_width=True): go_to_page(3)
elif page == 3:
    cols = st.columns(3)
    with cols[0]:
        if st.button("< Back", key="back_p3", use_container_width=True): go_to_page(2)
    with cols[2]:
        if st.button("Get My Ergonomic Report", key="next_p4", use_container_width=True): go_to_page(4)

elif page == 4:
    st.header("⏱️ 분석 중입니다...")
    st.info("AI가 당신의 책상 환경을 정밀 분석하고 맞춤형 리포트를 생성하고 있습니다.")

    try:
        # 데이터 준비 및 변환
        with st.spinner("데이터를 준비하는 중..."):
            workflow_result = st.session_state.get('workflow_result', [{}])[0]
            main_screen_raw = st.session_state.get('main_screen')
            main_screen_inch = st.session_state.get('monitor_inch')
            user_inputs = st.session_state.get('user_inputs', {})

            if not workflow_result or not main_screen_raw or not main_screen_inch:
                st.error("분석에 필요한 이미지 또는 메인 스크린 정보가 부족합니다. 2단계로 돌아가 다시 시도해주세요.")
                if st.button("돌아가기"): handle_retry()
                st.stop()

            raw_detections = workflow_result.get("predictions", {}).get("predictions", [])
            image_width = workflow_result.get("image", {}).get("width", 1280)

            yolo_results = []
            for det in raw_detections:
                yolo_results.append({
                    "class": det.get("class"), "confidence": det.get("confidence"),
                    "box": {"x": det.get("x"), "y": det.get("y"), "width": det.get("width"),
                            "height": det.get("height")}
                })

            main_screen_id = None
            for i, det in enumerate(yolo_results):
                if (det['box']['x'] == main_screen_raw.get('x') and
                        det['box']['y'] == main_screen_raw.get('y') and
                        det['class'] == main_screen_raw.get('class')):
                    det['id'] = f"screen_{i}"
                    main_screen_id = f"screen_{i}"
                    break

            if not main_screen_id:
                raise ValueError("메인 스크린의 고유 ID를 생성하는데 실패했습니다.")

        # 분석 실행
        with st.spinner("인체공학 규칙에 따라 문제점을 분석하는 중..."):
            analyzer = ErgonomicsAnalyzer(yolo_results, user_inputs, image_width)
            analyzer.set_main_screen_by_id(main_screen_id, str(main_screen_inch))
            analysis_report = analyzer.run_all_analyses()
            st.session_state['detailed_report'] = analysis_report

        # AI 조언 생성
        with st.spinner("AI가 맞춤형 개선 가이드를 작성하는 중..."):
            gpt_text = get_gpt_recommendation(analysis_report)
            st.session_state['analysis_result'] = gpt_text

        st.success("분석 및 리포트 생성이 완료되었습니다!")
        time.sleep(1)
        go_to_page(5)

    except Exception as e:
        logger.exception("분석 파이프라인 오류")
        st.error(f"분석 중 오류가 발생했습니다: {e}")
        if st.button("처음으로 돌아가기", on_click=handle_retry): pass
        st.stop()

elif page == 5:
    st.subheader("📊 당신을 위한 AI 인체공학 분석 리포트")

    final_result = st.session_state.get('analysis_result', "분석 결과를 불러올 수 없습니다.")
    st.markdown(final_result)
    st.markdown("---")

    # --- [수정됨] 상세 분석 데이터를 한글로 번역하여 보여주는 UI ---
    st.subheader("📋 상세 분석 데이터")
    detailed_report = st.session_state.get('detailed_report', [])

    if not detailed_report:
        st.info("상세 분석 데이터가 없습니다.")
    else:
        for item in detailed_report:
            problem_id = item.get("problem_id", "UNKNOWN")
            severity = item.get("severity", "Low")
            details = item.get("details", {})

            # 딕셔너리를 사용해 한글로 변환
            title = PROBLEM_ID_MAP.get(problem_id, problem_id)
            severity_text = SEVERITY_MAP.get(severity, severity)

            with st.container(border=True):
                st.markdown(f"**항목: {title}**")
                st.markdown(f"**진단: {severity_text}**")

                # 상세 내용을 한글로 풀어 설명
                details_korean = format_details_korean(problem_id, details)
                st.markdown(f"세부 내용: {details_korean}")

    if st.button("다시 분석하기", key="retry_p5", use_container_width=True):
        handle_retry()

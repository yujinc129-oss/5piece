import streamlit as st
from PIL import Image
import json
import time
import math
import re
import openai

# --------------------------------------------------------------------------
# ⚙️ 1. 인체공학 분석 엔진 (Ergonomics Analysis Engine)
# (사용자가 제공한 상세 분석 로직을 모두 반영하여 수정)
# --------------------------------------------------------------------------

def find_objects(yolo_output, class_name):
    """YOLO 결과에서 특정 클래스의 모든 객체를 리스트로 반환"""
    return [obj for obj in yolo_output if obj.get('class') == class_name]

def find_object(yolo_output, class_name):
    """YOLO 결과에서 특정 클래스의 첫 번째 객체를 반환 (없으면 None)"""
    return next((obj for obj in yolo_output if obj.get('class') == class_name), None)

def get_object_side(obj_x, image_width):
    if obj_x < image_width / 3: return "left"
    elif obj_x > image_width * 2 / 3: return "right"
    else: return "center"

def _monitor_real_height_cm(inch, aspect_w=16, aspect_h=9):
    diag_cm = inch * 2.54
    return diag_cm * (aspect_h / math.sqrt(aspect_w**2 + aspect_h**2))

def calculate_ideal_screen_height(user_height_cm, user_gender):
    if user_gender == '남성': return ((3.32 * user_height_cm) - 25.50) / 10
    elif user_gender == '여성': return ((2.61 * user_height_cm) + 93.84) / 10
    else: return ((2.96 * user_height_cm) + 34.17) / 10

def check_proximity(upper_box, lower_box, threshold_px=100):
    upper_bottom_y = upper_box['y'] + upper_box['height'] / 2
    lower_top_y = lower_box['y'] - lower_box['height'] / 2
    horizontal_distance = abs(upper_box['x'] - lower_box['x'])
    h_alignment_threshold = (upper_box['width'] + lower_box['width']) / 4
    return abs(upper_bottom_y - lower_top_y) < threshold_px and horizontal_distance < h_alignment_threshold

class ErgonomicsAnalyzer:
    def __init__(self, yolo_predictions, user_inputs):
        self.yolo_output = yolo_predictions.get('predictions', [])
        self.image_width_px = yolo_predictions.get('image', {}).get('width', 1)
        self.user_inputs = user_inputs
        self.report = []
        self.severity_map = {"High": "High", "Moderate": "Moderate", "Low": "Low"}
        self.main_screen = None
        self.px_to_cm_ratio = None

    def detect_screens(self):
        screens = find_objects(self.yolo_output, 'screen') + find_objects(self.yolo_output, 'laptop')
        for i, screen in enumerate(screens):
            screen['id'] = f"screen_{i}"
        return screens

    def set_main_screen_by_id(self, screen_id, main_screen_inch):
        screens = self.detect_screens()
        self.main_screen = next((s for s in screens if s.get('id') == screen_id), None)
        if self.main_screen and main_screen_inch and self.main_screen.get('height', 0) > 0:
            real_h_cm = _monitor_real_height_cm(main_screen_inch)
            self.px_to_cm_ratio = real_h_cm / self.main_screen['height']
            return True
        return False

    def _estimate_desk_y(self):
        bottom_y_coords = []
        for class_name in ['keyboard', 'mouse', 'wrist rest', 'monitor support']:
            obj = find_object(self.yolo_output, class_name)
            if obj: bottom_y_coords.append(obj['y'] + obj['height'] / 2)
        
        laptop = find_object(self.yolo_output, 'laptop')
        support = find_object(self.yolo_output, 'monitor support')
        if laptop and not (support and check_proximity(laptop, support)):
            bottom_y_coords.append(laptop['y'] + laptop['height'] / 2)
            
        return sum(bottom_y_coords) / len(bottom_y_coords) if bottom_y_coords else None

    def _analyze_screen_height(self, screen_obj, details={}):
        if self.px_to_cm_ratio is None: return
        user_height_cm = self.user_inputs.get("height")
        gender = self.user_inputs.get("gender")
        if not all([user_height_cm, gender]): return

        desk_y = self._estimate_desk_y() or (screen_obj['y'] + screen_obj['height'] / 2.0)
        ideal_height_cm = calculate_ideal_screen_height(user_height_cm, gender)
        screen_top_y = screen_obj['y'] - screen_obj['height'] / 2.0
        distance_px = desk_y - screen_top_y
        estimated_actual_height_cm = round(distance_px * self.px_to_cm_ratio, 1)
        delta = round(estimated_actual_height_cm - ideal_height_cm, 1)

        severity = self.severity_map["Low"]
        if abs(delta) > 15: severity = self.severity_map["High"]
        elif abs(delta) > 5: severity = self.severity_map["Moderate"]
        
        problem_id = f"{screen_obj['class'].upper()}_HEIGHT"
        details.update({"delta_cm": delta, "ideal_height_cm": ideal_height_cm, "estimated_actual_height_cm": estimated_actual_height_cm})
        self.report.append({"problem_id": problem_id, "severity": severity, "details": details})

    def analyze_screen_setup(self):
        for screen in find_objects(self.yolo_output, "screen"):
            support = find_object(self.yolo_output, 'monitor support')
            has_support = support and check_proximity(screen, support)
            self._analyze_screen_height(screen, {"has_support": bool(has_support)})

    def analyze_laptop_setup(self):
        for laptop in find_objects(self.yolo_output, "laptop"):
            support = find_object(self.yolo_output, 'monitor support')
            has_support = support and check_proximity(laptop, support)
            has_external_keyboard = find_object(self.yolo_output, 'keyboard') is not None
            details = {"has_support": has_support, "has_external_keyboard": has_external_keyboard}
            self._analyze_screen_height(laptop, details)

    def analyze_light_position(self):
        lamp = find_object(self.yolo_output, "desk lamp")
        if not lamp: return
        handedness = self.user_inputs.get("dominant_hand")
        lamp_side = get_object_side(lamp['x'], self.image_width_px)
        is_misaligned = (handedness == "왼손" and lamp_side == "left") or (handedness == "오른손" and lamp_side == "right")
        severity = self.severity_map["Moderate"] if is_misaligned else self.severity_map["Low"]
        self.report.append({"problem_id": "LIGHT_POSITION", "severity": severity, "details": {"handedness": handedness, "lamp_side": lamp_side}})

    def analyze_wrist_rest(self):
        has_wrist_rest = find_object(self.yolo_output, "wrist rest")
        severity = self.severity_map["High"] if not has_wrist_rest else self.severity_map["Low"]
        self.report.append({"problem_id": "WRIST_REST_PRESENCE", "severity": severity, "details": {"has_wrist_rest": bool(has_wrist_rest)}})

    def analyze_window_position(self):
        if self.main_screen is None or self.px_to_cm_ratio is None: return
        window = find_object(self.yolo_output, "window")
        if not window: return
        horizontal_distance_px = abs(self.main_screen['x'] - window['x'])
        horizontal_distance_cm = round(horizontal_distance_px * self.px_to_cm_ratio, 1)
        severity = self.severity_map["Moderate"] if horizontal_distance_cm <= 50 else self.severity_map["Low"]
        self.report.append({"problem_id": "WINDOW_POSITION", "severity": severity, "details": {"horizontal_distance_cm": horizontal_distance_cm}})

    def analyze_keyboard_mouse_distance(self):
        if self.px_to_cm_ratio is None: return
        keyboard = find_object(self.yolo_output, "keyboard")
        mouse = find_object(self.yolo_output, "mouse")
        gender = self.user_inputs.get("gender")
        if not all([keyboard, mouse, gender]): return
        distance_cm = abs(keyboard['x'] - mouse['x']) * self.px_to_cm_ratio
        threshold_cm = 15 if gender == '남성' else 10
        severity = self.severity_map["High"] if distance_cm > threshold_cm else self.severity_map["Low"]
        self.report.append({"problem_id": "KEYBOARD_MOUSE_DISTANCE", "severity": severity, "details": {"actual_distance_cm": round(distance_cm, 1), "threshold_cm": threshold_cm}})

    def analyze_keyboard_mouse_alignment(self):
        keyboard = find_object(self.yolo_output, "keyboard")
        mouse = find_object(self.yolo_output, "mouse")
        if not all([keyboard, mouse]): return
        
        ky_min = keyboard['y'] - keyboard['height'] / 2
        ky_max = keyboard['y'] + keyboard['height'] / 2
        is_vertically_aligned = (ky_min <= mouse['y'] <= ky_max)
        
        severity = self.severity_map["Moderate"] if not is_vertically_aligned else self.severity_map["Low"]
        self.report.append({"problem_id": "KEYBOARD_MOUSE_ALIGNMENT", "severity": severity, "details": {"is_vertically_aligned": is_vertically_aligned}})

    def analyze_viewing_distance_by_ratio(self):
        if not self.main_screen: return
        ratio = self.main_screen['width'] / self.image_width_px
        severity = self.severity_map["Low"]
        if ratio > 0.50: severity = self.severity_map["High"]
        elif ratio < 0.40: severity = self.severity_map["Moderate"]
        self.report.append({"problem_id": "VIEWING_DISTANCE", "severity": severity, "details": {"main_screen_type": self.main_screen['class'], "screen_width_ratio": f"{ratio:.1%}"}})


    def run_all_analyses(self):
        if not self.main_screen:
            raise ValueError("메인 스크린이 설정되지 않았습니다.")
        
        self.analyze_light_position()
        self.analyze_wrist_rest()
        self.analyze_keyboard_mouse_distance()
        self.analyze_keyboard_mouse_alignment()
        self.analyze_window_position()
        self.analyze_viewing_distance_by_ratio()
        self.analyze_screen_setup()
        self.analyze_laptop_setup()

        return self.report if self.report else [{"problem_id": "NO_ISSUES", "severity": "None", "details": "훌륭한 배치입니다."}]

# --- GPT 연동 함수 ---
def get_gpt_recommendation(report):
    try:
        openai.api_key = st.secrets["OPENAI_API_KEY"]
        prompt = f"""
        # ROLE
        너는 세계 최고의 인체공학 컨설턴트다.
        # CONTEXT
        [사용자 정보]: {json.dumps(report.get("user_info"), ensure_ascii=False)}
        [발견된 문제점]: {json.dumps(report.get("detected_problems"), ensure_ascii=False)}
        # TASK
        위 정보를 바탕으로 사용자만을 위한 종합적인 개선 방안을 단계별로 작성해줘. 각 문제점에 대해 '왜 문제인가?', '어떻게 해결해야 하는가?', '기대 효과는 무엇인가?'를 포함해서 설명해줘.
        # FORMAT
        - 친절하고 격려하는 전문가의 톤을 유지하고, Markdown을 사용해 가독성 좋게 정리해줘.
        """
        response = openai.chat.completions.create(model="gpt-4o mini", messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"GPT와 통신 중 오류가 발생했습니다: {e}")
        return "GPT 조언을 생성하는 데 실패했습니다."

# --- 페이지 흐름 및 UI 함수 ---
def go_to_page(page_name):
    st.session_state.page = page_name
    st.rerun()

def handle_retry():
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()

def page_user_input():
    st.header("1단계: 👤 사용자 정보 입력")
    with st.form(key='user_info_form'):
        st.write("정확한 분석을 위해 기본 정보를 입력해주세요.")
        col1, col2, col3 = st.columns(3)
        gender = col1.radio("성별", ('여성', '남성'), horizontal=True)
        height = col2.number_input("키(cm)", 100, 250, 165, 1)
        hand = col3.radio("주 사용 손", ('오른손', '왼손'), horizontal=True)
        if st.form_submit_button('정보 저장하고 다음으로', type="primary"):
            st.session_state.user_info = {"gender": gender, "height": height, "dominant_hand": hand}
            go_to_page('P2_IMAGE_UPLOAD')

def page_image_upload():
    st.header("2단계: 📸 책상 사진 업로드")
    st.info("의자에 앉아 눈높이에서 책상 전체가 나오도록 찍은 사진을 올려주세요.")
    uploaded_file = st.file_uploader("사진 선택", type=["jpg", "jpeg", "png"])
    if uploaded_file:
        st.session_state.uploaded_image = uploaded_file
        st.image(uploaded_file, caption="업로드된 사진", width=400)
        if st.button("AI 분석 시작하기", type="primary"):
            st.session_state.yolo_result = {
                "predictions": {
                    "image": {"width": 638, "height": 585},
                    "predictions": [
                        {"width": 158, "height": 242, "x": 473, "y": 220, "class": "screen"},
                        {"width": 257, "height": 187, "x": 247.5, "y": 244.5, "class": "laptop"},
                        {"width": 50, "height": 38, "x": 427, "y": 418, "class": "mouse"},
                        {"width": 238, "height": 97, "x": 363, "y": 485.5, "class": "wrist rest"},
                        {"width": 208, "height": 93, "x": 312, "y": 444.5, "class": "keyboard"}
                    ]
                }
            }
            go_to_page('P3_SELECT_SCREEN')

def page_select_screen():
    st.header("3단계: 🖥️ 주 모니터 선택")
    st.info("분석의 기준이 될 주 모니터와 크기를 알려주세요.")
    analyzer = ErgonomicsAnalyzer(st.session_state.yolo_result['predictions'], st.session_state.user_info)
    screens = analyzer.detect_screens()
    
    if not screens:
        st.warning("사진에서 모니터나 노트북을 찾을 수 없습니다.")
        if st.button("사진 다시 올리기"): go_to_page('P2_IMAGE_UPLOAD')
        return

    screen_options = {s['id']: f"{s['class'].capitalize()} ({s['width']:.0f}x{s['height']:.0f}px)" for s in screens}
    
    with st.form("screen_select_form"):
        col1, col2 = st.columns(2)
        selected_id = col1.selectbox("주로 사용하는 화면을 선택하세요:", options=list(screen_options.keys()), format_func=lambda x: screen_options[x])
        monitor_size = col2.number_input("선택한 화면의 대각선 길이(인치)를 입력하세요:", min_value=10.0, max_value=50.0, value=24.0, step=0.5)
        if st.form_submit_button("선택 완료하고 분석 진행", type="primary"):
            analyzer.set_main_screen_by_id(selected_id, monitor_size)
            st.session_state.analyzer = analyzer
            go_to_page('P4_SHOW_RESULTS') # ⭐ 페이지 흐름 변경: 바로 결과 페이지로 이동

# ⭐ 페이지 4와 5를 통합한 새로운 결과 페이지 함수
def page_show_results():
    st.header("4단계: 📊 최종 분석 결과")
    
    # 분석이 이미 실행되었는지 확인, 안됐으면 실행
    if 'detailed_report' not in st.session_state:
        with st.spinner("인체공학 규칙 엔진 적용 중..."):
            time.sleep(1) 
            analyzer = st.session_state.analyzer
            problems_found = analyzer.run_all_analyses()
            
            detailed_report = { "user_info": analyzer.user_inputs, "detected_problems": problems_found }
            basic_solution = "### 📋 기본 진단 결과\n\n"
            if not problems_found or (problems_found and problems_found[0]['problem_id'] == "NO_ISSUES"):
                basic_solution += "✅ AI 분석 결과, 현재 책상 배치가 훌륭합니다!"
            else:
                basic_solution += f"총 {len(problems_found)}개의 개선점을 발견했습니다.\n"
                for p in problems_found:
                     basic_solution += f"- **문제:** {p['problem_id']} (심각도: {p['severity']})\n"
            
            st.session_state.detailed_report = detailed_report
            st.session_state.basic_solution = basic_solution

    # 기본 분석 결과 먼저 표시
    st.markdown(st.session_state.basic_solution)
    st.markdown("---")

    # GPT 상세 분석 옵션 제공
    st.info("더 상세한 개인 맞춤형 조언을 원하시면 아래 버튼을 클릭하세요.")
    if st.button("✅ AI(GPT)로 더 자세한 조언 받기", use_container_width=True):
        if 'gpt_result' not in st.session_state:
            with st.spinner("AI가 당신만을 위한 맞춤 조언을 생성 중입니다..."):
                gpt_text = get_gpt_recommendation(st.session_state.detailed_report)
                st.session_state.gpt_result = gpt_text
        
        st.subheader("🤖 AI 컨설턴트의 상세 조언")
        st.markdown(st.session_state.gpt_result)

    # 상세 리포트 (JSON)
    with st.expander("상세 분석 리포트 보기 (JSON)"):
        st.json(st.session_state.get('detailed_report', {}))
    
    st.markdown("---")
    if st.button("처음부터 다시 시작하기", use_container_width=True):
        handle_retry()

# --- 메인 앱 라우터 (페이지 흐름 제어) ---
st.title("👨‍💻 AI Ergonomic Desk Consultant")
if 'page' not in st.session_state:
    st.session_state.page = 'P1_USER_INPUT'

# ⭐ 페이지 맵 수정: P4와 P5를 하나로 통합
page_map = {
    'P1_USER_INPUT': page_user_input,
    'P2_IMAGE_UPLOAD': page_image_upload,
    'P3_SELECT_SCREEN': page_select_screen,
    'P4_SHOW_RESULTS': page_show_results, # P4가 이제 최종 결과 페이지
}

page_function = page_map.get(st.session_state.page)
if page_function:
    page_function()
else:
    st.error("잘못된 페이지입니다. 처음부터 다시 시작합니다.")
    handle_retry()

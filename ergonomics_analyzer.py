import math
import json
import re


# --------------------------------------------------------------------------
# 👤 1. 공통 헬퍼 함수 (Helper Functions)
# --------------------------------------------------------------------------

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
    """위쪽 객체(upper_box)가 아래쪽 객체(lower_box) 바로 위에 있는지 Y축 및 X축 기준으로 확인"""
    upper_bottom_y = upper_box['y'] + upper_box['height'] / 2
    lower_top_y = lower_box['y'] - lower_box['height'] / 2

    horizontal_distance = abs(upper_box['x'] - lower_box['x'])
    horizontal_alignment_threshold = (upper_box['width'] + lower_box['width']) / 4

    is_vertically_close = abs(upper_bottom_y - lower_top_y) < threshold_px
    is_horizontally_aligned = horizontal_distance < horizontal_alignment_threshold

    return is_vertically_close and is_horizontally_aligned


# --------------------------------------------------------------------------
# 🧐 2. 인체공학 진단 분석 클래스 (ErgonomicsAnalyzer Class)
# --------------------------------------------------------------------------
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
        if laptop:
            is_on_support = support and check_proximity(laptop['box'], support['box'])
            if not is_on_support:
                bottom_y_coords.append(laptop['box']['y'] + laptop['box']['height'] / 2)

        if not bottom_y_coords:
            return None

        return sum(bottom_y_coords) / len(bottom_y_coords)

    def _analyze_screen_height(self, screen_obj, details={}):
        """스크린 객체의 높이를 분석하는 공통 로직"""
        if self.px_to_cm_ratio is None: return
        user_height_cm = self.user_inputs.get("user_height_cm")
        gender = self.user_inputs.get("gender")
        if not all([user_height_cm, gender]): return

        desk_y = self._estimate_desk_y()
        if desk_y is None:
            desk_y = screen_obj['box']['y'] + screen_obj['box']['height'] / 2.0

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

        problem_id = f"{screen_obj['class'].upper()}_HEIGHT"

        details.update({
            "delta_cm": delta,
            "ideal_height_cm": ideal_height_cm,
            "estimated_actual_height_cm": estimated_actual_height_cm
        })
        self.report.append({"problem_id": problem_id, "severity": severity, "details": details})

    def detect_screens(self):
        """감지된 모든 스크린 객체에 고유 ID를 부여하여 리스트로 반환"""
        screen_classes = ['screen', 'laptop']
        screens = [obj for obj in self.yolo_output if obj['class'] in screen_classes]

        for i, screen in enumerate(screens):
            screen['id'] = f"screen_{i}"

        return screens

    def set_main_screen_by_id(self, screen_id, main_screen_inch_str):
        """ID와 인치 정보를 받아 사용자가 선택한 스크린을 self.main_screen으로 설정하고, px_to_cm_ratio를 계산"""
        screens = self.detect_screens()
        selected_screen = next((s for s in screens if s.get('id') == screen_id), None)

        if selected_screen:
            self.main_screen = selected_screen

            self.user_inputs['main_screen_inch'] = main_screen_inch_str
            main_screen_inch = parse_inch_from_string(str(main_screen_inch_str))

            if main_screen_inch and self.main_screen['box']['height'] > 0:
                real_h_cm = _monitor_real_height_cm(main_screen_inch)
                self.px_to_cm_ratio = real_h_cm / self.main_screen['box']['height']

            return True
        return False

    def analyze_screen_setup(self):
        screen = find_object(self.yolo_output, "screen")
        if screen:
            support = find_object(self.yolo_output, 'monitor support')
            has_support = support and check_proximity(screen['box'], support['box'])
            details = {"has_support": bool(has_support)}
            self._analyze_screen_height(screen, details)

    def analyze_laptop_setup(self):
        laptop = find_object(self.yolo_output, "laptop")
        if laptop:
            support = find_object(self.yolo_output, 'monitor support')
            has_support = support and check_proximity(laptop['box'], support['box'])
            has_external_keyboard = find_object(self.yolo_output, 'keyboard') is not None
            details = {"has_support": has_support, "has_external_keyboard": has_external_keyboard}
            self._analyze_screen_height(laptop, details)

    def analyze_window_position(self):
        if self.main_screen is None or self.px_to_cm_ratio is None: return
        window = find_object(self.yolo_output, "window")
        if not window: return
        horizontal_distance_px = abs(self.main_screen['box']['x'] - window['box']['x'])
        horizontal_distance_cm = round(horizontal_distance_px * self.px_to_cm_ratio, 1)
        severity = self.severity_map["Moderate"] if horizontal_distance_cm <= 50 else self.severity_map["Low"]
        self.report.append({"problem_id": "WINDOW_POSITION", "severity": severity,
                            "details": {"horizontal_distance_cm": horizontal_distance_cm}})

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

    def analyze_wrist_rest(self):
        has_wrist_rest = find_object(self.yolo_output, "wrist_rest")
        severity = self.severity_map["High"] if not has_wrist_rest else self.severity_map["Low"]
        self.report.append({"problem_id": "WRIST_REST_PRESENCE", "severity": severity,
                            "details": {"has_wrist_rest": bool(has_wrist_rest)}})

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

    # [수정] analyze_keyboard_mouse_alignment 함수 로직 변경
    def analyze_keyboard_mouse_alignment(self):
        keyboard = find_object(self.yolo_output, "keyboard")
        mouse = find_object(self.yolo_output, "mouse")
        if not all([keyboard, mouse]): return

        kbd_box = keyboard['box']
        mouse_center_y = mouse['box']['y']

        # 키보드의 상단(y_min)과 하단(y_max) 좌표 계산
        ky_min = kbd_box['y'] - kbd_box['height'] / 2
        ky_max = kbd_box['y'] + kbd_box['height'] / 2

        # 마우스의 y좌표가 키보드의 세로 면적 안에 있는지 확인
        is_vertically_aligned = (ky_min <= mouse_center_y <= ky_max)

        severity = self.severity_map["Moderate"] if not is_vertically_aligned else self.severity_map["Low"]
        self.report.append({
            "problem_id": "KEYBOARD_MOUSE_ALIGNMENT",
            "severity": severity,
            "details": {"is_vertically_aligned": is_vertically_aligned}
        })

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
        if not self.main_screen:
            raise ValueError("메인 스크린이 설정되지 않았습니다. set_main_screen_by_id()를 먼저 호출해주세요.")

        self.analyze_light_position()
        self.analyze_wrist_rest()
        self.analyze_keyboard_mouse_distance()
        self.analyze_keyboard_mouse_alignment()

        self.analyze_window_position()
        self.analyze_viewing_distance_by_ratio()

        self.analyze_screen_setup()
        self.analyze_laptop_setup()

        return self.report


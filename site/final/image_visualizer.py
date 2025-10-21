from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

# --------------------------------------------------------------------------
# 시각화 헬퍼 함수
# --------------------------------------------------------------------------
FONT_PATH = "LiberationSans-Regular.ttf"  # Colab 기본 폰트 경로, 로컬에서는 폰트 파일 필요
PROBLEM_COLOR = (255, 82, 82)
IDEAL_COLOR = (0, 255, 255)
IDEAL_TEXT_BG_COLOR = (0, 139, 139)

def find_object(yolo_output, class_name):
    """YOLO 결과에서 특정 클래스의 첫 번째 객체를 반환 (없으면 None)"""
    return next((obj for obj in yolo_output if obj['class'] == class_name), None)

def get_font(size=24):
    """기본 폰트를 로드하는 헬퍼 함수"""
    try:
        return ImageFont.truetype(FONT_PATH, size=size)
    except IOError:
        return ImageFont.load_default()

def draw_text_with_bg(draw, pos, text, font, text_color="white", bg_color=(0, 0, 0, 128), anchor="lt"):
    """텍스트 뒤에 반투명 배경을 그려 가독성을 높입니다."""
    bbox = draw.textbbox(pos, text, font=font, anchor=anchor)
    padded_bbox = [bbox[0] - 5, bbox[1] - 2, bbox[2] + 5, bbox[3] + 2]
    draw.rectangle(padded_bbox, fill=bg_color)
    draw.text(pos, text, fill=text_color, font=font, anchor=anchor)

def _draw_bounding_box(draw, obj, severity):
    """문제 객체에 반투명 채움과 테두리가 있는 바운딩 박스를 그립니다."""
    box = obj['box']
    x1, y1 = box['x'] - box['width'] / 2, box['y'] - box['height'] / 2
    x2, y2 = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
    
    color = PROBLEM_COLOR
    fill_color = color + (100,)

    draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=3, fill=fill_color)
    draw_text_with_bg(draw, (x1 + 5, y1 + 5), obj['class'], get_font(20), bg_color=color)

def _draw_ideal_screen_box(draw, analyzer, report):
    height_problem = next((p for p in report if "HEIGHT" in p["problem_id"] and p['severity'] != 'Low'), None)
    if not analyzer.main_screen or not height_problem or not analyzer.px_to_cm_ratio: return

    details = height_problem["details"]
    current_top_y = analyzer.main_screen['box']['y'] - analyzer.main_screen['box']['height'] / 2
    delta_cm = details['delta_cm']
    delta_px = delta_cm / analyzer.px_to_cm_ratio
    ideal_top_y = current_top_y - delta_px
    
    ideal_width = analyzer.image_width_px * 0.45
    ideal_height = ideal_width * (9 / 16)
    
    center_x = analyzer.image_width_px / 2
    ix1, iy1 = center_x - ideal_width / 2, ideal_top_y
    ix2, iy2 = center_x + ideal_width / 2, ideal_top_y + ideal_height
    
    draw.rectangle([(ix1, iy1), (ix2, iy2)], outline=IDEAL_COLOR, width=4, fill=IDEAL_COLOR + (100,))
    center_box_y = iy1 + (ideal_height / 2)
    draw_text_with_bg(draw, (center_x, center_box_y), "Ideal Screen Position & Size", get_font(20), bg_color=IDEAL_TEXT_BG_COLOR, anchor="mm")
    
    if height_problem:
        arrow_x = ix2 + 20
        draw.line([(arrow_x, current_top_y), (arrow_x, ideal_top_y)], fill="yellow", width=5)
        direction_text = "Move Up" if delta_cm > 0 else "Move Down"
        text = f"{direction_text}: {abs(delta_cm)}cm"
        draw_text_with_bg(draw, (arrow_x + 10, (current_top_y + ideal_top_y) / 2), text, get_font(22), bg_color="green")

def _draw_ideal_kb_mouse_position(draw, analyzer, report):
    ideal_center_x = analyzer.image_width_px / 2
    keyboard, mouse = find_object(analyzer.yolo_output, 'keyboard'), find_object(analyzer.yolo_output, 'mouse')
    distance_problem = next((p for p in report if p['problem_id'] == 'KEYBOARD_MOUSE_DISTANCE'), None)
    if not all([keyboard, mouse, analyzer.px_to_cm_ratio, distance_problem]): return
        
    kb_y = keyboard['box']['y']
    kb_w, kb_h = keyboard['box']['width'], keyboard['box']['height']
    ikb_x1, ikb_y1 = ideal_center_x - kb_w / 2, kb_y - kb_h / 2
    ikb_x2, ikb_y2 = ideal_center_x + kb_w / 2, kb_y + kb_h / 2
    draw.rectangle([(ikb_x1, ikb_y1), (ikb_x2, ikb_y2)], outline=IDEAL_COLOR, width=3, fill=IDEAL_COLOR + (100,))
    draw_text_with_bg(draw, (ideal_center_x, kb_y), "Ideal Keyboard", get_font(20), bg_color=IDEAL_TEXT_BG_COLOR, anchor="mm")

    threshold_cm = distance_problem['details']['threshold_cm']
    threshold_px = threshold_cm / analyzer.px_to_cm_ratio
    ideal_mouse_x = ikb_x2 + (threshold_px / 2) + (mouse['box']['width'] / 2)
    mouse_w, mouse_h = mouse['box']['width'], mouse['box']['height']
    im_x1, im_y1 = ideal_mouse_x - mouse_w / 2, kb_y - mouse_h / 2
    im_x2, im_y2 = ideal_mouse_x + mouse_w / 2, kb_y + mouse_h / 2
    draw.rectangle([(im_x1, im_y1), (im_x2, im_y2)], outline=IDEAL_COLOR, width=3, fill=IDEAL_COLOR + (100,))
    draw_text_with_bg(draw, (ideal_mouse_x, kb_y), "Ideal Mouse", get_font(20), bg_color=IDEAL_TEXT_BG_COLOR, anchor="mm")

def draw_feedback_on_image(image_bytes, report, analyzer):
    """
    메인 함수: 원본 이미지, 분석 리포트, 분석기 인스턴스를 받아
    피드백이 그려진 새 이미지를 반환합니다.
    """
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    
    problems_to_draw = [p for p in report if p['severity'] != 'Low']
    if not problems_to_draw:
        return image.convert("RGB") # 그릴 문제가 없으면 원본 반환

    # 문제점 레이어
    problem_overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    problem_draw = ImageDraw.Draw(problem_overlay)
    
    problematic_objects = {}
    for problem in report:
        if problem['severity'] == 'Low': continue
        problem_id = problem["problem_id"]
        involved_classes = []
        if "HEIGHT" in problem_id: involved_classes.append(problem_id.split('_')[0].lower())
        elif "KEYBOARD_MOUSE" in problem_id: involved_classes.extend(["keyboard", "mouse"])
        elif "WRIST_REST" in problem_id: involved_classes.append("mouse")
        elif "VIEWING_DISTANCE" in problem_id:
            if analyzer.main_screen: involved_classes.append(analyzer.main_screen['class'])
        elif "LIGHT_POSITION" in problem_id: involved_classes.append("desk lamp")
        for class_name in involved_classes:
            obj = find_object(analyzer.yolo_output, class_name)
            if obj: problematic_objects[class_name] = (obj, problem['severity'])

    for class_name, (obj, severity) in problematic_objects.items():
        _draw_bounding_box(problem_draw, obj, severity)

    # 이상적인 위치 레이어
    ideal_overlay = Image.new("RGBA", image.size, (255, 255, 255, 0))
    ideal_draw = ImageDraw.Draw(ideal_overlay)
    
    drawn_kb_mouse_ideal, drawn_screen_ideal = False, False
    for problem in report:
        if problem['severity'] == 'Low': continue
        problem_id = problem["problem_id"]
        
        if problem_id in ["SCREEN_HEIGHT", "LAPTOP_HEIGHT", "VIEWING_DISTANCE"]:
            if not drawn_screen_ideal:
                _draw_ideal_screen_box(ideal_draw, analyzer, report)
                drawn_screen_ideal = True
        elif problem_id in ["KEYBOARD_MOUSE_DISTANCE", "KEYBOARD_MOUSE_ALIGNMENT"]:
            if not drawn_kb_mouse_ideal:
                _draw_ideal_kb_mouse_position(ideal_draw, analyzer, report)
                drawn_kb_mouse_ideal = True
    
    # 이미지 합성
    image_with_problems = Image.alpha_composite(image, problem_overlay)
    final_image = Image.alpha_composite(image_with_problems, ideal_overlay)
    
    return final_image.convert("RGB")

# pages/page1.py
import os
import base64
import streamlit as st

def show_opening_page():
    """
    인트로 페이지 렌더링
    - 배경 이미지는 프로젝트 루트의 project 폴더에서 찾음
    - 이미지가 없으면 경고 표시 및 기본 스타일 유지
    """
    def get_base64_of_bin_file(bin_file: str):
        try:
            with open(bin_file, "rb") as f:
                data = f.read()
            return base64.b64encode(data).decode()
        except FileNotFoundError:
            return None
        except Exception as e:
            st.warning(f"배경 이미지 로드 중 오류: {e}")
            return None

    def set_png_as_page_bg(png_file: str):
        bin_str = get_base64_of_bin_file(png_file)
        if not bin_str:
            st.warning(f"배경 이미지 파일을 찾을 수 없습니다: {png_file}")
            return
        page_bg_img = f"""
        <style>
        div.stButton > button {{
            background-color: #FFD1DC;
            color: #4A4A4A;
            border-radius: 12px;
            border: 2px solid #FFC0CB;
            padding: 12px 30px;
            font-size: 1.0rem;
            font-weight: bold;
            box-shadow: 2px 2px 8px rgba(0,0,0,0.2);
            transition: all 0.2s ease-in-out;
        }}
        div.stButton > button:hover {{
            background-color: #FFC0CB;
            color: white;
            border-color: #FFB6C1;
            transform: translateY(-2px);
        }}
        div.stButton > button:active {{
            transform: translateY(0);
        }}
        .stApp {{        
            background-image: linear-gradient(rgba(0,0,0,0.45), rgba(0,0,0,0.45)), url("data:image/png;base64,{bin_str}");
            # background-size: cover;
            
            /* [수정] cover(덮기)에서 contain(포함하기)으로 변경 */
            background-size: contain; 
            
            /* [수정] 이미지가 화면보다 작을 때 반복되지 않도록 설정 */
            background-repeat: no-repeat;
            
            background-position: center;
            
            
        }}
        .stApp > header {{
            
            display: none;
        }}
        </style>
        """
        st.markdown(page_bg_img, unsafe_allow_html=True)

    # app_root: pages 폴더 기준 한 단계 위 (website_frame)
    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    # 실제 이미지 파일명에 맞춰 수정하세요
    image_path_candidates = [
        os.path.join(app_root, "project", "곰돌이.png"),
        os.path.join(app_root, "project", "곰돌이1.png"),
        os.path.join(app_root, "project", "coding.png"),
    ]

    # 가장 먼저 존재하는 경로를 사용
    image_path = next((p for p in image_path_candidates if os.path.exists(p)), None)

    # 디버그용 경로 출력 (개발 시에만 볼 것)
    # st.write(f"image_path resolved to: {image_path or 'None (no file found)'}")

    if image_path:
        set_png_as_page_bg(image_path)
    else:
        st.info("배경 이미지가 없으므로 기본 스타일로 표시합니다.")

    # 메인 콘텐츠
    st.markdown(
        """
        <div style="display:flex;justify-content:center;align-items:center;height:60vh;flex-direction:column;">
            <h1 style="color:#FFFFFF;text-align:center;font-size:3rem;margin:0;">5Piece</h1>
            <p style="color:#FFFFFF;text-align:center;font-size:1.05rem;margin-top:12px;">
                책상 사진 한 장만으로 잘못된 자세와 작업 환경을 진단받아 보세요.<br>
                5Piece가 당신의 몸에 꼭 맞는 최적의 책상 배치를 찾아드립니다.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

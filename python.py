import streamlit as st
import pandas as pd
from google import genai
from google.genai.errors import APIError

# ==============================
# ⚙️ Cấu hình Trang Streamlit
# ==============================
st.set_page_config(
    page_title="Phân Tích Báo Cáo Tài Chính",
    layout="wide",
    page_icon="📊",
)

st.markdown("""
    <style>
        .main {background-color: #f9f9f9;}
        .stChatMessage {padding: 12px; border-radius: 12px;}
        .user {background-color: #DCF8C6;}
        .assistant {background-color: #F1F0F0;}
        .title {text-align:center; color:#004aad; font-size:30px; font-weight:bold; margin-bottom:20px;}
        .subheader {color:#0066cc; margin-top:30px;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📊 ỨNG DỤNG PHÂN TÍCH BÁO CÁO TÀI CHÍNH</div>', unsafe_allow_html=True)

# ==============================
# 📁 Xử lý Dữ liệu
# ==============================
@st.cache_data
def process_financial_data(df):
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100

    return df

# ==============================
# 🤖 Hàm Gọi API Gemini
# ==============================
def get_ai_response(prompt, api_key, model="gemini-2.5-flash"):
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        return response.text
    except APIError as e:
        return f"Lỗi API Gemini: {e}"
    except Exception as e:
        return f"Lỗi không xác định: {e}"

# ==============================
# 📂 Upload & Xử lý File
# ==============================
uploaded_file = st.file_uploader(
    "📥 1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']

        df_processed = process_financial_data(df_raw.copy())

        st.subheader("📈 2. Tốc độ Tăng trưởng & Tỷ trọng Cơ cấu Tài sản")
        st.dataframe(df_processed.style.format({
            'Năm trước': '{:,.0f}',
            'Năm sau': '{:,.0f}',
            'Tốc độ tăng trưởng (%)': '{:.2f}%',
            'Tỷ trọng Năm trước (%)': '{:.2f}%',
            'Tỷ trọng Năm sau (%)': '{:.2f}%'
        }), use_container_width=True)

        # === Chỉ số tài chính cơ bản ===
        st.subheader("💹 3. Các Chỉ số Tài chính Cơ bản")

        try:
            tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
            tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]
            no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
            no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

            thanh_toan_hien_hanh_N = tsnh_n / no_ngan_han_N
            thanh_toan_hien_hanh_N_1 = tsnh_n_1 / no_ngan_han_N_1

            col1, col2 = st.columns(2)
            col1.metric("Năm trước", f"{thanh_toan_hien_hanh_N_1:.2f} lần")
            col2.metric("Năm sau", f"{thanh_toan_hien_hanh_N:.2f} lần",
                        delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}")
        except IndexError:
            st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")

        # === Phân tích AI ===
        st.subheader("🧠 4. Nhận xét Tình hình Tài chính (AI Gemini)")
        data_for_ai = df_processed.to_markdown(index=False)

        if st.button("🚀 Gửi cho Gemini Phân tích"):
            api_key = st.secrets.get("GEMINI_API_KEY")
            if api_key:
                with st.spinner("Đang phân tích bằng Gemini..."):
                    prompt = f"""
                    Bạn là chuyên gia phân tích tài chính. Dưới đây là bảng dữ liệu:
                    {data_for_ai}
                    Hãy viết nhận xét tổng quan 3-4 đoạn, tập trung vào xu hướng tăng trưởng và cơ cấu tài sản.
                    """
                    ai_result = get_ai_response(prompt, api_key)
                    st.markdown("**📋 Kết quả từ Gemini:**")
                    st.info(ai_result)
            else:
                st.error("Chưa có GEMINI_API_KEY trong Streamlit Secrets.")

    except Exception as e:
        st.error(f"Lỗi xử lý file: {e}")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

# ==============================
# 💬 KHUNG CHAT GEMINI (Phần mới)
# ==============================
st.markdown("---")
st.subheader("💬 5. Trò chuyện trực tiếp với Gemini AI")

api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.warning("⚠️ Bạn cần thêm GEMINI_API_KEY trong phần Secrets để dùng Chat.")
else:
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Hiển thị lịch sử chat
    for msg in st.session_state["messages"]:
        role, text = msg["role"], msg["content"]
        if role == "user":
            st.markdown(f"<div class='stChatMessage user'><b>🧑‍💼 Bạn:</b> {text}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='stChatMessage assistant'><b>🤖 Gemini:</b> {text}</div>", unsafe_allow_html=True)

    user_input = st.text_input("Nhập câu hỏi của bạn tại đây...")
    if st.button("Gửi câu hỏi"):
        if user_input.strip():
            st.session_state["messages"].append({"role": "user", "content": user_input})
            with st.spinner("Gemini đang trả lời..."):
                ai_reply = get_ai_response(user_input, api_key)
            st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
            st.experimental_rerun()

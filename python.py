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

# --- CSS giao diện chuyên nghiệp ---
st.markdown("""
<style>
body {
    background-color: #f5f7fa;
    font-family: 'Segoe UI', sans-serif;
}
.title {
    text-align: center;
    color: #004aad;
    font-size: 30px;
    font-weight: bold;
    margin-bottom: 20px;
}
.stChatContainer {
    border-radius: 12px;
    background-color: #ffffff;
    padding: 15px;
}
.user-bubble {
    background-color: #DCF8C6;
    border-radius: 16px 16px 0 16px;
    padding: 10px 14px;
    margin: 5px 0;
    max-width: 80%;
    float: right;
    clear: both;
}
.bot-bubble {
    background-color: #E8E8E8;
    border-radius: 16px 16px 16px 0;
    padding: 10px 14px;
    margin: 5px 0;
    max-width: 80%;
    float: left;
    clear: both;
}
.avatar {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    vertical-align: middle;
    margin-right: 8px;
}
.stButton>button {
    background-color: #004aad;
    color: white;
    border-radius: 8px;
    border: none;
}
.stButton>button:hover {
    background-color: #0066cc;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="title">📊 ỨNG DỤNG PHÂN TÍCH BÁO CÁO TÀI CHÍNH</div>', unsafe_allow_html=True)

# ==============================
# 📁 Hàm xử lý dữ liệu
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
# 🤖 Gọi API Gemini
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
# 📂 Tải và xử lý File Excel
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
# 💬 5. KHUNG CHAT GEMINI (Messenger Style)
# ==============================
st.markdown("---")
st.subheader("💬 Trò chuyện trực tiếp với Gemini AI")

api_key = st.secrets.get("GEMINI_API_KEY")
if not api_key:
    st.warning("⚠️ Bạn cần thêm GEMINI_API_KEY trong phần Secrets để sử dụng Chat.")
else:
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    # Hiển thị lịch sử chat
    for msg in st.session_state["messages"]:
        if msg["role"] == "user":
            st.markdown(
                f"<div class='user-bubble'><img class='avatar' src='https://cdn-icons-png.flaticon.com/512/1077/1077063.png'>{msg['content']}</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div class='bot-bubble'><img class='avatar' src='https://cdn-icons-png.flaticon.com/512/4712/4712109.png'>{msg['content']}</div>",
                unsafe_allow_html=True
            )

    # Ô nhập câu hỏi
    user_input = st.text_input("💭 Nhập câu hỏi của bạn với Gemini:")
    if st.button("Gửi câu hỏi 🚀"):
        if user_input.strip():
            st.session_state["messages"].append({"role": "user", "content": user_input})
            with st.spinner("Gemini đang trả lời..."):
                ai_reply = get_ai_response(user_input, api_key)
            st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
            st.rerun()

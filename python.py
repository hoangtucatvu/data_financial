import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from google.api_core.exceptions import GoogleAPICallError

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    page_icon="📊",
    layout="wide"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính & Hỏi Đáp AI 📊")
st.markdown("Tải lên file Báo cáo tài chính của bạn, ứng dụng sẽ tự động tính toán các chỉ số và đưa ra nhận xét từ AI. Sau đó, bạn có thể hỏi đáp trực tiếp với AI về dữ liệu.")

# --- Lấy API Key từ Streamlit Secrets ---
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except (KeyError, FileNotFoundError):
    st.error("LỖI: Không tìm thấy khóa API 'GEMINI_API_KEY'. Vui lòng thiết lập trong phần Secrets của Streamlit.")
    GEMINI_API_KEY = None # Đặt là None để kiểm tra sau

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""
    
    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. Tính Tốc độ Tăng trưởng
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'. Vui lòng kiểm tra lại file Excel.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini cho Phân tích Tổng quan ---
def get_ai_analysis(data_for_ai):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét tổng quan."""
    if not GEMINI_API_KEY:
        return "Lỗi: API Key chưa được cấu hình."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """
        response = model.generate_content(prompt)
        return response.text
    except GoogleAPICallError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# --- Hàm gọi API Gemini cho Chat ---
# Sử dụng safety_settings để giảm thiểu việc chặn nội dung hợp lệ
def get_gemini_chat_response(context_data, chat_history, question):
    """Gửi câu hỏi và lịch sử chat đến Gemini để nhận câu trả lời."""
    if not GEMINI_API_KEY:
        return "Lỗi: API Key chưa được cấu hình."
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # Xây dựng context và lịch sử cho mô hình
        system_instruction = f"""
        Bạn là một trợ lý phân tích tài chính AI. Nhiệm vụ của bạn là trả lời các câu hỏi của người dùng dựa trên dữ liệu tài chính được cung cấp dưới đây. Hãy trả lời một cách chính xác, súc tích và chỉ sử dụng thông tin từ dữ liệu này.

        **Dữ liệu Báo cáo tài chính:**
        {context_data}
        ---
        """
        
        # Chuyển đổi lịch sử chat sang định dạng của Gemini
        messages = [{"role": "user" if msg["role"] == "user" else "model", "parts": [msg["content"]]} for msg in chat_history]
        
        # Bắt đầu phiên chat với context và lịch sử
        chat_session = model.start_chat(history=messages)

        # Gửi câu hỏi mới của người dùng
        response = chat_session.send_message(
            f"{system_instruction}\n\nCâu hỏi: {question}",
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )
        return response.text
    except GoogleAPICallError as e:
        return f"Lỗi gọi Gemini API: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định trong khi chat: {e}"

# --- Giao diện chính của ứng dụng ---
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (3 cột: Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Đảm bảo DataFrame có đúng 3 cột và đặt lại tên
        if df_raw.shape[1] >= 3:
             df_raw = df_raw.iloc[:, :3]
             df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
        else:
            st.error(f"File Excel phải có ít nhất 3 cột. File bạn tải lên chỉ có {df_raw.shape[1]} cột.")
            st.stop() # Dừng thực thi nếu file không hợp lệ

        df_processed = process_financial_data(df_raw.copy())
        st.session_state['df_processed'] = df_processed # Lưu vào session state để chat

        # --- Chức năng 2 & 3: Hiển thị Kết quả ---
        st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
        st.dataframe(df_processed.style.format({
            'Năm trước': '{:,.0f}',
            'Năm sau': '{:,.0f}',
            'Tốc độ tăng trưởng (%)': '{:.2f}%',
            'Tỷ trọng Năm trước (%)': '{:.2f}%',
            'Tỷ trọng Năm sau (%)': '{:.2f}%'
        }), use_container_width=True)
        
        # --- Chức năng 4: Tính Chỉ số Tài chính ---
        st.subheader("4. Các Chỉ số Tài chính Cơ bản")
        
        try:
            tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
            tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]
            no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]  
            no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

            thanh_toan_hien_hanh_N = tsnh_n / no_ngan_han_N if no_ngan_han_N != 0 else 0
            thanh_toan_hien_hanh_N_1 = tsnh_n_1 / no_ngan_han_N_1 if no_ngan_han_N_1 != 0 else 0
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric(
                    label="Chỉ số Thanh toán Hiện hành (Năm trước)",
                    value=f"{thanh_toan_hien_hanh_N_1:.2f} lần"
                )
            with col2:
                st.metric(
                    label="Chỉ số Thanh toán Hiện hành (Năm sau)",
                    value=f"{thanh_toan_hien_hanh_N:.2f} lần",
                    delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}"
                )
            
        except (IndexError, KeyError):
            st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số thanh toán.")
            thanh_toan_hien_hanh_N = "N/A"
            thanh_toan_hien_hanh_N_1 = "N/A"
        
        # --- Chức năng 5: Nhận xét AI Tổng quan ---
        st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
        
        data_for_ai = df_processed.to_markdown(index=False)
        st.session_state['data_for_ai'] = data_for_ai # Lưu context cho chat

        if st.button("Yêu cầu AI Phân tích Tổng quan"):
            with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                ai_result = get_ai_analysis(data_for_ai)
                st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                st.info(ai_result)

        # --- *PHẦN MỚI*: Chức năng 6: Chat với AI ---
        st.subheader("6. Trò chuyện với AI về dữ liệu")

        # Khởi tạo lịch sử chat trong session state
        if "messages" not in st.session_state:
            st.session_state.messages = []

        # Hiển thị các tin nhắn đã có
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Khung nhập liệu cho người dùng
        if prompt := st.chat_input("Hỏi AI điều gì về báo cáo này?"):
            # Thêm tin nhắn của người dùng vào lịch sử và hiển thị
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Lấy phản hồi từ AI và hiển thị
            with st.chat_message("assistant"):
                with st.spinner("AI đang suy nghĩ..."):
                    context_data = st.session_state.get('data_for_ai', 'Không có dữ liệu.')
                    response = get_gemini_chat_response(context_data, st.session_state.messages, prompt)
                    st.markdown(response)
            
            # Thêm tin nhắn của AI vào lịch sử
            st.session_state.messages.append({"role": "assistant", "content": response})


    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

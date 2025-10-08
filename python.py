import streamlit as st
import pandas as pd
import google.generativeai as genai
import os

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    page_icon="📊",
    layout="wide"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính 📊")
st.caption("Tải lên file BCTC của bạn, xem phân tích và trò chuyện với Gemini AI.")


# --- CẤU HÌNH GEMINI AI ---
# Lấy API key từ Streamlit Secrets
try:
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")
        st.stop()
    genai.configure(api_key=api_key)
    # Khởi tạo model
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
except Exception as e:
    st.error(f"Lỗi khi cấu hình Gemini: {e}")
    st.stop()

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
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini cho phân tích tổng quan---
def get_ai_summary(data_for_ai):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét tổng quan."""
    try:
        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Đã xảy ra lỗi khi gọi Gemini API: {e}"

# --- Chức năng 1: Tải File ---
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        
        # Tiền xử lý: Đảm bảo chỉ có 3 cột quan trọng
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
        
        # Xử lý dữ liệu
        df_processed = process_financial_data(df_raw.copy())

        if df_processed is not None:
            # Lưu trữ dữ liệu đã xử lý vào session_state để dùng cho chatbot
            st.session_state.df_processed = df_processed

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
                # Lấy Tài sản ngắn hạn
                tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Lấy Nợ ngắn hạn
                no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Tính toán
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
                
                # Lưu chỉ số vào session state để dùng cho AI
                st.session_state.financial_ratios = {
                    'thanh_toan_hien_hanh_N': thanh_toan_hien_hanh_N,
                    'thanh_toan_hien_hanh_N_1': thanh_toan_hien_hanh_N_1
                }

            except (IndexError, KeyError):
                st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")
                st.session_state.financial_ratios = {} # Khởi tạo rỗng để không bị lỗi
            
            # --- Chức năng 5: Nhận xét AI ---
            st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
            
            if st.button("Yêu cầu AI Phân tích Tổng quan"):
                 with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                    # Chuẩn bị dữ liệu để gửi cho AI
                    data_for_ai_summary = df_processed.to_markdown(index=False)
                    ratios = st.session_state.get('financial_ratios', {})
                    if ratios:
                        data_for_ai_summary += f"\n\nChỉ số thanh toán hiện hành (Năm sau): {ratios.get('thanh_toan_hien_hanh_N', 'N/A'):.2f}"
                        data_for_ai_summary += f"\nChỉ số thanh toán hiện hành (Năm trước): {ratios.get('thanh_toan_hien_hanh_N_1', 'N/A'):.2f}"
                    
                    ai_result = get_ai_summary(data_for_ai_summary)
                    st.info(ai_result)

            # --- CHỨC NĂNG 6: KHUNG CHAT TƯƠNG TÁC ---
            st.subheader("6. Trò chuyện tương tác với AI về dữ liệu")

            # Khởi tạo lịch sử chat nếu chưa có
            if "messages" not in st.session_state:
                st.session_state.messages = []
            
            # Hiển thị các tin nhắn đã có
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Khung nhập liệu cho người dùng
            if prompt := st.chat_input("Bạn muốn hỏi gì về dữ liệu tài chính này?"):
                # Thêm tin nhắn của người dùng vào lịch sử
                st.session_state.messages.append({"role": "user", "content": prompt})
                # Hiển thị tin nhắn của người dùng
                with st.chat_message("user"):
                    st.markdown(prompt)

                # Chuẩn bị context và câu hỏi để gửi cho AI
                with st.spinner("Gemini đang suy nghĩ..."):
                    data_context = df_processed.to_markdown(index=False)
                    full_prompt = f"""
                    Dựa vào bối cảnh là dữ liệu tài chính của một công ty dưới đây:
                    {data_context}
                    
                    Hãy trả lời câu hỏi sau của người dùng một cách chuyên nghiệp như một chuyên gia tài chính.
                    Câu hỏi: "{prompt}"
                    """
                    
                    # Gửi tới AI và nhận câu trả lời
                    try:
                        response = model.generate_content(full_prompt)
                        response_text = response.text
                    except Exception as e:
                        response_text = f"Đã có lỗi xảy ra: {e}"

                    # Hiển thị câu trả lời của AI
                    with st.chat_message("assistant"):
                        st.markdown(response_text)
                    
                    # Thêm câu trả lời của AI vào lịch sử
                    st.session_state.messages.append({"role": "assistant", "content": response_text})


    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")


import streamlit as st
import pandas as pd
import google.generativeai as genai
import os

# --- Configure Gemini API ---
# WARNING: Hardcoding API keys directly in code is NOT recommended for security reasons.
# It's better to use Streamlit's secrets management (st.secrets).
# However, as per user instruction, the API key is placed directly here for ease of use.

# <<< IMPORTANT: Replace "YOUR_GEMINI_API_KEY_HERE" with your actual API key >>>
api_key = "AIzaSyDzirWUubBVyjF10_JZ8UVSd6c6nnTKpLw" 

# Configure genai only if an API key is provided (even if hardcoded)
model = None # Initialize model as None
if api_key and api_key != "YOUR_GEMINI_API_KEY_HERE":
    try:
        genai.configure(api_key=api_key)
        # Use a model name appropriate for text generation, e.g., "gemini-pro"
        model = genai.GenerativeModel('gemini-pro')
        # st.success("Gemini API با موفقیت پیکربندی شد.") # Optional success message
    except Exception as e:
        st.error(f"خطا در بارگذاری مدل Gemini: {e}")
        model = None # Ensure model is None if loading fails

def render_ai_analysis(farm_data_df, filters):
    """
    Renders the AI analysis section with Gemini functionality
    """
    st.title("🧠 تحلیل هوشمند با Gemini")
    
    if farm_data_df.empty:
        st.warning("داده‌های مزارع بارگذاری نشده است")
        return
    
    # Check if API key is provided and model is loaded
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
         st.info("لطفاً کلید Gemini API را در ابتدای فایل ai_analysis.py وارد کنید تا قابلیت تحلیل هوشمند فعال شود.")
         return

    if not model:
         st.warning("مدل Gemini بارگذاری نشد. لطفاً کلید API و اتصال اینترنت را بررسی کنید.")
         return
    
    # Filter data based on selected farm if available
    filtered_df = farm_data_df
    farm_name_col = 'farm_name' if 'farm_name' in farm_data_df.columns else 'name'
    
    selected_farm = filters.get('selected_farm')
    if selected_farm:
        filtered_df = farm_data_df[farm_data_df[farm_name_col] == selected_farm]
        if filtered_df.empty:
             st.warning(f"مزرعه \"{selected_farm}\" در داده‌ها یافت نشد.")
             return
    
    # AI analysis section
    st.write("با استفاده از قدرت هوش مصنوعی Gemini، می‌توانید سوالات خود را درباره داده‌های مزارع نیشکر بپرسید.")
    
    # Display simplified analysis options
    st.subheader("گزینه‌های تحلیل سریع")
    
    option = st.selectbox(
        "انتخاب نوع تحلیل سریع",
        ["تحلیل عملکرد مزرعه", "ارزیابی سلامت گیاهان", "پیش‌بینی محصول", "توصیه‌های آبیاری", "پرسش آزاد"],
        key="ai_analysis_option"
    )
    
    prompt_prefix = {
        "تحلیل عملکرد مزرعه": "لطفاً عملکرد این مزرعه نیشکر را با توجه به داده‌های زیر تحلیل کنید: ",
        "ارزیابی سلامت گیاهان": "وضعیت سلامت گیاهان نیشکر این مزرعه را بر اساس داده‌های NDVI زیر ارزیابی کنید: ",
        "پیش‌بینی محصول": "با توجه به داده‌های زیر، میزان محصول نیشکر این مزرعه را پیش‌بینی کنید: ",
        "توصیه‌های آبیاری": "با توجه به داده‌های زیر، توصیه‌های آبیاری برای این مزرعه نیشکر ارائه دهید: ",
        "پرسش آزاد": "با توجه به داده‌های زیر، به سوال من پاسخ دهید: "
    }
    
    # User input for AI query
    user_query_text = st.text_area(
        "سوال یا دستور خود را بنویسید:",
        value=prompt_prefix[option],
        height=150,
        key="ai_user_query"
    )
    
    # Create context from filtered farm data
    # Convert DataFrame to a string format suitable for the model
    if not filtered_df.empty:
         farm_data_context = filtered_df.to_markdown(index=False)
         context_prompt = f"\n\nداده‌های مزرعه (یا مزارع) انتخاب شده:\n{farm_data_context}\n\n"
    else:
         farm_data_context = farm_data_df.to_markdown(index=False) # Provide all data if no farm selected
         context_prompt = f"\n\nداده‌های کلی مزارع:\n{farm_data_context}\n\n"
         if selected_farm:
             context_prompt += f"توجه: مزرعه \"{selected_farm}\" انتخاب شده است اما در مجموعه داده فیلتر شده یافت نشد. تحلیل بر اساس کل داده‌ها انجام می‌شود.\n\n"

    full_prompt = user_query_text + context_prompt

    if st.button("ارسال به Gemini", key="send_to_gemini_button"):
        if not user_query_text:
             st.warning("لطفاً سوال یا دستور خود را وارد کنید.")
             return

        with st.spinner("⏳ Gemini در حال پردازش درخواست..."):
            try:
                # Call the actual Gemini API
                response = model.generate_content(full_prompt)

                # Display response using enhanced styling
                st.subheader("پاسخ تحلیل هوشمند:")

                # Check if the response has parts and display them
                if response and response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                     # Join content parts into a single string
                    response_text = "".join([part.text for part in response.candidates[0].content.parts])

                    st.markdown(f"""
                    <div class="gemini-response-report">
                    {response_text}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                     st.error("Gemini پاسخ معتبری برنگرداند.")
                     if response and response.prompt_feedback:
                         st.warning(f"Prompt feedback: {response.prompt_feedback}")

            except Exception as e:
                st.error(f"خطا در برقراری ارتباط با Gemini API: {str(e)}")
                st.info("لطفاً از صحت کلید API خود اطمینان حاصل کرده و اتصال اینترنت را بررسی کنید.") 
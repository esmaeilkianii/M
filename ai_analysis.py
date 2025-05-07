import streamlit as st
import pandas as pd
import datetime
import ee
from utils.gemini_functions import (
    ask_gemini, generate_farm_report, analyze_time_series,
    suggest_farm_actions, answer_general_question
)
from utils.gee_functions import get_index_time_series

def render_ai_analysis(farm_data_df, filters):
    """Render the AI analysis tab content
    
    Args:
        farm_data_df: DataFrame containing farm data
        filters: Dict containing selected filters
    """
    # Unpack filters
    selected_day = filters['selected_day']
    filtered_farms_df = filters['filtered_farms_df']
    selected_farm_name = filters['selected_farm_name']
    selected_index = filters['selected_index']
    index_options = filters['index_options']
    date_range = filters['date_range']
    
    # Header with animation
    st.markdown("""
    <div class="card-container">
        <h1 style="margin-bottom: 10px;">💡 تحلیل هوشمند با Gemini</h1>
        <p>استفاده از هوش مصنوعی برای تحلیل وضعیت مزارع</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create some variables for reuse
    selected_farm_details = None
    selected_farm_geom = None
    ranking_df_sorted = None
    
    # Retrieve farm details if a specific farm is selected
    if selected_farm_name != "همه مزارع":
        selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        lat = selected_farm_details['عرض جغرافیایی']
        lon = selected_farm_details['طول جغرافیایی']
        selected_farm_geom = ee.Geometry.Point([lon, lat])
    
    # Display AI analysis options
    st.markdown("""
    <div class="analysis-box">
        <h4>🔍 امکانات تحلیل هوشمند</h4>
        <ul>
            <li>پاسخگویی به سوالات تخصصی در مورد وضعیت مزارع</li>
            <li>تحلیل روند زمانی شاخص‌های گیاهی</li>
            <li>تولید گزارش‌های خودکار از وضعیت مزارع</li>
            <li>پیشنهاد اقدامات کشاورزی بر اساس شاخص‌ها</li>
        </ul>
        <p><strong>توجه:</strong> پاسخ‌های ارائه شده توسط هوش مصنوعی Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان کشاورزی شوند.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Section 1: Smart Q&A
    st.markdown("""
    <div class="card-container">
        <h2>💬 پاسخ هوشمند به سوالات</h2>
        <p>سوال خود را در مورد مزرعه انتخاب شده یا وضعیت کلی مزارع بپرسید</p>
    </div>
    """, unsafe_allow_html=True)
    
    user_farm_q = st.text_input(
        "سوال خود را وارد کنید:", 
        key="gemini_farm_q",
        placeholder="مثال: علت کاهش شاخص NDVI در مزارع چیست؟"
    )
    
    if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q", type="primary"):
        if not user_farm_q:
            st.info("لطفاً سوال خود را وارد کنید.")
        else:
            with st.spinner("در حال پردازش پاسخ با Gemini..."):
                prompt = ""
                context_data = ""
                
                # Prepare context data for selected farm
                if selected_farm_name != "همه مزارع" and selected_farm_details is not None:
                    # Collect farm indices data if available
                    try:
                        farm_indices_df = farm_data_df[farm_data_df['مزرعه'] == selected_farm_name]
                        if len(farm_indices_df) > 0:
                            context_data = f"داده‌های مزرعه '{selected_farm_name}' برای شاخص {selected_index}:\n"
                            
                            # Add more context based on the data we have
                            context_data += f"- مساحت: {selected_farm_details.get('مساحت', 'N/A')} هکتار\n"
                            context_data += f"- واریته: {selected_farm_details.get('واریته', 'N/A')}\n"
                            context_data += f"- کانال: {selected_farm_details.get('کانال', 'N/A')}\n"
                            context_data += f"- سن: {selected_farm_details.get('سن', 'N/A')}\n"
                            context_data += f"- اداره: {selected_farm_details.get('اداره', 'N/A')}\n"
                            
                            prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. " \
                                    f"کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'.\n{context_data}\n" \
                                    f"لطفاً بر اساس این داده‌ها و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."
                    except Exception as e:
                        prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. " \
                                f"کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'. " \
                                f"داده‌های کافی برای این مزرعه در دسترس نیست. لطفاً به صورت کلی پاسخ دهید."
                
                else:  # "همه مزارع" or no specific farm data
                    context_data = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{selected_index}' در حال بررسی است. " \
                                  f"تعداد {len(filtered_farms_df)} مزرعه در این روز فیلتر شده‌اند."
                    
                    prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. " \
                            f"کاربر سوالی در مورد وضعیت کلی مزارع پرسیده است: '{user_farm_q}'.\n{context_data}\n" \
                            f"لطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."
                
                response = ask_gemini(prompt)
                
                st.markdown("""
                <div class="card-container" style="background-color: rgba(46, 125, 50, 0.05); border-right: 4px solid #2e7d32;">
                """, unsafe_allow_html=True)
                
                st.markdown(response)
                
                st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Section 2: Farm Report Generation
    st.markdown("""
    <div class="card-container">
        <h2>📄 تولید گزارش خودکار هفتگی</h2>
    </div>
    """, unsafe_allow_html=True)
    
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را برای تولید گزارش انتخاب کنید.")
    elif selected_farm_details is None:
        st.info(f"داده‌های جزئی برای مزرعه {selected_farm_name} یافت نشد.")
    else:
        # In a real application, we would use the ranking_df or fetch additional data
        # For this demo, we'll simulate some farm data
        if st.button(f"📝 تولید گزارش برای مزرعه '{selected_farm_name}'", key="btn_gemini_report"):
            with st.spinner("در حال تولید گزارش با Gemini..."):
                # Simulate farm data (in a real app, use actual data)
                current_val = "0.76"  # Example value
                previous_val = "0.71"
                change_val = "+0.05"
                status = "رشد مثبت"
                
                report = generate_farm_report(
                    selected_farm_name, selected_index, index_options,
                    selected_farm_details, current_val, previous_val, 
                    change_val, status, date_range
                )
                
                st.markdown(f"""
                <div class="card-container" style="background-color: rgba(21, 101, 192, 0.05); border-right: 4px solid #1565c0;">
                    <h3>گزارش هفتگی مزرعه {selected_farm_name}</h3>
                    <p><strong>تاریخ گزارش:</strong> {datetime.date.today().strftime('%Y-%m-%d')}</p>
                    <p><strong>بازه زمانی مورد بررسی:</strong> {date_range['start_current']} الی {date_range['end_current']}</p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(report)
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Section 3: Time Series Analysis
    st.markdown("""
    <div class="card-container">
        <h2>📉 تحلیل روند زمانی شاخص</h2>
    </div>
    """, unsafe_allow_html=True)
    
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را برای تحلیل سری زمانی انتخاب کنید.")
    elif selected_farm_geom:
        is_point_geom_gemini = False
        try:
            if selected_farm_geom.type().getInfo() == 'Point': 
                is_point_geom_gemini = True
        except Exception:
            if isinstance(selected_farm_geom, ee.geometry.Point): 
                is_point_geom_gemini = True
        
        if is_point_geom_gemini:
            if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{selected_farm_name}'", key="btn_gemini_timeseries"):
                with st.spinner(f"در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                    # Get time series data
                    today = datetime.date.today()
                    timeseries_end_date_gemini = today.strftime('%Y-%m-%d')
                    timeseries_start_date_gemini = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d')  # Last 6 months
                    
                    ts_df_gemini, ts_error_gemini = get_index_time_series(
                        selected_farm_geom, selected_index,
                        start_date=timeseries_start_date_gemini, end_date=timeseries_end_date_gemini
                    )
                    
                    if ts_error_gemini:
                        st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini}")
                    elif ts_df_gemini is not None and not ts_df_gemini.empty:
                        # Get analysis from Gemini
                        analysis = analyze_time_series(
                            selected_farm_name, selected_index, ts_df_gemini, date_range
                        )
                        
                        st.markdown(f"""
                        <div class="card-container" style="background-color: rgba(245, 124, 0, 0.05); border-right: 4px solid #f57c00;">
                            <h3>تحلیل روند شاخص {selected_index} برای مزرعه {selected_farm_name}</h3>
                            <p><strong>دوره زمانی:</strong> 6 ماه گذشته</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        st.markdown(analysis)
                    else:
                        st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای مزرعه {selected_farm_name} یافت نشد.")
        else:
            st.info("تحلیل سری زمانی فقط برای مزارع منفرد (نقطه‌ای) امکان‌پذیر است.")
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Section 4: Suggested Actions
    st.markdown("""
    <div class="card-container">
        <h2>🌱 پیشنهاد اقدامات کشاورزی</h2>
    </div>
    """, unsafe_allow_html=True)
    
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را برای دریافت پیشنهادات انتخاب کنید.")
    elif selected_farm_details is None:
        st.info(f"داده‌های کافی برای ارائه پیشنهاد برای مزرعه {selected_farm_name} موجود نیست.")
    else:
        # Simulate farm data (in a real app, use actual data)
        if st.button(f"💡 دریافت پیشنهادات برای مزرعه '{selected_farm_name}'", key="btn_gemini_actions"):
            with st.spinner("در حال دریافت پیشنهادات کشاورزی با Gemini..."):
                # Simulate farm data
                current_val = "0.76"  # Example value
                status = "رشد مثبت"
                
                suggestions = suggest_farm_actions(
                    selected_farm_name, selected_index, index_options, current_val, status
                )
                
                st.markdown(f"""
                <div class="card-container pulse-element" style="background-color: rgba(46, 125, 50, 0.05); border-right: 4px solid #2e7d32;">
                    <h3>پیشنهادات اقدام برای مزرعه {selected_farm_name}</h3>
                    <p><strong>شاخص فعلی:</strong> {selected_index} = {current_val}</p>
                    <p><strong>وضعیت:</strong> <span class="status-badge status-positive">{status}</span></p>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(suggestions)
    
    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Section 5: General Q&A
    st.markdown("""
    <div class="card-container">
        <h2>🗣️ پاسخ به سوالات عمومی</h2>
        <p>سوالات کلی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور یا این سامانه بپرسید</p>
    </div>
    """, unsafe_allow_html=True)
    
    user_general_q = st.text_input(
        "سوال عمومی خود را وارد کنید:", 
        key="gemini_general_q",
        placeholder="مثال: شاخص NDVI چیست و چگونه به مدیریت مزرعه کمک می‌کند؟"
    )
    
    if st.button("❓ پرسیدن سوال از Gemini", key="btn_gemini_general_q"):
        if not user_general_q:
            st.info("لطفاً سوال خود را وارد کنید.")
        else:
            with st.spinner("در حال جستجو برای پاسخ با Gemini..."):
                response = answer_general_question(user_general_q, selected_farm_name)
                
                st.markdown("""
                <div class="card-container" style="background-color: rgba(21, 101, 192, 0.05); border-right: 4px solid #1565c0;">
                """, unsafe_allow_html=True)
                
                st.markdown(response)
                
                st.markdown("</div>", unsafe_all
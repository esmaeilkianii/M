import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
import traceback
from streamlit_folium import st_folium
from evapotranspiration import (
    calculate_et_sebal,
    get_et_time_series,
    visualize_et,
    analyze_et_trends,
    plot_et_time_series,
    create_water_requirement_cards
)

# Function to create ET mapping page
def et_mapping_page(farm_data_df, selected_farm_name, selected_farm_geom, service_account_file):
    """Create the evapotranspiration mapping page."""
    st.title("🌱 نقشه تبخیر و تعرق واقعی")
    st.markdown("""این صفحه با استفاده از داده‌های ماهواره‌ای و الگوریتم‌های SEBAL/METRIC، تبخیر و تعرق واقعی را محاسبه و نمایش می‌دهد.""")
    
    # Sidebar options
    st.sidebar.header("تنظیمات تبخیر و تعرق")
    
    # Satellite data source selection
    sensor_options = {
        "MODIS": "MODIS (رزولوشن 1 کیلومتر، بازه زمانی روزانه)",
        "Landsat": "Landsat 8 (رزولوشن 30 متر، بازه زمانی 16 روزه)"
    }
    selected_sensor = st.sidebar.selectbox(
        "منبع داده ماهواره‌ای:",
        options=list(sensor_options.keys()),
        format_func=lambda x: sensor_options[x],
        index=0
    )
    
    # Date range selection
    today = datetime.date.today()
    default_end_date = today
    default_start_date = today - datetime.timedelta(days=30)
    
    start_date = st.sidebar.date_input(
        "تاریخ شروع:",
        value=default_start_date,
        max_value=today
    )
    
    end_date = st.sidebar.date_input(
        "تاریخ پایان:",
        value=default_end_date,
        min_value=start_date,
        max_value=today
    )
    
    # Convert dates to string format for GEE
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    # Farm selection
    if selected_farm_name == "همه مزارع":
        st.warning("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا تحلیل تبخیر و تعرق آن نمایش داده شود.")
        return
    
    # Get farm details if available
    farm_details = None
    if selected_farm_name != "همه مزارع":
        farm_details = farm_data_df[farm_data_df['مزرعه'] == selected_farm_name].iloc[0]
    
    # Display farm information
    if farm_details is not None:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("مزرعه", selected_farm_name)
        with col2:
            st.metric("مساحت (هکتار)", f"{farm_details.get('مساحت', 1.0):,.2f}" if pd.notna(farm_details.get('مساحت')) else "1.0")
        with col3:
            st.metric("گروه", f"{farm_details.get('گروه', 'N/A')}")
    
    # Calculate ET using SEBAL/METRIC algorithm
    with st.spinner("در حال محاسبه تبخیر و تعرق با استفاده از الگوریتم SEBAL/METRIC..."):
        try:
            # Calculate ET
            et_result = calculate_et_sebal(
                selected_farm_geom,
                start_date_str,
                end_date_str,
                sensor=selected_sensor
            )
            
            if et_result['count'] == 0:
                st.warning(f"هیچ تصویر {selected_sensor} در بازه زمانی انتخاب شده یافت نشد.")
                return
            
            # Get ET image
            et_image = et_result['et_image']
            
            # Create map
            m = geemap.Map(
                location=[farm_details['latitude'], farm_details['longitude']],
                zoom=14,
                add_google_map=False
            )
            m.add_basemap("HYBRID")
            
            # Add ET layer to map
            visualize_et(et_image, selected_farm_geom, m)
            
            # Add farm marker
            folium.Marker(
                location=[farm_details['latitude'], farm_details['longitude']],
                popup=f"مزرعه: {selected_farm_name}",
                tooltip=selected_farm_name,
                icon=folium.Icon(color='red', icon='star')
            ).add_to(m)
            
            # Display map
            st.subheader("🗺️ نقشه تبخیر و تعرق واقعی")
            st_folium(m, width=None, height=500, use_container_width=True)
            
            # Get ET time series
            et_df = get_et_time_series(
                selected_farm_geom,
                start_date_str,
                end_date_str,
                sensor=selected_sensor
            )
            
            # Analyze ET trends
            et_analysis = analyze_et_trends(et_df)
            
            # Display ET statistics in colored cards
            st.subheader("📊 آمار تبخیر و تعرق")
            
            # Create colored cards for statistics
            stats_cols = st.columns(4)
            with stats_cols[0]:
                st.markdown(
                    f"""<div style='background-color: #e6f7ff; padding: 10px; border-radius: 10px;'>
                    <h3 style='text-align: center; color: #0066cc;'>میانگین ET</h3>
                    <h2 style='text-align: center; color: #0066cc;'>{et_analysis['mean_et']:.2f} mm/day</h2>
                    </div>""",
                    unsafe_allow_html=True
                )
            
            with stats_cols[1]:
                st.markdown(
                    f"""<div style='background-color: #ffe6e6; padding: 10px; border-radius: 10px;'>
                    <h3 style='text-align: center; color: #cc0000;'>حداکثر ET</h3>
                    <h2 style='text-align: center; color: #cc0000;'>{et_analysis['max_et']:.2f} mm/day</h2>
                    </div>""",
                    unsafe_allow_html=True
                )
            
            with stats_cols[2]:
                st.markdown(
                    f"""<div style='background-color: #e6ffe6; padding: 10px; border-radius: 10px;'>
                    <h3 style='text-align: center; color: #006600;'>حداقل ET</h3>
                    <h2 style='text-align: center; color: #006600;'>{et_analysis['min_et']:.2f} mm/day</h2>
                    </div>""",
                    unsafe_allow_html=True
                )
            
            with stats_cols[3]:
                trend_color = "#0066cc" if et_analysis['trend'] == "stable" else ("#cc0000" if et_analysis['trend'] == "decreasing" else "#006600")
                trend_bg = "#e6f7ff" if et_analysis['trend'] == "stable" else ("#ffe6e6" if et_analysis['trend'] == "decreasing" else "#e6ffe6")
                trend_text = "ثابت" if et_analysis['trend'] == "stable" else ("کاهشی" if et_analysis['trend'] == "decreasing" else "افزایشی")
                
                st.markdown(
                    f"""<div style='background-color: {trend_bg}; padding: 10px; border-radius: 10px;'>
                    <h3 style='text-align: center; color: {trend_color};'>روند ET</h3>
                    <h2 style='text-align: center; color: {trend_color};'>{trend_text}</h2>
                    </div>""",
                    unsafe_allow_html=True
                )
            
            # Display water requirements
            st.subheader("💧 نیاز آبی")
            farm_area = farm_details.get('مساحت', 1.0) if pd.notna(farm_details.get('مساحت')) else 1.0
            create_water_requirement_cards(et_analysis, farm_area)
            
            # Display time series chart
            st.subheader("📈 نمودار سری زمانی تبخیر و تعرق")
            if not et_df.empty:
                fig = plot_et_time_series(et_df, selected_farm_name)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("داده‌ای برای نمایش نمودار سری زمانی تبخیر و تعرق یافت نشد.")
            
            # Display water stress analysis
            st.subheader("⚠️ تحلیل تنش آبی")
            if et_analysis['water_stress_days'] is not None:
                stress_percentage = (et_analysis['water_stress_days'] / len(et_df)) * 100 if len(et_df) > 0 else 0
                
                # Create a gauge chart for water stress
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=stress_percentage,
                    title={'text': "درصد روزهای با تنش آبی احتمالی"},
                    gauge={
                        'axis': {'range': [0, 100]},
                        'bar': {'color': "#ff9999"},
                        'steps': [
                            {'range': [0, 30], 'color': "#e6ffe6"},
                            {'range': [30, 70], 'color': "#fff3e6"},
                            {'range': [70, 100], 'color': "#ffe6e6"}
                        ],
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': stress_percentage
                        }
                    }
                ))
                
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
                
                # Add interpretation
                if stress_percentage < 30:
                    st.success("🟢 تنش آبی کم: مزرعه در وضعیت مطلوبی از نظر آبی قرار دارد.")
                elif stress_percentage < 70:
                    st.warning("🟠 تنش آبی متوسط: نیاز به بررسی برنامه آبیاری و افزایش احتمالی آب مصرفی.")
                else:
                    st.error("🔴 تنش آبی بالا: نیاز فوری به اصلاح برنامه آبیاری و افزایش آب مصرفی.")
            else:
                st.info("داده‌ای برای تحلیل تنش آبی یافت نشد.")
            
            # Add recommendations section
            st.subheader("🔍 توصیه‌های آبیاری")
            if et_analysis['mean_et'] is not None:
                # Calculate irrigation recommendations
                daily_water_req = et_analysis['mean_et'] * farm_area * 10  # mm/day * ha * 10 = m³/day
                
                # Create recommendations based on ET and trend
                recommendations = []
                
                if et_analysis['trend'] == 'increasing':
                    recommendations.append("افزایش میزان آبیاری متناسب با روند افزایشی تبخیر و تعرق")
                elif et_analysis['trend'] == 'decreasing':
                    recommendations.append("امکان کاهش تدریجی میزان آبیاری با توجه به روند کاهشی تبخیر و تعرق")
                
                if et_analysis['water_stress_days'] and et_analysis['water_stress_days'] > len(et_df) * 0.3:
                    recommendations.append("افزایش تعداد دفعات آبیاری برای کاهش روزهای تنش آبی")
                
                if not recommendations:
                    recommendations.append("ادامه برنامه آبیاری فعلی با توجه به شرایط مطلوب")
                
                # Display recommendations
                for i, rec in enumerate(recommendations):
                    st.markdown(f"**{i+1}. {rec}**")
                
                # Add specific irrigation schedule
                st.markdown("### برنامه پیشنهادی آبیاری")
                st.markdown(f"**میزان آب مورد نیاز روزانه:** {daily_water_req:.1f} متر مکعب")
                st.markdown(f"**دور آبیاری پیشنهادی:** {3 if et_analysis['mean_et'] > 7 else (5 if et_analysis['mean_et'] > 5 else 7)} روز")
            else:
                st.info("داده‌ای برای ارائه توصیه‌های آبیاری یافت نشد.")
            
        except Exception as e:
            st.error(f"خطا در محاسبه تبخیر و تعرق: {e}")
            st.error(traceback.format_exc())
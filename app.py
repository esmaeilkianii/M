import streamlit as st
import pandas as pd
import ee
import datetime
import folium
from streamlit_folium import folium_static
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import math # برای محاسبات ریاضی مانند رطوبت
# --- 5. رابط کاربری Streamlit ---
st.set_page_config(layout="wide", page_title="محاسبه نیاز آبی نیشکر")

st.title("📊 محاسبه نیاز آبی مزارع نیشکر")

# --- 0. تنظیمات اولیه و احراز هویت GEE ---
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
EE_SERVICE_ACCOUNT_EMAIL = 'ee-esmaeilkiani13877@ee-esmaeilkiani13877.iam.gserviceaccount.com'

@st.cache_resource
def initialize_gee():
    try:
        credentials = ee.ServiceAccountCredentials(email=EE_SERVICE_ACCOUNT_EMAIL, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials)
        st.success("Google Earth Engine با موفقیت مقداردهی اولیه شد.")
        return True
    except Exception as e:
        st.error(f"خطا در مقداردهی اولیه Google Earth Engine: {e}")
        st.error("لطفاً از معتبر بودن فایل Service Account و دسترسی‌های لازم اطمینان حاصل کنید.")
        return False

gee_initialized = initialize_gee()

# --- 1. بارگذاری داده‌های مزارع ---
@st.cache_data
def load_farm_data(csv_path="cleaned_output.csv"):
    try:
        df = pd.read_csv(csv_path)
        # اطمینان از اینکه ستون 'سن' عددی است
        df['سن'] = pd.to_numeric(df['سن'], errors='coerce')
        # اطمینان از اینکه ستون 'مساحت' عددی است
        df['مساحت'] = pd.to_numeric(df['مساحت'], errors='coerce')
        # تبدیل coordinates_missing به بولین اگر رشته‌ای است
        if 'coordinates_missing' in df.columns and df['coordinates_missing'].dtype == 'object':
            df['coordinates_missing'] = df['coordinates_missing'].str.lower().map({'true': True, 'false': False, '': False}).fillna(False)
        elif 'coordinates_missing' not in df.columns:
             df['coordinates_missing'] = False # اگر ستون وجود ندارد، فرض می کنیم مختصات موجود است

        # حذف ردیف‌هایی که سن یا مساحت معتبر ندارند
        df.dropna(subset=['سن', 'مساحت', 'عرض جغرافیایی', 'طول جغرافیایی'], inplace=True)
        return df
    except FileNotFoundError:
        st.error(f"فایل {csv_path} یافت نشد. لطفاً فایل CSV مشخصات مزارع را در کنار برنامه قرار دهید.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        return pd.DataFrame()


farms_df = load_farm_data()

# --- 2. جدول Kc بر اساس سن گیاه (روز) ---
KC_STAGES = {
    "initial": (0, 30, 0.35),
    "development_1": (31, 60, 0.55),
    "development_2": (61, 90, 0.80),
    "mid_season_1": (91, 150, 1.15),
    "mid_season_2": (151, 210, 1.25),
    "mid_season_3": (211, 270, 1.20),
    "late_season_1": (271, 330, 0.90),
    "late_season_2": (331, 365, 0.70)
}

def get_kc(plant_age_days):
    for stage, (start_day, end_day, kc_value) in KC_STAGES.items():
        if start_day <= plant_age_days <= end_day:
            return kc_value
    if plant_age_days > 365:
        return KC_STAGES["late_season_2"][2]
    return 0.2

# --- 3. دریافت داده‌های هواشناسی از GEE ---
@st.cache_data(ttl=3600)
def get_weather_data_gee(latitude, longitude, target_datetime):
    if not gee_initialized:
        return None
    try:
        point = ee.Geometry.Point(float(longitude), float(latitude))
        start_date_gee = ee.Date(target_datetime.strftime('%Y-%m-%dT%H:%M:%S'))
        end_date_gee = start_date_gee.advance(1, 'hour')

        era5_land = ee.ImageCollection('ECMWF/ERA5_LAND/HOURLY') \
            .filterBounds(point) \
            .filterDate(start_date_gee, end_date_gee) \
            .select(['temperature_2m', 'dewpoint_temperature_2m',
                     'surface_solar_radiation_downwards_hourly',
                     'u_component_of_wind_10m', 'v_component_of_wind_10m',
                     'potential_evaporation'])

        if era5_land.size().getInfo() == 0:
            st.warning(f"داده‌ای از ERA5-Land برای تاریخ {target_datetime.strftime('%Y-%m-%d %H:00')} در موقعیت ({latitude}, {longitude}) یافت نشد.")
            return None

        image = era5_land.first()
        data = image.reduceRegion(reducer=ee.Reducer.first(), geometry=point, scale=11132).getInfo()

        if not data or 'potential_evaporation' not in data or data['potential_evaporation'] is None:
            st.warning(f"مقدار 'potential_evaporation' برای ساعت مورد نظر یافت نشد.")
            return None

        et0_mm_per_hour = data.get('potential_evaporation', 0) * 1000
        temp_c = data.get('temperature_2m', 273.15) - 273.15
        dewpoint_c = data.get('dewpoint_temperature_2m', 273.15) - 273.15
        u_wind = data.get('u_component_of_wind_10m', 0)
        v_wind = data.get('v_component_of_wind_10m', 0)
        wind_speed_mps = (u_wind**2 + v_wind**2)**0.5
        solar_radiation_j_m2_h = data.get('surface_solar_radiation_downwards_hourly', 0)

        e_s = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
        e_d = 6.112 * math.exp((17.67 * dewpoint_c) / (dewpoint_c + 243.5))
        rh_percent = (e_d / e_s) * 100 if e_s > 0 else 0
        rh_percent = min(max(rh_percent, 0), 100)

        return {
            "et0_mm_per_hour": et0_mm_per_hour,
            "temperature_c": temp_c,
            "relative_humidity_percent": rh_percent,
            "wind_speed_mps": wind_speed_mps,
            "solar_radiation_j_m2_h": solar_radiation_j_m2_h
        }
    except Exception as e:
        st.error(f"خطا در ارتباط با GEE یا پردازش داده‌های هواشناسی: {e}")
        return None

# --- 4. محاسبه نیاز آبی (CWR) ---
def calculate_cwr(et0_mm_per_hour, kc, area_hectare):
    area_m2 = area_hectare * 10000
    cwr_mm_per_hour = et0_mm_per_hour * kc
    cwr_m3_per_hour = (cwr_mm_per_hour / 1000) * area_m2
    cwr_liters_per_hour = cwr_m3_per_hour * 1000
    return cwr_liters_per_hour, cwr_m3_per_hour, cwr_mm_per_hour

if not gee_initialized:
    st.warning("سرویس Google Earth Engine مقداردهی اولیه نشده است. محاسبات ممکن است انجام نشود.")
    # st.stop() # اگر می‌خواهید برنامه متوقف شود

if farms_df.empty:
    st.error("داده‌های مزارع بارگذاری نشد یا خالی است. لطفاً فایل CSV را بررسی کنید و از وجود داده‌های معتبر اطمینان حاصل کنید.")
    st.stop()

col_input, col_map = st.columns([1, 1])

with col_input:
    st.header("ورودی‌های کاربر")
    farm_names = farms_df['مزرعه'].tolist()
    if not farm_names:
        st.error("هیچ مزرعه‌ای در فایل CSV یافت نشد یا داده‌های لازم برای نمایش وجود ندارد.")
        st.stop()
        
    selected_farm_name = st.selectbox("انتخاب مزرعه:", farm_names)
    selected_farm_info = farms_df[farms_df['مزرعه'] == selected_farm_name].iloc[0]

    st.subheader(f"مشخصات مزرعه: {selected_farm_name}")
    if selected_farm_info['coordinates_missing']:
        st.warning("⚠️ مختصات جغرافیایی برای این مزرعه در فایل ثبت نشده یا ناقص است. محاسبات ممکن است دقیق نباشد.")

    st.markdown(f"""
    - **مساحت:** {selected_farm_info['مساحت']} هکتار
    - **سن گیاه (از فایل):** {selected_farm_info['سن']} روز
    - **واریته:** {selected_farm_info['واریته']}
    - **کانال:** {selected_farm_info.get('کانال', 'نامشخص')}
    - **اداره:** {selected_farm_info.get('اداره', 'نامشخص')}
    - **مختصات:** ({selected_farm_info['عرض جغرافیایی']:.4f}, {selected_farm_info['طول جغرافیایی']:.4f})
    """)

    target_date = st.date_input("تاریخ مورد نظر برای آبیاری:", datetime.date.today())
    target_hour = st.slider("ساعت مورد نظر (0-23):", 0, 23, datetime.datetime.now().hour)
    target_datetime = datetime.datetime.combine(target_date, datetime.time(hour=target_hour))

    # سن گیاه مستقیماً از CSV خوانده می‌شود
    plant_age_at_target_date = int(selected_farm_info['سن'])
    st.info(f"سن پایه گیاه (از فایل): **{plant_age_at_target_date} روز**. Kc بر این اساس محاسبه می‌شود.")
    st.caption("توجه: برای نمودار هفتگی، سن گیاه برای هر روز هفته متناسب با تاریخ انتخابی تعدیل خواهد شد.")


    kc_value = get_kc(plant_age_at_target_date)
    st.info(f"ضریب گیاهی (Kc) محاسبه شده بر اساس سن پایه: **{kc_value:.2f}**")

with col_map:
    st.header("موقعیت مزرعه روی نقشه")
    try:
        map_center = [float(selected_farm_info['عرض جغرافیایی']), float(selected_farm_info['طول جغرافیایی'])]
        m = folium.Map(location=map_center, zoom_start=12)
        folium.Marker(
            location=map_center,
            popup=f"{selected_farm_info['مزرعه']}\nمساحت: {selected_farm_info['مساحت']} هکتار\nسن: {selected_farm_info['سن']} روز",
            tooltip=selected_farm_info['مزرعه']
        ).add_to(m)
        
        for idx, row in farms_df.iterrows():
            if row['مزرعه'] != selected_farm_name and not row['coordinates_missing']:
                 try:
                     folium.CircleMarker(
                        location=[float(row['عرض جغرافیایی']), float(row['طول جغرافیایی'])],
                        radius=5,
                        popup=f"{row['مزرعه']}",
                        tooltip=row['مزرعه'],
                        color='blue',
                        fill=True,
                        fill_color='blue'
                    ).add_to(m)
                 except Exception:
                     pass # اگر مختصات برای مزرعه دیگر هم مشکل داشت، رد شو
        folium_static(m, width=600, height=400)
    except Exception as e:
        st.error(f"خطا در نمایش نقشه: {e}. لطفاً مختصات جغرافیایی را در فایل CSV بررسی کنید.")


if st.button("محاسبه نیاز آبی", type="primary", disabled=bool(selected_farm_info['coordinates_missing'] and gee_initialized)):
    if selected_farm_info['coordinates_missing'] and gee_initialized:
        st.error("امکان محاسبه وجود ندارد زیرا مختصات جغرافیایی مزرعه مشخص نیست.")
    else:
        st.header(f"نتایج برای مزرعه '{selected_farm_name}' در تاریخ {target_datetime.strftime('%Y-%m-%d %H:00')}")
        
        with st.spinner("در حال دریافت داده‌های هواشناسی از GEE و محاسبه..."):
            weather_data = get_weather_data_gee(
                selected_farm_info['عرض جغرافیایی'],
                selected_farm_info['طول جغرافیایی'],
                target_datetime
            )

        if weather_data:
            et0 = weather_data["et0_mm_per_hour"]
            
            col_weather, col_cwr = st.columns(2)
            with col_weather:
                st.subheader("داده‌های هواشناسی (ساعتی):")
                st.metric(label="تبخیر و تعرق مرجع (ET₀)", value=f"{et0:.3f} mm/hour")
                st.metric(label="دما", value=f"{weather_data['temperature_c']:.1f} °C")
                st.metric(label="رطوبت نسبی", value=f"{weather_data['relative_humidity_percent']:.1f} %")
                st.metric(label="سرعت باد", value=f"{weather_data['wind_speed_mps']:.1f} m/s")
                st.metric(label="تابش خورشیدی", value=f"{weather_data['solar_radiation_j_m2_h'] / 3600000:.2f} MJ/m²/hour")


            cwr_liters, cwr_m3, cwr_mm = calculate_cwr(et0, kc_value, float(selected_farm_info['مساحت']))
            
            with col_cwr:
                st.subheader("نیاز آبی محاسبه شده:")
                st.metric(label="نیاز آبی گیاه (ETc)", value=f"{cwr_mm:.3f} mm/hour")
                st.success(f"**میزان آب مورد نیاز:**")
                st.markdown(f"### **{cwr_m3:,.2f} متر مکعب در ساعت**")
                st.markdown(f"### **{cwr_liters:,.0f} لیتر در ساعت**")

            st.subheader("نمودار تغییرات نیاز آبی (تخمینی)")
            tab_daily, tab_weekly = st.tabs(["تغییرات روزانه", "تغییرات هفتگی (میانگین روزانه)"])

            # Kc برای نمودار روزانه همان kc_value محاسبه شده بر اساس سن از CSV است
            kc_for_daily_chart = kc_value

            with tab_daily:
                with st.spinner("در حال محاسبه نمودار روزانه..."):
                    hourly_et0_daily = []
                    hours_of_day_daily = []
                    hourly_cwr_m3_daily = []
                    current_day_start = datetime.datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
                    
                    for hour_offset in range(24):
                        dt_hourly = current_day_start + datetime.timedelta(hours=hour_offset)
                        weather_hourly = get_weather_data_gee(
                            selected_farm_info['عرض جغرافیایی'],
                            selected_farm_info['طول جغرافیایی'],
                            dt_hourly
                        )
                        if weather_hourly and weather_hourly["et0_mm_per_hour"] is not None:
                            et0_val = weather_hourly["et0_mm_per_hour"]
                            _, cwr_m3_val, _ = calculate_cwr(et0_val, kc_for_daily_chart, float(selected_farm_info['مساحت']))
                            hourly_et0_daily.append(et0_val)
                            hourly_cwr_m3_daily.append(cwr_m3_val)
                        else:
                            hourly_et0_daily.append(0)
                            hourly_cwr_m3_daily.append(0)
                        hours_of_day_daily.append(dt_hourly)

                    if hours_of_day_daily:
                        fig_daily, ax1 = plt.subplots(figsize=(12, 6))
                        color = 'tab:red'
                        ax1.set_xlabel(f'ساعت در تاریخ {target_date.strftime("%Y-%m-%d")}')
                        ax1.set_ylabel('نیاز آبی (m³/hour)', color=color)
                        ax1.plot(hours_of_day_daily, hourly_cwr_m3_daily, color=color, marker='o', linestyle='-')
                        ax1.tick_params(axis='y', labelcolor=color)
                        ax1.grid(True, linestyle='--', alpha=0.7)
                        ax2 = ax1.twinx()
                        color = 'tab:blue'
                        ax2.set_ylabel('ET₀ (mm/hour)', color=color)
                        ax2.plot(hours_of_day_daily, hourly_et0_daily, color=color, marker='x', linestyle='--')
                        ax2.tick_params(axis='y', labelcolor=color)
                        fig_daily.tight_layout()
                        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                        plt.title(f'تغییرات ساعتی نیاز آبی و ET₀ برای {selected_farm_name}')
                        st.pyplot(fig_daily)
                    else:
                        st.warning("داده کافی برای رسم نمودار روزانه یافت نشد.")

            with tab_weekly:
                 with st.spinner("در حال محاسبه نمودار هفتگی..."):
                    daily_avg_et0_weekly = []
                    days_of_week_weekly = []
                    daily_total_cwr_m3_weekly = []
                    
                    base_age_for_week = int(selected_farm_info['سن']) # سن از CSV به عنوان سن در target_date

                    for day_offset in range(-3, 4): # 7 days total
                        current_date_for_week = target_date + datetime.timedelta(days=day_offset)
                        
                        # تعدیل سن گیاه برای روز فعلی در هفته
                        # اگر day_offset=0 است، سن همان سن پایه است
                        # اگر day_offset=1 (فردا)، سن = سن پایه + 1
                        # اگر day_offset=-1 (دیروز)، سن = سن پایه - 1
                        plant_age_current_day_in_week = base_age_for_week + day_offset
                        kc_current_day_in_week = get_kc(plant_age_current_day_in_week)

                        temp_daily_et0_values = []
                        for h_offset in range(24):
                            dt_hourly_for_week = datetime.datetime.combine(current_date_for_week, datetime.time(hour=h_offset))
                            weather_h_week = get_weather_data_gee(
                                selected_farm_info['عرض جغرافیایی'],
                                selected_farm_info['طول جغرافیایی'],
                                dt_hourly_for_week
                            )
                            if weather_h_week and weather_h_week["et0_mm_per_hour"] is not None:
                                temp_daily_et0_values.append(weather_h_week["et0_mm_per_hour"])
                        
                        if temp_daily_et0_values:
                            # ET0 روزانه (mm/day) = جمع ET0 ساعتی (mm/hour)
                            et0_mm_per_day = sum(temp_daily_et0_values) # این جمع ET0 ساعتی برای یک روز است
                            
                            # CWR روزانه = ET0 روزانه (mm/day) * Kc
                            # برای تابع calculate_cwr، باید ET0 را به صورت mm/واحد زمان و مساحت را بدهیم
                            # اینجا et0_mm_per_day واحدش mm/day است. مساحت هم هکتار.
                            # cwr_liters, cwr_m3, cwr_mm_per_day_value = calculate_cwr(et0_mm_per_day / 24, kc_current_day_in_week, float(selected_farm_info['مساحت']))
                            # cwr_m3_per_day = cwr_m3_per_day_value * 24
                            
                            # روش ساده تر:
                            area_m2 = float(selected_farm_info['مساحت']) * 10000
                            cwr_m3_per_day = (et0_mm_per_day / 1000) * kc_current_day_in_week * area_m2


                            daily_avg_et0_weekly.append(et0_mm_per_day)
                            daily_total_cwr_m3_weekly.append(cwr_m3_per_day)
                        else:
                            daily_avg_et0_weekly.append(0)
                            daily_total_cwr_m3_weekly.append(0)
                        days_of_week_weekly.append(current_date_for_week)

                    if days_of_week_weekly:
                        fig_weekly, ax1_w = plt.subplots(figsize=(12, 6))
                        color = 'tab:green'
                        ax1_w.set_xlabel('تاریخ')
                        ax1_w.set_ylabel('نیاز آبی روزانه (m³/day)', color=color)
                        ax1_w.plot(days_of_week_weekly, daily_total_cwr_m3_weekly, color=color, marker='o', linestyle='-')
                        ax1_w.tick_params(axis='y', labelcolor=color)
                        ax1_w.grid(True, linestyle='--', alpha=0.7)
                        ax2_w = ax1_w.twinx()
                        color = 'tab:purple'
                        ax2_w.set_ylabel('ET₀ روزانه (mm/day)', color=color)
                        ax2_w.plot(days_of_week_weekly, daily_avg_et0_weekly, color=color, marker='x', linestyle='--')
                        ax2_w.tick_params(axis='y', labelcolor=color)
                        fig_weekly.tight_layout()
                        ax1_w.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                        plt.xticks(rotation=45)
                        plt.title(f'تغییرات هفتگی نیاز آبی و ET₀ (روزانه) برای {selected_farm_name}')
                        st.pyplot(fig_weekly)
                    else:
                        st.warning("داده کافی برای رسم نمودار هفتگی یافت نشد.")
        else:
            st.error("خطا در دریافت داده‌های هواشناسی. لطفاً ورودی‌ها و اتصال اینترنت را بررسی کنید.")

st.markdown("---")
st.caption("طراحی شده برای محاسبه نیاز آبی نیشکر با استفاده از GEE و Streamlit")
import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import os
from io import BytesIO
import requests # Needed for getThumbUrl download
import traceback
from streamlit_folium import st_folium
import base64
import google.generativeai as genai # Added for Gemini

# --- Custom CSS (Enhanced for Modern Look and Animations) ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/animate.css/4.1.1/animate.min.css');
        body {
            font-family: 'Vazirmatn', sans-serif;
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        }
        .main {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #ffffff;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            animation: fadeIn 1s ease-in-out;
        }
        .header {
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 20px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
            text-align: center;
            position: relative;
            overflow: hidden;
            animation: fadeIn 0.8s ease-in-out;
        }
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 900;
            text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            animation: bounceIn 1s ease-in-out;
        }
        .metric-card {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            border-radius: 15px;
            padding: 25px;
            margin: 15px 0;
            text-align: center;
            position: relative;
            overflow: hidden;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15);
            transition: all 0.5s ease;
            animation: bounceIn 0.8s ease-in-out;
        }
        .metric-card::after {
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: linear-gradient(to right, #43cea2, #185a9d);
        }
        .metric-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 15px 30px rgba(0, 0, 0, 0.2);
        }
        .metric-card h3 {
            font-size: 1.2em;
            opacity: 0.9;
            margin-bottom: 10px;
            font-weight: 500;
        }
        .metric-card h2 {
            font-size: 2.5em;
            font-weight: 900;
            margin: 0;
            padding: 0;
            line-height: 1;
        }
        .metric-card i {
            font-size: 2em;
            margin-bottom: 15px;
            display: block;
            opacity: 0.8;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 5px;
            direction: rtl;
            margin-bottom: 1rem;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 20px;
            background-color: #f8f9fa;
            border-radius: 8px 8px 0 0;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            color: #34495e;
            transition: background-color 0.3s ease-in-out, color 0.3s ease-in-out;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #e0e0e0;
            color: #2c3e50;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #3498db;
            color: white;
            font-weight: 700;
            border-bottom-color: transparent;
        }
        /* Sidebar */
        .css-1d391kg {
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
            background-color: #34495e;
            color: white;
            padding: 1.5rem;
        }
        .css-1d391kg h1, .css-1d391kg h2, .css-1d391kg h3, .css-1d391kg label {
            color: white;
            border-bottom-color: #3498db;
        }
        .css-1d391kg .stselectbox > label,
        .css-1d391kg .sttextinput > label,
        .css-1d391kg .stbutton > label {
            color: white !important;
        }
        .stButton > button {
            background-color: #2ecc71;
            color: white;
            font-weight: bold;
            border-radius: 5px;
            transition: background-color 0.3s ease-in-out;
        }
        .stButton > button:hover {
            background-color: #27ae60;
        }
        /* Animation keyframes */
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes bounceIn {
            0% {
                opacity: 0;
                transform: scale(0.3);
            }
            50% {
                opacity: 1;
                transform: scale(1.05);
            }
            70% { transform: scale(0.9); }
            100% { transform: scale(1); }
        }
    </style>
""", unsafe_allow_html=True)

# --- Header Modern ---
st.markdown("""
    <div class="header">
        <h1>🌾 سامانه پایش هوشمند نیشکر</h1>
        <p style="margin-top: 10px; font-size: 1.2em; opacity: 0.9;">مطالعات کاربردی شرکت کشت و صنعت دهخدا</p>
    </div>
""", unsafe_allow_html=True)

# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# --- GEE Authentication ---
@st.cache_resource # Cache the GEE initialization
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully using Service Account.")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()


# --- Load Farm Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...", persist=True)
def load_farm_data(csv_path=CSV_FILE_PATH):
    """Loads farm data from the specified CSV file."""
    try:
        df = pd.read_csv(csv_path)
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            return None
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool)
        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
        df = df[~df['coordinates_missing']]

        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات).")
            return None

        df['روزهای هفته'] = df['روزهای هفته'].astype(str).str.strip()
        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت بارگذاری شد.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های مزارع را در مسیر صحیح قرار دهید.")
        return None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.error(traceback.format_exc())
        return None

# Initialize GEE and Load Data
if initialize_gee():
    farm_data_df = load_farm_data()
else:
    st.error("❌ امکان ادامه کار بدون اتصال به Google Earth Engine وجود ندارد.")
    st.stop()

if farm_data_df is None:
    st.error("❌ امکان ادامه کار بدون داده‌های مزارع وجود ندارد.")
    st.stop()

# ==============================================================================
# Gemini API Configuration
# ==============================================================================
st.sidebar.subheader("✨ تنظیمات هوش مصنوعی Gemini")
GEMINI_API_KEY = st.sidebar.text_input("🔑 کلید API جمینای خود را وارد کنید:", type="password", help="برای استفاده از قابلیت‌های هوشمند، کلید API خود را از Google AI Studio دریافت و وارد کنید.")

gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest') # Using a recent model
        st.sidebar.success("✅ اتصال به Gemini برقرار شد.")
    except Exception as e:
        st.sidebar.error(f"خطا در اتصال به Gemini: {e}")
        gemini_model = None
else:
    st.sidebar.info("قابلیت‌های هوشمند Gemini با وارد کردن کلید API فعال می‌شوند.")

def ask_gemini(prompt_text, temperature=0.7, top_p=1.0, top_k=40):
    """Sends a prompt to Gemini and returns the response."""
    if not gemini_model:
        return "خطا: مدل Gemini مقداردهی اولیه نشده است. لطفاً کلید API را بررسی کنید."
    try:
        # Configuration for generation
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=2048 # Adjust as needed
        )
        response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini API: {e}\n{traceback.format_exc()}"


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

available_days = sorted(farm_data_df['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته را انتخاب کنید:",
    options=available_days,
    index=0,
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

filtered_farms_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

available_farms = sorted(filtered_farms_df['مزرعه'].unique())
farm_options = ["همه مزارع"] + available_farms
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه مورد نظر را انتخاب کنید:",
    options=farm_options,
    index=0,
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
)

index_options = {
    "NDVI": "شاخص پوشش گیاهی تفاضلی نرمال شده",
    "EVI": "شاخص پوشش گیاهی بهبود یافته",
    "NDMI": "شاخص رطوبت تفاضلی نرمال شده",
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص مورد نظر برای نمایش روی نقشه:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})",
    index=0
)

today = datetime.date.today()
persian_to_weekday = {
    "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
}
try:
    target_weekday = persian_to_weekday[selected_day]
    # Calculate the date of the most recent past (or current) occurrence of the target weekday
    days_to_subtract = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today - datetime.timedelta(days=days_to_subtract)

    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%m')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.info(f"بازه زمانی فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"بازه زمانی قبلی: {start_date_previous_str} تا {end_date_previous_str}")

except KeyError:
    st.sidebar.error(f"نام روز هفته '{selected_day}' قابل شناسایی نیست.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()

# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================
def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    # Pixels with SCL values 4, 5, 6, 7, 11 are usually good for vegetation analysis
    good_quality = scl.remap([4, 5, 6, 7, 11], [1, 1, 1, 1, 1], 0)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality)

def add_indices(image):
    # Ensure bands exist before calculating indices
    bands = image.bandNames()
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI') if 'B8' in bands and 'B4' in bands else image.addBands(ee.Image(-9999).rename('NDVI'))
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI') if all(b in bands for b in ['B8', 'B4', 'B2']) else image.addBands(ee.Image(-9999).rename('EVI'))

    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI') if 'B8' in bands and 'B11' in bands else image.addBands(ee.Image(-9999).rename('NDMI'))

    # MSI calculation requires B11 (SWIR1) and B8 (NIR)
    msi = image.expression('SWIR1 / NIR', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI') if 'B11' in bands and 'B8' in bands else image.addBands(ee.Image(-9999).rename('MSI'))

    # LAI is an estimation based on NDVI
    lai = ndvi.multiply(3.5).rename('LAI') if 'NDVI' in ndvi.bandNames().getInfo() else image.addBands(ee.Image(-9999).rename('LAI'))

    # CVI requires B8 (NIR), B3 (Green), B4 (Red)
    green_safe = image.select('B3').max(ee.Image(0.0001)) if 'B3' in bands else ee.Image(0.0001)
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
        {'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': image.select('B4')}
    ).rename('CVI') if all(b in bands for b in ['B8', 'B3', 'B4']) else image.addBands(ee.Image(-9999).rename('CVI'))

    # Return original image with calculated indices added. Use bandNames().addAll to ensure all bands are kept.
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi]).select(image.bandNames().addAll([ndvi.bandNames(), evi.bandNames(), ndmi.bandNames(), msi.bandNames(), lai.bandNames(), cvi.bandNames()]).distinct())


@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date}."
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median()
        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str) and 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
            elif isinstance(error_details, str) and 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        except Exception: pass
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))
        def extract_value(image):
            # Ensure the selected index band exists in the image
            if index_name in image.bandNames().getInfo():
                value = image.reduceRegion(
                    reducer=ee.Reducer.first(), geometry=_point_geom, scale=10
                ).get(index_name)
                return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: None}) # Return None if band is missing

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']
        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد."
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Main Panel Display
# ==============================================================================
tab1, tab2, tab3 = st.tabs([
    "<i class='fas fa-tachometer-alt'></i> داشبورد اصلی",
    "<i class='fas fa-map-marked-alt'></i> نقشه و نمودارها",
    "<i class='fas fa-brain'></i> تحلیل هوشمند با Gemini"
])

with tab1:
    # کارت‌های متریک رنگی و مدرن
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("""
            <div class="metric-card">
                <i class="fas fa-chart-area"></i>
                <h3>تعداد کل مزارع</h3>
                <h2>{}</h2>
            </div>
        """.format(len(farm_data_df)), unsafe_allow_html=True)
    with col2:
        st.markdown("""
            <div class="metric-card">
                <i class="fas fa-seedling"></i>
                <h3>تعداد واریته‌ها</h3>
                <h2>{}</h2>
            </div>
        """.format(farm_data_df['واریته'].nunique() if 'واریته' in farm_data_df.columns else "-"), unsafe_allow_html=True)
    with col3:
        st.markdown("""
            <div class="metric-card">
                <i class="fas fa-building"></i>
                <h3>تعداد ادارات</h3>
                <h2>{}</h2>
            </div>
        """.format(farm_data_df['اداره'].nunique() if 'اداره' in farm_data_df.columns else "-"), unsafe_allow_html=True)
    with col4:
        st.markdown("""
            <div class="metric-card">
                <i class="fas fa-calendar-alt"></i>
                <h3>تعداد سن‌ها</h3>
                <h2>{}</h2>
            </div>
        """.format(farm_data_df['سن'].nunique() if 'سن' in farm_data_df.columns else "-"), unsafe_allow_html=True)
    st.markdown("---")

    selected_farm_details = None
    selected_farm_geom = None
    lat, lon = INITIAL_LAT, INITIAL_LON # Default values

    if selected_farm_name == "همه مزارع":
        min_lon_df, min_lat_df = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
        max_lon_df, max_lat_df = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
        selected_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
        st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
        st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
    else:
        selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        lat = selected_farm_details['عرض جغرافیایی']
        lon = selected_farm_details['طول جغرافیایی']
        selected_farm_geom = ee.Geometry.Point([lon, lat])
        st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
        details_cols = st.columns(3)
        with details_cols[0]:
            st.metric("مساحت داشت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A")
            st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
        with details_cols[1]:
            st.metric("کانال", f"{selected_farm_details.get('کانال', 'N/A')}")
            st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
        with details_cols[2]:
            st.metric("اداره", f"{selected_farm_details.get('اداره', 'N/A')}")
            st.metric("مختصات", f"{lat:.5f}, {lon:.5f}")

    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
        results = []
        errors = []
        total_farms = len(_farms_df)
        progress_bar = st.progress(0)
        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            farm_name = farm['مزرعه']
            _lat = farm['عرض جغرافیایی']
            _lon = farm['طول جغرافیایی']
            point_geom = ee.Geometry.Point([_lon, _lat])
            def get_mean_value(start, end):
                try:
                    image, error = get_processed_image(point_geom, start, end, index_name)
                    if image:
                        mean_dict = image.reduceRegion(reducer=ee.Reducer.mean(), geometry=point_geom, scale=10).getInfo()
                        return mean_dict.get(index_name) if mean_dict else None, None
                    return None, error
                except Exception as e:
                     return None, f"خطا در محاسبه مقدار برای {farm_name} ({start}-{end}): {e}"
            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")
            change = None
            if current_val is not None and previous_val is not None:
                try: change = current_val - previous_val
                except TypeError: change = None
            results.append({
                'مزرعه': farm_name, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                f'{index_name} (هفته جاری)': current_val, f'{index_name} (هفته قبل)': previous_val, 'تغییر': change
            })
            progress_bar.progress((i + 1) / total_farms)
        progress_bar.empty()
        return pd.DataFrame(results), errors

    ranking_df, calculation_errors = calculate_weekly_indices(
        filtered_farms_df, selected_index,
        start_date_current_str, end_date_current_str,
        start_date_previous_str, end_date_previous_str
    )

    if calculation_errors:
        st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها رخ داد:")
        for error in calculation_errors[:5]: st.caption(f"- {error}") # Show limited errors
        if len(calculation_errors) > 5: st.caption(f"... و {len(calculation_errors) - 5} خطای دیگر.")

    ranking_df_sorted = pd.DataFrame() # Initialize to avoid NameError if ranking_df is empty
    if not ranking_df.empty:
        ascending_sort = selected_index in ['MSI'] # MSI and potentially NDMI lower is better
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        def determine_status(row, index_name):
            if pd.isna(row['تغییر']) or pd.isna(row[f'{index_name} (هفته جاری)']) or pd.isna(row[f'{index_name} (هفته قبل)']):
                return "بدون داده"
            if index_name in ['NDVI', 'EVI', 'LAI', 'CVI']:
                if row['تغییر'] > 0.05: return "رشد مثبت"
                elif row['تغییر'] < -0.05: return "تنش/کاهش"
                else: return "ثابت"
            elif index_name in ['MSI', 'NDMI']: # Lower MSI/NDMI is generally better
                if row['تغییر'] < -0.05: return "بهبود" # Negative change is improvement
                elif row['تغییر'] > 0.05: return "تنش/بدتر شدن"
                else: return "ثابت"
            return "نامشخص" # Should not happen with the checks above

        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)

        # Format numerical columns and add status badge
        def format_with_badge(row, col, index_name):
            value = row[col]
            status = row['وضعیت']
            formatted_value = f"{value:.3f}" if pd.notna(value) and isinstance(value, (int, float)) else "N/A"

            if col == 'وضعیت':
                 status_class = "status-info" if status == "بدون داده" else ("status-positive" if status in ["رشد مثبت", "بهبود"] else ("status-negative" if status in ["تنش/کاهش", "تنش/بدتر شدن"] else "status-neutral"))
                 return f'<span class="status-badge {status_class}">{status}</span>'
            elif col == 'تغییر':
                 status = determine_status(row, index_name) # Re-determine status for change column
                 change_class = "status-info" if status == "بدون داده" else ("status-positive" if status in ["رشد مثبت", "بهبود"] else ("status-negative" if status in ["تنش/کاهش", "تنش/بدتر شدن"] else "status-neutral"))
                 return f'<span style="color: {'green' if status in ["رشد مثبت", "بهبود"] else ('red' if status in ["تنش/کاهش", "تنش/بدتر شدن"] else 'gray')}; font-weight: bold;">{formatted_value}</span>'
            else:
                 return formatted_value


        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        # Apply formatting for display, but keep original numeric for sorting if needed elsewhere
        ranking_df_display = ranking_df_sorted.copy()
        for col_format in cols_to_format:
             if col_format in ranking_df_display.columns:
                  # Apply numeric formatting
                  ranking_df_display[col_format] = ranking_df_display[col_format].map(lambda x: f"{x:.3f}" if pd.notna(x) and isinstance(x, (int, float)) else "N/A")

        # Apply badge formatting to Status column and conditional coloring/bolding to Change column
        ranking_df_display['وضعیت'] = ranking_df_display.apply(lambda row: format_with_badge(row, 'وضعیت', selected_index), axis=1)
        ranking_df_display['تغییر'] = ranking_df_display.apply(lambda row: format_with_badge(row, 'تغییر', selected_index), axis=1)

        # Use st.markdown for HTML rendering of badges and colored text
        st.markdown(ranking_df_display.to_html(escape=False), unsafe_allow_html=True)

        st.subheader("📊 خلاصه وضعیت مزارع")
        status_counts = ranking_df_sorted['وضعیت'].value_counts()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            count_positive = status_counts.get("رشد مثبت", 0) + status_counts.get("بهبود", 0)
            st.metric("🟢 بهبود/رشد", count_positive)
        with col2:
            st.metric("⚪ ثابت", status_counts.get("ثابت", 0))
        with col3:
            count_negative = status_counts.get("تنش/کاهش", 0) + status_counts.get("تنش/بدتر شدن", 0)
            st.metric("🔴 تنش/کاهش", count_negative)
        with col4:
            st.metric("❔ بدون داده", status_counts.get("بدون داده", 0))

        st.info("""
        **توضیحات وضعیت:**
        - **🟢 رشد مثبت/بهبود**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش در شاخص‌های مثبت مانند NDVI، یا کاهش در شاخص‌های تنش مانند MSI).
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت بدتری داشته‌اند.
        - **❔ بدون داده**: اطلاعات کافی برای ارزیابی وضعیت موجود نیست.
        """)

        # Prepare CSV data from the original numerical dataframe
        csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")

with tab2:
    st.subheader("🗺️ نقشه وضعیت مزارع")
    vis_params = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'NDMI': {'min': -1, 'max': 1, 'palette': ['brown', 'white', 'blue']}, # Brown (dry) to Blue (wet)
        'LAI': {'min': 0, 'max': 6, 'palette': ['white', 'lightgreen', 'darkgreen']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['blue', 'white', 'brown']}, # Blue (low stress/wet) to Brown (high stress/dry)
        'CVI': {'min': 0, 'max': 20, 'palette': ['yellow', 'lightgreen', 'darkgreen']},
    }
    map_center_lat = lat if selected_farm_name != "همه مزارع" else INITIAL_LAT
    map_center_lon = lon if selected_farm_name != "همه مزارع" else INITIAL_LON
    initial_zoom_map = 14 if selected_farm_name != "همه مزارع" else INITIAL_ZOOM

    m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=initial_zoom_map, add_google_map=False)
    m.add_basemap("HYBRID")

    if selected_farm_geom:
        gee_image_current, error_msg_current = get_processed_image(
            selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )
        if gee_image_current:
            try:
                m.addLayer(
                    gee_image_current,
                    vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}),
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )
                # Custom Legend
                legend_html_content = ""
                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                    legend_html_content = '<p style="margin: 0; color: red; text-align: right;">بحرانی/پایین</p><p style="margin: 0; color: yellow; text-align: right;">متوسط</p><p style="margin: 0; color: green; text-align: right;">سالم/بالا</p>'
                elif selected_index == 'NDMI':
                     legend_html_content = '<p style="margin: 0; color: brown; text-align: right;">خشک</p><p style="margin: 0; color: white; text-align: right;">متوسط</p><p style="margin: 0; color: blue; text-align: right;">مرطوب</p>'
                elif selected_index == 'MSI':
                     legend_html_content = '<p style="margin: 0; color: blue; text-align: right;">رطوبت بالا / تنش کم</p><p style="margin: 0; color: white; text-align: right;">متوسط</p><p style="margin: 0; color: brown; text-align: right;">رطوبت پایین / تنش زیاد</p>'

                if legend_html_content:
                    legend_html = f'''
                    <div style="position: fixed; bottom: 50px; left: 10px; z-index: 1000; background-color: white; padding: 10px; border: 1px solid grey; border-radius: 5px; font-family: Vazirmatn, sans-serif; text-align: right;">
                        <p style="margin: 0; font-weight: bold;">راهنمای {selected_index}</p>
                        {legend_html_content}
                    </div>
                    '''
                    m.get_root().html.add_child(folium.Element(legend_html))

                if selected_farm_name == "همه مزارع":
                     for idx_farm, farm_row in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm_row['عرض جغرافیایی'], farm_row['طول جغرافیایی']],
                             popup=f"مزرعه: {farm_row['مزرعه']}<br>کانال: {farm_row['کانال']}<br>اداره: {farm_row['اداره']}",
                             tooltip=farm_row['مزرعه'], icon=folium.Icon(color='blue', icon='info-sign')
                         ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM)
                else:
                     folium.Marker(
                         location=[lat, lon], tooltip=selected_farm_name,
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=14)
                m.add_layer_control()
            except Exception as map_err:
                st.error(f"خطا در افزودن لایه به نقشه: {map_err}\n{traceback.format_exc()}")
        else:
            st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")
        st_folium(m, width=None, height=500, use_container_width=True)
        st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها برای تغییر نقشه پایه استفاده کنید.")
    else:
        st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده است.")


    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom:
        # Check if the geometry is a Point
        is_point_geom = False
        try:
            if selected_farm_geom.type().getInfo() == 'Point':
                is_point_geom = True
        except Exception: # Fallback for non-EE geometry or error in getInfo
            if isinstance(selected_farm_geom, ee.geometry.Point):
                 is_point_geom = True


        if is_point_geom:
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365*2)).strftime('%Y-%m-%d') # 2 years of data
            ts_df, ts_error = get_index_time_series(
                selected_farm_geom, selected_index,
                start_date=timeseries_start_date, end_date=timeseries_end_date
            )
            if ts_error:
                st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                fig = px.line(ts_df, y=selected_index, title=f"روند زمانی {selected_index} برای {selected_farm_name}")
                fig.update_layout(xaxis_title="تاریخ", yaxis_title=index_options[selected_index], font=dict(family="Vazirmatn"))
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 2 سال گذشته.")
            else:
                st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
        else:
            st.warning("نمودار سری زمانی فقط برای مزارع منفرد (نقطه‌ای) قابل نمایش است.")
    else:
        st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست.")


with tab3:
    st.header("💡 تحلیل هوشمند با Gemini")
    st.markdown("""
    **توجه:** پاسخ‌های ارائه شده توسط هوش مصنوعی Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان کشاورزی شوند. همیشه برای تصمیم‌گیری‌های مهم با متخصصین مشورت کنید.
    """)

    if not gemini_model:
        st.warning("⚠️ برای استفاده از قابلیت‌های هوشمند، لطفاً کلید API جمینای خود را در نوار کناری وارد کنید.")
    else:
        st.subheader("💬 پاسخ هوشمند به سوالات در مورد داده‌های مزارع")
        user_farm_q = st.text_input("سوال خود را در مورد مزرعه انتخاب شده یا وضعیت کلی مزارع بپرسید:", key="gemini_farm_q")
        if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q"):
            if not user_farm_q:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt = ""
                context_data = ""
                if selected_farm_name != "همه مزارع" and selected_farm_details is not None and not ranking_df_sorted.empty:
                    farm_data_for_prompt = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                    if not farm_data_for_prompt.empty:
                        current_val_str = farm_data_for_prompt[f'{selected_index} (هفته جاری)'].iloc[0]
                        prev_val_str = farm_data_for_prompt[f'{selected_index} (هفته قبل)'].iloc[0]
                        change_str = farm_data_for_prompt['تغییر'].iloc[0]
                        status_str = farm_data_for_prompt['وضعیت'].iloc[0]
                        context_data = f"داده‌های مزرعه '{selected_farm_name}' برای شاخص {selected_index} ({index_options.get(selected_index, selected_index)}) (هفته منتهی به {end_date_current_str}):\n" \
                                       f"- مقدار هفته جاری: {current_val_str}\n" \
                                       f"- مقدار هفته قبل: {prev_val_str}\n" \
                                       f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                                       f"- وضعیت کلی: {status_str}\n"
                        prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این داده‌ها و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."
                    else:
                        prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'. داده‌های رتبه‌بندی برای این مزرعه در دسترس نیست. لطفاً به صورت کلی و بر اساس سوال کاربر پاسخ دهید. پاسخ به زبان فارسی."

                else: # "همه مزارع" or no specific farm data
                    context_data = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{selected_index}' در حال بررسی است. تعداد {len(filtered_farms_df)} مزرعه در این روز فیلتر شده‌اند."
                    if not ranking_df_sorted.empty:
                        context_data += f"\nخلاصه وضعیت مزارع بر اساس شاخص {selected_index}:\n"
                        status_counts = ranking_df_sorted['وضعیت'].value_counts()
                        context_data += f"- تعداد مزارع با بهبود/رشد: {status_counts.get('رشد مثبت', 0) + status_counts.get('بهبود', 0)}\n"
                        context_data += f"- تعداد مزارع با وضعیت ثابت: {status_counts.get('ثابت', 0)}\n"
                        context_data += f"- تعداد مزارع با تنش/کاهش: {status_counts.get('تنش/کاهش', 0) + status_counts.get('تنش/بدتر شدن', 0)}\n"
                        context_data += f"- تعداد مزارع بدون داده: {status_counts.get('بدون داده', 0)}\n"

                    prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر سوالی در مورد وضعیت کلی مزارع پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."

                with st.spinner("در حال پردازش پاسخ با Gemini..."):
                    response = ask_gemini(prompt)
                    st.markdown(response)
        st.markdown("---")

        st.subheader("📄 تولید گزارش خودکار هفتگی برای مزرعه")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تولید گزارش انتخاب کنید.")
        elif selected_farm_details is None:
            st.info(f"داده‌های جزئی برای مزرعه {selected_farm_name} یافت نشد.")
        elif ranking_df_sorted.empty:
            st.info(f"داده‌های رتبه‌بندی برای مزرعه {selected_farm_name} جهت تولید گزارش موجود نیست.")
        else:
            if st.button(f"📝 تولید گزارش برای مزرعه '{selected_farm_name}'", key="btn_gemini_report"):
                farm_data_for_report = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                if not farm_data_for_report.empty:
                    current_val_str = farm_data_for_report[f'{selected_index} (هفته جاری)'].iloc[0]
                    prev_val_str = farm_data_for_report[f'{selected_index} (هفته قبل)'].iloc[0]
                    change_str = farm_data_for_report['تغییر'].iloc[0]
                    status_str = farm_data_for_report['وضعیت'].iloc[0]
                    area_str = f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A"
                    variety_str = selected_farm_details.get('واریته', 'N/A')

                    prompt = f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت مزرعه '{selected_farm_name}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n" \
                             f"اطلاعات مزرعه:\n" \
                             f"- مساحت: {area_str} هکتار\n" \
                             f"- واریته: {variety_str}\n" \
                             f"- شاخص مورد بررسی: {selected_index} ({index_options.get(selected_index, selected_index)})\n" \
                             f"- مقدار شاخص در هفته جاری: {current_val_str}\n" \
                             f"- مقدار شاخص در هفته قبل: {prev_val_str}\n" \
                             f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                             f"- وضعیت کلی بر اساس تغییرات: {status_str}\n\n" \
                             f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی) برای بهبود یا حفظ وضعیت مطلوب بیان کنید. گزارش باید رسمی و قابل فهم برای مدیران کشاورزی باشد."

                    with st.spinner("در حال تولید گزارش با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.6, top_p=0.9)
                        st.markdown(response)
                else:
                    st.error(f"داده‌های کافی برای تولید گزارش برای مزرعه {selected_farm_name} یافت نشد.")
        st.markdown("---")

        st.subheader(f"📉 تحلیل تغییرات شاخص {selected_index} (سری زمانی)")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تحلیل سری زمانی انتخاب کنید.")
        elif selected_farm_geom:
            is_point_geom_gemini = False
            try:
                # Check if the geometry is a Point by checking its type
                if selected_farm_geom.type().getInfo() == 'Point': is_point_geom_gemini = True
            except Exception:
                 # Fallback in case getInfo() fails or it's not an EE geometry object
                 if isinstance(selected_farm_geom, ee.geometry.Point): is_point_geom_gemini = True

            if is_point_geom_gemini:
                if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{selected_farm_name}'", key="btn_gemini_timeseries"):
                    timeseries_end_date_gemini = today.strftime('%Y-%m-%d')
                    timeseries_start_date_gemini = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d') # Last 6 months
                    ts_df_gemini, ts_error_gemini = get_index_time_series(
                        selected_farm_geom, selected_index,
                        start_date=timeseries_start_date_gemini, end_date=timeseries_end_date_gemini
                    )
                    if ts_error_gemini:
                        st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini}")
                    elif not ts_df_gemini.empty:
                        # Prepare a summary of time series for the prompt
                        ts_summary = f"داده‌های سری زمانی شاخص {selected_index} برای مزرعه '{selected_farm_name}' در 6 ماه گذشته (از {timeseries_start_date_gemini} تا {timeseries_end_date_gemini}):\n"
                        # Sample ~5-10 points or include start/end/min/max
                        sample_size = min(10, len(ts_df_gemini))
                        ts_summary += ts_df_gemini.iloc[::len(ts_df_gemini)//sample_size if len(ts_df_gemini)>sample_size else 1].to_string(header=True, index=True)
                        ts_summary += f"\nمقدار اولیه حدود {ts_df_gemini[selected_index].iloc[0]:.3f} و مقدار نهایی حدود {ts_df_gemini[selected_index].iloc[-1]:.3f} بوده است."
                        if not ts_df_gemini.empty:
                             min_val = ts_df_gemini[selected_index].min()
                             max_val = ts_df_gemini[selected_index].max()
                             ts_summary += f"\nکمترین مقدار ثبت شده حدود {min_val:.3f} و بیشترین مقدار حدود {max_val:.3f} بوده است."


                        prompt = f"شما یک تحلیلگر داده‌های کشاورزی هستید. بر اساس داده‌های سری زمانی زیر برای شاخص {selected_index} ({index_options.get(selected_index, selected_index)}) مزرعه '{selected_farm_name}' طی 6 ماه گذشته:\n{ts_summary}\n" \
                                 f"۱. روند کلی تغییرات شاخص (افزایشی، کاهشی، نوسانی، ثابت) را توصیف کنید.\n" \
                                 f"۲. نقاط عطف یا تغییرات قابل توجه در روند را شناسایی کنید (اگر وجود دارد).\n" \
                                 f"۳. دلایل احتمالی کلی (مانند تغییرات فصلی، مراحل رشد گیاه، تنش‌های محیطی عمومی) برای این روندها چه می‌تواند باشد؟\n" \
                                 f"پاسخ به زبان فارسی، ساختاریافته و تحلیلی باشد."
                        with st.spinner(f"در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                            response = ask_gemini(prompt, temperature=0.5)
                            st.markdown(response)
                    else:
                        st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای مزرعه {selected_farm_name} یافت نشد.")
            else:
                st.info("تحلیل سری زمانی فقط برای مزارع منفرد (نقطه‌ای) امکان‌پذیر است.")
        st.markdown("---")

        st.subheader("🌱 پیشنهاد اقدامات کشاورزی")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای دریافت پیشنهادات انتخاب کنید.")
        elif selected_farm_details is None or ranking_df_sorted.empty :
             st.info(f"داده‌های کافی برای ارائه پیشنهاد برای مزرعه {selected_farm_name} موجود نیست.")
        else:
            if st.button(f"💡 دریافت پیشنهادات برای مزرعه '{selected_farm_name}'", key="btn_gemini_actions"):
                farm_data_for_actions = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                if not farm_data_for_actions.empty:
                    current_val_str = farm_data_for_actions[f'{selected_index} (هفته جاری)'].iloc[0]
                    status_str = farm_data_for_actions['وضعیت'].iloc[0]
                    # Add other relevant farm details if available and helpful for actions
                    area_str = f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A"
                    variety_str = selected_farm_details.get('واریته', 'N/A')
                    age_str = selected_farm_details.get('سن', 'N/A')


                    prompt = f"شما یک مشاور کشاورزی هوشمند هستید که در زمینه نیشکر تخصص دارید. برای مزرعه '{selected_farm_name}' (مساحت: {area_str} هکتار، واریته: {variety_str}, سن: {age_str}), شاخص {selected_index} ({index_options.get(selected_index, selected_index)}) در هفته جاری مقدار {current_val_str} را نشان می‌دهد و وضعیت کلی آن '{status_str}' ارزیابی شده است.\n" \
                             f"بر اساس این اطلاعات و دانش کلی کشاورزی نیشکر:\n" \
                             f"۱. تفسیر مختصری از مقدار فعلی شاخص {selected_index} در زمینه رشد نیشکر ارائه دهید (مثلاً اگر NDVI پایین است، چه چیزی را نشان می‌دهد؟ اگر MSI بالاست، نشانه چیست؟).\n" \
                             f"۲. با توجه به مقدار شاخص، وضعیت ('{status_str}') و اطلاعات مزرعه، چه نوع بررسی‌ها یا اقدامات عمومی کشاورزی (مانند بررسی وضعیت آبیاری، نیاز به کوددهی، پایش علائم آفات و بیماری‌ها، مدیریت زهکشی، عملیات خاک‌ورزی) ممکن است لازم باشد؟ لطفاً پیشنهادات کلی و غیر تخصصی ارائه دهید که نیاز به بازدید میدانی یا مشاوره با متخصص را مطرح کند.\n" \
                             f"پاسخ به زبان فارسی، ساختاریافته و به صورت عملیاتی برای یک کشاورز باشد."

                    with st.spinner("در حال دریافت پیشنهادات کشاورزی با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.8, top_k=30)
                        st.markdown(response)
                else:
                    st.error(f"داده‌های رتبه‌بندی برای مزرعه {selected_farm_name} جهت ارائه پیشنهاد یافت نشد.")
        st.markdown("---")

        st.subheader("🗣️ پاسخ به سوالات عمومی کاربران")
        user_general_q = st.text_input("سوال عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور یا این سامانه بپرسید:", key="gemini_general_q")
        if st.button("❓ پرسیدن سوال از Gemini", key="btn_gemini_general_q"):
            if not user_general_q:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید. لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. سعی کنید پاسخ شما ساده، قابل فهم و دقیق باشد.\n\nسوال کاربر: '{user_general_q}'"
                # Add some context for specific questions if possible
                context_for_general_q = ""
                if "مزرعه من قرمز شده" in user_general_q or "مزرعه قرمز" in user_general_q or ("قرمز" in user_general_q and "نقشه" in user_general_q): # Heuristic for map color questions
                     if selected_farm_name != "همه مزارع" and not ranking_df_sorted.empty:
                        farm_data_color = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                        # Check if the selected index is one where 'red' in the palette indicates low/bad values
                        indices_where_red_is_bad = ['NDVI', 'EVI', 'LAI', 'CVI']
                        if not farm_data_color.empty and selected_index in indices_where_red_is_bad:
                            current_val_color = farm_data_color[f'{selected_index} (هفته جاری)'].iloc[0]
                            context_for_general_q = f"در این سامانه، رنگ قرمز روی نقشه برای شاخص‌هایی مانند {selected_index} ({index_options.get(selected_index, selected_index)}) معمولاً نشان‌دهنده مقدار پایین و وضعیت نامطلوب پوشش گیاهی/سلامت گیاه است. برای مزرعه '{selected_farm_name}'، مقدار فعلی شاخص {selected_index} برابر {current_val_color} است (بر اساس داده‌های هفته جاری). لطفاً توضیح دهید که چه عواملی می‌توانند باعث پایین بودن این شاخص و 'قرمز' دیده شدن مزرعه در نقشه شوند و چه بررسی‌هایی ممکن است لازم باشد. پاسخ به زبان فارسی."
                            prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید. کاربر پرسیده: '{user_general_q}'. {context_for_general_q} سعی کنید پاسخ شما ساده، قابل فهم و دقیق باشد."
                        elif not farm_data_color.empty and selected_index in ['MSI', 'NDMI']: # Indices where red/brown might indicate stress/dryness
                            current_val_color = farm_data_color[f'{selected_index} (هفته جاری)'].iloc[0]
                            context_for_general_q = f"در این سامانه، برای شاخص‌هایی مانند {selected_index} ({index_options.get(selected_index, selected_index)})، رنگ‌هایی مانند قرمز یا قهوه‌ای معمولاً نشان‌دهنده تنش رطوبتی بالا یا خشکی هستند. برای مزرعه '{selected_farm_name}'، مقدار فعلی شاخص {selected_index} برابر {current_val_color} است (بر اساس داده‌های هفته جاری). لطفاً توضیح دهید که چه عواملی می‌توانند باعث بالا بودن این شاخص (و 'قرمز' یا 'قهوه‌ای' دیده شدن مزرعه در نقشه) شوند و چه بررسی‌هایی ممکن است لازم باشد. پاسخ به زبان فارسی."
                            prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید. کاربر پرسیده: '{user_general_q}'. {context_for_general_q} سعی کنید پاسخ شما ساده، قابل فهم و دقیق باشد."

                if not context_for_general_q: # If no specific context was added
                     prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید. لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. سعی کنید پاسخ شما ساده، قابل فهم و دقیق باشد.\n\nسوال کاربر: '{user_general_q}'"


                with st.spinner("در حال جستجو برای پاسخ با Gemini..."):
                    response = ask_gemini(prompt, temperature=0.3)
                    st.markdown(response)

st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط [اسماعیل کیانی] با استفاده از Streamlit, Google Earth Engine, geemap و Gemini API")
st.sidebar.markdown("🌾 شرکت کشت و صنعت دهخدا")
import streamlit as st

# --- Custom CSS ---
# MUST BE THE FIRST STREAMLIT COMMAND (after imports)
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

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
import google.generativeai as genai

# Custom CSS for Persian text alignment and professional styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap');
        
        /* Main container */
        .main {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f0f2f6; /* Light grey background for the page */
        }
        
        /* Headers */
        h1, h2, h3 {
            font-family: 'Vazirmatn', sans-serif;
            color: #1a535c; /* Dark teal */
            text-align: right;
            font-weight: 600;
        }
        h1 {
            border-bottom: 2px solid #4ecdc4; /* Light teal accent */
            padding-bottom: 0.3em;
            margin-bottom: 0.7em;
        }
        h2 {
            color: #2a9d8f; /* Medium teal */
        }
        h3 {
            color: #e76f51; /* Coral accent for sub-subheaders */
            font-weight: 500;
        }
        
        /* Metrics - Enhanced Styling */
        .stMetric { /* Targeting Streamlit's Metric component more directly */
            font-family: 'Vazirmatn', sans-serif;
            background-color: #ffffff; /* White background */
            border: 1px solid #e0e0e0; /* Light border */
            border-left: 5px solid #4ecdc4; /* Accent border on the left */
            border-radius: 8px;
            padding: 1.2rem;
            box-shadow: 0 4px 8px rgba(0,0,0,0.05);
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        }
        .stMetric:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0,0,0,0.1);
        }
        .stMetric > label { /* Metric label */
            font-weight: 500;
            color: #1a535c;
        }
        .stMetric > div[data-testid="stMetricValue"] { /* Metric value */
            font-size: 1.8em;
            font-weight: 600;
            color: #264653; /* Dark blue/green */
        }
        .stMetric > div[data-testid="stMetricDelta"] { /* Metric delta (if used) */
            font-weight: 500;
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 5px;
            direction: rtl;
            border-bottom: 2px solid #e0e0e0;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 55px;
            padding: 12px 25px;
            background-color: #f8f9fa;
            border-radius: 8px 8px 0 0;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            color: #495057;
            border: 1px solid #e0e0e0;
            border-bottom: none;
            transition: background-color 0.2s, color 0.2s;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #4ecdc4; /* Light teal for active tab */
            color: white;
            border-color: #4ecdc4;
        }
        
        /* Tables */
        .dataframe-container table { /* More specific selector for pandas table */
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
            border-collapse: collapse;
            width: 100%;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border-radius: 8px;
            overflow: hidden; /* Ensures border-radius is applied to table */
        }
        .dataframe-container th {
            background-color: #2a9d8f; /* Medium teal for headers */
            color: white;
            padding: 12px 15px;
            font-weight: 600;
            text-align: right; /* Ensure header text is right-aligned */
        }
        .dataframe-container td {
            padding: 10px 15px;
            border-bottom: 1px solid #e0e0e0;
        }
        .dataframe-container tr:nth-child(even) td {
            background-color: #f8f9fa; /* Lighter rows */
        }
        .dataframe-container tr:hover td {
            background-color: #e9ecef; /* Hover effect */
        }

        /* Sidebar */
        .css-1d391kg { /* Streamlit's default sidebar class */
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
            background-color: #ffffff;
            padding: 1.5rem;
            border-left: 1px solid #e0e0e0;
        }
        .css-1d391kg .stSelectbox label, .css-1d391kg .stTextInput label, .css-1d391kg .stButton > button {
            font-weight: 500;
        }
        
        /* Custom status badges */
        .status-badge {
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.85em;
            font-weight: 500;
            display: inline-block;
        }
        .status-positive {
            background-color: #d1fae5; /* Lighter green */
            color: #065f46; /* Darker green text */
            border: 1px solid #6ee7b7;
        }
        .status-neutral {
            background-color: #feF3c7; /* Lighter yellow */
            color: #92400e; /* Darker yellow text */
            border: 1px solid #fcd34d;
        }
        .status-negative {
            background-color: #fee2e2; /* Lighter red */
            color: #991b1b; /* Darker red text */
            border: 1px solid #fca5a5;
        }

        /* Custom containers for better visual grouping */
        .section-container {
            background-color: #ffffff;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 3px 10px rgba(0,0,0,0.07);
            margin-bottom: 2rem;
        }

        /* Styling for buttons */
        .stButton > button {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #264653; /* Dark blue/green */
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            font-weight: 500;
            transition: background-color 0.2s, transform 0.1s;
        }
        .stButton > button:hover {
            background-color: #2a9d8f; /* Medium teal on hover */
            transform: translateY(-2px);
        }
        .stButton > button:active {
            background-color: #1a535c; /* Darker teal on active */
            transform: translateY(0px);
        }

        /* Input fields */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 8px;
            border: 1px solid #ced4da;
        }
        .stTextInput input:focus, .stSelectbox div[data-baseweb="select"] > div:focus-within {
            border-color: #4ecdc4;
            box-shadow: 0 0 0 0.2rem rgba(78, 205, 196, 0.25);
        }

        /* Markdown links */
        a {
            color: #e76f51; /* Coral for links */
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }

    </style>
""", unsafe_allow_html=True)


# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # Ganti dengan nama file Anda


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
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
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

# !!! هشدار امنیتی: قرار دادن مستقیم API Key در کد ریسک بالایی دارد !!!
# این روش فقط برای تست‌های محلی و خصوصی مناسب است.
# برای محیط‌های عمومی، از Streamlit Secrets یا متغیرهای محیطی استفاده کنید.
# GEMINI_API_KEY = st.sidebar.text_input("🔑 کلید API جمینای خود را وارد کنید:", type="password", help="برای استفاده از قابلیت‌های هوشمند، کلید API خود را از Google AI Studio دریافت و وارد کنید.")
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE" # <<<<<<< جایگزین کنید با کلید واقعی خودتان >>>>>>>>

gemini_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        st.sidebar.success("✅ اتصال به Gemini برقرار شد.")
    except Exception as e:
        st.sidebar.error(f"خطا در اتصال به Gemini: {e}")
        gemini_model = None
elif GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
    st.sidebar.warning("⚠️ لطفاً کلید API جمینای خود را مستقیماً در کد برنامه (متغیر GEMINI_API_KEY) وارد کنید تا قابلیت‌های هوشمند فعال شوند.")
    gemini_model = None
else: # No API key provided (empty string)
    st.sidebar.info("کلید API Gemini وارد نشده است. قابلیت‌های هوشمند غیرفعال هستند.")
    gemini_model = None


def ask_gemini(prompt_text, temperature=0.7, top_p=1.0, top_k=40):
    """Sends a prompt to Gemini and returns the response."""
    if not gemini_model:
        return "خطا: مدل Gemini مقداردهی اولیه نشده است. لطفاً کلید API را بررسی و در کد وارد کنید."
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=3072
        )
        response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini API: {e}\n{traceback.format_exc()}"


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("⚙️ تنظیمات نمایش")

available_days = sorted(farm_data_df['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته:",
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
    "🌾 انتخاب مزرعه:",
    options=farm_options,
    index=0,
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
)

index_options = {
    "NDVI": "پوشش گیاهی (NDVI)",
    "EVI": "پوشش گیاهی بهبودیافته (EVI)",
    "NDMI": "رطوبت گیاه (NDMI)",
    "LAI": "سطح برگ (LAI تخمینی)",
    "MSI": "تنش رطوبتی (MSI)",
    "CVI": "کلروفیل (CVI تخمینی)",
}
selected_index = st.sidebar.selectbox(
    "📈 انتخاب شاخص:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} - {index_options[x]}",
    index=0
)

today = datetime.date.today()
persian_to_weekday = {
    "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_to_subtract = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today - datetime.timedelta(days=days_to_subtract if days_to_subtract !=0 else 0)
    if today.weekday() == target_weekday and days_to_subtract == 0:
        end_date_current = today
    elif days_to_subtract == 0 and today.weekday() != target_weekday :
        end_date_current = today - datetime.timedelta(days=7)

    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')
    
    st.sidebar.markdown(f"<p style='font-size:0.9em; color:#264653;'>🗓️ <b>بازه فعلی:</b> {start_date_current_str} تا {end_date_current_str}</p>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<p style='font-size:0.9em; color:#264653;'>🗓️ <b>بازه قبلی:</b> {start_date_previous_str} تا {end_date_previous_str}</p>", unsafe_allow_html=True)


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
    good_quality_scl = scl.remap([4, 5, 6], [1, 1, 1], 0)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality_scl)


def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai_expr = ndvi.multiply(3.5).clamp(0,8)
    lai = lai_expr.rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001))
    red_safe = image.select('B4').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
        {'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': red_safe}
    ).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi])

@st.cache_data(show_spinner="⏳ در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"تصویر بدون ابری در بازه {start_date} تا {end_date} یافت نشد."
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median()
        if index_name not in median_image.bandNames().getInfo():
             return None, f"شاخص '{index_name}' پس از پردازش در تصویر میانه یافت نشد."
        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        error_details = e.args[0] if e.args else str(e)
        if isinstance(error_details, str):
            if 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
            elif 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="⏳ در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date_str, end_date_str):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date_str, end_date_str)
                     .map(maskS2clouds)
                     .map(add_indices))
        
        def extract_value(image):
            value = ee.Algorithms.If(
                image.bandNames().contains(index_name),
                image.reduceRegion(
                    reducer=ee.Reducer.first(), geometry=_point_geom, scale=10 # Use first for point, or mean for small buffer
                ).get(index_name),
                None
            )
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']
        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد."
        
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info if f['properties'] and f['properties'][index_name] is not None]
        if not ts_data:
            return pd.DataFrame(columns=['date', index_name]), "داده معتبری برای سری زمانی یافت نشد."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Determine active farm geometry (always point from CSV for this version)
# ==============================================================================
active_farm_geom = None
active_farm_name_display = selected_farm_name # Name for display purposes
active_farm_area_ha_display = None

if selected_farm_name == "همه مزارع":
    min_lon_df, min_lat_df = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
    max_lon_df, max_lat_df = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
    active_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
else:
    selected_farm_details_active = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat_active = selected_farm_details_active['عرض جغرافیایی']
    lon_active = selected_farm_details_active['طول جغرافیایی']
    active_farm_geom = ee.Geometry.Point([lon_active, lat_active])
    if 'مساحت' in selected_farm_details_active and pd.notna(selected_farm_details_active['مساحت']):
        active_farm_area_ha_display = selected_farm_details_active['مساحت']


# ==============================================================================
# Main Panel Display
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["📊 داشبورد اصلی", "🗺️ نقشه و نمودارها", "💡 تحلیل هوشمند"])

with tab1:
    st.markdown(f"<div class='section-container'><h1>🌾 {APP_TITLE}</h1><p>{APP_SUBTITLE}</p></div>", unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='section-container'>", unsafe_allow_html=True)
        if selected_farm_name == "همه مزارع":
            st.subheader(f"📋 نمایش کلی مزارع برای روز: {selected_day}")
            st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
        else:
            selected_farm_details_tab1 = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
            lat_tab1 = selected_farm_details_tab1['عرض جغرافیایی']
            lon_tab1 = selected_farm_details_tab1['طول جغرافیایی']
            
            st.subheader(f"📋 جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
            
            cols_details = st.columns([1,1,1,2]) # Adjusted column widths
            with cols_details[0]:
                area_val = selected_farm_details_tab1.get('مساحت', "N/A")
                st.metric("مساحت (هکتار)", f"{area_val:,.2f}" if pd.notna(area_val) and isinstance(area_val, (int, float)) else "N/A")
            with cols_details[1]:
                st.metric("واریته", f"{selected_farm_details_tab1.get('واریته', 'N/A')}")
            with cols_details[2]:
                st.metric("کانال", f"{selected_farm_details_tab1.get('کانال', 'N/A')}")
            # Removed some metrics to avoid clutter, can be added back if needed
            # with cols_details[1]:
            #     st.metric("سن", f"{selected_farm_details_tab1.get('سن', 'N/A')}")
            # with cols_details[2]:
            #     st.metric("اداره", f"{selected_farm_details_tab1.get('اداره', 'N/A')}")
            #     st.metric("مختصات", f"{lat_tab1:.4f}, {lon_tab1:.4f}")

        st.markdown("</div>", unsafe_allow_html=True)


    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"📈 جدول رتبه‌بندی مزارع بر اساس {index_options[selected_index]} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص (بر اساس نقاط مرکزی از CSV) در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"⏳ در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices_for_ranking_table(_farms_df, index_name_calc, start_curr, end_curr, start_prev, end_prev):
        results = []
        errors = []
        total_farms = len(_farms_df)
        status_placeholder_calc = st.empty()

        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            status_placeholder_calc.info(f"⏳ پردازش مزرعه {i+1} از {total_farms}: {farm['مزرعه']}...")
            farm_name_calc = farm['مزرعه']
            _lat_calc = farm['عرض جغرافیایی']
            _lon_calc = farm['طول جغرافیایی']
            point_geom_calc = ee.Geometry.Point([_lon_calc, _lat_calc])

            def get_mean_value(start_dt, end_dt):
                try:
                    image_calc, error_calc = get_processed_image(point_geom_calc, start_dt, end_dt, index_name_calc)
                    if image_calc:
                        buffered_point_calc = point_geom_calc.buffer(15) # Approx 1 pixel for 30m image from 10m bands
                        mean_dict = image_calc.reduceRegion(
                            reducer=ee.Reducer.mean(), geometry=buffered_point_calc, scale=10, maxPixels=1e9
                        ).getInfo()
                        return mean_dict.get(index_name_calc) if mean_dict else None, None
                    return None, error_calc
                except Exception as e_reduce:
                     return None, f"خطا در محاسبه مقدار برای {farm_name_calc} ({start_dt}-{end_dt}): {e_reduce}"

            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name_calc} (جاری): {err_curr}")
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name_calc} (قبلی): {err_prev}")

            change = None
            if current_val is not None and previous_val is not None:
                try: change = float(current_val) - float(previous_val)
                except (TypeError, ValueError): change = None

            results.append({
                'مزرعه': farm_name_calc, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                f'{index_name_calc} (هفته جاری)': current_val, f'{index_name_calc} (هفته قبل)': previous_val, 'تغییر': change
            })
        status_placeholder_calc.empty()
        return pd.DataFrame(results), errors

    ranking_df, calculation_errors = calculate_weekly_indices_for_ranking_table(
        filtered_farms_df, selected_index,
        start_date_current_str, end_date_current_str,
        start_date_previous_str, end_date_previous_str
    )

    if calculation_errors:
        with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها (کلیک کنید)", expanded=False):
            for error_item in calculation_errors: st.caption(f"- {error_item}")

    ranking_df_sorted = pd.DataFrame()
    if not ranking_df.empty:
        ascending_sort = selected_index in ['MSI']
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        def determine_status_html(row, index_name_col_status):
            change_val_status = row['تغییر']
            current_val_status = row[f'{index_name_col_status} (هفته جاری)']
            prev_val_status = row[f'{index_name_col_status} (هفته قبل)']

            if pd.isna(change_val_status) or pd.isna(current_val_status) or pd.isna(prev_val_status):
                return "<span class='status-badge status-neutral'>بدون داده</span>"
            
            try: change_val_status = float(change_val_status)
            except (ValueError, TypeError): return "<span class='status-badge status-neutral'>خطا در داده</span>"

            threshold_status = 0.05
            if index_name_col_status in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI']:
                if change_val_status > threshold_status: return "<span class='status-badge status-positive'>رشد/بهبود</span>"
                elif change_val_status < -threshold_status: return "<span class='status-badge status-negative'>تنش/کاهش</span>"
                else: return "<span class='status-badge status-neutral'>ثابت</span>"
            elif index_name_col_status in ['MSI']:
                if change_val_status < -threshold_status: return "<span class='status-badge status-positive'>بهبود (تنش کمتر)</span>"
                elif change_val_status > threshold_status: return "<span class='status-badge status-negative'>تنش بیشتر</span>"
                else: return "<span class='status-badge status-neutral'>ثابت</span>"
            return "<span class='status-badge status-neutral'>نامشخص</span>"

        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status_html(row, selected_index), axis=1)
        
        # Format numeric columns for display
        df_display = ranking_df_sorted.copy()
        cols_to_format_display = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col_fmt_dsp in cols_to_format_display:
            if col_fmt_dsp in df_display.columns:
                 df_display[col_fmt_dsp] = df_display[col_fmt_dsp].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else str(x)))
        
        # Display table with HTML for status
        st.markdown(f"<div class='dataframe-container'>{df_display.to_html(escape=False, index=True, classes='styled-table')}</div>", unsafe_allow_html=True)


        st.subheader("📊 خلاصه وضعیت مزارع")
        # Need to re-calculate status counts from the original (non-HTML) column if it exists, or parse HTML (complex)
        # For simplicity, we'll assume the HTML string contains the class name for counting
        status_counts = ranking_df_sorted['وضعیت'].value_counts() # This counts HTML strings
        
        count_positive_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'status-positive' in s)
        count_neutral_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'status-neutral' in s and 'بدون داده' not in s and 'خطا' not in s) # exclude no data
        count_negative_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'status-negative' in s)
        count_nodata_summary = sum(1 for s in ranking_df_sorted['وضعیت'] if 'بدون داده' in s or 'خطا' in s or 'نامشخص' in s)


        col1_sum, col2_sum, col3_sum, col4_sum = st.columns(4)
        with col1_sum: st.metric("🟢 بهبود/رشد", count_positive_summary)
        with col2_sum: st.metric("⚪ ثابت", count_neutral_summary)
        with col3_sum: st.metric("🔴 تنش/کاهش", count_negative_summary)
        with col4_sum: st.metric("❔ بدون داده/خطا", count_nodata_summary)


        st.info("""
        **توضیحات وضعیت (برای جدول رتبه‌بندی):**
        - **🟢 رشد/بهبود**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی در شاخص داشته‌اند.
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند.
        - **❔ بدون داده/خطا**: اطلاعات کافی برای ارزیابی وضعیت موجود نیست یا خطایی در داده‌ها وجود دارد.
        """)

        csv_data_dl = ranking_df_sorted.copy() # Use a copy for download
        # For CSV, we want raw status text, not HTML
        def extract_status_text(html_badge):
            if 'رشد/بهبود' in html_badge: return 'رشد/بهبود'
            if 'تنش کمتر' in html_badge: return 'بهبود (تنش کمتر)'
            if 'ثابت' in html_badge: return 'ثابت'
            if 'تنش/کاهش' in html_badge: return 'تنش/کاهش'
            if 'تنش بیشتر' in html_badge: return 'تنش بیشتر'
            if 'بدون داده' in html_badge: return 'بدون داده'
            if 'خطا در داده' in html_badge: return 'خطا در داده'
            return 'نامشخص'
        csv_data_dl['وضعیت'] = csv_data_dl['وضعیت'].apply(extract_status_text)

        csv_output = csv_data_dl.to_csv(index=True).encode('utf-8-sig')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_output,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")
    st.markdown("</div>", unsafe_allow_html=True) # End section-container

with tab2:
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"🗺️ نقشه وضعیت: {active_farm_name_display} (شاخص: {index_options[selected_index]})")

    # Enhanced Palettes
    vis_params_map = {
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837']}, # RdYlGn
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#ffffbf', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837']}, # RdYlGn
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#8c510a', '#bf812d', '#dfc27d', '#f6e8c3', '#f5f5f5', '#c7eae5', '#80cdc1', '#35978f', '#01665e']}, # BrBG
        'LAI': {'min': 0, 'max': 7, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Sequential Yellow-Orange-Brown
        'MSI': {'min': 0.2, 'max': 3.0, 'palette': ['#01665e', '#35978f', '#80cdc1', '#c7eae5', '#f5f5f5', '#f6e8c3', '#dfc27d', '#bf812d', '#8c510a']}, # Reversed BrBG (Low stress = green, high stress = brown)
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
    }
    
    map_center_lat_folium = INITIAL_LAT
    map_center_lon_folium = INITIAL_LON
    initial_zoom_map_val_folium = INITIAL_ZOOM

    if active_farm_geom:
        try:
            if active_farm_geom.type().getInfo() == 'Point':
                coords_folium = active_farm_geom.coordinates().getInfo()
                map_center_lon_folium, map_center_lat_folium = coords_folium[0], coords_folium[1]
                initial_zoom_map_val_folium = 15
            else: # Rectangle (for "همه مزارع")
                centroid_folium = active_farm_geom.centroid(maxError=1).coordinates().getInfo()
                map_center_lon_folium, map_center_lat_folium = centroid_folium[0], centroid_folium[1]
        except Exception: pass # Use defaults if error

    m = geemap.Map(location=[map_center_lat_folium, map_center_lon_folium], zoom=initial_zoom_map_val_folium, add_google_map=True)
    m.add_basemap("HYBRID")
    m.add_basemap("SATELLITE")

    if active_farm_geom:
        gee_image_current_map, error_msg_current_map = get_processed_image(
            active_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )
        if gee_image_current_map:
            try:
                display_image_map = gee_image_current_map
                if active_farm_name_display != "همه مزارع" and active_farm_geom.type().getInfo() == 'Point':
                    # For single point, clip to a small buffer for visualization if desired, or show larger area
                    # display_image_map = gee_image_current_map.clip(active_farm_geom.buffer(500)) # Example: 500m buffer
                    pass # Or don't clip for point, let user zoom
                
                m.addLayer(
                    display_image_map,
                    vis_params_map.get(selected_index, {}),
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )
                
                # Legend
                palette_map_lgd = vis_params_map.get(selected_index, {}).get('palette', [])
                legend_html_content = ""
                if palette_map_lgd:
                    if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                        legend_html_content = f'<p style="margin:0; background-color:{palette_map_lgd[-1]}; color:white; padding: 2px 5px; border-radius:3px;">بالا (مطلوب)</p>' \
                                              f'<p style="margin:0; background-color:{palette_map_lgd[len(palette_map_lgd)//2]}; color:black; padding: 2px 5px; border-radius:3px;">متوسط</p>' \
                                              f'<p style="margin:0; background-color:{palette_map_lgd[0]}; color:white; padding: 2px 5px; border-radius:3px;">پایین (نامطلوب)</p>'
                    elif selected_index == 'NDMI':
                         legend_html_content = f'<p style="margin:0; background-color:{palette_map_lgd[-1]}; color:white; padding: 2px 5px; border-radius:3px;">مرطوب</p>' \
                                               f'<p style="margin:0; background-color:{palette_map_lgd[0]}; color:black; padding: 2px 5px; border-radius:3px;">خشک</p>'
                    elif selected_index == 'MSI':
                         legend_html_content = f'<p style="margin:0; background-color:{palette_map_lgd[0]}; color:white; padding: 2px 5px; border-radius:3px;">تنش کم (مرطوب)</p>' \
                                               f'<p style="margin:0; background-color:{palette_map_lgd[-1]}; color:black; padding: 2px 5px; border-radius:3px;">تنش زیاد (خشک)</p>'

                if legend_html_content:
                    legend_title_map = index_options[selected_index].split('(')[0].strip()
                    legend_html = f'''
                     <div style="position: fixed; 
                                bottom: 50px; left: 10px; width: auto; 
                                background-color: rgba(255,255,255,0.85); z-index:1000; padding: 10px; border-radius:8px;
                                font-family: 'Vazirmatn', sans-serif; font-size: 0.9em; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
                       <p style="margin:0 0 8px 0; font-weight:bold; color:#1a535c;">راهنمای {legend_title_map}</p>
                       {legend_html_content}
                     </div>'''
                    m.get_root().html.add_child(folium.Element(legend_html))

                if active_farm_name_display == "همه مزارع":
                     for idx_map_farm, farm_row_map in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm_row_map['عرض جغرافیایی'], farm_row_map['طول جغرافیایی']],
                             popup=f"<b>{farm_row_map['مزرعه']}</b><br>کانال: {farm_row_map['کانال']}<br>اداره: {farm_row_map['اداره']}",
                             tooltip=farm_row_map['مزرعه'], icon=folium.Icon(color='royalblue', icon='leaf', prefix='fa')
                         ).add_to(m)
                elif active_farm_geom.type().getInfo() == 'Point': # Single farm point
                     point_coords_map = active_farm_geom.coordinates().getInfo()
                     folium.Marker(
                         location=[point_coords_map[1], point_coords_map[0]], tooltip=f"مزرعه: {active_farm_name_display}",
                         icon=folium.Icon(color='crimson', icon='map-marker', prefix='fa')
                     ).add_to(m)
                
                m.add_layer_control(position='topright')
            except Exception as map_err:
                st.error(f"خطا در افزودن لایه به نقشه: {map_err}")
        else:
            st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current_map}")
        
        st_folium(m, width=None, height=500, use_container_width=True, returned_objects=[])
    else:
        st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده است.")
    st.markdown("</div>", unsafe_allow_html=True) # End section-container


    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.subheader(f"📊 نمودار روند زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}'")
    
    if active_farm_name_display == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif active_farm_geom and active_farm_geom.type().getInfo() == 'Point':
        # Time series for a single point
        ts_end_date_chart = today.strftime('%Y-%m-%d')
        # Default to 1 year, can be made configurable
        ts_start_date_chart_user = st.date_input("تاریخ شروع برای سری زمانی:", 
                                                   value=today - datetime.timedelta(days=365),
                                                   min_value=datetime.date(2017,1,1), # Sentinel-2 data generally good from here
                                                   max_value=today - datetime.timedelta(days=30), # At least 1 month
                                                   key="ts_start_date_chart",
                                                   help="بازه زمانی حداقل ۳۰ روز و حداکثر ۲ سال توصیه می‌شود.")
        
        if st.button("📈 نمایش/به‌روزرسانی نمودار سری زمانی", key="btn_ts_chart_show"):
            max_days_chart = 365 * 2 # Max 2 years for performance
            if (today - ts_start_date_chart_user).days > max_days_chart:
                st.warning(f"بازه زمانی انتخاب شده ({ (today - ts_start_date_chart_user).days } روز) طولانی است. برای بهبود عملکرد، به ۲ سال محدود می‌شود.")
                ts_start_date_chart_user = today - datetime.timedelta(days=max_days_chart)

            with st.spinner(f"⏳ در حال دریافت و ترسیم سری زمانی {selected_index} برای '{active_farm_name_display}'..."):
                ts_df_chart, ts_error_chart = get_index_time_series(
                    active_farm_geom, selected_index,
                    start_date_str=ts_start_date_chart_user.strftime('%Y-%m-%d'),
                    end_date_str=ts_end_date_chart
                )
                if ts_error_chart:
                    st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error_chart}")
                elif not ts_df_chart.empty:
                    fig_chart = px.line(ts_df_chart, y=selected_index, markers=True,
                                  title=f"روند زمانی {index_options[selected_index]} برای '{active_farm_name_display}'",
                                  labels={'date': 'تاریخ', selected_index: index_options[selected_index]})
                    fig_chart.update_layout(
                        font=dict(family="Vazirmatn"),
                        xaxis_title="تاریخ", 
                        yaxis_title=index_options[selected_index],
                        plot_bgcolor='rgba(240, 242, 246, 0.8)', # Light background for plot area
                        paper_bgcolor='rgba(255,255,255,0.9)',
                        hovermode="x unified"
                    )
                    fig_chart.update_traces(line=dict(color='#e76f51', width=2.5), marker=dict(color='#264653', size=6))
                    st.plotly_chart(fig_chart, use_container_width=True)
                else:
                    st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
    else: # "همه مزارع" or non-point geometry (though this version only uses points)
        st.warning("نمودار سری زمانی فقط برای مزارع منفرد (نقطه‌ای) قابل نمایش است.")
    st.markdown("</div>", unsafe_allow_html=True) # End section-container

with tab3:
    st.markdown("<div class='section-container'>", unsafe_allow_html=True)
    st.header("💡 تحلیل هوشمند با Gemini")
    st.markdown("""
    **توجه:** پاسخ‌های ارائه شده توسط هوش مصنوعی Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان کشاورزی شوند. همیشه برای تصمیم‌گیری‌های مهم با متخصصین مشورت کنید.
    """)

    if not gemini_model:
        st.warning("⚠️ برای استفاده از قابلیت‌های هوشمند، لطفاً کلید API جمینای خود را مستقیماً در کد برنامه (متغیر GEMINI_API_KEY) وارد و برنامه را مجدداً اجرا کنید.")
    else:
        # Prepare farm details string for Gemini prompts (always point-based for this version)
        farm_details_for_gemini_tab3 = ""
        analysis_basis_str_gemini_tab3 = "تحلیل بر اساس نقطه مرکزی مزرعه از داده‌های CSV انجام می‌شود."
        
        if active_farm_name_display != "همه مزارع":
            farm_details_for_gemini_tab3 = f"مزرعه مورد نظر: '{active_farm_name_display}'.\n"
            if active_farm_area_ha_display:
                farm_details_for_gemini_tab3 += f"مساحت ثبت شده در CSV: {active_farm_area_ha_display:,.2f} هکتار.\n"
            
            csv_farm_details_tab3 = filtered_farms_df[filtered_farms_df['مزرعه'] == active_farm_name_display].iloc[0]
            variety_str_gemini_tab3 = csv_farm_details_tab3.get('واریته', 'N/A')
            farm_details_for_gemini_tab3 += f"واریته (از CSV): {variety_str_gemini_tab3}.\n"

        # --- Gemini Q&A ---
        st.subheader("💬 پرسش و پاسخ هوشمند")
        user_farm_q_gemini = st.text_area(f"سوال خود را در مورد وضعیت '{active_farm_name_display}' یا وضعیت کلی مزارع روز '{selected_day}' بپرسید:", key="gemini_farm_q_text", height=100)
        if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q_send"):
            if not user_farm_q_gemini:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt_gemini_q = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. {analysis_basis_str_gemini_tab3}\n"
                context_data_gemini_q = ""

                if active_farm_name_display != "همه مزارع":
                    context_data_gemini_q += farm_details_for_gemini_tab3
                    farm_data_for_prompt_q = pd.DataFrame()
                    if not ranking_df_sorted.empty:
                        farm_data_for_prompt_q = ranking_df_sorted[ranking_df_sorted['مزرعه'] == active_farm_name_display]
                    
                    if not farm_data_for_prompt_q.empty:
                        # Use raw status text for Gemini context
                        status_text_gemini_q = extract_status_text(farm_data_for_prompt_q['وضعیت'].iloc[0])
                        current_val_str_gemini_q = farm_data_for_prompt_q[f'{selected_index} (هفته جاری)'].iloc[0] # This is already formatted string
                        prev_val_str_gemini_q = farm_data_for_prompt_q[f'{selected_index} (هفته قبل)'].iloc[0]
                        change_str_gemini_q = farm_data_for_prompt_q['تغییر'].iloc[0]
                        
                        context_data_gemini_q += f"داده‌های مزرعه '{active_farm_name_display}' برای شاخص {index_options[selected_index]} (هفته منتهی به {end_date_current_str}):\n" \
                                       f"- مقدار هفته جاری: {current_val_str_gemini_q}\n" \
                                       f"- مقدار هفته قبل: {prev_val_str_gemini_q}\n" \
                                       f"- تغییر نسبت به هفته قبل: {change_str_gemini_q}\n" \
                                       f"- وضعیت کلی: {status_text_gemini_q}\n"
                    else:
                        context_data_gemini_q += f"داده‌های عددی هفتگی برای '{active_farm_name_display}' از جدول رتبه‌بندی در دسترس نیست.\n"
                    prompt_gemini_q += f"کاربر در مورد '{active_farm_name_display}' سوالی پرسیده است: '{user_farm_q_gemini}'.\n{context_data_gemini_q}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."
                else: # "همه مزارع"
                    context_data_gemini_q = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{index_options[selected_index]}' در حال بررسی است. تعداد {len(filtered_farms_df)} مزرعه در این روز فیلتر شده‌اند."
                    if not ranking_df_sorted.empty:
                        context_data_gemini_q += f"\nخلاصه وضعیت مزارع (بر اساس نقاط مرکزی از CSV) برای شاخص {selected_index}:\n"
                        context_data_gemini_q += f"- تعداد مزارع با بهبود/رشد: {count_positive_summary}\n"
                        context_data_gemini_q += f"- تعداد مزارع با وضعیت ثابت: {count_neutral_summary}\n"
                        context_data_gemini_q += f"- تعداد مزارع با تنش/کاهش: {count_negative_summary}\n"
                        context_data_gemini_q += f"- تعداد مزارع بدون داده/خطا: {count_nodata_summary}\n"
                    prompt_gemini_q += f"کاربر سوالی در مورد وضعیت کلی مزارع پرسیده است: '{user_farm_q_gemini}'.\n{context_data_gemini_q}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."

                with st.spinner("⏳ در حال پردازش پاسخ با Gemini..."):
                    response_gemini_q = ask_gemini(prompt_gemini_q)
                    st.markdown(f"<div style='background-color: #e6f7ff; border-left: 5px solid #007bff; padding: 15px; border-radius: 5px; margin-top:15px;'>{response_gemini_q}</div>", unsafe_allow_html=True)
        st.markdown("---")

        # --- Gemini Auto Report ---
        st.subheader("📄 تولید گزارش خودکار هفتگی")
        if active_farm_name_display == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تولید گزارش انتخاب کنید.")
        else:
            farm_data_for_report_gemini = pd.DataFrame()
            if not ranking_df_sorted.empty:
                farm_data_for_report_gemini = ranking_df_sorted[ranking_df_sorted['مزرعه'] == active_farm_name_display]

            if farm_data_for_report_gemini.empty:
                st.info(f"داده‌های رتبه‌بندی (مقادیر هفتگی) برای مزرعه '{active_farm_name_display}' جهت تولید گزارش موجود نیست.")
            elif st.button(f"📝 تولید گزارش برای '{active_farm_name_display}'", key="btn_gemini_report_gen"):
                report_context_gemini = farm_details_for_gemini_tab3
                current_val_str_rep = farm_data_for_report_gemini[f'{selected_index} (هفته جاری)'].iloc[0]
                prev_val_str_rep = farm_data_for_report_gemini[f'{selected_index} (هفته قبل)'].iloc[0]
                change_str_rep = farm_data_for_report_gemini['تغییر'].iloc[0]
                status_text_rep = extract_status_text(farm_data_for_report_gemini['وضعیت'].iloc[0])

                report_context_gemini += f"داده‌های شاخص {index_options[selected_index]} برای '{active_farm_name_display}' در هفته منتهی به {end_date_current_str}:\n" \
                                  f"- مقدار شاخص در هفته جاری: {current_val_str_rep}\n" \
                                  f"- مقدار شاخص در هفته قبل: {prev_val_str_rep}\n" \
                                  f"- تغییر نسبت به هفته قبل: {change_str_rep}\n" \
                                  f"- وضعیت کلی بر اساس تغییرات: {status_text_rep}\n"

                prompt_rep = f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت '{active_farm_name_display}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n" \
                         f"اطلاعات موجود:\n{report_context_gemini}\n" \
                         f"{analysis_basis_str_gemini_tab3}\n\n" \
                         f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت (با توجه به شاخص {selected_index}) ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی و قطعی) برای بهبود یا حفظ وضعیت مطلوب بیان کنید. گزارش باید رسمی، دارای عنوان، تاریخ، و بخش‌های مشخص (مثلاً: مقدمه، وضعیت فعلی شاخص، تحلیل تغییرات، پیشنهادات) و قابل فهم برای مدیران کشاورزی باشد."

                with st.spinner(f"⏳ در حال تولید گزارش برای '{active_farm_name_display}' با Gemini..."):
                    response_rep = ask_gemini(prompt_rep, temperature=0.6, top_p=0.9)
                    st.markdown(f"### گزارش هفتگی '{active_farm_name_display}' (شاخص {index_options[selected_index]})")
                    st.markdown(f"**تاریخ گزارش:** {datetime.date.today().strftime('%Y-%m-%d')}")
                    st.markdown(f"**بازه زمانی مورد بررسی:** {start_date_current_str} الی {end_date_current_str}")
                    st.markdown(f"<div style='background-color: #f0fff0; border-left: 5px solid #28a745; padding: 15px; border-radius: 5px; margin-top:15px;'>{response_rep}</div>", unsafe_allow_html=True)
        st.markdown("---")

        # --- Gemini Timeseries Analysis ---
        st.subheader(f"📉 تحلیل هوشمند روند زمانی شاخص {index_options[selected_index]}")
        if active_farm_name_display == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تحلیل سری زمانی انتخاب کنید.")
        elif active_farm_geom and active_farm_geom.type().getInfo() == 'Point':
            if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{active_farm_name_display}' با Gemini", key="btn_gemini_timeseries_an"):
                ts_end_date_gemini_ts = today.strftime('%Y-%m-%d')
                ts_start_date_gemini_ts = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d') # Last 6 months
                
                with st.spinner(f"⏳ در حال دریافت داده‌های سری زمانی برای تحلیل Gemini..."):
                    ts_df_gemini_ts, ts_error_gemini_ts = get_index_time_series(
                        active_farm_geom, selected_index,
                        start_date_str=ts_start_date_gemini_ts, end_date_str=ts_end_date_gemini_ts
                    )

                if ts_error_gemini_ts:
                    st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini_ts}")
                elif not ts_df_gemini_ts.empty:
                    ts_summary_gemini = f"داده‌های سری زمانی شاخص {index_options[selected_index]} برای '{active_farm_name_display}' در 6 ماه گذشته (از {ts_start_date_gemini_ts} تا {ts_end_date_gemini_ts}):\n"
                    sample_freq_gemini = max(1, len(ts_df_gemini_ts) // 10)
                    ts_summary_gemini += ts_df_gemini_ts.iloc[::sample_freq_gemini][selected_index].to_string(header=True, index=True) # Only the index column
                    ts_summary_gemini += f"\nمقدار اولیه حدود {ts_df_gemini_ts[selected_index].iloc[0]:.3f} و مقدار نهایی حدود {ts_df_gemini_ts[selected_index].iloc[-1]:.3f} بوده است."
                    ts_summary_gemini += f"\n میانگین: {ts_df_gemini_ts[selected_index].mean():.3f}, کمترین: {ts_df_gemini_ts[selected_index].min():.3f}, بیشترین: {ts_df_gemini_ts[selected_index].max():.3f}."
                    
                    prompt_ts_an = f"شما یک تحلیلگر داده‌های کشاورزی خبره هستید. {analysis_basis_str_gemini_tab3}\n بر اساس داده‌های سری زمانی زیر برای شاخص {index_options[selected_index]} مزرعه '{active_farm_name_display}' طی 6 ماه گذشته:\n{ts_summary_gemini}\n" \
                                 f"۱. روند کلی تغییرات شاخص را توصیف کنید.\n" \
                                 f"۲. آیا دوره‌های خاصی از رشد، کاهش یا ثبات مشاهده می‌شود؟\n" \
                                 f"۳. با توجه به ماهیت شاخص {selected_index} و روند، چه تفسیرهای اولیه‌ای می‌توان داشت؟\n" \
                                 f"۴. چه مشاهدات میدانی می‌تواند به درک بهتر این روند کمک کند?\n" \
                                 f"پاسخ به زبان فارسی، ساختاریافته، تحلیلی و کاربردی باشد."
                    with st.spinner(f"⏳ در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                        response_ts_an = ask_gemini(prompt_ts_an, temperature=0.5)
                        st.markdown(f"<div style='background-color: #fff3cd; border-left: 5px solid #ffc107; padding: 15px; border-radius: 5px; margin-top:15px;'>{response_ts_an}</div>", unsafe_allow_html=True)
                else:
                    st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای '{active_farm_name_display}' در 6 ماه گذشته یافت نشد.")
        st.markdown("---")
        
        # --- General Q&A ---
        st.subheader("🗣️ پرسش و پاسخ عمومی")
        user_general_q_gemini = st.text_area("سوال عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور، نیشکر یا این سامانه بپرسید:", key="gemini_general_q_text", height=100)
        if st.button("❓ پرسیدن سوال عمومی از Gemini", key="btn_gemini_general_q_send"):
            if not user_general_q_gemini:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt_gen_q = f"شما یک دانشنامه هوشمند در زمینه کشاورزی (با تمرکز بر نیشکر) و سنجش از دور هستید. لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. سعی کنید پاسخ شما ساده، قابل فهم، دقیق و در حد امکان جامع باشد.\n\nسوال کاربر: '{user_general_q_gemini}'"
                
                with st.spinner("⏳ در حال جستجو برای پاسخ با Gemini..."):
                    response_gen_q = ask_gemini(prompt_gen_q, temperature=0.4)
                    st.markdown(f"<div style='background-color: #e6f7ff; border-left: 5px solid #007bff; padding: 15px; border-radius: 5px; margin-top:15px;'>{response_gen_q}</div>", unsafe_allow_html=True)


    st.markdown("</div>", unsafe_allow_html=True) # End section-container for Gemini tab

st.sidebar.markdown("---")
st.sidebar.markdown("<div style='text-align:center; font-size:0.9em; color:#264653;'>ساخته شده با 💻 توسط <strong>اسماعیل کیانی</strong></div>", unsafe_allow_html=True)
st.sidebar.markdown("<div style='text-align:center; font-size:0.95em; color:#1a535c;'>🌾 شرکت کشت و صنعت دهخدا</div>", unsafe_allow_html=True)
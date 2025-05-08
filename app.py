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
import google.generativeai as genai

# --- Page Configuration ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# ==============================================================================
# HARDCODED GEMINI API KEY
# WARNING: It's best practice to use environment variables or Streamlit secrets for API keys.
# Replace "YOUR_GEMINI_API_KEY_HERE" with your actual Gemini API key.
# If you are deploying this on a public platform, ensure this key is secured.
# ==============================================================================
GEMINI_API_KEY = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <--- REPLACE WITH YOUR ACTUAL KEY

if GEMINI_API_KEY == "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ":
    st.warning("""
       Esmaeil.Kiani
    """, icon="⚠️")


# --- Custom CSS for Modern Look and Animations ---
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap');
        
        body {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f4f6f9; /* Light grey background for a softer look */
        }
        
        /* Main container subtle fade-in */
        .main > div { 
            animation: fadeInAnimation ease-in 0.8s;
            animation-iteration-count: 1;
            animation-fill-mode: forwards;
        }
        @keyframes fadeInAnimation {
            0% {
                opacity: 0;
                transform: translateY(15px);
            }
            100% {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* Headers */
        h1, h2, h3 {
            font-family: 'Vazirmatn', sans-serif;
            color: #1a2534; /* Darker, more modern header color */
            text-align: right;
        }
        h1 {
            font-weight: 700;
        }
        h2 {
            font-weight: 600;
            margin-top: 1.5em;
            margin-bottom: 0.8em;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 0.3em;
        }
        h3 {
            font-weight: 500;
            color: #2c3e50;
        }
        
        /* Metric Cards Styling */
        div[data-testid="stMetric"] {
            background-color: #ffffff !important;
            border: 1px solid #e8e8e8;
            border-left: 6px solid #007bff !important; /* Primary blue for left border */
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            box-shadow: 0 5px 15px rgba(0,0,0,0.07);
            transition: transform 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
            font-family: 'Vazirmatn', sans-serif;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        }
        div[data-testid="stMetric"] label { /* Metric label */
            font-weight: 500;
            color: #555;
            font-size: 0.95em;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] { /* Metric value */
            font-size: 2.2em;
            font-weight: 700;
            color: #0056b3; /* Darker blue for value */
        }
        div[data-testid="stMetric"] div[data-testid="stMetricDelta"] { /* Metric delta */
            font-weight: 500;
            font-size: 0.9em;
        }
        /* Custom colors for delta based on positive/negative - Streamlit handles this, but can be overridden */
        /* .stMetricDelta > div[class*="Positive"] { color: #28a745 !important; } */
        /* .stMetricDelta > div[class*="Negative"] { color: #dc3545 !important; } */

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 5px; /* Space between tabs */
            direction: rtl;
            border-bottom: 2px solid #dee2e6; /* Underline for the tab bar */
        }
        .stTabs [data-baseweb="tab"] {
            height: 55px;
            padding: 12px 25px;
            background-color: transparent; /* Cleaner look */
            border-radius: 8px 8px 0 0;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            font-size: 1.05em;
            color: #495057;
            border: none; /* Remove default borders */
            border-bottom: 4px solid transparent; /* For active state */
            transition: color 0.2s ease, border-bottom-color 0.2s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            background-color: #e9ecef;
            color: #0056b3;
        }
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #ffffff; /* Slightly different bg for active tab */
            color: #007bff; /* Primary color for active tab text */
            border-bottom: 4px solid #007bff; /* Prominent underline for active tab */
            box-shadow: 0 -3px 5px rgba(0,0,0,0.03);
        }
        
        /* Tables */
        .dataframe {
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
            border-radius: 8px;
            overflow: hidden; /* Ensures border-radius is applied to table */
        }
        .dataframe thead th {
            background-color: #e9ecef;
            color: #343a40;
            font-weight: 600;
        }
        
        /* Sidebar */
        .css-1d391kg { /* Streamlit's default sidebar class, adjust if different */
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
            background-color: #ffffff; /* White sidebar background */
            padding: 1.5rem 1rem;
            box-shadow: 2px 0 10px rgba(0,0,0,0.05);
        }
        .css-1d391kg .stSelectbox label, .css-1d391kg .stTextInput label {
             font-weight: 600;
             color: #333;
        }
        
        /* Custom status badges */
        .status-badge {
            padding: 5px 10px;
            border-radius: 18px;
            font-size: 0.85em;
            font-weight: 500;
            display: inline-block;
        }
        .status-positive { /* رشد مثبت, بهبود */
            background-color: #d1f7e0; /* Lighter green */
            color: #126b39;
            border: 1px solid #a3e9c1;
        }
        .status-neutral { /* ثابت */
            background-color: #feefc9; /* Lighter yellow */
            color: #7a5b0c;
            border: 1px solid #fddc93;
        }
        .status-negative { /* تنش/کاهش, تنش/بدتر شدن */
            background-color: #fddde2; /* Lighter red */
            color: #8b1e2c;
            border: 1px solid #fbbbc3;
        }
        .status-no-data { /* بدون داده */
            background-color: #e9ecef;
            color: #495057;
            border: 1px solid #ced4da;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 25px; /* More rounded */
            padding: 10px 22px;
            font-weight: 600;
            border: none;
            background-color: #007bff;
            color: white;
            transition: background-color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
            box-shadow: 0 3px 6px rgba(0,123,255,0.2);
        }
        .stButton > button:hover {
            background-color: #0056b3;
            transform: translateY(-2px);
            box-shadow: 0 5px 10px rgba(0,86,179,0.3);
        }
        .stButton > button:active {
            transform: translateY(0px);
            box-shadow: 0 2px 4px rgba(0,123,255,0.2);
        }

        /* Input fields */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] > div, .stDateInput input {
            border-radius: 8px;
            border: 1px solid #ced4da;
            padding: 10px 12px;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
            font-family: 'Vazirmatn', sans-serif;
        }
        .stTextInput input:focus, 
        .stSelectbox div[data-baseweb="select"] > div:focus-within,
        .stDateInput input:focus {
            border-color: #80bdff;
            box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25);
        }
        
        /* Styling for containers or panels */
        .custom-panel {
            background-color: #ffffff;
            padding: 25px;
            border-radius: 15px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.08);
            margin-bottom: 25px;
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
@st.cache_data(show_spinner="⏳ در حال بارگذاری داده‌های مزارع...")
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
gemini_model = None
if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY_HERE":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        st.sidebar.success("✅ اتصال به Gemini برقرار شد.", icon="💡")
    except Exception as e:
        st.sidebar.error(f"خطا در اتصال به Gemini: {e}", icon="⚠️")
        gemini_model = None
else:
    st.sidebar.info("کلید API جمینای معتبر برای فعالسازی قابلیت‌های هوشمند لازم است.", icon="🔑")


def ask_gemini(prompt_text, temperature=0.7, top_p=1.0, top_k=40):
    """Sends a prompt to Gemini and returns the response."""
    if not gemini_model:
        return "خطا: مدل Gemini مقداردهی اولیه نشده است. لطفاً از صحت کلید API اطمینان حاصل کنید."
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=3072 # Increased token limit
        )
        response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini API: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Sidebar
# ==============================================================================
st.sidebar.markdown("<h1 style='text-align: center; color: #0056b3; font-weight: 700;'>🌾 سامانه پایش نیشکر</h1>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size: 0.9em; color: #555;'>کشت و صنعت دهخدا</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.header("⚙️ تنظیمات نمایش")

available_days = sorted(farm_data_df['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 انتخاب روز هفته:",
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
    "🏞️ انتخاب مزرعه:",
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
    "🌿 انتخاب شاخص:",
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
    days_ago = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today - datetime.timedelta(days=days_ago if days_ago !=0 else 0)
    if today.weekday() == target_weekday:
        end_date_current = today
    else:
        days_to_subtract = (today.weekday() - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_to_subtract if days_to_subtract != 0 else 7)


    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗓️ بازه‌های زمانی")
    st.sidebar.info(f"**هفته جاری:** {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"**هفته قبل:** {start_date_previous_str} تا {end_date_previous_str}")

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
    good_quality = scl.remap([2, 4, 5, 6, 7, 11], [1, 1, 1, 1, 1, 1], 0) # Added more clear sky classes
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality)

def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1.0001)', # Added small epsilon to avoid div by zero
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / (NIR + 0.0001)', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai = ndvi.multiply(3.5).rename('LAI') # Simple LAI estimation
    green_safe = image.select('B3').max(ee.Image(0.0001)) # Ensure green is not zero
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
        {'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': image.select('B4')}
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
            return None, f"تصویری بدون ابر برای بازه {start_date} تا {end_date} یافت نشد."
        indexed_col = s2_sr_col.map(add_indices)
        # Use qualityMosaic for less cloudy pixels if median is too blurry or use median for general trend
        # median_image = indexed_col.median()
        median_image = indexed_col.qualityMosaic(selected_index if selected_index in ['NDVI', 'EVI'] else 'NDVI') # Prioritize NDVI for mosaicing
        if not median_image.bandNames().contains(selected_index).getInfo(): # If index not in mosaic (e.g. all cloudy)
             median_image = indexed_col.median() # Fallback to median
        
        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'computation timed out' in error_details.lower():
                     error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی. سعی کنید بازه را کوتاهتر کنید.)"
                elif 'user memory limit exceeded' in error_details.lower():
                     error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده. سعی کنید منطقه کوچکتری را انتخاب کنید.)"
                elif 'image.select: Pattern' in error_details and 'matches no bands' in error_details:
                     error_message += f"\n(شاخص '{index_name}' در تصویر محاسبه شده یافت نشد. ممکن است به دلیل پوشش ابر کامل باشد.)"
        except Exception: pass
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="⏳ در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices)
                     .sort('system:time_start')) # Sort for chronological order
        
        def extract_value(image):
            # Ensure the index band exists before trying to reduce
            has_band = ee.Algorithms.IsEqual(ee.List(image.bandNames()).contains(index_name), True)
            
            # Use a conditional to avoid errors if band is missing
            value = ee.Algorithms.If(
                has_band,
                image.reduceRegion(reducer=ee.Reducer.first(), geometry=_point_geom, scale=10).get(index_name),
                None # Return None if the band is not present
            )
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد (ممکن است به دلیل پوشش ابر یا عدم وجود تصاویر باشد)."
        
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info if f['properties'][index_name] is not None]
        if not ts_data:
             return pd.DataFrame(columns=['date', index_name]), "داده معتبری (پس از فیلتر مقادیر null) برای سری زمانی یافت نشد."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Main Panel Display with Modern Tabs
# ==============================================================================
# New tab order and names
tab_dashboard, tab_gemini, tab_map = st.tabs([
    "📊 داشبورد اصلی", 
    "💡 تحلیل هوشمند Gemini", 
    "🗺️ نقشه و نمودارها"
])


with tab_dashboard: # Was tab1
    st.header(f"{APP_TITLE}")
    st.caption(f"{APP_SUBTITLE} | روز انتخابی: {selected_day} | شاخص: {selected_index}")

    selected_farm_details = None
    selected_farm_geom = None
    lat, lon = INITIAL_LAT, INITIAL_LON

    if selected_farm_name == "همه مزارع":
        min_lon_df, min_lat_df = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
        max_lon_df, max_lat_df = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
        try:
            selected_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
        except Exception as e:
            st.error(f"خطا در ایجاد هندسه برای 'همه مزارع': {e}. مقادیر: {min_lon_df}, {min_lat_df}, {max_lon_df}, {max_lat_df}")
            selected_farm_geom = None # Prevent further errors
        
        with st.container():
            st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
            st.subheader(f"ภาพรวม مزارع برای روز: {selected_day}")
            st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        lat = selected_farm_details['عرض جغرافیایی']
        lon = selected_farm_details['طول جغرافیایی']
        selected_farm_geom = ee.Geometry.Point([lon, lat])

        with st.container():
            st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
            st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
            details_cols = st.columns([1,1,1,2]) # Adjusted column widths
            with details_cols[0]:
                st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A")
            with details_cols[1]:
                 st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
            with details_cols[2]:
                st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
            with details_cols[3]:
                 st.markdown(f"""
                    **کانال:** {selected_farm_details.get('کانال', 'N/A')} | 
                    **اداره:** {selected_farm_details.get('اداره', 'N/A')} <br>
                    **مختصات:** {lat:.5f}, {lon:.5f}
                 """, unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    with st.container():
        st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
        st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
        st.caption("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

        @st.cache_data(show_spinner=f"⏳ در حال محاسبه {selected_index} برای مزارع...", persist=True)
        def calculate_weekly_indices(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
            results = []
            errors = []
            # total_farms = len(_farms_df)
            # progress_text = f"پردازش مزارع برای شاخص {index_name}"
            # progress_bar = st.progress(0, text=progress_text)
            
            # Using st.status for a cleaner progress display
            with st.status(f"درحال محاسبه شاخص {index_name} برای {len(_farms_df)} مزرعه...", expanded=False) as status_calc:
                for i, (idx, farm) in enumerate(_farms_df.iterrows()):
                    farm_name = farm['مزرعه']
                    _lat = farm['عرض جغرافیایی']
                    _lon = farm['طول جغرافیایی']
                    point_geom = ee.Geometry.Point([_lon, _lat]).buffer(30) # Buffer point slightly for mean calculation

                    def get_mean_value(start, end, period_name):
                        try:
                            st.write(f"   - مزرعه {farm_name}: محاسبه برای {period_name} ({start} تا {end})")
                            image, error = get_processed_image(point_geom, start, end, index_name)
                            if image:
                                mean_dict = image.reduceRegion(reducer=ee.Reducer.mean(), geometry=point_geom, scale=10, maxPixels=1e9).getInfo()
                                val = mean_dict.get(index_name)
                                if val is None:
                                    return None, f"شاخص {index_name} در داده‌های {farm_name} ({start}-{end}) یافت نشد."
                                return val, None
                            return None, error if error else "تصویری یافت نشد."
                        except Exception as e:
                            return None, f"خطا در محاسبه مقدار برای {farm_name} ({start}-{end}): {str(e)[:200]}" # Truncate long errors
                    
                    current_val, err_curr = get_mean_value(start_curr, end_curr, "هفته جاری")
                    if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")
                    
                    previous_val, err_prev = get_mean_value(start_prev, end_prev, "هفته قبل")
                    if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")
                    
                    change = None
                    if current_val is not None and previous_val is not None:
                        try: change = current_val - previous_val
                        except TypeError: change = None # Should not happen if both are numbers

                    results.append({
                        'مزرعه': farm_name, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                        f'{index_name} (هفته جاری)': current_val, f'{index_name} (هفته قبل)': previous_val, 'تغییر': change
                    })
                    # progress_bar.progress((i + 1) / total_farms, text=f"{progress_text} ({i+1}/{total_farms})")
                status_calc.update(label=f"محاسبه {index_name} برای {len(_farms_df)} مزرعه کامل شد!", state="complete")
            # progress_bar.empty()
            return pd.DataFrame(results), errors

        ranking_df, calculation_errors = calculate_weekly_indices(
            filtered_farms_df, selected_index,
            start_date_current_str, end_date_current_str,
            start_date_previous_str, end_date_previous_str
        )

        if calculation_errors:
            with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها", expanded=False):
                for error_idx, error_msg in enumerate(calculation_errors):
                    st.caption(f"- {error_msg}")
                    if error_idx > 10 and len(calculation_errors) > 15 : # Limit displayed errors
                        st.caption(f"... و {len(calculation_errors) - 10} خطای دیگر.")
                        break


        ranking_df_sorted = pd.DataFrame()
        if not ranking_df.empty:
            ascending_sort = selected_index in ['MSI'] # Lower MSI is better (less stress)
            ranking_df_sorted = ranking_df.sort_values(
                by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
            ).reset_index(drop=True)
            ranking_df_sorted.index = ranking_df_sorted.index + 1
            ranking_df_sorted.index.name = 'رتبه'

            def determine_status(row, index_name):
                # Determine status based on change and index type
                if pd.isna(row['تغییر']) or pd.isna(row[f'{index_name} (هفته جاری)']) or pd.isna(row[f'{index_name} (هفته قبل)']):
                    return "بدون داده"
                
                change_val = row['تغییر']
                # Positive indices (higher is better): NDVI, EVI, LAI, CVI
                if index_name in ['NDVI', 'EVI', 'LAI', 'CVI']:
                    if change_val > 0.05: return "رشد مثبت"
                    elif change_val < -0.05: return "کاهش/تنش"
                    else: return "ثابت"
                # Negative indices (lower is better, e.g., stress): MSI
                elif index_name == 'MSI':
                    if change_val < -0.05: return "بهبود (تنش کمتر)" # Negative change means MSI decreased = good
                    elif change_val > 0.05: return "بدتر شدن (تنش بیشتر)" # Positive change means MSI increased = bad
                    else: return "ثابت"
                # Indices where interpretation of change can be dual: NDMI (Moisture)
                elif index_name == 'NDMI':
                     # Assuming higher NDMI is generally better (more moisture)
                    if change_val > 0.05: return "افزایش رطوبت"
                    elif change_val < -0.05: return "کاهش رطوبت"
                    else: return "ثابت"
                return "نامشخص"

            ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)
            
            # Prepare DataFrame for display
            display_df = ranking_df_sorted.copy()
            cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
            for col_format in cols_to_format:
                if col_format in display_df.columns:
                    display_df[col_format] = display_df[col_format].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
            
            # Apply HTML styling for status badges
            def style_status(status):
                if status == "رشد مثبت" or status == "بهبود (تنش کمتر)" or status == "افزایش رطوبت":
                    return f'<span class="status-badge status-positive">{status}</span>'
                elif status == "کاهش/تنش" or status == "بدتر شدن (تنش بیشتر)" or status == "کاهش رطوبت":
                    return f'<span class="status-badge status-negative">{status}</span>'
                elif status == "ثابت":
                    return f'<span class="status-badge status-neutral">{status}</span>'
                elif status == "بدون داده":
                    return f'<span class="status-badge status-no-data">{status}</span>'
                return status

            display_df['وضعیت'] = display_df['وضعیت'].apply(style_status)
            st.markdown(display_df.to_html(escape=False, index=True, classes='dataframe'), unsafe_allow_html=True)


            st.subheader("📊 خلاصه وضعیت مزارع")
            status_counts = ranking_df_sorted['وضعیت'].value_counts()
            col1, col2, col3, col4 = st.columns(4)
            
            positive_statuses = ["رشد مثبت", "بهبود (تنش کمتر)", "افزایش رطوبت"]
            negative_statuses = ["کاهش/تنش", "بدتر شدن (تنش بیشتر)", "کاهش رطوبت"]

            count_positive = sum(status_counts.get(s, 0) for s in positive_statuses)
            count_negative = sum(status_counts.get(s, 0) for s in negative_statuses)
            
            with col1:
                st.metric("🟢 بهبود/رشد", count_positive, help="مزارع با رشد مثبت، بهبود تنش یا افزایش رطوبت")
            with col2:
                st.metric("⚪ ثابت", status_counts.get("ثابت", 0), help="مزارع بدون تغییر محسوس")
            with col3:
                st.metric("🔴 تنش/کاهش", count_negative, help="مزارع با کاهش، بدتر شدن تنش یا کاهش رطوبت")
            with col4:
                st.metric("❔ بدون داده", status_counts.get("بدون داده", 0), help="مزارع بدون اطلاعات کافی برای ارزیابی")

            st.info("""
            **راهنمای وضعیت:**
            - **🟢 بهبود/رشد**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش در شاخص‌های مثبت مانند NDVI، کاهش در شاخص‌های تنش مانند MSI، یا افزایش رطوبت NDMI).
            - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
            - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند.
            - **❔ بدون داده**: اطلاعات کافی برای ارزیابی وضعیت موجود نیست.
            """)

            csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8-sig') # utf-8-sig for Excel compatibility
            st.download_button(
                label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_data,
                file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv',
            )
        else:
            st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")
        st.markdown('</div>', unsafe_allow_html=True)


with tab_map: # Was tab2
    with st.container():
        st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
        st.subheader(f"🗺️ نقشه وضعیت مزارع ({selected_index})")
        vis_params = {
            'NDVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # More detailed NDVI palette
            'EVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
            'NDMI': {'min': -1, 'max': 1, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']}, # Diverging Red-Blue
            'LAI': {'min': 0, 'max': 7, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Sequential Yellow-Orange-Brown
            'MSI': {'min': 0, 'max': 3.5, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b']}, # Reversed NDMI: Blue (low stress) to Red (high stress)
            'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFD9', '#EDF8B1', '#C7E9B4', '#7FCDBB', '#41B6C4', '#1D91C0', '#225EA8', '#253494', '#081D58']}, # Sequential Yellow-Green-Blue for Chlorophyll
        }
        map_center_lat = lat if selected_farm_name != "همه مزارع" else INITIAL_LAT
        map_center_lon = lon if selected_farm_name != "همه مزارع" else INITIAL_LON
        initial_zoom_map = 15 if selected_farm_name != "همه مزارع" else INITIAL_ZOOM

        m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=initial_zoom_map, add_google_map=False)
        m.add_basemap("HYBRID")
        m.add_basemap("SATELLITE") # Add another option

        if selected_farm_geom:
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom.buffer(100) if selected_farm_name != "همه مزارع" else selected_farm_geom, # Buffer single farm for better context
                start_date_current_str, end_date_current_str, selected_index
            )
            if gee_image_current:
                try:
                    m.addLayer(
                        gee_image_current,
                        vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}),
                        f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                    )
                    
                    # Add legend
                    legend_dict = {
                        'NDVI': 'پوشش گیاهی (کم <span style="color:red;">■</span> تا زیاد <span style="color:green;">■</span>)',
                        'EVI': 'پوشش گیاهی بهبودیافته (کم <span style="color:red;">■</span> تا زیاد <span style="color:green;">■</span>)',
                        'NDMI': 'رطوبت (خشک <span style="color:brown;">■</span> تا مرطوب <span style="color:blue;">■</span>)',
                        'LAI': 'شاخص سطح برگ (کم <span style="color:yellow;">■</span> تا زیاد <span style="color:darkgreen;">■</span>)',
                        'MSI': 'تنش رطوبتی (رطوبت بالا/تنش کم <span style="color:blue;">■</span> تا رطوبت پایین/تنش زیاد <span style="color:brown;">■</span>)',
                        'CVI': 'کلروفیل (کم <span style="color:yellow;">■</span> تا زیاد <span style="color:darkgreen;">■</span>)',
                    }
                    m.add_legend(title=f"راهنمای {selected_index}", legend_dict=legend_dict, position="bottomright")


                    if selected_farm_name == "همه مزارع":
                        for idx_farm, farm_row in filtered_farms_df.iterrows():
                            folium.Marker(
                                location=[farm_row['عرض جغرافیایی'], farm_row['طول جغرافیایی']],
                                popup=f"<b>مزرعه:</b> {farm_row['مزرعه']}<br><b>کانال:</b> {farm_row.get('کانال', 'N/A')}<br><b>اداره:</b> {farm_row.get('اداره', 'N/A')}",
                                tooltip=farm_row['مزرعه'], icon=folium.Icon(color='blue', icon='info-sign', prefix='fa')
                            ).add_to(m)
                        if selected_farm_geom: m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM)
                    else:
                        folium.Marker(
                            location=[lat, lon], tooltip=selected_farm_name,
                            popup=f"<b>مزرعه:</b> {selected_farm_name}",
                            icon=folium.Icon(color='red', icon='star', prefix='fa')
                        ).add_to(m)
                        if selected_farm_geom: m.center_object(selected_farm_geom.buffer(200), zoom=15) # Zoom closer for single farm
                    m.add_layer_control()
                except Exception as map_err:
                    st.error(f"خطا در افزودن لایه به نقشه: {map_err}\n{traceback.format_exc()}")
            else:
                st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")
            
            # Use st_folium for interactivity
            st_folium(m, width='100%', height=550, use_container_width=True) # use_container_width was false
            st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها (بالا سمت راست نقشه) برای تغییر نقشه پایه استفاده کنید.")
        else:
            st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده است.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    with st.container():
        st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
        st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
        elif selected_farm_geom:
            is_point_geom = False
            try:
                if selected_farm_geom.type().getInfo() == 'Point': is_point_geom = True
            except Exception:
                if isinstance(selected_farm_geom, ee.geometry.Point): is_point_geom = True

            if is_point_geom:
                timeseries_end_date = today.strftime('%Y-%m-%d')
                timeseries_start_date = (today - datetime.timedelta(days=365*2)).strftime('%Y-%m-%d') # 2 years
                
                ts_df, ts_error = get_index_time_series(
                    selected_farm_geom, selected_index,
                    start_date=timeseries_start_date, end_date=timeseries_end_date
                )
                if ts_error:
                    st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
                elif not ts_df.empty:
                    fig = px.line(ts_df, y=selected_index, markers=True,
                                  title=f"روند زمانی {selected_index} برای {selected_farm_name} (2 سال اخیر)")
                    fig.update_layout(
                        xaxis_title="تاریخ", yaxis_title=selected_index, 
                        font=dict(family="Vazirmatn, sans-serif"),
                        plot_bgcolor='rgba(245,245,245,1)', paper_bgcolor='rgba(255,255,255,1)',
                        xaxis=dict(gridcolor='rgba(220,220,220,0.5)'),
                        yaxis=dict(gridcolor='rgba(220,220,220,0.5)'),
                    )
                    fig.update_traces(line=dict(width=2.5, color='#007bff'), marker=dict(size=6, color='#0056b3'))
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
            else:
                st.warning("نمودار سری زمانی فقط برای مزارع منفرد (نقطه‌ای) قابل نمایش است.")
        else:
            st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست.")
        st.markdown('</div>', unsafe_allow_html=True)


with tab_gemini: # Was tab3
    st.header("💡 تحلیل هوشمند با Gemini")
    st.markdown("""
    <div class="custom-panel" style="background-color: #e6f7ff; border-left: 5px solid #007bff;">
    <p style="font-weight: 500;">توجه:</p>
    <p>پاسخ‌های ارائه شده توسط هوش مصنوعی Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان کشاورزی شوند. همیشه برای تصمیم‌گیری‌های مهم با متخصصین مشورت کنید. برای استفاده از این بخش، نیاز به کلید API معتبر از Google AI Studio دارید.</p>
    </div>
    """, unsafe_allow_html=True)

    if not gemini_model:
        st.warning("⚠️ برای استفاده از قابلیت‌های هوشمند، لطفاً کلید API جمینای معتبر را در کد برنامه وارد کنید.")
    else:
        tab_gemini_qna, tab_gemini_report, tab_gemini_trend, tab_gemini_actions, tab_gemini_general = st.tabs([
            "💬 پرسش و پاسخ", "📄 گزارش هفتگی", "📉 تحلیل روند", "🌱 پیشنهادات", "🗣️ سوالات عمومی"
        ])

        with tab_gemini_qna:
            with st.container():
                st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
                st.subheader("💬 پاسخ هوشمند به سوالات در مورد داده‌های مزارع")
                user_farm_q = st.text_input("سوال خود را در مورد مزرعه انتخاب شده یا وضعیت کلی مزارع بپرسید:", key="gemini_farm_q", placeholder="مثلا: وضعیت مزرعه X چگونه است؟ یا کدام مزارع نیاز به توجه بیشتری دارند؟")
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
                                status_str = farm_data_for_prompt['وضعیت'].iloc[0] # This is HTML, need original
                                # Get original status for prompt
                                original_status_str = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]['وضعیت'].iloc[0]

                                context_data = f"داده‌های مزرعه '{selected_farm_name}' برای شاخص {selected_index} (هفته منتهی به {end_date_current_str}):\n" \
                                            f"- مقدار هفته جاری: {current_val_str}\n" \
                                            f"- مقدار هفته قبل: {prev_val_str}\n" \
                                            f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                                            f"- وضعیت کلی (بر اساس تحلیل داده): {original_status_str}\n" # Use original status
                                prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این داده‌ها و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."
                            else:
                                prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'. داده‌های رتبه‌بندی برای این مزرعه در دسترس نیست. لطفاً به صورت کلی و بر اساس سوال کاربر پاسخ دهید. پاسخ به زبان فارسی."

                        else: # "همه مزارع" or no specific farm data
                            context_data = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{selected_index}' در حال بررسی است. تعداد {len(filtered_farms_df)} مزرعه در این روز فیلتر شده‌اند."
                            if not ranking_df_sorted.empty:
                                context_data += f"\nخلاصه وضعیت مزارع بر اساس شاخص {selected_index}:\n"
                                status_counts = ranking_df_sorted['وضعیت'].value_counts() # Use original status_counts
                                
                                positive_statuses = ["رشد مثبت", "بهبود (تنش کمتر)", "افزایش رطوبت"]
                                negative_statuses = ["کاهش/تنش", "بدتر شدن (تنش بیشتر)", "کاهش رطوبت"]
                                count_positive = sum(status_counts.get(s, 0) for s in positive_statuses)
                                count_negative = sum(status_counts.get(s, 0) for s in negative_statuses)

                                context_data += f"- تعداد مزارع با بهبود/رشد: {count_positive}\n"
                                context_data += f"- تعداد مزارع با وضعیت ثابت: {status_counts.get('ثابت', 0)}\n"
                                context_data += f"- تعداد مزارع با تنش/کاهش: {count_negative}\n"
                                context_data += f"- تعداد مزارع بدون داده: {status_counts.get('بدون داده', 0)}\n"

                            prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر سوالی در مورد وضعیت کلی مزارع پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."

                        with st.spinner("⏳ در حال پردازش پاسخ با Gemini..."):
                            response = ask_gemini(prompt)
                            st.markdown(response, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        with tab_gemini_report:
            with st.container():
                st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
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
                            original_status_str = farm_data_for_report['وضعیت'].iloc[0] # Get original status

                            area_str = f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A"
                            variety_str = selected_farm_details.get('واریته', 'N/A')

                            prompt = f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت مزرعه '{selected_farm_name}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n" \
                                    f"اطلاعات مزرعه:\n" \
                                    f"- مساحت: {area_str} هکتار\n" \
                                    f"- واریته: {variety_str}\n" \
                                    f"- شاخص مورد بررسی: {selected_index} ({index_options[selected_index]})\n" \
                                    f"- مقدار شاخص در هفته جاری: {current_val_str}\n" \
                                    f"- مقدار شاخص در هفته قبل: {prev_val_str}\n" \
                                    f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                                    f"- وضعیت کلی بر اساس تغییرات: {original_status_str}\n\n" \
                                    f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی و قطعی) برای بررسی‌های بیشتر یا بهبود و حفظ وضعیت مطلوب بیان کنید. گزارش باید رسمی و قابل فهم برای مدیران کشاورزی باشد. از لیست‌ها و عنوان‌بندی برای خوانایی بهتر استفاده کنید."

                            with st.spinner("⏳ در حال تولید گزارش با Gemini..."):
                                response = ask_gemini(prompt, temperature=0.6, top_p=0.9)
                                st.markdown(f"### گزارش هفتگی مزرعه {selected_farm_name} (شاخص {selected_index})")
                                st.markdown(f"**تاریخ گزارش:** {datetime.date.today().strftime('%Y-%m-%d')}")
                                st.markdown(f"**بازه زمانی مورد بررسی:** {start_date_current_str} الی {end_date_current_str}")
                                st.markdown(response, unsafe_allow_html=True)
                        else:
                            st.error(f"داده‌های کافی برای تولید گزارش برای مزرعه {selected_farm_name} یافت نشد.")
                st.markdown('</div>', unsafe_allow_html=True)

        with tab_gemini_trend:
            with st.container():
                st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
                st.subheader(f"📉 تحلیل تغییرات شاخص {selected_index} (سری زمانی)")
                if selected_farm_name == "همه مزارع":
                    st.info("لطفاً یک مزرعه خاص را برای تحلیل سری زمانی انتخاب کنید.")
                elif selected_farm_geom:
                    is_point_geom_gemini = False
                    try:
                        if selected_farm_geom.type().getInfo() == 'Point': is_point_geom_gemini = True
                    except Exception:
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
                                ts_summary = f"داده‌های نمونه از سری زمانی شاخص {selected_index} برای مزرعه '{selected_farm_name}' در 6 ماه گذشته (از {timeseries_start_date_gemini} تا {timeseries_end_date_gemini}):\n"
                                # Sample fewer points if too many, ensure first and last are included
                                if len(ts_df_gemini) > 10:
                                    sample_indices = list(range(0, len(ts_df_gemini), len(ts_df_gemini)//7))
                                    if len(ts_df_gemini)-1 not in sample_indices: sample_indices.append(len(ts_df_gemini)-1)
                                    ts_sample_df = ts_df_gemini.iloc[sorted(list(set(sample_indices)))]
                                else:
                                    ts_sample_df = ts_df_gemini
                                ts_summary += ts_sample_df.to_string(header=True, index=True)
                                ts_summary += f"\nمقدار اولیه حدود {ts_df_gemini[selected_index].iloc[0]:.3f} و مقدار نهایی حدود {ts_df_gemini[selected_index].iloc[-1]:.3f} بوده است. تعداد کل نقاط داده: {len(ts_df_gemini)}."
                                
                                prompt = f"شما یک تحلیلگر داده‌های کشاورزی سنجش از دور هستید. بر اساس داده‌های سری زمانی زیر برای شاخص {selected_index} ({index_options[selected_index]}) مزرعه '{selected_farm_name}' طی 6 ماه گذشته:\n{ts_summary}\n" \
                                        f"۱. روند کلی تغییرات شاخص (افزایشی، کاهشی، نوسانی، ثابت) را به تفصیل توصیف کنید.\n" \
                                        f"۲. آیا نقاط عطف، دوره‌های رشد سریع، کاهش ناگهانی یا تغییرات قابل توجه دیگری در روند مشاهده می‌شود؟ آنها را شناسایی و زمان تقریبی وقوعشان را ذکر کنید.\n" \
                                        f"۳. دلایل احتمالی کلی (مانند تغییرات فصلی طبیعی، مراحل مختلف رشد گیاه نیشکر، عملیات زراعی احتمالی، یا تنش‌های محیطی عمومی) برای این روندها و تغییرات چه می‌تواند باشد؟\n" \
                                        f"پاسخ به زبان فارسی، کاملاً ساختاریافته، تحلیلی و دقیق باشد. از لیست‌ها و توضیحات واضح استفاده کنید."
                                with st.spinner(f"⏳ در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                                    response = ask_gemini(prompt, temperature=0.5)
                                    st.markdown(response, unsafe_allow_html=True)
                            else:
                                st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای مزرعه {selected_farm_name} یافت نشد.")
                    else:
                        st.info("تحلیل سری زمانی فقط برای مزارع منفرد (نقطه‌ای) امکان‌پذیر است.")
                st.markdown('</div>', unsafe_allow_html=True)

        with tab_gemini_actions:
            with st.container():
                st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
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
                            original_status_str = farm_data_for_actions['وضعیت'].iloc[0] # Get original status

                            prompt = f"شما یک مشاور کشاورزی هوشمند برای مزارع نیشکر هستید. برای مزرعه '{selected_farm_name}'، شاخص {selected_index} ({index_options[selected_index]}) در هفته جاری مقدار {current_val_str} را نشان می‌دهد و وضعیت کلی آن '{original_status_str}' ارزیابی شده است.\n" \
                                    f"بر اساس این اطلاعات:\n" \
                                    f"۱. تفسیر مختصری از مقدار فعلی شاخص {selected_index} و معنای آن برای سلامت و وضعیت گیاه نیشکر ارائه دهید (مثلاً اگر NDVI پایین است، یعنی چه؟ اگر MSI بالاست یعنی چه؟ ارتباط آن با نیاز آبی یا غذایی چیست؟).\n" \
                                    f"۲. با توجه به مقدار شاخص و وضعیت '{original_status_str}'، چه نوع بررسی‌های میدانی دقیق‌تر یا اقدامات عمومی کشاورزی (مانند تنظیم آبیاری، بررسی نیاز به عناصر غذایی خاص، پایش دقیق آفات و بیماری‌ها، مدیریت بقایای گیاهی، یا بررسی فشردگی خاک) ممکن است لازم باشد؟ لطفاً پیشنهادات کلی، عملی و اولویت‌بندی شده (در صورت امکان) ارائه دهید. تاکید کنید که اینها پیشنهادهای اولیه هستند و نیاز به بررسی کارشناسی دارند.\n" \
                                    f"پاسخ به زبان فارسی، به صورت عملیاتی، و با لحنی مشاوره‌ای و مفید باشد."

                            with st.spinner("⏳ در حال دریافت پیشنهادات کشاورزی با Gemini..."):
                                response = ask_gemini(prompt, temperature=0.8, top_k=30)
                                st.markdown(response, unsafe_allow_html=True)
                        else:
                            st.error(f"داده‌های رتبه‌بندی برای مزرعه {selected_farm_name} جهت ارائه پیشنهاد یافت نشد.")
                st.markdown('</div>', unsafe_allow_html=True)

        with tab_gemini_general:
            with st.container():
                st.markdown('<div class="custom-panel">', unsafe_allow_html=True)
                st.subheader("🗣️ پاسخ به سوالات عمومی کاربران")
                user_general_q = st.text_input("سوال عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور یا این سامانه بپرسید:", key="gemini_general_q", placeholder="مثلا: شاخص NDVI چیست و چه کاربردی دارد؟ یا چگونه می‌توانم از این سامانه بهتر استفاده کنم؟")
                if st.button("❓ پرسیدن سوال از Gemini", key="btn_gemini_general_q"):
                    if not user_general_q:
                        st.info("لطفاً سوال خود را وارد کنید.")
                    else:
                        prompt_base = f"شما یک دانشنامه هوشمند در زمینه کشاورزی نیشکر، سنجش از دور و کار با سامانه‌های پایش کشاورزی هستید. لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. سعی کنید پاسخ شما ساده، قابل فهم، دقیق و کاربردی باشد.\n\nسوال کاربر: '{user_general_q}'"
                        
                        # Contextual enhancement for common questions
                        context_specific = ""
                        if "مزرعه من قرمز شده" in user_general_q.lower() or "مزرعه قرمز" in user_general_q.lower() or "رنگ قرمز" in user_general_q.lower():
                            if selected_farm_name != "همه مزارع" and not ranking_df_sorted.empty:
                                farm_data_color = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                                if not farm_data_color.empty and selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']: # Indices where red is bad
                                    current_val_color = farm_data_color[f'{selected_index} (هفته جاری)'].iloc[0]
                                    context_specific = f"\n\nاطلاعات تکمیلی برای پاسخ دقیق‌تر: در این سامانه، رنگ قرمز روی نقشه برای شاخص‌هایی مانند NDVI، EVI، LAI و CVI معمولاً نشان‌دهنده مقدار پایین و وضعیت نامطلوب پوشش گیاهی است. برای مزرعه '{selected_farm_name}' (که ممکن است کاربر به آن اشاره داشته باشد)، مقدار فعلی شاخص {selected_index} برابر {current_val_color} است. لطفاً در پاسخ خود به این نکته توجه کنید و توضیح دهید که چه عواملی می‌توانند باعث پایین بودن این شاخص و 'قرمز' دیده شدن مزرعه در نقشه شوند و چه بررسی‌های کلی ممکن است لازم باشد."
                        
                        prompt = prompt_base + context_specific
                        
                        with st.spinner("⏳ در حال جستجو برای پاسخ با Gemini..."):
                            response = ask_gemini(prompt, temperature=0.4) # Slightly lower temp for factual Qs
                            st.markdown(response, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("<p style='text-align: center; font-size: 0.85em; color: #777;'>ساخته شده با 💻 توسط <strong>اسماعیل کیانی</strong></p>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size: 0.8em; color: #888;'>با استفاده از Streamlit, GEE, Geemap و Gemini API</p>", unsafe_allow_html=True)
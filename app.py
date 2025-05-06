# --- START OF FILE app_enhanced.py ---

import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import plotly.graph_objects as go # For 3D plots if needed later, using scatter now
import os
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium
import base64
import time
import math # For checking NaN

# --- Gemini API Integration ---
import google.generativeai as genai

# WARNING: Storing API keys directly in code is insecure!
# Use environment variables or st.secrets in production.
# Replace "YOUR_GEMINI_API_KEY" with your actual key for this specific implementation.
GEMINI_API_KEY = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- PASTE YOUR KEY HERE

# --- Constants ---
APP_TITLE = "سامانه پایش هوشمند نیشکر (نسخه بهبود یافته)"
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12
# Indices and their properties
INDEX_INFO = {
    "NDVI": {"name": "شاخص تراکم پوشش گیاهی", "palette": 'RdYlGn', "min": 0.0, "max": 0.9, "higher_is_better": True, "desc": "رنگ سبز بیانگر محصول متراکم و سالم و رنگ قرمز نشان‌دهنده‌ی محصول کم‌پشت و پراکنده است."},
    "NDWI": {"name": "شاخص محتوای آبی گیاهان", "palette": ['#d7191c', '#fdae61', '#ffffbf', '#abd9e9', '#2c7bb6'], "min": -0.2, "max": 0.6, "higher_is_better": True, "desc": "رنگ آبی بیشتر نشان‌دهنده محتوای آبی بیشتر و رنگ قرمز نشان‌دهنده کم‌آبی است."},
    "NDRE": {"name": "شاخص میزان ازت گیاه (لبه قرمز)", "palette": 'Purples', "min": 0.0, "max": 0.6, "higher_is_better": True, "desc": "رنگ بنفش نشان‌دهنده میزان زیاد ازت/کلروفیل و رنگ روشن‌تر نشان‌دهنده کاهش آن در گیاه است."},
    "LAI": {"name": "شاخص سطح برگ (تخمینی)", "palette": 'YlGn', "min": 0, "max": 7, "higher_is_better": True, "desc": "رنگ سبز پررنگ‌تر نشان‌دهنده سطح برگ بیشتر در ناحیه است."},
    "CHL": {"name": "شاخص کلروفیل (تخمینی)", "palette": ['#b35806','#f1a340','#fee0b6','#d8daeb','#998ec3','#542788'], "min": 0, "max": 10, "higher_is_better": True, "desc": "رنگ بنفش/تیره نشان‌دهنده کلروفیل بیشتر است و رنگ قهوه‌ای/روشن نشان‌دهنده کاهش کلروفیل یا تنش است."}
}
# Default threshold for significant change
CHANGE_THRESHOLD = 0.03

# --- Page Config and CSS ---
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🌾",
    layout="wide"
)

# Custom CSS (remains mostly the same, ensure Vazirmatn is loaded)
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        body, .main, button, input, textarea, select, .stTextInput, .stSelectbox, .stDateInput, .stButton>button, .stTabs [data-baseweb="tab"], .stMetric, .stDataFrame, .stPlotlyChart {
            font-family: 'Vazirmatn', sans-serif !important;
            direction: rtl; /* Ensure consistent RTL */
        }
        /* Ensure elements within columns/containers also inherit RTL */
        .stBlock, .stHorizontalBlock { direction: rtl; }
        /* Align headers right */
        h1, h2, h3, h4, h5, h6 { text-align: right; color: #2c3e50; }
        /* Align Plotly titles (might need specific Plotly config too) */
        .plotly .gtitle { text-align: right !important; }
        /* Specific alignment for Streamlit components if needed */
        .stSelectbox > label, .stDateInput > label, .stTextInput > label, .stTextArea > label {
             text-align: right !important; width: 100%; display: block;
         }
        /* Right-align text in dataframes */
        .dataframe { text-align: right; }
        .stTabs [data-baseweb="tab-list"] { gap: 5px; }
        .stTabs [data-baseweb="tab"] { height: 50px; padding: 10px 20px; background-color: #f0f2f6; border-radius: 8px 8px 0 0; font-weight: 600; }
        .stTabs [aria-selected="true"] { background-color: #e6f2ff; } /* Highlight selected tab */
        .stMetric { background-color: #f8f9fa; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;}
        .stMetric > label { font-weight: bold; color: #495057; } /* Style metric label */
        .stMetric > div { font-size: 1.5em; color: #007bff; } /* Style metric value */
         /* Ensure sidebar is RTL */
        .css-1d391kg { direction: rtl; }
        .css-1d391kg .stSelectbox > label { text-align: right !important; } /* Fix sidebar select label */
    </style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'gee_initialized' not in st.session_state:
    st.session_state.gee_initialized = False
if 'farm_data' not in st.session_state:
    st.session_state.farm_data = None
if 'ranking_data' not in st.session_state:
    st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}
if 'gemini_analysis' not in st.session_state:
    st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None}
if 'gemini_available' not in st.session_state:
    st.session_state.gemini_available = False
if 'gemini_model' not in st.session_state:
    st.session_state.gemini_model = None

# --- GEE and Gemini Initialization ---
@st.cache_resource
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            return False
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except Exception as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        return False

@st.cache_resource
def configure_gemini():
    """Configures the Gemini API."""
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
             print("Gemini API Key not provided.")
             return None, False # Model, Available status
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash') # Use a fast model
        print("Gemini API Configured Successfully.")
        return model, True
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        st.warning(f"⚠️ اخطار: خطا در پیکربندی Gemini API ({e}). تحلیل هوش مصنوعی غیرفعال خواهد بود.")
        return None, False

# Initialize only once
if not st.session_state.gee_initialized:
    st.session_state.gee_initialized = initialize_gee()
    if not st.session_state.gee_initialized:
        st.error("❌ اتصال به Google Earth Engine ناموفق بود. برنامه متوقف شد.")
        st.stop()

if st.session_state.gemini_model is None:
     st.session_state.gemini_model, st.session_state.gemini_available = configure_gemini()

# --- Load Farm Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    """Loads and validates farm data from CSV."""
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
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد.")
            return None
        df['روزهای هفته'] = df['روزهای هفته'].astype(str).str.strip()
        # Add a unique ID for potential joining later
        df['farm_id'] = df['مزرعه'] + '_' + df['طول جغرافیایی'].astype(str) + '_' + df['عرض جغرافیایی'].astype(str)
        print(f"Farm data loaded successfully: {len(df)} farms.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد.")
        return None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.error(traceback.format_exc())
        return None

# Load data only once or if it's not in session state
if st.session_state.farm_data is None:
    st.session_state.farm_data = load_farm_data()

if st.session_state.farm_data is None:
    st.error("❌ داده‌های مزارع بارگذاری نشد. برنامه متوقف شد.")
    st.stop()

# ========================= Sidebar Inputs =========================
st.sidebar.header("⚙️ تنظیمات نمایش")

# --- Day Selection ---
available_days = sorted(st.session_state.farm_data['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته:",
    options=available_days,
    index=available_days.index("شنبه") if "شنبه" in available_days else 0, # Default to Saturday
    key='selected_day_key' # Add key to help manage state
)

# --- Filter Data Based on Selected Day ---
filtered_farms_df = st.session_state.farm_data[st.session_state.farm_data['روزهای هفته'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

# --- Farm Selection ---
available_farms = ["همه مزارع"] + sorted(filtered_farms_df['مزرعه'].unique())
selected_farm_name = st.sidebar.selectbox(
    "🌾 انتخاب مزرعه:",
    options=available_farms,
    index=0, # Default to "All Farms"
    key='selected_farm_key'
)

# --- Index Selection ---
selected_index = st.sidebar.selectbox(
    "📈 انتخاب شاخص:",
    options=list(INDEX_INFO.keys()),
    format_func=lambda x: f"{x} ({INDEX_INFO[x]['name']})",
    index=0, # Default to NDVI
    key='selected_index_key'
)
# Get index properties
index_props = INDEX_INFO[selected_index]
vis_params = {'min': index_props['min'], 'max': index_props['max'], 'palette': index_props['palette']}

# --- Date Range Calculation ---
# Perform calculation only if needed (e.g., day changes)
# Using inputs directly, no need to cache this simple calculation
today = datetime.date.today()
persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_ago = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today - datetime.timedelta(days=days_ago) if days_ago != 0 else today
    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.info(f"🗓️ بازه فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"🗓️ بازه قبلی: {start_date_previous_str} تا {end_date_previous_str}")

except KeyError:
    st.sidebar.error(f"نام روز هفته '{selected_day}' نامعتبر است.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()

# ========================= GEE Functions (Cached) =========================

@st.cache_data(persist=True) # Cache cloud masking logic
def maskS2clouds(image_dict):
    """Masks clouds using QA band and SCL. Input/Output: Dictionary representation."""
    image = ee.Image.fromDictionary(image_dict) # Reconstruct image object
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    good_quality = scl.remap([4, 5, 6], [1, 1, 1], 0) # Keep Veg, Bare Soil, Water
    opticalBands = image.select('B.*').multiply(0.0001)
    masked_image = image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality)
    return masked_image.toDictionary() # Return dictionary

@st.cache_data(persist=True) # Cache index calculation logic
def add_indices_dict(image_dict):
    """Calculates indices. Input/Output: Dictionary representation."""
    image = ee.Image.fromDictionary(image_dict)
    try:
        # Calculate all indices - ensure bands exist implicitly (GEE handles errors later)
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = image.normalizedDifference(['B8', 'B11']).rename('NDWI')
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        lai = ndvi.multiply(3.5).rename('LAI') # Simple estimation
        re1_safe = image.select('B5').max(ee.Image(0.0001))
        chl = image.expression('(NIR / RE1) - 1', {'NIR': image.select('B8'), 'RE1': re1_safe}).rename('CHL')
        return image.addBands([ndvi, ndwi, ndre, lai, chl]).toDictionary()
    except Exception as e:
        # print(f"Warning: Could not calculate indices for image {image.id().getInfo()}: {e}")
        # Return original image dictionary if calculation fails for any reason
        return image.toDictionary()

@st.cache_data(ttl=3600, show_spinner=False, persist=True) # Cache image retrieval for 1 hour
def get_processed_image_gee(_geometry_json, start_date, end_date, index_name):
    """Gets processed GEE image. Input geometry as JSON, returns Image JSON or error."""
    _geometry = ee.Geometry(json.loads(_geometry_json)) # Recreate geometry
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date))

        # Serialize/Deserialize for caching cloud masking and index calculation
        s2_list = s2_sr_col.toList(s2_sr_col.size())
        s2_dicts = [img.toDictionary() for img in ee.List(s2_list).getInfo()] # GetInfo here is necessary

        masked_dicts = [maskS2clouds(img_dict) for img_dict in s2_dicts]
        indexed_dicts = [add_indices_dict(img_dict) for img_dict in masked_dicts]

        # Filter out dicts where masking/indexing might have failed (e.g., missing essential bands)
        # Reconstruct ImageCollection from valid dictionaries
        valid_images = [ee.Image.fromDictionary(d) for d in indexed_dicts if 'B8' in d.get('bands', [])] # Check a common band

        if not valid_images:
             return None, f"هیچ تصویر معتبری پس از ماسک و محاسبه شاخص یافت نشد ({start_date} تا {end_date})."

        indexed_col = ee.ImageCollection.fromImages(valid_images)

        # Ensure the target index exists in the collection
        # sample_bands = indexed_col.first().bandNames().getInfo() # Check bands on first image
        # if index_name not in sample_bands:
        #      return None, f"شاخص '{index_name}' در تصاویر این دوره یافت نشد."

        median_image = indexed_col.select(list(INDEX_INFO.keys())).median() # Select all known indices before median

        # Final check if the specific index exists after median
        final_bands = median_image.bandNames().getInfo()
        if index_name not in final_bands:
             return None, f"شاخص '{index_name}' پس از ترکیب median در تصویر نهایی موجود نیست."

        output_image = median_image.select(index_name)
        # Return image info for caching, not the object itself
        return output_image.serialize(), None

    except ee.EEException as e:
        error_message = f"خطای GEE در get_processed_image: {e}"
        # Add more specific error parsing if needed
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در get_processed_image: {e}\n{traceback.format_exc()}"
        return None, error_message

# --- Function to get thumbnail URL ---
@st.cache_data(ttl=3600, show_spinner="در حال تولید تصویر کوچک...")
def get_thumbnail_url(_image_serialized, _geometry_json, _vis_params):
    """Gets a thumbnail URL for a GEE image."""
    if not _image_serialized:
        return None, "No image data for thumbnail."
    try:
        image = ee.Image.deserialize(_image_serialized)
        geometry = ee.Geometry(json.loads(_geometry_json))
        thumb_url = image.getThumbURL({
            'region': geometry.buffer(500).bounds(), # Buffer point slightly and get bounds
            'dimensions': 256,
            'params': _vis_params,
            'format': 'png'
        })
        return thumb_url, None
    except Exception as e:
        return None, f"خطا در تولید thumbnail: {e}"

# --- Function to get time series ---
@st.cache_data(ttl=3600, show_spinner="در حال دریافت سری زمانی...")
def get_index_time_series_data(_point_geom_json, index_name, start_date, end_date):
    """Gets time series data, returns DataFrame JSON or error."""
    _point_geom = ee.Geometry(json.loads(_point_geom_json))
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date))

        # Use the cached masking/indexing functions
        s2_list = s2_sr_col.toList(s2_sr_col.size())
        s2_dicts = [img.toDictionary() for img in ee.List(s2_list).getInfo()]
        masked_dicts = [maskS2clouds(img_dict) for img_dict in s2_dicts]
        indexed_dicts = [add_indices_dict(img_dict) for img_dict in masked_dicts]

        # Filter, reconstruct, and map to extract values
        valid_images = [ee.Image.fromDictionary(d) for d in indexed_dicts if index_name in [b['id'] for b in d.get('bands', [])]]

        if not valid_images:
             return None, f"داده‌ای برای سری زمانی {index_name} یافت نشد (پس از فیلتر)."

        indexed_col = ee.ImageCollection.fromImages(valid_images)

        def extract_value(image):
            value = image.select(index_name).reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=_point_geom,
                scale=10
            ).get(index_name)
            # Ensure date is properly formatted
            img_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
            return ee.Feature(None, {'date': img_date, index_name: value})

        ts_features = indexed_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return None, f"داده معتبری برای سری زمانی {index_name} یافت نشد."

        # Convert to DataFrame and then to JSON for caching
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        # Ensure numeric type before returning JSON
        ts_df[index_name] = pd.to_numeric(ts_df[index_name], errors='coerce')
        ts_df.dropna(subset=[index_name], inplace=True)

        if ts_df.empty:
             return None, f"داده عددی معتبری برای سری زمانی {index_name} یافت نشد."

        return ts_df.to_json(orient='split', date_format='iso'), None

    except ee.EEException as e:
        return None, f"خطای GEE در سری زمانی ({index_name}): {e}"
    except Exception as e:
        return None, f"خطای ناشناخته در سری زمانی ({index_name}): {e}"

# --- Function to calculate indices for ranking table ---
# This is the slowest part - use spinner and session state
def calculate_all_farm_indices(farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
    results = []
    errors = []
    total_farms = len(farms_df)

    # Use st.expander for progress, as spinner blocks interaction
    with st.expander(f"⏳ در حال محاسبه شاخص {index_name} برای {total_farms} مزرعه...", expanded=True):
        progress_bar = st.progress(0)
        status_text = st.empty()

        for i, (idx, farm) in enumerate(farms_df.iterrows()):
            farm_name = farm['مزرعه']
            lat = farm['عرض جغرافیایی']
            lon = farm['طول جغرافیایی']
            point_geom = ee.Geometry.Point([lon, lat])
            point_geom_json = json.dumps(point_geom.getInfo()) # Serialize for cached function

            status_text.text(f"پردازش مزرعه {i+1}/{total_farms}: {farm_name}")

            def get_mean_value_cached(geom_json, start, end):
                image_serialized, error_img = get_processed_image_gee(geom_json, start, end, index_name)
                if image_serialized:
                    try:
                        image = ee.Image.deserialize(image_serialized)
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=ee.Geometry(json.loads(geom_json)),
                            scale=10
                        ).getInfo()
                        val = mean_dict.get(index_name) if mean_dict else None
                        if val is None and mean_dict is not None:
                            return None, f"'{index_name}' در نتیجه reduceRegion یافت نشد."
                        elif val is None:
                            return None, "ReduceRegion نتیجه‌ای نداشت."
                        return val, None # Return value and no error
                    except ee.EEException as e_reduce:
                        return None, f"خطای GEE در reduceRegion: {e_reduce}"
                    except Exception as e_other:
                        return None, f"خطای ناشناخته در reduceRegion: {e_other}"
                else:
                    return None, error_img or "تصویری برای پردازش یافت نشد."

            # Calculate for current week
            current_val, err_curr = get_mean_value_cached(point_geom_json, start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (جاری): {err_curr}")

            # Calculate for previous week
            previous_val, err_prev = get_mean_value_cached(point_geom_json, start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (قبل): {err_prev}")

            # Calculate change
            change = None
            if current_val is not None and previous_val is not None:
                try: change = float(current_val) - float(previous_val)
                except (TypeError, ValueError): change = None

            results.append({
                'farm_id': farm['farm_id'], # Use unique ID
                'مزرعه': farm_name,
                'کانال': farm.get('کانال', 'N/A'),
                'اداره': farm.get('اداره', 'N/A'),
                'طول جغرافیایی': lon,
                'عرض جغرافیایی': lat,
                f'{index_name}_curr': current_val,
                f'{index_name}_prev': previous_val,
                f'{index_name}_change': change
            })
            progress_bar.progress((i + 1) / total_farms)
            # time.sleep(0.01) # Avoid potential GEE rate limits if needed

        status_text.text(f"محاسبه کامل شد.")
        time.sleep(1) # Keep message visible briefly

    return pd.DataFrame(results), errors


# --- Gemini AI Analysis Function ---
@st.cache_data(show_spinner="🧠 در حال تحلیل با هوش مصنوعی...")
def get_gemini_analysis(_index_name, _farm_name, _current_val, _previous_val, _change_val):
    """Generates analysis and recommendations using Gemini API."""
    if not st.session_state.gemini_available or st.session_state.gemini_model is None:
        return "تحلیل هوش مصنوعی به دلیل خطا در پیکربندی API در دسترس نیست.", None

    if pd.isna(_current_val) or pd.isna(_previous_val) or pd.isna(_change_val) or \
       math.isnan(float(_current_val)) or math.isnan(float(_previous_val)) or math.isnan(float(_change_val)): # Check for actual NaN
         return "داده‌های معتبر کافی برای تحلیل (مقادیر عددی فعلی، قبلی و تغییر) وجود ندارد.", None

    current_str = f"{float(_current_val):.3f}"
    previous_str = f"{float(_previous_val):.3f}"
    change_str = f"{float(_change_val):.3f}"

    index_details = INDEX_INFO.get(_index_name, {"name": _index_name, "desc": ""})
    interpretation = f"شاخص {_index_name} ({index_details['name']}) {index_details['desc']}"

    prompt = f"""
    شما یک دستیار متخصص کشاورزی برای تحلیل داده‌های ماهواره‌ای مزارع نیشکر هستید.
    برای مزرعه نیشکر با نام "{_farm_name}"، شاخص "{_index_name}" تحلیل شده است.
    {interpretation}

    مقدار شاخص در هفته جاری: {current_str}
    مقدار شاخص در هفته قبل: {previous_str}
    میزان تغییر نسبت به هفته قبل: {change_str}

    وظایف شما:
    1.  **تحلیل وضعیت:** به زبان فارسی ساده و دقیق توضیح دهید که این تغییر در مقدار شاخص {_index_name} چه معنایی برای وضعیت سلامت، رشد، یا تنش (مانند تنش آبی یا کمبود مواد مغذی بسته به شاخص) نیشکر در این مزرعه دارد. به مثبت یا منفی بودن تغییر و مقدار آن اشاره کنید.
    2.  **پیشنهاد آبیاری:** بر اساس این تغییر و ماهیت شاخص (به‌خصوص NDWI یا NDVI)، یک پیشنهاد کلی و اولیه برای مدیریت آبیاری در هفته پیش رو ارائه دهید. (مثلاً "نیاز به بررسی دقیق‌تر وضعیت رطوبت خاک و احتمالاً افزایش آبیاری وجود دارد" یا "وضعیت آبی گیاه مطلوب به نظر می‌رسد، روند فعلی حفظ شود").
    3.  **پیشنهاد کوددهی:** بر اساس این تغییر و ماهیت شاخص (به‌خصوص NDRE، CHL یا NDVI)، یک پیشنهاد کلی و اولیه برای مدیریت کوددهی (به‌ویژه نیتروژن) ارائه دهید. (مثلاً "کاهش شاخص NDRE ممکن است نشان‌دهنده نیاز به بررسی وضعیت تغذیه و احتمالاً کوددهی نیتروژنه باشد" یا "شاخص‌های مرتبط با کلروفیل وضعیت خوبی دارند، نیاز فوری به تغییر در کوددهی مشاهده نمی‌شود").

    نکات مهم:
    -   تحلیل و پیشنهادات باید **فقط** بر اساس اطلاعات داده شده باشد.
    -   زبان نوشتار رسمی و علمی اما قابل فهم باشد.
    -   پاسخ کوتاه و متمرکز باشد.
    -   پاسخ به زبان فارسی باشد.

    فرمت پاسخ:
    **تحلیل وضعیت:** [توضیح شما]
    **پیشنهاد آبیاری:** [پیشنهاد شما]
    **پیشنهاد کوددهی:** [پیشنهاد شما]
    """

    try:
        response = st.session_state.gemini_model.generate_content(prompt)
        analysis_text = response.text
        # Simple check for empty or placeholder response
        if not analysis_text or len(analysis_text) < 50:
            return "مدل هوش مصنوعی پاسخی ارائه نکرد یا پاسخ بسیار کوتاه بود.", None
        return analysis_text, None
    except Exception as e:
        error_message = f"خطا در ارتباط با Gemini API: {e}"
        # Don't show error directly here, return it
        return None, error_message

# ========================= Main Panel Layout =========================
st.title(APP_TITLE)
st.markdown(f"**مطالعات کاربردی شرکت کشت و صنعت دهخدا** | تاریخ گزارش: {datetime.date.today().strftime('%Y-%m-%d')}")
st.markdown("---")

# --- Display Selected Farm Info ---
selected_farm_details = None
selected_farm_geom = None
selected_farm_geom_json = None # For caching

if selected_farm_name == "همه مزارع":
    st.info(f"نمایش اطلاعات کلی برای {len(filtered_farms_df)} مزرعه در روز **{selected_day}**.")
    # Define a bounding box geometry for map centering/zooming if needed
    try:
        min_lon, min_lat = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
        max_lon, max_lat = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
        selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo()) # Serialize
    except Exception as e:
        st.warning(f"خطا در ایجاد bounding box برای همه مزارع: {e}")
        # Fallback geometry (e.g., center of the area)
        center_lat = filtered_farms_df['عرض جغرافیایی'].mean()
        center_lon = filtered_farms_df['طول جغرافیایی'].mean()
        selected_farm_geom = ee.Geometry.Point([center_lon, center_lat])
        selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())

else:
    selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat = selected_farm_details['عرض جغرافیایی']
    lon = selected_farm_details['طول جغرافیایی']
    selected_farm_geom = ee.Geometry.Point([lon, lat])
    selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo()) # Serialize

    st.subheader(f"📍 اطلاعات مزرعه: {selected_farm_name}")
    cols = st.columns([1, 1, 1, 2]) # Adjust column widths
    with cols[0]:
        st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A")
        st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
    with cols[1]:
        st.metric("کانال", f"{selected_farm_details.get('کانال', 'N/A')}")
        st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
    with cols[2]:
        st.metric("اداره", f"{selected_farm_details.get('اداره', 'N/A')}")
        st.metric("روز آبیاری", f"{selected_farm_details.get('روزهای هفته', 'N/A')}")

    # --- Display Thumbnail ---
    with cols[3]:
        st.markdown("**تصویر کوچک (هفته جاری):**")
        # Get the current image for the thumbnail
        thumb_image_serial, err_img = get_processed_image_gee(
            selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index
        )
        if thumb_image_serial:
            thumb_url, err_thumb = get_thumbnail_url(thumb_image_serial, selected_farm_geom_json, vis_params)
            if thumb_url:
                st.image(thumb_url, caption=f"{selected_index} - {start_date_current_str} to {end_date_current_str}", width=200)
            elif err_thumb:
                st.warning(f"Thumbnail Error: {err_thumb}")
        elif err_img:
             st.warning(f"Image Error: {err_img}")


# --- Main Content Tabs ---
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ نقشه", "📊 جدول رتبه‌بندی", "📈 نمودار سری زمانی", " dashboards داشبورد خلاصه"])

with tab1:
    st.subheader(f"نقشه ماهواره‌ای - شاخص: {selected_index}")
    m = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
    m.add_basemap("HYBRID")

    map_data_placeholder = st.empty() # Placeholder for map rendering status

    if selected_farm_geom_json:
        map_data_placeholder.info("در حال بارگذاری لایه شاخص روی نقشه...")
        gee_image_serial, error_msg_current = get_processed_image_gee(
            selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index
        )

        if gee_image_serial:
            try:
                gee_image_current = ee.Image.deserialize(gee_image_serial) # Deserialize for map
                m.addLayer(
                    gee_image_current,
                    vis_params,
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )

                # Add Legend
                legend_title = f"{selected_index} ({index_props['name']})"
                m.add_legend(legend_title=legend_title, palette=index_props['palette'], min=index_props['min'], max=index_props['max'], layer_name=legend_title)


                # Add Markers
                if selected_farm_name == "همه مزارع":
                    points = filtered_farms_df[['عرض جغرافیایی', 'طول جغرافیایی', 'مزرعه']].to_dict('records')
                    # Create GeoJSON for geemap (more efficient for many points)
                    features = []
                    for p in points:
                         features.append({
                             'type': 'Feature',
                             'geometry': {'type': 'Point', 'coordinates': [p['طول جغرافیایی'], p['عرض جغرافیایی']]},
                             'properties': {'name': p['مزرعه']}
                         })
                    farm_geojson = {'type': 'FeatureCollection', 'features': features}
                    m.add_geojson(farm_geojson, layer_name="مزارع", info_mode='on_hover', style={'color': 'blue', 'fillColor': 'blue', 'opacity': 0.7, 'weight': 1, 'radius': 3})
                    # Center map on the bounding box or center point
                    if isinstance(selected_farm_geom, ee.geometry.Geometry):
                         m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM)
                else:
                     # Single marker for selected farm
                     folium.Marker(
                         location=[selected_farm_details['عرض جغرافیایی'], selected_farm_details['طول جغرافیایی']],
                         popup=f"<b>{selected_farm_name}</b><br>{selected_index} (جاری): محاسبه...",
                         tooltip=selected_farm_name,
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     if isinstance(selected_farm_geom, ee.geometry.Geometry):
                          m.center_object(selected_farm_geom, zoom=15) # Zoom closer

                m.add_layer_control()
                map_data_placeholder.empty() # Remove loading message
                st_folium(m, width=None, height=600, use_container_width=True, key="map1") # Add key
            except Exception as map_err:
                 map_data_placeholder.error(f"خطا در نمایش نقشه: {map_err}")
                 st.error(traceback.format_exc())
        else:
            map_data_placeholder.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")
    else:
         map_data_placeholder.warning("موقعیت جغرافیایی برای نمایش نقشه تعریف نشده است.")


with tab2:
    st.subheader(f"جدول رتبه‌بندی مزارع بر اساس {selected_index} ({selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    # --- Calculate or Retrieve Ranking Data ---
    ranking_params = (selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str, selected_day)

    # Check if calculation is needed (parameters changed or data is empty)
    if st.session_state.ranking_data['params'] != ranking_params or st.session_state.ranking_data['df'].empty:
        print(f"Recalculating ranking table for: {ranking_params}")
        # Clear previous results before recalculating
        st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}
        ranking_df_raw, calculation_errors = calculate_all_farm_indices(
            filtered_farms_df, selected_index,
            start_date_current_str, end_date_current_str,
            start_date_previous_str, end_date_previous_str
        )
        # Store results in session state
        st.session_state.ranking_data['df'] = ranking_df_raw
        st.session_state.ranking_data['errors'] = calculation_errors
        st.session_state.ranking_data['params'] = ranking_params
        # Clear Gemini cache as ranking data changed
        st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None}
    else:
        print("Using cached ranking data from session state.")
        ranking_df_raw = st.session_state.ranking_data['df']
        calculation_errors = st.session_state.ranking_data['errors']

    # --- Display Ranking Table ---
    if not ranking_df_raw.empty:
        ranking_df_display = ranking_df_raw.copy()
        
        # Rename columns for display clarity
        curr_col = f'{selected_index} (هفته جاری)'
        prev_col = f'{selected_index} (هفته قبل)'
        change_col = 'تغییر'
        ranking_df_display = ranking_df_display.rename(columns={
            f'{selected_index}_curr': curr_col,
            f'{selected_index}_prev': prev_col,
            f'{selected_index}_change': change_col
        })
        
        # Determine Status
        higher_is_better = index_props['higher_is_better']
        def determine_status(change_val):
            if pd.isna(change_val) or math.isnan(float(change_val)):
                 return "بدون داده"

            change_val = float(change_val) # Ensure float

            if higher_is_better:
                if change_val > CHANGE_THRESHOLD: return "🟢 بهبود / رشد"
                elif change_val < -CHANGE_THRESHOLD: return "🔴 کاهش / تنش"
                else: return "⚪ ثابت"
            else: # Lower is better (not used for current indices, but for future)
                if change_val < -CHANGE_THRESHOLD: return "🟢 بهبود / رشد"
                elif change_val > CHANGE_THRESHOLD: return "🔴 کاهش / تنش"
                else: return "⚪ ثابت"

        ranking_df_display['وضعیت'] = ranking_df_display[change_col].apply(determine_status)

        # Sort table
        ranking_df_sorted = ranking_df_display.sort_values(
            by=curr_col,
            ascending=not higher_is_better, # Sort descending if higher is better
            na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # Format numbers
        cols_to_format = [curr_col, prev_col, change_col]
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                 ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float, str)) and str(x).replace('.', '', 1).isdigit() else ("-" if pd.isna(x) else x))


        # Display table
        st.dataframe(ranking_df_sorted[[
            'مزرعه', 'کانال', 'اداره', curr_col, prev_col, change_col, 'وضعیت'
            ]], use_container_width=True, height=400) # Set height for scroll

        # Download Button
        try:
            csv_data = ranking_df_sorted.to_csv(index=True, encoding='utf-8-sig')
            st.download_button(
                label="📥 دانلود جدول (CSV)", data=csv_data,
                file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv'
            )
        except Exception as e: st.error(f"خطا در ایجاد فایل دانلود: {e}")

        # Display Errors during calculation
        if calculation_errors:
            with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها", expanded=False):
                 unique_errors = sorted(list(set(calculation_errors)))
                 st.warning(f"تعداد کل خطاها: {len(calculation_errors)} (نمایش موارد منحصربفرد)")
                 for i, error in enumerate(unique_errors):
                     st.error(f"- {error}")
                     if i > 15: # Limit displayed errors
                          st.warning(f"... و {len(unique_errors) - i} خطای منحصربفرد دیگر.")
                          break
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی {selected_index} یافت نشد یا محاسبه نشد.")
        # Also show errors if the dataframe is empty but errors exist
        if calculation_errors:
             st.error("خطاهایی در حین تلاش برای محاسبه رخ داده است (جزئیات در بالا).")


with tab3:
    st.subheader(f"نمودار روند زمانی شاخص {selected_index}")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom_json:
        # Define time series period (e.g., last 12 months)
        ts_end_date = today.strftime('%Y-%m-%d')
        ts_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')

        # Get time series data (returns DataFrame JSON)
        ts_df_json, ts_error = get_index_time_series_data(
            selected_farm_geom_json, selected_index, ts_start_date, ts_end_date
        )

        if ts_error:
            st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
        elif ts_df_json:
            try:
                # Read DataFrame from JSON
                ts_df = pd.read_json(ts_df_json, orient='split')
                ts_df.index = pd.to_datetime(ts_df.index, format='iso') # Ensure datetime index

                if not ts_df.empty:
                     fig_ts = px.line(ts_df, y=selected_index, markers=True,
                                      title=f"روند زمانی {selected_index} برای مزرعه {selected_farm_name}",
                                      labels={'index': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                     fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                     st.plotly_chart(fig_ts, use_container_width=True)
                     st.caption("نقاط داده بر اساس تصاویر ماهواره‌ای بدون ابر موجود در بازه زمانی نمایش داده شده‌اند.")
                     # Optional: Download time series data
                     csv_ts = ts_df.to_csv(encoding='utf-8-sig')
                     st.download_button(label="📥 دانلود داده‌های سری زمانی (CSV)", data=csv_ts, file_name=f'timeseries_{selected_farm_name}_{selected_index}.csv', mime='text/csv')

                else:
                     st.info(f"داده معتبری برای نمایش نمودار سری زمانی {selected_index} یافت نشد.")
            except Exception as e_plot:
                 st.error(f"خطا در رسم نمودار سری زمانی: {e_plot}")
                 st.error(traceback.format_exc())

        else:
             st.info(f"داده‌ای برای سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
    else:
         st.warning("موقعیت جغرافیایی مزرعه برای دریافت سری زمانی مشخص نیست.")

with tab4:
    st.subheader(f"داشبورد خلاصه وضعیت روزانه ({selected_day}) - شاخص: {selected_index}")

    # Ensure ranking data is calculated and available
    ranking_df_raw = st.session_state.ranking_data.get('df')
    if ranking_df_raw is None or ranking_df_raw.empty:
        st.warning(f"داده‌های رتبه‌بندی برای روز {selected_day} و شاخص {selected_index} محاسبه نشده یا خالی است. لطفاً ابتدا به تب 'جدول رتبه‌بندی' بروید تا محاسبات انجام شود.")
        # Optionally trigger calculation here if desired, but could be slow
        # st.button("محاسبه داده‌های رتبه‌بندی") -> would need logic to call calculate_all_farm_indices
    else:
        # Use the processed dataframe from the ranking tab if possible, or re-process raw data
        # For simplicity, let's re-use the sorted/formatted df if available in session state,
        # otherwise re-process the raw data stored in session state.
        # Note: This assumes the ranking tab was visited or calculation triggered.

        # Reprocess raw data for dashboard (ensures consistency)
        df_dash = ranking_df_raw.copy()
        curr_col_raw = f'{selected_index}_curr'
        prev_col_raw = f'{selected_index}_prev'
        change_col_raw = f'{selected_index}_change'
        
        # Convert to numeric, coercing errors
        df_dash[curr_col_raw] = pd.to_numeric(df_dash[curr_col_raw], errors='coerce')
        df_dash[prev_col_raw] = pd.to_numeric(df_dash[prev_col_raw], errors='coerce')
        df_dash[change_col_raw] = pd.to_numeric(df_dash[change_col_raw], errors='coerce')

        # --- Summary Metrics ---
        st.markdown("**آمار کلی وضعیت مزارع:**")
        higher_is_better = index_props['higher_is_better']

        def get_status_dash(change):
            if pd.isna(change) or math.isnan(change): return "بدون داده"
            if higher_is_better:
                 if change > CHANGE_THRESHOLD: return "بهبود"
                 elif change < -CHANGE_THRESHOLD: return "کاهش"
                 else: return "ثابت"
            else:
                 if change < -CHANGE_THRESHOLD: return "بهبود"
                 elif change > CHANGE_THRESHOLD: return "کاهش"
                 else: return "ثابت"

        df_dash['status'] = df_dash[change_col_raw].apply(get_status_dash)
        status_counts = df_dash['status'].value_counts()

        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("🟢 بهبود", status_counts.get("بهبود", 0))
        with col2: st.metric("⚪ ثابت", status_counts.get("ثابت", 0))
        with col3: st.metric("🔴 کاهش", status_counts.get("کاهش", 0))
        with col4: st.metric("⚫️ بدون داده", status_counts.get("بدون داده", 0))
        st.markdown("---")


        # --- Plots ---
        col_plot1, col_plot2 = st.columns(2)

        with col_plot1:
            st.markdown(f"**توزیع مقادیر {selected_index} (هفته جاری)**")
            # Filter out NaNs for histogram
            hist_data = df_dash[curr_col_raw].dropna()
            if not hist_data.empty:
                 fig_hist = px.histogram(hist_data, nbins=20, title=f"توزیع {selected_index}", labels={'value': f'مقدار {selected_index}'})
                 fig_hist.update_layout(yaxis_title="تعداد مزارع", xaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                 st.plotly_chart(fig_hist, use_container_width=True)
            else:
                 st.info("داده‌ای برای رسم هیستوگرام وجود ندارد.")

        with col_plot2:
            st.markdown("**مقایسه مقادیر هفته جاری و قبل**")
            # Filter out NaNs for scatter plot
            scatter_data = df_dash.dropna(subset=[curr_col_raw, prev_col_raw, 'status'])
            if not scatter_data.empty:
                 fig_scatter = px.scatter(
                     scatter_data, x=prev_col_raw, y=curr_col_raw,
                     color='status', hover_name='مزرعه',
                     title=f"مقایسه {selected_index}: هفته جاری در مقابل هفته قبل",
                     labels={prev_col_raw: f"{selected_index} (هفته قبل)", curr_col_raw: f"{selected_index} (هفته جاری)", 'status': 'وضعیت'},
                     color_discrete_map={ # Map status to colors
                         'بهبود': 'green',
                         'ثابت': 'grey',
                         'کاهش': 'red',
                         'بدون داده': 'black'
                     }
                 )
                 # Add a y=x line for reference
                 min_val_sc = min(scatter_data[prev_col_raw].min(), scatter_data[curr_col_raw].min())
                 max_val_sc = max(scatter_data[prev_col_raw].max(), scatter_data[curr_col_raw].max())
                 fig_scatter.add_shape(type='line', x0=min_val_sc, y0=min_val_sc, x1=max_val_sc, y1=max_val_sc, line=dict(color='rgba(0,0,0,0.5)', dash='dash'))
                 fig_scatter.update_layout(xaxis_title=f"{selected_index} (هفته قبل)", yaxis_title=f"{selected_index} (هفته جاری)", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                 st.plotly_chart(fig_scatter, use_container_width=True)
                 st.caption("نقاط بالای خط چین بهبود یافته‌اند، نقاط پایین خط کاهش داشته‌اند.")
            else:
                 st.info("داده‌ای برای رسم نمودار پراکندگی وجود ندارد.")

        st.markdown("---")

        # --- Top/Bottom Farms ---
        st.markdown("**عملکرد مزارع (بر اساس مقدار هفته جاری):**")
        df_sorted_dash = df_dash.sort_values(by=curr_col_raw, ascending=not higher_is_better, na_position='last').dropna(subset=[curr_col_raw])

        col_top, col_bottom = st.columns(2)
        with col_top:
            st.markdown(f"**🟢 ۵ مزرعه برتر**")
            st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].head(5).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}"}), use_container_width=True)
        with col_bottom:
            st.markdown(f"**🔴 ۵ مزرعه ضعیف‌تر**")
            st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].tail(5).sort_values(by=curr_col_raw, ascending=not higher_is_better).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}"}), use_container_width=True)


# --- AI Analysis Section (if single farm selected) ---
if selected_farm_name != "همه مزارع":
    st.markdown("---")
    st.subheader(f"🧠 تحلیل هوش مصنوعی ({selected_index}) برای مزرعه: {selected_farm_name}")

    # Check if ranking data is available for the farm
    ranking_df_raw = st.session_state.ranking_data.get('df')
    if ranking_df_raw is not None and not ranking_df_raw.empty:
        farm_analysis_data = ranking_df_raw[ranking_df_raw['مزرعه'] == selected_farm_name]

        if not farm_analysis_data.empty:
            farm_row = farm_analysis_data.iloc[0]
            current_val = farm_row.get(f'{selected_index}_curr')
            previous_val = farm_row.get(f'{selected_index}_prev')
            change_val = farm_row.get(f'{selected_index}_change')

            # Check if analysis is needed or already cached
            gemini_params = (selected_index, selected_farm_name, current_val, previous_val, change_val)
            if st.session_state.gemini_analysis.get('params') != gemini_params:
                print(f"Requesting new Gemini analysis for: {gemini_params}")
                analysis_text, analysis_error = get_gemini_analysis(
                    selected_index, selected_farm_name, current_val, previous_val, change_val
                )
                # Store result in session state
                st.session_state.gemini_analysis['text'] = analysis_text
                st.session_state.gemini_analysis['error'] = analysis_error
                st.session_state.gemini_analysis['params'] = gemini_params
            else:
                print("Using cached Gemini analysis from session state.")
                analysis_text = st.session_state.gemini_analysis.get('text')
                analysis_error = st.session_state.gemini_analysis.get('error')

            # Display analysis or error
            if analysis_error:
                 st.error(f"خطا در تولید تحلیل توسط هوش مصنوعی: {analysis_error}")
            elif analysis_text:
                 st.markdown(analysis_text)
                 st.caption("توجه: این تحلیل توسط هوش مصنوعی و صرفاً بر اساس تغییرات شاخص ارائه شده است. همیشه با مشاهدات میدانی تلفیق شود.")
            elif st.session_state.gemini_available: # Check if API was available but no text returned
                  st.info("تحلیلی توسط هوش مصنوعی برای این داده‌ها ارائه نشد.")
            else: # API was not available
                  st.warning("تحلیل هوش مصنوعی به دلیل عدم پیکربندی صحیح API در دسترس نیست.")

        else:
             st.warning(f"داده‌های محاسبه شده برای مزرعه '{selected_farm_name}' جهت تحلیل یافت نشد (ممکن است در محاسبات جدول رتبه‌بندی خطا رخ داده باشد).")
    else:
        st.info("برای مشاهده تحلیل هوش مصنوعی، لطفاً یک مزرعه خاص را انتخاب کنید و از محاسبه داده‌ها در تب 'جدول رتبه‌بندی' اطمینان حاصل کنید.")


# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط اسماعیل کیانی")
st.sidebar.markdown("Streamlit | GEE | Geemap | Plotly | Gemini")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    st.sidebar.error("🚨 کلید API Gemini ارائه نشده است.")
elif st.session_state.gemini_available:
    st.sidebar.success("✅ Gemini API فعال است.")
else:
     st.sidebar.warning("⚠️ Gemini API غیرفعال است.")
st.sidebar.warning("هشدار امنیتی: کلید API در کد قرار دارد.")

# --- END OF FILE ---
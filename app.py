# --- START OF FILE app_chatbot.py ---

import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium
import base64
import time
import math
import re # For simple text processing in chatbot

# --- Gemini API Integration ---
import google.generativeai as genai

# WARNING: Storing API keys directly in code is insecure!
# Use environment variables or st.secrets in production.
GEMINI_API_KEY = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- PASTE YOUR KEY HERE

# --- Constants ---
APP_TITLE = "سامانه پایش هوشمند نیشکر (نسخه چت‌بات)"
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' #<-- YOUR SERVICE ACCOUNT FILE
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12
INDEX_INFO = {
    "NDVI": {"name": "شاخص تراکم پوشش گیاهی", "palette": 'RdYlGn', "min": 0.0, "max": 0.9, "higher_is_better": True, "desc": "رنگ سبز بیانگر محصول متراکم و سالم و رنگ قرمز نشان‌دهنده‌ی محصول کم‌پشت و پراکنده است."},
    "NDWI": {"name": "شاخص محتوای آبی گیاهان", "palette": ['#d7191c', '#fdae61', '#ffffbf', '#abd9e9', '#2c7bb6'], "min": -0.2, "max": 0.6, "higher_is_better": True, "desc": "رنگ آبی بیشتر نشان‌دهنده محتوای آبی بیشتر و رنگ قرمز نشان‌دهنده کم‌آبی است."},
    "NDRE": {"name": "شاخص میزان ازت گیاه (لبه قرمز)", "palette": 'Purples', "min": 0.0, "max": 0.6, "higher_is_better": True, "desc": "رنگ بنفش نشان‌دهنده میزان زیاد ازت/کلروفیل و رنگ روشن‌تر نشان‌دهنده کاهش آن در گیاه است."},
    "LAI": {"name": "شاخص سطح برگ (تخمینی)", "palette": 'YlGn', "min": 0, "max": 7, "higher_is_better": True, "desc": "رنگ سبز پررنگ‌تر نشان‌دهنده سطح برگ بیشتر در ناحیه است."},
    "CHL": {"name": "شاخص کلروفیل (تخمینی)", "palette": ['#b35806','#f1a340','#fee0b6','#d8daeb','#998ec3','#542788'], "min": 0, "max": 10, "higher_is_better": True, "desc": "رنگ بنفش/تیره نشان‌دهنده کلروفیل بیشتر است و رنگ قهوه‌ای/روشن نشان‌دهنده کاهش کلروفیل یا تنش است."}
}
CHANGE_THRESHOLD = 0.03

# --- Page Config and CSS ---
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🌾",
    layout="wide"
)
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        body, .main, button, input, textarea, select, .stTextInput, .stSelectbox, .stDateInput, .stButton>button, .stTabs [data-baseweb="tab"], .stMetric, .stDataFrame, .stPlotlyChart, .stChatMessage {
            font-family: 'Vazirmatn', sans-serif !important;
            direction: rtl; /* Ensure consistent RTL */
        }
        .stBlock, .stHorizontalBlock { direction: rtl; }
        h1, h2, h3, h4, h5, h6 { text-align: right; color: #2c3e50; }
        .plotly .gtitle { text-align: right !important; }
        .stSelectbox > label, .stDateInput > label, .stTextInput > label, .stTextArea > label {
             text-align: right !important; width: 100%; display: block;
         }
        .dataframe { text-align: right; }
        .stTabs [data-baseweb="tab-list"] { gap: 5px; }
        .stTabs [data-baseweb="tab"] { height: 50px; padding: 10px 20px; background-color: #f0f2f6; border-radius: 8px 8px 0 0; font-weight: 600; }
        .stTabs [aria-selected="true"] { background-color: #e6f2ff; }
        .stMetric { background-color: #f8f9fa; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;}
        .stMetric > label { font-weight: bold; color: #495057; }
        .stMetric > div { font-size: 1.5em; color: #007bff; }
        .css-1d391kg { direction: rtl; }
        .css-1d391kg .stSelectbox > label { text-align: right !important; }
        /* Chat message alignment */
        .stChatMessage[data-testid="chatAvatarIcon-user"] + div { order: 1; /* Puts user message text to the left */ }
        .stChatMessage[data-testid="chatAvatarIcon-assistant"] + div { order: -1; /* Puts assistant message text to the right */ }
        /* Ensure text within message is right-aligned */
        .stChatMessage div[data-testid="stChatMessageContent"] p { text-align: right; }
    </style>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if 'gee_initialized' not in st.session_state: st.session_state.gee_initialized = False
if 'farm_data' not in st.session_state: st.session_state.farm_data = None
if 'ranking_data' not in st.session_state: st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}
if 'gemini_analysis' not in st.session_state: st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None}
if 'gemini_available' not in st.session_state: st.session_state.gemini_available = False
if 'gemini_model' not in st.session_state: st.session_state.gemini_model = None
if "messages" not in st.session_state: st.session_state.messages = [] # For chatbot history

# --- GEE and Gemini Initialization ---
@st.cache_resource
def initialize_gee():
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            return False
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except Exception as e:
        st.error(f"خطا در اتصال به GEE: {e}")
        return False

@st.cache_resource
def configure_gemini():
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
             print("Gemini API Key not provided.")
             return None, False
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Gemini API Configured Successfully.")
        return model, True
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        st.warning(f"⚠️ اخطار: خطا در پیکربندی Gemini API ({e}). تحلیل و چت‌بات AI غیرفعال خواهد بود.")
        return None, False

if not st.session_state.gee_initialized:
    st.session_state.gee_initialized = initialize_gee()
    if not st.session_state.gee_initialized: st.stop()

if st.session_state.gemini_model is None:
     st.session_state.gemini_model, st.session_state.gemini_available = configure_gemini()

# --- Load Farm Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    try:
        df = pd.read_csv(csv_path)
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل CSV فاقد ستون‌های ضروری است: {required_cols}")
            return None
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool)
        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
        df = df[~df['coordinates_missing']]
        if df.empty:
            st.warning("⚠️ داده معتبر مزرعه یافت نشد.")
            return None
        df['روزهای هفته'] = df['روزهای هفته'].astype(str).str.strip()
        df['farm_id'] = df['مزرعه'] + '_' + df['طول جغرافیایی'].astype(str) + '_' + df['عرض جغرافیایی'].astype(str)
        print(f"Farm data loaded: {len(df)} farms.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد.")
        return None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری CSV: {e}")
        st.error(traceback.format_exc())
        return None

if st.session_state.farm_data is None:
    st.session_state.farm_data = load_farm_data()

if st.session_state.farm_data is None: st.stop()

# ========================= Sidebar Inputs =========================
st.sidebar.header("⚙️ تنظیمات نمایش")

available_days = sorted(st.session_state.farm_data['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته:", options=available_days,
    index=available_days.index("شنبه") if "شنبه" in available_days else 0,
    key='selected_day_key'
)

filtered_farms_df = st.session_state.farm_data[st.session_state.farm_data['روزهای هفته'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

# Create list of farm names available for the selected day
available_farm_names_today = ["همه مزارع"] + sorted(filtered_farms_df['مزرعه'].unique())

selected_farm_name = st.sidebar.selectbox(
    "🌾 انتخاب مزرعه:", options=available_farm_names_today, index=0, key='selected_farm_key'
)

selected_index = st.sidebar.selectbox(
    "📈 انتخاب شاخص:", options=list(INDEX_INFO.keys()),
    format_func=lambda x: f"{x} ({INDEX_INFO[x]['name']})", index=0, key='selected_index_key'
)
index_props = INDEX_INFO[selected_index]
vis_params = {'min': index_props['min'], 'max': index_props['max'], 'palette': index_props['palette']}

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
except KeyError: st.sidebar.error(f"روز هفته '{selected_day}' نامعتبر."); st.stop()
except Exception as e: st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}"); st.stop()

# ========================= GEE Functions (Cached - unchanged from previous version) =========================
@st.cache_data(persist=True)
def maskS2clouds(image_dict):
    image = ee.Image.fromDictionary(image_dict)
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    good_quality = scl.remap([4, 5, 6], [1, 1, 1], 0)
    opticalBands = image.select('B.*').multiply(0.0001)
    masked_image = image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality)
    return masked_image.toDictionary()

@st.cache_data(persist=True)
def add_indices_dict(image_dict):
    image = ee.Image.fromDictionary(image_dict)
    try:
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = image.normalizedDifference(['B8', 'B11']).rename('NDWI')
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        lai = ndvi.multiply(3.5).rename('LAI')
        re1_safe = image.select('B5').max(ee.Image(0.0001))
        chl = image.expression('(NIR / RE1) - 1', {'NIR': image.select('B8'), 'RE1': re1_safe}).rename('CHL')
        return image.addBands([ndvi, ndwi, ndre, lai, chl]).toDictionary()
    except Exception:
        return image.toDictionary()

@st.cache_data(ttl=3600, show_spinner=False, persist=True)
def get_processed_image_gee(_geometry_json, start_date, end_date, index_name):
    _geometry = ee.Geometry(json.loads(_geometry_json))
    try:
        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_geometry).filterDate(start_date, end_date)
        s2_list = s2_sr_col.toList(s2_sr_col.size())
        s2_dicts = ee.List(s2_list).getInfo()
        if not isinstance(s2_dicts, list): raise ValueError(f"getInfo() did not return a list: {type(s2_dicts)}")
        if not s2_dicts: return None, f"No initial images found ({start_date} to {end_date})."

        masked_dicts = [maskS2clouds(img_dict) for img_dict in s2_dicts]
        indexed_dicts = [add_indices_dict(img_dict) for img_dict in masked_dicts]
        valid_indexed_dicts = [d for d in indexed_dicts if d and index_name in [b.get('id') for b in d.get('bands', [])]]
        valid_images = [ee.Image.fromDictionary(d) for d in valid_indexed_dicts]

        if not valid_images:
            err_detail = f"(Initial: {len(s2_dicts)}, Valid with index '{index_name}': {len(valid_images)})"
            return None, f"No valid images found after processing {err_detail}."

        indexed_col = ee.ImageCollection.fromImages(valid_images)
        median_image = indexed_col.select(list(INDEX_INFO.keys())).median()
        final_bands = median_image.bandNames().getInfo()
        if index_name not in final_bands:
            return None, f"Index '{index_name}' not present in final median. Available: {final_bands}"

        output_image = median_image.select(index_name)
        return output_image.serialize(), None
    except ee.EEException as e: return None, f"GEE Error: {e}"
    except Exception as e: return None, f"Unknown Error in get_processed_image: {e}\n{traceback.format_exc()}"

@st.cache_data(ttl=3600, show_spinner="در حال تولید تصویر کوچک...")
def get_thumbnail_url(_image_serialized, _geometry_json, _vis_params):
    if not _image_serialized: return None, "No image data for thumbnail."
    try:
        image = ee.Image.deserialize(_image_serialized)
        geometry = ee.Geometry(json.loads(_geometry_json))
        thumb_url = image.getThumbURL({'region': geometry.buffer(500).bounds(), 'dimensions': 256, 'params': _vis_params, 'format': 'png'})
        return thumb_url, None
    except Exception as e: return None, f"Thumbnail Error: {e}"

@st.cache_data(ttl=3600, show_spinner="در حال دریافت سری زمانی...")
def get_index_time_series_data(_point_geom_json, index_name, start_date, end_date):
    _point_geom = ee.Geometry(json.loads(_point_geom_json))
    try:
        s2_sr_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(_point_geom).filterDate(start_date, end_date)
        s2_list = s2_sr_col.toList(s2_sr_col.size())
        s2_dicts = ee.List(s2_list).getInfo()
        if not isinstance(s2_dicts, list): raise ValueError(f"getInfo() did not return a list: {type(s2_dicts)}")
        masked_dicts = [maskS2clouds(img_dict) for img_dict in s2_dicts]
        indexed_dicts = [add_indices_dict(img_dict) for img_dict in masked_dicts]
        valid_images = [ee.Image.fromDictionary(d) for d in indexed_dicts if d and index_name in [b.get('id') for b in d.get('bands', [])]]
        if not valid_images: return None, f"No valid images found for time series ({index_name})."

        indexed_col = ee.ImageCollection.fromImages(valid_images)
        def extract_value(image):
            value = image.select(index_name).reduceRegion(reducer=ee.Reducer.first(), geometry=_point_geom, scale=10).get(index_name)
            img_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
            return ee.Feature(None, {'date': img_date, index_name: value})

        ts_features = indexed_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']
        if not ts_info: return None, f"No valid time series data points found for {index_name}."

        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        ts_df[index_name] = pd.to_numeric(ts_df[index_name], errors='coerce')
        ts_df.dropna(subset=[index_name], inplace=True)
        if ts_df.empty: return None, f"No valid numeric time series data for {index_name}."
        return ts_df.to_json(orient='split', date_format='iso'), None
    except ee.EEException as e: return None, f"GEE Time Series Error ({index_name}): {e}"
    except Exception as e: return None, f"Unknown Time Series Error ({index_name}): {e}"

# --- Function to calculate indices for ranking table (unchanged) ---
def calculate_all_farm_indices(farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
    results = []
    errors = []
    total_farms = len(farms_df)
    with st.expander(f"⏳ در حال محاسبه شاخص {index_name} برای {total_farms} مزرعه...", expanded=True):
        progress_bar = st.progress(0)
        status_text = st.empty()
        for i, (idx, farm) in enumerate(farms_df.iterrows()):
            farm_name = farm['مزرعه']
            lat = farm['عرض جغرافیایی']
            lon = farm['طول جغرافیایی']
            point_geom = ee.Geometry.Point([lon, lat])
            point_geom_json = json.dumps(point_geom.getInfo())
            status_text.text(f"پردازش مزرعه {i+1}/{total_farms}: {farm_name}")
            def get_mean_value_cached(geom_json, start, end):
                image_serialized, error_img = get_processed_image_gee(geom_json, start, end, index_name)
                if image_serialized:
                    try:
                        image = ee.Image.deserialize(image_serialized)
                        mean_dict = image.reduceRegion(reducer=ee.Reducer.mean(), geometry=ee.Geometry(json.loads(geom_json)), scale=10).getInfo()
                        val = mean_dict.get(index_name) if mean_dict else None
                        if val is None and mean_dict is not None: return None, f"'{index_name}' not found in reduceRegion result."
                        elif val is None: return None, "ReduceRegion returned no result."
                        return val, None
                    except ee.EEException as e_reduce: return None, f"GEE Error in reduceRegion: {e_reduce}"
                    except Exception as e_other: return None, f"Unknown Error in reduceRegion: {e_other}"
                else: return None, error_img or "Image not found for processing."

            current_val, err_curr = get_mean_value_cached(point_geom_json, start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (Current): {err_curr}")
            previous_val, err_prev = get_mean_value_cached(point_geom_json, start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (Previous): {err_prev}")

            change = None
            if current_val is not None and previous_val is not None:
                try: change = float(current_val) - float(previous_val)
                except (TypeError, ValueError): change = None

            results.append({'farm_id': farm['farm_id'], 'مزرعه': farm_name, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                           'طول جغرافیایی': lon, 'عرض جغرافیایی': lat, f'{index_name}_curr': current_val, f'{index_name}_prev': previous_val, f'{index_name}_change': change})
            progress_bar.progress((i + 1) / total_farms)
        status_text.text(f"محاسبه کامل شد.")
        time.sleep(1)
    return pd.DataFrame(results), errors

# --- Gemini AI Analysis Function (unchanged) ---
@st.cache_data(show_spinner="🧠 در حال تحلیل با هوش مصنوعی...")
def get_gemini_analysis(_index_name, _farm_name, _current_val, _previous_val, _change_val):
    if not st.session_state.gemini_available or st.session_state.gemini_model is None:
        return "تحلیل هوش مصنوعی به دلیل خطا در پیکربندی API در دسترس نیست.", None
    # Check for NaN explicitly
    try:
        if pd.isna(_current_val) or pd.isna(_previous_val) or pd.isna(_change_val) or \
           math.isnan(float(_current_val)) or math.isnan(float(_previous_val)) or math.isnan(float(_change_val)):
            return "داده‌های معتبر کافی برای تحلیل (مقادیر عددی فعلی، قبلی و تغییر) وجود ندارد.", None
    except (TypeError, ValueError): # Handle cases where conversion to float fails
        return "مقادیر ورودی نامعتبر برای تحلیل.", None


    current_str = f"{float(_current_val):.3f}"
    previous_str = f"{float(_previous_val):.3f}"
    change_str = f"{float(_change_val):.3f}"
    index_details = INDEX_INFO.get(_index_name, {"name": _index_name, "desc": ""})
    interpretation = f"شاخص {_index_name} ({index_details['name']}) {index_details['desc']}"
    prompt = f"""
    شما یک دستیار متخصص کشاورزی برای تحلیل داده‌های ماهواره‌ای مزارع نیشکر هستید.
    برای مزرعه نیشکر با نام "{_farm_name}"، شاخص "{_index_name}" تحلیل شده است. {interpretation}
    مقدار شاخص در هفته جاری: {current_str}. مقدار شاخص در هفته قبل: {previous_str}. میزان تغییر: {change_str}.

    وظایف:
    1.  **تحلیل وضعیت:** به زبان فارسی ساده و دقیق توضیح دهید که این تغییر در شاخص {_index_name} چه معنایی برای وضعیت سلامت، رشد، یا تنش (بسته به شاخص) نیشکر دارد.
    2.  **پیشنهاد آبیاری:** بر اساس این تغییر و ماهیت شاخص، پیشنهاد کلی برای مدیریت آبیاری ارائه دهید.
    3.  **پیشنهاد کوددهی:** بر اساس این تغییر و ماهیت شاخص، پیشنهاد کلی برای مدیریت کوددهی (به‌ویژه نیتروژن) ارائه دهید.

    نکات: تحلیل فقط بر اساس اطلاعات داده شده باشد. زبان رسمی و قابل فهم. پاسخ کوتاه و متمرکز. پاسخ به زبان فارسی.

    فرمت پاسخ:
    **تحلیل وضعیت:** [توضیح شما]
    **پیشنهاد آبیاری:** [پیشنهاد شما]
    **پیشنهاد کوددهی:** [پیشنهاد شما]
    """
    try:
        response = st.session_state.gemini_model.generate_content(prompt)
        analysis_text = response.text
        if not analysis_text or len(analysis_text) < 50:
            return "مدل هوش مصنوعی پاسخی ارائه نکرد یا پاسخ بسیار کوتاه بود.", None
        return analysis_text, None
    except Exception as e: return None, f"خطا در ارتباط با Gemini API: {e}"

# --- Chatbot Helper Function ---
def extract_farm_name(text, available_farms_list):
    """Simple farm name extraction from text."""
    # Remove "همه مزارع" if present
    farms_to_check = [f for f in available_farms_list if f != "همه مزارع"]
    for farm_name in farms_to_check:
        # Basic check if farm name is in the text (case-insensitive can be added)
        if farm_name in text:
            return farm_name
    return None

# ========================= Main Panel Layout =========================
st.title(APP_TITLE)
st.markdown(f"**مطالعات کاربردی شرکت کشت و صنعت دهخدا** | تاریخ گزارش: {datetime.date.today().strftime('%Y-%m-%d')}")
st.markdown("---")

# --- Display Selected Farm Info ---
selected_farm_details = None
selected_farm_geom = None
selected_farm_geom_json = None

if selected_farm_name == "همه مزارع":
    st.info(f"نمایش اطلاعات کلی برای {len(filtered_farms_df)} مزرعه در روز **{selected_day}**.")
    try:
        min_lon, min_lat = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
        max_lon, max_lat = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
        selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
        selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
    except Exception:
        center_lat = filtered_farms_df['عرض جغرافیایی'].mean()
        center_lon = filtered_farms_df['طول جغرافیایی'].mean()
        selected_farm_geom = ee.Geometry.Point([center_lon, center_lat])
        selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
else:
    selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat = selected_farm_details['عرض جغرافیایی']
    lon = selected_farm_details['طول جغرافیایی']
    selected_farm_geom = ee.Geometry.Point([lon, lat])
    selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
    st.subheader(f"📍 اطلاعات مزرعه: {selected_farm_name}")
    cols = st.columns([1, 1, 1, 2])
    with cols[0]:
        st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', '-'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "-")
        st.metric("واریته", f"{selected_farm_details.get('واریته', '-')}")
    with cols[1]:
        st.metric("کانال", f"{selected_farm_details.get('کانال', '-')}")
        st.metric("سن", f"{selected_farm_details.get('سن', '-')}")
    with cols[2]:
        st.metric("اداره", f"{selected_farm_details.get('اداره', '-')}")
        st.metric("روز آبیاری", f"{selected_farm_details.get('روزهای هفته', '-')}")
    with cols[3]:
        st.markdown("**تصویر کوچک (هفته جاری):**")
        thumb_image_serial, err_img = get_processed_image_gee(selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index)
        if thumb_image_serial:
            thumb_url, err_thumb = get_thumbnail_url(thumb_image_serial, selected_farm_geom_json, vis_params)
            if thumb_url: st.image(thumb_url, caption=f"{selected_index}", width=200)
            elif err_thumb: st.warning(f"خطا Thumbnail: {err_thumb}")
        elif err_img: st.warning(f"خطا تصویر: {err_img}")

# --- Main Content Tabs ---
# Add Chatbot tab
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ نقشه", "📊 جدول رتبه‌بندی", "📈 سری زمانی", " dashboards خلاصه", "💬 چت‌بات"])

with tab1: # Map Tab (Content largely unchanged)
    st.subheader(f"نقشه ماهواره‌ای - شاخص: {selected_index}")
    m = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
    m.add_basemap("HYBRID")
    map_data_placeholder = st.empty()
    if selected_farm_geom_json:
        map_data_placeholder.info("در حال بارگذاری لایه شاخص...")
        gee_image_serial, error_msg_current = get_processed_image_gee(selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index)
        if gee_image_serial:
            try:
                gee_image_current = ee.Image.deserialize(gee_image_serial)
                m.addLayer(gee_image_current, vis_params, f"{selected_index} ({start_date_current_str} to {end_date_current_str})")
                legend_title = f"{selected_index} ({index_props['name']})"
                m.add_legend(legend_title=legend_title, palette=index_props['palette'], min=index_props['min'], max=index_props['max'])
                if selected_farm_name == "همه مزارع":
                    points = filtered_farms_df[['عرض جغرافیایی', 'طول جغرافیایی', 'مزرعه']].to_dict('records')
                    features = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [p['طول جغرافیایی'], p['عرض جغرافیایی']]}, 'properties': {'name': p['مزرعه']}} for p in points]
                    farm_geojson = {'type': 'FeatureCollection', 'features': features}
                    m.add_geojson(farm_geojson, layer_name="مزارع", info_mode='on_hover', style={'color': 'blue', 'fillColor': 'blue', 'opacity': 0.7, 'weight': 1, 'radius': 3})
                    if isinstance(selected_farm_geom, ee.geometry.Geometry): m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM)
                else:
                    folium.Marker(location=[selected_farm_details['عرض جغرافیایی'], selected_farm_details['طول جغرافیایی']], popup=f"<b>{selected_farm_name}</b>", tooltip=selected_farm_name, icon=folium.Icon(color='red', icon='star')).add_to(m)
                    if isinstance(selected_farm_geom, ee.geometry.Geometry): m.center_object(selected_farm_geom, zoom=15)
                m.add_layer_control()
                map_data_placeholder.empty()
                st_folium(m, width=None, height=600, use_container_width=True, key="map_tab1")
            except Exception as map_err: map_data_placeholder.error(f"خطا در نمایش نقشه: {map_err}")
        else: map_data_placeholder.warning(f"تصویری برای نقشه یافت نشد. {error_msg_current}")
    else: map_data_placeholder.warning("موقعیت جغرافیایی تعریف نشده.")

with tab2: # Ranking Table Tab (Content largely unchanged)
    st.subheader(f"جدول رتبه‌بندی مزارع بر اساس {selected_index} ({selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")
    ranking_params = (selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str, selected_day)
    if st.session_state.ranking_data['params'] != ranking_params or st.session_state.ranking_data['df'].empty:
        print(f"Recalculating ranking table for: {ranking_params}")
        st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None} # Clear old data
        ranking_df_raw, calculation_errors = calculate_all_farm_indices(
            filtered_farms_df, selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str)
        st.session_state.ranking_data['df'] = ranking_df_raw
        st.session_state.ranking_data['errors'] = calculation_errors
        st.session_state.ranking_data['params'] = ranking_params
        st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None} # Clear AI cache
        st.rerun() # Rerun to display the newly calculated data immediately
    else:
        print("Using cached ranking data from session state.")
        ranking_df_raw = st.session_state.ranking_data['df']
        calculation_errors = st.session_state.ranking_data['errors']

    if not ranking_df_raw.empty:
        ranking_df_display = ranking_df_raw.copy()
        curr_col = f'{selected_index} (هفته جاری)'
        prev_col = f'{selected_index} (هفته قبل)'
        change_col = 'تغییر'
        ranking_df_display = ranking_df_display.rename(columns={f'{selected_index}_curr': curr_col, f'{selected_index}_prev': prev_col, f'{selected_index}_change': change_col})
        higher_is_better = index_props['higher_is_better']
        def determine_status(change_val):
            try:
                if pd.isna(change_val) or math.isnan(float(change_val)): return "بدون داده"
                change_val = float(change_val)
                if higher_is_better:
                    if change_val > CHANGE_THRESHOLD: return "🟢 بهبود / رشد"
                    elif change_val < -CHANGE_THRESHOLD: return "🔴 کاهش / تنش"
                    else: return "⚪ ثابت"
                else:
                    if change_val < -CHANGE_THRESHOLD: return "🟢 بهبود / رشد"
                    elif change_val > CHANGE_THRESHOLD: return "🔴 کاهش / تنش"
                    else: return "⚪ ثابت"
            except (TypeError, ValueError): return "خطا در مقدار"

        ranking_df_display['وضعیت'] = ranking_df_display[change_col].apply(determine_status)
        ranking_df_sorted = ranking_df_display.sort_values(by=curr_col, ascending=not higher_is_better, na_position='last').reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'
        cols_to_format = [curr_col, prev_col, change_col]
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("-" if pd.isna(x) else x))
        st.dataframe(ranking_df_sorted[['مزرعه', 'کانال', 'اداره', curr_col, prev_col, change_col, 'وضعیت']], use_container_width=True, height=400)
        try:
            csv_data = ranking_df_sorted.to_csv(index=True, encoding='utf-8-sig')
            st.download_button(label="📥 دانلود جدول (CSV)", data=csv_data, file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv')
        except Exception as e: st.error(f"خطا در ایجاد فایل دانلود: {e}")
        if calculation_errors:
            with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها", expanded=False):
                unique_errors = sorted(list(set(calculation_errors)))
                st.warning(f"تعداد کل خطاها: {len(calculation_errors)} (نمایش موارد منحصربفرد)")
                for i, error in enumerate(unique_errors):
                    st.error(f"- {error}")
                    if i > 15: st.warning(f"... و {len(unique_errors) - i} خطای منحصربفرد دیگر."); break
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی {selected_index} یافت نشد یا محاسبه نشد.")
        if calculation_errors: st.error("خطاهایی در حین تلاش برای محاسبه رخ داده است (جزئیات در بالا).")

with tab3: # Time Series Tab (Content largely unchanged)
    st.subheader(f"نمودار روند زمانی شاخص {selected_index}")
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید.")
    elif selected_farm_geom_json:
        ts_end_date = today.strftime('%Y-%m-%d')
        ts_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        ts_df_json, ts_error = get_index_time_series_data(selected_farm_geom_json, selected_index, ts_start_date, ts_end_date)
        if ts_error: st.warning(f"خطا در دریافت سری زمانی: {ts_error}")
        elif ts_df_json:
            try:
                ts_df = pd.read_json(ts_df_json, orient='split')
                ts_df.index = pd.to_datetime(ts_df.index, format='iso')
                if not ts_df.empty:
                    fig_ts = px.line(ts_df, y=selected_index, markers=True, title=f"روند زمانی {selected_index} برای مزرعه {selected_farm_name}", labels={'index': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                    fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                    st.plotly_chart(fig_ts, use_container_width=True)
                    csv_ts = ts_df.to_csv(encoding='utf-8-sig')
                    st.download_button(label="📥 دانلود داده‌های سری زمانی (CSV)", data=csv_ts, file_name=f'timeseries_{selected_farm_name}_{selected_index}.csv', mime='text/csv')
                else: st.info(f"داده معتبری برای نمودار سری زمانی {selected_index} یافت نشد.")
            except Exception as e_plot: st.error(f"خطا در رسم نمودار سری زمانی: {e_plot}")
        else: st.info(f"داده‌ای برای سری زمانی {selected_index} یافت نشد.")
    else: st.warning("موقعیت جغرافیایی مزرعه نامشخص است.")

with tab4: # Dashboard Tab (Content largely unchanged)
    st.subheader(f"داشبورد خلاصه وضعیت روزانه ({selected_day}) - شاخص: {selected_index}")
    ranking_df_raw = st.session_state.ranking_data.get('df')
    if ranking_df_raw is None or ranking_df_raw.empty:
        st.warning(f"داده‌های رتبه‌بندی برای {selected_day} و {selected_index} محاسبه نشده یا خالی است. لطفاً ابتدا به تب 'جدول رتبه‌بندی' بروید.")
    else:
        df_dash = ranking_df_raw.copy()
        curr_col_raw = f'{selected_index}_curr'
        prev_col_raw = f'{selected_index}_prev'
        change_col_raw = f'{selected_index}_change'
        df_dash[curr_col_raw] = pd.to_numeric(df_dash[curr_col_raw], errors='coerce')
        df_dash[prev_col_raw] = pd.to_numeric(df_dash[prev_col_raw], errors='coerce')
        df_dash[change_col_raw] = pd.to_numeric(df_dash[change_col_raw], errors='coerce')
        higher_is_better = index_props['higher_is_better']
        def get_status_dash(change):
            try:
                if pd.isna(change) or math.isnan(change): return "بدون داده"
                if higher_is_better:
                    if change > CHANGE_THRESHOLD: return "بهبود"
                    elif change < -CHANGE_THRESHOLD: return "کاهش"
                    else: return "ثابت"
                else:
                    if change < -CHANGE_THRESHOLD: return "بهبود"
                    elif change > CHANGE_THRESHOLD: return "کاهش"
                    else: return "ثابت"
            except: return "خطا"
        df_dash['status'] = df_dash[change_col_raw].apply(get_status_dash)
        status_counts = df_dash['status'].value_counts()
        st.markdown("**آمار کلی وضعیت مزارع:**")
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("🟢 بهبود", status_counts.get("بهبود", 0))
        with col2: st.metric("⚪ ثابت", status_counts.get("ثابت", 0))
        with col3: st.metric("🔴 کاهش", status_counts.get("کاهش", 0))
        with col4: st.metric("⚫️ بدون داده", status_counts.get("بدون داده", 0) + status_counts.get("خطا", 0))
        st.markdown("---")
        col_plot1, col_plot2 = st.columns(2)
        with col_plot1:
            st.markdown(f"**توزیع مقادیر {selected_index} (هفته جاری)**")
            hist_data = df_dash[curr_col_raw].dropna()
            if not hist_data.empty:
                fig_hist = px.histogram(hist_data, nbins=20, title=f"توزیع {selected_index}", labels={'value': f'مقدار {selected_index}'})
                fig_hist.update_layout(yaxis_title="تعداد مزارع", xaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                st.plotly_chart(fig_hist, use_container_width=True)
            else: st.info("داده‌ای برای هیستوگرام نیست.")
        with col_plot2:
            st.markdown("**مقایسه مقادیر هفته جاری و قبل**")
            scatter_data = df_dash.dropna(subset=[curr_col_raw, prev_col_raw, 'status'])
            if not scatter_data.empty:
                fig_scatter = px.scatter(scatter_data, x=prev_col_raw, y=curr_col_raw, color='status', hover_name='مزرعه', title=f"مقایسه {selected_index}", labels={prev_col_raw: f"{selected_index} (قبل)", curr_col_raw: f"{selected_index} (جاری)", 'status': 'وضعیت'}, color_discrete_map={'بهبود': 'green', 'ثابت': 'grey', 'کاهش': 'red', 'بدون داده': 'black', 'خطا':'orange'})
                min_val_sc = min(scatter_data[prev_col_raw].min(), scatter_data[curr_col_raw].min())
                max_val_sc = max(scatter_data[prev_col_raw].max(), scatter_data[curr_col_raw].max())
                fig_scatter.add_shape(type='line', x0=min_val_sc, y0=min_val_sc, x1=max_val_sc, y1=max_val_sc, line=dict(color='rgba(0,0,0,0.5)', dash='dash'))
                fig_scatter.update_layout(xaxis_title=f"{selected_index} (قبل)", yaxis_title=f"{selected_index} (جاری)", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                st.plotly_chart(fig_scatter, use_container_width=True)
            else: st.info("داده‌ای برای نمودار پراکندگی نیست.")
        st.markdown("---")
        st.markdown("**عملکرد مزارع (بر اساس مقدار هفته جاری):**")
        df_sorted_dash = df_dash.sort_values(by=curr_col_raw, ascending=not higher_is_better, na_position='last').dropna(subset=[curr_col_raw])
        col_top, col_bottom = st.columns(2)
        with col_top:
            st.markdown(f"**🟢 ۵ مزرعه برتر**")
            st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].head(5).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}"}), use_container_width=True)
        with col_bottom:
            st.markdown(f"**🔴 ۵ مزرعه ضعیف‌تر**")
            st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].tail(5).sort_values(by=curr_col_raw, ascending=not higher_is_better).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}"}), use_container_width=True)

with tab5: # Chatbot Tab
    st.subheader("💬 چت‌بات تحلیل وضعیت مزارع")
    st.info(f"می‌توانید در مورد وضعیت یک مزرعه خاص برای روز **{selected_day}** و با توجه به شاخص **{selected_index}** سوال بپرسید. مثال: 'وضعیت مزرعه فلان چگونه است؟'")
    st.warning("توجه: پاسخ چت‌بات بر اساس داده‌هایی است که در تب 'جدول رتبه‌بندی' محاسبه شده است. اگر داده‌ها محاسبه نشده باشند، پاسخی ارائه نخواهد شد.", icon="⚠️")

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input(f"در مورد وضعیت مزارع برای روز {selected_day} بپرسید..."):
        # Display user message in chat message container
        with st.chat_message("user"):
            st.markdown(prompt)
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})

        # --- Bot Response Logic ---
        response = "متاسفم، نتوانستم درخواست شما را پردازش کنم." # Default response
        extracted_farm = extract_farm_name(prompt, available_farm_names_today)

        if not st.session_state.gemini_available:
            response = "متاسفم، سرویس هوش مصنوعی در حال حاضر در دسترس نیست."
        elif extracted_farm:
            # Check if ranking data is available
            ranking_df = st.session_state.ranking_data.get('df')
            if ranking_df is None or ranking_df.empty:
                response = f"داده‌های شاخص {selected_index} برای روز {selected_day} هنوز محاسبه نشده‌اند. لطفاً ابتدا به تب 'جدول رتبه‌بندی' مراجعه کنید تا محاسبات انجام شود و سپس سوال خود را مجدداً بپرسید."
            else:
                farm_data_row = ranking_df[ranking_df['مزرعه'] == extracted_farm]
                if not farm_data_row.empty:
                    farm_row = farm_data_row.iloc[0]
                    current_val = farm_row.get(f'{selected_index}_curr')
                    previous_val = farm_row.get(f'{selected_index}_prev')
                    change_val = farm_row.get(f'{selected_index}_change')

                    # Call Gemini for analysis
                    analysis_text, analysis_error = get_gemini_analysis(
                        selected_index, extracted_farm, current_val, previous_val, change_val
                    )

                    if analysis_error:
                        response = f"خطایی در تولید تحلیل برای مزرعه {extracted_farm} رخ داد: {analysis_error}"
                    elif analysis_text:
                        response = f"**تحلیل وضعیت مزرعه {extracted_farm} (بر اساس شاخص {selected_index} برای روز {selected_day}):**\n\n{analysis_text}"
                    else:
                         # Handle case where AI didn't return text but no specific error
                         response = f"متاسفانه تحلیل مشخصی برای وضعیت مزرعه {extracted_farm} با داده‌های موجود تولید نشد. ممکن است داده‌ها کافی نباشند."

                else:
                    # This case might happen if the farm name exists but somehow wasn't in the calculated results
                    response = f"داده‌های محاسبه‌شده برای مزرعه '{extracted_farm}' در نتایج جدول رتبه‌بندی یافت نشد. لطفاً از صحت محاسبات در تب مربوطه اطمینان حاصل کنید."
        else:
            # Could not extract a known farm name
            response = "متاسفم، نام مزرعه معتبری در سوال شما تشخیص داده نشد. لطفاً نام یکی از مزارع موجود برای این روز را ذکر کنید:\n"
            response += ", ".join([f for f in available_farm_names_today if f != "همه مزارع"][:10]) # Show some examples
            if len(available_farm_names_today) > 11: response += "..."


        # Display assistant response in chat message container
        with st.chat_message("assistant"):
            st.markdown(response)
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})


# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط اسماعیل کیانی")
st.sidebar.markdown("Streamlit | GEE | Geemap | Plotly | Gemini")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY": st.sidebar.error("🚨 کلید API Gemini ارائه نشده است.")
elif st.session_state.gemini_available: st.sidebar.success("✅ Gemini API فعال است.")
else: st.sidebar.warning("⚠️ Gemini API غیرفعال است.")
st.sidebar.warning("هشدار امنیتی: کلید API در کد قرار دارد.")

# --- END OF FILE ---
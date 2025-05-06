# --- START OF FILE app_chatbot_v2.py ---

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
GEMINI_API_KEY = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- PASTE YOUR KEY HERE

# --- Constants ---
APP_TITLE = "سامانه پایش هوشمند نیشکر (نسخه چت‌بات اصلاح شده)"
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

# --- Page Config and CSS (unchanged) ---
st.set_page_config(page_title=APP_TITLE, page_icon="🌾", layout="wide")
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        body, .main, button, input, textarea, select, .stTextInput, .stSelectbox, .stDateInput, .stButton>button, .stTabs [data-baseweb="tab"], .stMetric, .stDataFrame, .stPlotlyChart, .stChatMessage {
            font-family: 'Vazirmatn', sans-serif !important; direction: rtl;
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
        .stChatMessage[data-testid="chatAvatarIcon-user"] + div { order: 1; }
        .stChatMessage[data-testid="chatAvatarIcon-assistant"] + div { order: -1; }
        .stChatMessage div[data-testid="stChatMessageContent"] p { text-align: right; }
    </style>
""", unsafe_allow_html=True)

# --- Initialize Session State (unchanged) ---
if 'gee_initialized' not in st.session_state: st.session_state.gee_initialized = False
if 'farm_data' not in st.session_state: st.session_state.farm_data = None
if 'ranking_data' not in st.session_state: st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}
if 'gemini_analysis' not in st.session_state: st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None}
if 'gemini_available' not in st.session_state: st.session_state.gemini_available = False
if 'gemini_model' not in st.session_state: st.session_state.gemini_model = None
if "messages" not in st.session_state: st.session_state.messages = []

# --- GEE and Gemini Initialization (unchanged) ---
@st.cache_resource
def initialize_gee():
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE): st.error(f"'{SERVICE_ACCOUNT_FILE}' یافت نشد."); return False
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized."); return True
    except Exception as e: st.error(f"GEE Init Error: {e}"); return False

@st.cache_resource
def configure_gemini():
    try:
        if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY": print("Gemini Key missing."); return None, False
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        print("Gemini Configured."); return model, True
    except Exception as e: print(f"Gemini Config Error: {e}"); st.warning(f"Gemini API Error: {e}"); return None, False

if not st.session_state.gee_initialized:
    st.session_state.gee_initialized = initialize_gee()
    if not st.session_state.gee_initialized: st.stop()

if st.session_state.gemini_model is None:
     st.session_state.gemini_model, st.session_state.gemini_available = configure_gemini()

# --- Load Farm Data (unchanged) ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    try:
        df = pd.read_csv(csv_path)
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols): st.error(f"CSV فاقد ستون: {required_cols}"); return None
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool)
        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
        df = df[~df['coordinates_missing']]
        if df.empty: st.warning("داده معتبر مزرعه نیست."); return None
        df['روزهای هفته'] = df['روزهای هفته'].astype(str).str.strip()
        df['farm_id'] = df['مزرعه'] + '_' + df['طول جغرافیایی'].astype(str) + '_' + df['عرض جغرافیایی'].astype(str)
        print(f"Farm data loaded: {len(df)} farms."); return df
    except FileNotFoundError: st.error(f"'{csv_path}' یافت نشد."); return None
    except Exception as e: st.error(f"CSV Load Error: {e}"); st.error(traceback.format_exc()); return None

if st.session_state.farm_data is None: st.session_state.farm_data = load_farm_data()
if st.session_state.farm_data is None: st.stop()

# ========================= Sidebar Inputs (unchanged) =========================
st.sidebar.header("⚙️ تنظیمات نمایش")
available_days = sorted(st.session_state.farm_data['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox("📅 روز هفته:", options=available_days, index=available_days.index("شنبه") if "شنبه" in available_days else 0, key='sd_key')
filtered_farms_df = st.session_state.farm_data[st.session_state.farm_data['روزهای هفته'] == selected_day].copy()
if filtered_farms_df.empty: st.warning(f"مزرعه‌ای برای '{selected_day}' نیست."); st.stop()
available_farm_names_today = ["همه مزارع"] + sorted(filtered_farms_df['مزرعه'].unique())
selected_farm_name = st.sidebar.selectbox("🌾 انتخاب مزرعه:", options=available_farm_names_today, index=0, key='sf_key')
selected_index = st.sidebar.selectbox("📈 انتخاب شاخص:", options=list(INDEX_INFO.keys()), format_func=lambda x: f"{x} ({INDEX_INFO[x]['name']})", index=0, key='si_key')
index_props = INDEX_INFO[selected_index]
vis_params = {'min': index_props['min'], 'max': index_props['max'], 'palette': index_props['palette']}
today_date = datetime.date.today() # Renamed to avoid conflict
persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_ago = (today_date.weekday() - target_weekday + 7) % 7
    end_date_current = today_date - datetime.timedelta(days=days_ago) if days_ago != 0 else today_date
    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)
    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')
    st.sidebar.info(f"🗓️ بازه فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"🗓️ بازه قبلی: {start_date_previous_str} تا {end_date_previous_str}")
except KeyError: st.sidebar.error(f"روز '{selected_day}' نامعتبر."); st.stop()
except Exception as e: st.sidebar.error(f"خطا بازه زمانی: {e}"); st.stop()

# ========================= GEE Functions (REVISED) =========================
# These functions now operate on and return ee.Image objects directly for server-side chaining.
# Caching is still applied to the logic of these functions.
@st.cache_data(persist="disk") # Cache the function logic
def maskS2clouds_ee(image: ee.Image) -> ee.Image:
    """Masks clouds in a Sentinel-2 SR image using the QA band and SCL. Operates on ee.Image."""
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    good_quality = scl.remap([4, 5, 6], [1, 1, 1], 0) # Keep Veg, Bare Soil, Water
    # Scale optical bands (Needed for index calculations)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality)

@st.cache_data(persist="disk") # Cache the function logic
def add_indices_ee(image: ee.Image) -> ee.Image:
    """Calculates and adds NDVI, NDWI, NDRE, LAI, CHL bands. Operates on ee.Image."""
    try:
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = image.normalizedDifference(['B8', 'B11']).rename('NDWI')
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        lai = ndvi.multiply(3.5).rename('LAI') # Simple empirical estimation
        re1_safe = image.select('B5').max(ee.Image(0.0001)) # Add small epsilon
        chl = image.expression('(NIR / RE1) - 1', {'NIR': image.select('B8'), 'RE1': re1_safe}).rename('CHL')
        return image.addBands([ndvi, ndwi, ndre, lai, chl])
    except Exception as e:
        # If an error occurs (e.g., missing band), return the image without added indices
        # This error should ideally be caught by GEE during computation.
        print(f"Warning: Could not calculate indices for an image: {e}")
        return image # Return original image if calculation fails

# This function fetches and processes the image collection, then serializes the final image.
@st.cache_data(ttl=3600, show_spinner=False, persist="disk")
def get_processed_image_serialized(_geometry_json, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite.
    Input geometry as JSON, returns final Image serialized or error string.
    """
    _geometry = ee.Geometry(json.loads(_geometry_json))
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds_ee) # Apply cloud masking (server-side)
                     .map(add_indices_ee))  # Calculate indices (server-side)

        # Check if any images are available after filtering and processing
        count = s2_sr_col.size().getInfo() # getInfo() here to check count
        if count == 0:
            return None, f"No valid Sentinel-2 images found after processing for {start_date} to {end_date}."

        # Create a median composite image
        # Select all known indices before median to ensure availability if one is chosen later
        median_image = s2_sr_col.select(list(INDEX_INFO.keys())).median()

        # Final check if the specific index exists after median
        # This requires getInfo(), defer if possible or make it optional for performance
        # For now, we assume if processing was fine, index should be there.
        # band_names = median_image.bandNames().getInfo()
        # if index_name not in band_names:
        #      return None, f"Index '{index_name}' not present in final median. Available: {band_names}"

        output_image = median_image.select(index_name)

        # Serialize the GEE Image object for caching
        return output_image.serialize(), None

    except ee.EEException as e:
        error_message = f"GEE Error in get_processed_image: {e}"
        return None, error_message
    except Exception as e:
        error_message = f"Unknown Error in get_processed_image: {e}\n{traceback.format_exc()}"
        return None, error_message

# --- Function to get thumbnail URL (unchanged, uses serialized image) ---
@st.cache_data(ttl=3600, show_spinner="در حال تولید تصویر کوچک...")
def get_thumbnail_url(_image_serialized, _geometry_json, _vis_params):
    if not _image_serialized: return None, "No image data for thumbnail."
    try:
        image = ee.Image.deserialize(_image_serialized) # Deserialize here
        geometry = ee.Geometry(json.loads(_geometry_json))
        thumb_url = image.getThumbURL({'region': geometry.buffer(500).bounds(), 'dimensions': 256, 'params': _vis_params, 'format': 'png'})
        return thumb_url, None
    except Exception as e: return None, f"Thumbnail Error: {e}"

# --- Function to get time series (REVISED) ---
@st.cache_data(ttl=3600, show_spinner="در حال دریافت سری زمانی...")
def get_index_time_series_data(_point_geom_json, index_name, start_date, end_date):
    _point_geom = ee.Geometry(json.loads(_point_geom_json))
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds_ee) # Server-side
                     .map(add_indices_ee))  # Server-side

        # Filter for images that actually have the index band after processing
        # This requires checking band names, which ideally happens on server if possible
        # For simplicity, we'll assume add_indices_ee handles this or rely on reduceRegion failure
        # A more robust filter: .filter(ee.Filter.listContains('system:band_names', index_name))

        def extract_value(image: ee.Image):
            # Ensure the image has the band before reducing (robustness)
            # This check is client-side after a map, so might be slow or better done differently
            # value = ee.Algorithms.If(image.bandNames().contains(index_name),
            #                         image.select(index_name).reduceRegion(reducer=ee.Reducer.first(), geometry=_point_geom, scale=10).get(index_name),
            #                         None) # Or some other placeholder
            value = image.select(index_name).reduceRegion(reducer=ee.Reducer.first(), geometry=_point_geom, scale=10).get(index_name)
            img_date = ee.Date(image.get('system:time_start')).format('YYYY-MM-dd')
            return ee.Feature(None, {'date': img_date, index_name: value})

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features'] # getInfo() to bring data to client

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

# --- Function to calculate indices for ranking table (REVISED) ---
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
            point_geom_json = json.dumps(point_geom.getInfo()) # Serialize for cached function
            status_text.text(f"پردازش مزرعه {i+1}/{total_farms}: {farm_name}")

            def get_mean_value_from_serialized(geom_json, start, end, idx_name):
                image_serialized, error_img = get_processed_image_serialized(geom_json, start, end, idx_name) # Use revised function
                if image_serialized:
                    try:
                        image = ee.Image.deserialize(image_serialized) # Deserialize GEE object
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=ee.Geometry(json.loads(geom_json)), # Recreate geometry for reduceRegion
                            scale=10
                        ).getInfo() # Get the result
                        val = mean_dict.get(idx_name) if mean_dict else None
                        if val is None and mean_dict is not None: return None, f"'{idx_name}' not in reduceRegion."
                        elif val is None: return None, "ReduceRegion no result."
                        return val, None
                    except ee.EEException as e_reduce: return None, f"GEE Error in reduceRegion: {e_reduce}"
                    except Exception as e_other: return None, f"Unknown Error in reduceRegion: {e_other}"
                else: return None, error_img or "Image not found for processing."

            current_val, err_curr = get_mean_value_from_serialized(point_geom_json, start_curr, end_curr, index_name)
            if err_curr: errors.append(f"{farm_name} (Current): {err_curr}")
            previous_val, err_prev = get_mean_value_from_serialized(point_geom_json, start_prev, end_prev, index_name)
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
    if not st.session_state.gemini_available or st.session_state.gemini_model is None: return "AI API Error.", None
    try:
        if pd.isna(_current_val) or pd.isna(_previous_val) or pd.isna(_change_val) or \
           math.isnan(float(_current_val)) or math.isnan(float(_previous_val)) or math.isnan(float(_change_val)):
            return "داده نامعتبر برای تحلیل.", None
    except (TypeError, ValueError): return "داده ورودی نامعتبر.", None
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
        if not analysis_text or len(analysis_text) < 50: return "AI پاسخ کوتاه داد.", None
        return analysis_text, None
    except Exception as e: return None, f"Gemini API Error: {e}"

# --- Chatbot Helper Function (unchanged) ---
def extract_farm_name(text, available_farms_list):
    farms_to_check = [f for f in available_farms_list if f != "همه مزارع"]
    for farm_name in farms_to_check:
        if farm_name in text: return farm_name
    return None

# ========================= Main Panel Layout (Map Tab REVISED for deserialization) =========================
st.title(APP_TITLE)
st.markdown(f"**مطالعات کاربردی شرکت کشت و صنعت دهخدا** | تاریخ گزارش: {datetime.date.today().strftime('%Y-%m-%d')}")
st.markdown("---")

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
    except Exception: # Fallback
        center_lat = filtered_farms_df['عرض جغرافیایی'].mean(); center_lon = filtered_farms_df['طول جغرافیایی'].mean()
        selected_farm_geom = ee.Geometry.Point([center_lon, center_lat]); selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
else:
    selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat = selected_farm_details['عرض جغرافیایی']; lon = selected_farm_details['طول جغرافیایی']
    selected_farm_geom = ee.Geometry.Point([lon, lat]); selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
    st.subheader(f"📍 اطلاعات مزرعه: {selected_farm_name}")
    cols = st.columns([1, 1, 1, 2])
    with cols[0]: st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', '-'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "-"); st.metric("واریته", f"{selected_farm_details.get('واریته', '-')}")
    with cols[1]: st.metric("کانال", f"{selected_farm_details.get('کانال', '-')}"); st.metric("سن", f"{selected_farm_details.get('سن', '-')}")
    with cols[2]: st.metric("اداره", f"{selected_farm_details.get('اداره', '-')}"); st.metric("روز آبیاری", f"{selected_farm_details.get('روزهای هفته', '-')}")
    with cols[3]:
        st.markdown("**تصویر کوچک (هفته جاری):**")
        if selected_farm_geom_json: # Ensure geometry is available
            thumb_image_serial, err_img = get_processed_image_serialized(selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index)
            if thumb_image_serial:
                thumb_url, err_thumb = get_thumbnail_url(thumb_image_serial, selected_farm_geom_json, vis_params)
                if thumb_url: st.image(thumb_url, caption=f"{selected_index}", width=200)
                elif err_thumb: st.warning(f"خطا Thumbnail: {err_thumb}")
            elif err_img: st.warning(f"خطا تصویر: {err_img}")
        else: st.warning("موقعیت برای تصویر کوچک نیست.")


tab1, tab2, tab3, tab4, tab5 = st.tabs(["🗺️ نقشه", "📊 جدول رتبه‌بندی", "📈 سری زمانی", " dashboards خلاصه", "💬 چت‌بات"])

with tab1:
    st.subheader(f"نقشه ماهواره‌ای - شاخص: {selected_index}")
    m = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
    m.add_basemap("HYBRID")
    map_data_placeholder = st.empty()
    if selected_farm_geom_json:
        map_data_placeholder.info("در حال بارگذاری لایه شاخص...")
        # Use the REVISED function that returns serialized image
        gee_image_serialized, error_msg_current = get_processed_image_serialized(
            selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index
        )
        if gee_image_serialized:
            try:
                gee_image_current = ee.Image.deserialize(gee_image_serialized) # Deserialize for map
                m.addLayer(gee_image_current, vis_params, f"{selected_index} ({start_date_current_str} to {end_date_current_str})")
                legend_title = f"{selected_index} ({index_props['name']})"
                m.add_legend(legend_title=legend_title, palette=index_props['palette'], min=index_props['min'], max=index_props['max']) # Geemap legend
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
                st_folium(m, width=None, height=600, use_container_width=True, key="map_tab_main")
            except Exception as map_err: map_data_placeholder.error(f"خطا نمایش نقشه: {map_err}\n{traceback.format_exc()}")
        else: map_data_placeholder.warning(f"تصویر نقشه نیست. {error_msg_current}")
    else: map_data_placeholder.warning("موقعیت نقشه نیست.")

# --- Ranking Table Tab (Tab 2 - Logic largely unchanged, relies on calculate_all_farm_indices) ---
with tab2:
    st.subheader(f"جدول رتبه‌بندی مزارع بر اساس {selected_index} ({selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")
    ranking_params = (selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str, selected_day)
    if st.session_state.ranking_data['params'] != ranking_params or st.session_state.ranking_data['df'].empty:
        print(f"Recalculating ranking table for: {ranking_params}")
        st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}
        with st.spinner(f"در حال محاسبه شاخص {selected_index} برای همه مزارع... این ممکن است چند دقیقه طول بکشد."):
            ranking_df_raw, calculation_errors = calculate_all_farm_indices(
                filtered_farms_df, selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str)
        st.session_state.ranking_data['df'] = ranking_df_raw
        st.session_state.ranking_data['errors'] = calculation_errors
        st.session_state.ranking_data['params'] = ranking_params
        st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None}
        st.rerun() # Rerun to ensure new data is used by other tabs
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
        def determine_status_tab2(change_val): # Renamed to avoid conflict
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
        ranking_df_display['وضعیت'] = ranking_df_display[change_col].apply(determine_status_tab2)
        ranking_df_sorted = ranking_df_display.sort_values(by=curr_col, ascending=not higher_is_better, na_position='last').reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1; ranking_df_sorted.index.name = 'رتبه'
        cols_to_format = [curr_col, prev_col, change_col]
        for col_name in cols_to_format: # Renamed loop variable
            if col_name in ranking_df_sorted.columns:
                ranking_df_sorted[col_name] = ranking_df_sorted[col_name].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("-" if pd.isna(x) else x))
        st.dataframe(ranking_df_sorted[['مزرعه', 'کانال', 'اداره', curr_col, prev_col, change_col, 'وضعیت']], use_container_width=True, height=400)
        try:
            csv_data = ranking_df_sorted.to_csv(index=True, encoding='utf-8-sig')
            st.download_button("📥 دانلود جدول (CSV)", data=csv_data, file_name=f'ranking_{selected_index}_{selected_day}.csv', mime='text/csv')
        except Exception as e: st.error(f"خطا دانلود: {e}")
        if calculation_errors:
            with st.expander("⚠️ خطاهای محاسبه", expanded=False):
                unique_errors = sorted(list(set(calculation_errors)))
                st.warning(f"کل خطاها: {len(calculation_errors)}")
                for i, error in enumerate(unique_errors): st.error(f"- {error}");
                if i > 15: st.warning("..."); break
    else:
        st.info(f"داده رتبه‌بندی {selected_index} نیست.")
        if calculation_errors: st.error("خطا در محاسبه (بالا).")

# --- Time Series Tab (Tab 3 - Logic largely unchanged) ---
with tab3:
    st.subheader(f"نمودار روند زمانی شاخص {selected_index}")
    if selected_farm_name == "همه مزارع": st.info("یک مزرعه انتخاب کنید.")
    elif selected_farm_geom_json:
        ts_end_date = today_date.strftime('%Y-%m-%d'); ts_start_date = (today_date - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
        ts_df_json, ts_error = get_index_time_series_data(selected_farm_geom_json, selected_index, ts_start_date, ts_end_date)
        if ts_error: st.warning(f"خطا سری زمانی: {ts_error}")
        elif ts_df_json:
            try:
                ts_df = pd.read_json(ts_df_json, orient='split'); ts_df.index = pd.to_datetime(ts_df.index, format='iso')
                if not ts_df.empty:
                    fig_ts = px.line(ts_df, y=selected_index, markers=True, title=f"روند {selected_index} برای {selected_farm_name}", labels={'index': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                    fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                    st.plotly_chart(fig_ts, use_container_width=True)
                    csv_ts = ts_df.to_csv(encoding='utf-8-sig')
                    st.download_button("📥 دانلود داده سری زمانی (CSV)", data=csv_ts, file_name=f'ts_{selected_farm_name}_{selected_index}.csv', mime='text/csv')
                else: st.info(f"داده معتبر سری زمانی {selected_index} نیست.")
            except Exception as e_plot: st.error(f"خطا رسم نمودار: {e_plot}")
        else: st.info(f"داده سری زمانی {selected_index} نیست.")
    else: st.warning("موقعیت مزرعه نیست.")

# --- Dashboard Tab (Tab 4 - Logic largely unchanged) ---
with tab4:
    st.subheader(f"داشبورد خلاصه وضعیت روزانه ({selected_day}) - شاخص: {selected_index}")
    ranking_df_raw_dash = st.session_state.ranking_data.get('df') # Renamed for clarity
    if ranking_df_raw_dash is None or ranking_df_raw_dash.empty: st.warning(f"داده رتبه‌بندی برای {selected_day} و {selected_index} نیست. به تب 'جدول رتبه‌بندی' بروید.")
    else:
        df_dash = ranking_df_raw_dash.copy()
        curr_col_raw = f'{selected_index}_curr'; prev_col_raw = f'{selected_index}_prev'; change_col_raw = f'{selected_index}_change'
        df_dash[curr_col_raw] = pd.to_numeric(df_dash[curr_col_raw], errors='coerce')
        df_dash[prev_col_raw] = pd.to_numeric(df_dash[prev_col_raw], errors='coerce')
        df_dash[change_col_raw] = pd.to_numeric(df_dash[change_col_raw], errors='coerce')
        higher_is_better_dash = index_props['higher_is_better'] # Renamed
        def get_status_dashboard(change): # Renamed
            try:
                if pd.isna(change) or math.isnan(change): return "بدون داده"
                if higher_is_better_dash:
                    if change > CHANGE_THRESHOLD: return "بهبود"
                    elif change < -CHANGE_THRESHOLD: return "کاهش"
                    else: return "ثابت"
                else:
                    if change < -CHANGE_THRESHOLD: return "بهبود"
                    elif change > CHANGE_THRESHOLD: return "کاهش"
                    else: return "ثابت"
            except: return "خطا"
        df_dash['status'] = df_dash[change_col_raw].apply(get_status_dashboard)
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
            else: st.info("داده هیستوگرام نیست.")
        with col_plot2:
            st.markdown("**مقایسه مقادیر هفته جاری و قبل**")
            scatter_data = df_dash.dropna(subset=[curr_col_raw, prev_col_raw, 'status'])
            if not scatter_data.empty:
                fig_scatter = px.scatter(scatter_data, x=prev_col_raw, y=curr_col_raw, color='status', hover_name='مزرعه', title=f"مقایسه {selected_index}", labels={prev_col_raw: f"{selected_index} (قبل)", curr_col_raw: f"{selected_index} (جاری)", 'status': 'وضعیت'}, color_discrete_map={'بهبود': 'green', 'ثابت': 'grey', 'کاهش': 'red', 'بدون داده': 'black', 'خطا':'orange'})
                min_val_sc = min(scatter_data[prev_col_raw].min(), scatter_data[curr_col_raw].min()) if not scatter_data.empty else 0
                max_val_sc = max(scatter_data[prev_col_raw].max(), scatter_data[curr_col_raw].max()) if not scatter_data.empty else 1
                fig_scatter.add_shape(type='line', x0=min_val_sc, y0=min_val_sc, x1=max_val_sc, y1=max_val_sc, line=dict(color='rgba(0,0,0,0.5)', dash='dash'))
                fig_scatter.update_layout(xaxis_title=f"{selected_index} (قبل)", yaxis_title=f"{selected_index} (جاری)", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                st.plotly_chart(fig_scatter, use_container_width=True)
            else: st.info("داده نمودار پراکندگی نیست.")
        st.markdown("---")
        st.markdown("**عملکرد مزارع (بر اساس مقدار هفته جاری):**")
        df_sorted_dash = df_dash.sort_values(by=curr_col_raw, ascending=not higher_is_better_dash, na_position='last').dropna(subset=[curr_col_raw])
        col_top, col_bottom = st.columns(2)
        with col_top: st.markdown(f"**🟢 ۵ مزرعه برتر**"); st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].head(5).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}"}), use_container_width=True)
        with col_bottom: st.markdown(f"**🔴 ۵ مزرعه ضعیف‌تر**"); st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].tail(5).sort_values(by=curr_col_raw, ascending=not higher_is_better_dash).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}"}), use_container_width=True)

# --- Chatbot Tab (Tab 5 - Logic largely unchanged) ---
with tab5:
    st.subheader("💬 چت‌بات تحلیل وضعیت مزارع")
    st.info(f"در مورد وضعیت یک مزرعه خاص برای روز **{selected_day}** و با شاخص **{selected_index}** بپرسید. مثال: 'وضعیت مزرعه نیشکر ۱ چگونه است؟'")
    st.warning("توجه: پاسخ چت‌بات به داده‌های محاسبه‌شده در تب 'جدول رتبه‌بندی' وابسته است.", icon="⚠️")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    if prompt := st.chat_input(f"در مورد مزارع برای {selected_day} بپرسید..."):
        with st.chat_message("user"): st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        response = "متاسفم، پردازش نشد."
        extracted_farm = extract_farm_name(prompt, available_farm_names_today)
        if not st.session_state.gemini_available: response = "AI در دسترس نیست."
        elif extracted_farm:
            ranking_df_chat = st.session_state.ranking_data.get('df') # Renamed
            if ranking_df_chat is None or ranking_df_chat.empty: response = f"داده {selected_index} برای {selected_day} محاسبه نشده. به تب 'جدول رتبه‌بندی' بروید."
            else:
                farm_data_row_chat = ranking_df_chat[ranking_df_chat['مزرعه'] == extracted_farm] # Renamed
                if not farm_data_row_chat.empty:
                    farm_row_chat = farm_data_row_chat.iloc[0] # Renamed
                    current_val = farm_row_chat.get(f'{selected_index}_curr')
                    previous_val = farm_row_chat.get(f'{selected_index}_prev')
                    change_val = farm_row_chat.get(f'{selected_index}_change')
                    analysis_text, analysis_error = get_gemini_analysis(selected_index, extracted_farm, current_val, previous_val, change_val)
                    if analysis_error: response = f"خطا تحلیل {extracted_farm}: {analysis_error}"
                    elif analysis_text: response = f"**تحلیل {extracted_farm} ({selected_index} برای {selected_day}):**\n\n{analysis_text}"
                    else: response = f"تحلیل برای {extracted_farm} تولید نشد."
                else: response = f"داده '{extracted_farm}' در جدول نیست."
        else:
            response = "نام مزرعه معتبر نیست. مثال: "
            response += ", ".join([f for f in available_farm_names_today if f != "همه مزارع"][:5])
            if len(available_farm_names_today) > 6: response += "..."
        with st.chat_message("assistant"): st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# --- Footer (unchanged) ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط اسماعیل کیانی")
st.sidebar.markdown("Streamlit | GEE | Geemap | Plotly | Gemini")
if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY": st.sidebar.error("🚨 کلید Gemini نیست.")
elif st.session_state.gemini_available: st.sidebar.success("✅ Gemini API فعال.")
else: st.sidebar.warning("⚠️ Gemini API غیرفعال.")
st.sidebar.warning("هشدار امنیتی: کلید API در کد است.")

# --- END OF FILE ---
import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap # Import specifically for map creation
import folium
import json
import datetime
import plotly.express as px
import plotly.graph_objects as go
import os
from io import BytesIO
import requests
import traceback
from streamlit_folium import st_folium # For displaying folium maps in Streamlit
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
APP_TITLE = "سامانه پایش هوشمند نیشکر (نسخه نهایی)"
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' #<-- YOUR SERVICE ACCOUNT JSON FILE
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
st.set_page_config(page_title=APP_TITLE, page_icon="🌾", layout="wide")

# Custom CSS for colored buttons and RTL layout
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        body, .main, button, input, textarea, select, .stTextInput, .stSelectbox, .stDateInput, .stButton>button, .stMetric, .stDataFrame, .stPlotlyChart, .stChatMessage {
            font-family: 'Vazirmatn', sans-serif !important; direction: rtl;
        }
        .stBlock, .stHorizontalBlock { direction: rtl; }
        h1, h2, h3, h4, h5, h6 { text-align: right; color: #2c3e50; }
        .plotly .gtitle { text-align: right !important; }
        .stSelectbox > label, .stDateInput > label, .stTextInput > label, .stTextArea > label {
             text-align: right !important; width: 100%; display: block;
         }
        .dataframe { text-align: right; }

        /* Style for the custom tab buttons container */
        .tab-buttons-container > div { /* Target the columns div */
            display: flex;
            flex-direction: row;
            gap: 5px; /* Space between buttons */
            justify-content: flex-end; /* Align buttons to the right */
            margin-bottom: 20px; /* Space below buttons */
        }

        /* Style for all custom tab buttons */
        .tab-buttons-container button {
            flex-grow: 0; /* Prevent buttons from growing */
            white-space: nowrap; /* Prevent text wrapping */
            padding: 10px 15px;
            border: none;
            border-radius: 8px 8px 0 0; /* Rounded top corners */
            cursor: pointer;
            font-weight: 600;
            transition: background-color 0.2s ease, transform 0.1s ease; /* Animation */
            color: white; /* Default text color */
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); /* Subtle shadow */
        }

        /* Specific colors for each tab button */
        .tab-button-map button { background-color: #4CAF50; } /* Green */
        .tab-button-ranking button { background-color: #2196F3; } /* Blue */
        .tab-button-timeseries button { background-color: #ff9800; } /* Orange */
        .tab-button-dashboard button { background-color: #9C27B0; } /* Purple */
        .tab-button-chatbot button { background-color: #00BCD4; } /* Cyan */

        /* Active button style (example - requires a way to target the active one) */
        /* This part is tricky with pure CSS on Streamlit buttons */
        /* As a workaround, we'll rely on visual cues like lack of other buttons */
        /* or potentially slightly different shadow/border if needed */

        /* Hover effect */
        .tab-buttons-container button:hover {
            opacity: 0.9;
             transform: translateY(-2px); /* Slight lift effect */
        }

        .stMetric { background-color: #f8f9fa; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;}
        .stMetric > label { font-weight: bold; color: #495057; }
        .stMetric > div { font-size: 1.5em; color: #007bff; }
        .css-1d391kg { direction: rtl; } /* Sidebar */
        .css-1d391kg .stSelectbox > label { text-align: right !important; } /* Sidebar select label */
        /* Chat message alignment for RTL */
        .stChatMessage[data-testid="chatAvatarIcon-user"] + div { order: 1; }
        .stChatMessage[data-testid="chatAvatarIcon-assistant"] + div { order: -1; }
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
# Session state for custom tabs
if 'active_tab' not in st.session_state: st.session_state.active_tab = "🗺️ نقشه" # Default tab

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
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error(traceback.format_exc())
        return False

@st.cache_resource
def configure_gemini():
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
        st.warning(f"⚠️ اخطار: خطا در پیکربندی Gemini API ({e}). تحلیل و چت‌بات هوش مصنوعی غیرفعال خواهد بود.")
        st.warning(traceback.format_exc())
        return None, False

if not st.session_state.gee_initialized:
    st.session_state.gee_initialized = initialize_gee()
    if not st.session_state.gee_initialized:
        st.stop() # Stop execution if GEE initialization fails

if st.session_state.gemini_model is None: # Configure Gemini only once
     st.session_state.gemini_model, st.session_state.gemini_available = configure_gemini()

# --- Load Farm Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    try:
        df = pd.read_csv(csv_path)
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل CSV فاقد ستون‌های ضروری است: {', '.join(required_cols)}")
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
        # Add a unique ID for potential joining later
        df['farm_id'] = df['مزرعه'].astype(str) + '_' + df['طول جغرافیایی'].astype(str) + '_' + df['عرض جغرافیایی'].astype(str)
        print(f"Farm data loaded successfully: {len(df)} farms.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد.")
        return None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.error(traceback.format_exc())
        return None

if st.session_state.farm_data is None:
    st.session_state.farm_data = load_farm_data()

if st.session_state.farm_data is None: # Stop if data loading failed
    st.stop()

# ========================= Sidebar Inputs =========================
st.sidebar.header("⚙️ تنظیمات نمایش")

available_days = sorted(st.session_state.farm_data['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته:", options=available_days,
    index=available_days.index("شنبه") if "شنبه" in available_days else 0, # Default to Saturday if exists
    key='selected_day_key'
)

filtered_farms_df = st.session_state.farm_data[st.session_state.farm_data['روزهای هفته'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

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

# --- Date Range Calculation ---
today_date_obj = datetime.date.today() # Renamed to avoid conflict
persian_to_weekday = {"شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1, "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4}
try:
    target_weekday = persian_to_weekday[selected_day]
    # Calculate days ago, ensuring it's non-negative and finds the most recent past occurrence
    today_weekday = today_date_obj.weekday()
    days_ago = (today_weekday - target_weekday + 7) % 7
    # If today is the target day, days_ago is 0. If the target day is in the future this week,
    # we need to go back to the target day of the *previous* week.
    # Let's adjust to always get the range ending on or before today.
    # Find the date of the most recent target_weekday on or before today_date_obj
    end_date_current = today_date_obj - datetime.timedelta(days=(today_weekday - target_weekday + 7) % 7)
    start_date_current = end_date_current - datetime.timedelta(days=6)

    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    start_date_current_str = start_date_current.strftime('%Y-%m-%d')
    end_date_current_str = end_date_current.strftime('%Y-%m-%d')
    start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
    end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

    st.sidebar.info(f"🗓️ بازه فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"🗓️ بازه قبلی: {start_date_previous_str} تا {end_date_previous_str}")
except KeyError: st.sidebar.error(f"نام روز هفته '{selected_day}' نامعتبر است."); st.stop()
except Exception as e: st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}"); st.stop()


# ========================= GEE Functions (REVISED for ee.Image operations) =========================
@st.cache_data(persist="disk")
def maskS2clouds_ee(_image: ee.Image) -> ee.Image:
    try:
        qa = _image.select('QA60')
        cloudBitMask = 1 << 10; cirrusBitMask = 1 << 11
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
        # Also consider the Scene Classification Layer (SCL) for more robust cloud/shadow masking
        scl = _image.select('SCL')
        # Pixels to mask out: clouds, shadows, snow/ice, cirrus, saturated
        scl_mask = scl.remap([3, 8, 9, 10, 11], [0, 0, 0, 0, 0], 1) # 3: cloud shadow, 8: cloud medium probability, 9: cloud high probability, 10: cirrus, 11: snow/ice
        # Combine QA60 mask with SCL mask
        final_mask = mask.And(scl_mask)

        # Apply scaling factor and mask
        opticalBands = _image.select(['B2', 'B3', 'B4', 'B8', 'B11', 'B12']).multiply(0.0001) # Apply scaling to relevant bands
        # Keep other bands (like QA60, SCL) without scaling if needed, or drop them
        otherBands = _image.select(['QA60', 'SCL']) # Select bands you want to keep unscaled
        # Update masked bands with scaled values, keep others as they are
        return _image.addBands(opticalBands, None, True).updateMask(final_mask).addBands(otherBands, None, True)

    except Exception as e:
        # In a mapped function, printing/logging is limited. Server-side errors are best debugged
        # using GEE's Code Editor or inspecting task errors.
        # This print won't appear in Streamlit logs for mapped functions.
        print(f"Error in maskS2clouds_ee: {e}")
        # Returning the original image or an indicator might be alternatives,
        # but ideally, mapped functions should handle errors gracefully within GEE.
        # For now, let's return the original image unmasked in case of an error in masking itself.
        return _image # Or raise a GEE error if appropriate


@st.cache_data(persist="disk")
def add_indices_ee(_image: ee.Image) -> ee.Image:
    try:
        # Calculate indices directly; missing bands will result in masked values
        ndvi = _image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        ndwi = _image.normalizedDifference(['B8', 'B11']).rename('NDWI')
        ndre = _image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        lai = ndvi.multiply(3.5).rename('LAI')
        chl = _image.expression(
            '(NIR / RE1) - 1',
            {
                'NIR': _image.select('B8'),
                'RE1': _image.select('B5').max(ee.Image(0.0001))
            }
        ).clamp(0, 10).rename('CHL')
        # Add all calculated indices; if bands are missing, the result will be masked
        return _image.addBands([ndvi, ndwi, ndre, lai, chl], None, True)
    except Exception as e:
        print(f"Warning: Index calculation failed for an image: {e}")
        return _image


@st.cache_data(ttl=3600, show_spinner=False, persist="disk")
def get_processed_image_serialized(_geometry_json, start_date, end_date, index_name):
    _geometry = ee.Geometry(json.loads(_geometry_json))
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) # Filter by cloud percentage
                     .map(maskS2clouds_ee)
                     .map(add_indices_ee)
                    )

        count = s2_sr_col.size().getInfo()
        if count == 0: return None, f"No valid images after processing ({start_date} to {end_date}). Consider adjusting date range or cloud filter."

        # Select only the bands needed before taking the median to potentially reduce memory
        all_indices_bands = list(INDEX_INFO.keys())
        s2_sr_col = s2_sr_col.select(all_indices_bands)

        median_image = s2_sr_col.median()

        # Ensure the selected index band exists in the median image
        available_bands_in_median = median_image.bandNames().getInfo()
        if index_name not in available_bands_in_median:
             # This might happen if add_indices_ee failed for all images in the collection
             return None, f"شاخص '{index_name}' در تصویر median نهایی یافت نشد. باندهای موجود: {available_bands_in_median}. (این ممکن است به دلیل خطای پردازش تصاویر خام باشد)"

        output_image = median_image.select(index_name)

        # Mask the output image to the geometry bounds explicitly
        output_image = output_image.clip(_geometry)

        return output_image.serialize(), None

    except ee.EEException as e:
        # Specific GEE errors can be caught here
        return None, f"GEE Error (get_processed_image): {e}"
    except Exception as e:
        # Other potential errors during processing
        return None, f"Unknown Error (get_processed_image): {e}\n{traceback.format_exc()}"

@st.cache_data(ttl=3600, show_spinner="در حال تولید تصویر کوچک...")
def get_thumbnail_url(_image_serialized, _geometry_json, _vis_params):
    if not _image_serialized: return None, "No image data for thumbnail."
    try:
        image = ee.Image.deserialize(_image_serialized)
        geometry = ee.Geometry(json.loads(_geometry_json))
        # Use the geometry bounds for the thumbnail region
        thumb_region = geometry.bounds()
        thumb_url = image.getThumbURL({'region': thumb_region, 'dimensions': 256, 'params': _vis_params, 'format': 'png'})
        return thumb_url, None
    except Exception as e: return None, f"Thumbnail Error: {e}"

@st.cache_data(ttl=3600, show_spinner="در حال دریافت سری زمانی...")
def get_index_time_series_data(_point_geom_json, index_name, start_date, end_date):
    _point_geom = ee.Geometry(json.loads(_point_geom_json))
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) # Filter by cloud percentage
                     .map(maskS2clouds_ee)
                     .map(add_indices_ee)
                     .select([index_name]) # Select the specific index band
                    )

        # Function to extract value at point, designed for server-side map
        def extract_value(image: ee.Image):
            # Ensure the selected band exists before reducing
            if index_name not in image.bandNames().getInfo():
                 # Skip this image if the band is missing
                 return None # GEE map will filter out None results with filter(ee.Filter.notNull())

            # Reduce the image value at the point
            value_dict = image.reduceRegion(
                reducer=ee.Reducer.first(), # Use first() for a single point
                geometry=_point_geom,
                scale=10, # Set a suitable scale
                bestEffort=True, # Use bestEffort for flexible scaling
                maxPixels=1e4 # Limit max pixels
            )

            # Get the value and date
            value = value_dict.get(index_name)
            img_date = image.date().format('YYYY-MM-dd') # Use image.date()

            # Return a Feature with date and value if value is not null
            return ee.Feature(None, {'date': img_date, index_name: value})

        # Map the function and filter out failed results
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))

        # Get info client-side
        ts_info = ts_features.getInfo()['features']

        if not ts_info: return None, f"No valid time series data points for {index_name}."

        # Convert features to DataFrame
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data); ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        ts_df[index_name] = pd.to_numeric(ts_df[index_name], errors='coerce')
        ts_df.dropna(subset=[index_name], inplace=True)

        if ts_df.empty: return None, f"No valid numeric time series for {index_name}."

        return ts_df.to_json(orient='split', date_format='iso'), None

    except ee.EEException as e: return None, f"GEE Time Series Error ({index_name}): {e}"
    except Exception as e: return None, f"Unknown Time Series Error ({index_name}): {e}\n{traceback.format_exc()}"


def calculate_all_farm_indices(farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
    results = []; errors = []; total_farms = len(farms_df)
    st.markdown(f"⏳ در حال محاسبه شاخص {index_name} برای {total_farms} مزرعه...")
    progress_bar = st.progress(0); status_text = st.empty() # Use empty for dynamic text updates

    # Define a helper function to get mean value from serialized image
    def get_mean_value_from_serialized(geom_json, start, end, idx_name):
        image_serialized, error_img = get_processed_image_serialized(geom_json, start, end, idx_name)
        if image_serialized:
            try:
                image = ee.Image.deserialize(image_serialized)
                # Reduce the image over the point geometry
                mean_dict = image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=ee.Geometry(json.loads(geom_json)), # Use the geometry JSON
                    scale=10, # Set a suitable scale
                    bestEffort=True,
                    maxPixels=1e4
                ).getInfo() # Use getInfo() to fetch the result

                val = mean_dict.get(idx_name) if mean_dict else None
                # Check for None explicitly as the value could be 0.
                if val is None and mean_dict is not None:
                    return None, f"'{idx_name}' not in reduceRegion result dictionary."
                elif val is None:
                     return None, "ReduceRegion returned None (possible no pixels in geometry at scale)."

                # Convert to float if possible
                try:
                    return float(val), None
                except (ValueError, TypeError):
                    return None, f"Could not convert reduced value '{val}' to float."

            except ee.EEException as e_reduce:
                 # GEE specific error during reduceRegion
                 return None, f"GEE Error during reduceRegion: {e_reduce}"
            except Exception as e_other:
                 # Other Python errors during processing
                 return None, f"Unknown Error during reduceRegion or deserialization: {e_other}"
        else:
            # Error from get_processed_image_serialized itself
            return None, error_img or "Image not found for processing."

    for i, (idx, farm) in enumerate(farms_df.iterrows()):
        farm_name = farm['مزرعه']; lat = farm['عرض جغرافیایی']; lon = farm['طول جغرافیایی']
        # Create a point geometry for reduction. For a farm area, you might use a polygon geometry.
        # Assuming point reduction for now based on the provided coordinates structure.
        # If farms are polygons, the CSV needs polygon GeoJSON or WKT.
        point_geom = ee.Geometry.Point([lon, lat]); point_geom_json = json.dumps(point_geom.getInfo())

        status_text.text(f"پردازش مزرعه {i+1}/{total_farms}: {farm_name}")

        # Get current and previous values using the helper function
        current_val, err_curr = get_mean_value_from_serialized(point_geom_json, start_curr, end_curr, index_name)
        if err_curr: errors.append(f"{farm_name} (جاری): {err_curr}")

        previous_val, err_prev = get_mean_value_from_serialized(point_geom_json, start_prev, end_prev, index_name)
        if err_prev: errors.append(f"{farm_name} (قبل): {err_prev}")

        change = None
        if current_val is not None and previous_val is not None:
            try:
                change = float(current_val) - float(previous_val)
            except (TypeError, ValueError):
                change = None # Keep change as None if values are not numeric

        results.append({'farm_id': farm['farm_id'], 'مزرعه': farm_name, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                       'طول جغرافیایی': lon, 'عرض جغرافیایی': lat, f'{index_name}_curr': current_val, f'{index_name}_prev': previous_val, f'{index_name}_change': change})

        progress_bar.progress((i + 1) / total_farms)

    status_text.text(f"محاسبه کامل شد."); time.sleep(1) # Keep final status for a moment
    progress_bar.empty() # Hide progress bar after completion
    status_text.empty() # Hide status text after completion

    return pd.DataFrame(results), errors

@st.cache_data(show_spinner="🧠 در حال تحلیل با هوش مصنوعی...")
def get_gemini_analysis(_index_name, _farm_name, _current_val, _previous_val, _change_val):
    if not st.session_state.gemini_available or st.session_state.gemini_model is None: return "AI API Error.", None
    # Check if input values are valid numbers (not NaN or None)
    try:
        if pd.isna(_current_val) or pd.isna(_previous_val) or pd.isna(_change_val) or \
           not isinstance(_current_val, (int, float)) or not isinstance(_previous_val, (int, float)) or not isinstance(_change_val, (int, float)):
            return "داده نامعتبر برای تحلیل (مقادیر عددی نیستند).", None
    except Exception:
        return "داده ورودی نامعتبر (خطا در بررسی نوع داده).", None

    current_str = f"{float(_current_val):.3f}"; previous_str = f"{float(_previous_val):.3f}"; change_str = f"{float(_change_val):+.3f}" # Add + for positive change
    index_details = INDEX_INFO.get(_index_name, {"name": _index_name, "desc": ""})
    interpretation = f"شاخص {_index_name} ({index_details.get('name', '')}). ماهیت شاخص: {index_details.get('desc', 'توضیحی نیست.')}"

    prompt = f"""
    شما یک دستیار متخصص کشاورزی برای تحلیل داده‌های ماهواره‌ای مزارع نیشکر هستید.
    برای مزرعه نیشکر با نام "{_farm_name}"، شاخص "{_index_name}" تحلیل شده است. {interpretation}
    مقدار شاخص در هفته جاری: {current_str}. مقدار شاخص در هفته قبل: {previous_str}. میزان تغییر: {change_str}.
    آیا مقدار بیشتر در این شاخص نشان‌دهنده وضعیت بهتر محصول است؟ {'بله' if index_details.get('higher_is_better', False) else 'خیر'}.

    وظایف:
    1.  **تحلیل وضعیت:** به زبان فارسی ساده و دقیق توضیح دهید که این تغییر در شاخص {_index_name} (افزایش، کاهش، یا ثبات) چه معنایی برای وضعیت سلامت، رشد، یا تنش (بسته به ماهیت شاخص) نیشکر در این مزرعه دارد. به این نکته اشاره کنید که آیا تغییر مثبت نشان‌دهنده بهبود است یا خیر (بر اساس 'آیا مقدار بیشتر ...').
    2.  **پیشنهاد مدیریتی:** بر اساس این تحلیل و ماهیت شاخص، یک یا دو پیشنهاد کلی مدیریتی (مانند آبیاری، کوددهی، پایش بیشتر) برای این مزرعه ارائه دهید.

    نکات: تحلیل فقط بر اساس اطلاعات داده شده باشد. زبان رسمی و قابل فهم. پاسخ کوتاه و متمرکز (حدود ۱۰۰-۱۵۰ کلمه). پاسخ به زبان فارسی. از توضیح مفاهیم پایه شاخص‌ها خودداری کنید مگر در حد اشاره کوتاه.

    فرمت پاسخ:
    **تحلیل وضعیت:** [توضیح شما]
    **پیشنهاد مدیریتی:** [پیشنهاد شما]"""

    try:
        response = st.session_state.gemini_model.generate_content(prompt)
        analysis_text = response.text
        if not analysis_text or len(analysis_text.strip()) < 50: return "AI پاسخ کوتاه یا نامفهوم داد.", None
        return analysis_text.strip(), None
    except Exception as e:
        print(f"Gemini API Error during analysis: {e}")
        return None, f"Gemini API Error: {e}"

def extract_farm_name(text, available_farms_list):
    # Clean and normalize farm names and input text for better matching
    def normalize(name):
        # Remove common punctuation and potentially extra spaces
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip().lower()
        return name

    normalized_text = normalize(text)
    normalized_farms = {normalize(name): name for name in available_farms_list if name != "همه مزارع"}

    # Try exact match first
    if normalized_text in normalized_farms:
        return normalized_farms[normalized_text]

    # Then try partial matching (less reliable)
    for normalized_farm, original_farm in normalized_farms.items():
        # Check if a significant part of the farm name is in the text
        if normalized_farm in normalized_text or normalized_text in normalized_farm:
            return original_farm # Return the original farm name from the list

    # If no match, return None
    return None


# ========================= Main Panel Layout =========================
st.title(APP_TITLE)
st.markdown(f"**مطالعات کاربردی شرکت کشت و صنعت دهخدا** | تاریخ گزارش: {today_date_obj.strftime('%Y-%m-%d')}")
st.markdown("---")

selected_farm_details = None; selected_farm_geom = None; selected_farm_geom_json = None
if selected_farm_name == "همه مزارع":
    st.info(f"نمایش اطلاعات کلی برای {len(filtered_farms_df)} مزرعه در روز **{selected_day}**.")
    try:
        # Create a bounding box for all farms for the map center/bounds
        min_lon, min_lat = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
        max_lon, max_lat = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
        # Ensure valid coordinates before creating geometry
        if pd.notna(min_lon) and pd.notna(min_lat) and pd.notna(max_lon) and pd.notna(max_lat):
            selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
            selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
        else:
             # Fallback to a point geometry if bounds are invalid
             center_lat = filtered_farms_df['عرض جغرافیایی'].mean(); center_lon = filtered_farms_df['طول جغرافیایی'].mean()
             selected_farm_geom = ee.Geometry.Point([center_lon, center_lat])
             selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
             st.warning("⚠️ مختصات برخی مزارع نامعتبر است. نمایشگر نقشه بر اساس نقطه مرکزی خواهد بود.")

    except Exception as e:
        st.error(f"خطا در تعیین محدوده نقشه برای 'همه مزارع': {e}")
        # Fallback to a point geometry
        center_lat = filtered_farms_df['عرض جغرافیایی'].mean(); center_lon = filtered_farms_df['طول جغرافیایی'].mean()
        selected_farm_geom = ee.Geometry.Point([center_lon, center_lat])
        selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
        st.warning("⚠️ خطا در تعیین محدوده نقشه. نمایشگر نقشه بر اساس نقطه مرکزی خواهد بود.")

else:
    # Select the specific farm details
    farm_row_index = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].index
    if not farm_row_index.empty:
        selected_farm_details = filtered_farms_df.loc[farm_row_index[0]] # Use .loc for row selection
        lat = selected_farm_details['عرض جغرافیایی']; lon = selected_farm_details['طول جغرافیایی']
        # Ensure coordinates are valid numbers
        if pd.notna(lat) and pd.notna(lon):
             selected_farm_geom = ee.Geometry.Point([lon, lat])
             selected_farm_geom_json = json.dumps(selected_farm_geom.getInfo())
        else:
             st.error(f"❌ مختصات مزرعه '{selected_farm_name}' نامعتبر است.")
             selected_farm_geom = None
             selected_farm_geom_json = None
    else:
        st.error(f"❌ مزرعه '{selected_farm_name}' در داده‌های روز '{selected_day}' یافت نشد.")
        selected_farm_geom = None
        selected_farm_geom_json = None

    # Display farm details if a specific farm is selected and found
    if selected_farm_details is not None:
        st.subheader(f"📍 اطلاعات مزرعه: {selected_farm_name}")
        cols = st.columns([1, 1, 1, 2])
        with cols[0]: st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', '-'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "-"); st.metric("واریته", f"{selected_farm_details.get('واریته', '-')}")
        with cols[1]: st.metric("کانال", f"{selected_farm_details.get('کانال', '-')}"); st.metric("سن", f"{selected_farm_details.get('سن', '-')}")
        with cols[2]: st.metric("اداره", f"{selected_farm_details.get('اداره', '-')}"); st.metric("روز آبیاری", f"{selected_farm_details.get('روزهای هفته', '-')}")
        with cols[3]:
            st.markdown("**تصویر کوچک (هفته جاری):**")
            if selected_farm_geom_json:
                # Use a smaller buffer for point geometries in thumbnail
                thumbnail_geom = ee.Geometry(json.loads(selected_farm_geom_json))
                # If it's a point, buffer it slightly for thumbnail view
                if thumbnail_geom.type().getInfo() == 'Point':
                     thumbnail_geom = thumbnail_geom.buffer(100).bounds() # Buffer point by 100 meters and get bounds

                thumb_image_serial, err_img = get_processed_image_serialized(json.dumps(thumbnail_geom.getInfo()), start_date_current_str, end_date_current_str, selected_index)
                if thumb_image_serial:
                    thumb_url, err_thumb = get_thumbnail_url(thumb_image_serial, json.dumps(thumbnail_geom.getInfo()), vis_params)
                    if thumb_url: st.image(thumb_url, caption=f"{selected_index}", width=200)
                    elif err_thumb: st.warning(f"خطا Thumbnail: {err_thumb}")
                elif err_img: st.warning(f"خطا تصویر: {err_img}")
            else: st.warning("موقعیت برای تصویر کوچک نیست.")

# --- Custom Tab Buttons ---
tab_buttons = {
    "🗺️ نقشه": 'tab-button-map',
    "📊 جدول رتبه‌بندی": 'tab-button-ranking',
    "📈 سری زمانی": 'tab-button-timeseries',
    " dashboards خلاصه": 'tab-button-dashboard',
    "💬 چت‌بات": 'tab-button-chatbot'
}
cols = st.columns(len(tab_buttons))
# Use a container to apply CSS flexbox
button_container = st.container()
with button_container:
    button_cols = st.columns(len(tab_buttons))
    for i, (tab_name, css_class) in enumerate(tab_buttons.items()):
        with button_cols[i]:
            # Add a unique key to each button based on its tab name
            if st.button(tab_name, key=f"tab_button_{tab_name}"):
                st.session_state.active_tab = tab_name
            # Inject CSS class using markdown to target the button directly
            # This is a workaround and might be fragile depending on Streamlit's internal HTML structure
            st.markdown(f"""
            <style>
                /* Find the button by its text content (fragile) or parent structure */
                /* A more reliable way is to target based on the key if possible, or inject CSS */
                div[data-testid="column"]:nth-child({i+1}) button {{
                    background-color: {"#f0f2f6" if st.session_state.active_tab != tab_name else tab_buttons[tab_name].split('-')[-1]}; /* Default inactive or active color */
                    color: {"#333" if st.session_state.active_tab != tab_name else "white"};
                     border-bottom: 3px solid {"transparent" if st.session_state.active_tab != tab_name else tab_buttons[tab_name].split('-')[-1]}; /* Underline active tab */
                }}
                /* Reapply the specific colors for active tabs for clarity */
                div[data-testid="column"]:nth-child({i+1}) button {{
                     background-color: {tab_buttons[tab_name].split('-')[-1]} !important; /* Force specific button color */
                     color: white !important;
                     border-bottom: 3px solid {"transparent" if st.session_state.active_tab != tab_name else "white"}; /* White underline for active */
                }}
                 div[data-testid="column"]:nth-child({i+1}) button:hover {{
                     opacity: 0.9;
                     transform: translateY(-2px);
                 }}
            </style>
            """, unsafe_allow_html=True)
            # This dynamic CSS injection per button within columns is complex and might not work reliably.
            # Let's simplify and rely on the general CSS injected at the start.
            # The general CSS above targets buttons within .tab-buttons-container.
            # We can add a class to the button or its container if possible.
            # Streamlit buttons don't allow easy class addition. Let's remove the per-button CSS injection.

# We will rely on the general CSS class `.tab-buttons-container button` and the specific color classes defined at the top.
# The challenge is visually highlighting the *active* button with pure CSS and Streamlit's default buttons.
# A common workaround is to change the button's label slightly or its container style, but it's hacky.
# Let's proceed with the basic colored buttons and rely on the content below to indicate the active tab.


# --- Conditional Content Display based on Active Tab ---

if st.session_state.active_tab == "🗺️ نقشه": # Map Tab
    st.subheader(f"نقشه ماهواره‌ای - شاخص: {selected_index}")
    # Re-initialize map only when needed or parameters change
    map_key = f"map_display_key_{selected_index}_{selected_farm_name}_{start_date_current_str}_{end_date_current_str}"
    if map_key not in st.session_state: st.session_state[map_key] = None # Initialize key if not exists

    if st.session_state[map_key] is None:
        m = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
        m.add_basemap("HYBRID")
        map_data_placeholder = st.empty()
        if selected_farm_geom_json:
            map_data_placeholder.info("در حال بارگذاری لایه شاخص...")
            gee_image_serialized, error_msg_current = get_processed_image_serialized(selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index)
            if gee_image_serialized:
                try:
                    gee_image_current = ee.Image.deserialize(gee_image_serialized)
                    m.addLayer(gee_image_current, vis_params, f"{selected_index} ({start_date_current_str} to {end_date_current_str})")
                    legend_title = f"{selected_index} ({index_props['name']})"
                    m.add_legend(legend_title=legend_title, palette=index_props['palette'], min=index_props['min'], max=index_props['max'])

                    if selected_farm_name == "همه مزارع":
                        # Add markers for all farms
                        points = filtered_farms_df[['عرض جغرافیایی', 'طول جغرافیایی', 'مزرعه']].to_dict('records')
                        # Create a list of Folium Markers
                        for point in points:
                            if pd.notna(point['عرض جغرافیایی']) and pd.notna(point['طول جغرافیایی']):
                                folium.Marker(
                                    location=[point['عرض جغرافیایی'], point['طول جغرافیایی']],
                                    popup=f"<b>{point['مزرعه']}</b>",
                                    tooltip=point['مزرعه'],
                                    icon=folium.Icon(color='blue', icon='info-sign') # Use info-sign icon
                                ).add_to(m)

                        # Fit map to the bounds of all farms if selected_farm_geom is a bounds rectangle
                        if isinstance(selected_farm_geom, ee.geometry.Geometry) and selected_farm_geom.type().getInfo() == 'Rectangle':
                             try:
                                 bounds = selected_farm_geom.bounds().getInfo()
                                 m.fit_bounds([[bounds['coordinates'][0][1], bounds['coordinates'][0][0]], [bounds['coordinates'][0][3], bounds['coordinates'][0][2]]])
                             except Exception as e_fit: print(f"Error fitting bounds: {e_fit}")
                        elif isinstance(selected_farm_geom, ee.geometry.Geometry):
                             m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM) # Center on point if bounds failed

                    else: # Single farm selected
                        if selected_farm_details is not None and pd.notna(selected_farm_details['عرض جغرافیایی']) and pd.notna(selected_farm_details['طول جغرافیایی']):
                            folium.Marker(location=[selected_farm_details['عرض جغرافیایی'], selected_farm_details['طول جغرافیایی']], popup=f"<b>{selected_farm_name}</b>", tooltip=selected_farm_name, icon=folium.Icon(color='red', icon='star')).add_to(m)
                            # Center map on the selected farm with a slightly higher zoom
                            if isinstance(selected_farm_geom, ee.geometry.Geometry):
                                m.center_object(selected_farm_geom, zoom=15)

                    m.add_layer_control()
                    map_data_placeholder.empty()
                    st_folium(m, width=None, height=600, use_container_width=True, key=map_key) # Use the dynamic key
                    st.session_state[map_key] = True # Mark map as rendered
                except Exception as map_err:
                    map_data_placeholder.error(f"خطا نمایش نقشه: {map_err}\n{traceback.format_exc()}")
                    st.session_state[map_key] = False # Mark map rendering as failed
            else:
                 map_data_placeholder.warning(f"تصویر نقشه نیست. {error_msg_current}")
                 st.session_state[map_key] = False # Mark map rendering as failed
        else:
            map_data_placeholder.warning("موقعیت نقشه نیست.")
            st.session_state[map_key] = False # Mark map rendering as failed
    else:
        # If map was already rendered for these parameters, display it from session state
        # Note: st_folium doesn't store the map object itself in session state easily for re-rendering
        # We trigger a re-render by calling st_folium again with the same key,
        # relying on Streamlit's caching or re-execution to build the map.
        # If initialization failed, just show the warning again.
        if st.session_state[map_key] is False: # If previous attempt failed
             if selected_farm_geom_json:
                 map_data_placeholder = st.empty()
                 map_data_placeholder.warning(f"خطا در بارگذاری یا نمایش نقشه در اجرای قبلی. لطفا دوباره تلاش کنید یا پارامترها را تغییر دهید.")
             else:
                 map_data_placeholder = st.empty()
                 map_data_placeholder.warning("موقعیت نقشه نیست.")
        else:
             # Re-render the map by calling st_folium with the cached key
             m = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
             m.add_basemap("HYBRID")
             # Need to re-add layers and markers to the map object before calling st_folium
             # This requires re-fetching or storing layer info, which adds complexity.
             # For simplicity in this example, let's assume re-running the block builds the map correctly.
             # A more robust solution might involve storing the generated Folium map object or its components.

             # Re-fetch the image and add layers for display
             gee_image_serialized, error_msg_current = get_processed_image_serialized(selected_farm_geom_json, start_date_current_str, end_date_current_str, selected_index)
             if gee_image_serialized:
                 try:
                     gee_image_current = ee.Image.deserialize(gee_image_serialized)
                     m.addLayer(gee_image_current, vis_params, f"{selected_index} ({start_date_current_str} to {end_date_current_str})")
                     legend_title = f"{selected_index} ({index_props['name']})"
                     m.add_legend(legend_title=legend_title, palette=index_props['palette'], min=index_props['min'], max=index_props['max'])

                     if selected_farm_name == "همه مزارع":
                        points = filtered_farms_df[['عرض جغرافیایی', 'طول جغرافیایی', 'مزرعه']].to_dict('records')
                        for point in points:
                             if pd.notna(point['عرض جغرافیایی']) and pd.notna(point['طول جغرافیایی']):
                                folium.Marker(
                                    location=[point['عرض جغرافیایی'], point['طول جغرافیایی']],
                                    popup=f"<b>{point['مزرعه']}</b>",
                                    tooltip=point['مزرعه'],
                                    icon=folium.Icon(color='blue', icon='info-sign')
                                ).add_to(m)
                        if isinstance(selected_farm_geom, ee.geometry.Geometry) and selected_farm_geom.type().getInfo() == 'Rectangle':
                             try:
                                 bounds = selected_farm_geom.bounds().getInfo()
                                 m.fit_bounds([[bounds['coordinates'][0][1], bounds['coordinates'][0][0]], [bounds['coordinates'][0][3], bounds['coordinates'][0][2]]])
                             except Exception as e_fit: print(f"Error fitting bounds: {e_fit}")
                        elif isinstance(selected_farm_geom, ee.geometry.Geometry):
                             m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM)

                     else:
                         if selected_farm_details is not None and pd.notna(selected_farm_details['عرض جغرافیایی']) and pd.notna(selected_farm_details['طول جغرافیایی']):
                            folium.Marker(location=[selected_farm_details['عرض جغرافیایی'], selected_farm_details['طول جغرافیایی']], popup=f"<b>{selected_farm_name}</b>", tooltip=selected_farm_name, icon=folium.Icon(color='red', icon='star')).add_to(m)
                            if isinstance(selected_farm_geom, ee.geometry.Geometry):
                                m.center_object(selected_farm_geom, zoom=15)

                     m.add_layer_control()
                     st_folium(m, width=None, height=600, use_container_width=True, key=map_key)

                 except Exception as map_err:
                     st.error(f"خطا نمایش نقشه در حالت کش شده: {map_err}\n{traceback.format_exc()}")
                     st.session_state[map_key] = False # Mark as failed if error occurs during re-render


if st.session_state.active_tab == "📊 جدول رتبه‌بندی": # Ranking Table Tab
    st.subheader(f"جدول رتبه‌بندی مزارع بر اساس {selected_index} ({selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")
    # Define parameters that affect the ranking table
    ranking_params = (selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str, selected_day)

    # Check if ranking data needs to be recalculated
    if st.session_state.ranking_data['params'] != ranking_params or st.session_state.ranking_data['df'].empty:
        print(f"Recalculating ranking table for: {ranking_params}")
        # Reset ranking and analysis data when parameters change
        st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}
        st.session_state.gemini_analysis = {'text': None, 'error': None, 'params': None} # Reset AI analysis
        st.session_state.messages = [] # Reset chatbot history

        # Perform the calculation
        ranking_df_raw, calculation_errors = calculate_all_farm_indices(filtered_farms_df, selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str)

        # Store results in session state
        st.session_state.ranking_data['df'] = ranking_df_raw
        st.session_state.ranking_data['errors'] = calculation_errors
        st.session_state.ranking_data['params'] = ranking_params

        # Rerun to display the results after calculation is complete
        st.rerun()
    else:
        # Use cached ranking data from session state
        print("Using cached ranking data from session state.")
        ranking_df_raw = st.session_state.ranking_data['df']
        calculation_errors = st.session_state.ranking_data['errors']

    # Display the ranking table if data exists
    if not ranking_df_raw.empty:
        ranking_df_display = ranking_df_raw.copy()
        curr_col = f'{selected_index} (هفته جاری)'; prev_col = f'{selected_index} (هفته قبل)'; change_col = 'تغییر'
        ranking_df_display = ranking_df_display.rename(columns={f'{selected_index}_curr': curr_col, f'{selected_index}_prev': prev_col, f'{selected_index}_change': change_col})

        higher_is_better = index_props['higher_is_better']

        def determine_status_tab2(change_val):
            try:
                # Check for pandas NaN or None
                if pd.isna(change_val): return "بدون داده"
                # Convert to float and check for math NaN or infinity
                change_val_float = float(change_val)
                if math.isnan(change_val_float) or math.isinf(change_val_float): return "بدون داده"

                if higher_is_better:
                    if change_val_float > CHANGE_THRESHOLD: return "🟢 بهبود / رشد"
                    elif change_val_float < -CHANGE_THRESHOLD: return "🔴 کاهش / تنش"
                    else: return "⚪ ثابت"
                else: # Lower is better
                    if change_val_float < -CHANGE_THRESHOLD: return "🟢 بهبود / رشد"
                    elif change_val_float > CHANGE_THRESHOLD: return "🔴 کاهش / تنش"
                    else: return "⚪ ثابت"
            except (TypeError, ValueError): return "خطا در مقدار" # Handle cases where change_val is not convertible to float

        ranking_df_display['وضعیت'] = ranking_df_display[change_col].apply(determine_status_tab2)

        # Sort the DataFrame for ranking
        ranking_df_sorted = ranking_df_display.sort_values(by=curr_col, ascending=not higher_is_better, na_position='last').reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1 # Start index from 1
        ranking_df_sorted.index.name = 'رتبه' # Rename index column

        # Format numeric columns for display
        cols_to_format = [curr_col, prev_col, change_col]
        for col_name_fmt in cols_to_format:
            if col_name_fmt in ranking_df_sorted.columns:
                ranking_df_sorted[col_name_fmt] = ranking_df_sorted[col_name_fmt].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float, str)) and str(x).replace('.', '', 1).replace('-', '', 1).lstrip('-').isdigit() else ("-" if pd.isna(x) else str(x))) # Handle non-numeric values gracefully

        # Display the dataframe
        st.dataframe(ranking_df_sorted[['مزرعه', 'کانال', 'اداره', curr_col, prev_col, change_col, 'وضعیت']], use_container_width=True, height=400)

        # Download button for CSV
        try:
            csv_data = ranking_df_sorted.to_csv(index=True, encoding='utf-8-sig') # Include index (Rتبه)
            st.download_button("📥 دانلود جدول (CSV)", data=csv_data, file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv')
        except Exception as e: st.error(f"خطا دانلود CSV: {e}")

        # Display calculation errors if any
        if calculation_errors:
            with st.expander("⚠️ مشاهده خطاهای محاسبه در جدول رتبه‌بندی", expanded=False):
                # Filter unique errors and display a limited number
                unique_errors = sorted(list(set(str(e) for e in calculation_errors)))
                st.warning(f"تعداد کل خطاهای منحصربفرد در محاسبه: {len(unique_errors)}")
                for i, error_msg in enumerate(unique_errors):
                    st.error(f"- {error_msg}")
                    if i >= 15: # Limit the number of displayed errors to avoid clutter
                        st.warning("... و احتمالاً خطاهای بیشتر. برای مشاهده کامل، لاگ‌های برنامه را بررسی کنید.")
                        break
    else:
        # Message if ranking data is empty after calculation attempt
        st.info(f"داده رتبه‌بندی برای شاخص '{selected_index}' و روز '{selected_day}' پس از محاسبه نیست.")
        if calculation_errors: st.error("خطا در محاسبه مقادیر جدول (بالا).")


if st.session_state.active_tab == "📈 سری زمانی": # Time Series Tab
    st.subheader(f"نمودار روند زمانی شاخص {selected_index}")
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از نوار کناری انتخاب کنید تا نمودار سری زمانی نمایش داده شود.")
    elif selected_farm_geom_json:
        # Define the date range for the time series (e.g., last year)
        ts_end_date = today_date_obj.strftime('%Y-%m-%d')
        ts_start_date = (today_date_obj - datetime.timedelta(days=365)).strftime('%Y-%m-%d') # Last 365 days

        # Check if time series data for this farm/index/date range is cached
        ts_params = (selected_farm_name, selected_index, ts_start_date, ts_end_date)
        ts_data_key = f"ts_data_{'_'.join(ts_params).replace(' ', '_')}"

        if ts_data_key not in st.session_state:
             st.session_state[ts_data_key] = {'json': None, 'error': None}
             # Fetch data if not cached
             ts_df_json, ts_error = get_index_time_series_data(selected_farm_geom_json, selected_index, ts_start_date, ts_end_date)
             st.session_state[ts_data_key] = {'json': ts_df_json, 'error': ts_error}
             # Rerun to display after fetching
             st.rerun()
        else:
            # Use cached data
            ts_df_json = st.session_state[ts_data_key]['json']
            ts_error = st.session_state[ts_data_key]['error']


        if ts_error:
            st.warning(f"خطا در دریافت داده سری زمانی: {ts_error}")
        elif ts_df_json:
            try:
                # Load data from JSON
                ts_df = pd.read_json(ts_df_json, orient='split')
                ts_df.index = pd.to_datetime(ts_df.index, format='iso') # Ensure datetime index

                if not ts_df.empty:
                    # Create Plotly line chart
                    fig_ts = px.line(ts_df, y=selected_index, markers=True, title=f"روند زمانی شاخص {selected_index} برای مزرعه {selected_farm_name}", labels={'index': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                    # Update layout for RTL and font
                    fig_ts.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                    # Display the chart
                    st.plotly_chart(fig_ts, use_container_width=True)

                    # Download button for time series data
                    csv_ts = ts_df.to_csv(encoding='utf-8-sig')
                    st.download_button("📥 دانلود داده سری زمانی (CSV)", data=csv_ts, file_name=f'ts_{selected_farm_name}_{selected_index}.csv', mime='text/csv')
                else:
                    st.info(f"داده معتبر سری زمانی برای شاخص '{selected_index}' و مزرعه '{selected_farm_name}' در بازه انتخاب شده یافت نشد.")
            except Exception as e_plot:
                st.error(f"خطا در رسم نمودار سری زمانی یا پردازش داده: {e_plot}\n{traceback.format_exc()}")
        else:
            # Message when ts_df_json is None and there was no specific error message from GEE
            st.info(f"داده سری زمانی برای شاخص '{selected_index}' و مزرعه '{selected_farm_name}' در بازه انتخاب شده نیست.")
    else:
        st.warning("موقعیت مزرعه برای نمایش سری زمانی معتبر نیست.")

if st.session_state.active_tab == " dashboards خلاصه": # Dashboard Tab
    st.subheader(f"داشبورد خلاصه وضعیت روزانه ({selected_day}) - شاخص: {selected_index}")
    # Get ranking data from session state
    ranking_df_raw_dash = st.session_state.ranking_data.get('df')

    # Check if ranking data is available
    if ranking_df_raw_dash is None or ranking_df_raw_dash.empty:
        st.warning(f"داده رتبه‌بندی برای روز **{selected_day}** و شاخص **{selected_index}** نیست. لطفاً ابتدا به تب '📊 جدول رتبه‌بندی' بروید تا محاسبات انجام شود.")
    else:
        # Process data for dashboard
        df_dash = ranking_df_raw_dash.copy()
        curr_col_raw = f'{selected_index}_curr'; prev_col_raw = f'{selected_index}_prev'; change_col_raw = f'{selected_index}_change'

        # Ensure columns exist and are numeric
        for col in [curr_col_raw, prev_col_raw, change_col_raw]:
            if col in df_dash.columns:
                 df_dash[col] = pd.to_numeric(df_dash[col], errors='coerce')
            else:
                 df_dash[col] = pd.NA # Add column with missing values if it doesn't exist

        higher_is_better_dash = index_props['higher_is_better']

        # Determine status for dashboard visualization
        def get_status_dashboard(change):
            try:
                if pd.isna(change) or math.isnan(change) or math.isinf(change): return "بدون داده"
                if higher_is_better_dash:
                    if change > CHANGE_THRESHOLD: return "بهبود"
                    elif change < -CHANGE_THRESHOLD: return "کاهش"
                    else: return "ثابت"
                else: # Lower is better
                    if change < -CHANGE_THRESHOLD: return "بهبود"
                    elif change > CHANGE_THRESHOLD: return "کاهش"
                    else: return "ثابت"
            except: return "خطا" # Catch any other unexpected errors

        df_dash['status'] = df_dash[change_col_raw].apply(get_status_dashboard)

        # Count statuses
        status_counts = df_dash['status'].value_counts().to_dict() # Convert to dictionary for easier access

        st.markdown("**آمار کلی وضعیت مزارع:**")
        col1, col2, col3, col4 = st.columns(4)
        # Display metrics using get() with a default of 0 for statuses that might not exist
        with col1: st.metric("🟢 بهبود", status_counts.get("بهبود", 0))
        with col2: st.metric("⚪ ثابت", status_counts.get("ثابت", 0))
        with col3: st.metric("🔴 کاهش", status_counts.get("کاهش", 0))
        with col4: st.metric("⚫️ بدون داده / خطا", status_counts.get("بدون داده", 0) + status_counts.get("خطا", 0)) # Combine "بدون داده" and "خطا"

        st.markdown("---")

        # Plotting
        col_plot1, col_plot2 = st.columns(2)

        with col_plot1:
            st.markdown(f"**توزیع مقادیر {selected_index} (هفته جاری)**")
            # Drop NA values for histogram plotting
            hist_data = df_dash[curr_col_raw].dropna()
            if not hist_data.empty:
                fig_hist = px.histogram(hist_data, nbins=20, title=f"توزیع مقادیر {selected_index} (هفته جاری)", labels={'value': f'مقدار {selected_index}'})
                fig_hist.update_layout(yaxis_title="تعداد مزارع", xaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                st.plotly_chart(fig_hist, use_container_width=True)
            else:
                st.info(f"داده کافی برای رسم هیستوگرام شاخص {selected_index} نیست.")

        with col_plot2:
            st.markdown("**مقایسه مقادیر هفته جاری و قبل**")
            # Drop rows with missing values for scatter plot
            scatter_data = df_dash.dropna(subset=[curr_col_raw, prev_col_raw, 'status'])
            if not scatter_data.empty:
                fig_scatter = px.scatter(scatter_data, x=prev_col_raw, y=curr_col_raw, color='status', hover_name='مزرعه', title=f"مقایسه شاخص {selected_index} (هفته جاری در مقابل قبل)", labels={prev_col_raw: f"{selected_index} (هفته قبل)", curr_col_raw: f"{selected_index} (هفته جاری)", 'status': 'وضعیت'}, color_discrete_map={'بهبود': 'green', 'ثابت': 'grey', 'کاهش': 'red', 'بدون داده': 'black', 'خطا':'orange'})

                # Add 1:1 line (y=x)
                # Determine the range for the line based on data
                min_val_sc = min(scatter_data[prev_col_raw].min(), scatter_data[curr_col_raw].min())
                max_val_sc = max(scatter_data[prev_col_raw].max(), scatter_data[curr_col_raw].max())
                # Add a small buffer to the range
                range_buffer = (max_val_sc - min_val_sc) * 0.1
                line_start = min_val_sc - range_buffer
                line_end = max_val_sc + range_buffer

                fig_scatter.add_shape(type='line', x0=line_start, y0=line_start, x1=line_end, y1=line_end, line=dict(color='rgba(0,0,0,0.5)', dash='dash'))

                fig_scatter.update_layout(xaxis_title=f"{selected_index} (هفته قبل)", yaxis_title=f"{selected_index} (هفته جاری)", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                st.plotly_chart(fig_scatter, use_container_width=True)
            else:
                st.info(f"داده کافی برای رسم نمودار پراکندگی شاخص {selected_index} نیست ( نیاز به مقادیر هفته جاری و قبل).")

        st.markdown("---")

        st.markdown("**عملکرد مزارع (بر اساس مقدار هفته جاری):**")
        # Sort data for top/bottom lists, dropping rows where current value is NA
        df_sorted_dash = df_dash.sort_values(by=curr_col_raw, ascending=not higher_is_better_dash, na_position='last').dropna(subset=[curr_col_raw])

        col_top, col_bottom = st.columns(2)

        with col_top:
            st.markdown(f"**🟢 ۵ مزرعه برتر**")
            if not df_sorted_dash.empty:
                st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].head(5).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}" if pd.notna else "-"}), use_container_width=True, hide_index=True) # Hide index
            else:
                st.info("داده برای لیست برترین مزارع نیست.")

        with col_bottom:
            st.markdown(f"**🔴 ۵ مزرعه ضعیف‌تر**")
            if not df_sorted_dash.empty:
                # Sort descending for bottom list, then take the head
                st.dataframe(df_sorted_dash[['مزرعه', curr_col_raw, change_col_raw]].tail(5).sort_values(by=curr_col_raw, ascending=higher_is_better_dash).style.format({curr_col_raw: "{:.3f}", change_col_raw: "{:+.3f}" if pd.notna else "-"}), use_container_width=True, hide_index=True) # Hide index
            else:
                st.info("داده برای لیست ضعیف‌ترین مزارع نیست.")


if st.session_state.active_tab == "💬 چت‌بات": # Chatbot Tab
    st.subheader("💬 چت‌بات تحلیل وضعیت مزارع")
    st.info(f"در مورد وضعیت یک مزرعه خاص برای روز **{selected_day}** و با شاخص **{selected_index}** بپرسید. مثال: 'وضعیت مزرعه نیشکر ۱ چگونه است؟'")

    # Check if Gemini is available and ranking data is present for analysis
    if not st.session_state.gemini_available:
         st.warning("⚠️ چت‌بات هوش مصنوعی به دلیل خطای پیکربندی Gemini API غیرفعال است.", icon="⚠️")
    else:
        ranking_df_chat_check = st.session_state.ranking_data.get('df')
        if ranking_df_chat_check is None or ranking_df_chat_check.empty:
             st.warning("⚠️ پاسخ چت‌بات به داده‌های محاسبه‌شده در تب '📊 جدول رتبه‌بندی' وابسته است. لطفاً ابتدا به آن تب بروید.", icon="⚠️")

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input(f"در مورد مزارع برای {selected_day} بپرسید..."):
        # Add user message to chat history and display it
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        response_text = "متاسفم، نتوانستم درخواست شما را پردازش کنم." # Default response

        if not st.session_state.gemini_available:
             response_text = "AI در دسترس نیست. لطفاً از فعال بودن Gemini API اطمینان حاصل کنید."
        else:
             # Try to extract farm name from the prompt
             extracted_farm = extract_farm_name(prompt, available_farm_names_today)

             if extracted_farm:
                 # Get ranking data for analysis
                 ranking_df_chat = st.session_state.ranking_data.get('df')

                 if ranking_df_chat is None or ranking_df_chat.empty:
                      response_text = f"داده‌های شاخص '{selected_index}' برای روز '{selected_day}' محاسبه نشده است. لطفاً ابتدا به تب '📊 جدول رتبه‌بندی' بروید تا محاسبات انجام شود."
                 else:
                     # Find the row for the extracted farm
                     farm_data_row_chat = ranking_df_chat[ranking_df_chat['مزرعه'] == extracted_farm]

                     if not farm_data_row_chat.empty:
                         # Get the relevant data for the farm
                         farm_row_chat = farm_data_row_chat.iloc[0]
                         current_val = farm_row_chat.get(f'{selected_index}_curr')
                         previous_val = farm_row_chat.get(f'{selected_index}_prev')
                         change_val = farm_row_chat.get(f'{selected_index}_change')

                         # Perform AI analysis using Gemini
                         # Cache analysis results based on farm, index, and dates to avoid re-calling API for same params
                         analysis_params = (extracted_farm, selected_index, current_val, previous_val, change_val)
                         if st.session_state.gemini_analysis['params'] == analysis_params and st.session_state.gemini_analysis['text'] is not None:
                              print("Using cached Gemini analysis.")
                              analysis_text = st.session_state.gemini_analysis['text']
                              analysis_error = st.session_state.gemini_analysis['error']
                         else:
                             print("Generating new Gemini analysis.")
                             analysis_text, analysis_error = get_gemini_analysis(selected_index, extracted_farm, current_val, previous_val, change_val)
                             # Store the new analysis in session state
                             st.session_state.gemini_analysis = {'text': analysis_text, 'error': analysis_error, 'params': analysis_params}

                         if analysis_error:
                             response_text = f"خطا در تحلیل با هوش مصنوعی برای مزرعه '{extracted_farm}': {analysis_error}"
                         elif analysis_text:
                             response_text = f"**تحلیل وضعیت مزرعه {extracted_farm} ({selected_index} برای روز {selected_day}):**\n\n{analysis_text}"
                         else:
                             response_text = f"تحلیل وضعیت برای مزرعه '{extracted_farm}' با هوش مصنوعی تولید نشد (پاسخ خالی)."

                     else:
                         response_text = f"داده‌های شاخص '{selected_index}' برای مزرعه '{extracted_farm}' در جدول رتبه‌بندی روز '{selected_day}' یافت نشد."
             else:
                 # If no farm name was extracted
                 response_text = "نام مزرعه معتبر نیست یا در سوال شما مشخص نشده است. لطفاً نام یکی از مزارع موجود را ذکر کنید. مثال: 'وضعیت مزرعه **مزرعه ۱** چگونه است؟'"
                 # Add a few example farm names to help the user
                 example_farms = [f for f in available_farm_names_today if f != "همه مزارع"][:5]
                 if example_farms:
                     response_text += "\n\nنمونه مزارع امروز: " + ", ".join(example_farms)
                     if len(available_farm_names_today) > 6: response_text += "..."


        # Display the assistant's response and add to chat history
        with st.chat_message("assistant"):
            st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})

# --- Footer ---
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط اسماعیل کیانی")
st.sidebar.markdown("Streamlit | GEE | Geemap | Plotly | Gemini")

# Display API status in sidebar
if not st.session_state.gee_initialized:
    st.sidebar.error("🚨 Google Earth Engine غیرفعال.")
elif st.session_state.gee_initialized:
    st.sidebar.success("✅ Google Earth Engine فعال.")

if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
    st.sidebar.error("🚨 کلید Gemini نیست یا نامعتبر است.")
elif st.session_state.gemini_available:
    st.sidebar.success("✅ Gemini API فعال.")
else:
    st.sidebar.warning("⚠️ Gemini API غیرفعال.")

st.sidebar.warning("هشدار امنیتی: کلید API در کد است (فقط برای توسعه/تست).")

# --- END OF FILE ---
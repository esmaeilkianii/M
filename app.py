# --- START OF FILE app (67).py ---

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
import time # For potential delays if needed

# --- Gemini API Integration ---
import google.generativeai as genai

# WARNING: Storing API keys directly in code is insecure!
# Use environment variables or st.secrets in production.
# Replace "YOUR_GEMINI_API_KEY" with your actual key for this specific implementation.
GEMINI_API_KEY = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- PASTE YOUR KEY HERE

# --- Configure Gemini ---
try:
    if not GEMINI_API_KEY or GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        st.error("❌ کلید API Gemini تنظیم نشده است. لطفاً کلید معتبر را در کد قرار دهید.")
        st.stop() # Stop if key is missing
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash') # Or another suitable model
    print("Gemini API Configured Successfully.")
    gemini_available = True
except Exception as e:
    st.error(f"❌ خطا در پیکربندی Gemini API: {e}")
    st.warning("⚠️ تحلیل و پیشنهادات هوش مصنوعی در دسترس نخواهد بود.")
    gemini_available = False
    gemini_model = None # Ensure model is None if configuration fails

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Custom CSS for Persian text alignment and professional styling (remains the same)
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        body { direction: rtl; text-align: right; font-family: 'Vazirmatn', sans-serif !important; }
        .main { font-family: 'Vazirmatn', sans-serif; }
        h1, h2, h3 { font-family: 'Vazirmatn', sans-serif; color: #2c3e50; text-align: right; }
        .css-1xarl3l { font-family: 'Vazirmatn', sans-serif; background-color: #f8f9fa; border-radius: 10px; padding: 1rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stTabs [data-baseweb="tab-list"] { gap: 2px; direction: rtl; }
        .stTabs [data-baseweb="tab"] { height: 50px; padding: 10px 20px; background-color: #f8f9fa; border-radius: 5px 5px 0 0; font-family: 'Vazirmatn', sans-serif; font-weight: 600; }
        .dataframe { font-family: 'Vazirmatn', sans-serif; text-align: right; }
        .css-1d391kg { font-family: 'Vazirmatn', sans-serif; direction: rtl; }
        .stSelectbox label, .stDateInput label, .stTextInput label, .stTextArea label { text-align: right !important; width: 100%; }
        .stExpander > div > div > p { text-align: right; } /* Align text inside expander */
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
# IMPORTANT: Ensure this JSON file exists in your Hugging Face Space repository
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
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
available_days = sorted(farm_data_df['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته را انتخاب کنید:",
    options=available_days,
    index=0,
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

# --- Filter Data Based on Selected Day ---
filtered_farms_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

# --- Farm Selection ---
available_farms = sorted(filtered_farms_df['مزرعه'].unique())
farm_options = ["همه مزارع"] + available_farms
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه مورد نظر را انتخاب کنید:",
    options=farm_options,
    index=0,
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
)

# --- Index Selection (Updated) ---
index_options = {
    "NDVI": "شاخص تراکم پوشش گیاهی",
    "NDWI": "شاخص محتوای آبی گیاهان",
    "NDRE": "شاخص میزان ازت گیاه (لبه قرمز)",
    "LAI": "شاخص سطح برگ (تخمینی)",
    "CHL": "شاخص کلروفیل (تخمینی)",
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص مورد نظر برای نمایش:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})",
    index=0 # Default to NDVI
)

# --- Date Range Calculation ---
today = datetime.date.today()
persian_to_weekday = {
    "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
}
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

    st.sidebar.info(f"بازه زمانی فعلی: {start_date_current_str} تا {end_date_current_str}")
    st.sidebar.info(f"بازه زمانی قبلی: {start_date_previous_str} تا {end_date_previous_str}")

except KeyError:
    st.sidebar.error(f"نام روز هفته '{selected_day}' قابل شناسایی نیست.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
    st.stop()


# ==============================================================================
# Google Earth Engine Functions (Updated)
# ==============================================================================

# --- Cloud Masking Function for Sentinel-2 ---
def maskS2clouds(image):
    """Masks clouds in a Sentinel-2 SR image using the QA band and SCL."""
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
             qa.bitwiseAnd(cirrusBitMask).eq(0))

    scl = image.select('SCL')
    # Valid classes: 4 (Veg), 5 (Bare Soil), 6 (Water), 7 (Unclassified), 11 (Snow/Ice) - Keep 7? Maybe not.
    # Let's keep Veg, Bare Soil, Water: 4, 5, 6
    good_quality = scl.remap([4, 5, 6], [1, 1, 1], 0) # Map good classes to 1, others to 0

    # Scale optical bands (Needed for index calculations)
    opticalBands = image.select('B.*').multiply(0.0001)

    return image.addBands(opticalBands, None, True)\
                .updateMask(mask).updateMask(good_quality) # Apply both masks


# --- Index Calculation Functions (Updated) ---
def add_indices(image):
    """Calculates and adds NDVI, NDWI, NDRE, LAI, CHL bands."""
    # Ensure required bands exist and handle potential missing bands gracefully
    required_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11']
    # Check if all required bands are present
    # Note: GEE lazy evaluation means we can't easily check bands *before* calculation
    # We rely on GEE errors if a band is missing or operations fail.

    try:
        # NDVI: (NIR - Red) / (NIR + Red) | S2: (B8 - B4) / (B8 + B4)
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

        # NDWI (Gao version uses NIR & SWIR): (NIR - SWIR1) / (NIR + SWIR1) | S2: (B8 - B11) / (B8 + B11)
        # Often used for vegetation water content. McFeeters version (Green-NIR) is for surface water.
        ndwi = image.normalizedDifference(['B8', 'B11']).rename('NDWI')

        # NDRE: (NIR - RedEdge1) / (NIR + RedEdge1) | S2: (B8 - B5) / (B8 + B5)
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')

        # LAI (Leaf Area Index) - Simple estimation using NDVI (Needs calibration)
        # Placeholder: LAI proportional to NDVI. Adjust multiplier based on research/calibration.
        lai = ndvi.multiply(3.5).rename('LAI') # Simple empirical estimation

        # CHL (Chlorophyll Index) - Using Red Edge (e.g., CI_RedEdge = NIR/RE1 - 1) | S2: B8/B5 - 1
        # Ensure RedEdge band (B5) is not zero to avoid division errors
        re1_safe = image.select('B5').max(ee.Image(0.0001)) # Add small epsilon
        chl = image.expression('(NIR / RE1) - 1', {
            'NIR': image.select('B8'),
            'RE1': re1_safe
        }).rename('CHL')

        return image.addBands([ndvi, ndwi, ndre, lai, chl])
    except Exception as e:
        # If an error occurs (e.g., missing band), return the image without added indices
        # Or handle more gracefully if possible, but GEE makes this tricky pre-computation
        print(f"Warning: Could not calculate indices for image {image.id().getInfo()}: {e}")
        return image # Return original image if calculation fails


# --- Function to get processed image for a date range and geometry ---
# @st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True) # Re-enable caching if performance allows
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite.
    """
    try:
        # Increased timeout might be needed for complex calcs or large areas
        # ee.data.setDeadline(60000) # Example: 60 seconds timeout (optional)

        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))

        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date}."

        # Calculate indices *after* filtering. Handle potential errors inside add_indices.
        indexed_col = s2_sr_col.map(add_indices)

        # Select only images that likely have the calculated index band
        # This is a bit indirect; assumes if NDVI exists, others likely do too if bands were present.
        # A more robust way might involve checking band names after map, but that's complex in GEE.
        # indexed_col = indexed_col.filter(ee.Filter.listContains('system:band_names', index_name))

        # Create a median composite image
        median_image = indexed_col.median() # Use median

        # Select the specific index band *after* compositing
        # Check if the band exists in the final composite
        band_names = median_image.bandNames().getInfo()
        if index_name not in band_names:
             return None, f"شاخص '{index_name}' پس از پردازش در تصویر نهایی یافت نشد (احتمالاً به دلیل نبود باند ورودی یا خطای محاسبه)."

        output_image = median_image.select(index_name)

        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'required band' in error_details.lower() or 'not found' in error_details.lower():
                     error_message += f"\n(احتمالاً باند مورد نیاز برای شاخص {index_name} در تصاویر این بازه موجود نیست)"
                elif 'computation timed out' in error_details.lower():
                     error_message += "\n(زمان پردازش بیش از حد مجاز)"
                elif 'user memory limit exceeded' in error_details.lower():
                     error_message += "\n(حافظه مورد نیاز بیش از حد مجاز)"
        except Exception: pass
        # st.error(error_message) # Don't show error here, return it
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"
        # st.error(error_message) # Don't show error here, return it
        return None, error_message


# --- Function to get time series data for a point ---
# @st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True) # Re-enable caching if needed
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets a time series of a specified index for a point geometry."""
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices)) # Add all indices

        def extract_value(image):
            # Ensure the index band exists before trying to reduce
            if index_name in image.bandNames().getInfo():
                value = image.select(index_name).reduceRegion(
                    reducer=ee.Reducer.first(), # Use 'first' or 'mean'
                    geometry=_point_geom,
                    scale=10 # S2 scale
                ).get(index_name)
                return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})
            else:
                # Return null feature if the band doesn't exist in this specific image
                return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: None})


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
        error_message = f"خطای GEE در دریافت سری زمانی ({index_name}): {e}"
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی ({index_name}): {e}\n{traceback.format_exc()}"
        return pd.DataFrame(columns=['date', index_name]), error_message


# ==============================================================================
# Gemini AI Analysis Function
# ==============================================================================

# @st.cache_data(show_spinner="🧠 در حال تحلیل با هوش مصنوعی...", persist=True) # Cache AI response for same inputs
def get_gemini_analysis(_index_name, _farm_name, _current_val, _previous_val, _change_val):
    """Generates analysis and recommendations using Gemini API."""
    if not gemini_available or gemini_model is None:
        return "تحلیل هوش مصنوعی به دلیل خطا در پیکربندی API در دسترس نیست.", None

    if pd.isna(_current_val) or pd.isna(_previous_val) or pd.isna(_change_val):
         return "داده‌های کافی برای تحلیل (مقادیر فعلی، قبلی و تغییر) وجود ندارد.", None

    # Format values for the prompt
    current_str = f"{_current_val:.3f}"
    previous_str = f"{_previous_val:.3f}"
    change_str = f"{_change_val:.3f}"
    
    # Define index interpretations for the prompt
    index_interpretations = {
        "NDVI": "شاخص تراکم و سلامت پوشش گیاهی است. مقادیر بالاتر (نزدیک به ۱) نشان‌دهنده پوشش گیاهی متراکم‌تر و سالم‌تر است.",
        "NDWI": "شاخص محتوای آب در برگ گیاهان است. مقادیر بالاتر نشان‌دهنده رطوبت بیشتر در گیاه است.",
        "NDRE": "شاخص مرتبط با محتوای کلروفیل و نیتروژن در گیاه است (حساس به تغییرات در مراحل میانی و پایانی رشد). مقادیر بالاتر عموماً بهتر است.",
        "LAI": "شاخص سطح برگ (نسبت سطح کل برگ به سطح زمین) است. مقادیر بالاتر نشان‌دهنده پوشش گیاهی بیشتر و پتانسیل فتوسنتز بالاتر است.",
        "CHL": "شاخص تخمینی میزان کلروفیل در برگ است. مقادیر بالاتر نشان‌دهنده کلروفیل بیشتر و سلامت بهتر گیاه است."
    }
    
    interpretation = index_interpretations.get(_index_name, f"شاخص {_index_name}")

    prompt = f"""
    شما یک دستیار متخصص کشاورزی برای تحلیل داده‌های ماهواره‌ای مزارع نیشکر هستید.
    برای مزرعه نیشکر با نام "{_farm_name}"، شاخص "{_index_name}" تحلیل شده است.
    {interpretation}

    مقدار این شاخص در هفته جاری: {current_str}
    مقدار این شاخص در هفته قبل: {previous_str}
    میزان تغییر نسبت به هفته قبل: {change_str}

    وظایف شما:
    1.  **تحلیل وضعیت:** به زبان فارسی ساده توضیح دهید که این تغییر در مقدار شاخص {_index_name} چه معنایی برای وضعیت سلامت و رشد نیشکر در این مزرعه دارد. (مثلاً آیا بهبود یافته؟ آیا دچار تنش شده؟ وضعیت پایدار است؟)
    2.  **پیشنهاد آبیاری:** بر اساس این تغییر و ماهیت شاخص، یک پیشنهاد کلی و اولیه برای مدیریت آبیاری در هفته پیش رو ارائه دهید. (مثلاً نیاز به افزایش/کاهش/حفظ روند فعلی آبیاری)
    3.  **پیشنهاد کوددهی:** بر اساس این تغییر و ماهیت شاخص (به‌خصوص اگر NDRE یا CHL باشد)، یک پیشنهاد کلی و اولیه برای مدیریت کوددهی (به‌ویژه نیتروژن) ارائه دهید. برای سایر شاخص‌ها، اشاره کنید که نیاز به بررسی بیشتری است.

    نکات مهم:
    -   تحلیل و پیشنهادات باید **فقط** بر اساس اطلاعات داده شده (تغییر یک شاخص) باشد.
    -   زبان نوشتار باید رسمی و علمی اما قابل فهم برای کارشناس مزرعه باشد.
    -   پاسخ کوتاه و متمرکز بر تحلیل و پیشنهادات باشد.
    -   پاسخ به زبان فارسی باشد.

    فرمت پاسخ:
    **تحلیل وضعیت:** [توضیح شما]
    **پیشنهاد آبیاری:** [پیشنهاد شما]
    **پیشنهاد کوددهی:** [پیشنهاد شما]
    """

    try:
        response = gemini_model.generate_content(prompt)
        # Add basic safety check if needed (though newer models handle this better)
        # if not response.candidates or not response.candidates[0].content.parts:
        #     return "مدل هوش مصنوعی پاسخی ارائه نکرد. (ممکن است محتوا ناامن تشخیص داده شده باشد)", None
        
        analysis_text = response.text
        return analysis_text, None # Return analysis and no error
    except Exception as e:
        error_message = f"خطا در ارتباط با Gemini API: {e}"
        st.error(error_message) # Show error in the UI as well
        return "خطا در تولید تحلیل توسط هوش مصنوعی.", error_message


# ==============================================================================
# Main Panel Display
# ==============================================================================

# --- Get Selected Farm Geometry and Details ---
selected_farm_details = None
selected_farm_geom = None
map_center_lat = INITIAL_LAT
map_center_lon = INITIAL_LON
map_zoom = INITIAL_ZOOM

if selected_farm_name == "همه مزارع":
    min_lon, min_lat = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
    max_lon, max_lat = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
    selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    map_center_lat = filtered_farms_df['عرض جغرافیایی'].mean()
    map_center_lon = filtered_farms_df['طول جغرافیایی'].mean()
    map_zoom = INITIAL_ZOOM # Keep initial zoom for overview
    st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
    st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
else:
    selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat = selected_farm_details['عرض جغرافیایی']
    lon = selected_farm_details['طول جغرافیایی']
    selected_farm_geom = ee.Geometry.Point([lon, lat])
    map_center_lat = lat
    map_center_lon = lon
    map_zoom = 14 # Zoom closer for single farm
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


# --- Map Display ---
st.markdown("---")
st.subheader(" نقشه وضعیت مزارع")

# Define visualization parameters based on the selected index (Updated)
vis_params = {
    'NDVI': {'min': 0.0, 'max': 0.9, 'palette': 'RdYlGn'}, # Standard NDVI range and palette
    'NDWI': {'min': -0.2, 'max': 0.6, 'palette': ['#d7191c', '#fdae61', '#ffffbf', '#abd9e9', '#2c7bb6']}, # Diverging for moisture: Red(dry)->Yellow->Blue(wet)
    'NDRE': {'min': 0.0, 'max': 0.6, 'palette': 'Purples'}, # Often lower range than NDVI, Purples palette
    'LAI': {'min': 0, 'max': 7, 'palette': 'YlGn'}, # 0 to ~7 is common for crops, YlGn palette
    'CHL': {'min': 0, 'max': 10, 'palette': 'YlOrBr'}, # CIrededge range, YlOrBr palette (Yellow->Brown = low->high stress/less Chl?) Let's reverse it: BrOrangeYl
    'CHL': {'min': 0, 'max': 10, 'palette': ['#b35806','#f1a340','#fee0b6','#d8daeb','#998ec3','#542788']}, # Better: Brown(low Chl/stress) -> Purple(high Chl)
}

# Create a geemap Map instance
m = geemap.Map(
    location=[map_center_lat, map_center_lon],
    zoom=map_zoom,
    add_google_map=False # Start clean
)
m.add_basemap("HYBRID") # Add Google Satellite Hybrid basemap

# Get the processed image for the current week
if selected_farm_geom:
    gee_image_current, error_msg_current = get_processed_image(
        selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
    )

    if gee_image_current:
        try:
            current_vis_param = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': 'gray'}) # Default gray if not found
            m.addLayer(
                gee_image_current,
                current_vis_param,
                f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
            )

            # --- Add Custom Legend ---
            # Use user-provided descriptions
            legend_dict = {
                'NDVI': ("NDVI (شاخص تراکم پوشش گیاهی)", "رنگ سبز بیانگر محصول متراکم و سالم و رنگ قرمز نشان‌دهنده‌ی محصول کم‌پشت و پراکنده است."),
                'NDWI': ("NDWI (شاخص محتوای آبی گیاهان)", "رنگ آبی بیشتر نشان‌دهنده محتوای آبی بیشتر و رنگ قرمز نشان‌دهنده کم‌آبی است."),
                'NDRE': ("NDRE (شاخص میزان ازت گیاه)", "رنگ بنفش نشان‌دهنده میزان زیاد ازت/کلروفیل و رنگ روشن‌تر نشان‌دهنده کاهش آن در گیاه است."),
                'LAI': ("LAI (شاخص گیاهی سطح برگ)", "رنگ سبز پررنگ‌تر نشان‌دهنده سطح برگ بیشتر در ناحیه است."),
                'CHL': ("CHL (شاخص کلروفیل)", "رنگ بنفش/تیره نشان‌دهنده کلروفیل بیشتر است و رنگ قهوه‌ای/روشن نشان‌دهنده کاهش کلروفیل یا تنش است.")
            }

            legend_title, legend_desc = legend_dict.get(selected_index, (selected_index, "مقادیر پایین به بالا"))
            palette = current_vis_param.get('palette', [])
            min_val = current_vis_param.get('min', 0)
            max_val = current_vis_param.get('max', 1)

            # Create a simple gradient or categorical legend based on palette
            legend_html = f'''
            <div style="position: fixed; bottom: 50px; right: 10px; z-index: 1000; background-color: rgba(255, 255, 255, 0.8); padding: 10px; border: 1px solid grey; border-radius: 5px; font-family: 'Vazirmatn', sans-serif; font-size: 12px; text-align: right;">
                <p style="margin: 0 0 5px 0; font-weight: bold;">{legend_title}</p>
                <p style="margin: 0 0 10px 0; font-size: 11px;">{legend_desc}</p>
            '''
            # Add color scale bar (simple version)
            if isinstance(palette, list) and len(palette) > 1:
                gradient = f"linear-gradient(to top, {', '.join(palette)})"
                legend_html += f'<div style="height: 100px; width: 20px; background: {gradient}; border: 1px solid #ccc; display: inline-block; margin-left: 5px;"></div>'
                legend_html += f'<div style="display: inline-block; vertical-align: top; height: 100px; position: relative;">'
                legend_html += f'<span style="position: absolute; top: 0;">{max_val:.1f} (بالا)</span>'
                legend_html += f'<span style="position: absolute; bottom: 0;">{min_val:.1f} (پایین)</span>'
                legend_html += f'</div>'
            elif isinstance(palette, str): # If palette name is given (like RdYlGn)
                 legend_html += f'<div style="text-align: center;">(مقیاس رنگی: {palette})<br>کم ← زیاد</div>' # Placeholder if gradient is hard

            legend_html += '</div>'
            m.get_root().html.add_child(folium.Element(legend_html))

            # Add markers
            if selected_farm_name == "همه مزارع":
                 for idx, farm in filtered_farms_df.iterrows():
                     folium.Marker(
                         location=[farm['عرض جغرافیایی'], farm['طول جغرافیایی']],
                         popup=f"مزرعه: {farm['مزرعه']}\nکانال: {farm['کانال']}\nاداره: {farm['اداره']}",
                         tooltip=farm['مزرعه'],
                         icon=folium.Icon(color='blue', icon='info-sign')
                     ).add_to(m)
            else:
                 folium.Marker(
                     location=[lat, lon],
                     popup=f"مزرعه: {selected_farm_name}\n{selected_index} (جاری): در حال محاسبه...",
                     tooltip=selected_farm_name,
                     icon=folium.Icon(color='red', icon='star')
                 ).add_to(m)

            m.add_layer_control()

        except Exception as map_err:
            st.error(f"خطا در افزودن لایه به نقشه: {map_err}")
            st.error(traceback.format_exc())
    else:
        st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")

# Display the map
st_folium(m, width=None, height=500, use_container_width=True)
st.caption("راهنما: برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها (بالا سمت راست نقشه) برای تغییر نقشه پایه یا خاموش/روشن کردن لایه شاخص استفاده کنید.")
st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


# --- Time Series Chart ---
st.markdown("---")
st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

if selected_farm_name == "همه مزارع":
    st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
elif selected_farm_geom and isinstance(selected_farm_geom, ee.Geometry.Point):
    timeseries_end_date = today.strftime('%Y-%m-%d')
    timeseries_start_date = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d') # Last 6 months

    ts_df, ts_error = get_index_time_series(
        selected_farm_geom,
        selected_index,
        start_date=timeseries_start_date,
        end_date=timeseries_end_date
    )

    if ts_error:
        st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
    elif not ts_df.empty:
        # Ensure index column is numeric for plotting
        ts_df[selected_index] = pd.to_numeric(ts_df[selected_index], errors='coerce')
        ts_df.dropna(subset=[selected_index], inplace=True)
        if not ts_df.empty:
            st.line_chart(ts_df[selected_index])
            st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 6 ماه گذشته (نقاط داده بر اساس تصاویر ماهواره‌ای بدون ابر موجود است).")
        else:
             st.info(f"داده معتبر عددی برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
    else:
        st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
elif not isinstance(selected_farm_geom, ee.Geometry.Point):
     st.warning("نمودار سری زمانی فقط برای مزارع منفرد (نقطه) قابل نمایش است.")


# --- Ranking Table and AI Analysis ---
st.markdown("---")
st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

# Use a session state variable to store ranking results to avoid recalculating on every interaction
if 'ranking_data' not in st.session_state:
    st.session_state.ranking_data = {'df': pd.DataFrame(), 'errors': [], 'params': None}

# Function to calculate rankings (modified to reduce direct GEE calls if possible)
# @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True) # Cache might be tricky with GEE objects/errors
def calculate_farm_indices(farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
    """Calculates the average index value for the current and previous week for a list of farms."""
    results = []
    errors = []
    total_farms = len(farms_df)
    # progress_bar = st.progress(0) # Progress bar can be slow with many small GEE calls

    # Pre-fetch images if possible (might time out for large areas/long ranges)
    # This is complex to manage correctly with point-based reduction.
    # Sticking to per-farm calculation for now.

    status_placeholder = st.empty() # Placeholder for status updates

    for i, (idx, farm) in enumerate(farms_df.iterrows()):
        status_placeholder.info(f"در حال پردازش مزرعه {i+1}/{total_farms}: {farm['مزرعه']}...")
        farm_name = farm['مزرعه']
        lat = farm['عرض جغرافیایی']
        lon = farm['طول جغرافیایی']
        point_geom = ee.Geometry.Point([lon, lat])

        def get_mean_value(start, end):
            try:
                # Use the function that returns image and error msg
                image, error_img = get_processed_image(point_geom, start, end, index_name)
                if image:
                    mean_dict = image.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=point_geom,
                        scale=10
                    ).getInfo()
                    # Check if index_name is actually in the result
                    if mean_dict and index_name in mean_dict:
                         return mean_dict.get(index_name), None
                    elif mean_dict is None:
                         return None, "ReduceRegion returned None."
                    else:
                         return None, f"شاخص '{index_name}' در نتیجه ReduceRegion یافت نشد."
                else:
                    # If image is None, return None value and the error from get_processed_image
                    return None, error_img or "تصویری برای پردازش یافت نشد."
            except ee.EEException as e:
                 # Catch GEE specific errors during reduceRegion/getInfo
                 err_detail = f"EE Error: {e}"
                 try: # Try to get more specific GEE error details
                      err_detail = e.args[0] if e.args else str(e)
                 except: pass
                 return None, f"خطای GEE در محاسبه مقدار: {err_detail}"
            except Exception as e:
                 # Catch other errors
                 return None, f"خطای ناشناخته در محاسبه مقدار: {e}"

        # Calculate for current week
        current_val, err_curr = get_mean_value(start_curr, end_curr)
        if err_curr: errors.append(f"{farm_name} (جاری: {start_curr} تا {end_curr}): {err_curr}")

        # Calculate for previous week
        previous_val, err_prev = get_mean_value(start_prev, end_prev)
        if err_prev: errors.append(f"{farm_name} (قبل: {start_prev} تا {end_prev}): {err_prev}")

        # Calculate change
        change = None
        if current_val is not None and previous_val is not None:
            try:
                 # Ensure they are floats before subtracting
                 change = float(current_val) - float(previous_val)
            except (TypeError, ValueError):
                 change = None # Handle if values are not numeric

        results.append({
            'مزرعه': farm_name,
            'کانال': farm.get('کانال', 'N/A'),
            'اداره': farm.get('اداره', 'N/A'),
            f'{index_name}_curr': current_val, # Store raw values
            f'{index_name}_prev': previous_val,
            f'{index_name}_change': change
        })
        # Update progress bar (removed for potential performance gain)
        # progress_bar.progress((i + 1) / total_farms)
        time.sleep(0.05) # Small delay to prevent hitting GEE limits too hard?

    # progress_bar.empty()
    status_placeholder.success(f"محاسبه شاخص {index_name} برای {total_farms} مزرعه کامل شد.")
    time.sleep(2)
    status_placeholder.empty() # Clear status message

    return pd.DataFrame(results), errors

# Define parameters for caching check
current_params = (selected_index, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str, selected_day)

# Check if calculation is needed
if st.session_state.ranking_data['params'] != current_params:
    print(f"Recalculating ranking for: {current_params}") # Debug print
    ranking_df_raw, calculation_errors = calculate_farm_indices(
        filtered_farms_df,
        selected_index,
        start_date_current_str,
        end_date_current_str,
        start_date_previous_str,
        end_date_previous_str
    )
    st.session_state.ranking_data['df'] = ranking_df_raw
    st.session_state.ranking_data['errors'] = calculation_errors
    st.session_state.ranking_data['params'] = current_params # Store current parameters
else:
    print("Using cached ranking data.") # Debug print
    ranking_df_raw = st.session_state.ranking_data['df']
    calculation_errors = st.session_state.ranking_data['errors']


# Display errors if any
if calculation_errors:
    with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها", expanded=False):
        st.warning(f"تعداد کل خطاها: {len(calculation_errors)}")
        # Show unique errors to avoid repetition
        unique_errors = sorted(list(set(calculation_errors)))
        for i, error in enumerate(unique_errors):
            st.error(f"- {error}")
            if i > 20: # Limit displayed unique errors
                 st.warning(f"... و {len(unique_errors) - i} خطای منحصربفرد دیگر.")
                 break

if not ranking_df_raw.empty:
    # Create display copy
    ranking_df_display = ranking_df_raw.copy()
    
    # Rename columns for display
    ranking_df_display = ranking_df_display.rename(columns={
        f'{selected_index}_curr': f'{selected_index} (هفته جاری)',
        f'{selected_index}_prev': f'{selected_index} (هفته قبل)',
        f'{selected_index}_change': 'تغییر'
    })

    # Define status based on change (Most indices: higher is better)
    def determine_status(change_val, index_name):
        # All requested indices (NDVI, NDWI, NDRE, LAI, CHL) generally mean 'better' when higher
        if pd.isna(change_val):
            return "بدون داده" # Status: No data / Cannot compare

        threshold = 0.03 # Define a threshold for significant change (adjust as needed)

        if change_val > threshold:
            return "بهبود / رشد" # Status: Positive change
        elif change_val < -threshold:
            return "کاهش / تنش" # Status: Negative change
        else:
            return "ثابت / بدون تغییر" # Status: Neutral / Stable

    ranking_df_display['وضعیت'] = ranking_df_display['تغییر'].apply(lambda x: determine_status(x, selected_index))

    # Sort table
    # Generally sort descending for these indices (higher = better rank)
    ranking_df_sorted = ranking_df_display.sort_values(
        by=f'{selected_index} (هفته جاری)',
        ascending=False,
        na_position='last'
    ).reset_index(drop=True)

    # Add Rank
    ranking_df_sorted.index = ranking_df_sorted.index + 1
    ranking_df_sorted.index.name = 'رتبه'

    # Format numbers for display
    cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
    for col in cols_to_format:
        if col in ranking_df_sorted.columns:
             ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x))


    # Display the table
    st.dataframe(ranking_df_sorted[[
        'مزرعه', 'کانال', 'اداره',
        f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'وضعیت'
        ]], use_container_width=True)

    # --- Display Gemini AI Analysis for Selected Farm ---
    if selected_farm_name != "همه مزارع" and gemini_available:
        st.markdown("---")
        st.subheader(f"🧠 تحلیل هوش مصنوعی و پیشنهادات برای مزرعه: {selected_farm_name}")

        # Find the data for the selected farm in the raw results
        farm_analysis_data = ranking_df_raw[ranking_df_raw['مزرعه'] == selected_farm_name]

        if not farm_analysis_data.empty:
            farm_row = farm_analysis_data.iloc[0]
            current_val = farm_row.get(f'{selected_index}_curr')
            previous_val = farm_row.get(f'{selected_index}_prev')
            change_val = farm_row.get(f'{selected_index}_change')

            # Call Gemini function (use caching maybe)
            analysis_text, analysis_error = get_gemini_analysis(
                selected_index,
                selected_farm_name,
                current_val,
                previous_val,
                change_val
            )

            if analysis_error:
                 st.error(f"خطا در تولید تحلیل: {analysis_error}")
            elif analysis_text:
                 st.markdown(analysis_text) # Display the formatted text from Gemini
                 st.caption("توجه: این تحلیل و پیشنهادات توسط هوش مصنوعی و صرفاً بر اساس تغییرات شاخص انتخاب شده ارائه شده است. همیشه داده‌ها را با مشاهدات میدانی و دانش کارشناسی تلفیق کنید.")
            else:
                 st.info("تحلیلی توسط هوش مصنوعی ارائه نشد.")
        else:
             st.warning(f"داده‌های محاسبه شده برای مزرعه '{selected_farm_name}' جهت تحلیل یافت نشد.")
    elif selected_farm_name != "همه مزارع" and not gemini_available:
         st.warning("⚠️ تحلیل هوش مصنوعی به دلیل عدم پیکربندی صحیح API در دسترس نیست.")

    # --- Summary Stats ---
    st.markdown("---")
    st.subheader("📊 خلاصه وضعیت مزارع")
    status_counts = ranking_df_sorted['وضعیت'].value_counts()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        count_pos = status_counts.get("بهبود / رشد", 0)
        st.metric("🟢 بهبود / رشد", count_pos)
    with col2:
        count_neu = status_counts.get("ثابت / بدون تغییر", 0)
        st.metric("⚪ ثابت / بدون تغییر", count_neu)
    with col3:
        count_neg = status_counts.get("کاهش / تنش", 0)
        st.metric("🔴 کاهش / تنش", count_neg)
    with col4:
        count_nan = status_counts.get("بدون داده", 0)
        st.metric("⚫️ بدون داده", count_nan)

    st.info(f"""
    **راهنمای وضعیت:**
    - **🟢 بهبود / رشد**: مزارعی که شاخص {selected_index} آنها نسبت به هفته قبل افزایش معناداری داشته است.
    - **⚪ ثابت / بدون تغییر**: مزارعی که تغییر معناداری در شاخص {selected_index} نداشته‌اند.
    - **🔴 کاهش / تنش**: مزارعی که شاخص {selected_index} آنها نسبت به هفته قبل کاهش معناداری داشته است.
    - **⚫️ بدون داده**: مزارعی که امکان مقایسه مقدار شاخص در دو هفته وجود نداشته است.
    """)

    # --- Download Button ---
    try:
        csv_data = ranking_df_sorted.to_csv(index=True, encoding='utf-8-sig') # Use utf-8-sig for Excel compatibility
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)",
            data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
            mime='text/csv',
        )
    except Exception as e:
        st.error(f"خطا در ایجاد فایل دانلود: {e}")

else:
    st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی و برای این روز یافت نشد یا محاسبه نشد.")


st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط اسماعیل کیانی")
st.sidebar.markdown("با استفاده از Streamlit, Google Earth Engine, geemap و Google Gemini")
st.sidebar.warning("🚨 هشدار: کلید API Gemini مستقیماً در کد قرار داده شده است که ناامن است. در محیط عملیاتی از روش‌های امن‌تر استفاده کنید.")

# --- END OF FILE ---
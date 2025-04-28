import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import datetime
import plotly.express as px
import plotly.graph_objects as go # Add plotly graph objects
import os
from io import BytesIO
import requests # Needed for getThumbUrl download
import traceback  # Add missing traceback import
from streamlit_folium import st_folium  # Add missing st_folium import
import base64
import google.generativeai as genai # Gemini API

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Custom CSS for Persian text alignment and professional styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        
        /* Main container */
        .main {
            font-family: 'Vazirmatn', sans-serif;
        }
        
        /* Headers */
        h1, h2, h3 {
            font-family: 'Vazirmatn', sans-serif;
            color: #2c3e50;
            text-align: right;
        }
        
        /* Metrics */
        .css-1xarl3l {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            direction: rtl;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 20px;
            background-color: #f8f9fa;
            border-radius: 5px 5px 0 0;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
        }
        
        /* Tables */
        .dataframe {
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
        }
        
        /* Sidebar */
        .css-1d391kg {
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
        }
        
        /* Custom status badges */
        .status-badge {
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
        }
        .status-positive {
            background-color: #d4edda;
            color: #155724;
        }
        .status-neutral {
            background-color: #fff3cd;
            color: #856404;
        }
        .status-negative {
            background-color: #f8d7da;
            color: #721c24;
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
CSV_FILE_PATH = 'برنامه_ریزی_با_مختصات (1).csv'
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
        # Basic validation
        required_cols = ['مزرعه', 'longitude', 'latitude', 'روز', 'گروه']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            st.stop()
        # Convert coordinate columns to numeric, coercing errors
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')

        # Drop rows where essential coordinates are actually missing after coercion
        initial_count = len(df)
        df = df.dropna(subset=['longitude', 'latitude', 'روز'])
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            st.warning(f"⚠️ {dropped_count} رکورد به دلیل مقادیر نامعتبر یا خالی در ستون‌های مختصات یا روز حذف شدند.")


        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات یا روز).")
            st.stop()

        # Ensure 'روز' is string type and normalize spaces (including non-breaking spaces)
        df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        # Ensure 'گروه' is treated appropriately (e.g., as string or category)
        df['گروه'] = df['گروه'].astype(str).str.strip()


        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت بارگذاری شد.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های مزارع را در مسیر صحیح قرار دهید.")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.error(traceback.format_exc())
        st.stop()

# --- Load Analysis Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های محاسبات...")
def load_analysis_data(csv_path='محاسبات 2.csv'):
    """Loads and preprocesses data from the analysis CSV file."""
    try:
        # Read the raw lines to identify sections
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Find the headers and split points
        headers_indices = [i for i, line in enumerate(lines) if 'اداره,سن,' in line or 'تولید,سن,' in line]
        if len(headers_indices) < 2:
            # Fallback if only one section header is found (less robust)
            headers_indices = [i for i, line in enumerate(lines) if ',سن,' in line]
            if len(headers_indices) < 1:
                st.error(f"❌ ساختار فایل '{csv_path}' قابل شناسایی نیست. هدرهای مورد انتظار یافت نشد.")
                st.stop()
            st.warning("⚠️ فقط یک بخش داده در فایل محاسبات شناسایی شد.")
            section1_start = headers_indices[0] + 1
            section2_start = None
            # Try to find a likely separator (e.g., a mostly blank line)
            blank_lines = [i for i, line in enumerate(lines[section1_start:]) if len(line.strip()) < 5]
            if blank_lines:
                section2_start = section1_start + blank_lines[0] + 1 # Heuristic guess
        else:
            section1_start = headers_indices[0] + 1
            section2_start = headers_indices[1] + 1 # Line after the second header

        # Read the first section (Area)
        df_area = pd.read_csv(csv_path, skiprows=headers_indices[0], nrows=(section2_start - section1_start - 2) if section2_start else None, encoding='utf-8')
        df_area.rename(columns={'اداره': 'مساحت_اداره'}, inplace=True) # Rename first col for clarity
        df_area.rename(columns={df_area.columns[0]: 'اداره'}, inplace=True) # The actual 'اداره' column might be the first if unnamed

        # Read the second section (Production) if found
        df_prod = None
        if section2_start:
            # Skip rows until the second header, read until end or grand total
            end_row_prod = None
            for i in range(section2_start, len(lines)):
                if "Grand Total" in lines[i]:
                    end_row_prod = i
                    break
            nrows_prod = (end_row_prod - section2_start) if end_row_prod else None
            df_prod = pd.read_csv(csv_path, skiprows=section2_start-1, nrows=nrows_prod, encoding='utf-8') # Read including header
            # The first column name in the second section is actually 'تولید', needs renaming
            df_prod.rename(columns={df_prod.columns[0]: 'اداره'}, inplace=True)


        # --- Preprocessing Function ---
        def preprocess_df(df, section_name):
            if df is None:
                return None
            # Ensure 'اداره' is the first column if it got misplaced
            if 'اداره' not in df.columns and len(df.columns) > 0:
                 df.rename(columns={df.columns[0]: 'اداره'}, inplace=True)

            # Check for required columns
            if not all(col in df.columns for col in ['اداره', 'سن']):
                 st.warning(f"⚠️ ستون های ضروری 'اداره' یا 'سن' در بخش '{section_name}' یافت نشد.")
                 return None

            # Forward fill 'اداره'
            df['اداره'] = df['اداره'].ffill()

            # Filter out 'total' and 'Grand Total' rows in 'سن' and 'اداره'
            df = df[~df['سن'].astype(str).str.contains('total', case=False, na=False)]
            df = df[~df['اداره'].astype(str).str.contains('total|دهخدا', case=False, na=False)] # Filter Grand Total/summary rows in اداره

            # Remove rows where 'اداره' is NaN after ffill (first rows before a number)
            df = df.dropna(subset=['اداره'])

             # Convert 'اداره' to integer where possible
            try:
                df['اداره'] = pd.to_numeric(df['اداره'], errors='coerce')
                df = df.dropna(subset=['اداره']) # Drop if conversion failed
                df['اداره'] = df['اداره'].astype(int)
            except Exception:
                st.warning(f"⚠️ امکان تبدیل ستون 'اداره' به عدد صحیح در بخش '{section_name}' وجود ندارد.")
                # Keep as is if conversion fails

            # Convert numeric columns, coerce errors to NaN
            value_cols = [col for col in df.columns if col not in ['اداره', 'سن', 'درصد', 'Grand Total']]
            for col in value_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Drop Grand Total and درصد columns if they exist
            df = df.drop(columns=['Grand Total', 'درصد'], errors='ignore')

            # Set multi-index for easier access
            if 'اداره' in df.columns and 'سن' in df.columns:
                df = df.set_index(['اداره', 'سن'])
            else:
                 st.warning(f"⚠️ امکان تنظیم ایندکس چندگانه در بخش '{section_name}' وجود ندارد.")


            return df

        df_area_processed = preprocess_df(df_area, "مساحت")
        df_prod_processed = preprocess_df(df_prod, "تولید")


        st.success(f"✅ داده‌های محاسبات با موفقیت بارگذاری و پردازش شد.")
        return df_area_processed, df_prod_processed

    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های محاسبات را در مسیر صحیح قرار دهید.")
        return None, None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل محاسبات CSV: {e}")
        st.error(traceback.format_exc()) # Print detailed error
        return None, None


# Initialize GEE and Load Data
if initialize_gee():
    farm_data_df = load_farm_data()

# Load Analysis Data
analysis_area_df, analysis_prod_df = load_analysis_data()

# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
available_days = sorted(farm_data_df['روز'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته را انتخاب کنید:",
    options=available_days,
    index=0, # Default to the first day
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

# --- Filter Data Based on Selected Day ---
filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

# --- Farm Selection ---
available_farms = sorted(filtered_farms_df['مزرعه'].unique())
# Add an option for "All Farms"
farm_options = ["همه مزارع"] + available_farms
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه مورد نظر را انتخاب کنید:",
    options=farm_options,
    index=0, # Default to "All Farms"
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
)

# --- Index Selection ---
index_options = {
    "NDVI": "شاخص پوشش گیاهی تفاضلی نرمال شده",
    "EVI": "شاخص پوشش گیاهی بهبود یافته",
    "NDMI": "شاخص رطوبت تفاضلی نرمال شده (وضعیت آبی)",
    "ET": "تبخیر و تعرق واقعی (ماهانه)", # Added ET
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
    # Add more indices if needed and implemented
    # "Biomass": "زیست‌توده (تخمینی)",
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص مورد نظر برای نمایش روی نقشه:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})",
    index=0 # Default to NDVI
)

# --- Date Range Calculation ---
today = datetime.date.today()
# Find the most recent date corresponding to the selected day of the week
# Map Persian day names to Python's weekday() (Monday=0, Sunday=6) - Adjust if needed
persian_to_weekday = {
    "شنبه": 5,
    "یکشنبه": 6,
    "دوشنبه": 0,
    "سه شنبه": 1, # Handle potential space variations (normalized in loading)
    "چهارشنبه": 2,
    "پنجشنبه": 3,
    "جمعه": 4,
}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_ago = (today.weekday() - target_weekday + 7) % 7
    if days_ago == 0: # If today is the selected day, use today
         end_date_current = today
    else:
         end_date_current = today - datetime.timedelta(days=days_ago)

    start_date_current = end_date_current - datetime.timedelta(days=6)
    end_date_previous = start_date_current - datetime.timedelta(days=1)
    start_date_previous = end_date_previous - datetime.timedelta(days=6)

    # Convert to strings for GEE
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
# Google Earth Engine Functions
# ==============================================================================

# --- Cloud Masking Function for Sentinel-2 ---
def maskS2clouds(image):
    """Masks clouds in a Sentinel-2 SR image using the QA band."""
    qa = image.select('QA60')
    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    # Both flags should be set to zero, indicating clear conditions.
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
             qa.bitwiseAnd(cirrusBitMask).eq(0))
    # Also mask based on SCL band if available (more robust)
    scl = image.select('SCL')
    # Keep 'Vegetation', 'Not Vegetated', 'Water', 'Snow/Ice', 'Bare Soil'
    # Mask out 'Cloud Medium Probability', 'Cloud High Probability', 'Cirrus', 'Cloud Shadow'
    good_quality = scl.remap([4, 5, 6, 7, 11], [1, 1, 1, 1, 1], 0) # Map good classes to 1, others to 0

    # Scale and offset factors for Sentinel-2 SR bands
    opticalBands = image.select('B.*').multiply(0.0001)
    
    # Remove thermal band processing as it's not available in the dataset
    # thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0) # If using thermal

    return image.addBands(opticalBands, None, True)\
                .updateMask(mask).updateMask(good_quality) # Apply both masks


# --- Index Calculation Functions ---
def add_indices(image):
    """Calculates and adds various indices as bands to an image."""
    # NDVI: (NIR - Red) / (NIR + Red) | Sentinel-2: (B8 - B4) / (B8 + B4)
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    # EVI: 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1) | S2: 2.5 * (B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1)
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }).rename('EVI')

    # NDMI (Normalized Difference Moisture Index): (NIR - SWIR1) / (NIR + SWIR1) | S2: (B8 - B11) / (B8 + B11)
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')

    # SAVI (Soil-Adjusted Vegetation Index): ((NIR - Red) / (NIR + Red + L)) * (1 + L) | L=0.5
    # S2: ((B8 - B4) / (B8 + B4 + 0.5)) * 1.5
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
        {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'L': 0.5
        }
    ).rename('SAVI')

    # MSI (Moisture Stress Index): SWIR1 / NIR | S2: B11 / B8
    msi = image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('B11'),
        'NIR': image.select('B8')
    }).rename('MSI')

    # LAI (Leaf Area Index) - Simple estimation using NDVI (Needs calibration for accuracy)
    # Example formula: LAI = a * exp(b * NDVI) or simpler linear/polynomial fits
    # Using a very basic placeholder: LAI = 3.618 * EVI - 0.118 (adjust based on research/calibration)
    # Or even simpler: LAI proportional to NDVI
    lai = ndvi.multiply(3.5).rename('LAI') # Placeholder - Needs proper calibration

    # CVI (Chlorophyll Vegetation Index) - (NIR / Green) * (Red / Green) | S2: (B8 / B3) * (B4 / B3)
    # Handle potential division by zero if Green band is 0
    green_safe = image.select('B3').max(ee.Image(0.0001)) # Avoid division by zero
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
        'NIR': image.select('B8'),
        'GREEN': green_safe,
        'RED': image.select('B4')
    }).rename('CVI')

    # Biomass - Placeholder: Needs calibration (e.g., Biomass = a * LAI + b)
    # biomass = lai.multiply(1.5).add(0.5).rename('Biomass') # Example: a=1.5, b=0.5

    # ET (Evapotranspiration) - Complex: Requires meteorological data or specialized models/datasets (e.g., MODIS ET, SSEBop)
    # Not calculating directly here, would typically use a pre-existing GEE product if available.

    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi]) # Add calculated indices, including SAVI

# --- Function to get processed image for a date range and geometry ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked Sentinel-2 median composite OR latest ET image
    for a given geometry and date range/end date.
    _geometry: ee.Geometry (Point or Polygon)
    start_date, end_date: YYYY-MM-DD strings
    index_name: Name of the primary index band to return (e.g., 'NDVI', 'ET')
    """
    try:
        if index_name == 'ET':
            # Use SSEBop Monthly for ET
            et_col = ee.ImageCollection('NASA/SSEBop/MONTHLY').select('et') \
                       .filterBounds(_geometry) \
                       .filterDate(start_date, end_date) # Filter for the range initially

            # Get the latest image within the range (most likely the image covering the end_date month)
            latest_et_image = et_col.sort('system:time_start', False).first()

            if latest_et_image is None:
                 return None, f"No SSEBop ET images found for {start_date} to {end_date}."

            # SSEBop 'et' band is total monthly ET in mm. No scaling needed.
            # No cloud masking needed for this product.
            # Rename the band to 'ET' for consistency
            output_image = latest_et_image.rename(index_name)
            return output_image, None

        else:
            # Process Sentinel-2 for other indices
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_geometry)
                         .filterDate(start_date, end_date)
                         .map(maskS2clouds)) # Apply cloud masking

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date}."

            indexed_col = s2_sr_col.map(add_indices)
            median_image = indexed_col.median() # Use median to reduce noise/outliers
            output_image = median_image.select(index_name)
            return output_image, None # Return the image and no error message

    except ee.EEException as e:
        # Handle GEE specific errors
        error_message = f"خطای Google Earth Engine: {e}"
        st.error(error_message)
        # Try to extract more details if available
        try:
            # GEE errors sometimes have details nested
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str) and 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
            elif isinstance(error_details, str) and 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        except Exception:
            pass # Ignore errors during error detail extraction
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"
        st.error(error_message)
        return None, error_message

# ... inside app.py ...

# Modify get_farm_needs_data to include ET
@st.cache_data(show_spinner="در حال محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_point_geom, start_curr, end_curr, start_prev, end_prev):
    """Calculates mean NDVI, NDMI, EVI, SAVI for current and previous periods (weekly)
       AND latest monthly ET and previous month's ET."""
    results = {
        'NDVI_curr': None, 'NDMI_curr': None, 'EVI_curr': None, 'SAVI_curr': None,
        'NDVI_prev': None, 'NDMI_prev': None, 'EVI_prev': None, 'SAVI_prev': None,
        'ET_curr': None, # Added ET current month
        'ET_prev': None, # Added ET previous month
        'error': None
    }
    # Indices from Sentinel-2 (weekly median)
    s2_indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    # --- Helper for S2 indices ---
    def get_mean_s2_values(start, end):
        period_values = {index: None for index in s2_indices_to_get}
        try:
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_point_geom)
                         .filterDate(start, end)
                         .map(maskS2clouds)
                         .map(add_indices)) # Calculate all S2 indices
            count = s2_sr_col.size().getInfo()
            if count == 0: return period_values, f"No S2 images {start}-{end}"
            median_image = s2_sr_col.median()
            mean_dict = median_image.select(s2_indices_to_get).reduceRegion(
                reducer=ee.Reducer.mean(), geometry=_point_geom, scale=10
            ).getInfo()
            if mean_dict:
                for index in s2_indices_to_get: period_values[index] = mean_dict.get(index)
            return period_values, None
        except Exception as e: return period_values, f"S2 Error {start}-{end}: {e}"

    # --- Helper for Monthly ET ---
    def get_monthly_et(ref_end_date_str):
        """Gets the ET value for the month containing ref_end_date_str."""
        try:
            # Use get_processed_image which handles ET correctly
            # Need a start date far enough back to get the image for the ref_end_date_str month
            # Let's use the start of the month containing ref_end_date_str
            ref_date_dt = datetime.datetime.strptime(ref_end_date_str, '%Y-%m-%d').date()
            month_start_str = ref_date_dt.replace(day=1).strftime('%Y-%m-%d')

            et_image, error = get_processed_image(_point_geom, month_start_str, ref_end_date_str, 'ET')
            if error:
                # If no image exactly in the month range, maybe try extending the start date slightly?
                # For now, just return the error.
                return None, f"ET Error ({ref_end_date_str}): {error}"
            if et_image is None:
                 return None, f"No ET Image found for month of {ref_end_date_str}"


            et_value_dict = et_image.reduceRegion(
                reducer=ee.Reducer.mean(), geometry=_point_geom, scale=1000 # SSEBop scale
            ).getInfo()
            return et_value_dict.get('ET') if et_value_dict else None, None
        except ee.EEException as e:
             # Catch specific GEE errors if needed
             return None, f"GEE ET Error ({ref_end_date_str}): {e}"
        except Exception as e:
            # Catch other errors like date parsing
            return None, f"General ET Error ({ref_end_date_str}): {e}"


    # --- Calculate S2 Indices ---
    curr_s2_values, err_curr_s2 = get_mean_s2_values(start_curr, end_curr)
    if err_curr_s2: results['error'] = f"{results.get('error', '')} | {err_curr_s2}"
    else:
        for index in s2_indices_to_get: results[f'{index}_curr'] = curr_s2_values.get(index)

    prev_s2_values, err_prev_s2 = get_mean_s2_values(start_prev, end_prev)
    if err_prev_s2: results['error'] = f"{results.get('error', '')} | {err_prev_s2}"
    else:
        for index in s2_indices_to_get: results[f'{index}_prev'] = prev_s2_values.get(index)

    # --- Calculate ET ---
    # Get ET for the month containing the end date of the "current" period
    et_curr_val, err_et_curr = get_monthly_et(end_curr)
    if err_et_curr: results['error'] = f"{results.get('error', '')} | Current ET: {err_et_curr}"
    else: results['ET_curr'] = et_curr_val

    # Get ET for the month containing the end date of the "previous" period
    et_prev_val, err_et_prev = get_monthly_et(end_prev)
    if err_et_prev: results['error'] = f"{results.get('error', '')} | Previous ET: {err_et_prev}"
    else: results['ET_prev'] = et_prev_val

    return results


# Modify get_ai_analysis prompt
@st.cache_data(show_spinner="در حال دریافت تحلیل هوش مصنوعی...", persist=True)
def get_ai_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition, including ET."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    # Prepare data string, including ET
    data_str = ""
    # Format helper
    def fmt(val, prev_val, decimals=3):
        curr_str = f"{val:.{decimals}f}" if pd.notna(val) else "N/A"
        prev_str = f"{prev_val:.{decimals}f}" if pd.notna(prev_val) else "N/A"
        return f"{curr_str} (قبلی: {prev_str})"

    if 'NDVI_curr' in index_data and index_data['NDVI_curr'] is not None:
         data_str += f"NDVI (هفتگی): {fmt(index_data['NDVI_curr'], index_data.get('NDVI_prev'))}\n"
    if 'NDMI_curr' in index_data and index_data['NDMI_curr'] is not None:
         data_str += f"NDMI (هفتگی): {fmt(index_data['NDMI_curr'], index_data.get('NDMI_prev'))}\n"
    if 'EVI_curr' in index_data and index_data['EVI_curr'] is not None:
         data_str += f"EVI (هفتگی): {fmt(index_data['EVI_curr'], index_data.get('EVI_prev'))}\n"
    if 'SAVI_curr' in index_data and index_data['SAVI_curr'] is not None:
         data_str += f"SAVI (هفتگی): {fmt(index_data['SAVI_curr'], index_data.get('SAVI_prev'))}\n"
    # Add ET (different format - monthly)
    if 'ET_curr' in index_data and index_data['ET_curr'] is not None:
        et_curr_str = f"{index_data['ET_curr']:.1f} mm"
        et_prev_str = f"{index_data.get('ET_prev'):.1f} mm" if pd.notna(index_data.get('ET_prev')) else "N/A"
        data_str += f"ET (ماهانه): {et_curr_str} (ماه قبل: {et_prev_str})\n"


    prompt = f"""
    شما یک متخصص کشاورزی نیشکر در ایران هستید. لطفاً وضعیت مزرعه '{farm_name}' را بر اساس داده‌های شاخص (شامل NDVI, NDMI, EVI, SAVI هفتگی و ET ماهانه) و توصیه‌های اولیه زیر تحلیل کنید. یک توضیح کوتاه و کاربردی به زبان فارسی ارائه دهید. تمرکز تحلیل بر نیاز آبیاری و کودی باشد و نقش تبخیر و تعرق واقعی ماهانه (ET) را در ارزیابی نیاز آبی فعلی و برنامه‌ریزی آتی لحاظ کنید.

    داده‌های شاخص:
    {data_str if data_str else 'داده‌های شاخص در دسترس نیست.'}
    توصیه‌های اولیه:
    {', '.join(recommendations) if recommendations else 'هیچ توصیه‌ای وجود ندارد.'}

    تحلیل شما (با تاکید بر نیاز آبی و کودی و با استفاده از ET):
    """

    try:
        response = _model.generate_content(prompt)
        # Ensure response.text exists or handle potential errors/different structures
        return response.text if hasattr(response, 'text') else str(response)
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API: {e}")
        return "خطا در دریافت تحلیل هوش مصنوعی."


# ... inside tab_needs ...
# ... (after checking selected_farm_name != "همه مزارع" and geometry is point) ...

            st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

            # Define thresholds (existing sliders)
            st.markdown("**تنظیم آستانه‌ها:**")
            ndmi_threshold = st.slider("آستانه NDMI برای هشدار آبیاری:", 0.0, 0.5, 0.25, 0.01,
                                     help="اگر NDMI کمتر از این مقدار باشد، نیاز به آبیاری اعلام می‌شود.")
            ndvi_drop_threshold = st.slider("آستانه افت NDVI برای بررسی کوددهی (%):", 0.0, 20.0, 5.0, 0.5,
                                        help="اگر NDVI نسبت به هفته قبل بیش از این درصد افت کند، نیاز به بررسی کوددهی اعلام می‌شود.")

            # Get the required index data (now includes ET)
            farm_needs_data = get_farm_needs_data(
                selected_farm_geom,
                start_date_current_str, end_date_current_str,
                start_date_previous_str, end_date_previous_str
            )

            # Check for critical errors during data fetch
            if farm_needs_data.get('error'):
                st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل نیازها: {farm_needs_data['error']}")
                st.warning("ادامه تحلیل ممکن است ناقص باشد.") # Warn but maybe continue if some data exists

            # --- Display Current Indices in Cards ---
            st.markdown("**مقادیر شاخص‌ها:**")
            # Use columns for better layout
            idx_cols = st.columns(5) # 5 columns for NDVI, NDMI, EVI, SAVI, ET

            with idx_cols[0]:
                val = farm_needs_data.get('NDVI_curr')
                prev = farm_needs_data.get('NDVI_prev')
                delta = (val - prev) if pd.notna(val) and pd.notna(prev) else None
                st.metric("NDVI (هفته جاری)", f"{val:.3f}" if pd.notna(val) else "N/A", f"{delta:+.3f}" if delta is not None else None)
            with idx_cols[1]:
                val = farm_needs_data.get('NDMI_curr')
                prev = farm_needs_data.get('NDMI_prev')
                delta = (val - prev) if pd.notna(val) and pd.notna(prev) else None
                st.metric("NDMI (هفته جاری)", f"{val:.3f}" if pd.notna(val) else "N/A", f"{delta:+.3f}" if delta is not None else None)
            with idx_cols[2]:
                val = farm_needs_data.get('EVI_curr')
                prev = farm_needs_data.get('EVI_prev')
                delta = (val - prev) if pd.notna(val) and pd.notna(prev) else None
                st.metric("EVI (هفته جاری)", f"{val:.3f}" if pd.notna(val) else "N/A", f"{delta:+.3f}" if delta is not None else None)
            with idx_cols[3]:
                val = farm_needs_data.get('SAVI_curr')
                prev = farm_needs_data.get('SAVI_prev')
                delta = (val - prev) if pd.notna(val) and pd.notna(prev) else None
                st.metric("SAVI (هفته جاری)", f"{val:.3f}" if pd.notna(val) else "N/A", f"{delta:+.3f}" if delta is not None else None)
            with idx_cols[4]: # Column for ET
                val = farm_needs_data.get('ET_curr')
                prev = farm_needs_data.get('ET_prev')
                delta = (val - prev) if pd.notna(val) and pd.notna(prev) else None
                st.metric("ET (ماه جاری, mm)", f"{val:.1f}" if pd.notna(val) else "N/A", f"{delta:+.1f}" if delta is not None else None, help="تبخیر و تعرق واقعی محاسبه شده با SSEBop")


            # --- Generate Recommendations ---
            recommendations = []
            # Check if essential data for recommendations is present
            ndmi_curr = farm_needs_data.get('NDMI_curr')
            ndvi_curr = farm_needs_data.get('NDVI_curr')
            ndvi_prev = farm_needs_data.get('NDVI_prev')

            # 1. Irrigation Check (only if NDMI is valid)
            if pd.notna(ndmi_curr):
                if ndmi_curr < ndmi_threshold:
                    recommendations.append("💧 نیاز به آبیاری بر اساس NDMI")
                # Potentially add ET-based check here in the future
            else:
                st.caption("NDMI برای بررسی نیاز آبیاری در دسترس نیست.")


            # 2. Fertilization Check (only if NDVI current and previous are valid)
            if pd.notna(ndvi_curr) and pd.notna(ndvi_prev):
                 if ndvi_curr < ndvi_prev : # Check if dropped at all first
                     # Avoid division by zero if ndvi_prev is 0 or close to it
                     if abs(ndvi_prev) > 1e-6:
                         ndvi_change_percent = ((ndvi_prev - ndvi_curr) / ndvi_prev) * 100
                         if ndvi_change_percent > ndvi_drop_threshold:
                             recommendations.append(f"⚠️ نیاز به بررسی کوددهی (افت {ndvi_change_percent:.1f}% در NDVI)")
                     elif ndvi_curr < ndvi_prev: # If prev was ~0 and curr is negative, flag it
                          recommendations.append(f"⚠️ نیاز به بررسی کوددهی (افت قابل توجه در NDVI)")
            elif pd.notna(ndvi_curr) and pd.isna(ndvi_prev):
                 st.caption("داده NDVI هفته قبل برای بررسی افت در دسترس نیست.")
            else: # Neither NDVI nor NDMI might be available
                st.caption("NDVI برای بررسی نیاز کودی در دسترس نیست.")


            # 3. Default if no issues found and data was available
            if not recommendations and pd.notna(ndmi_curr) and pd.notna(ndvi_curr):
                 # Only add 'Good' if both primary checks were possible and found no issues
                 recommendations.append("✅ وضعیت بر اساس NDMI/NDVI مطلوب به نظر می‌رسد.")
            elif not recommendations:
                 # If no recommendations were added (either due to no issues or missing data for checks)
                 recommendations.append("ℹ️ وضعیت کلی نیاز به بررسی بیشتر دارد (با توجه به ET و مشاهدات میدانی).")


            # Display Recommendations
            st.markdown("**توصیه‌های اولیه:**")
            for rec in recommendations:
                if "آبیاری" in rec: st.error(rec)
                elif "کوددهی" in rec: st.warning(rec)
                elif "مطلوب" in rec: st.success(rec)
                else: st.info(rec) # For "check further" etc.

            # --- Get and Display AI Analysis ---
            if gemini_model:
                st.markdown("**تحلیل هوش مصنوعی:**")
                # Pass the potentially partial farm_needs_data
                ai_explanation = get_ai_analysis(gemini_model, selected_farm_name, farm_needs_data, recommendations)
                st.markdown(ai_explanation)
            else:
                st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده است.")

    else: # Handle case where selected_farm_geom is None (shouldn't happen if selection is handled properly)
         st.info("ابتدا یک مزرعه را از پنل کناری انتخاب کنید.")

# Final bits at the end of the file
st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")
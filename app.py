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
import traceback  # Add missing traceback import
from streamlit_folium import st_folium  # Add missing st_folium import
import base64
import logging

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Custom CSS for Persian text alignment and professional styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700&display=swap');
        
        /* Main container */
        .main {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f8f9fa;
        }
        
        /* Headers */
        h1, h2, h3 {
            font-family: 'Vazirmatn', sans-serif;
            color: #2c3e50;
            text-align: right;
        }
        
        /* Custom header with logo */
        .header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1rem 2rem;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        .header-title {
            color: white;
            margin: 0;
            font-size: 1.8rem;
            font-weight: 700;
        }
        
        .header-subtitle {
            color: rgba(255, 255, 255, 0.9);
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
            font-weight: 500;
        }
        
        .header-logo {
            height: 60px;
            margin-left: 1rem;
        }
        
        /* Metrics */
        .css-1xarl3l {
            font-family: 'Vazirmatn', sans-serif;
            background-color: white;
            border-radius: 10px;
            padding: 1.2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .css-1xarl3l:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 2px;
            direction: rtl;
            background-color: #f1f3f5;
            padding: 0.5rem;
            border-radius: 10px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding: 10px 20px;
            background-color: white;
            border-radius: 8px;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            transition: all 0.3s ease;
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            background-color: #1e3c72;
            color: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* Tables */
        .dataframe {
            font-family: 'Vazirmatn', sans-serif;
            text-align: right;
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        .dataframe th {
            background-color: #1e3c72;
            color: white;
            padding: 12px 15px;
            font-weight: 600;
        }
        
        .dataframe td {
            padding: 10px 15px;
            border-bottom: 1px solid #e9ecef;
        }
        
        .dataframe tr:nth-child(even) {
            background-color: #f8f9fa;
        }
        
        .dataframe tr:hover {
            background-color: #e9ecef;
        }
        
        /* Sidebar */
        .css-1d391kg {
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 10px;
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
        
        /* Buttons */
        .stButton button {
            background-color: #1e3c72;
            color: white;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            transition: all 0.3s ease;
            border: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .stButton button:hover {
            background-color: #2a5298;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* Charts */
        .stPlotlyChart {
            background-color: white;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        
        /* Download buttons */
        .download-button {
            display: inline-flex;
            align-items: center;
            background-color: #28a745;
            color: white;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-family: 'Vazirmatn', sans-serif;
            font-weight: 600;
            transition: all 0.3s ease;
            border: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-decoration: none;
        }
        
        .download-button:hover {
            background-color: #218838;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        .download-button i {
            margin-left: 0.5rem;
        }
        
        /* Summary cards */
        .summary-card {
            background-color: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .summary-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .summary-card-title {
            font-size: 1rem;
            font-weight: 600;
            color: #6c757d;
            margin-bottom: 0.5rem;
        }
        
        .summary-card-value {
            font-size: 1.8rem;
            font-weight: 700;
            color: #1e3c72;
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .animate-fade-in {
            animation: fadeIn 0.5s ease forwards;
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
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    """Loads farm data from the specified CSV file."""
    try:
        df = pd.read_csv(csv_path)
        # Basic validation
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            return None
        # Convert coordinate columns to numeric, coercing errors
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        # Handle missing coordinates flag explicitly if needed
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool)
        # Drop rows where coordinates are actually missing after coercion or flagged
        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'])
        df = df[~df['coordinates_missing']]

        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات).")
            return None

        # Ensure 'روزهای هفته' is string type for consistent filtering
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
    index=0, # Default to the first day
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

# --- Filter Data Based on Selected Day ---
filtered_farms_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

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
    "NDMI": "شاخص رطوبت تفاضلی نرمال شده",
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
    # Add more indices if needed and implemented
    # "Biomass": "زیست‌توده (تخمینی)",
    # "ET": "تبخیر و تعرق (تخمینی)",
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
    "سه شنبه": 1, # Assuming space is correct
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

    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi]) # Add calculated indices

# --- Function to get processed image for a date range and geometry ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given geometry and date range.
    _geometry: ee.Geometry (Point or Polygon)
    start_date, end_date: YYYY-MM-DD strings
    index_name: Name of the primary index band to return (e.g., 'NDVI')
    """
    try:
        st.write(f"Fetching images for date range: {start_date} to {end_date}")
        
        # Get the Sentinel-2 collection
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date))
        
        # Log the initial collection size
        initial_count = s2_sr_col.size().getInfo()
        st.write(f"Initial collection size: {initial_count} images")
        
        if initial_count == 0:
            return None, f"No Sentinel-2 images found for {start_date} to {end_date}."
        
        # Apply cloud masking
        st.write("Applying cloud masking...")
        s2_sr_col = s2_sr_col.map(maskS2clouds)
        
        # Check collection size after cloud masking
        masked_count = s2_sr_col.size().getInfo()
        st.write(f"Images after cloud masking: {masked_count}")
        
        if masked_count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date}."
        
        # Calculate indices for each image
        st.write("Calculating indices...")
        indexed_col = s2_sr_col.map(add_indices)
        
        # Create median composite
        st.write("Creating median composite...")
        median_image = indexed_col.median()
        
        # Select the desired index band
        st.write(f"Selecting {index_name} band...")
        output_image = median_image.select(index_name)
        
        # Verify the image has data
        try:
            # Get a sample of the image to verify it has data
            sample = output_image.reduceRegion(
                reducer=ee.Reducer.first(),
                geometry=_geometry,
                scale=10
            ).getInfo()
            
            if sample and index_name in sample:
                st.write(f"Sample data for {index_name}: {sample[index_name]}")
                if sample[index_name] is None:
                    st.warning(f"No valid data found for {index_name} in the sample area")
                    return None, f"No valid data found for {index_name} in the sample area"
            else:
                st.warning(f"No {index_name} data found in the sample")
                return None, f"No {index_name} data found in the sample"
                
        except Exception as e:
            st.write(f"Error getting sample data: {e}")
            return None, f"Error verifying image data: {e}"
        
        return output_image, None
        
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        st.error(error_message)
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'computation timed out' in error_details.lower():
                    error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
                elif 'user memory limit exceeded' in error_details.lower():
                    error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        except Exception:
            pass
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"
        st.error(error_message)
        return None, error_message

# --- Function to get time series data for a point ---
@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets a time series of a specified index for a point geometry."""
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))

        def extract_value(image):
            # Extract the index value at the point
            # Use reduceRegion for points; scale should match sensor resolution (e.g., 10m for S2 NDVI)
            value = image.reduceRegion(
                reducer=ee.Reducer.first(), # Use 'first' or 'mean' if point covers multiple pixels
                geometry=_point_geom,
                scale=10 # Scale in meters (10m for Sentinel-2 RGB/NIR)
            ).get(index_name)
            # Return a feature with the value and the image date
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                index_name: value
            })

        # Map over the collection and remove features with null values
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))

        # Convert the FeatureCollection to a list of dictionaries
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد."

        # Convert to Pandas DataFrame
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')

        return ts_df, None # Return DataFrame and no error
    except ee.EEException as e:
        error_message = f"خطای GEE در دریافت سری زمانی: {e}"
        st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"
        st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message


# ==============================================================================
# Main Panel Display
# ==============================================================================

# --- Header with Logo ---
logo_path = "logo (1).png"
if os.path.exists(logo_path):
    # Read the logo file and encode it as base64
    with open(logo_path, "rb") as f:
        logo_data = f.read()
        logo_base64 = base64.b64encode(logo_data).decode()
    
    # Create the header with logo
    st.markdown(f"""
    <div class="header-container animate-fade-in">
        <div>
            <h1 class="header-title">{APP_TITLE}</h1>
            <p class="header-subtitle">{APP_SUBTITLE}</p>
        </div>
        <img src="data:image/png;base64,{logo_base64}" class="header-logo" alt="Logo">
    </div>
    """, unsafe_allow_html=True)
else:
    # Fallback header without logo
    st.markdown(f"""
    <div class="header-container animate-fade-in">
        <div>
            <h1 class="header-title">{APP_TITLE}</h1>
            <p class="header-subtitle">{APP_SUBTITLE}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- Get Selected Farm Geometry and Details ---
selected_farm_details = None
selected_farm_geom = None

if selected_farm_name == "همه مزارع":
    # Use the bounding box of all filtered farms for the map view
    min_lon, min_lat = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
    max_lon, max_lat = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
    # Create a bounding box geometry
    selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    
    # Display summary statistics
    st.markdown("### 📊 خلاصه آماری")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">تعداد مزارع</div>
            <div class="summary-card-value">{len(filtered_farms_df)}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Calculate average area if available
        avg_area = filtered_farms_df['مساحت'].mean() if 'مساحت' in filtered_farms_df.columns else None
        area_text = f"{avg_area:.2f}" if avg_area is not None else "N/A"
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">میانگین مساحت (هکتار)</div>
            <div class="summary-card-value">{area_text}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Count unique varieties if available
        unique_varieties = filtered_farms_df['واریته'].nunique() if 'واریته' in filtered_farms_df.columns else 0
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">تعداد واریته‌ها</div>
            <div class="summary-card-value">{unique_varieties}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        # Count unique channels if available
        unique_channels = filtered_farms_df['کانال'].nunique() if 'کانال' in filtered_farms_df.columns else 0
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">تعداد کانال‌ها</div>
            <div class="summary-card-value">{unique_channels}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"### نمایش کلی مزارع برای روز: {selected_day}")
    st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
else:
    selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat = selected_farm_details['عرض جغرافیایی']
    lon = selected_farm_details['طول جغرافیایی']
    selected_farm_geom = ee.Geometry.Point([lon, lat])
    
    # Display summary statistics
    st.markdown("### 📊 خلاصه آماری")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">نام مزرعه</div>
            <div class="summary-card-value">{selected_farm_name}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        area = selected_farm_details.get('مساحت', 'N/A')
        area_text = f"{area:.2f}" if pd.notna(area) else "N/A"
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">مساحت (هکتار)</div>
            <div class="summary-card-value">{area_text}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        variety = selected_farm_details.get('واریته', 'N/A')
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">واریته</div>
            <div class="summary-card-value">{variety}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        channel = selected_farm_details.get('کانال', 'N/A')
        st.markdown(f"""
        <div class="summary-card animate-fade-in">
            <div class="summary-card-title">کانال</div>
            <div class="summary-card-value">{channel}</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown(f"### جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
    # Display farm details
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

# --- Tabs Structure ---
st.markdown("---")
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ نقشه", "📈 نمودارها", "📊 جدول رتبه‌بندی", "📋 گزارش‌ها"])

with tab1:
    st.markdown("### نقشه وضعیت مزارع")
    
    # Define visualization parameters based on the selected index
    vis_params = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'NDWI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'NDMI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'NDBI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'red']},
        'SAVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'GNDVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'OSAVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MSAVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'NDRE': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MCARI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'TCARI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'CARI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'SIPI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'PSRI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'ARI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'CRI1': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'CRI2': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MTCI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'REIP': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'Chlgreen': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'Chlrededge': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'GM1': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'GM2': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'LWCI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'DWSI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MSI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'NDII': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'NDWI2': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'SR': {'min': 0, 'max': 30, 'palette': ['blue', 'white', 'green']},
        'DVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'RVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'TVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'CTVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'TTVI': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'GDVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'WDVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'TDVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'RDVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MSR': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MSAVI2': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'VARI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'VIG': {'min': 0, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'GRVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'MGRVI': {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'green']},
        'RGB': {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000}
    }

    map_center_lat = 31.534442
    map_center_lon = 48.724416
    initial_zoom = 11

    # Create a geemap Map instance
    m = geemap.Map(
        location=[map_center_lat, map_center_lon],
        zoom=initial_zoom,
        add_google_map=False # Start clean
    )
    m.add_basemap("HYBRID") # Add Google Satellite Hybrid basemap

    # Get the processed image for the current week
    if selected_farm_geom:
        gee_image_current, error_msg_current = get_processed_image(
            selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )

        if gee_image_current:
            # Add the GEE layer to the map
            try:
                m.addLayer(
                    gee_image_current,
                    vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}), # Default vis
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )

                # Remove the problematic add_legend call and replace with a custom legend
                # Create a custom legend using folium
                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                    legend_html = '''
                    <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
                        <p style="margin: 0;"><strong>{} Legend</strong></p>
                        <p style="margin: 0; color: red;">بحرانی/پایین</p>
                        <p style="margin: 0; color: yellow;">متوسط</p>
                        <p style="margin: 0; color: green;">سالم/بالا</p>
                    </div>
                    '''.format(selected_index)
                elif selected_index in ['NDMI', 'MSI']:
                    legend_html = '''
                    <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
                        <p style="margin: 0;"><strong>{} Legend</strong></p>
                        <p style="margin: 0; color: blue;">مرطوب/بالا</p>
                        <p style="margin: 0; color: white;">متوسط</p>
                        <p style="margin: 0; color: brown;">خشک/پایین</p>
                    </div>
                    '''.format(selected_index)
                else:
                    # Default legend for other indices
                    legend_html = '''
                    <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
                        <p style="margin: 0;"><strong>{} Legend</strong></p>
                        <p style="margin: 0;">Low</p>
                        <p style="margin: 0;">Medium</p>
                        <p style="margin: 0;">High</p>
                    </div>
                    '''.format(selected_index)
                
                # Add the custom legend to the map
                m.get_root().html.add_child(folium.Element(legend_html))

                # Add markers for farms
                if selected_farm_name == "همه مزارع":
                     # Add markers for all filtered farms
                     for idx, farm in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm['عرض جغرافیایی'], farm['طول جغرافیایی']],
                             popup=f"مزرعه: {farm['مزرعه']}\nکانال: {farm['کانال']}\nاداره: {farm['اداره']}",
                             tooltip=farm['مزرعه'],
                             icon=folium.Icon(color='blue', icon='info-sign')
                         ).add_to(m)
                     # Adjust map bounds if showing all farms
                     m.center_object(selected_farm_geom, zoom=initial_zoom) # Center on the bounding box
                else:
                     # Add marker for the single selected farm
                     folium.Marker(
                         location=[lat, lon],
                         popup=f"مزرعه: {selected_farm_name}\n{selected_index} (هفته جاری): محاسبه می‌شود...", # Placeholder popup
                         tooltip=selected_farm_name,
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=14) # Zoom closer for a single farm

                m.add_layer_control() # Add layer control to toggle base maps and layers

            except Exception as map_err:
                st.error(f"خطا در افزودن لایه به نقشه: {map_err}")
                st.error(traceback.format_exc())
        else:
            st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")

    # Display the map in Streamlit
    st_folium(m, width=None, height=500, use_container_width=True)
    st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها برای تغییر نقشه پایه استفاده کنید.")
    
    # Add download button for the map
    st.markdown("""
    <div style="text-align: center; margin-top: 10px;">
        <a href="#" class="download-button">
            <i class="fas fa-download"></i> دانلود نقشه
        </a>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")

with tab2:
    st.markdown("### 📈 نمودار روند زمانی شاخص {selected_index}")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom:
        # Fix the isinstance check - use string comparison instead
        # Check if the geometry type is Point by converting to string and checking
        is_point = str(selected_farm_geom).find('Point') >= 0
        
        if is_point:
            # Define a longer period for the time series chart (e.g., last 6 months)
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d')

            ts_df, ts_error = get_index_time_series(
                selected_farm_geom,
                selected_index,
                start_date=timeseries_start_date,
                end_date=timeseries_end_date
            )

            if ts_error:
                st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                # Create a more visually appealing chart with Plotly
                fig = px.line(
                    ts_df, 
                    y=selected_index,
                    title=f"روند تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name}",
                    labels={selected_index: f"مقدار {selected_index}", "index": "تاریخ"},
                    template="plotly_white"
                )
                
                # Customize the chart
                fig.update_layout(
                    font=dict(family="Vazirmatn"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(
                        title="تاریخ",
                        gridcolor="rgba(0,0,0,0.1)",
                        showgrid=True
                    ),
                    yaxis=dict(
                        title=f"مقدار {selected_index}",
                        gridcolor="rgba(0,0,0,0.1)",
                        showgrid=True
                    ),
                    hovermode="x unified"
                )
                
                # Display the chart
                st.plotly_chart(fig, use_container_width=True)
                
                # Add download button for the chart data
                csv_data = ts_df.reset_index().to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 دانلود داده‌های نمودار (CSV)",
                    data=csv_data,
                    file_name=f'timeseries_{selected_index}_{selected_farm_name}_{timeseries_end_date}.csv',
                    mime='text/csv',
                )
                
                st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 6 ماه گذشته.")
            else:
                st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
        else:
            st.warning("نوع هندسه مزرعه برای نمودار سری زمانی پشتیبانی نمی‌شود (فقط نقطه).")
    else:
        st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست.")

with tab3:
    st.markdown(f"### 📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
        """Calculates the average index value for the current and previous week for a list of farms."""
        results = []
        errors = []
        total_farms = len(_farms_df)
        progress_bar = st.progress(0)

        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            farm_name = farm['مزرعه']
            lat = farm['عرض جغرافیایی']
            lon = farm['طول جغرافیایی']
            point_geom = ee.Geometry.Point([lon, lat])

            def get_mean_value(start, end):
                try:
                    image, error = get_processed_image(point_geom, start, end, index_name)
                    if image:
                        # Reduce region to get the mean value at the point
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=point_geom,
                            scale=10  # Scale in meters
                        ).getInfo()
                        return mean_dict.get(index_name) if mean_dict else None, None
                    else:
                        return None, error
                except Exception as e:
                     # Catch errors during reduceRegion or getInfo
                     error_msg = f"خطا در محاسبه مقدار برای {farm_name} ({start}-{end}): {e}"
                     # errors.append(error_msg) # Collect errors
                     # st.warning(error_msg) # Show warning immediately
                     return None, error_msg


            # Calculate for current week
            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")

            # Calculate for previous week
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")


            # Calculate change
            change = None
            if current_val is not None and previous_val is not None:
                try:
                    change = current_val - previous_val
                except TypeError: # Handle cases where values might not be numeric unexpectedly
                    change = None

            results.append({
                'مزرعه': farm_name,
                'کانال': farm.get('کانال', 'N/A'),
                'اداره': farm.get('اداره', 'N/A'),
                f'{index_name} (هفته جاری)': current_val,
                f'{index_name} (هفته قبل)': previous_val,
                'تغییر': change
            })

            # Update progress bar
            progress_bar.progress((i + 1) / total_farms)

        progress_bar.empty() # Remove progress bar after completion
        return pd.DataFrame(results), errors

    # Calculate and display the ranking table
    ranking_df, calculation_errors = calculate_weekly_indices(
        filtered_farms_df,
        selected_index,
        start_date_current_str,
        end_date_current_str,
        start_date_previous_str,
        end_date_previous_str
    )

    # Display any errors that occurred during calculation
    if calculation_errors:
        st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها رخ داد:")
        for error in calculation_errors[:10]: # Show first 10 errors
            st.warning(f"- {error}")
        if len(calculation_errors) > 10:
            st.warning(f"... و {len(calculation_errors) - 10} خطای دیگر.")


    if not ranking_df.empty:
        # Sort by the current week's index value (descending for NDVI/EVI/LAI/CVI, ascending for MSI?)
        # Adjust sorting based on index meaning
        ascending_sort = selected_index in ['MSI'] # Indices where lower is better
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)',
            ascending=ascending_sort,
            na_position='last' # Put farms with no data at the bottom
        ).reset_index(drop=True)

        # Add rank number
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # Add a status column to indicate growth or stress
        # For NDVI, EVI, LAI, CVI: higher is better
        # For MSI, NDMI: lower is better
        def determine_status(row, index_name):
            if pd.isna(row['تغییر']) or pd.isna(row[f'{index_name} (هفته جاری)']) or pd.isna(row[f'{index_name} (هفته قبل)']):
                return "بدون داده"
            
            # For indices where higher is better (NDVI, EVI, LAI, CVI)
            if index_name in ['NDVI', 'EVI', 'LAI', 'CVI']:
                if row['تغییر'] > 0.05:  # Significant growth
                    return "رشد مثبت"
                elif row['تغییر'] < -0.05:  # Significant decline
                    return "تنش/کاهش"
                else:
                    return "ثابت"
            # For indices where lower is better (MSI, NDMI)
            elif index_name in ['MSI', 'NDMI']:
                if row['تغییر'] < -0.05:  # Significant improvement
                    return "بهبود"
                elif row['تغییر'] > 0.05:  # Significant deterioration
                    return "تنش/بدتر شدن"
                else:
                    return "ثابت"
            else:
                return "نامشخص"

        # Add status column
        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)
        
        # Format numbers for better readability
        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                 # Check if column exists before formatting
                 ranking_df_sorted[col] = ranking_df_sorted[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

        # Apply custom styling to the table
        def highlight_status(val):
            if val == "رشد مثبت" or val == "بهبود":
                return 'background-color: #d4edda; color: #155724;'
            elif val == "ثابت":
                return 'background-color: #fff3cd; color: #856404;'
            elif val == "تنش/کاهش" or val == "تنش/بدتر شدن":
                return 'background-color: #f8d7da; color: #721c24;'
            elif val == "بدون داده":
                return 'background-color: #e9ecef; color: #495057;'
            return ''

        # Apply the styling
        styled_df = ranking_df_sorted.style.applymap(highlight_status, subset=['وضعیت'])

        # Display the styled table
        st.dataframe(styled_df, use_container_width=True)
        
        # Add a summary of farm statuses
        st.markdown("### 📊 خلاصه وضعیت مزارع")
        
        # Display status counts with appropriate colors
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if "رشد مثبت" in ranking_df_sorted['وضعیت'].value_counts() or "بهبود" in ranking_df_sorted['وضعیت'].value_counts():
                status = "رشد مثبت" if "رشد مثبت" in ranking_df_sorted['وضعیت'].value_counts() else "بهبود"
                count = ranking_df_sorted['وضعیت'].value_counts()[status]
                st.markdown(f"""
                <div class="summary-card animate-fade-in" style="background-color: #d4edda; color: #155724;">
                    <div class="summary-card-title">🟢 {status}</div>
                    <div class="summary-card-value">{count}</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            if "ثابت" in ranking_df_sorted['وضعیت'].value_counts():
                count = ranking_df_sorted['وضعیت'].value_counts()["ثابت"]
                st.markdown(f"""
                <div class="summary-card animate-fade-in" style="background-color: #fff3cd; color: #856404;">
                    <div class="summary-card-title">⚪ ثابت</div>
                    <div class="summary-card-value">{count}</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col3:
            if "تنش/کاهش" in ranking_df_sorted['وضعیت'].value_counts() or "تنش/بدتر شدن" in ranking_df_sorted['وضعیت'].value_counts():
                status = "تنش/کاهش" if "تنش/کاهش" in ranking_df_sorted['وضعیت'].value_counts() else "تنش/بدتر شدن"
                count = ranking_df_sorted['وضعیت'].value_counts()[status]
                st.markdown(f"""
                <div class="summary-card animate-fade-in" style="background-color: #f8d7da; color: #721c24;">
                    <div class="summary-card-title">🔴 {status}</div>
                    <div class="summary-card-value">{count}</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col4:
            if "بدون داده" in ranking_df_sorted['وضعیت'].value_counts():
                count = ranking_df_sorted['وضعیت'].value_counts()["بدون داده"]
                st.markdown(f"""
                <div class="summary-card animate-fade-in" style="background-color: #e9ecef; color: #495057;">
                    <div class="summary-card-title">⚫ بدون داده</div>
                    <div class="summary-card-value">{count}</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Add explanation
        st.info(f"""
        **توضیحات:**
        - **🟢 رشد مثبت/بهبود**: مزارعی که نسبت به هفته قبل بهبود داشته‌اند
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند
        - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت بدتری داشته‌اند
        """)

        # Add download button for the table
        csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)",
            data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
            mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")

with tab4:
    st.markdown("### 📋 گزارش‌ها و تحلیل‌ها")
    
    # Create a report section with multiple subsections
    report_tab1, report_tab2, report_tab3 = st.tabs(["📊 تحلیل آماری", "📈 روند تغییرات", "📑 گزارش‌های سفارشی"])
    
    with report_tab1:
        st.markdown("#### تحلیل آماری شاخص‌های مزارع")
        
        if not ranking_df.empty:
            # Calculate basic statistics
            current_values = ranking_df[f'{selected_index} (هفته جاری)'].dropna()
            
            if not current_values.empty:
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"""
                    <div class="summary-card animate-fade-in">
                        <div class="summary-card-title">میانگین {selected_index}</div>
                        <div class="summary-card-value">{current_values.mean():.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="summary-card animate-fade-in">
                        <div class="summary-card-title">حداقل {selected_index}</div>
                        <div class="summary-card-value">{current_values.min():.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"""
                    <div class="summary-card animate-fade-in">
                        <div class="summary-card-title">حداکثر {selected_index}</div>
                        <div class="summary-card-value">{current_values.max():.3f}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Create a histogram of the current values
                fig = px.histogram(
                    current_values, 
                    title=f"توزیع مقادیر {selected_index}",
                    labels={f'{selected_index} (هفته جاری)': f"مقدار {selected_index}", "count": "تعداد مزارع"},
                    template="plotly_white"
                )
                
                # Customize the chart
                fig.update_layout(
                    font=dict(family="Vazirmatn"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(
                        gridcolor="rgba(0,0,0,0.1)",
                        showgrid=True
                    ),
                    yaxis=dict(
                        gridcolor="rgba(0,0,0,0.1)",
                        showgrid=True
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"داده‌ای برای تحلیل آماری {selected_index} در دسترس نیست.")
        else:
            st.info("داده‌ای برای تحلیل آماری در دسترس نیست.")
    
    with report_tab2:
        st.markdown("#### روند تغییرات شاخص‌ها")
        
        if not ranking_df.empty:
            # Calculate the percentage of farms with positive, neutral, and negative changes
            status_counts = ranking_df_sorted['وضعیت'].value_counts()
            
            # Create a pie chart of the status distribution
            fig = px.pie(
                values=status_counts.values, 
                names=status_counts.index,
                title="توزیع وضعیت مزارع",
                template="plotly_white",
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            
            # Customize the chart
            fig.update_layout(
                font=dict(family="Vazirmatn"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Add a summary of the changes
            st.markdown("##### خلاصه تغییرات")
            
            # Calculate the average change
            changes = ranking_df['تغییر'].dropna()
            if not changes.empty:
                avg_change = changes.mean()
                change_direction = "افزایش" if avg_change > 0 else "کاهش"
                
                st.markdown(f"""
                <div style="background-color: white; padding: 1.5rem; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                    <h4 style="margin-top: 0;">میانگین تغییر {selected_index}</h4>
                    <p style="font-size: 1.2rem;">در هفته جاری نسبت به هفته قبل، میانگین {selected_index} 
                    <strong>{change_direction}</strong> یافته است (تغییر: {avg_change:.3f}).</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.info("داده‌ای برای محاسبه میانگین تغییرات در دسترس نیست.")
        else:
            st.info("داده‌ای برای تحلیل روند تغییرات در دسترس نیست.")
    
    with report_tab3:
        st.markdown("#### گزارش‌های سفارشی")
        
        # Add options for custom reports
        report_type = st.selectbox(
            "نوع گزارش",
            options=["گزارش مقایسه‌ای مزارع", "گزارش روند زمانی", "گزارش وضعیت کلی"]
        )
        
        if report_type == "گزارش مقایسه‌ای مزارع":
            st.markdown("##### گزارش مقایسه‌ای مزارع")
            
            # Add options for comparison
            compare_by = st.selectbox(
                "مقایسه بر اساس",
                options=["کانال", "واریته", "اداره"]
            )
            
            if not ranking_df.empty and compare_by in ranking_df.columns:
                # Group by the selected column and calculate statistics
                grouped = ranking_df.groupby(compare_by)[f'{selected_index} (هفته جاری)'].agg(['mean', 'min', 'max', 'count']).reset_index()
                
                # Sort by mean value
                ascending_sort = selected_index in ['MSI'] # Indices where lower is better
                grouped = grouped.sort_values('mean', ascending=ascending_sort)
                
                # Display the comparison table
                st.dataframe(grouped, use_container_width=True)
                
                # Create a bar chart of the comparison
                fig = px.bar(
                    grouped, 
                    x=compare_by, 
                    y='mean',
                    title=f"میانگین {selected_index} بر اساس {compare_by}",
                    labels={'mean': f"میانگین {selected_index}", compare_by: compare_by},
                    template="plotly_white"
                )
                
                # Customize the chart
                fig.update_layout(
                    font=dict(family="Vazirmatn"),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(
                        gridcolor="rgba(0,0,0,0.1)",
                        showgrid=True
                    ),
                    yaxis=dict(
                        gridcolor="rgba(0,0,0,0.1)",
                        showgrid=True
                    )
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"داده‌ای برای مقایسه بر اساس {compare_by} در دسترس نیست.")
        
        elif report_type == "گزارش روند زمانی":
            st.markdown("##### گزارش روند زمانی")
            
            # Add options for time series report
            time_period = st.selectbox(
                "بازه زمانی",
                options=["1 ماه گذشته", "3 ماه گذشته", "6 ماه گذشته", "1 سال گذشته"]
            )
            
            # Map time period to days
            days_map = {
                "1 ماه گذشته": 30,
                "3 ماه گذشته": 90,
                "6 ماه گذشته": 180,
                "1 سال گذشته": 365
            }
            
            days = days_map[time_period]
            
            if selected_farm_name != "همه مزارع" and selected_farm_geom:
                # Get time series data for the selected farm
                timeseries_end_date = today.strftime('%Y-%m-%d')
                timeseries_start_date = (today - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
                
                ts_df, ts_error = get_index_time_series(
                    selected_farm_geom,
                    selected_index,
                    start_date=timeseries_start_date,
                    end_date=timeseries_end_date
                )
                
                if not ts_error and not ts_df.empty:
                    # Create a time series chart
                    fig = px.line(
                        ts_df, 
                        y=selected_index,
                        title=f"روند تغییرات {selected_index} برای مزرعه {selected_farm_name}",
                        labels={selected_index: f"مقدار {selected_index}", "index": "تاریخ"},
                        template="plotly_white"
                    )
                    
                    # Customize the chart
                    fig.update_layout(
                        font=dict(family="Vazirmatn"),
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(
                            title="تاریخ",
                            gridcolor="rgba(0,0,0,0.1)",
                            showgrid=True
                        ),
                        yaxis=dict(
                            title=f"مقدار {selected_index}",
                            gridcolor="rgba(0,0,0,0.1)",
                            showgrid=True
                        ),
                        hovermode="x unified"
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Add statistics about the time series
                    st.markdown("##### آمار توصیفی سری زمانی")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown(f"""
                        <div class="summary-card animate-fade-in">
                            <div class="summary-card-title">میانگین {selected_index}</div>
                            <div class="summary-card-value">{ts_df[selected_index].mean():.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown(f"""
                        <div class="summary-card animate-fade-in">
                            <div class="summary-card-title">حداقل {selected_index}</div>
                            <div class="summary-card-value">{ts_df[selected_index].min():.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col3:
                        st.markdown(f"""
                        <div class="summary-card animate-fade-in">
                            <div class="summary-card-title">حداکثر {selected_index}</div>
                            <div class="summary-card-value">{ts_df[selected_index].max():.3f}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info(f"داده‌ای برای نمایش روند زمانی {selected_index} در بازه {time_period} یافت نشد.")
            else:
                st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا گزارش روند زمانی آن نمایش داده شود.")
        
        elif report_type == "گزارش وضعیت کلی":
            st.markdown("##### گزارش وضعیت کلی مزارع")
            
            if not ranking_df.empty:
                # Create a summary of the overall status
                status_summary = ranking_df_sorted['وضعیت'].value_counts()
                
                # Calculate percentages
                total_farms = len(ranking_df_sorted)
                status_percentages = {status: (count / total_farms) * 100 for status, count in status_summary.items()}
                
                # Display the summary
                st.markdown("##### توزیع وضعیت مزارع")
                
                for status, count in status_summary.items():
                    percentage = status_percentages[status]
                    
                    # Determine color based on status
                    if status in ["رشد مثبت", "بهبود"]:
                        color = "#d4edda"
                        text_color = "#155724"
                    elif status == "ثابت":
                        color = "#fff3cd"
                        text_color = "#856404"
                    elif status in ["تنش/کاهش", "تنش/بدتر شدن"]:
                        color = "#f8d7da"
                        text_color = "#721c24"
                    else:
                        color = "#e9ecef"
                        text_color = "#495057"
                    
                    st.markdown(f"""
                    <div style="background-color: {color}; color: {text_color}; padding: 1rem; border-radius: 8px; margin-bottom: 0.5rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div style="font-weight: bold;">{status}</div>
                            <div>{count} مزرعه ({percentage:.1f}%)</div>
                        </div>
                        <div style="background-color: rgba(0,0,0,0.1); height: 8px; border-radius: 4px; margin-top: 0.5rem;">
                            <div style="background-color: {text_color}; height: 100%; width: {percentage}%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Add recommendations based on the status
                st.markdown("##### توصیه‌ها")
                
                if "تنش/کاهش" in status_summary or "تنش/بدتر شدن" in status_summary:
                    st.warning("""
                    **توصیه برای مزارع با وضعیت تنش/کاهش:**
                    - بررسی وضعیت آبیاری و اطمینان از تامین آب کافی
                    - بررسی وجود آفات و بیماری‌ها
                    - بررسی وضعیت خاک و تغذیه گیاه
                    - در صورت نیاز، مشاوره با کارشناسان کشاورزی
                    """)
                
                if "رشد مثبت" in status_summary or "بهبود" in status_summary:
                    st.success("""
                    **توصیه برای مزارع با وضعیت رشد مثبت/بهبود:**
                    - ادامه روند فعلی مدیریت مزرعه
                    - ثبت و مستندسازی روش‌های موفق
                    - به اشتراک‌گذاری تجربیات با سایر مزارع
                    """)
                
                if "ثابت" in status_summary:
                    st.info("""
                    **توصیه برای مزارع با وضعیت ثابت:**
                    - بررسی پتانسیل‌های بهبود وضعیت
                    - مقایسه با مزارع مشابه با وضعیت بهتر
                    - شناسایی عوامل محدودکننده رشد
                    """)
            else:
                st.info("داده‌ای برای گزارش وضعیت کلی در دسترس نیست.")

# Add footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 1rem; color: #6c757d; font-size: 0.9rem;">
    <p>سامانه پایش هوشمند نیشکر | مطالعات کاربردی شرکت کشت و صنعت دهخدا</p>
    <p>ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap</p>
</div>
""", unsafe_allow_html=True)

# Visualization parameters for different indices
VISUALIZATION_PARAMS = {
    'NDVI': {
        'min': 0,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'NDWI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'NDMI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'NDBI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'red']
    },
    'NDSI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'red']
    },
    'SAVI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'EVI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'GNDVI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'OSAVI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'MSAVI': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'NDRE': {
        'min': -1,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    },
    'NDVI_TS': {
        'min': 0,
        'max': 1,
        'palette': ['blue', 'white', 'green']
    }
}

def get_visualization_params(index_name):
    """
    Returns visualization parameters for a given index.
    If the index is not found in the predefined parameters, returns default parameters.
    """
    if index_name in VISUALIZATION_PARAMS:
        return VISUALIZATION_PARAMS[index_name]
    else:
        # Default parameters for unknown indices
        return {
            'min': -1,
            'max': 1,
            'palette': ['blue', 'white', 'green']
        }

def get_processed_image(roi, date_range, index_type):
    """
    Get processed image for visualization with enhanced error handling and logging.
    
    Args:
        roi: Region of interest
        date_range: Tuple of (start_date, end_date)
        index_type: Type of index to calculate
        
    Returns:
        Processed image for visualization
    """
    try:
        logging.info(f"Fetching images for date range: {date_range}")
        start_date, end_date = date_range
        
        # Get image collection
        collection = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2') \
            .filterBounds(roi) \
            .filterDate(start_date, end_date) \
            .sort('CLOUD_COVER')
            
        initial_count = collection.size().getInfo()
        logging.info(f"Initial collection size: {initial_count} images")
        
        if initial_count == 0:
            raise ValueError("No images found for the specified date range and region")
            
        # Apply cloud masking
        def mask_clouds(image):
            cloudShadowBitMask = 1 << 3
            cloudsBitMask = 1 << 5
            qa = image.select('QA_PIXEL')
            mask = qa.bitwiseAnd(cloudShadowBitMask).eq(0).And(
                qa.bitwiseAnd(cloudsBitMask).eq(0))
            return image.updateMask(mask)
            
        collection = collection.map(mask_clouds)
        filtered_count = collection.size().getInfo()
        logging.info(f"Images after cloud masking: {filtered_count}")
        
        if filtered_count == 0:
            raise ValueError("No clear images available after cloud masking")
            
        # Get the least cloudy image
        image = collection.first()
        
        # Calculate the selected index
        if index_type == 'NDVI':
            index = calculate_ndvi(image)
        elif index_type == 'NDWI':
            index = calculate_ndwi(image)
        elif index_type == 'NDMI':
            index = calculate_ndmi(image)
        elif index_type == 'NDBI':
            index = calculate_ndbi(image)
        elif index_type == 'NDSI':
            index = calculate_ndsi(image)
        elif index_type == 'SAVI':
            index = calculate_savi(image)
        elif index_type == 'EVI':
            index = calculate_evi(image)
        elif index_type == 'GNDVI':
            index = calculate_gndvi(image)
        elif index_type == 'OSAVI':
            index = calculate_osavi(image)
        elif index_type == 'MSAVI':
            index = calculate_msavi(image)
        elif index_type == 'NDRE':
            index = calculate_ndre(image)
        else:
            raise ValueError(f"Unsupported index type: {index_type}")
            
        # Get visualization parameters
        vis_params = get_visualization_params(index_type)
        
        # Clip to ROI and apply visualization parameters
        processed_image = index.clip(roi).visualize(vis_params)
        
        # Get the URL for the processed image
        url = processed_image.getThumbURL({
            'format': 'png',
            'dimensions': 512
        })
        
        logging.info(f"Successfully processed image for {index_type}")
        return url
        
    except ee.EEException as e:
        error_msg = str(e)
        if "Computation timed out" in error_msg:
            logging.error("Google Earth Engine computation timed out. Try reducing the region size or date range.")
            raise ValueError("Computation timed out. Please try with a smaller region or shorter date range.")
        elif "User memory limit exceeded" in error_msg:
            logging.error("Google Earth Engine memory limit exceeded. Try reducing the region size.")
            raise ValueError("Memory limit exceeded. Please try with a smaller region.")
        else:
            logging.error(f"Google Earth Engine error: {error_msg}")
            raise ValueError(f"Error processing image: {error_msg}")
            
    except Exception as e:
        logging.error(f"Error in get_processed_image: {str(e)}")
        raise ValueError(f"Error processing image: {str(e)}")
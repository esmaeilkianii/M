# -*- coding: utf-8 -*-
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

        /* Standard Metrics */
        .stMetric {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: right; /* Ensure text aligns right */
            border-left: 5px solid #17a2b8; /* Default border color */
            transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        }
        .stMetric:hover {
            transform: scale(1.03);
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .stMetric > label { /* Metric Label */
            font-weight: 700;
            color: #495057;
        }
        .stMetric > div[data-testid="stMetricValue"] { /* Metric Value */
            font-size: 1.5em;
            font-weight: bold;
            color: #2c3e50;
            direction: ltr; /* Ensure numbers display correctly */
            text-align: right;
        }
        .stMetric > div[data-testid="stMetricDelta"] { /* Metric Delta (optional) */
             font-size: 1em;
             font-weight: normal;
        }


        /* Custom colored metric cards */
        .metric-card-1 { border-left-color: #007bff; } /* Blue */
        .metric-card-2 { border-left-color: #ffc107; } /* Yellow */
        .metric-card-3 { border-left-color: #28a745; } /* Green */
        .metric-card-4 { border-left-color: #dc3545; } /* Red */
        .metric-card-5 { border-left-color: #6f42c1; } /* Purple */


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
        th { /* Table header alignment */
            text-align: right !important;
        }
        td { /* Ensure table data cells are also right-aligned */
             text-align: right !important;
             direction: rtl; /* Right-to-left text direction for content */
        }
        td:last-child { /* Align last column (often numbers or status) to center or left if needed */
           /* text-align: center !important; */
           /* direction: ltr; */ /* Keep default for numbers */
        }


        /* Sidebar */
        .css-1d391kg { /* Adjust this selector based on Streamlit version if sidebar styling fails */
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
        }
        /* Ensure sidebar content like selectbox options are right-aligned */
         .stSelectbox label, .stTextInput label, .stDateInput label {
            text-align: right !important;
            width: 100%;
         }
         .stSelectbox [data-baseweb="select"] > div {
            text-align: right !important;
         }


        /* Custom status badges */
        .status-badge {
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 0.8em;
            font-weight: bold;
            display: inline-block; /* Make badges inline */
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

        /* Folium Legend Styling (if possible within Streamlit) */
        .legend {
             font-family: 'Vazirmatn', sans-serif;
             font-size: 12px;
             direction: rtl;
        }
        .legend-title {
            font-weight: bold;
            margin-bottom: 5px;
            text-align: right;
        }
        .legend-items div {
             text-align: right;
        }
        .legend-items span {
             margin-left: 5px; /* Space between color box and text */
        }


    </style>
""", unsafe_allow_html=True)

# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 11 # Adjusted zoom level

# --- File Paths ---
# ***** UPDATED CSV FILE PATH *****
CSV_FILE_PATH = 'برنامه_ریزی_با_مختصات (1).csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# --- Display Titles ---
st.title(APP_TITLE)
st.caption(APP_SUBTITLE)


# --- Summary Statistics Cards ---
st.markdown("### خلاصه وضعیت کلی") # Header for the cards

# Data from the image provided
summary_data = {
    "داشت ۱۴۰۳": "9008.35", # Using dot for decimal
    "آیش ۱۴۰۳-۰۴": "1703.04",
    "راتون ۱۴۰۴": "7305.31",
    "پلنت ۱۴۰۴": "2115.99",
    "داشت کلی ۱۴۰۴": "9421.3"
}

# Create columns for the cards
cols = st.columns(len(summary_data))

# Assign data to cards with custom CSS classes
card_classes = ["metric-card-1", "metric-card-2", "metric-card-3", "metric-card-4", "metric-card-5"]

for i, (label, value) in enumerate(summary_data.items()):
    with cols[i]:
        # Inject custom CSS class using markdown hack
        st.markdown(f'<div class="stMetric {card_classes[i]}">', unsafe_allow_html=True)
        st.metric(label=label, value=value)
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("---") # Separator

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
    """Loads farm data from the specified CSV file using new column names."""
    try:
        df = pd.read_csv(csv_path)
        # ***** UPDATED REQUIRED COLUMNS *****
        required_cols = ['مزرعه', 'روز', 'longitude', 'latitude'] # 'گروه' is optional based on usage
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            st.error(f"❌ فایل CSV باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}. ستون‌های یافت‌نشده: {', '.join(missing_cols)}")
            return None

        # ***** USE NEW COORDINATE COLUMN NAMES *****
        # Convert coordinate columns to numeric, coercing errors
        df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
        df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')

        # Handle missing coordinates flag explicitly if needed (Assuming no specific 'missing' flag column in new file)
        # Drop rows where coordinates are actually missing after coercion
        initial_rows = len(df)
        df = df.dropna(subset=['longitude', 'latitude'])
        dropped_rows = initial_rows - len(df)
        if dropped_rows > 0:
            st.warning(f"⚠️ {dropped_rows} رکورد به دلیل نداشتن مختصات معتبر حذف شدند.")


        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات).")
            return None

        # ***** USE NEW DAY COLUMN NAME *****
        # Ensure 'روز' is string type for consistent filtering
        if 'روز' in df.columns:
            df['روز'] = df['روز'].astype(str).str.strip()
            # Clean potential whitespace variations in day names
            df['روز'] = df['روز'].str.replace(' ', '', regex=False) # Remove all spaces
            # Example: Make 'سه شنبه' consistent as 'سهشنبه' or handle variations explicitly
            # You might need more specific cleaning based on actual data variations
            df['روز'] = df['روز'].replace({'سهشنبه': 'سه شنبه', 'پنجشنبه': 'پنج شنبه'}) # Example: Standardize specific names if needed AFTER removing spaces


        else:
            st.error("❌ ستون 'روز' در فایل CSV یافت نشد.")
            return None

        # Ensure 'مزرعه' is suitable as key/identifier (e.g., string)
        df['مزرعه'] = df['مزرعه'].astype(str)

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
st.sidebar.header("⚙️ تنظیمات نمایش")

# --- Day of the Week Selection ---
# ***** USE NEW DAY COLUMN NAME *****
try:
    available_days_raw = farm_data_df['روز'].unique()
    # Clean the list of available days for display (e.g., add space back if removed earlier for matching)
    # This depends on how you standardized them in load_farm_data
    available_days_display = sorted([day.replace('پنجشنبه', 'پنج شنبه').replace('سهشنبه', 'سه شنبه') for day in available_days_raw]) # Example for display

    # Map displayed day back to the potentially cleaned version for filtering if needed
    day_display_map = {display: raw for display, raw in zip(available_days_display, sorted(available_days_raw))}


    selected_day_display = st.sidebar.selectbox(
        "📅 روز هفته را انتخاب کنید:",
        options=available_days_display,
        index=0, # Default to the first day
        help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
    )
    # Get the potentially 'cleaned' day name for filtering
    selected_day_filter = day_display_map[selected_day_display]

except KeyError:
    st.sidebar.error("خطا: ستون 'روز' در داده های بارگذاری شده یافت نشد.")
    st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در پردازش روزهای هفته: {e}")
    st.stop()


# --- Filter Data Based on Selected Day ---
# ***** USE cleaned 'selected_day_filter' *****
filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day_filter].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day_display}' یافت نشد.")
    # Don't stop here, allow user to potentially change the day
    # st.stop() # Avoid stopping abruptly

# --- Farm Selection ---
# Check if filtered_farms_df is not empty before proceeding
if not filtered_farms_df.empty:
    try:
        available_farms = sorted(filtered_farms_df['مزرعه'].unique())
        # Add an option for "All Farms"
        farm_options = ["همه مزارع"] + available_farms
        selected_farm_name = st.sidebar.selectbox(
            "🌾 مزرعه مورد نظر را انتخاب کنید:",
            options=farm_options,
            index=0, # Default to "All Farms"
            help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
        )
    except KeyError:
        st.sidebar.error("خطا: ستون 'مزرعه' در داده های فیلتر شده یافت نشد.")
        st.stop()
    except Exception as e:
        st.sidebar.error(f"خطا در پردازش لیست مزارع: {e}")
        st.stop()
else:
    # Handle the case where no farms are available for the selected day
    selected_farm_name = "همه مزارع" # Default or provide a message
    st.sidebar.warning(f"مزرعه‌ای برای انتخاب در روز '{selected_day_display}' وجود ندارد.")


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
# Map Persian day names to Python's weekday() (Monday=0, Sunday=6) - Use the display name
persian_to_weekday = {
    "شنبه": 5,
    "یکشنبه": 6,
    "دوشنبه": 0,
    "سه شنبه": 1, # Use the display format
    "چهارشنبه": 2,
    "پنج شنبه": 3, # Use the display format
    "جمعه": 4,
}

# Check if selected_day_display is valid before proceeding
if selected_day_display in persian_to_weekday:
    try:
        target_weekday = persian_to_weekday[selected_day_display]
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

        st.sidebar.info(f"🗓️ بازه زمانی فعلی: {start_date_current_str} تا {end_date_current_str}")
        st.sidebar.info(f"🗓️ بازه زمانی قبلی: {start_date_previous_str} تا {end_date_previous_str}")

    except Exception as e:
        st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
        st.stop()
else:
    st.sidebar.error(f"نام روز هفته '{selected_day_display}' در دیکشنری persian_to_weekday یافت نشد. لطفاً مقادیر ستون 'روز' در CSV را بررسی کنید.")
    # Provide default dates or stop
    start_date_current_str = (today - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
    end_date_current_str = today.strftime('%Y-%m-%d')
    start_date_previous_str = (today - datetime.timedelta(days=13)).strftime('%Y-%m-%d')
    end_date_previous_str = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    st.sidebar.warning("از بازه‌های زمانی پیش‌فرض استفاده می‌شود.")


# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================

# --- Cloud Masking Function for Sentinel-2 ---
def maskS2clouds(image):
    """Masks clouds in a Sentinel-2 SR image using the QA band."""
    try:
        qa = image.select('QA60')
        # Bits 10 and 11 are clouds and cirrus, respectively.
        cloudBitMask = 1 << 10
        cirrusBitMask = 1 << 11
        # Both flags should be set to zero, indicating clear conditions.
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
                 qa.bitwiseAnd(cirrusBitMask).eq(0))

        # Use SCL band for more robust cloud masking if available
        # Check if 'SCL' band exists before selecting
        if 'SCL' in image.bandNames().getInfo():
            scl = image.select('SCL')
            # Cloud Shadow (3), Cloud Medium Probability (8), Cloud High Probability (9), Cirrus (10)
            cloud_mask = scl.eq(3).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
            mask = mask.And(cloud_mask.Not()) # Combine QA mask and SCL mask

        # Scale and offset factors for Sentinel-2 SR bands (B1 to B12)
        opticalBands = image.select('B.*').multiply(0.0001)

        # Return the image with scaled bands and applied mask
        return image.addBands(opticalBands, None, True).updateMask(mask)
    except Exception as e:
        # st.warning(f"Error masking clouds for an image: {e}") # Optional: log error
        # Return the original image if masking fails for any reason
        # print(f"Warning: Cloud masking failed for image {image.id().getInfo() if image.id() else 'unknown'}. Returning original. Error: {e}")
        return image


# --- Index Calculation Functions ---
def add_indices(image):
    """Calculates and adds various indices as bands to an image."""
    try:
        # Ensure required bands exist before calculation
        required_bands = ['B2', 'B3', 'B4', 'B8', 'B11']
        if not all(band in image.bandNames().getInfo() for band in required_bands):
             # print(f"Warning: Image {image.id().getInfo() if image.id() else 'unknown'} missing required bands for index calculation. Skipping.")
             return image # Return original image if bands are missing

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
        msi = image.expression('B11 / B8', { # Direct band expression
             'B11': image.select('B11'),
             'B8': image.select('B8')
             }).rename('MSI')


        # LAI (Leaf Area Index) - Simple estimation using NDVI (Needs calibration for accuracy)
        # Using a very basic placeholder: LAI proportional to NDVI
        lai = ndvi.multiply(3.5).rename('LAI') # Placeholder - Needs proper calibration

        # CVI (Chlorophyll Vegetation Index) - (NIR / Green) * (Red / Green) | S2: (B8 / B3) * (B4 / B3)
        # Handle potential division by zero if Green band is 0
        green_safe = image.select('B3').max(ee.Image(0.0001)) # Avoid division by zero
        cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
            'NIR': image.select('B8'),
            'GREEN': green_safe,
            'RED': image.select('B4')
        }).rename('CVI')

        return image.addBands([ndvi, evi, ndmi, msi, lai, cvi]) # Add calculated indices
    except Exception as e:
        # st.warning(f"Error calculating indices for an image: {e}") # Optional: log error
        # print(f"Warning: Index calculation failed for image {image.id().getInfo() if image.id() else 'unknown'}. Returning original. Error: {e}")
        # Return the original image if index calculation fails
        return image


# --- Function to get processed image for a date range and geometry ---
#@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True) # Caching can be complex with GEE objects, disable if causing issues
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given geometry and date range.
    _geometry: ee.Geometry (Point or Polygon)
    start_date, end_date: YYYY-MM-DD strings
    index_name: Name of the primary index band to return (e.g., 'NDVI')
    """
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)) # Pre-filter very cloudy scenes
                     .map(maskS2clouds)) # Apply cloud masking

        # Check if any images are available after filtering
        count = s2_sr_col.size().getInfo()
        if count == 0:
            # st.warning(f"هیچ تصویر Sentinel-2 بدون ابر در بازه {start_date} تا {end_date} یافت نشد.")
            return None, f"No suitable Sentinel-2 images found for {start_date} to {end_date} (0 images after filtering)."

        # Calculate indices for each image in the collection
        indexed_col = s2_sr_col.map(add_indices)

        # Select the specific index band *before* median to potentially save memory
        index_only_col = indexed_col.select(index_name)

        # Create a median composite image
        # Use .unmask() if you want to fill masked pixels (e.g., with 0 or NaN) before median
        # median_image = index_only_col.median().unmask(ee.Number(0)) # Example: fill with 0
        median_image = index_only_col.median() # Default: median ignores masked pixels

        # Clip to the geometry if it's a polygon to potentially reduce data size
        if _geometry.type().getInfo() == 'Polygon':
            median_image = median_image.clip(_geometry)

        return median_image, None # Return the image and no error message

    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine در get_processed_image: {e}"
        # Try to extract more details if available
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'computation timed out' in error_details.lower():
                     error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
                elif 'user memory limit exceeded' in error_details.lower():
                     error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
                elif 'resolution' in error_details.lower():
                     error_message += "\n(ممکن است مربوط به مقیاس (scale) در reduceRegion باشد)"
                elif 'image.select' in error_details.lower() and 'not found' in error_details.lower():
                     error_message += f"\n(خطا: باند مورد نیاز برای شاخص '{index_name}' در برخی تصاویر یافت نشد)"
                elif 'collection.size: Unable to compute' in error_details:
                     error_message += "\n(خطا در محاسبه تعداد تصاویر اولیه - ممکن است مشکل دسترسی یا فیلتر GEE باشد)"

        except Exception:
            pass # Ignore errors during error detail extraction
        # st.error(error_message) # Show error in main app? Maybe return it is better.
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE (get_processed_image): {e}\n{traceback.format_exc()}"
        # st.error(error_message)
        return None, error_message

# --- Function to get time series data for a point ---
#@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True) # Caching can be complex with GEE objects
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets a time series of a specified index for a point geometry."""
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     # Consider adding a cloud filter here too, although maskS2clouds should handle it
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50)) # Stricter cloud filter for time series
                     .map(maskS2clouds)
                     .map(add_indices)
                     .filter(ee.Filter.listContains('system:band_names', index_name))) # Ensure index band exists

        def extract_value(image):
            try:
                # Extract the index value at the point
                # Use reduceRegion for points; scale should match sensor resolution
                # Use firstNonNull to get the first valid pixel value at the point
                value = image.select(index_name).reduceRegion(
                    reducer=ee.Reducer.firstNonNull(),
                    geometry=_point_geom,
                    scale=10 # Scale in meters (10m for Sentinel-2 relevant bands)
                ).get(index_name)

                # Only return feature if value is not null
                return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}) \
                        .set('hasValue', ee.Algorithms.IsEqual(value, None).Not()) # Check if value is null

            except Exception as reduce_err:
                 # If reduceRegion fails for an image, return null feature
                 # print(f"Warning: reduceRegion failed for image {image.id().getInfo() if image.id() else 'unknown'} in time series. Error: {reduce_err}")
                 return ee.Feature(None, {'hasValue': False})


        # Map over the collection and filter out features where value extraction failed or was null
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.eq('hasValue', True))

        # Limit the number of features to avoid GEE compute limits if necessary
        # ts_features = ts_features.limit(300, 'system:time_start', False) # Get 300 most recent

        # Convert the FeatureCollection to a list of dictionaries
        # Use getInfo() which can be slow/fail for large collections
        try:
            ts_info = ts_features.getInfo()['features']
        except ee.EEException as e:
             if 'too large' in str(e).lower():
                  # If getInfo fails due to size, try exporting or reducing the date range
                  return pd.DataFrame(columns=['date', index_name]), f"خطای GEE: مجموعه داده سری زمانی بیش از حد بزرگ است ({e}). بازه زمانی را کوتاه‌تر کنید."
             else:
                  raise e # Re-raise other GEE errors


        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای سری زمانی {index_name} یافت نشد (پس از فیلتر)."

        # Convert to Pandas DataFrame more carefully
        ts_data = []
        for f in ts_info:
            props = f.get('properties', {})
            date_val = props.get('date')
            index_val = props.get(index_name)
            # Ensure both date and value are present
            if date_val is not None and index_val is not None:
                 ts_data.append({'date': date_val, index_name: index_val})


        if not ts_data:
             return pd.DataFrame(columns=['date', index_name]), f"داده معتبری برای سری زمانی {index_name} یافت نشد (پس از فیلتر نهایی)."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df[index_name] = pd.to_numeric(ts_df[index_name], errors='coerce')
        ts_df = ts_df.dropna(subset=[index_name]) # Ensure numeric conversion worked
        ts_df = ts_df.sort_values('date').set_index('date')

        return ts_df, None # Return DataFrame and no error
    except ee.EEException as e:
        error_message = f"خطای GEE در دریافت سری زمانی: {e}"
        # st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"
        # st.error(error_message)
        return pd.DataFrame(columns=['date', index_name]), error_message


# ==============================================================================
# Main Panel Display
# ==============================================================================

# --- Get Selected Farm Geometry and Details ---
selected_farm_details = None
selected_farm_geom = None
map_needs_update = True # Flag to control map rendering

# Only proceed if there are farms for the selected day
if filtered_farms_df.empty and selected_farm_name == "همه مزارع":
     st.warning(f"داده‌ای برای نمایش در روز '{selected_day_display}' وجود ندارد.")
     map_needs_update = False # Don't try to draw map or tables
elif selected_farm_name == "همه مزارع":
    # Use the bounding box of all filtered farms for the map view
    try:
        # ***** USE NEW COORDINATE COLUMN NAMES *****
        min_lon, min_lat = filtered_farms_df['longitude'].min(), filtered_farms_df['latitude'].min()
        max_lon, max_lat = filtered_farms_df['longitude'].max(), filtered_farms_df['latitude'].max()
        # Create a bounding box geometry
        # Add a small buffer if min/max are the same (single point farm)
        if min_lon == max_lon and min_lat == max_lat:
            buffer = 0.001 # Small buffer in degrees
            selected_farm_geom = ee.Geometry.Rectangle([min_lon-buffer, min_lat-buffer, max_lon+buffer, max_lat+buffer])
        else:
            selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])

        st.subheader(f"🗺️ نمایش کلی مزارع برای روز: {selected_day_display}")
        st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
    except Exception as e:
        st.error(f"خطا در ایجاد محدوده برای نمایش همه مزارع: {e}")
        map_needs_update = False
else:
    # Handle single farm selection
    try:
        selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        # ***** USE NEW COORDINATE COLUMN NAMES *****
        lat = selected_farm_details['latitude']
        lon = selected_farm_details['longitude']
        if pd.isna(lat) or pd.isna(lon):
            st.error(f"مختصات نامعتبر برای مزرعه {selected_farm_name}.")
            map_needs_update = False
        else:
            selected_farm_geom = ee.Geometry.Point([lon, lat])
            st.subheader(f"📍 جزئیات مزرعه: {selected_farm_name} (روز: {selected_day_display})")
            # Display farm details - use .get() for robustness if columns missing
            details_cols = st.columns(3)
            with details_cols[0]:
                # Assuming 'مساحت', 'واریته' etc. might still exist or use 'گروه' if relevant
                st.metric("گروه", f"{selected_farm_details.get('گروه', 'N/A')}") # Example using 'گروه' if it exists
                st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A") # Keep if 'مساحت' exists
            with details_cols[1]:
                st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}") # Keep if 'واریته' exists
                st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}") # Keep if 'سن' exists
            with details_cols[2]:
                st.metric("کانال", f"{selected_farm_details.get('کانال', 'N/A')}") # Keep if 'کانال' exists
                st.metric("اداره", f"{selected_farm_details.get('اداره', 'N/A')}") # Keep if 'اداره' exists
                # ***** DISPLAY NEW COORDINATE COLUMN NAMES *****
                st.metric("مختصات (Lat, Lon)", f"{lat:.5f}, {lon:.5f}")
    except IndexError:
        st.error(f"اطلاعات مزرعه '{selected_farm_name}' یافت نشد (ممکن است در داده‌های فیلتر شده نباشد).")
        map_needs_update = False
    except KeyError as e:
         st.error(f"خطا: ستون مورد نیاز ({e}) برای نمایش جزئیات مزرعه یافت نشد.")
         map_needs_update = False
    except Exception as e:
        st.error(f"خطا در نمایش جزئیات مزرعه: {e}")
        map_needs_update = False


# --- Map Display ---
if map_needs_update:
    st.markdown("---")
    st.subheader("🛰️ نقشه وضعیت مزارع")

    # Define visualization parameters based on the selected index
    vis_params = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # Detailed green palette
        'EVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']}, # Red-Blue for moisture
        'LAI': {'min': 0, 'max': 7, 'palette': ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#006d2c', '#00441b']}, # Sequential green for LAI
        'MSI': {'min': 0, 'max': 3, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b']}, # Blue-Red for stress (lower = wetter/less stress)
        'CVI': {'min': 0, 'max': 25, 'palette': ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#1d91c0', '#225ea8', '#0c2c84']}, # Yellow-Green-Blue for Chlorophyll
    }

    map_center_lat = INITIAL_LAT
    map_center_lon = INITIAL_LON
    initial_zoom = INITIAL_ZOOM

    # Create a geemap Map instance
    m = geemap.Map(
        location=[map_center_lat, map_center_lon],
        zoom=initial_zoom,
        add_google_map=False # Start clean
    )
    m.add_basemap("HYBRID") # Add Google Satellite Hybrid basemap

    # Get the processed image for the current week
    if selected_farm_geom:
        # Use a spinner while processing the image for the map
        with st.spinner(f"در حال پردازش تصویر {selected_index} برای نقشه..."):
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
            )

        if error_msg_current:
            st.warning(f"خطا در پردازش تصویر برای دوره جاری: {error_msg_current}")

        if gee_image_current:
            # Add the GEE layer to the map
            try:
                current_vis = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}) # Default vis
                m.addLayer(
                    gee_image_current,
                    current_vis,
                    f"{selected_index} ({start_date_current_str} تا {end_date_current_str})"
                )

                # --- Add Custom Legend ---
                legend_title_text = f"{selected_index} ({index_options.get(selected_index, '')})"
                palette = current_vis.get('palette', [])
                min_val = current_vis.get('min', 0)
                max_val = current_vis.get('max', 1)

                # Adjust labels for specific indices for clarity
                if selected_index in ['NDVI', 'EVI']:
                    legend_dict = {"بالا (سالم)": palette[-1], "متوسط": palette[len(palette)//2], "پایین (ضعیف)": palette[0]}
                elif selected_index == 'NDMI':
                     legend_dict = {"مرطوب": palette[-1], "متوسط": palette[len(palette)//2], "خشک": palette[0]}
                elif selected_index == 'MSI':
                     # Note: Palette for MSI goes Blue(wet) to Red(dry), but dict keys reflect condition
                     legend_dict = {"تنش کم (مرطوب)": palette[0], "متوسط": palette[len(palette)//2], "تنش بالا (خشک)": palette[-1]}
                elif selected_index == 'LAI':
                     legend_dict = {"LAI بالا": palette[-1], "LAI متوسط": palette[len(palette)//2], "LAI پایین": palette[0]}
                elif selected_index == 'CVI':
                     legend_dict = {"کلروفیل بالا": palette[-1], "کلروفیل متوسط": palette[len(palette)//2], "کلروفیل پایین": palette[0]}
                else: # Default legend based on palette values
                    steps = len(palette)
                    legend_dict = {}
                    if steps > 1:
                         legend_dict[f"بالا ({max_val:.2f})"] = palette[-1]
                         legend_dict[f"متوسط ({min_val + (max_val - min_val)/2:.2f})"] = palette[len(palette)//2]
                         legend_dict[f"پایین ({min_val:.2f})"] = palette[0]
                    elif steps == 1:
                         legend_dict[f"{min_val:.2f} - {max_val:.2f}"] = palette[0]


                # ***** CORRECTED KEYWORD ARGUMENT: Use 'title' instead of 'legend_title' *****
                m.add_legend(title=legend_title_text, legend_dict=legend_dict, position='bottomright')


                # Add markers for farms
                if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
                     # Add markers for all filtered farms
                     for idx, farm in filtered_farms_df.iterrows():
                         # ***** USE NEW COORDINATE COLUMN NAMES *****
                         lat_f, lon_f = farm['latitude'], farm['longitude']
                         if pd.notna(lat_f) and pd.notna(lon_f): # Check coords are valid
                             folium.Marker(
                                 location=[lat_f, lon_f],
                                 popup=(f"<b>مزرعه:</b> {farm['مزرعه']}<br>"
                                        #f"<b>گروه:</b> {farm.get('گروه', 'N/A')}<br>" # Uncomment if 'گروه' column exists and is useful
                                        f"<b>روز:</b> {farm.get('روز', 'N/A')}<br>"
                                        f"<b>کانال:</b> {farm.get('کانال', 'N/A')}<br>" # Keep if relevant
                                        f"<b>اداره:</b> {farm.get('اداره', 'N/A')}"), # Keep if relevant
                                 tooltip=farm['مزرعه'],
                                 icon=folium.Icon(color='blue', icon='info-sign')
                             ).add_to(m)
                     # Adjust map bounds if showing all farms
                     if selected_farm_geom: # Ensure geom exists
                        m.center_object(selected_farm_geom, zoom=initial_zoom) # Center on the bounding box
                elif selected_farm_details is not None and selected_farm_geom:
                     # Add marker for the single selected farm
                     # ***** USE lat, lon derived earlier *****
                     folium.Marker(
                         location=[lat, lon],
                         popup=(f"<b>مزرعه:</b> {selected_farm_name}<br>"
                                f"<b>{selected_index} (هفته جاری):</b> در حال محاسبه...<br>" # Placeholder, value added later if needed
                                f"<b>کانال:</b> {selected_farm_details.get('کانال', 'N/A')}<br>"
                                f"<b>اداره:</b> {selected_farm_details.get('اداره', 'N/A')}"),
                         tooltip=selected_farm_name,
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=15) # Zoom closer for a single farm

                m.add_layer_control() # Add layer control to toggle base maps and layers

            except ee.EEException as map_err:
                st.error(f"خطا در افزودن لایه GEE به نقشه: {map_err}")
                # st.error(traceback.format_exc())
            except Exception as map_err:
                st.error(f"خطا در ایجاد نقشه یا افزودن نشانگرها: {map_err}")
                st.error(traceback.format_exc())
        else:
            # Handle case where GEE image could not be processed but geom exists
            st.warning(f"تصویری برای نمایش روی نقشه در بازه زمانی جاری یافت نشد یا قابل پردازش نبود.")
            # Still show markers if possible
            try:
                if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
                     for idx, farm in filtered_farms_df.iterrows():
                          lat_f, lon_f = farm['latitude'], farm['longitude']
                          if pd.notna(lat_f) and pd.notna(lon_f):
                              folium.Marker(location=[lat_f, lon_f], tooltip=farm['مزرعه']).add_to(m)
                     if selected_farm_geom: m.center_object(selected_farm_geom, zoom=initial_zoom)
                elif selected_farm_details is not None and selected_farm_geom:
                     folium.Marker(location=[lat, lon], tooltip=selected_farm_name).add_to(m)
                     m.center_object(selected_farm_geom, zoom=15)
                m.add_layer_control()
            except Exception as marker_err:
                 st.error(f"خطا در افزودن نشانگرها به نقشه خالی: {marker_err}")


    # Display the map in Streamlit
    st_folium(m, width=None, height=500, use_container_width=True, returned_objects=[]) # returned_objects=[] might prevent some callback issues
    st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها (بالا سمت راست) برای تغییر نقشه پایه و روشن/خاموش کردن لایه شاخص استفاده کنید.")
    st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")
else:
    # If map_needs_update is False, show a message instead of the map section
    st.markdown("---")
    st.warning("نقشه به دلیل عدم وجود داده‌های معتبر یا انتخاب مزرعه نامعتبر، نمایش داده نمی‌شود.")


# --- Time Series Chart ---
if map_needs_update: # Only show chart if map was attempted
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom:
        # Check if the geometry is a Point
        is_point = False
        if selected_farm_geom: # Check if geom exists first
            try:
                is_point = selected_farm_geom.type().getInfo() == 'Point'
            except Exception as geom_err:
                st.warning(f"خطا در بررسی نوع هندسه مزرعه: {geom_err}")

        if is_point:
            # Define a longer period for the time series chart (e.g., last 6-12 months)
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d') # 1 year

            with st.spinner(f"در حال دریافت داده‌های سری زمانی {selected_index} برای {selected_farm_name}..."):
                ts_df, ts_error = get_index_time_series(
                    selected_farm_geom,
                    selected_index,
                    start_date=timeseries_start_date,
                    end_date=timeseries_end_date
                )

            if ts_error:
                st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                try:
                    # Create interactive chart with Plotly
                    fig = px.line(ts_df, y=selected_index, markers=True,
                                  title=f"روند تغییرات {selected_index} برای مزرعه {selected_farm_name}",
                                  labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                    fig.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                    fig.update_traces(line_color='#17a2b8', marker=dict(color='#17a2b8'))
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در یک سال گذشته (نقاط نشان‌دهنده تصاویر ماهواره‌ای بدون ابر هستند).")
                except Exception as chart_err:
                    st.error(f"خطا در رسم نمودار: {chart_err}")
                    # Fallback to basic chart if plotly fails
                    try:
                        st.line_chart(ts_df[selected_index])
                    except Exception as basic_chart_err:
                        st.error(f"خطا در رسم نمودار پایه: {basic_chart_err}")
            else:
                st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده (یک سال اخیر) یافت نشد.")
        else:
            st.warning("نمودار سری زمانی فقط برای مزارع منفرد (با مختصات نقطه‌ای) قابل نمایش است.")
    # else: # Case handled by selected_farm_name == "همه مزارع" or map_needs_update=False
    #     st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست.")


# --- Ranking Table ---
if map_needs_update and not filtered_farms_df.empty: # Only show table if map was attempted and data exists for the day
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day_display})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    # Use a separate cache for ranking calculation as it depends on more inputs
    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist="disk") # Persist to disk might help with large datasets
    def calculate_weekly_indices(_farms_df_subset_records, index_name, start_curr, end_curr, start_prev, end_prev, _selected_day_cache_key):
        """Calculates the average index value for the current and previous week for a list of farms."""
        # Input is now a list of dicts to be cache-friendly
        # Note: _selected_day_cache_key added to make cache specific to the selected day

        results = []
        errors = []
        total_farms = len(_farms_df_subset_records)
        # Avoid progress bar inside cached function directly

        for i, farm_info in enumerate(_farms_df_subset_records):
            farm_name = farm_info.get('مزرعه', 'نامشخص')
            lat = farm_info.get('latitude')
            lon = farm_info.get('longitude')

            # Basic check before creating point
            if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                errors.append(f"{farm_name}: مختصات نامعتبر.")
                # Add placeholder result to maintain row count if needed, or just skip
                results.append({
                    'مزرعه': farm_name,
                    'کانال': farm_info.get('کانال', 'N/A'),
                    'اداره': farm_info.get('اداره', 'N/A'),
                    f'{index_name} (هفته جاری)': None,
                    f'{index_name} (هفته قبل)': None,
                    'تغییر': None
                })
                continue

            point_geom = ee.Geometry.Point([lon, lat])

            def get_mean_value(start, end):
                # This function uses GEE and cannot be directly part of the cached function's core logic
                # if we want the results to be cached. We calculate GEE results *outside* or accept
                # that this part is re-run. For simplicity here, we keep it, but acknowledge cache limitations.
                try:
                    image, error = get_processed_image(point_geom, start, end, index_name)
                    if image:
                        # Reduce region to get the mean value at the point
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=point_geom,
                            scale=10,  # Scale in meters
                            maxPixels=1e9 # Increase maxPixels if needed
                        ).getInfo()
                        # Check if the key exists and value is not None
                        value = mean_dict.get(index_name) if mean_dict else None
                        return value if value is not None else None, None # Return None if value is null
                    else:
                        # If no image, error message should explain why
                        return None, error if error else "No image found"
                except ee.EEException as e:
                    # Catch GEE errors during reduceRegion or getInfo
                    err_detail = str(e)
                    error_reason = f"خطای GEE ({e})"
                    if 'reduceRegion' in err_detail.lower() and 'memory' in err_detail.lower():
                        error_reason = "خطای حافظه GEE"
                    elif 'reduceRegion' in err_detail.lower() and 'time limit' in err_detail.lower():
                        error_reason = "پایان زمان GEE"
                    elif 'cannot be applied to objects of type <null>' in err_detail.lower():
                         error_reason = "خطای داده Null در GEE" # Often due to masked inputs
                    return None, error_reason
                except Exception as e:
                     # Catch other potential errors
                     return None, f"خطای محاسبه: {e}"


            # Calculate for current week
            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (جاری: {start_curr}-{end_curr}): {err_curr}")

            # Calculate for previous week
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (قبل: {start_prev}-{end_prev}): {err_prev}")


            # Calculate change only if both values are valid numbers
            change = None
            # Check if values are numeric before subtracting
            if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                 change = current_val - previous_val


            results.append({
                'مزرعه': farm_name,
                # Include other details if needed and present in farm_info
                'کانال': farm_info.get('کانال', 'N/A'),
                'اداره': farm_info.get('اداره', 'N/A'),
                f'{index_name} (هفته جاری)': current_val,
                f'{index_name} (هفته قبل)': previous_val,
                'تغییر': change
            })

            # Update progress outside the loop if needed

        return pd.DataFrame(results), errors

    # Prepare subset of data for caching (convert to list of dicts)
    cols_needed = ['مزرعه', 'latitude', 'longitude', 'کانال', 'اداره'] # Adjust if needed
    cols_available = [col for col in cols_needed if col in filtered_farms_df.columns]
    # Use 'records' that are JSON serializable for caching
    farms_subset_records = filtered_farms_df[cols_available].to_dict('records')


    # Calculate and display the ranking table
    # Add a progress bar here
    ranking_progress = st.progress(0)
    status_text = st.text(f"در حال محاسبه شاخص {selected_index} برای {len(farms_subset_records)} مزرعه...")
    ranking_df = pd.DataFrame() # Initialize empty DataFrame
    calculation_errors = []
    try:
        ranking_df, calculation_errors = calculate_weekly_indices(
            farms_subset_records, # Pass list of dicts
            selected_index,
            start_date_current_str,
            end_date_current_str,
            start_date_previous_str,
            end_date_previous_str,
            selected_day_display # Pass display day as cache key part
        )
        ranking_progress.progress(1.0) # Mark as complete
        status_text.text(f"محاسبه شاخص {selected_index} برای {len(ranking_df)} مزرعه کامل شد.")
        ranking_progress.empty() # Remove progress bar after a short delay or success message
    except Exception as calc_err:
        ranking_progress.empty()
        status_text.text(f"خطا در محاسبه رتبه‌بندی.")
        st.error(f"خطای کلی در محاسبه رتبه‌بندی: {calc_err}")
        st.error(traceback.format_exc())
        calculation_errors.append(f"خطای کلی: {calc_err}")


    # Display any errors that occurred during calculation
    if calculation_errors:
        st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها رخ داد:")
        error_expander = st.expander("مشاهده جزئیات خطاها", expanded=False)
        with error_expander:
            # Show unique errors to avoid repetition
            unique_errors = sorted(list(set(calculation_errors)))
            for error in unique_errors[:20]: # Limit displayed errors
                st.caption(f"- {error}")
            if len(unique_errors) > 20:
                 st.caption(f"... و {len(unique_errors) - 20} خطای منحصربفرد دیگر.")
        # Show only a summary count if too many errors
        if len(calculation_errors) > 5:
             st.warning(f"(تعداد کل رخدادهای خطا: {len(calculation_errors)})")


    if not ranking_df.empty:
        # Drop rows that might have been added as placeholders for invalid coords
        ranking_df = ranking_df.dropna(subset=[f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)'], how='all')


        if not ranking_df.empty:
            # Sort by the current week's index value
            ascending_sort = selected_index in ['MSI'] # Indices where lower is generally 'better' (less stress)
            sort_col = f'{selected_index} (هفته جاری)'
            try:
                # Convert column to numeric before sorting, coercing errors
                ranking_df[sort_col] = pd.to_numeric(ranking_df[sort_col], errors='coerce')
                ranking_df_sorted = ranking_df.sort_values(
                    by=sort_col,
                    ascending=ascending_sort,
                    na_position='last' # Put farms with no data at the bottom
                ).reset_index(drop=True)
            except KeyError:
                 st.error(f"خطا: ستون مرتب‌سازی '{sort_col}' یافت نشد.")
                 ranking_df_sorted = ranking_df.reset_index(drop=True) # Use unsorted if sort fails
            except Exception as sort_err:
                 st.error(f"خطا در مرتب‌سازی جدول: {sort_err}")
                 ranking_df_sorted = ranking_df.reset_index(drop=True) # Use unsorted if sort fails


            # Add rank number (1-based index)
            ranking_df_sorted.index = ranking_df_sorted.index + 1
            ranking_df_sorted.index.name = 'رتبه'

            # Add a status column based on 'change'
            def determine_status(row, index_name):
                change_val = row['تغییر'] # Already calculated or None
                current_val = row[f'{index_name} (هفته جاری)']

                # Check for None or NaN explicitly
                if pd.isna(change_val):
                    if pd.isna(current_val):
                         return "بدون داده" # No data for either week
                    else:
                         return "داده جدید" # Data only for current week
                elif not isinstance(change_val, (int, float)):
                    # If change is not numeric (e.g., an error string), mark as error
                    return "خطا در مقایسه"

                # Define thresholds for significant change (adjust as needed)
                threshold = 0.05 # Example threshold for NDVI/EVI/NDMI
                if index_name == 'MSI': threshold = 0.1 # Example for MSI
                if index_name == 'LAI': threshold = 0.2 # Example for LAI
                if index_name == 'CVI': threshold = 1.0 # Example for CVI

                # Status logic based on index type
                positive_change_label = "رشد مثبت"
                negative_change_label = "تنش/کاهش"
                improve_label = "بهبود (رطوبت/تنش)"
                worsen_label = "بدتر شدن (رطوبت/تنش)"

                if index_name in ['NDVI', 'EVI', 'LAI', 'CVI']: # Higher is better
                    if change_val > threshold: return positive_change_label
                    elif change_val < -threshold: return negative_change_label
                    else: return "ثابت"
                elif index_name in ['NDMI']: # Higher is wetter (often better for crops)
                    if change_val > threshold: return improve_label # More moist
                    elif change_val < -threshold: return worsen_label # Dryer
                    else: return "ثابت"
                elif index_name in ['MSI']: # Lower is wetter/less stress (better)
                    if change_val < -threshold: return improve_label # Less stress
                    elif change_val > threshold: return worsen_label # More stress
                    else: return "ثابت"
                else: # Default/unknown index
                    if change_val > threshold: return "افزایش"
                    elif change_val < -threshold: return "کاهش"
                    else: return "ثابت"

            ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)

            # Format numbers for better readability *after* status calculation
            cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
            for col in cols_to_format:
                if col in ranking_df_sorted.columns:
                     # Apply formatting, handling potential non-numeric 'N/A' or None
                     ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{x:.3f}" if isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else str(x)))


            # Define columns to display
            display_cols = ['مزرعه', 'کانال', 'اداره', f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر', 'وضعیت']
            # Filter out columns that might not exist in the source CSV (like کانال, اداره) if they weren't found
            display_cols_final = ['رتبه'] + [col for col in display_cols if col in ranking_df_sorted.columns]


            # Display the table using st.dataframe for better interactivity
            st.dataframe(ranking_df_sorted[display_cols_final], use_container_width=True)

            # --- Status Summary ---
            st.subheader("📊 خلاصه وضعیت تغییرات هفتگی")
            if 'وضعیت' in ranking_df_sorted.columns:
                status_counts = ranking_df_sorted['وضعیت'].value_counts()

                # Map status labels to icons/colors for summary display
                status_map = {
                    "رشد مثبت": ("🟢", "مثبت"),
                    "بهبود (رطوبت/تنش)": ("🟢", "مثبت"),
                    "ثابت": ("⚪", "خنثی"),
                    "تنش/کاهش": ("🔴", "منفی"),
                    "بدتر شدن (رطوبت/تنش)": ("🔴", "منفی"),
                    "داده جدید": ("🆕", "نامشخص"), # New status for first week data
                    "خطا در مقایسه": ("⚠️", "نامشخص"),
                    "بدون داده": ("⚫", "نامشخص"),
                     # Add default for unknown statuses
                     "افزایش": ("🟢", "مثبت"),
                     "کاهش": ("🔴", "منفی"),
                }

                # Group counts by type (Positive, Negative, Neutral, Unknown)
                summary_counts = {"مثبت": 0, "منفی": 0, "خنثی": 0, "نامشخص": 0}
                for status, count in status_counts.items():
                    icon, type = status_map.get(status, ("❓", "نامشخص"))
                    summary_counts[type] += count

                # Display summary counts using columns and metrics
                num_cols_to_show = len([c for c in summary_counts.values() if c > 0])
                if num_cols_to_show > 0:
                    summary_cols = st.columns(num_cols_to_show)
                    col_idx = 0
                    if summary_counts["مثبت"] > 0:
                        with summary_cols[col_idx]:
                            st.metric("🟢 بهبود یافته", summary_counts["مثبت"])
                        col_idx += 1
                    if summary_counts["خنثی"] > 0:
                         with summary_cols[col_idx]:
                             st.metric("⚪ ثابت", summary_counts["خنثی"])
                         col_idx += 1
                    if summary_counts["منفی"] > 0:
                        with summary_cols[col_idx]:
                            st.metric("🔴 بدتر شده", summary_counts["منفی"])
                        col_idx += 1
                    # Combine all 'نامشخص' types
                    if summary_counts["نامشخص"] > 0:
                         with summary_cols[col_idx]:
                             st.metric("⚫ نامشخص/جدید/خطا", summary_counts["نامشخص"])
                         col_idx += 1
                else:
                     st.info("خلاصه‌ای برای نمایش وجود ندارد.")


                # Add explanation expander
                with st.expander("راهنمای وضعیت‌ها", expanded=False):
                    st.markdown("""
                    *   **🟢 بهبود یافته**: وضعیت شاخص نسبت به هفته قبل بهتر شده است.
                    *   **⚪ ثابت**: تغییر قابل توجهی نسبت به هفته قبل وجود ندارد.
                    *   **🔴 بدتر شده**: وضعیت شاخص نسبت به هفته قبل نامطلوب‌تر شده است.
                    *   **⚫ نامشخص/جدید/خطا**: داده کافی برای مقایسه وجود نداشته (ممکن است داده فقط برای هفته جاری موجود باشد 'داده جدید'، یا خطایی در محاسبه رخ داده باشد، یا داده‌ای موجود نباشد 'بدون داده').
                    """)

                # --- Download Button ---
                try:
                    # Re-create the final display DF for download if needed (with rank as column)
                    download_df = ranking_df_sorted[display_cols_final].reset_index() # Keep rank as column
                    csv_data = download_df.to_csv(index=False, encoding='utf-8-sig') # Use utf-8-sig for Excel compatibility
                    st.download_button(
                        label="📥 دانلود جدول رتبه‌بندی (CSV)",
                        data=csv_data,
                        file_name=f'ranking_{selected_index}_{selected_day_display.replace(" ", "_")}_{end_date_current_str}.csv',
                        mime='text/csv',
                    )
                except Exception as e:
                    st.error(f"خطا در ایجاد فایل دانلود: {e}")

            else:
                 st.info("ستون 'وضعیت' برای نمایش خلاصه در دسترس نیست.")
        else:
            st.info(f"پس از حذف رکوردهای نامعتبر، داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")

    elif not calculation_errors: # If DF is empty but no errors reported during calculation
        st.info(f"محاسبات انجام شد، اما نتیجه‌ای برای جدول رتبه‌بندی {selected_index} در این بازه زمانی یافت نشد.")


st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط [گروه مطالعات کاربردی] با استفاده از Streamlit, Google Earth Engine, و geemap.")
st.sidebar.markdown(f"آخرین بروزرسانی داده‌ها: {today.strftime('%Y-%m-%d')}") # Indicate data freshness
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
            width: 100%; /* Ensure dataframe uses container width */
        }
        th { /* Table header alignment */
            text-align: right !important;
            background-color: #f2f2f2; /* Light grey background for header */
        }
        td { /* Ensure table data cells are also right-aligned */
             text-align: right !important;
             direction: rtl; /* Right-to-left text direction for content */
             padding: 8px; /* Add padding to cells */
             border-bottom: 1px solid #ddd; /* Add horizontal lines */
        }
        /* Align numeric/status columns potentially differently */
        .dataframe td:nth-last-child(1), /* Last column (وضعیت) */
        .dataframe td:nth-last-child(2), /* تغییر */
        .dataframe td:nth-last-child(3), /* هفته قبل */
        .dataframe td:nth-last-child(4) { /* هفته جاری */
           text-align: center !important; /* Center align these columns */
           direction: ltr; /* Ensure numbers/status display LTR */
        }


        /* Sidebar */
        .css-1d391kg { /* Adjust this selector based on Streamlit version if sidebar styling fails */
            font-family: 'Vazirmatn', sans-serif;
            direction: rtl;
            padding-right: 1rem; /* Add some padding to the right of the sidebar */
        }
        /* Ensure sidebar widgets and labels are right-aligned */
         .stSelectbox > label, .stTextInput > label, .stDateInput > label, .stButton > button {
            text-align: right !important;
            width: 100%; /* Make labels take full width */
            display: block; /* Ensure label is block element */
         }
         .stSelectbox [data-baseweb="select"] > div {
            text-align: right !important;
            direction: rtl; /* Align text inside selectbox right */
         }
         /* Ensure sidebar text/info is right-aligned */
         .stSidebar .stMarkdown, .stSidebar .stInfo, .stSidebar .stWarning, .stSidebar .stError {
             text-align: right;
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
             font-family: 'Vazirmatn', sans-serif !important;
             font-size: 12px !important;
             direction: rtl !important;
        }
        .legend-title {
            font-weight: bold !important;
            margin-bottom: 5px !important;
            text-align: right !important;
        }
        .legend-items div {
             text-align: right !important;
             margin-bottom: 2px; /* Space between legend items */
        }
        .legend-items span {
             margin-left: 5px !important; /* Space between color box and text */
             vertical-align: middle; /* Align text vertically with color box */
        }
        .legend-items i { /* Style the color box */
            width: 15px;
            height: 15px;
            float: right; /* Position color box to the right */
            margin-left: 8px; /* Space between box and text */
            opacity: 0.7;
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
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # Keep your service account file name

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
            df['روز'] = df['روز'].str.replace(' ', '', regex=False) # Remove all spaces first
            # Standardize specific names if needed AFTER removing spaces
            # This mapping should match the keys used in persian_to_weekday later
            day_standardization_map = {
                'سهشنبه': 'سه شنبه',
                'پنجشنبه': 'پنج شنبه',
                # Add other potential variations if necessary
            }
            df['روز_cleaned'] = df['روز'].replace(day_standardization_map)
            # Create a display version if needed (or use the cleaned one directly if suitable)
            df['روز_display'] = df['روز_cleaned'] # Assuming cleaned version is good for display

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
    farm_data_df_raw = load_farm_data()
else:
    st.error("❌ امکان ادامه کار بدون اتصال به Google Earth Engine وجود ندارد.")
    st.stop()

if farm_data_df_raw is None:
    st.error("❌ امکان ادامه کار بدون داده‌های مزارع وجود ندارد.")
    st.stop()


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("⚙️ تنظیمات نمایش")

# --- Day of the Week Selection ---
try:
    # Use the display version for the selectbox options
    available_days_display = sorted(farm_data_df_raw['روز_display'].unique())

    selected_day_display = st.sidebar.selectbox(
        "📅 روز هفته را انتخاب کنید:",
        options=available_days_display,
        index=0, # Default to the first day
        help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
    )
    # Find the corresponding 'cleaned' name for filtering based on the display selection
    selected_day_filter = farm_data_df_raw[farm_data_df_raw['روز_display'] == selected_day_display]['روز_cleaned'].iloc[0]

except KeyError:
    st.sidebar.error("خطا: ستون 'روز_display' یا 'روز_cleaned' در داده های بارگذاری شده یافت نشد.")
    st.stop()
except IndexError:
     st.sidebar.error(f"خطا: نام روز فیلتر متناظر با '{selected_day_display}' یافت نشد.")
     st.stop()
except Exception as e:
    st.sidebar.error(f"خطا در پردازش روزهای هفته: {e}")
    st.stop()


# --- Filter Data Based on Selected Day ---
# ***** USE cleaned 'selected_day_filter' *****
filtered_farms_df = farm_data_df_raw[farm_data_df_raw['روز_cleaned'] == selected_day_filter].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day_display}' یافت نشد.")
    # Don't stop here, allow user to potentially change the day

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
# Map Persian day names (standardized display names) to Python's weekday() (Monday=0, Sunday=6)
persian_to_weekday = {
    "شنبه": 5,
    "یکشنبه": 6,
    "دوشنبه": 0,
    "سه شنبه": 1, # Standardized display name
    "چهارشنبه": 2,
    "پنج شنبه": 3, # Standardized display name
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
        # Set default dates if calculation fails
        start_date_current_str = (today - datetime.timedelta(days=6)).strftime('%Y-%m-%d')
        end_date_current_str = today.strftime('%Y-%m-%d')
        start_date_previous_str = (today - datetime.timedelta(days=13)).strftime('%Y-%m-%d')
        end_date_previous_str = (today - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
        st.sidebar.warning("از بازه‌های زمانی پیش‌فرض استفاده می‌شود.")

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
    """Masks clouds in a Sentinel-2 SR image using the QA and SCL bands."""
    try:
        qa = image.select('QA60')
        # Bits 10 and 11 are clouds and cirrus, respectively.
        cloudBitMask = 1 << 10
        cirrusBitMask = 1 << 11
        # Both flags should be set to zero, indicating clear conditions.
        mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(
                 qa.bitwiseAnd(cirrusBitMask).eq(0))

        # Use SCL band for more robust cloud masking if available
        if 'SCL' in image.bandNames().getInfo():
            scl = image.select('SCL')
            # Mask Cloud Shadow (3), Cloud Medium Prob (8), Cloud High Prob (9), Cirrus (10)
            # Keep Vegetation (4), Not Vegetated (5), Water (6), Unclassified (7), Snow/Ice (11), Bare Soil (not explicitly listed but keep)
            # Classes to mask out
            mask_classes = [3, 8, 9, 10]
            scl_mask = scl.remap(mask_classes, [0]*len(mask_classes), 1) # Map bad classes to 0, others to 1
            mask = mask.And(scl_mask) # Combine QA mask and SCL mask

        # Scale and offset factors for Sentinel-2 SR bands (B1 to B12)
        opticalBands = image.select('B.*').multiply(0.0001)

        # Return the image with scaled bands and applied mask
        # Update mask ensures only clear pixels according to both methods are kept
        return image.addBands(opticalBands, None, True).updateMask(mask)
    except Exception as e:
        # print(f"Warning: Cloud masking failed for image {image.id().getInfo() if image.id() else 'unknown'}. Returning original. Error: {e}")
        return image # Return original image if masking fails


# --- Index Calculation Functions ---
def add_indices(image):
    """Calculates and adds various indices as bands to an image."""
    try:
        # Ensure required bands exist before calculation
        # Check for the actual bands needed by the formulas used below
        required_bands = ['B2', 'B3', 'B4', 'B8', 'B11'] # Blue, Green, Red, NIR, SWIR1
        img_bands = image.bandNames().getInfo()
        if not all(band in img_bands for band in required_bands):
             # print(f"Warning: Image {image.id().getInfo() if image.id() else 'unknown'} missing required bands ({[b for b in required_bands if b not in img_bands]}). Skipping index calculation.")
             return image # Return original image if bands are missing

        # Calculate indices using expressions for robustness
        # NDVI: (NIR - Red) / (NIR + Red)
        ndvi = image.expression('(NIR - RED) / (NIR + RED)', {
            'NIR': image.select('B8'), 'RED': image.select('B4')
        }).rename('NDVI')

        # EVI: 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1)
        evi = image.expression('2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')
        }).rename('EVI')

        # NDMI (Normalized Difference Moisture Index): (NIR - SWIR1) / (NIR + SWIR1)
        ndmi = image.expression('(NIR - SWIR1) / (NIR + SWIR1)', {
            'NIR': image.select('B8'), 'SWIR1': image.select('B11')
        }).rename('NDMI')

        # MSI (Moisture Stress Index): SWIR1 / NIR
        msi = image.expression('SWIR1 / NIR', {
            'SWIR1': image.select('B11'), 'NIR': image.select('B8')
        }).rename('MSI')

        # LAI (Leaf Area Index) - Simple estimation using NDVI
        lai = ndvi.multiply(3.5).rename('LAI') # Placeholder - Needs calibration

        # CVI (Chlorophyll Vegetation Index) - (NIR / Green) * (Red / Green)
        # Handle potential division by zero if Green band is 0
        cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
            'NIR': image.select('B8'),
            'GREEN': image.select('B3').max(ee.Image(0.0001)), # Avoid division by zero
            'RED': image.select('B4')
        }).rename('CVI')

        return image.addBands([ndvi, evi, ndmi, msi, lai, cvi]) # Add calculated indices

    except Exception as e:
        # print(f"Warning: Index calculation failed for image {image.id().getInfo() if image.id() else 'unknown'}. Error: {e}")
        return image # Return the original image if index calculation fails


# --- Function to get processed image for a date range and geometry ---
# Incorporates the fix for the 'Band pattern ... did not match any bands' error
#@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True) # Consider disabling GEE caching
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given geometry and date range.
    Handles cases where index calculation might fail for some images.
    """
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 80)) # Pre-filter very cloudy scenes
                     .map(maskS2clouds)) # Apply cloud masking

        # Check count *before* index calculation
        initial_count = s2_sr_col.size().getInfo()
        if initial_count == 0:
            return None, f"هیچ تصویر Sentinel-2 مناسبی در بازه {start_date} تا {end_date} یافت نشد (0 تصویر پس از فیلتر اولیه)."

        # Calculate indices for each image in the collection
        indexed_col = s2_sr_col.map(add_indices)

        # ***** CRITICAL FIX: Filter images AFTER mapping add_indices *****
        # Ensure the desired index band actually exists in each image
        filtered_indexed_col = indexed_col.filter(ee.Filter.listContains('system:band_names', index_name))

        # Check if any images remain after filtering for the band
        final_count = filtered_indexed_col.size().getInfo()
        if final_count == 0:
            return None, f"تصویری با باند '{index_name}' معتبر پس از محاسبه یافت نشد (تعداد تصاویر اولیه مناسب: {initial_count}). این ممکن است به دلیل پوشش ابری مداوم یا خطاهای پردازش در add_indices برای تمام تصاویر در این بازه باشد."

        # Select the specific index band *from the filtered collection*
        index_only_col = filtered_indexed_col.select(index_name)

        # Create a median composite image
        median_image = index_only_col.median()

        # Clip to the geometry if it's a polygon
        # No need to clip explicitly for points here, handled by reduceRegion later
        if _geometry.type().getInfo() == 'Polygon':
             median_image = median_image.clip(_geometry)

        # Optional: Check if the final image is completely masked (can be slow)
        # try:
        #     stats = median_image.reduceRegion(reducer=ee.Reducer.count(), geometry=_geometry, scale=30, maxPixels=1e9).getInfo()
        #     if stats is None or stats.get(index_name, 0) == 0:
        #         return None, f"تصویر نهایی مدین برای '{index_name}' در منطقه انتخابی کاملاً ماسک شده است (احتمالا به دلیل ابرها یا نبود داده)."
        # except ee.EEException: # Ignore compute errors on this optional check
        #      pass


        return median_image, None # Return the image and no error message

    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine در get_processed_image: {e}"
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'time limit' in error_details.lower(): error_message += "\n(زمان محاسبه GEE تمام شد)"
                elif 'memory limit' in error_details.lower(): error_message += "\n(حافظه GEE پر شد)"
                elif 'image.select' in error_details.lower() and 'not found' in error_details.lower(): error_message += f"\n(خطای داخلی: باند '{index_name}' یافت نشد)"
                elif 'collection.size' in error_details.lower(): error_message += "\n(خطا در محاسبه تعداد تصاویر)"
                elif 'dictionary.get' in error_details.lower(): error_message += "\n(خطای دیکشنری GEE)"
        except Exception: pass
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE (get_processed_image): {e}\n{traceback.format_exc()}"
        return None, error_message


# --- Function to get time series data for a point ---
#@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True) # Caching issues with GEE
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets a time series of a specified index for a point geometry."""
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 50)) # Stricter cloud filter
                     .map(maskS2clouds)
                     .map(add_indices)
                     .filter(ee.Filter.listContains('system:band_names', index_name))) # Ensure index band exists

        def extract_value(image):
            try:
                value = image.select(index_name).reduceRegion(
                    reducer=ee.Reducer.firstNonNull(), # Get first valid pixel at point
                    geometry=_point_geom,
                    scale=10 # 10m scale for S2
                ).get(index_name)
                # Check if value is null using EE server-side functions
                is_null = ee.Algorithms.IsEqual(value, None)
                # Return feature with value and date, set 'hasValue' property
                return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value}) \
                        .set('hasValue', is_null.Not())
            except Exception as reduce_err:
                 # print(f"Warning: reduceRegion failed for image {image.id().getInfo() if image.id() else 'unknown'} in time series. Error: {reduce_err}")
                 return ee.Feature(None, {'hasValue': False}) # Indicate failure

        # Map extraction and filter out features where value extraction failed or was null
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.eq('hasValue', True))

        # Limit the number of features before getInfo() if necessary
        # ts_features = ts_features.limit(300, 'system:time_start', False)

        # Convert the FeatureCollection to a list of dictionaries
        try:
            ts_info = ts_features.getInfo()['features']
        except ee.EEException as e:
             if 'collection query aborted' in str(e).lower() or 'too large' in str(e).lower():
                  return pd.DataFrame(columns=['date', index_name]), f"خطای GEE: مجموعه داده سری زمانی بیش از حد بزرگ است. بازه زمانی را کوتاه‌تر کنید یا فیلترها را دقیق‌تر کنید."
             else:
                  return pd.DataFrame(columns=['date', index_name]), f"خطای GEE getInfo: {e}"


        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای سری زمانی {index_name} یافت نشد (پس از فیلتر)."

        # Convert to Pandas DataFrame carefully
        ts_data = []
        for f in ts_info:
            props = f.get('properties', {})
            date_val = props.get('date')
            index_val = props.get(index_name)
            if date_val is not None and index_val is not None: # Ensure both exist
                 ts_data.append({'date': date_val, index_name: index_val})

        if not ts_data:
             return pd.DataFrame(columns=['date', index_name]), f"داده معتبری برای سری زمانی {index_name} یافت نشد (پس از فیلتر نهایی)."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df[index_name] = pd.to_numeric(ts_df[index_name], errors='coerce')
        ts_df = ts_df.dropna(subset=[index_name]) # Drop rows where conversion failed
        ts_df = ts_df.sort_values('date').set_index('date')

        # Remove potential duplicates just in case
        ts_df = ts_df[~ts_df.index.duplicated(keep='first')]

        return ts_df, None # Return DataFrame and no error
    except ee.EEException as e:
        error_message = f"خطای GEE در دریافت سری زمانی: {e}"
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"
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
        min_lon, min_lat = filtered_farms_df['longitude'].min(), filtered_farms_df['latitude'].min()
        max_lon, max_lat = filtered_farms_df['longitude'].max(), filtered_farms_df['latitude'].max()
        # Add a small buffer if min/max are the same (single point farm)
        if abs(min_lon - max_lon) < 1e-6 and abs(min_lat - max_lat) < 1e-6:
            buffer = 0.005 # Slightly larger buffer for visibility
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
        lat = selected_farm_details['latitude']
        lon = selected_farm_details['longitude']
        if pd.isna(lat) or pd.isna(lon):
            st.error(f"مختصات نامعتبر برای مزرعه {selected_farm_name}.")
            map_needs_update = False
        else:
            selected_farm_geom = ee.Geometry.Point([lon, lat])
            st.subheader(f"📍 جزئیات مزرعه: {selected_farm_name} (روز: {selected_day_display})")
            # Display farm details - use .get() for robustness
            details_cols = st.columns(3)
            with details_cols[0]:
                st.metric("گروه", f"{selected_farm_details.get('گروه', 'N/A')}")
                st.metric("مساحت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A")
            with details_cols[1]:
                st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
                st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
            with details_cols[2]:
                st.metric("کانال", f"{selected_farm_details.get('کانال', 'N/A')}")
                st.metric("اداره", f"{selected_farm_details.get('اداره', 'N/A')}")
                st.metric("مختصات (Lat, Lon)", f"{lat:.5f}, {lon:.5f}")
    except IndexError:
        st.error(f"اطلاعات مزرعه '{selected_farm_name}' یافت نشد.")
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
        'NDVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']},
        'LAI': {'min': 0, 'max': 7, 'palette': ['#f7fcf5', '#e5f5e0', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#006d2c', '#00441b']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b']},
        'CVI': {'min': 0, 'max': 25, 'palette': ['#ffffcc', '#c7e9b4', '#7fcdbb', '#41b6c4', '#1d91c0', '#225ea8', '#0c2c84']},
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
    m.add_basemap("HYBRID")

    # Get the processed image for the current week
    if selected_farm_geom:
        with st.spinner(f"در حال پردازش تصویر {selected_index} برای نقشه..."):
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
            )

        if error_msg_current:
            st.warning(f"خطا در پردازش تصویر برای دوره جاری: {error_msg_current}")

        if gee_image_current:
            # Add the GEE layer to the map
            try:
                current_vis = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})
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
                if selected_index in ['NDVI', 'EVI']: legend_dict = {"بالا (سالم)": palette[-1], "متوسط": palette[len(palette)//2], "پایین (ضعیف)": palette[0]}
                elif selected_index == 'NDMI': legend_dict = {"مرطوب": palette[-1], "متوسط": palette[len(palette)//2], "خشک": palette[0]}
                elif selected_index == 'MSI': legend_dict = {"تنش کم (مرطوب)": palette[0], "متوسط": palette[len(palette)//2], "تنش بالا (خشک)": palette[-1]}
                elif selected_index == 'LAI': legend_dict = {"LAI بالا": palette[-1], "LAI متوسط": palette[len(palette)//2], "LAI پایین": palette[0]}
                elif selected_index == 'CVI': legend_dict = {"کلروفیل بالا": palette[-1], "کلروفیل متوسط": palette[len(palette)//2], "کلروفیل پایین": palette[0]}
                else: # Default legend
                    steps = len(palette); legend_dict = {}
                    if steps > 1: legend_dict[f"بالا ({max_val:.2f})"] = palette[-1]; legend_dict[f"متوسط ({min_val + (max_val - min_val)/2:.2f})"] = palette[len(palette)//2]; legend_dict[f"پایین ({min_val:.2f})"] = palette[0]
                    elif steps == 1: legend_dict[f"{min_val:.2f} - {max_val:.2f}"] = palette[0]

                # Add legend using the corrected 'title' keyword
                m.add_legend(title=legend_title_text, legend_dict=legend_dict, position='bottomright')

            except ee.EEException as map_err:
                st.error(f"خطا در افزودن لایه GEE به نقشه: {map_err}")
            except Exception as map_err:
                st.error(f"خطا در ایجاد لجند نقشه: {map_err}")
                st.error(traceback.format_exc())
        # else: # Handled by error_msg_current check above

            # Add markers regardless of GEE layer success (if data exists)
            try:
                if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
                     # Add markers for all filtered farms
                     for idx, farm in filtered_farms_df.iterrows():
                         lat_f, lon_f = farm['latitude'], farm['longitude']
                         if pd.notna(lat_f) and pd.notna(lon_f):
                             # Create richer popups using HTML
                             popup_html = f"""
                                 <b>مزرعه:</b> {farm.get('مزرعه', 'N/A')}<br>
                                 <b>روز:</b> {farm.get('روز_display', 'N/A')}<br>
                                 <b>گروه:</b> {farm.get('گروه', 'N/A')}<br>
                                 <b>کانال:</b> {farm.get('کانال', 'N/A')}<br>
                                 <b>اداره:</b> {farm.get('اداره', 'N/A')}
                             """
                             iframe = folium.IFrame(popup_html, width=200, height=100)
                             popup = folium.Popup(iframe, max_width=200)

                             folium.Marker(
                                 location=[lat_f, lon_f],
                                 popup=popup,
                                 tooltip=farm.get('مزرعه', 'N/A'),
                                 icon=folium.Icon(color='blue', icon='info-sign')
                             ).add_to(m)
                     if selected_farm_geom: m.center_object(selected_farm_geom, zoom=initial_zoom)
                elif selected_farm_details is not None and selected_farm_geom:
                     # Add marker for the single selected farm
                     popup_html = f"""
                         <b>مزرعه:</b> {selected_farm_name}<br>
                         <b>روز:</b> {selected_farm_details.get('روز_display', 'N/A')}<br>
                         <b>کانال:</b> {selected_farm_details.get('کانال', 'N/A')}<br>
                         <b>اداره:</b> {selected_farm_details.get('اداره', 'N/A')}<br>
                         <b>{selected_index}:</b> {'مقدار در حال محاسبه...' if gee_image_current else 'خطا در دریافت تصویر'}
                     """
                     iframe = folium.IFrame(popup_html, width=200, height=100)
                     popup = folium.Popup(iframe, max_width=200)
                     folium.Marker(
                         location=[lat, lon],
                         popup=popup,
                         tooltip=selected_farm_name,
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=15)
            except Exception as marker_err:
                 st.error(f"خطا در افزودن نشانگرها به نقشه: {marker_err}")

            m.add_layer_control() # Add layer control

    # Display the map in Streamlit
    st_folium(m, width=None, height=500, use_container_width=True, returned_objects=[])
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
        is_point = False
        if selected_farm_geom:
            try: is_point = selected_farm_geom.type().getInfo() == 'Point'
            except Exception as geom_err: st.warning(f"خطا در بررسی نوع هندسه مزرعه: {geom_err}")

        if is_point:
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d') # 1 year

            with st.spinner(f"در حال دریافت داده‌های سری زمانی {selected_index} برای {selected_farm_name}..."):
                ts_df, ts_error = get_index_time_series(
                    selected_farm_geom, selected_index,
                    start_date=timeseries_start_date, end_date=timeseries_end_date
                )

            if ts_error: st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                try:
                    fig = px.line(ts_df, y=selected_index, markers=True,
                                  title=f"روند تغییرات {selected_index} برای مزرعه {selected_farm_name}",
                                  labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                    fig.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}", title_x=0.5, title_font_family="Vazirmatn", font_family="Vazirmatn")
                    fig.update_traces(line_color='#17a2b8', marker=dict(color='#17a2b8', size=5))
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در یک سال گذشته (نقاط نشان‌دهنده تصاویر ماهواره‌ای بدون ابر هستند).")
                except Exception as chart_err:
                    st.error(f"خطا در رسم نمودار پلاتلی: {chart_err}")
                    try: st.line_chart(ts_df[selected_index]) # Fallback
                    except Exception as basic_chart_err: st.error(f"خطا در رسم نمودار پایه: {basic_chart_err}")
            else: st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده (یک سال اخیر) یافت نشد.")
        else: st.warning("نمودار سری زمانی فقط برای مزارع منفرد (با مختصات نقطه‌ای) قابل نمایش است.")


# --- Ranking Table ---
if map_needs_update and not filtered_farms_df.empty: # Only show table if map was attempted and data exists for the day
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day_display})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist="disk")
    def calculate_weekly_indices(_farms_df_subset_records, index_name, start_curr, end_curr, start_prev, end_prev, _cache_key_day_index):
        """Calculates the average index value for the current and previous week for a list of farms."""
        results = []
        errors = []
        total_farms = len(_farms_df_subset_records)

        for i, farm_info in enumerate(_farms_df_subset_records):
            farm_name = farm_info.get('مزرعه', 'نامشخص')
            lat = farm_info.get('latitude')
            lon = farm_info.get('longitude')

            if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
                errors.append(f"{farm_name}: مختصات نامعتبر.")
                current_val, err_curr, previous_val, err_prev = None, "مختصات نامعتبر", None, "مختصات نامعتبر"
            else:
                 point_geom = ee.Geometry.Point([lon, lat])
                 # --- Inner function to get mean value (cannot be cached directly with GEE) ---
                 def get_mean_value(start, end):
                    try:
                        image, error_img = get_processed_image(point_geom, start, end, index_name)
                        if image:
                            mean_dict = image.reduceRegion(
                                reducer=ee.Reducer.mean(), geometry=point_geom, scale=10, maxPixels=1e9
                            ).getInfo()
                            value = mean_dict.get(index_name) if mean_dict else None
                            # Handle potential null values explicitly AFTER getInfo()
                            if value is None:
                                 # Check if the image itself had an error message
                                 if error_img: return None, f"تصویر نامعتبر ({error_img})"
                                 # Otherwise, likely masked area
                                 else: return None, "ناحیه ماسک شده یا بدون داده"
                            return value, None # Success
                        else:
                            return None, error_img if error_img else "تصویری یافت نشد"
                    except ee.EEException as e_reduce:
                        err_detail = str(e_reduce).lower()
                        reason = f"خطای GEE Reduce ({e_reduce})"
                        if 'memory' in err_detail: reason = "خطای حافظه GEE"
                        elif 'time limit' in err_detail: reason = "پایان زمان GEE"
                        elif 'null' in err_detail: reason = "خطای داده Null در GEE"
                        return None, reason
                    except Exception as e_other:
                        return None, f"خطای محاسبه مقدار: {e_other}"
                 # --- End Inner function ---

                 # Calculate for current week
                 current_val, err_curr = get_mean_value(start_curr, end_curr)
                 if err_curr: errors.append(f"{farm_name} (جاری): {err_curr}")

                 # Calculate for previous week
                 previous_val, err_prev = get_mean_value(start_prev, end_prev)
                 if err_prev: errors.append(f"{farm_name} (قبل): {err_prev}")

            # Calculate change only if both values are valid numbers
            change = None
            if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                 change = current_val - previous_val

            results.append({
                'مزرعه': farm_name,
                'کانال': farm_info.get('کانال', 'N/A'),
                'اداره': farm_info.get('اداره', 'N/A'),
                f'{index_name} (هفته جاری)': current_val,
                f'{index_name} (هفته قبل)': previous_val,
                'تغییر': change,
                'خطای جاری': err_curr, # Store errors per row
                'خطای قبلی': err_prev
            })

        return pd.DataFrame(results), errors # Return aggregated errors as well

    # Prepare subset of data for caching (list of dicts)
    cols_needed = ['مزرعه', 'latitude', 'longitude', 'کانال', 'اداره']
    cols_available = [col for col in cols_needed if col in filtered_farms_df.columns]
    farms_subset_records = filtered_farms_df[cols_available].to_dict('records')

    # Create a cache key combining day and index
    cache_key = f"{selected_day_display}_{selected_index}"

    # Calculate and display the ranking table
    ranking_progress = st.progress(0)
    status_text = st.text(f"در حال محاسبه شاخص {selected_index} برای {len(farms_subset_records)} مزرعه...")
    ranking_df = pd.DataFrame()
    calculation_errors = []
    try:
        # Pass the cache key to the function
        ranking_df, calculation_errors = calculate_weekly_indices(
            farms_subset_records, selected_index,
            start_date_current_str, end_date_current_str,
            start_date_previous_str, end_date_previous_str,
            cache_key # Use combined key
        )
        ranking_progress.progress(1.0)
        status_text.text(f"محاسبه شاخص {selected_index} برای {len(ranking_df)} مزرعه کامل شد.")
        # Consider removing progress bar after success: ranking_progress.empty()
    except Exception as calc_err:
        ranking_progress.empty()
        status_text.text(f"خطا در محاسبه رتبه‌بندی.")
        st.error(f"خطای کلی در محاسبه رتبه‌بندی: {calc_err}")
        st.error(traceback.format_exc())
        calculation_errors.append(f"خطای کلی: {calc_err}")


    # Display any errors that occurred during calculation
    # Filter errors related to invalid coords as they are handled in the table
    filtered_errors = [e for e in calculation_errors if "مختصات نامعتبر" not in e]
    if filtered_errors:
        st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها رخ داد:")
        error_expander = st.expander("مشاهده جزئیات خطاها", expanded=False)
        with error_expander:
            unique_errors = sorted(list(set(filtered_errors)))
            for error in unique_errors[:20]: st.caption(f"- {error}")
            if len(unique_errors) > 20: st.caption(f"... و {len(unique_errors) - 20} خطای منحصربفرد دیگر.")
        if len(calculation_errors) > 5: st.warning(f"(تعداد کل رخدادهای خطا: {len(calculation_errors)})")


    if not ranking_df.empty:
        # --- Process Ranking Data ---
        # Define columns for index values and change
        current_col = f'{selected_index} (هفته جاری)'
        prev_col = f'{selected_index} (هفته قبل)'
        change_col = 'تغییر'

        # Convert to numeric, coercing errors. Invalid values become NaN.
        ranking_df[current_col] = pd.to_numeric(ranking_df[current_col], errors='coerce')
        ranking_df[prev_col] = pd.to_numeric(ranking_df[prev_col], errors='coerce')
        # Recalculate change based on numeric columns, respecting NaN
        ranking_df[change_col] = ranking_df[current_col] - ranking_df[prev_col]


        # Sort by the current week's index value
        ascending_sort = selected_index in ['MSI']
        ranking_df_sorted = ranking_df.sort_values(
            by=current_col, ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)

        # Add rank number
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # --- Determine Status ---
        def determine_status(row, index_name):
            change_val = row[change_col]
            current_val = row[current_col]
            prev_val = row[prev_col]
            err_curr = row['خطای جاری']
            err_prev = row['خطای قبلی']

            if pd.isna(current_val) and pd.isna(prev_val):
                status = "بدون داده معتبر"
                if err_curr or err_prev: status += " (خطا)"
                return status
            elif pd.isna(prev_val) and not pd.isna(current_val):
                 return "داده جدید" # Data only for current week
            elif pd.isna(current_val) and not pd.isna(prev_val):
                 return "داده قبلی ناموجود" # Data only for prev week (shouldn't happen with sorting?)
            elif pd.isna(change_val): # Both values exist but change is NaN (shouldn't happen after recalc)
                 return "خطا در مقایسه"

            # Define thresholds
            threshold = 0.05; # Default
            if index_name == 'MSI': threshold = 0.1
            elif index_name == 'LAI': threshold = 0.2
            elif index_name == 'CVI': threshold = 1.0

            # Status logic
            if index_name in ['NDVI', 'EVI', 'LAI', 'CVI']: # Higher is better
                if change_val > threshold: return "رشد مثبت"
                elif change_val < -threshold: return "تنش/کاهش"
                else: return "ثابت"
            elif index_name in ['NDMI']: # Higher is wetter
                if change_val > threshold: return "بهبود رطوبت"
                elif change_val < -threshold: return "کاهش رطوبت"
                else: return "ثابت"
            elif index_name in ['MSI']: # Lower is wetter/less stress
                if change_val < -threshold: return "بهبود تنش"
                elif change_val > threshold: return "افزایش تنش"
                else: return "ثابت"
            else: # Default
                if change_val > threshold: return "افزایش"
                elif change_val < -threshold: return "کاهش"
                else: return "ثابت"

        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)

        # Format numbers for display *after* calculations
        display_df = ranking_df_sorted.copy()
        format_cols = [current_col, prev_col, change_col]
        for col in format_cols:
             display_df[col] = display_df[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

        # Define columns to display
        display_cols_order = ['مزرعه', 'کانال', 'اداره', current_col, prev_col, change_col, 'وضعیت']
        final_display_cols = ['رتبه'] + [col for col in display_cols_order if col in display_df.columns]

        # Display the table using st.dataframe
        st.dataframe(display_df[final_display_cols], use_container_width=True)

        # --- Status Summary ---
        st.subheader("📊 خلاصه وضعیت تغییرات هفتگی")
        if 'وضعیت' in ranking_df_sorted.columns:
            status_counts = ranking_df_sorted['وضعیت'].value_counts()
            status_map = { # Simplified mapping
                "رشد مثبت": ("🟢", "مثبت"), "بهبود رطوبت": ("🟢", "مثبت"), "بهبود تنش": ("🟢", "مثبت"), "افزایش": ("🟢", "مثبت"),
                "ثابت": ("⚪", "خنثی"),
                "تنش/کاهش": ("🔴", "منفی"), "کاهش رطوبت": ("🔴", "منفی"), "افزایش تنش": ("🔴", "منفی"), "کاهش": ("🔴", "منفی"),
                "داده جدید": ("🆕", "نامشخص"), "داده قبلی ناموجود": ("❓", "نامشخص"),
                "بدون داده معتبر": ("⚫", "نامشخص"), "خطا در مقایسه": ("⚠️", "نامشخص"),
                "بدون داده معتبر (خطا)": ("⚠️", "نامشخص"), # Combine error states
            }
            summary_counts = {"مثبت": 0, "منفی": 0, "خنثی": 0, "نامشخص": 0}
            for status, count in status_counts.items():
                icon, type = status_map.get(status, ("❓", "نامشخص"))
                summary_counts[type] += count

            # Display summary
            num_cols_to_show = len([c for c in summary_counts.values() if c > 0])
            if num_cols_to_show > 0:
                summary_cols = st.columns(num_cols_to_show)
                col_idx = 0
                if summary_counts["مثبت"] > 0:
                    with summary_cols[col_idx]: st.metric("🟢 بهبود یافته", summary_counts["مثبت"])
                    col_idx += 1
                if summary_counts["خنثی"] > 0:
                     with summary_cols[col_idx]: st.metric("⚪ ثابت", summary_counts["خنثی"])
                     col_idx += 1
                if summary_counts["منفی"] > 0:
                    with summary_cols[col_idx]: st.metric("🔴 بدتر شده", summary_counts["منفی"])
                    col_idx += 1
                if summary_counts["نامشخص"] > 0:
                     with summary_cols[col_idx]: st.metric("⚫/🆕/⚠️ نامشخص/جدید/خطا", summary_counts["نامشخص"])
                     col_idx += 1
            else: st.info("خلاصه‌ای برای نمایش وجود ندارد.")

            # Explanation expander
            with st.expander("راهنمای وضعیت‌ها", expanded=False):
                st.markdown("""
                *   **🟢 بهبود یافته**: وضعیت شاخص نسبت به هفته قبل بهتر شده است.
                *   **⚪ ثابت**: تغییر قابل توجهی نسبت به هفته قبل وجود ندارد.
                *   **🔴 بدتر شده**: وضعیت شاخص نسبت به هفته قبل نامطلوب‌تر شده است.
                *   **⚫/🆕/⚠️ نامشخص/جدید/خطا**: شامل مزارع بدون داده معتبر، مزارعی که فقط داده هفته جاری را دارند (جدید)، یا مواردی که در محاسبه یا مقایسه خطا رخ داده است.
                """)

            # --- Download Button ---
            try:
                # Use the dataframe with formatted numbers but keep original numeric for potential analysis if needed
                # Here we use the display_df for user download
                download_df_display = display_df[final_display_cols].reset_index(drop=True) # Use display version
                csv_data = download_df_display.to_csv(index=False, encoding='utf-8-sig')
                st.download_button(
                    label="📥 دانلود جدول رتبه‌بندی (CSV)",
                    data=csv_data,
                    file_name=f'ranking_{selected_index}_{selected_day_display.replace(" ", "_")}_{end_date_current_str}.csv',
                    mime='text/csv',
                )
            except Exception as e: st.error(f"خطا در ایجاد فایل دانلود: {e}")
        else: st.info("ستون 'وضعیت' برای نمایش خلاصه در دسترس نیست.")

    elif not calculation_errors: # If DF is empty but no errors reported
        st.info(f"محاسبات انجام شد، اما نتیجه‌ای برای جدول رتبه‌بندی {selected_index} در این بازه زمانی یافت نشد.")


st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط [گروه مطالعات کاربردی]") # Updated credit
st.sidebar.markdown("با استفاده از Streamlit, Google Earth Engine, و geemap.")
st.sidebar.markdown(f"آخرین بروزرسانی داده‌ها: {today.strftime('%Y-%m-%d')}")
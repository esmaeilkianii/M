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
# from io import BytesIO # Not strictly needed for this version
# import requests # Needed for getThumbUrl download (Not used currently)
import traceback  # Add missing traceback import
from streamlit_folium import st_folium  # Add missing st_folium import
# import base64 # Not strictly needed for this version
import google.generativeai as genai # Gemini API

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Modern CSS with dark mode and color palette
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        html, body, .main, .stApp {
            font-family: 'Vazirmatn', sans-serif !important;
            background: linear-gradient(135deg, #e0f7fa 0%, #f8fafc 100%);
        }
        /* Modern card style */
        .modern-card {
            background: linear-gradient(135deg, #43cea2 0%, #185a9d 100%);
            color: white;
            border-radius: 18px;
            padding: 24px 18px;
            margin: 10px 0;
            box-shadow: 0 4px 16px rgba(30,60,114,0.08);
            text-align: center;
            transition: transform 0.2s;
        }
        .modern-card:hover {
            transform: translateY(-4px) scale(1.02);
        }
        /* Sidebar logo */
        .sidebar-logo {
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 1.5rem;
        }
        .sidebar-logo img {
            width: 90px;
            height: 90px;
            border-radius: 18px;
            box-shadow: 0 2px 8px rgba(30,60,114,0.12);
        }
        /* Main header logo */
        .main-logo {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            margin-left: 12px;
            vertical-align: middle;
        }
        /* Status Badges */
        .status-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.9em;
            white-space: nowrap;
        }
        .status-positive {
            background-color: #d4edda; /* Light Green */
            color: #155724; /* Dark Green */
            border: 1px solid #c3e6cb;
        }
        .status-negative {
            background-color: #f8d7da; /* Light Red */
            color: #721c24; /* Dark Red */
            border: 1px solid #f5c6cb;
        }
        .status-neutral {
            background-color: #fff3cd; /* Light Yellow */
            color: #856404; /* Dark Yellow */
            border: 1px solid #ffeeba;
        }
        .status-nodata {
            background-color: #e2e3e5; /* Light Gray */
            color: #383d41; /* Dark Gray */
            border: 1px solid #d6d8db;
        }
        .status-unknown {
            background-color: #f0f0f0; /* Lighter Gray */
            color: #555;
            border: 1px solid #e0e0e0;
        }

        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
            html, body, .main, .stApp {
                background: linear-gradient(135deg, #232526 0%, #414345 100%);
                color: #f8fafc;
            }
           .status-positive { background-color: #2a4d32; color: #c3e6cb; border-color: #446d50;}
           .status-negative { background-color: #582128; color: #f5c6cb; border-color: #8b3f46;}
           .status-neutral { background-color: #664d03; color: #ffeeba; border-color: #997404;}
           .status-nodata { background-color: #383d41; color: #d6d8db; border-color: #5a6268;}
           .status-unknown { background-color: #444; color: #ccc; border-color: #555;}
        }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar Logo ---
# Assuming the logo path is relative to the app's root directory in deployment
logo_path = 'logo (1).png'
if os.path.exists(logo_path):
    st.sidebar.markdown(
        f"""
        <div class='sidebar-logo'>
            <img src='{logo_path}' alt='لوگو سامانه' />
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.sidebar.warning("لوگو یافت نشد.")


# --- Main Header with Logo ---
if os.path.exists(logo_path):
    st.markdown(
        f"""
        <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 0.5rem;'>
            <img src='{logo_path}' class='main-logo' alt='لوگو' />
            <h1 style='font-family: Vazirmatn, sans-serif; color: #185a9d; margin: 0;'>سامانه پایش هوشمند نیشکر</h1>
        </div>
        <h4 style='color: #43cea2; margin-top: 0;'>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
        """,
        unsafe_allow_html=True
    )
else:
     st.markdown(
        """
        <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 0.5rem;'>
             <span style='font-size: 32px;'>🌾</span>
             <h1 style='font-family: Vazirmatn, sans-serif; color: #185a9d; margin: 0;'>سامانه پایش هوشمند نیشکر</h1>
        </div>
        <h4 style='color: #43cea2; margin-top: 0;'>مطالعات کاربردی شرکت کشت و صنعت دهخدا</h4>
        """,
        unsafe_allow_html=True
    )


# --- Configuration ---
APP_TITLE = "سامانه پایش هوشمند نیشکر"
APP_SUBTITLE = "مطالعات کاربردی شرکت کشت و صنعت دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
CSV_FILE_PATH = 'برنامه_ریزی_با_مختصات (1).csv' # Not used directly anymore? Check dependencies
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


# --- Load Farm Data from GeoJSON ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data_from_geojson(geojson_path='farm_geodata_fixed.geojson'):
    """Loads farm data from the specified GeoJSON file."""
    try:
        with open(geojson_path, 'r', encoding='utf-8') as f:
            gj = json.load(f)
        features = gj['features']
        # Extract properties and geometry
        records = []
        for feat in features:
            props = feat['properties']
            geom = feat['geometry']
            # For polygons, you may want centroid or all coordinates
            if geom and geom['type'] == 'Polygon' and geom['coordinates']:
                coords = geom['coordinates'][0]  # Outer ring
                # Calculate centroid for display/analysis
                lons = [pt[0] for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 1]
                lats = [pt[1] for pt in coords if isinstance(pt, (list, tuple)) and len(pt) >= 2]
                if lons and lats:
                    centroid_lon = sum(lons) / len(lons)
                    centroid_lat = sum(lats) / len(lats)
                else:
                    centroid_lon, centroid_lat = None, None
            elif geom and geom['type'] == 'Point' and geom['coordinates']:
                 centroid_lon, centroid_lat = geom['coordinates'] # Use point coords directly
            else: # Handle other types or missing geometry
                centroid_lon, centroid_lat = None, None

            record = {
                **props,
                'geometry_type': geom['type'] if geom else None,
                'coordinates': geom['coordinates'] if geom else None,
                'centroid_lon': centroid_lon,
                'centroid_lat': centroid_lat
            }
            records.append(record)
        df = pd.DataFrame(records)
        # Basic validation
        required_cols = ['مزرعه', 'centroid_lon', 'centroid_lat', 'روز', 'گروه']
        if not all(col in df.columns for col in required_cols):
            missing = [col for col in required_cols if col not in df.columns]
            st.error(f"❌ فایل GeoJSON باید شامل ستون‌های ضروری باشد. ستون‌های یافت‌نشده: {', '.join(missing)}")
            st.stop()

        # Drop rows where essential coordinates or day are missing
        initial_count = len(df)
        df = df.dropna(subset=['centroid_lon', 'centroid_lat', 'روز'])
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            st.warning(f"⚠️ {dropped_count} رکورد به دلیل مقادیر نامعتبر یا خالی در مختصات یا روز حذف شدند.")
        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات یا روز).")
            st.stop()
        df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        df['گروه'] = df['گروه'].astype(str).str.strip()
        # Convert area if it exists
        if 'مساحت' in df.columns:
            df['مساحت'] = pd.to_numeric(df['مساحت'], errors='coerce')

        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت از GeoJSON بارگذاری شد.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{geojson_path}' یافت نشد. لطفاً فایل GeoJSON داده‌های مزارع را در مسیر صحیح قرار دهید.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"❌ خطا در خواندن فایل GeoJSON (احتمالاً فرمت نامعتبر): {e}")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل GeoJSON: {e}")
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

        # Find the headers and split points - Robust approach looking for keywords
        header1_indices = [i for i, line in enumerate(lines) if 'اداره' in line and 'سن' in line and ('مساحت' in line or 'area' in line.lower() or line.strip().startswith('اداره,سن,'))] # More flexible header finding
        header2_indices = [i for i, line in enumerate(lines) if ('تولید' in line or 'production' in line.lower()) and 'سن' in line and line.strip().startswith('تولید,سن,')] # More specific for production

        if not header1_indices:
             st.error(f"❌ ساختار فایل '{csv_path}' قابل شناسایی نیست. هدر بخش 'مساحت' یافت نشد.")
             st.stop()

        header1_idx = header1_indices[0]

        # Try to find the second header *after* the first one
        header2_idx = None
        potential_header2 = [i for i, line in enumerate(lines) if ('تولید' in line or 'production' in line.lower()) and 'سن' in line and i > header1_idx]
        if potential_header2:
             header2_idx = potential_header2[0]

        section1_start = header1_idx + 1
        section2_start = header2_idx + 1 if header2_idx else None
        section1_end_guess = (header2_idx -1) if header2_idx else len(lines) # Read until next header or end

        # Find likely end of first section (e.g., line starting with 'Total' or 'Grand Total' before next header)
        for i in range(section1_start, section1_end_guess):
            if lines[i].strip().lower().startswith('total') or lines[i].strip().lower().startswith('grand total'):
                section1_end_guess = i
                break


        # Read the first section (Area)
        df_area = pd.read_csv(csv_path, skiprows=header1_idx, nrows=(section1_end_guess - header1_idx), encoding='utf-8')
        # The actual 'اداره' column might be the first unnamed one or named 'اداره'
        if df_area.columns[0].strip().lower() in ['اداره','area']:
            df_area.rename(columns={df_area.columns[0]: 'اداره'}, inplace=True)
        elif 'اداره' not in df_area.columns and 'Unnamed: 0' in df_area.columns:
             df_area.rename(columns={'Unnamed: 0': 'اداره'}, inplace=True)


        # Read the second section (Production) if found
        df_prod = None
        if section2_start:
            end_row_prod = None
            for i in range(section2_start, len(lines)):
                if lines[i].strip().lower().startswith("grand total"):
                    end_row_prod = i
                    break
            nrows_prod = (end_row_prod - section2_start) if end_row_prod else None # Read up to Grand Total

            df_prod = pd.read_csv(csv_path, skiprows=header2_idx, nrows=nrows_prod, encoding='utf-8') # Read including header
            # Rename production section's first column
            if df_prod.columns[0].strip().lower() in ['تولید','production']:
                 df_prod.rename(columns={df_prod.columns[0]: 'اداره'}, inplace=True)
            elif 'اداره' not in df_prod.columns and 'Unnamed: 0' in df_prod.columns:
                 df_prod.rename(columns={'Unnamed: 0': 'اداره'}, inplace=True)


        # --- Preprocessing Function ---
        def preprocess_df(df, section_name):
            if df is None:
                return None
            # Ensure 'اداره' is the first column if it got misplaced
            if 'اداره' not in df.columns and len(df.columns) > 0 and 'Unnamed: 0' in df.columns:
                 df.rename(columns={'Unnamed: 0': 'اداره'}, inplace=True)
            elif 'اداره' not in df.columns and len(df.columns) > 0 : # If first col is something else, assume it's اداره
                 df.rename(columns={df.columns[0]: 'اداره'}, inplace=True)

            # Check for required columns
            if not all(col in df.columns for col in ['اداره', 'سن']):
                 st.warning(f"⚠️ ستون های ضروری 'اداره' یا 'سن' در بخش '{section_name}' یافت نشد. ستون‌های موجود: {list(df.columns)}")
                 return None

            # Forward fill 'اداره' if it has NaNs (common in pivoted tables)
            if df['اداره'].isnull().any():
                df['اداره'] = df['اداره'].ffill()

            # Filter out 'total' and 'Grand Total' rows in 'سن' and 'اداره'
            df = df[~df['سن'].astype(str).str.contains('total', case=False, na=False)]
            df = df[~df['اداره'].astype(str).str.contains('total|دهخدا', case=False, na=False)] # Filter Grand Total/summary rows in اداره

            # Remove rows where 'اداره' is NaN after ffill (usually header artifacts)
            df = df.dropna(subset=['اداره'])

            # Convert 'اداره' to integer where possible, handling potential non-numeric entries
            df['اداره'] = pd.to_numeric(df['اداره'], errors='coerce')
            df = df.dropna(subset=['اداره']) # Drop if conversion failed
            df['اداره'] = df['اداره'].astype(int)

            # Convert numeric columns, coerce errors to NaN
            value_cols = [col for col in df.columns if col not in ['اداره', 'سن', 'درصد', 'Grand Total']]
            for col in value_cols:
                # Attempt to clean strings (remove commas) before converting
                if df[col].dtype == 'object':
                    df[col] = df[col].astype(str).str.replace(',', '', regex=False)
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Drop Grand Total and درصد columns if they exist
            df = df.drop(columns=['Grand Total', 'درصد'], errors='ignore')

            # Remove rows where 'سن' is NaN
            df = df.dropna(subset=['سن'])

            # Set multi-index for easier access
            try:
                df = df.set_index(['اداره', 'سن'])
            except KeyError:
                 st.warning(f"⚠️ امکان تنظیم ایندکس چندگانه در بخش '{section_name}' وجود ندارد (ستون‌های اداره یا سن وجود ندارند یا خالی هستند).")
                 return None # Cannot proceed without index

            # Drop columns that are all NaN (often artifacts of parsing)
            df = df.dropna(axis=1, how='all')

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

# --- HTML Helper Functions ---

# --- Modern Progress Bar (HTML) --- Moved Definition Higher ---
def modern_progress_bar(progress: float) -> str:
    """
    Returns a modern styled HTML progress bar for Streamlit.
    :param progress: float between 0 and 1
    :return: HTML string
    """
    percent = int(progress * 100)
    # Dynamic color based on progress completion
    bar_color = '#185a9d' if percent >= 99 else '#43cea2' # Dark blue when near/at 100%
    bg_color = '#e0f7fa' # Light background

    # Unique ID for progress bar elements to avoid style conflicts if multiple exist
    import uuid
    bar_id = f"progress-bar-{uuid.uuid4()}"

    # Improved styling for better visibility and centering
    return f'''
    <div id="{bar_id}" style="position: relative; width: 100%; background: {bg_color}; border-radius: 12px; height: 22px; margin: 8px 0; box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);">
      <div style="width: {percent}%; background: linear-gradient(90deg, {bar_color} 0%, #185a9d 100%); height: 100%; border-radius: 12px; transition: width 0.4s ease-in-out;"></div>
      <span style="position: absolute; width: 100%; top: 0; left: 0; text-align: center; color: #000; font-weight: bold; line-height: 22px; font-size: 0.85em;">{percent}%</span>
    </div>
    '''


# --- Modern Metric Card (HTML) --- Added Definition ---
def modern_metric_card(label, value, icon="fa-info-circle", color="#43cea2"):
    """Generates HTML for a modern metric card."""
    return f"""
    <div class="modern-card" style="background: linear-gradient(135deg, {color} 0%, #185a9d 100%);">
        <i class="fas {icon}" style="font-size: 1.8em; margin-bottom: 10px;"></i>
        <h5 style="color: white; margin-bottom: 5px;">{label}</h5>
        <h3 style="color: white; margin: 0;">{value}</h3>
    </div>
    """

# --- Status Badge (HTML) --- Added Definition ---
def status_badge(status_text):
    """Generates an HTML badge based on status text."""
    status_text_lower = status_text.lower()
    if "بهبود" in status_text_lower or "مثبت" in status_text_lower:
        css_class = "status-positive"
    elif "تنش" in status_text_lower or "کاهش" in status_text_lower or "بدتر" in status_text_lower:
        css_class = "status-negative"
    elif "ثابت" in status_text_lower:
        css_class = "status-neutral"
    elif "بدون داده" in status_text_lower or "n/a" in status_text_lower:
         css_class = "status-nodata"
    else:
        css_class = "status-unknown"
    return f'<span class="status-badge {css_class}">{status_text}</span>'


# Initialize GEE and Load Data
if initialize_gee():
    # --- Use GeoJSON for farm data ---
    FARM_GEOJSON_PATH = 'farm_geodata_fixed.geojson'
    farm_data_df = load_farm_data_from_geojson(FARM_GEOJSON_PATH)

# Load Analysis Data only if the file exists
ANALYSIS_CSV_PATH = 'محاسبات 2.csv'
analysis_area_df, analysis_prod_df = None, None
if os.path.exists(ANALYSIS_CSV_PATH):
    analysis_area_df, analysis_prod_df = load_analysis_data(ANALYSIS_CSV_PATH)
else:
    st.sidebar.warning(f"فایل داده‌های تحلیلی '{ANALYSIS_CSV_PATH}' یافت نشد. تب تحلیل داده‌ها غیرفعال خواهد بود.")


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

if 'farm_data_df' in locals() and not farm_data_df.empty: # Check if farm data loaded successfully

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
        "SAVI": "شاخص پوشش گیاهی تعدیل شده خاک",
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

else: # If farm data loading failed
    st.error("بارگذاری داده‌های مزارع با خطا مواجه شد. لطفاً فایل GeoJSON را بررسی کنید.")
    st.stop() # Stop execution if no farm data


# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================

# --- Cloud Masking Function for Sentinel-2 ---
def maskS2clouds(image):
    """Masks clouds in a Sentinel-2 SR image using QA band and SCL band."""
    qa = image.select('QA60')
    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    # Both flags should be set to zero, indicating clear conditions.
    clear_mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(
                   qa.bitwiseAnd(cirrusBitMask).eq(0))

    # Use SCL band for more robust cloud/shadow masking
    scl = image.select('SCL')
    # Keep 'Vegetation'(4), 'Not Vegetated'(5), 'Water'(6), 'Bare Soil'(11)
    # Mask out: 'Saturated/Defective'(1), 'Dark Area Pixels'(2), 'Cloud Shadows'(3),
    # 'Cloud Medium Probability'(8), 'Cloud High Probability'(9), 'Cirrus'(10), 'Snow/Ice'(7 - optional)
    # We choose to keep 7 (Snow/Ice) for broader applicability, mask if needed
    good_quality_scl = scl.remap([4, 5, 6, 11], [1, 1, 1, 1], 0) # Map good classes to 1, others to 0

    # Combine masks and apply scaling/offset
    combined_mask = clear_mask_qa.And(good_quality_scl)

    # Scale optical bands
    opticalBands = image.select('B.*').multiply(0.0001)

    # Return image with scaled bands and applied mask
    return image.addBands(opticalBands, None, True)\
                .updateMask(combined_mask)


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
    # Add small epsilon to NIR denominator to avoid division by zero potential
    msi = image.expression('SWIR1 / (NIR + 0.0001)', {
        'SWIR1': image.select('B11'),
        'NIR': image.select('B8')
    }).rename('MSI')

    # LAI (Leaf Area Index) - Simple estimation using NDVI (Needs calibration for accuracy)
    # Using a very basic placeholder - Requires proper calibration for reliable values
    lai = ndvi.multiply(3.5).max(0).rename('LAI') # Ensure non-negative

    # CVI (Chlorophyll Vegetation Index) - (NIR / Green) * (Red / Green) | S2: (B8 / B3) * (B4 / B3)
    # Handle potential division by zero if Green band is 0
    green_safe = image.select('B3').max(ee.Image(0.0001)) # Avoid division by zero
    cvi = image.expression('(NIR / GREEN_SAFE) * (RED / GREEN_SAFE)', {
        'NIR': image.select('B8'),
        'GREEN_SAFE': green_safe,
        'RED': image.select('B4')
    }).rename('CVI')

    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi]) # Add calculated indices, including SAVI

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
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)) # Apply cloud masking

        # Check if any images are available after filtering and masking
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"هیچ تصویر Sentinel-2 بدون ابر در بازه {start_date} تا {end_date} برای این منطقه یافت نشد."

        # Calculate indices for each image in the collection
        indexed_col = s2_sr_col.map(add_indices)

        # Create a median composite image
        median_image = indexed_col.median() # Use median to reduce noise/outliers

        # Select the desired index band(s) - select all calculated indices initially
        output_image = median_image.select(index_name) # Select the specific index needed

        return output_image, None # Return the image and no error message
    except ee.EEException as e:
        # Handle GEE specific errors
        error_message = f"خطای Google Earth Engine در بازه {start_date}-{end_date}: {e}"
        # Try to extract more details if available
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str):
                if 'computation timed out' in error_details.lower():
                     error_message += "\n(علت احتمالی: حجم بالای پردازش یا بازه زمانی طولانی)"
                elif 'user memory limit exceeded' in error_details.lower():
                     error_message += "\n(علت احتمالی: پردازش منطقه بزرگ یا عملیات پیچیده)"
                elif 'image.select' in error_details.lower() and 'band' in error_details.lower():
                     error_message += f"\n(علت احتمالی: باند مورد نیاز '{index_name}' محاسبه نشده یا در تصاویر اولیه موجود نیست)"
        except Exception:
            pass # Ignore errors during error detail extraction
        return None, error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در پردازش GEE ({start_date}-{end_date}): {e}\n{traceback.format_exc()}"
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
                     .map(add_indices)
                     .select(index_name)) # Select the index early

        def extract_value(image):
            # Extract the index value at the point
            # Use reduceRegion for points; scale should match sensor resolution
            value = image.reduceRegion(
                reducer=ee.Reducer.firstNonNull(), # Use first valid pixel at the point
                geometry=_point_geom,
                scale=10 # Scale in meters (10m for Sentinel-2 RGB/NIR/SWIR)
            ).get(index_name)
            # Return a feature with the value and the image date, only if value is not null
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                index_name: value
            }).set('hasValue', value) # Set a property to filter by later

        # Map over the collection and remove features with null values
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.neq('hasValue', None))

        # Convert the FeatureCollection to a list of dictionaries
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), f"داده‌ای برای سری زمانی {index_name} در بازه {start_date}-{end_date} یافت نشد."

        # Convert to Pandas DataFrame
        ts_data = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_info]
        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        # Handle potential duplicates on the same date (take the mean or last)
        ts_df = ts_df.groupby('date').mean().reset_index()
        ts_df = ts_df.sort_values('date').set_index('date')

        return ts_df, None # Return DataFrame and no error
    except ee.EEException as e:
        error_message = f"خطای GEE در دریافت سری زمانی {index_name}: {e}"
        return pd.DataFrame(columns=['date', index_name]), error_message
    except Exception as e:
        error_message = f"خطای ناشناخته در دریافت سری زمانی {index_name}: {e}\n{traceback.format_exc()}"
        return pd.DataFrame(columns=['date', index_name]), error_message


# ==============================================================================
# Function to get all relevant indices for a farm point for two periods
# ==============================================================================
@st.cache_data(show_spinner="در حال محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_point_geom, start_curr, end_curr, start_prev, end_prev):
    """Calculates mean NDVI, NDMI, EVI, SAVI for current and previous periods."""
    results = {
        'NDVI_curr': None, 'NDMI_curr': None, 'EVI_curr': None, 'SAVI_curr': None,
        'NDVI_prev': None, 'NDMI_prev': None, 'EVI_prev': None, 'SAVI_prev': None,
        'error': None
    }
    indices_to_get = ['NDVI', 'NDMI', 'EVI', 'SAVI']

    def get_mean_values_for_period(start, end):
        period_values = {index: None for index in indices_to_get}
        error_msg = None
        try:
            # Get median composite image with all indices calculated
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_point_geom)
                         .filterDate(start, end)
                         .map(maskS2clouds)
                         .map(add_indices))

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return period_values, f"هیچ تصویری در بازه {start}-{end} یافت نشد"

            # Calculate median composite from the indexed collection
            median_image = s2_sr_col.median() # Calculate median *after* adding indices

            # Reduce region to get the mean value at the point for all indices
            mean_dict = median_image.select(indices_to_get).reduceRegion(
                reducer=ee.Reducer.mean(), # Use mean for the period/point
                geometry=_point_geom,
                scale=10,  # Scale in meters
                maxPixels=1e9 # Allow potentially large computations if needed
            ).getInfo()

            if mean_dict:
                for index in indices_to_get:
                    period_values[index] = mean_dict.get(index) # Get value, defaults to None if key missing
            else:
                 # If reduceRegion returns empty or None
                 return period_values, f"مقدار معتبری در بازه {start}-{end} محاسبه نشد (احتمالاً داده وجود ندارد یا خطا در پردازش)"

            return period_values, None # Success
        except ee.EEException as e:
            error_msg = f"خطای GEE در محاسبه مقادیر متوسط ({start}-{end}): {e}"
            return period_values, error_msg
        except Exception as e:
            error_msg = f"خطای ناشناخته در محاسبه مقادیر متوسط ({start}-{end}): {e}"
            return period_values, error_msg

    # Get data for current period
    curr_values, err_curr = get_mean_values_for_period(start_curr, end_curr)
    if err_curr:
        results['error'] = err_curr
    else:
        results['NDVI_curr'] = curr_values['NDVI']
        results['NDMI_curr'] = curr_values['NDMI']
        results['EVI_curr'] = curr_values['EVI']
        results['SAVI_curr'] = curr_values['SAVI']

    # Get data for previous period
    prev_values, err_prev = get_mean_values_for_period(start_prev, end_prev)
    if err_prev:
        # Append previous period error if a current error already exists
        current_error = results.get('error')
        results['error'] = f"{current_error} | {err_prev}" if current_error else err_prev
    else:
        results['NDVI_prev'] = prev_values['NDVI']
        results['NDMI_prev'] = prev_values['NDMI']
        results['EVI_prev'] = prev_values['EVI']
        results['SAVI_prev'] = prev_values['SAVI']

    return results

# ==============================================================================
# Gemini AI Helper Functions
# ==============================================================================

# Configure Gemini API
@st.cache_resource
def configure_gemini():
    """Configures the Gemini API client using a hardcoded API key (NOT RECOMMENDED)."""
    try:
        # --- WARNING: Hardcoding API keys is insecure! Use Streamlit secrets instead. ---
        # Replace with st.secrets["GEMINI_API_KEY"] if using secrets.toml
        api_key = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- HARDCODED API KEY
        # ---------------------------------------------------------------------------

        if not api_key:
             st.error("❌ کلید API جمینای به صورت مستقیم در کد وارد نشده یا خالی است.")
             return None

        genai.configure(api_key=api_key)
        # Optional: Add safety settings configuration here if needed
        # safety_settings = [...]
        # model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)
        model = genai.GenerativeModel('gemini-1.5-flash') # Use the latest flash model
        print("Gemini Configured Successfully (using hardcoded key).")
        return model
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        return None

# Function to get AI analysis
@st.cache_data(show_spinner="در حال دریافت تحلیل هوش مصنوعی...", persist=True)
def get_ai_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    # Prepare data string, handling None values gracefully
    def format_value(val):
        return f"{val:.3f}" if val is not None else "N/A"

    data_str = ""
    data_str += f"NDVI فعلی: {format_value(index_data.get('NDVI_curr'))} (قبلی: {format_value(index_data.get('NDVI_prev'))})\n"
    data_str += f"NDMI فعلی: {format_value(index_data.get('NDMI_curr'))} (قبلی: {format_value(index_data.get('NDMI_prev'))})\n"
    data_str += f"EVI فعلی: {format_value(index_data.get('EVI_curr'))} (قبلی: {format_value(index_data.get('EVI_prev'))})\n"
    data_str += f"SAVI فعلی: {format_value(index_data.get('SAVI_curr'))} (قبلی: {format_value(index_data.get('SAVI_prev'))})\n"


    prompt = f"""
    شما یک متخصص کشاورزی نیشکر هستید. لطفاً وضعیت مزرعه '{farm_name}' را بر اساس داده‌های شاخص و توصیه‌های اولیه زیر به طور خلاصه (حدود 3-5 جمله) و کاربردی به زبان فارسی تحلیل کنید. تمرکز اصلی تحلیل بر نیاز احتمالی آبیاری و کوددهی باشد و توضیح دهید چرا این نیازها بر اساس شاخص‌ها مطرح شده‌اند.

    داده‌های شاخص:
    {data_str}
    توصیه‌های اولیه:
    {', '.join(recommendations) if recommendations else 'هیچ توصیه‌ اولیه‌ای وجود ندارد.'}

    تحلیل شما (کوتاه و کاربردی):
    """

    try:
        # Use specific generation config if needed (e.g., temperature)
        # generation_config = genai.types.GenerationConfig(temperature=0.7)
        response = _model.generate_content(prompt) #, generation_config=generation_config)

        # Accessing response text might differ slightly based on exact library version
        # Check response object structure if needed (e.g., response.candidates[0].content.parts[0].text)
        if response.parts:
             return response.parts[0].text
        else:
             # Fallback for older versions or different structures
             return response.text # Assuming response.text works

    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API: {e}")
        # Provide more detail if possible from the exception
        return f"خطا در دریافت تحلیل هوش مصنوعی: {str(e)}"



# ==============================================================================
# Main Application Layout (Using Tabs)
# ==============================================================================

# Configure Gemini Model at the start
gemini_model = configure_gemini()

# Define Tabs - **Corrected to include tab2**
tab_titles = ["📊 پایش مزارع"]
if analysis_area_df is not None or analysis_prod_df is not None:
    tab_titles.append("📈 تحلیل محاسبات") # Add analysis tab only if data loaded
else:
     tab_titles.append("📈 تحلیل محاسبات (غیرفعال)") # Indicate disabled tab

tab_titles.append("💧کود و آبیاری")

tabs = st.tabs(tab_titles)
tab1 = tabs[0]
tab2_idx = -1
if "📈 تحلیل محاسبات" in tab_titles:
    tab2_idx = tab_titles.index("📈 تحلیل محاسبات")
    tab2 = tabs[tab2_idx]
tab3 = tabs[-1] # Needs analysis is always the last tab


with tab1:
    # ==============================================================================
    # Main Panel Display (Monitoring)
    # ==============================================================================

    # --- Get Selected Farm Geometry and Details ---
    selected_farm_details = None
    selected_farm_geom = None
    map_center_lat = INITIAL_LAT
    map_center_lon = INITIAL_LON
    initial_zoom = INITIAL_ZOOM


    if selected_farm_name == "همه مزارع":
        # Use the bounding box of all filtered farms for the map view
        if not filtered_farms_df.empty:
            min_lon, min_lat = filtered_farms_df['centroid_lon'].min(), filtered_farms_df['centroid_lat'].min()
            max_lon, max_lat = filtered_farms_df['centroid_lon'].max(), filtered_farms_df['centroid_lat'].max()
            # Create a bounding box geometry
            # Add a small buffer to ensure visibility if points are collinear
            buffer = 0.001
            selected_farm_geom = ee.Geometry.Rectangle([min_lon - buffer, min_lat - buffer, max_lon + buffer, max_lat + buffer])
            map_center_lat = (min_lat + max_lat) / 2
            map_center_lon = (min_lon + max_lon) / 2
            # Adjust zoom based on extent? (Optional - geemap often handles this)
            initial_zoom = 11 # Reset zoom for overview

            st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
            st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
        else:
             st.warning("داده‌ای برای نمایش 'همه مزارع' در این روز وجود ندارد.")
             # Optionally set a default geometry or stop
             selected_farm_geom = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # Default point

    else:
        selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        lat = selected_farm_details['centroid_lat']
        lon = selected_farm_details['centroid_lon']
        # Create geometry based on farm data (Point or Polygon centroid)
        selected_farm_geom = ee.Geometry.Point([lon, lat]) # Use centroid for map focus/calculations
        map_center_lat = lat
        map_center_lon = lon
        initial_zoom = 14 # Zoom closer for single farm


        st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
        # Display farm details using modern cards
        details_cols = st.columns([1, 1, 1, 1]) # Adjust column ratios if needed
        with details_cols[0]:
            area_val = selected_farm_details.get('مساحت', 'N/A')
            area_display = f"{area_val:,.2f}" if pd.notna(area_val) and isinstance(area_val, (int, float)) else "N/A"
            st.markdown(modern_metric_card("مساحت (هکتار)", area_display, icon="fa-ruler-combined"), unsafe_allow_html=True)
        with details_cols[1]:
            st.markdown(modern_metric_card("واریته", f"{selected_farm_details.get('واریته', 'N/A')}", icon="fa-seedling"), unsafe_allow_html=True)
        with details_cols[2]:
            st.markdown(modern_metric_card("گروه", f"{selected_farm_details.get('گروه', 'N/A')}", icon="fa-users"), unsafe_allow_html=True)
        with details_cols[3]:
            st.markdown(modern_metric_card("سن", f"{selected_farm_details.get('سن', 'N/A')}", icon="fa-hourglass-half"), unsafe_allow_html=True)

        # Display coordinates separately or within a card
        # st.markdown(modern_metric_card("مختصات", f"{lat:.5f}, {lon:.5f}", icon="fa-map-marker-alt"), unsafe_allow_html=True)

        st.write(f"**مختصات (مرکزی):** {lat:.5f}, {lon:.5f}")


    # --- Variety Distribution Chart (if multiple farms selected or showing all) ---
    if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
        st.markdown("---")
        st.subheader("توزیع واریته‌ها در مزارع این روز")
        if 'واریته' in filtered_farms_df.columns:
            variety_counts = filtered_farms_df['واریته'].value_counts().sort_values(ascending=False)
            if not variety_counts.empty:
                variety_percent = 100 * variety_counts / variety_counts.sum()
                # ساخت دیتافریم برای نمودار
                pie_df = pd.DataFrame({
                    'واریته': variety_percent.index,
                    'درصد': variety_percent.values
                })
                # نمودار دایره‌ای (Pie Chart)
                fig_pie = px.pie(
                    pie_df,
                    names='واریته',
                    values='درصد',
                    title="درصد هر واریته در مزارع انتخاب شده",
                    hole=0.3,
                    color_discrete_sequence=px.colors.qualitative.Pastel
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05]*len(pie_df))
                fig_pie.update_layout(
                    showlegend=True,
                    height=400,
                    margin=dict(l=20, r=20, t=60, b=20),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                # st.caption("درصد هر واریته از کل مزارع ثبت شده در این روز.")
            else:
                st.info("داده واریته برای مزارع این روز موجود نیست یا خالی است.")
        else:
            st.info("ستون 'واریته' در داده‌های این روز وجود ندارد.")


    # --- Map Display ---
    st.markdown("---")
    st.subheader(" نقشه وضعیت مزارع")

    # Define visualization parameters based on the selected index
    vis_params = {
        'NDVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # Standard NDVI color ramp
        'EVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # Similar to NDVI
        'NDMI': {'min': -0.5, 'max': 0.8, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']}, # Diverging red-blue for moisture
        'SAVI': {'min': 0.0, 'max': 0.9, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']}, # Similar to NDVI
        'LAI': {'min': 0, 'max': 7, 'palette': ['#EFEFEF', '#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Sequential yellow-brown for LAI
        'MSI': {'min': 0, 'max': 3, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b'][::-1]}, # Reversed NDMI palette: high MSI (dry) is red
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Sequential yellow-brown for Chlorophyll proxy
    }

    # Create a geemap Map instance
    m = geemap.Map(
        location=[map_center_lat, map_center_lon],
        zoom=initial_zoom,
        add_google_map=True # Allow Google Maps baselayers
    )
    m.add_basemap("HYBRID") # Default to Google Satellite Hybrid

    # Get the processed image for the current week
    gee_image_current, error_msg_current = None, None
    if selected_farm_geom:
        gee_image_current, error_msg_current = get_processed_image(
            selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )

        if gee_image_current:
            # Add the GEE layer to the map
            try:
                current_vis = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}) # Default vis
                m.addLayer(
                    gee_image_current,
                    current_vis,
                    f"{selected_index} ({start_date_current_str[-5:]} تا {end_date_current_str[-5:]})" # Short date range
                )

                # Add a color bar legend
                m.add_colorbar(
                    current_vis,
                    label=f"{index_options[selected_index]} ({selected_index})",
                    layer_name=f"{selected_index} ({start_date_current_str[-5:]} تا {end_date_current_str[-5:]})"
                 )

                 # Add markers for farms
                if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
                     # Add markers for all filtered farms
                     for idx, farm in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm['centroid_lat'], farm['centroid_lon']],
                             popup=(f"<b>مزرعه:</b> {farm['مزرعه']}<br>"
                                    f"<b>گروه:</b> {farm.get('گروه', 'N/A')}<br>"
                                    f"<b>واریته:</b> {farm.get('واریته', 'N/A')}"
                                   ),
                             tooltip=f"مزرعه {farm['مزرعه']}",
                             icon=folium.Icon(color='blue', icon='info-sign')
                         ).add_to(m)
                     # Adjust map bounds if showing all farms
                     try:
                         m.center_object(selected_farm_geom, zoom=initial_zoom) # Center on the bounding box
                     except Exception as center_err:
                         print(f"Could not center map on geometry: {center_err}") # Non-critical error
                elif selected_farm_details is not None:
                     # Add marker for the single selected farm
                     folium.Marker(
                         location=[lat, lon],
                         popup=(f"<b>مزرعه:</b> {selected_farm_name}<br>"
                                f"<b>گروه:</b> {selected_farm_details.get('گروه', 'N/A')}<br>"
                                f"<b>واریته:</b> {selected_farm_details.get('واریته', 'N/A')}<br>"
                                f"<b>سن:</b> {selected_farm_details.get('سن', 'N/A')}"
                               ),
                         tooltip=f"مزرعه {selected_farm_name}",
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     m.set_center(lon, lat, zoom=14) # Zoom closer for a single farm

                m.add_layer_control() # Add layer control to toggle base maps and layers

            except Exception as map_err:
                st.error(f"خطا در افزودن لایه یا عناصر به نقشه: {map_err}")
                st.error(traceback.format_exc())
        else:
            st.warning(f"تصویری برای نمایش روی نقشه ({selected_index}) در بازه {start_date_current_str} تا {end_date_current_str} یافت نشد.")
            if error_msg_current:
                st.warning(f"علت: {error_msg_current}")
            # Still display the map with markers if no image
            if selected_farm_name == "همه مزارع" and not filtered_farms_df.empty:
                 for idx, farm in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm['centroid_lat'], farm['centroid_lon']],
                             popup=(f"<b>مزرعه:</b> {farm['مزرعه']}<br>"
                                    f"<b>گروه:</b> {farm.get('گروه', 'N/A')}<br>"
                                    f"<b>واریته:</b> {farm.get('واریته', 'N/A')}"
                                   ),
                             tooltip=f"مزرعه {farm['مزرعه']}",
                             icon=folium.Icon(color='gray', icon='info-sign') # Gray icon if no data
                         ).add_to(m)
                 try:
                     m.center_object(selected_farm_geom, zoom=initial_zoom)
                 except Exception as center_err:
                      print(f"Could not center map on geometry: {center_err}")
            elif selected_farm_details is not None:
                  folium.Marker(
                         location=[lat, lon],
                         popup=(f"<b>مزرعه:</b> {selected_farm_name}<br>"
                                f"<b>گروه:</b> {selected_farm_details.get('گروه', 'N/A')}<br>"
                                f"<b>واریته:</b> {selected_farm_details.get('واریته', 'N/A')}<br>"
                                f"<b>سن:</b> {selected_farm_details.get('سن', 'N/A')}"
                               ),
                         tooltip=f"مزرعه {selected_farm_name} (داده تصویری یافت نشد)",
                         icon=folium.Icon(color='gray', icon='star') # Gray icon if no data
                     ).add_to(m)
                  m.set_center(lon, lat, zoom=14)


    # Display the map in Streamlit
    try:
        # Use st_folium for better integration
        st_folium(m, width=None, height=500, use_container_width=True)
        st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها (بالا سمت راست نقشه) برای تغییر نقشه پایه یا نمایش/عدم نمایش لایه شاخص استفاده کنید.")
    except Exception as display_err:
        st.error(f"خطا در نمایش نقشه: {display_err}")
        st.error(traceback.format_exc())

    # Note: Direct PNG download from st_folium/geemap isn't built-in easily.
    st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


    # --- Time Series Chart ---
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom and selected_farm_details is not None:
        # Check if the geometry is a Point for time series
        # A more robust check might involve inspecting selected_farm_details['geometry_type'] if loaded
        is_point = isinstance(selected_farm_geom, ee.geometry.Point)

        if is_point:
            # Define a longer period for the time series chart (e.g., last 6-12 months)
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d') # Last year

            ts_df, ts_error = get_index_time_series(
                selected_farm_geom,
                selected_index,
                start_date=timeseries_start_date,
                end_date=timeseries_end_date
            )

            if ts_error:
                st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                # Create Plotly chart for better customization
                fig_ts = px.line(ts_df, x=ts_df.index, y=selected_index,
                                 title=f"روند زمانی {selected_index} برای مزرعه {selected_farm_name}",
                                 labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'})
                fig_ts.update_traces(mode='lines+markers')
                fig_ts.update_layout(hovermode="x unified")
                st.plotly_chart(fig_ts, use_container_width=True)
                st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 12 ماه گذشته.")
            else:
                st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه {timeseries_start_date} تا {timeseries_end_date} یافت نشد.")
        else:
            st.warning("نمودار سری زمانی فقط برای مزارع با هندسه نقطه‌ای (انتخاب تک مزرعه) در دسترس است.")
    else:
        # This case might occur if 'همه مزارع' is selected but filtered_farms_df is empty,
        # or if selected_farm_name is specific but details couldn't be found (shouldn't happen with current logic)
        st.warning("هندسه یا جزئیات مزرعه برای نمودار سری زمانی در دسترس نیست.")


    # ==============================================================================
    # Helper Function for Status Determination
    # ==============================================================================

    def determine_status(row, index_name):
        """Determines the status based on change in index value."""
        current_val_col = f'{index_name} (هفته جاری)'
        prev_val_col = f'{index_name} (هفته قبل)'
        change_col = 'تغییر'

        # Check if necessary columns exist and data is present
        if not all(col in row.index for col in [current_val_col, prev_val_col, change_col]):
            return "خطا در ستون" # Indicate missing columns
        if pd.isna(row[change_col]) or pd.isna(row[current_val_col]) or pd.isna(row[prev_val_col]):
            # Check if only one value is present
            if pd.notna(row[current_val_col]) and pd.isna(row[prev_val_col]):
                 return "جدید" # Data only for current week
            elif pd.isna(row[current_val_col]) and pd.notna(row[prev_val_col]):
                 return "حذف شده؟" # Data only for previous week
            else:
                 return "بدون داده" # Both missing or change couldn't be calculated


        change_val = row[change_col]
        # Threshold for significant change (relative or absolute)
        # Let's use a relative threshold for indices like NDVI/EVI
        # And an absolute threshold for indices like NDMI/MSI? Or keep it simple with absolute.
        absolute_threshold = 0.05 # e.g., 0.05 change in NDVI/NDMI
        # relative_threshold_percent = 5 # e.g., 5% change

        # Status based on index type and change direction
        higher_is_better = index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI', 'SAVI']
        lower_is_better = index_name in ['MSI']

        if higher_is_better:
            if change_val > absolute_threshold:
                return "رشد مثبت / بهبود"
            elif change_val < -absolute_threshold:
                return "تنش / کاهش"
            else:
                return "ثابت"
        elif lower_is_better:
            if change_val < -absolute_threshold: # Negative change means improvement (less stress)
                return "بهبود / کاهش تنش"
            elif change_val > absolute_threshold: # Positive change means deterioration (more stress)
                return "تنش / بدتر شدن"
            else:
                return "ثابت"
        else:
            # Default case if index type is unknown
            # Check absolute change
             if abs(change_val) > absolute_threshold:
                 return f"تغییر یافته ({change_val:+.2f})"
             else:
                 return "ثابت"

    # ==============================================================================
    # Ranking Table
    # ==============================================================================
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown(f"مقایسه مقادیر متوسط شاخص در هفته جاری ({end_date_current_str}) با هفته قبل ({end_date_previous_str}).")

    # Use a placeholder for the progress bar display area
    progress_placeholder = st.empty()

    @st.cache_data(show_spinner=False, persist=True) # Show spinner handled manually
    def calculate_weekly_indices(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
        """Calculates the average index value for the current and previous week for a list of farms."""
        results = []
        errors = []
        total_farms = len(_farms_df)
        # progress_bar = st.progress(0) # Use st.progress

        status_text = st.empty() # For text updates
        status_text.info(f"⏳ در حال محاسبه {index_name} برای {total_farms} مزرعه...")


        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            farm_name = farm['مزرعه']
            lat = farm['centroid_lat']
            lon = farm['centroid_lon']
            point_geom = ee.Geometry.Point([lon, lat])

            current_val, previous_val = None, None
            err_curr, err_prev = None, None

            def get_mean_value_robust(start, end):
                """Wrapper to get mean value, handling potential errors gracefully."""
                try:
                    # Use the main processing function, select the specific index
                    image_period, error_img = get_processed_image(point_geom, start, end, index_name)

                    if image_period:
                        # Reduce region to get the mean value at the point
                        mean_dict = image_period.reduceRegion(
                            reducer=ee.Reducer.mean(), # Use mean over the period/point
                            geometry=point_geom,
                            scale=10,  # Scale in meters
                            maxPixels=1e9
                        ).getInfo()

                        val = mean_dict.get(index_name) if mean_dict else None
                        if val is not None:
                             return val, None # Success
                        else:
                             # If reduceRegion worked but returned no value for the index
                             return None, f"مقدار {index_name} در بازه {start}-{end} یافت نشد (احتمالاً تمام پیکسل‌ها ماسک شده‌اند)"
                    else:
                        # If get_processed_image failed
                         return None, error_img # Return the error from get_processed_image
                except ee.EEException as e:
                     return None, f"خطای GEE در reduceRegion ({start}-{end}): {e}"
                except Exception as e:
                     return None, f"خطای ناشناخته در محاسبه مقدار ({start}-{end}): {e}"


            # Calculate for current week
            current_val, err_curr = get_mean_value_robust(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")

            # Calculate for previous week
            previous_val, err_prev = get_mean_value_robust(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")

            # Calculate change
            change = None
            if current_val is not None and previous_val is not None:
                try:
                    # Ensure both are numbers before subtracting
                    if isinstance(current_val, (int, float)) and isinstance(previous_val, (int, float)):
                        change = current_val - previous_val
                    else:
                         change = None # If types are wrong, cannot calculate change
                except TypeError:
                    change = None # Handle unexpected types

            results.append({
                'مزرعه': farm_name,
                'گروه': farm.get('گروه', 'N/A'),
                f'{index_name} (هفته جاری)': current_val,
                f'{index_name} (هفته قبل)': previous_val,
                'تغییر': change
            })

            # Update progress bar and status text
            progress_fraction = (i + 1) / total_farms
            # Update the placeholder with the progress bar HTML
            progress_placeholder.markdown(modern_progress_bar(progress_fraction), unsafe_allow_html=True)
            # Optionally update status text less frequently
            # if (i + 1) % 5 == 0 or (i + 1) == total_farms: # Update every 5 farms or at the end
            #     status_text.info(f"⏳ پردازش مزرعه {i+1} از {total_farms}...")


        status_text.success(f"✅ محاسبه {index_name} برای {total_farms} مزرعه تکمیل شد.")
        progress_placeholder.empty() # Remove progress bar after completion
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
        with st.expander("مشاهده خطاهای محاسبه (کلیک کنید)", expanded=False):
            st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها برای مزارع زیر رخ داد:")
            # Show errors grouped by farm if possible, or just list them
            # Create a dictionary to group errors by farm
            error_dict = {}
            for error_str in calculation_errors:
                try:
                    farm_name_err = error_str.split(" (")[0]
                    if farm_name_err not in error_dict:
                        error_dict[farm_name_err] = []
                    error_dict[farm_name_err].append(error_str)
                except Exception:
                     if "Unknown" not in error_dict: error_dict["Unknown"] = []
                     error_dict["Unknown"].append(error_str) # Fallback

            for farm_name_err, err_list in error_dict.items():
                 st.error(f"**مزرعه: {farm_name_err}**")
                 for err in err_list:
                      st.caption(f"- {err}")
            #for error in calculation_errors: # Simple list view
            #    st.warning(f"- {error}")

    if not ranking_df.empty:
        # Sort by the current week's index value
        # Higher is better for most indices, lower for MSI
        ascending_sort = selected_index in ['MSI'] # True if lower value is better
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)',
            ascending=ascending_sort,
            na_position='last' # Put farms with no data at the bottom
        ).reset_index(drop=True)

        # Add rank number (starting from 1)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # Apply the determine_status function to get status text
        ranking_df_sorted['وضعیت_متن'] = ranking_df_sorted.apply(
            lambda row: determine_status(row, selected_index), axis=1
        )
        # Apply the status_badge function to generate HTML badges
        ranking_df_sorted['وضعیت'] = ranking_df_sorted['وضعیت_متن'].apply(status_badge)


        # Format numeric columns for better readability, handle N/A
        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                 # Check if column exists before formatting
                 ranking_df_sorted[col] = ranking_df_sorted[col].apply(lambda x: f"{x:.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x))

        # Select and order columns to display
        display_columns_order = [
            'مزرعه', 'گروه',
             f'{selected_index} (هفته جاری)',
             f'{selected_index} (هفته قبل)',
             'تغییر',
             'وضعیت' # The HTML badge column
             ]
        # Ensure only existing columns are selected
        display_columns = [col for col in display_columns_order if col in ranking_df_sorted.columns]

        # Display the table using st.dataframe for interactivity or st.write(html) for static badges
        st.markdown("<style> td, th { text-align: right !important; } </style>", unsafe_allow_html=True) # Ensure right alignment for Farsi
        # Use st.write with HTML to render badges correctly
        st.write(ranking_df_sorted[display_columns].to_html(escape=False, index=True, classes='dataframe table table-striped', justify='right'), unsafe_allow_html=True)


        # --- Summary Metrics ---
        st.subheader("📊 خلاصه وضعیت مزارع")
        status_counts_text = ranking_df_sorted['وضعیت_متن'].value_counts()

        # Define categories based on expected status text
        positive_terms = ["رشد مثبت / بهبود", "بهبود / کاهش تنش", "جدید"]
        negative_terms = ["تنش / کاهش", "تنش / بدتر شدن", "حذف شده?"]
        neutral_terms = ["ثابت"]
        nodata_terms = ["بدون داده", "خطا در ستون"]

        # Calculate counts for each category
        positive_count = sum(status_counts_text.get(term, 0) for term in positive_terms)
        negative_count = sum(status_counts_text.get(term, 0) for term in negative_terms)
        neutral_count = sum(status_counts_text.get(term, 0) for term in neutral_terms)
        nodata_count = sum(status_counts_text.get(term, 0) for term in nodata_terms)
        unknown_count = len(ranking_df_sorted) - (positive_count + negative_count + neutral_count + nodata_count)

        summary_cols = st.columns(4)
        with summary_cols[0]:
            st.metric("🟢 بهبود/جدید", positive_count)
        with summary_cols[1]:
            st.metric("🔴 تنش/کاهش", negative_count)
        with summary_cols[2]:
            st.metric("⚪ ثابت", neutral_count)
        with summary_cols[3]:
            st.metric("⚫ بدون داده/خطا", nodata_count + unknown_count)


        # Add explanation of status terms
        st.info(f"""
        **راهنمای وضعیت:**
        - **🟢 رشد مثبت / بهبود / کاهش تنش / جدید**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند یا داده فقط برای هفته جاری موجود است.
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش / کاهش / بدتر شدن / حذف شده?**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند یا داده فقط برای هفته قبل موجود است.
        - **⚫ بدون داده / خطا**: مزارعی که داده کافی برای محاسبه وضعیت در هر دو هفته وجود نداشته یا در ستون‌ها مشکلی وجود داشته است.
        """)

        # Add download button for the table (including the raw status text)
        csv_df = ranking_df_sorted.drop(columns=['وضعیت']) # Drop HTML badge column for CSV
        csv_data = csv_df.to_csv(index=True, encoding='utf-8-sig') # Use utf-8-sig for Excel compatibility
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)",
            data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
            mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد یا محاسبه ناموفق بود.")


# --- Tab 2: Analysis Data Visualization (Conditional) ---
# Check if the tab exists before trying to use it
if tab2_idx != -1:
    with tab2: # Use the correct tab variable
        st.header("تحلیل داده‌های فایل محاسبات")
        st.markdown("نمایش گرافیکی داده‌های مساحت و تولید به تفکیک اداره و سن.")

        if analysis_area_df is not None or analysis_prod_df is not None:

            # Get unique 'اداره' values from both dataframes if they exist
            available_edareh = []
            if analysis_area_df is not None and 'اداره' in analysis_area_df.index.names:
                try:
                    available_edareh.extend(analysis_area_df.index.get_level_values('اداره').unique().tolist())
                except KeyError:
                    st.warning("سطح 'اداره' در ایندکس داده مساحت یافت نشد.")
            if analysis_prod_df is not None and 'اداره' in analysis_prod_df.index.names:
                 try:
                    available_edareh.extend(analysis_prod_df.index.get_level_values('اداره').unique().tolist())
                 except KeyError:
                     st.warning("سطح 'اداره' در ایندکس داده تولید یافت نشد.")


            # Ensure unique and sorted list of integers
            try:
                available_edareh = sorted(list(set(map(int, filter(lambda x: isinstance(x, (int, float)) and pd.notna(x), available_edareh)))))
            except Exception:
                 available_edareh = sorted(list(set(filter(pd.notna, available_edareh)))) # Keep as is if conversion fails


            if not available_edareh:
                st.warning("هیچ اداره‌ای برای نمایش در داده‌های تحلیلی یافت نشد.")
            else:
                selected_edareh = st.selectbox(
                    "اداره مورد نظر را انتخاب کنید:",
                    options=available_edareh,
                    key='analysis_edareh_select'
                )

                # --- Display Data for Selected Edareh ---
                st.subheader(f"داده‌های اداره: {selected_edareh}")

                col1, col2 = st.columns(2)

                # --- Area Data Visualization ---
                with col1:
                    st.markdown("#### مساحت (هکتار)")
                    df_area_selected = None
                    if analysis_area_df is not None:
                         try:
                            if selected_edareh in analysis_area_df.index.get_level_values('اداره'):
                                df_area_selected = analysis_area_df.loc[selected_edareh].copy()
                                # Drop rows/cols that are entirely NaN before plotting
                                df_area_selected = df_area_selected.dropna(axis=0, how='all').dropna(axis=1, how='all')
                            else:
                                st.info(f"داده مساحت برای اداره {selected_edareh} یافت نشد.")
                         except KeyError:
                                st.info(f"داده مساحت برای اداره {selected_edareh} یافت نشد (خطای Key).")
                         except Exception as e:
                                st.error(f"خطا در دسترسی به داده مساحت برای اداره {selected_edareh}: {e}")


                    if df_area_selected is not None and not df_area_selected.empty:
                        # Prepare data for plots
                        varieties = df_area_selected.columns.tolist()
                        ages = df_area_selected.index.tolist()
                        z_data = df_area_selected.fillna(0).values # Fill NA with 0 for surface plot

                        # Surface Plot (if enough data)
                        if len(ages) > 1 and len(varieties) > 1 :
                             try:
                                 fig_3d_area = go.Figure(data=[go.Surface(z=z_data, x=ages, y=varieties, colorscale='Viridis', showscale=True)])
                                 fig_3d_area.update_layout(
                                     title=f'Surface Plot مساحت - اداره {selected_edareh}',
                                     scene=dict(
                                         xaxis_title='سن',
                                         yaxis_title='واریته',
                                         zaxis_title='مساحت (هکتار)'),
                                     autosize=True, height=500, margin=dict(l=40, r=40, b=40, t=80))
                                 st.plotly_chart(fig_3d_area, use_container_width=True)
                             except Exception as e:
                                 st.error(f"خطا در ایجاد نمودار Surface Plot مساحت: {e}")
                                 st.dataframe(df_area_selected) # Show table as fallback
                        else:
                             st.info("داده کافی برای رسم نمودار Surface Plot مساحت وجود ندارد (نیاز به بیش از یک سن و یک واریته).")
                             st.dataframe(df_area_selected.fillna("N/A")) # Show table if not enough data for 3D

                        # Bar Chart of Area per Variety (Summed over Ages)
                        area_by_variety = df_area_selected.sum(axis=0) # Sum area for each variety
                        if not area_by_variety.empty:
                            fig_bar_area = px.bar(area_by_variety, x=area_by_variety.index, y=area_by_variety.values,
                                                   title=f'مجموع مساحت بر اساس واریته - اداره {selected_edareh}',
                                                   labels={'index':'واریته', 'y':'مجموع مساحت (هکتار)'})
                            st.plotly_chart(fig_bar_area, use_container_width=True)

                        # Bar Chart of Area per Age (Summed over Varieties)
                        area_by_age = df_area_selected.sum(axis=1) # Sum area for each age
                        if not area_by_age.empty:
                             fig_bar_age_area = px.bar(area_by_age, x=area_by_age.index, y=area_by_age.values,
                                                    title=f'مجموع مساحت بر اساس سن - اداره {selected_edareh}',
                                                    labels={'index':'سن', 'y':'مجموع مساحت (هکتار)'})
                             st.plotly_chart(fig_bar_age_area, use_container_width=True)


                    elif analysis_area_df is not None: # If df exists but no data for selected edareh
                        st.info(f"داده مساحت برای اداره {selected_edareh} یافت نشد یا خالی است.")
                    # else: analysis_area_df is None - warning already shown

                # --- Production Data Visualization ---
                with col2:
                    st.markdown("#### تولید (تن)")
                    df_prod_selected = None
                    if analysis_prod_df is not None:
                         try:
                            if selected_edareh in analysis_prod_df.index.get_level_values('اداره'):
                                df_prod_selected = analysis_prod_df.loc[selected_edareh].copy()
                                # Drop rows/cols that are entirely NaN before plotting
                                df_prod_selected = df_prod_selected.dropna(axis=0, how='all').dropna(axis=1, how='all')
                            else:
                                st.info(f"داده تولید برای اداره {selected_edareh} یافت نشد.")
                         except KeyError:
                             st.info(f"داده تولید برای اداره {selected_edareh} یافت نشد (خطای Key).")
                         except Exception as e:
                             st.error(f"خطا در دسترسی به داده تولید برای اداره {selected_edareh}: {e}")

                    if df_prod_selected is not None and not df_prod_selected.empty:
                        # Prepare data for plots
                        varieties_prod = df_prod_selected.columns.tolist()
                        ages_prod = df_prod_selected.index.tolist()
                        z_data_prod = df_prod_selected.fillna(0).values # Fill NA with 0 for surface plot

                        # Surface Plot (if enough data)
                        if len(ages_prod) > 1 and len(varieties_prod) > 1:
                             try:
                                 fig_3d_prod = go.Figure(data=[go.Surface(z=z_data_prod, x=ages_prod, y=varieties_prod, colorscale='Plasma', showscale=True)])
                                 fig_3d_prod.update_layout(
                                     title=f'Surface Plot تولید - اداره {selected_edareh}',
                                     scene=dict(
                                         xaxis_title='سن',
                                         yaxis_title='واریته',
                                         zaxis_title='تولید (تن)'),
                                     autosize=True, height=500, margin=dict(l=40, r=40, b=40, t=80))
                                 st.plotly_chart(fig_3d_prod, use_container_width=True)
                             except Exception as e:
                                  st.error(f"خطا در ایجاد نمودار Surface Plot تولید: {e}")
                                  st.dataframe(df_prod_selected) # Show table as fallback
                        else:
                             st.info("داده کافی برای رسم نمودار Surface Plot تولید وجود ندارد (نیاز به بیش از یک سن و یک واریته).")
                             st.dataframe(df_prod_selected.fillna("N/A")) # Show table if not enough data for 3D

                        # Bar Chart of Production per Variety (Summed over Ages)
                        prod_by_variety = df_prod_selected.sum(axis=0)
                        if not prod_by_variety.empty:
                            fig_bar_prod = px.bar(prod_by_variety, x=prod_by_variety.index, y=prod_by_variety.values,
                                                  title=f'مجموع تولید بر اساس واریته - اداره {selected_edareh}',
                                                  labels={'index':'واریته', 'y':'مجموع تولید (تن)'})
                            st.plotly_chart(fig_bar_prod, use_container_width=True)

                         # Bar Chart of Production per Age (Summed over Varieties)
                        prod_by_age = df_prod_selected.sum(axis=1)
                        if not prod_by_age.empty:
                             fig_bar_age_prod = px.bar(prod_by_age, x=prod_by_age.index, y=prod_by_age.values,
                                                    title=f'مجموع تولید بر اساس سن - اداره {selected_edareh}',
                                                    labels={'index':'سن', 'y':'مجموع تولید (تن)'})
                             st.plotly_chart(fig_bar_age_prod, use_container_width=True)

                    elif analysis_prod_df is not None: # If df exists but no data for selected edareh
                        st.info(f"داده تولید برای اداره {selected_edareh} یافت نشد یا خالی است.")
                    # else: analysis_prod_df is None - warning already shown

        else: # If analysis dataframes failed to load
            st.error("خطا در بارگذاری یا پردازش داده‌های تحلیل. این تب نمی‌تواند نمایش داده شود.")

# --- New Tab for Needs Analysis ---
with tab3:
    st.header("تحلیل نیاز آبیاری و کوددهی")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری در تب 'پایش مزارع' انتخاب کنید تا تحلیل نیازهای آن در این تب نمایش داده شود.")
    elif selected_farm_geom and selected_farm_details is not None: # Ensure details are available
        # Check if it's a point geometry for analysis (using centroid)
        is_point = isinstance(selected_farm_geom, ee.geometry.Point) # Check the geometry used
        if not is_point:
            st.warning("تحلیل نیازها فقط برای مزارع با مختصات نقطه‌ای (انتخاب تک مزرعه) در دسترس است.")
        else:
            st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

            # --- Define thresholds (allow user adjustment in sidebar or here) ---
            st.markdown("**تنظیم آستانه‌های هشدار:**")
            thresh_cols = st.columns(2)
            with thresh_cols[0]:
                ndmi_threshold = st.slider("آستانه NDMI برای هشدار کم آبی:", -0.2, 0.5, 0.25, 0.01, format="%.2f",
                                         help="اگر NDMI کمتر از این مقدار باشد، احتمال نیاز به آبیاری بیشتر است.")
            with thresh_cols[1]:
                ndvi_drop_threshold = st.slider("آستانه افت NDVI برای بررسی تغذیه (%):", 0.0, 20.0, 7.0, 0.5, format="%.1f%%",
                                            help="اگر NDVI نسبت به هفته قبل بیش از این درصد افت کند، ممکن است نیاز به بررسی کوددهی یا عوامل دیگر باشد.")

            # --- Get the required index data for the selected farm's centroid ---
            farm_needs_data = get_farm_needs_data(
                selected_farm_geom, # Use the Point geometry
                start_date_current_str, end_date_current_str,
                start_date_previous_str, end_date_previous_str
            )

            if farm_needs_data['error']:
                st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل نیازها:")
                st.error(farm_needs_data['error']) # Show specific GEE/calculation error
            elif farm_needs_data['NDMI_curr'] is None or farm_needs_data['NDVI_curr'] is None:
                st.warning("داده‌های شاخص لازم (NDMI و/یا NDVI) برای تحلیل در دوره فعلی یافت نشد. ممکن است به دلیل پوشش ابر یا نبود تصویر باشد.")
                # Display available data if any
                st.markdown("**مقادیر شاخص‌ها (هفته جاری - در صورت وجود):**")
                idx_cols_partial = st.columns(4)
                with idx_cols_partial[0]: st.metric("NDVI", format_value(farm_needs_data.get('NDVI_curr')))
                with idx_cols_partial[1]: st.metric("NDMI", format_value(farm_needs_data.get('NDMI_curr')))
                with idx_cols_partial[2]: st.metric("EVI", format_value(farm_needs_data.get('EVI_curr')))
                with idx_cols_partial[3]: st.metric("SAVI", format_value(farm_needs_data.get('SAVI_curr')))

            else: # Data is available
                # --- Display Current Indices ---
                st.markdown("**مقادیر شاخص‌ها (مقایسه هفتگی):**")
                idx_cols = st.columns(4)
                with idx_cols[0]: st.metric("NDVI", f"{farm_needs_data['NDVI_curr']:.3f}", f"{farm_needs_data['NDVI_curr'] - farm_needs_data.get('NDVI_prev', farm_needs_data['NDVI_curr']):+.3f}" if farm_needs_data.get('NDVI_prev') is not None else "N/A")
                with idx_cols[1]: st.metric("NDMI", f"{farm_needs_data['NDMI_curr']:.3f}", f"{farm_needs_data['NDMI_curr'] - farm_needs_data.get('NDMI_prev', farm_needs_data['NDMI_curr']):+.3f}" if farm_needs_data.get('NDMI_prev') is not None else "N/A")
                with idx_cols[2]: st.metric("EVI", f"{farm_needs_data.get('EVI_curr', 'N/A'):.3f}" if farm_needs_data.get('EVI_curr') is not None else "N/A", f"{farm_needs_data['EVI_curr'] - farm_needs_data.get('EVI_prev', farm_needs_data['EVI_curr']):+.3f}" if farm_needs_data.get('EVI_curr') is not None and farm_needs_data.get('EVI_prev') is not None else "N/A" )
                with idx_cols[3]: st.metric("SAVI", f"{farm_needs_data.get('SAVI_curr', 'N/A'):.3f}" if farm_needs_data.get('SAVI_curr') is not None else "N/A", f"{farm_needs_data['SAVI_curr'] - farm_needs_data.get('SAVI_prev', farm_needs_data['SAVI_curr']):+.3f}" if farm_needs_data.get('SAVI_curr') is not None and farm_needs_data.get('SAVI_prev') is not None else "N/A")
                st.caption("مقدار اصلی شاخص در هفته جاری نمایش داده شده است. دلتا (تغییر نسبت به هفته قبل) در زیر آن نشان داده شده است (در صورت وجود داده هفته قبل).")


                # --- Generate Recommendations ---
                recommendations = []
                issues_found = False # Flag to track if any negative condition is met

                # 1. Irrigation Check (Low NDMI)
                if farm_needs_data['NDMI_curr'] < ndmi_threshold:
                    recommendations.append(f"💧 **نیاز احتمالی به آبیاری:** مقدار NDMI ({farm_needs_data['NDMI_curr']:.3f}) کمتر از آستانه ({ndmi_threshold:.2f}) است که نشان‌دهنده رطوبت پایین پوشش گیاهی است.")
                    issues_found = True

                # 2. Fertilization/Stress Check (Significant NDVI drop)
                if farm_needs_data.get('NDVI_prev') is not None and farm_needs_data['NDVI_curr'] < farm_needs_data['NDVI_prev']:
                     # Calculate relative change percentage
                     try: # Avoid division by zero if NDVI_prev is very small or zero
                         if abs(farm_needs_data['NDVI_prev']) > 1e-6:
                             ndvi_change_percent = ((farm_needs_data['NDVI_curr'] - farm_needs_data['NDVI_prev']) / abs(farm_needs_data['NDVI_prev'])) * 100
                             # Check if the drop exceeds the threshold (change is negative, so compare absolute value)
                             if abs(ndvi_change_percent) > ndvi_drop_threshold:
                                 recommendations.append(f"⚠️ **نیاز به بررسی تغذیه/تنش:** افت قابل توجه NDVI ({ndvi_change_percent:.1f}%) نسبت به هفته قبل مشاهده شد. این می‌تواند ناشی از کمبود مواد مغذی، تنش آبی، آفت یا بیماری باشد. بررسی میدانی توصیه می‌شود.")
                                 issues_found = True
                         else: # NDVI previous was zero or near-zero
                             if farm_needs_data['NDVI_curr'] > 0.1: # If current NDVI is reasonably positive
                                 recommendations.append(f"📈 **رشد NDVI:** مقدار NDVI از نزدیک صفر به {farm_needs_data['NDVI_curr']:.3f} افزایش یافته است.")
                             # Else: still near zero, no significant change comment needed

                     except Exception as e:
                         st.warning(f"خطا در محاسبه درصد تغییر NDVI: {e}")

                elif farm_needs_data.get('NDVI_prev') is None:
                     st.caption("داده NDVI هفته قبل برای محاسبه روند در دسترس نیست.")

                # 3. General Health check (Low NDVI) - Add an absolute check
                if farm_needs_data['NDVI_curr'] < 0.3: # Example threshold for very low vegetation cover
                    # Avoid duplicating stress message if already triggered by drop
                    if not any("تغذیه/تنش" in rec for rec in recommendations):
                        recommendations.append(f"📉 **پوشش گیاهی ضعیف:** مقدار NDVI ({farm_needs_data['NDVI_curr']:.3f}) پایین است. وضعیت کلی مزرعه نیاز به بررسی دارد.")
                        issues_found = True


                # 4. Default if no specific issues flagged
                if not issues_found and not recommendations: # Ensure no recommendations were added for other reasons (like NDVI increase)
                    recommendations.append("✅ **وضعیت مطلوب:** بر اساس شاخص‌های NDMI و روند NDVI، وضعیت کلی مزرعه در حال حاضر مطلوب به نظر می‌رسد و هشداری شناسایی نشد.")

                # Display Recommendations Clearly
                st.markdown("**توصیه‌های اولیه:**")
                if recommendations:
                    for rec in recommendations:
                        if "آبیاری" in rec: st.error(rec)
                        elif "تغذیه/تنش" in rec: st.warning(rec)
                        elif "ضعیف" in rec: st.warning(rec)
                        else: st.success(rec) # For positive/neutral messages
                else:
                    # Should not happen due to default message, but as a fallback:
                    st.info("هیچ توصیه خاصی بر اساس آستانه‌های تنظیم شده ایجاد نشد.")


                # --- Get and Display AI Analysis ---
                st.markdown("---")
                st.markdown("**تحلیل هوش مصنوعی (Gemini):**")
                if gemini_model:
                    ai_explanation = get_ai_analysis(gemini_model, selected_farm_name, farm_needs_data, [rec.split(':')[0].strip() for rec in recommendations]) # Pass concise recommendations
                    st.markdown(ai_explanation)
                else:
                    st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست.")

    else:
         st.info("ابتدا یک مزرعه معتبر را از پنل کناری در تب 'پایش مزارع' انتخاب کنید.")


st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💚 توسط [نام شما یا تیم شما]") # Add credit
st.sidebar.markdown("[پیوند به GitHub یا مستندات](https://your-link-here)") # Optional link
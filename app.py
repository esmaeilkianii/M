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
import google.generativeai as genai

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
        /* Dark mode support */
        @media (prefers-color-scheme: dark) {
            html, body, .main, .stApp {
                background: linear-gradient(135deg, #232526 0%, #414345 100%);
                color: #f8fafc;
            }
        }
        /* Status badges */
        .status-badge {
            display: inline-block;
            padding: 0.25em 0.5em;
            font-size: 0.75em;
            font-weight: bold;
            line-height: 1;
            text-align: center;
            white-space: nowrap;
            vertical-align: baseline;
            border-radius: 0.25rem;
            color: #fff;
        }
        .status-positive {
            background-color: #28a745; /* Green */
        }
        .status-negative {
            background-color: #dc3545; /* Red */
        }
        .status-neutral {
            background-color: #6c757d; /* Grey */
             color: #fff; /* Ensure text is white */
        }
        .status-nodata {
            background-color: #ffc107; /* Yellow */
            color: #212529; /* Dark text */
        }
    </style>
""", unsafe_allow_html=True)

# --- Helper for Status Badges ---
def status_badge(status: str) -> str:
    """Returns HTML for a status badge with color."""
    if "بهبود" in status or "رشد مثبت" in status:
        badge_class = "status-positive"
    elif "تنش" in status or "کاهش" in status or "بدتر شدن" in status:
        badge_class = "status-negative"
    elif "ثابت" in status:
        badge_class = "status-neutral"
    elif "بدون داده" in status:
         badge_class = "status-nodata"
    else:
        badge_class = "status-neutral" # Default

    return f'<span class="status-badge {badge_class}">{status}</span>'


# --- Helper for Modern Metric Card ---
def modern_metric_card(title: str, value: str, icon: str, color: str) -> str:
    """
    Returns a modern styled HTML card for displaying a metric.
    :param title: Title of the metric
    :param value: Value of the metric
    :param icon: FontAwesome icon class (e.g., 'fa-leaf')
    :param color: Accent color for the card background gradient
    :return: HTML string
    """
    return f'''
    <div class="modern-card" style="background: linear-gradient(135deg, {color} 0%, #185a9d 100%);">
        <div style="font-size: 0.9em; opacity: 0.8;">{title} <i class="fa {icon}"></i></div>
        <div style="font-size: 1.8em; font-weight: bold; margin-top: 5px;">{value}</div>
    </div>
    '''

# --- Modern Progress Bar (HTML) ---
# Moved this function definition BEFORE its usage in calculate_weekly_indices
def modern_progress_bar(progress: float) -> str:
    """
    Returns a modern styled HTML progress bar for Streamlit.
    :param progress: float between 0 and 1
    :return: HTML string
    """
    percent = int(progress * 100)
    # Adjust color gradient based on progress
    color_start = '#43cea2' # Greenish
    color_end = '#185a9d'   # Bluish
    intermediate_color = '#ffc107' # Yellowish for middle
    if percent < 50:
         current_color_end = f"rgba({int(0x43 + (0xff-0x43)*(percent/50))},{int(0xce + (0xc1-0xce)*(percent/50))},{int(0xa2 + (0x07-0xa2)*(percent/50))},1)"
         background_gradient = f"linear-gradient(90deg, {color_start} 0%, {current_color_end} 100%)"
    elif percent < 100:
         current_color_start = f"rgba({int(0xff + (0x18-0xff)*((percent-50)/50))},{int(0xc1 + (0x5a-0xc1)*((percent-50)/50))},{int(0x07 + (0x9d-0x07)*((percent-50)/50))},1)"
         background_gradient = f"linear-gradient(90deg, {intermediate_color} 0%, {current_color_start} 100%)"
    else:
         background_gradient = f"linear-gradient(90deg, {color_start} 0%, {color_end} 100%)"


    return f'''
    <div style="width: 100%; background: #e0f7fa; border-radius: 12px; height: 22px; margin: 8px 0; box-shadow: 0 2px 8px rgba(30,60,114,0.08);">
      <div style="width: {percent}%; background: {background_gradient}; height: 100%; border-radius: 12px; transition: width 0.3s;"></div>
      <span style="position: absolute; left: 50%; top: 0; transform: translateX(-50%); color: #185a9d; font-weight: bold; line-height: 22px;">{percent}%</span>
    </div>
    '''


# --- Sidebar Logo ---
st.sidebar.markdown(
    """
    <div class='sidebar-logo'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' alt='لوگو سامانه' />
    </div>
    """,
    unsafe_allow_html=True
)

# --- Main Header with Logo ---
st.markdown(
    """
    <div style='display: flex; align-items: center; gap: 16px; margin-bottom: 0.5rem;'>
        <img src='https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/logo%20(1).png' class='main-logo' alt='لوگو' />
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

# --- File Paths (Relative to the script location or accessible via URL) ---
# Assuming the files are in the same repo or accessible path
CSV_FILE_PATH = 'برنامه_ریزی_با_مختصات (1).csv' # Not used in the provided code logic, kept for reference
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
FARM_GEOJSON_PATH = 'farm_geodata_fixed.geojson'
ANALYSIS_CSV_PATH = 'محاسبات 2.csv'


# --- GEE Authentication ---
@st.cache_resource # Cache the GEE initialization
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        # Check if running locally or in a deployment environment
        if os.path.exists(SERVICE_ACCOUNT_FILE):
            credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
            print("GEE Initialized Successfully using Service Account File.")
        else:
            # Attempt to use environment variables if service account file is not found (for deployment)
            # Ensure EE_ACCOUNT and EE_PRIVATE_KEY are set in your environment or secrets
            # For Streamlit Cloud, use secrets: https://docs.streamlit.io/streamlit-cloud/get-started/secrets-management
            try:
                # Assuming EE_ACCOUNT and EE_PRIVATE_KEY env vars are set
                # This part might need adjustment based on how secrets are exposed in the deployment env
                # In Streamlit Cloud secrets are typically accessed via st.secrets
                account_id = st.secrets["EE_ACCOUNT"] if "EE_ACCOUNT" in st.secrets else os.environ.get("EE_ACCOUNT")
                private_key_data = st.secrets["EE_PRIVATE_KEY"] if "EE_PRIVATE_KEY" in st.secrets else os.environ.get("EE_PRIVATE_KEY")

                if not account_id or not private_key_data:
                     raise ValueError("EE_ACCOUNT or EE_PRIVATE_KEY not found in secrets or environment variables.")

                # Need to write the private key data to a temporary file or use a direct method if GEE supports it
                # Writing to a temporary file is safer than hardcoding/exposing directly in memory for some GEE methods
                # A more robust approach would be using gee.auth.ServiceAccountCredentials.from_service_account_info
                # if available, but that requires the info in a dictionary format.
                # For simplicity, let's assume the file method is preferred or required by the current GEE library version.
                # THIS IS A SIMPLIFIED EXAMPLE - Secure handling of private keys in deployment is crucial.
                # A better way in Streamlit Cloud: save the JSON content in a single secret and load it.
                # Example: st.secrets["gee_auth_json"] containing the full JSON as a string.
                if "gee_auth_json" in st.secrets:
                    auth_info = json.loads(st.secrets["gee_auth_json"])
                    credentials = ee.ServiceAccountCredentials(auth_info['client_email'], None, private_key_id=auth_info['private_key_id'], private_key=auth_info['private_key'], token_uri=auth_info['token_uri'])
                    print("GEE Initialized Successfully using Streamlit Secrets JSON.")
                else:
                    # Fallback if separate EE_ACCOUNT and EE_PRIVATE_KEY are used (less common)
                    st.error("❌ Secret 'gee_auth_json' not found. Please configure GEE credentials using the full JSON in a single secret.")
                    st.stop()
                    # This path is less likely to work directly with ServiceAccountCredentials(None, key_file)
                    # If using EE_ACCOUNT and EE_PRIVATE_KEY env vars, you might need to configure GEE differently.
                    # ee.Authenticate() or similar interactive auth might be needed if service account file isn't used.
                    # The current code relies on key_file or equivalent from secrets.
                    # For a production app on Streamlit Cloud, using a single JSON secret is the recommended way.
                    # credentials = ee.ServiceAccountCredentials(account_id, private_key_data) # This line is illustrative, might not work directly

            except Exception as e:
                 st.error(f"خطا در دریافت اطلاعات Service Account از Secrets یا Environment Variables: {e}")
                 st.info("لطفاً از تنظیم صحیح Secrets یا Environment Variables برای Google Earth Engine اطمینان حاصل کنید.")
                 st.stop()


        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account یا تنظیمات Secrets/Environment Variables و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.error(traceback.format_exc())
        st.stop()

# --- Load Farm Data from GeoJSON ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data_from_geojson(geojson_path=FARM_GEOJSON_PATH):
    """Loads farm data from the specified GeoJSON file."""
    try:
        # Attempt to load from local path first
        if os.path.exists(geojson_path):
            with open(geojson_path, 'r', encoding='utf-8') as f:
                gj = json.load(f)
            print(f"Loaded GeoJSON from local path: {geojson_path}")
        else:
            # Fallback to fetching from a URL if specified (e.g., GitHub raw file)
            # Replace with your actual raw file URL if hosting elsewhere
            github_raw_url = f'https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/{geojson_path}'
            try:
                response = requests.get(github_raw_url)
                response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
                gj = response.json()
                print(f"Loaded GeoJSON from URL: {github_raw_url}")
            except requests.exceptions.RequestException as e:
                 st.error(f"❌ فایل '{geojson_path}' در مسیر محلی یا از URL گیت‌هاب '{github_raw_url}' یافت نشد یا قابل دسترسی نیست: {e}")
                 st.stop()
            except json.JSONDecodeError:
                 st.error(f"❌ فایل '{geojson_path}' از URL گیت‌هاب یک فایل GeoJSON معتبر نیست.")
                 st.stop()


        features = gj['features']
        # Extract properties and geometry
        records = []
        for feat in features:
            props = feat['properties']
            geom = feat['geometry']
            # For polygons, calculate centroid for display/analysis
            centroid_lon, centroid_lat = None, None
            if geom and geom['type'] == 'Polygon' and geom['coordinates']:
                try:
                    # Use ee.Geometry to calculate centroid - more robust
                    ee_geom = ee.Geometry(geom)
                    centroid = ee_geom.centroid(maxError=1).getInfo()['coordinates'] # Use a small maxError
                    centroid_lon, centroid_lat = centroid[0], centroid[1]
                except ee.EEException as e:
                    print(f"Warning: Could not calculate centroid for a polygon: {e}")
                    # Fallback to simple average if GEE centroid calculation fails
                    try:
                        coords = geom['coordinates'][0] # Assuming outer ring
                        lons = [pt[0] for pt in coords]
                        lats = [pt[1] for pt in coords]
                        centroid_lon = sum(lons) / len(lons) if lons else None
                        centroid_lat = sum(lats) / len(lats) if lats else None
                    except Exception as avg_e:
                        print(f"Warning: Simple average centroid calculation failed: {avg_e}")
                except Exception as general_e:
                     print(f"Warning: General error calculating centroid: {general_e}")

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
        required_cols = ['مزرعه', 'روز']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ فایل GeoJSON باید شامل ستون‌های ضروری باشد: {', '.join(required_cols)}")
            st.stop()
        # Ensure centroid columns exist even if initially None
        if 'centroid_lon' not in df.columns:
             df['centroid_lon'] = None
        if 'centroid_lat' not in df.columns:
             df['centroid_lat'] = None

        # Drop rows where essential data for processing is missing
        initial_count = len(df)
        df = df.dropna(subset=['مزرعه', 'centroid_lon', 'centroid_lat', 'روز'])
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            st.warning(f"⚠️ {dropped_count} رکورد به دلیل مقادیر نامعتبر یا خالی در نام مزرعه، مختصات یا روز حذف شدند.")

        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون نام مزرعه، مختصات یا روز).")
            st.stop()

        df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        # Handle potential non-string types in 'گروه' and 'واریته' before strip
        df['گروه'] = df.get('گروه', pd.Series()).astype(str).str.strip()
        df['واریته'] = df.get('واریته', pd.Series()).astype(str).str.strip()


        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت از GeoJSON بارگذاری شد.")
        return df
    except FileNotFoundError:
        st.error(f"❌ فایل '{geojson_path}' یافت نشد. لطفاً فایل GeoJSON داده‌های مزارع را در مسیر صحیح قرار دهید.")
        st.stop()
        return pd.DataFrame() # Return empty DataFrame on error
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل GeoJSON: {e}")
        st.error(traceback.format_exc())
        st.stop()
        return pd.DataFrame() # Return empty DataFrame on error


# --- Load Analysis Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های محاسبات...")
def load_analysis_data(csv_path=ANALYSIS_CSV_PATH):
    """Loads and preprocesses data from the analysis CSV file."""
    try:
        # Attempt to load from local path first
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            print(f"Loaded Analysis CSV from local path: {csv_path}")
        else:
             # Fallback to fetching from a URL (e.g., GitHub raw file)
             github_raw_url = f'https://raw.githubusercontent.com/esmaeilkiani13877/MonitoringSugarcane-13/main/{csv_path}'
             try:
                 response = requests.get(github_raw_url)
                 response.raise_for_status()
                 lines = response.text.splitlines()
                 print(f"Loaded Analysis CSV from URL: {github_raw_url}")
             except requests.exceptions.RequestException as e:
                 st.error(f"❌ فایل '{csv_path}' در مسیر محلی یا از URL گیت‌هاب '{github_raw_url}' یافت نشد یا قابل دسترسی نیست: {e}")
                 st.stop()
                 return None, None


        # Find the headers and split points
        headers_indices = [i for i, line in enumerate(lines) if 'اداره,سن,' in line or 'تولید,سن,' in line]
        if len(headers_indices) < 1: # Must find at least one header
            st.error(f"❌ ساختار فایل '{csv_path}' قابل شناسایی نیست. هدرهای مورد انتظار ('اداره,سن,' یا 'تولید,سن,') یافت نشد.")
            st.stop()
            return None, None

        section1_start = headers_indices[0] + 1
        section2_start = None
        if len(headers_indices) > 1:
            section2_start = headers_indices[1] + 1

        # Read the first section (Area)
        # Determine nrows by looking for the next header or 'Grand Total' or end of file
        end_row_area = len(lines)
        if section2_start:
            end_row_area = section2_start - 2 # Stop before the next header line
        else:
             # If no second section, look for 'Grand Total' or a mostly empty line after section1_start
             for i in range(section1_start, len(lines)):
                 if "Grand Total" in lines[i] or len(lines[i].strip()) < 5:
                     end_row_area = i
                     break

        nrows_area = (end_row_area - section1_start) if end_row_area > section1_start else 0
        df_area = None
        if nrows_area > 0:
             df_area = pd.read_csv(BytesIO("\n".join(lines[headers_indices[0]:end_row_area]).encode('utf-8')), encoding='utf-8')


        # Read the second section (Production) if found
        df_prod = None
        if section2_start:
            # Find the end of the second section (look for 'Grand Total' or end of file)
            end_row_prod = len(lines)
            for i in range(section2_start, len(lines)):
                if "Grand Total" in lines[i] or len(lines[i].strip()) < 5:
                    end_row_prod = i
                    break
            nrows_prod = (end_row_prod - section2_start) if end_row_prod > section2_start else 0
            if nrows_prod > 0:
                 df_prod = pd.read_csv(BytesIO("\n".join(lines[headers_indices[1]:end_row_prod]).encode('utf-8')), encoding='utf-8')


        # --- Preprocessing Function ---
        def preprocess_df(df, section_name):
            if df is None or df.empty:
                return None
            # Ensure 'اداره' is the first column if it got misplaced or is unnamed
            if df.columns.tolist() and 'اداره' not in df.columns:
                df.rename(columns={df.columns[0]: 'اداره'}, inplace=True)
                # Clean column names (remove leading/trailing spaces, potential BOM)
                df.columns = df.columns.str.strip()

            # Check for required columns after potential renaming
            if not all(col in df.columns for col in ['اداره', 'سن']):
                 st.warning(f"⚠️ ستون های ضروری 'اداره' یا 'سن' در بخش '{section_name}' یافت نشد.")
                 return None

            # Forward fill 'اداره' to fill down merged cells
            df['اداره'] = df['اداره'].ffill()

            # Filter out 'total' and 'Grand Total' rows in 'سن' and 'اداره' columns
            df = df[~df['سن'].astype(str).str.contains('total', case=False, na=False)]
            # Also filter rows in 'اداره' that contain 'total' or 'دهخدا' (case-insensitive)
            df = df[~df['اداره'].astype(str).str.contains('total|دهخدا', case=False, na=False)]

            # Remove rows where 'اداره' is NaN after ffill (first rows before a number)
            df = df.dropna(subset=['اداره'])

             # Convert 'اداره' to integer where possible, coercing errors
            df['اداره'] = pd.to_numeric(df['اداره'], errors='coerce').astype('Int64') # Use nullable integer type
            df = df.dropna(subset=['اداره']) # Drop if conversion resulted in NaN

            # Convert numeric columns, coerce errors to NaN
            # Exclude 'اداره' and 'سن' and any potential 'درصد' or 'Grand Total' columns that survived
            value_cols = [col for col in df.columns if col not in ['اداره', 'سن', 'درصد', 'Grand Total']]
            for col in value_cols:
                # Attempt to convert to float, coercing errors
                df[col] = pd.to_numeric(df[col], errors='coerce')

            # Drop columns that are mostly NaN after conversion (e.g., text columns mistaken as value cols)
            # Adjust threshold based on expected data structure
            df = df.dropna(axis=1, thresh=len(df)*0.5) # Drop columns with more than 50% NaNs

            # Drop Grand Total and درصد columns if they exist and weren't dropped by NA threshold
            df = df.drop(columns=['Grand Total', 'درصد'], errors='ignore')

            # Set multi-index for easier access
            if 'اداره' in df.columns and 'سن' in df.columns:
                try:
                    df = df.set_index(['اداره', 'سن'])
                except ValueError as e:
                     st.warning(f"⚠️ خطای تنظیم ایندکس چندگانه در بخش '{section_name}': {e}. ادامه بدون ایندکس.")
                     # If setting index fails (e.g., duplicate index combinations), return without index
            else:
                 st.warning(f"⚠️ ستون های 'اداره' یا 'سن' برای تنظیم ایندکس چندگانه در بخش '{section_name}' یافت نشد.")


            return df

        df_area_processed = preprocess_df(df_area, "مساحت")
        df_prod_processed = preprocess_df(df_prod, "تولید")

        if df_area_processed is not None or df_prod_processed is not None:
             st.success(f"✅ داده‌های محاسبات با موفقیت بارگذاری و پردازش شد.")
        else:
             st.warning("⚠️ هیچ داده معتبری از فایل محاسبات بارگذاری یا پردازش نشد.")

        return df_area_processed, df_prod_processed

    except FileNotFoundError:
        st.error(f"❌ فایل '{csv_path}' یافت نشد. لطفاً فایل CSV داده‌های محاسبات را در مسیر صحیح قرار دهید.")
        return None, None
    except Exception as e:
        st.error(f"❌ خطا در بارگذاری یا پردازش فایل محاسبات CSV: {e}")
        st.error(traceback.format_exc())
        return None, None


# Initialize GEE and Load Data
if initialize_gee():
    farm_data_df = load_farm_data_from_geojson()
    # Load Analysis Data - Load this regardless of selected farm/day
    analysis_area_df, analysis_prod_df = load_analysis_data()
else:
    st.stop() # Stop if GEE initialization failed


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
if not farm_data_df.empty:
    available_days = sorted(farm_data_df['روز'].unique())
    if not available_days:
         st.sidebar.warning("هیچ روز هفته‌ای در داده‌های مزارع یافت نشد.")
         selected_day = None
    else:
        selected_day = st.sidebar.selectbox(
            "📅 روز هفته را انتخاب کنید:",
            options=available_days,
            index=0, # Default to the first day
            help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
        )
else:
     st.sidebar.warning("داده مزارع برای فیلتر روز هفته در دسترس نیست.")
     selected_day = None


# --- Filter Data Based on Selected Day ---
filtered_farms_df = pd.DataFrame()
if selected_day:
    filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد. لطفاً روز دیگری را انتخاب کنید یا داده‌های مزارع را بررسی کنید.")
    # Prevent further processing if no farms
    selected_farm_name = "همه مزارع" # Default selection
    available_farms = []
else:
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
    "LAI": "شاخص سطح برگ (تخمینی)",
    "MSI": "شاخص تنش رطوبتی",
    "CVI": "شاخص کلروفیل (تخمینی)",
    "SAVI": "شاخص پوشش گیاهی تعدیل شده با خاک",
}
selected_index = st.sidebar.selectbox(
    "📈 شاخص مورد نظر برای نمایش روی نقشه و رتبه‌بندی:",
    options=list(index_options.keys()),
    format_func=lambda x: f"{x} ({index_options[x]})",
    index=0 # Default to NDVI
)

# --- Date Range Calculation ---
today = datetime.date.today()
# Find the most recent date corresponding to the selected day of the week
# Map Persian day names to Python's weekday() (Monday=0, Sunday=6)
persian_to_weekday = {
    "شنبه": 5,
    "یکشنبه": 6,
    "دوشنبه": 0,
    "سه شنبه": 1,
    "چهارشنبه": 2,
    "پنجشنبه": 3,
    "جمعه": 4,
}

start_date_current_str = None
end_date_current_str = None
start_date_previous_str = None
end_date_previous_str = None

if selected_day:
    try:
        target_weekday = persian_to_weekday[selected_day.strip()] # Ensure no leading/trailing spaces
        today_weekday = today.weekday() # Monday is 0, Sunday is 6

        # Calculate days difference to get to the most recent selected day
        days_ago = (today_weekday - target_weekday + 7) % 7
        # If today is the target day, days_ago is 0. If the target day was yesterday, days_ago is 1, etc.

        end_date_current = today - datetime.timedelta(days=days_ago)

        # Ensure the current week starts correctly based on the calculated end date
        start_date_current = end_date_current - datetime.timedelta(days=6)

        end_date_previous = start_date_current - datetime.timedelta(days=1)
        start_date_previous = end_date_previous - datetime.timedelta(days=6)

        # Convert to strings for GEE
        start_date_current_str = start_date_current.strftime('%Y-%m-%d')
        end_date_current_str = end_date_current.strftime('%Y-%m-%d')
        start_date_previous_str = start_date_previous.strftime('%Y-%m-%d')
        end_date_previous_str = end_date_previous.strftime('%Y-%m-%d')

        st.sidebar.info(f"**بازه زمانی فعلی:** {start_date_current_str} تا {end_date_current_str}")
        st.sidebar.info(f"**بازه زمانی قبلی:** {start_date_previous_str} تا {end_date_previous_str}")

    except KeyError:
        st.sidebar.error(f"نام روز هفته '{selected_day}' قابل شناسایی نیست.")
        # selected_day = None # Reset selected_day to prevent further errors
    except Exception as e:
        st.sidebar.error(f"خطا در محاسبه بازه زمانی: {e}")
        st.error(traceback.format_exc())
        # selected_day = None # Reset selected_day to prevent further errors


# ==============================================================================
# Google Earth Engine Functions
# ==============================================================================

# --- Cloud Masking Function for Sentinel-2 ---
def maskS2clouds(image):
    """Masks clouds in a Sentinel-2 SR image using the QA band and SCL band."""
    qa = image.select('QA60')
    # Bits 10 and 11 are clouds and cirrus, respectively.
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    # Both flags should be set to zero, indicating clear conditions.
    mask_qa = qa.bitwiseAnd(cloudBitMask).eq(0).And(
             qa.bitwiseAnd(cirrusBitMask).eq(0))

    # SCL (Scene Classification Layer) band - more detailed masking
    scl = image.select('SCL')
    # Classes to mask out:
    # 3 = Cloud medium probability
    # 8 = Cloud high probability
    # 9 = Cirrus
    # 10 = Snow/Ice (unless relevant to crop) - Masking for sugarcane
    # 11 = Cloud shadow
    # Good classes to keep:
    # 4 = Vegetation
    # 5 = Not Vegetated
    # 6 = Water (could be field puddles or irrigation canals, maybe keep?) - Keep for now
    # 7 = Unclassified (potentially risky, maybe mask?) - Mask for safety
    # 1 = Saturated or Defective - Mask
    # 2 = Dark Area Pixels - Mask
    # 0 = No Data - Mask

    masked_classes = [0, 1, 2, 3, 7, 8, 9, 10, 11]
    mask_scl = scl.remap(masked_classes, [0] * len(masked_classes), 1) # Map bad classes to 0, others to 1

    # Combine masks
    final_mask = mask_qa.And(mask_scl)

    # Scale and offset factors for Sentinel-2 SR bands
    opticalBands = image.select('B.*').multiply(0.0001)

    # Apply the final mask and add scaled bands
    return image.addBands(opticalBands, None, True)\
                .updateMask(final_mask)


# --- Index Calculation Functions ---
def add_indices(image):
    """Calculates and adds various indices as bands to an image."""
    # Use scaled bands for calculations
    red = image.select('B4')
    nir = image.select('B8')
    blue = image.select('B2')
    green = image.select('B3')
    swir1 = image.select('B11')

    # NDVI: (NIR - Red) / (NIR + Red)
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    # EVI: 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1)
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': nir,
            'RED': red,
            'BLUE': blue
        }).rename('EVI')

    # NDMI (Normalized Difference Moisture Index): (NIR - SWIR1) / (NIR + SWIR1)
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')

    # SAVI (Soil-Adjusted Vegetation Index): ((NIR - Red) / (NIR + Red + L)) * (1 + L) | L=0.5
    savi = image.expression(
        '((NIR - RED) / (NIR + RED + L)) * (1 + L)',
        {
            'NIR': nir,
            'RED': red,
            'L': 0.5
        }
    ).rename('SAVI')

    # MSI (Moisture Stress Index): SWIR1 / NIR
    # Handle potential division by zero if NIR is 0
    nir_safe = nir.max(ee.Image(0.0001))
    msi = image.expression('SWIR1 / NIR', {
        'SWIR1': swir1,
        'NIR': nir_safe
    }).rename('MSI')

    # LAI (Leaf Area Index) - Simple estimation using EVI (Needs calibration for accuracy)
    # Using the formula: LAI = 3.618 * EVI - 0.118 (from literature, may need local calibration)
    lai = evi.multiply(3.618).subtract(0.118).rename('LAI').reproject(crs=image.projection().crs(), scale=10) # Reproject after calculation

    # CVI (Chlorophyll Vegetation Index) - (NIR / Green) * (Red / Green)
    # Handle potential division by zero if Green band is 0
    green_safe = green.max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
        'NIR': nir,
        'GREEN': green_safe,
        'RED': red
    }).rename('CVI').reproject(crs=image.projection().crs(), scale=10) # Reproject after calculation


    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, savi]) # Add calculated indices

# --- Function to get processed image for a date range and geometry ---
# Increased cache persistence to reduce re-computation
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist="앱") # Persist across app restarts
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given geometry and date range.
    _geometry: ee.Geometry (Point or Polygon)
    start_date, end_date: YYYY-MM-DD strings
    index_name: Name of the primary index band to return (e.g., 'NDVI')
    """
    if _geometry is None:
        return None, "هندسه معتبر برای پردازش GEE وجود ندارد."
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))

        # Check if any images are available after filtering
        # Use aggregate_array and getInfo() - more robust than size().getInfo() in some cases
        image_list = s2_sr_col.aggregate_array('system:index').getInfo()
        if not image_list:
             return None, f"هیچ تصویر Sentinel-2 بدون ابر در بازه {start_date} تا {end_date} یافت نشد."

        # Calculate indices for each image in the collection
        indexed_col = s2_sr_col.map(add_indices)

        # Create a median composite image
        median_image = indexed_col.median() # Use median to reduce noise/outliers

        # Select the desired index band
        # Ensure the selected index band exists
        available_bands = median_image.bandNames().getInfo()
        if index_name not in available_bands:
             return None, f"شاخص '{index_name}' در تصاویر پردازش شده یافت نشد. باندهای موجود: {', '.join(available_bands)}"

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

# --- Function to get time series data for a point ---
# Increased cache persistence
@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist="앱") # Persist across app restarts
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """Gets a time series of a specified index for a point geometry."""
    if _point_geom is None:
        return pd.DataFrame(columns=['date', index_name]), "هندسه نقطه‌ای معتبر برای سری زمانی وجود ندارد."
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))

        # Check if the index band exists in the first image (assuming consistency)
        # Or check after mapping add_indices
        # Example check (requires fetching info):
        # first_image = s2_sr_col.first()
        # if first_image:
        #      available_bands = first_image.bandNames().getInfo()
        #      if index_name not in available_bands:
        #          return pd.DataFrame(columns=['date', index_name]), f"شاخص '{index_name}' در تصاویر یافت نشد."

        def extract_value(image):
            # Ensure the index band is selected to avoid issues with missing bands
            # Use reduceRegion for points; scale should match sensor resolution (e.g., 10m for S2)
            # Check if the band exists before reducing
            bands = image.bandNames()
            if bands.contains(index_name):
                value = image.select(index_name).reduceRegion(
                    reducer=ee.Reducer.first(), # Use 'first' or 'mean' if point covers multiple pixels
                    geometry=_point_geom,
                    scale=10, # Scale in meters (10m for Sentinel-2 RGB/NIR)
                    bestEffort=True # Use bestEffort for potentially complex geometries
                ).get(index_name)
                # Return a feature with the value and the image date
                return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-dd'),
                    index_name: value
                })
            else:
                 return ee.Feature(None, {
                    'date': image.date().format('YYYY-MM-dd'),
                    index_name: None # Return None if band is missing for this image
                })


        # Map over the collection and remove features with null values for the index
        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))

        # Convert the FeatureCollection to a list of dictionaries
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی در بازه مشخص شده یافت نشد."

        # Convert to Pandas DataFrame
        ts_data = []
        for f in ts_info:
            properties = f['properties']
            # Ensure the index_name key exists before accessing
            if index_name in properties:
                 ts_data.append({'date': properties['date'], index_name: properties[index_name]})
            else:
                 # This case should ideally be caught by filter, but adding safety
                 print(f"Warning: Index '{index_name}' not found in properties for date {properties.get('date', 'N/A')}")


        ts_df = pd.DataFrame(ts_data)
        if ts_df.empty:
             return pd.DataFrame(columns=['date', index_name]), "داده معتبری برای سری زمانی یافت نشد (پس از حذف مقادیر خالی)."

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
# Function to get all relevant indices for a farm point for two periods
# ==============================================================================
# Increased cache persistence
@st.cache_data(show_spinner="در حال محاسبه شاخص‌های نیازسنجی...", persist="앱") # Persist across app restarts
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
        if _point_geom is None:
             return period_values, "هندسه نقطه‌ای معتبر وجود ندارد."
        try:
            # Get median composite image with all indices calculated
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_point_geom)
                         .filterDate(start, end)
                         .map(maskS2clouds)
                         .map(add_indices))

            # Check if any images are available
            image_list = s2_sr_col.aggregate_array('system:index').getInfo()
            if not image_list:
                return period_values, f"هیچ تصویری در بازه {start}-{end} یافت نشد"

            median_image = s2_sr_col.median()

            # Reduce region to get the mean value at the point for all desired indices
            # Select only the indices we want to get values for
            selected_bands = median_image.select(indices_to_get)
            mean_dict = selected_bands.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=_point_geom,
                scale=10,  # Scale in meters
                bestEffort=True # Use bestEffort
            ).getInfo()

            if mean_dict:
                for index in indices_to_get:
                    # Check if the index exists and is not None in the result
                    if index in mean_dict and mean_dict[index] is not None:
                         period_values[index] = mean_dict[index]
                    # else: print(f"Warning: {index} not found or is None in mean_dict for {start}-{end}")

            return period_values, None
        except ee.EEException as e:
            error_msg = f"خطای GEE در بازه {start}-{end}: {e}"
            st.error(error_msg) # Display GEE error
            return period_values, error_msg
        except Exception as e:
            error_msg = f"خطای ناشناخته در بازه {start}-{end}: {e}\n{traceback.format_exc()}"
            st.error(error_msg) # Display unknown error
            return period_values, error_msg

    # Get data for current period
    curr_values, err_curr = get_mean_values_for_period(start_curr, end_curr)
    if err_curr:
        results['error'] = f"خطا در بازه جاری: {err_curr}"
    results['NDVI_curr'] = curr_values['NDVI']
    results['NDMI_curr'] = curr_values['NDMI']
    results['EVI_curr'] = curr_values['EVI']
    results['SAVI_curr'] = curr_values['SAVI']


    # Get data for previous period
    prev_values, err_prev = get_mean_values_for_period(start_prev, end_prev)
    if err_prev:
        results['error'] = f"{results.get('error', '')}\nخطا در بازه قبلی: {err_prev}".strip() # Append errors with separator
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
    """Configures the Gemini API client using Streamlit secrets."""
    try:
        # Recommended: Use Streamlit secrets
        # In your .streamlit/secrets.toml file, add:
        # GEMINI_API_KEY = "YOUR_API_KEY"
        # Access like: st.secrets["GEMINI_API_KEY"]

        # --- WARNING: Hardcoding API keys is HIGHLY INSECURE! ---
        # api_key = "YOUR_HARDCODED_API_KEY" # <--- REMOVE THIS LINE IN PRODUCTION
        # ----------------------------------------------------

        # Attempt to get API key from Streamlit secrets first
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            # Fallback to environment variable (less recommended than secrets for Streamlit Cloud)
            api_key = os.environ.get("GEMINI_API_KEY")

        if not api_key:
             st.error("❌ کلید API جمینای (GEMINI_API_KEY) در فایل secrets.toml یا Environment Variables یافت نشد.")
             st.info("لطفاً فایل .streamlit/secrets.toml را ایجاد کرده و کلید خود را در آن قرار دهید یا Environment Variable مربوطه را تنظیم کنید.")
             return None

        genai.configure(api_key=api_key)

        # Define safety settings - Adjust as needed
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_NONE", # Or BLOCK_LOW_AND_ABOVE
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_NONE",
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_NONE",
            },
        ]

        # Use a suitable model, e.g., 'gemini-1.5-flash' for lower latency/cost
        model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
        print("Gemini Configured Successfully.")
        return model
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        st.error(traceback.format_exc())
        return None

# Function to get AI analysis for needs
# Increased cache persistence
@st.cache_data(show_spinner="در حال دریافت تحلیل هوش مصنوعی...", persist="앱") # Persist across app restarts
def get_ai_needs_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition related to needs."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    # Prepare data string - Handle None values gracefully
    data_str_parts = []
    if pd.notna(index_data.get('NDVI_curr')):
        data_str_parts.append(f"NDVI فعلی: {index_data['NDVI_curr']:.3f}")
        if pd.notna(index_data.get('NDVI_prev')):
            data_str_parts.append(f"(قبلی: {index_data['NDVI_prev']:.3f})")
    if pd.notna(index_data.get('NDMI_curr')):
         data_str_parts.append(f"\nNDMI فعلی: {index_data['NDMI_curr']:.3f}")
         if pd.notna(index_data.get('NDMI_prev')):
              data_str_parts.append(f"(قبلی: {index_data['NDMI_prev']:.3f})")
    if pd.notna(index_data.get('EVI_curr')):
         data_str_parts.append(f"\nEVI فعلی: {index_data['EVI_curr']:.3f}")
         if pd.notna(index_data.get('EVI_prev')):
              data_str_parts.append(f"(قبلی: {index_data['EVI_prev']:.3f})")
    if pd.notna(index_data.get('SAVI_curr')):
         data_str_parts.append(f"\nSAVI فعلی: {index_data['SAVI_curr']:.3f}")
         if pd.notna(index_data.get('SAVI_prev')):
              data_str_parts.append(f"(قبلی: {index_data['SAVI_prev']:.3f})")

    data_str = " ".join(data_str_parts) if data_str_parts else "داده‌های شاخص در دسترس نیست."

    prompt = f"""
    شما یک متخصص کشاورزی نیشکر هستید. لطفاً وضعیت مزرعه '{farm_name}' را بر اساس داده‌های شاخص ماهواره‌ای و توصیه‌های اولیه زیر تحلیل کنید و یک توضیح کوتاه، کاربردی و فارسی ارائه دهید. تمرکز تحلیل بر نیاز آبیاری و کودی بر اساس تغییرات شاخص‌ها باشد. توضیح شما باید به زبان ساده و قابل فهم برای کشاورز باشد.

    داده‌های شاخص:
    {data_str}

    توصیه‌های اولیه (بر اساس قوانین ساده):
    {', '.join(recommendations) if recommendations else 'هیچ توصیه‌ای بر اساس قوانین اولیه وجود ندارد.'}

    تحلیل شما:
    """

    try:
        response = _model.generate_content(prompt)
        # Accessing response text
        if hasattr(response, 'text'):
            return response.text
        else:
             st.warning("⚠️ پاسخ معتبری از Gemini دریافت نشد (شاید محتوای مسدود شده).")
             # Optionally inspect response.prompt_feedback or response.candidates
             return "پاسخ هوش مصنوعی در دسترس نیست."
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API هنگام تحلیل نیازها: {e}")
        st.warning(traceback.format_exc())
        return "خطا در دریافت تحلیل هوش مصنوعی."


# --- Function to get AI summary for the map (Optional, based on data) ---
# This function was mentioned in the description but not fully implemented.
# To implement this, you would need to feed the AI a summary of the ranking_df_sorted,
# perhaps focusing on the farms with 'تنش' status.
# For now, providing a placeholder.
@st.cache_data(show_spinner="در حال دریافت خلاصه هوش مصنوعی نقشه...", persist="앱")
def get_ai_map_summary(_model, ranking_df_sorted, selected_index, selected_day):
    """Generates AI summary for the overall map/ranking status."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    if ranking_df_sorted.empty:
        return "داده‌ای برای خلاصه‌سازی نقشه وجود ندارد."

    # Prepare a summary of the ranking data for the AI
    # Focus on problematic farms or overall trends
    negative_status_farms = ranking_df_sorted[ranking_df_sorted['وضعیت'].astype(str).str.contains("تنش|کاهش|بدتر", case=False, na=False)]
    positive_status_farms = ranking_df_sorted[ranking_df_sorted['وضعیت'].astype(str).str.contains("بهبود|رشد مثبت", case=False, na=False)]

    summary_text = f"خلاصه وضعیت مزارع برای روز {selected_day} بر اساس شاخص {selected_index}:\n"
    summary_text += f"تعداد کل مزارع بررسی شده: {len(ranking_df_sorted)}\n"
    summary_text += f"تعداد مزارع با وضعیت 'تنش/کاهش': {len(negative_status_farms)}\n"
    summary_text += f"تعداد مزارع با وضعیت 'بهبود/رشد مثبت': {len(positive_status_farms)}\n"
    summary_text += f"تعداد مزارع با وضعیت 'ثابت': {len(ranking_df_sorted) - len(negative_status_farms) - len(positive_status_farms)}\n\n"

    if not negative_status_farms.empty:
        summary_text += "مزارع با بیشترین تنش/کاهش (بر اساس رتبه):\n"
        # Get top 5 problematic farms
        top_problem_farms = negative_status_farms.head(5)
        for idx, row in top_problem_farms.iterrows():
            summary_text += f"- مزرعه {row['مزرعه']}: وضعیت {row['وضعیت'].replace('<span class="status-badge status-negative">', '').replace('</span>', '')}, شاخص هفته جاری: {row[f'{selected_index} (هفته جاری)']}, تغییر: {row['تغییر']}\n"

    if not positive_status_farms.empty and len(positive_status_farms) > 0:
         summary_text += "\nمزارعی با بهترین بهبود/رشد (بر اساس رتبه):\n"
         # Get top 5 improving farms
         top_improving_farms = positive_status_farms.head(5) # Head after sorting by index value if ascending
         if selected_index in ['MSI']: # For MSI, better is lower value, so last after ascending sort
              top_improving_farms = positive_status_farms.tail(5) # Tail after sorting by index value if ascending

         for idx, row in top_improving_farms.iterrows():
              summary_text += f"- مزرعه {row['مزرعه']}: وضعیت {row['وضعیت'].replace('<span class="status-badge status-positive">', '').replace('</span>', '')}, شاخص هفته جاری: {row[f'{selected_index} (هفته جاری)']}, تغییر: {row['تغییر']}\n"


    prompt = f"""
    شما یک تحلیلگر کشاورزی هستید. لطفاً یک خلاصه فارسی کوتاه و مفید از وضعیت کلی مزارع بر اساس داده‌های رتبه‌بندی زیر ارائه دهید. به تعداد مزارع در هر وضعیت (تنش، بهبود، ثابت) و در صورت وجود، به مزارع با بیشترین تنش اشاره کنید.

    داده‌های خلاصه رتبه‌بندی:
    {summary_text}

    خلاصه تحلیل شما:
    """
    try:
        response = _model.generate_content(prompt)
        if hasattr(response, 'text'):
            return response.text
        else:
             st.warning("⚠️ پاسخ معتبری از Gemini برای خلاصه نقشه دریافت نشد.")
             return "خلاصه هوش مصنوعی در دسترس نیست."
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API هنگام خلاصه‌سازی نقشه: {e}")
        st.warning(traceback.format_exc())
        return "خطا در دریافت خلاصه هوش مصنوعی نقشه."


# ==============================================================================
# Helper Function for Status Determination
# ==============================================================================

def determine_status(row, index_name):
    """Determines the status based on change in index value."""
    # Use pd.notna for robust NaN check
    if pd.notna(row.get('تغییر')) and pd.notna(row.get(f'{index_name} (هفته جاری)')) and pd.notna(row.get(f'{index_name} (هفته قبل)')):
        change_val = row['تغییر']
        # Threshold for significant change - Can be adjusted
        threshold = 0.03 # Lowering threshold slightly for potentially more sensitive detection

        current_val = row[f'{index_name} (هفته جاری)']
        previous_val = row[f'{index_name} (هفته قبل)']

        # For indices where higher is better (NDVI, EVI, LAI, CVI, NDMI)
        # Consider the absolute values too, not just change, maybe relative change
        if index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI']:
            # Check for significant positive or negative change
            if change_val > threshold:
                return "رشد مثبت / بهبود"
            elif change_val < -threshold:
                return "تنش / کاهش"
            else:
                # If change is within threshold, check if values are consistently low/high
                # This part is more complex and depends on what "fixed" means for different indices
                # For simplicity, let's stick to change for now unless specific fixed thresholds are defined
                 return "ثابت"

        # For indices where lower is better (MSI)
        elif index_name in ['MSI']:
            # Negative change means improvement (less stress)
            if change_val < -threshold:
                return "بهبود"
            # Positive change means deterioration (more stress)
            elif change_val > threshold:
                return "تنش / بدتر شدن"
            else:
                return "ثابت"
        else:
            # Default case if index type is unknown or not handled
            return "نامشخص"
    elif pd.notna(row.get(f'{index_name} (هفته جاری)')) and pd.isna(row.get(f'{index_name} (هفته قبل)')):
         return "بدون داده هفته قبل"
    elif pd.isna(row.get(f'{index_name} (هفته جاری)')) and pd.notna(row.get(f'{index_name} (هفته قبل)')):
         return "بدون داده هفته جاری"
    else:
        return "بدون داده"


# ==============================================================================
# Main Application Layout (Using Tabs)
# ==============================================================================

# Configure Gemini Model at the start
gemini_model = configure_gemini()

# Define tabs
tab1, tab2, tab3 = st.tabs(["📊 پایش مزارع (نقشه و رتبه‌بندی)", "📈 تحلیل داده‌های محاسبات", "💧 تحلیل نیاز آبیاری و کوددهی"])

# --- Tab 1: Map and Ranking ---
with tab1:
    st.header("📊 پایش مزارع (نقشه و رتبه‌بندی)")

    if filtered_farms_df.empty:
        st.warning("⚠️ هیچ مزرعه‌ای برای روز و فیلترهای انتخابی یافت نشد. نمایش نقشه و رتبه‌بندی امکان‌پذیر نیست.")
    else:
        # --- Get Selected Farm Geometry and Details ---
        selected_farm_details = None
        selected_farm_geom = None
        center_lat = INITIAL_LAT
        center_lon = INITIAL_LON
        zoom_level = INITIAL_ZOOM

        if selected_farm_name == "همه مزارع":
            # Use the bounding box of all filtered farms for the map view
            min_lon, min_lat = filtered_farms_df['centroid_lon'].min(), filtered_farms_df['centroid_lat'].min()
            max_lon, max_lat = filtered_farms_df['centroid_lon'].max(), filtered_farms_df['centroid_lat'].max()
            # Create a bounding box geometry
            try:
                 # Ensure coordinates are valid before creating ee.Geometry
                 if pd.notna(min_lon) and pd.notna(min_lat) and pd.notna(max_lon) and pd.notna(max_lat):
                     selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                 else:
                     st.warning("⚠️ مختصات معتبر برای ایجاد ناحیه مرزی همه مزارع یافت نشد.")
            except Exception as e:
                 st.warning(f"⚠️ خطا در ایجاد ناحیه مرزی GEE برای همه مزارع: {e}")
                 selected_farm_geom = None # Set to None if geometry creation fails

            st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
            # --- تعداد مزارع در این روز (کارت زیبا) ---
            st.markdown(modern_metric_card("تعداد مزارع در این روز", f"{len(filtered_farms_df):,}", icon="fa-leaf", color="#185a9d"), unsafe_allow_html=True)
            st.caption("تعداد کل مزارع ثبت شده برای روز انتخاب شده.")

            # --- نمودار سه بعدی متحرک درصد هر واریته در این روز ---
            # محاسبه درصد هر واریته در بین مزارع این روز
            if 'واریته' in filtered_farms_df.columns and not filtered_farms_df['واریته'].isna().all():
                # Filter out 'nan' strings if any survived
                variety_counts = filtered_farms_df[filtered_farms_df['واریته'].astype(str).str.lower() != 'nan']['واریته'].value_counts().sort_values(ascending=False)
                if not variety_counts.empty:
                     variety_percent = 100 * variety_counts / variety_counts.sum()
                     # ساخت دیتافریم برای نمودار
                     pie_df = pd.DataFrame({
                         'واریته': variety_percent.index,
                         'درصد': variety_percent.values
                     })
                     # نمودار سه بعدی متحرک (Pie 3D Animated)
                     fig_pie = go.Figure(
                         data=[go.Pie(
                             labels=pie_df['واریته'],
                             values=pie_df['درصد'],
                             hole=0.3,
                             pull=[0.08]*len(pie_df),
                             marker=dict(line=dict(color='#fff', width=2)),
                             textinfo='label+percent',
                             insidetextorientation='radial',
                             rotation=90,
                         )]
                     )
                     fig_pie.update_traces(textfont_size=18)
                     fig_pie.update_layout(
                         title=f"درصد واریته‌ها در مزارع روز {selected_day} (داینامیک)",
                         showlegend=True,
                         height=450,
                         margin=dict(l=20, r=20, t=60, b=20),
                         paper_bgcolor='rgba(0,0,0,0)',
                         plot_bgcolor='rgba(0,0,0,0)'
                     )
                     st.plotly_chart(fig_pie, use_container_width=True)
                     st.caption("درصد هر واریته از کل مزارع ثبت شده در این روز.")
                else:
                    st.info("داده واریته معتبری برای نمودار در این روز یافت نشد.")
            else:
                st.info("ستون واریته در داده‌های این روز وجود ندارد یا خالی است.")


        else:
            selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
            lat = selected_farm_details['centroid_lat']
            lon = selected_farm_details['centroid_lon']
            # Ensure coordinates are valid numbers before creating GEE Point
            if pd.notna(lat) and pd.notna(lon):
                selected_farm_geom = ee.Geometry.Point([lon, lat])
                center_lat = lat
                center_lon = lon
                zoom_level = 14 # Zoom closer for a single farm
            else:
                 st.warning(f"⚠️ مختصات معتبر برای مزرعه '{selected_farm_name}' یافت نشد.")
                 selected_farm_geom = None


            st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
            # Display farm details using modern cards
            details_cols = st.columns(3)
            with details_cols[0]:
                st.markdown(modern_metric_card("مساحت داشت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A", icon="fa-ruler-combined", color="#43cea2"), unsafe_allow_html=True)
                st.markdown(modern_metric_card("واریته", f"{selected_farm_details.get('واریته', 'N/A')}", icon="fa-seedling", color="#43cea2"), unsafe_allow_html=True)
            with details_cols[1]:
                st.markdown(modern_metric_card("گروه", f"{selected_farm_details.get('گروه', 'N/A')}", icon="fa-users", color="#43cea2"), unsafe_allow_html=True)
                st.markdown(modern_metric_card("سن", f"{selected_farm_details.get('سن', 'N/A')}", icon="fa-hourglass-half", color="#43cea2"), unsafe_allow_html=True)
            with details_cols[2]:
                st.markdown(modern_metric_card("مختصات", f"{lat:.5f}, {lon:.5f}" if pd.notna(lat) and pd.notna(lon) else "N/A", icon="fa-map-marker-alt", color="#43cea2"), unsafe_allow_html=True)


        # --- Map Display ---
        st.markdown("---")
        st.subheader("🗺️ نقشه وضعیت مزارع")

        # Define visualization parameters based on the selected index
        vis_params = {
            'NDVI': {'min': 0, 'max': 0.9, 'palette': ['red', 'yellow', 'green']},
            'EVI': {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']},
            'NDMI': {'min': -0.5, 'max': 0.5, 'palette': ['brown', 'white', 'blue']}, # Adjusted range
            'LAI': {'min': 0, 'max': 5, 'palette': ['white', 'lightgreen', 'darkgreen']}, # Adjusted max based on expected values
            'MSI': {'min': 0.5, 'max': 2, 'palette': ['blue', 'white', 'brown']}, # Lower values = more moisture, adjusted range
            'CVI': {'min': 0, 'max': 15, 'palette': ['yellow', 'lightgreen', 'darkgreen']}, # Adjusted max based on expected values
            'SAVI': {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']},
        }

        # Create a geemap Map instance
        m = geemap.Map(
            location=[center_lat, center_lon],
            zoom=zoom_level,
            add_google_map=False # Start clean
        )
        m.add_basemap("HYBRID") # Add Google Satellite Hybrid basemap

        # Get the processed image for the current week
        gee_image_current = None
        error_msg_current = None
        if selected_farm_geom and start_date_current_str and end_date_current_str:
            gee_image_current, error_msg_current = get_processed_image(
                selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
            )

        if gee_image_current:
            # Add the GEE layer to the map
            try:
                # Ensure vis_params has default if selected_index is not in the dict
                index_vis_params = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})
                m.addLayer(
                    gee_image_current,
                    index_vis_params,
                    f"{selected_index} ({start_date_current_str} تا {end_date_current_str})"
                )

                # Create a custom legend using folium
                # Simplified legend based on color gradient meaning
                legend_title = f"راهنمای شاخص {selected_index}"
                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI', 'SAVI']:
                    legend_text = '''
                    <p style="margin: 0;"><span style="color: red;">Low Value</span> / <span style="color: yellow;">Medium Value</span> / <span style="color: green;">High Value</span></p>
                    <p style="margin: 0; font-size: 0.8em;">(نشان‌دهنده وضعیت پوشش گیاهی/سلامت)</p>
                    '''
                elif selected_index in ['NDMI']:
                    legend_text = '''
                    <p style="margin: 0;"><span style="color: brown;">Low Value</span> / <span style="color: white;">Medium Value</span> / <span style="color: blue;">High Value</span></p>
                    <p style="margin: 0; font-size: 0.8em;">(نشان‌دهنده رطوبت)</p>
                    '''
                elif selected_index in ['MSI']: # Lower MSI is better (more moisture)
                     legend_text = '''
                    <p style="margin: 0;"><span style="color: blue;">Low Value</span> / <span style="color: white;">Medium Value</span> / <span style="color: brown;">High Value</span></p>
                    <p style="margin: 0; font-size: 0.8em;">(نشان‌دهنده تنش رطوبتی، پایین‌تر بهتر است)</p>
                    '''
                else:
                    legend_text = '''
                    <p style="margin: 0;">Custom Index Legend</p>
                    '''

                legend_html = f'''
                <div style="position: fixed; bottom: 50px; right: 10px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px; font-family: Vazirmatn, sans-serif;">
                    <p style="margin: 0;"><strong>{legend_title}</strong></p>
                    {legend_text}
                </div>
                '''
                # Add the custom legend to the map
                m.get_root().html.add_child(folium.Element(legend_html))

                # --- Add Farm Markers with Popups ---
                # This section needs to be updated to show relevant info including current/previous indices
                # It might require calculating indices for each farm point beforehand or fetching them here.
                # To show index values in popups, we need the results from calculate_weekly_indices.
                # Let's calculate ranking_df_map here if selected_farm_name is "همه مزارع"
                # If selected_farm_name is a single farm, we can use the details we already have or fetch its index value.

                # --- Calculate Ranking Data for Map Popups if "همه مزارع" ---
                ranking_df_map_popups = pd.DataFrame()
                if selected_farm_name == "همه مزارع" and start_date_current_str and end_date_current_str and start_date_previous_str and end_date_previous_str:
                     # Reuse calculate_weekly_indices for the map popups
                     # Note: This might recalculate if the cache key is different from the table's call
                     # To optimize, we could store the results of the first calculation.
                     # For simplicity now, let's call it, cache should help.
                     st.info("در حال آماده‌سازی اطلاعات مزارع برای نمایش روی نقشه...")
                     ranking_df_map_popups, popup_calculation_errors = calculate_weekly_indices(
                          filtered_farms_df,
                          selected_index,
                          start_date_current_str,
                          end_date_current_str,
                          start_date_previous_str,
                          end_date_previous_str
                     )
                     if popup_calculation_errors:
                         st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها برای پاپ‌آپ‌های نقشه رخ داد:")
                         for error in popup_calculation_errors[:5]: st.warning(f"- {error}") # Show first 5

                # Add markers for farms
                if selected_farm_name == "همه مزارع":
                     # Add markers for all filtered farms using data from ranking_df_map_popups
                     if not ranking_df_map_popups.empty:
                         # Merge with original farm data to get other properties like age/variety
                         map_data_with_indices = pd.merge(
                             filtered_farms_df,
                             ranking_df_map_popups,
                             on='مزرعه',
                             how='left' # Keep all farms from filtered_farms_df
                         )

                         for idx, farm in map_data_with_indices.iterrows():
                              if pd.notna(farm['centroid_lat']) and pd.notna(farm['centroid_lon']):
                                  popup_html = f"""
                                  <strong>مزرعه:</strong> {farm['مزرعه']}<br>
                                  <strong>گروه:</strong> {farm.get('گروه', 'N/A')}<br>
                                  <strong>سن:</strong> {farm.get('سن', 'N/A')}<br>
                                  <strong>واریته:</strong> {farm.get('واریته', 'N/A')}<br>
                                  ---<br>
                                  <strong>{selected_index} (هفته جاری):</strong> {farm.get(f'{selected_index} (هفته جاری)', 'N/A'):.3f} <br>
                                  <strong>{selected_index} (هفته قبل):</strong> {farm.get(f'{selected_index} (هفته قبل)', 'N/A'):.3f} <br>
                                  <strong>تغییر:</strong> {farm.get('تغییر', 'N/A'):.3f}
                                  """
                                  # Add status badge to popup if available
                                  # Need to determine status for each farm here based on change
                                  if pd.notna(farm.get('تغییر')):
                                       status_text = determine_status(farm, selected_index)
                                       popup_html += f"<br><strong>وضعیت:</strong> {status_text}" # Add plain text status for popup

                                  folium.Marker(
                                      location=[farm['centroid_lat'], farm['centroid_lon']],
                                      popup=folium.Popup(popup_html, max_width=300),
                                      tooltip=farm['مزرعه'],
                                      icon=folium.Icon(color='blue', icon='info-sign')
                                  ).add_to(m)
                         # Center on the bounding box of the filtered farms
                         if selected_farm_geom:
                              m.center_object(selected_farm_geom, zoom=zoom_level) # Center on the bounding box
                     else:
                         st.info("داده‌های شاخص برای نمایش اطلاعات در پاپ‌آپ‌های نقشه همه مزارع در دسترس نیست.")

                else:
                     # Add marker for the single selected farm
                     if selected_farm_details is not None and pd.notna(selected_farm_details['centroid_lat']) and pd.notna(selected_farm_details['centroid_lon']):
                         # For a single farm, fetch its specific index values if needed for the popup
                         # Or ideally, use the results from calculate_weekly_indices if already run for the table.
                         # Let's assume calculate_weekly_indices has been run or will be.
                         # Find the farm in the potential ranking_df results
                         farm_ranking_info = None
                         if 'ranking_df_sorted' in locals() and not ranking_df_sorted.empty:
                             # Use ranking_df_sorted from the table calculation if available
                             farm_ranking_info = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name].iloc[0] if selected_farm_name in ranking_df_sorted['مزرعه'].values else None
                         elif start_date_current_str and end_date_current_str and start_date_previous_str and end_date_previous_str:
                              # If ranking_df_sorted is not available, perform a quick calculation for this single farm
                              # This might be redundant if calculate_weekly_indices is called later for the table.
                              # To avoid redundancy, maybe only fetch index value for the popup here.
                              # Let's fetch values for the popup directly if not in ranking_df_sorted
                              point_geom_single = ee.Geometry.Point([selected_farm_details['centroid_lon'], selected_farm_details['centroid_lat']])
                              curr_val, err_curr = get_farm_needs_data(point_geom_single, start_date_current_str, end_date_current_str, start_date_previous_str, end_date_previous_str)
                              if not err_curr:
                                   farm_ranking_info = {
                                       'مزرعه': selected_farm_name,
                                       f'{selected_index} (هفته جاری)': curr_val.get(f'{selected_index}_curr'),
                                       f'{selected_index} (هفته قبل)': curr_val.get(f'{selected_index}_prev')
                                   }
                                   # Calculate change if values exist
                                   if pd.notna(farm_ranking_info[f'{selected_index} (هفته جاری)']) and pd.notna(farm_ranking_info[f'{selected_index} (هفته قبل)']):
                                        farm_ranking_info['تغییر'] = farm_ranking_info[f'{selected_index} (هفته جاری)'] - farm_ranking_info[f'{selected_index} (هفته قبل)']
                                   else:
                                        farm_ranking_info['تغییر'] = None
                                   # Determine status
                                   farm_ranking_info['وضعیت'] = determine_status(farm_ranking_info, selected_index) if pd.notna(farm_ranking_info.get('تغییر')) else "بدون داده"


                         popup_html = f"""
                         <strong>مزرعه:</strong> {selected_farm_name}<br>
                         <strong>گروه:</strong> {selected_farm_details.get('گروه', 'N/A')}<br>
                         <strong>سن:</strong> {selected_farm_details.get('سن', 'N/A')}<br>
                         <strong>واریته:</strong> {selected_farm_details.get('واریته', 'N/A')}<br>
                         ---<br>
                         """
                         if farm_ranking_info:
                              popup_html += f"<strong>{selected_index} (هفته جاری):</strong> {farm_ranking_info.get(f'{selected_index} (هفته جاری)', 'N/A'):.3f} <br>"
                              popup_html += f"<strong>{selected_index} (هفته قبل):</strong> {farm_ranking_info.get(f'{selected_index} (هفته قبل)', 'N/A'):.3f} <br>"
                              popup_html += f"<strong>تغییر:</strong> {farm_ranking_info.get('تغییر', 'N/A'):.3f} <br>"
                              popup_html += f"<strong>وضعیت:</strong> {farm_ranking_info.get('وضعیت', 'N/A')}" # Add plain text status for popup
                         else:
                              popup_html += f"<strong>{selected_index} (هفته جاری):</strong> N/A <br>"
                              popup_html += f"<strong>{selected_index} (هفته قبل):</strong> N/A <br>"
                              popup_html += f"<strong>تغییر:</strong> N/A <br>"
                              popup_html += f"<strong>وضعیت:</strong> بدون داده"


                         folium.Marker(
                             location=[lat, lon],
                             popup=folium.Popup(popup_html, max_width=300),
                             tooltip=selected_farm_name,
                             icon=folium.Icon(color='red', icon='star')
                         ).add_to(m)


                m.add_layer_control() # Add layer control to toggle base maps and layers

                # --- Add Age, Variety, Status Layers (Based on Description - NOT FULLY IMPLEMENTED YET) ---
                # The description mentions adding layers for Age, Variety, and Status based on ranking_df_map.
                # Implementing this requires converting the Pandas DataFrame (with calculated statuses)
                # into a GEE FeatureCollection and styling it for display on the map.
                # This is a significant development task and is not included in this fix.
                # Placeholder comment to acknowledge this missing feature as per the description.
                # if 'ranking_df_map' is calculated and available:
                #     try:
                #         # Convert ranking_df_map to GEE FeatureCollection
                #         # Define visualization and styling based on 'وضعیت', 'سن', 'واریته'
                #         # Add these as separate layers to the map (m.addLayer)
                #         pass # Placeholder for future implementation
                #     except Exception as layer_err:
                #         st.warning(f"⚠️ خطا در افزودن لایه‌های سن، واریته یا وضعیت به نقشه: {layer_err}")


            except Exception as map_err:
                st.error(f"خطا در افزودن لایه GEE به نقشه: {map_err}")
                st.error(traceback.format_exc())
        else:
            st.warning(f"تصویری برای نمایش شاخص {selected_index} روی نقشه در بازه فعلی یافت نشد. {error_msg_current}")


        # Display the map in Streamlit
        st_folium(m, width=None, height=500, use_container_width=True)
        st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها در سمت راست بالا برای تغییر نقشه پایه و لایه شاخص استفاده کنید.")
        st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


        # --- Time Series Chart ---
        st.markdown("---")
        st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
        elif selected_farm_geom and selected_farm_details is not None:
             # Check if the geometry type is Point by checking the stored property
             is_point = selected_farm_details.get('geometry_type') == 'Point'

             if is_point:
                 # Define a longer period for the time series chart (e.g., last 1 year)
                 timeseries_end_date = today.strftime('%Y-%m-%d')
                 timeseries_start_date = (today - datetime.timedelta(days=365)).strftime('%Y-%m-%d')

                 ts_df, ts_error = get_index_time_series(
                     selected_farm_geom,
                     selected_index,
                     start_date=timeseries_start_date,
                     end_date=timeseries_end_date
                 )

                 if ts_error:
                     st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
                 elif not ts_df.empty:
                     # Plotting with Plotly for better interactivity and date handling
                     fig_ts = px.line(ts_df, y=selected_index, title=f'روند زمانی شاخص {selected_index} برای مزرعه {selected_farm_name}')
                     fig_ts.update_layout(
                         xaxis_title="تاریخ",
                         yaxis_title=selected_index,
                         hovermode="x unified", # Show tooltip for nearest data point across all lines
                         margin=dict(l=20, r=20, t=40, b=20)
                     )
                     st.plotly_chart(fig_ts, use_container_width=True)
                     st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در یک سال گذشته (تصاویر ماهواره‌ای بدون ابر).")
                 else:
                     st.info(f"داده‌ای برای نمایش نمودار سری زمانی شاخص {selected_index} در بازه مشخص شده یافت نشد (احتمالاً به دلیل پوشش ابری).")
             else:
                 st.warning("نوع هندسه مزرعه برای نمودار سری زمانی پشتیبانی نمی‌شود (فقط مختصات نقطه‌ای).")
        else:
            st.info("لطفاً یک مزرعه معتبر با مختصات نقطه‌ای برای مشاهده نمودار سری زمانی انتخاب کنید.")


        # ==============================================================================
        # Ranking Table
        # ==============================================================================
        st.markdown("---")
        st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
        st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

        @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع جهت رتبه‌بندی...", persist="앱") # Increased cache persistence
        def calculate_weekly_indices(
            _farms_df, index_name, start_curr, end_curr, start_prev, end_prev
        ):
            """Calculates the average index value for the current and previous week for a list of farms."""
            results = []
            errors = []
            total_farms = len(_farms_df)
            # Use a placeholder to update the progress bar within the loop
            progress_placeholder = st.empty()


            for i, (idx, farm) in enumerate(_farms_df.iterrows()):
                farm_name = farm['مزرعه']
                lat = farm['centroid_lat']
                lon = farm['centroid_lon']

                if pd.isna(lat) or pd.isna(lon):
                    errors.append(f"مختصات نامعتبر برای مزرعه '{farm_name}'. نادیده گرفته شد.")
                    continue # Skip this farm

                point_geom = ee.Geometry.Point([lon, lat])

                # Use get_farm_needs_data which already fetches for two periods
                # Although it fetches more indices, caching helps.
                # A dedicated function might be slightly more efficient if only the selected index is needed.
                # Let's stick to get_farm_needs_data for simplicity and cache leverage.
                # Note: get_farm_needs_data gets NDVI, NDMI, EVI, SAVI. We only need the selected_index.
                # We can call get_mean_values_for_period twice here for just the selected index.

                def get_mean_value_single_index(start, end, index):
                     try:
                          image, error = get_processed_image(point_geom, start, end, index)
                          if image:
                              # Reduce region to get the mean value at the point
                              mean_dict = image.reduceRegion(
                                  reducer=ee.Reducer.mean(),
                                  geometry=point_geom,
                                  scale=10,  # Scale in meters
                                  bestEffort=True # Use bestEffort
                              ).getInfo()
                              # Return the value for the specific index, handle potential None or key error
                              return mean_dict.get(index) if mean_dict and index in mean_dict else None, None
                          else:
                              return None, error # Return the error from get_processed_image
                     except ee.EEException as e:
                          return None, f"GEE Error for {farm_name} ({start}-{end}): {e}"
                     except Exception as e:
                          return None, f"Unknown Error for {farm_name} ({start}-{end}): {e}"


                # Calculate for current week (only the selected index)
                current_val, err_curr = get_mean_value_single_index(start_curr, end_curr, index_name)
                if err_curr: errors.append(f"مزرعه '{farm_name}' (هفته جاری): {err_curr}")

                # Calculate for previous week (only the selected index)
                previous_val, err_prev = get_mean_value_single_index(start_prev, end_prev, index_name)
                if err_prev: errors.append(f"مزرعه '{farm_name}' (هفته قبل): {err_prev}")

                # Calculate change
                change = None
                # Use pd.notna for robust check of numeric values
                if pd.notna(current_val) and pd.notna(previous_val):
                    try:
                        change = current_val - previous_val
                    except TypeError: # Handle cases where values might not be numeric unexpectedly
                        change = None


                results.append({
                    'مزرعه': farm_name,
                    'گروه': farm.get('گروه', 'N/A'), # Use .get for safety
                    f'{index_name} (هفته جاری)': current_val,
                    f'{index_name} (هفته قبل)': previous_val,
                    'تغییر': change,
                    'سن': farm.get('سن', 'N/A'), # Add سن to results
                    'واریته': farm.get('واریته', 'N/A'), # Add واریته to results
                })

                # Update progress bar
                progress = (i + 1) / total_farms
                progress_placeholder.markdown(modern_progress_bar(progress), unsafe_allow_html=True)

            progress_placeholder.empty() # Remove progress bar after completion
            return pd.DataFrame(results), errors

        # Calculate and display the ranking table
        # Only run calculation if date ranges are valid
        ranking_df = pd.DataFrame()
        calculation_errors = []
        if start_date_current_str and end_date_current_str and start_date_previous_str and end_date_previous_str:
             ranking_df, calculation_errors = calculate_weekly_indices(
                 filtered_farms_df,
                 selected_index,
                 start_date_current_str,
                 end_date_current_str,
                 start_date_previous_str,
                 end_date_previous_str
             )
        else:
             st.warning("⚠️ بازه‌های زمانی معتبر برای محاسبه رتبه‌بندی در دسترس نیست.")


        # Display any errors that occurred during calculation
        if calculation_errors:
            st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها برای رتبه‌بندی رخ داد:")
            for error in calculation_errors[:10]: # Show first 10 errors
                st.warning(f"- {error}")
            if len(calculation_errors) > 10:
                st.warning(f"... و {len(calculation_errors) - 10} خطای دیگر.")


        if not ranking_df.empty:
            # Sort by the current week's index value
            # Sorting order depends on whether higher index means better (NDVI, EVI, LAI, CVI, NDMI) or worse (MSI)
            ascending_sort = selected_index == 'MSI' # True if MSI (lower is better), False otherwise

            # Add a temporary column for sorting to handle potential non-numeric values robustly
            # Fill non-numeric with a value that places them last (e.g., large number for ascending, small for descending)
            sort_col_name = f'{selected_index} (هفته جاری)'
            temp_sort_col = f'{sort_col_name}_sortable'

            if ascending_sort: # MSI: lower is better -> ascending
                 ranking_df[temp_sort_col] = pd.to_numeric(ranking_df[sort_col_name], errors='coerce').fillna(1e9) # Large number places NaNs last
            else: # Others: higher is better -> descending
                 ranking_df[temp_sort_col] = pd.to_numeric(ranking_df[sort_col_name], errors='coerce').fillna(-1e9) # Small number places NaNs last


            ranking_df_sorted = ranking_df.sort_values(
                by=temp_sort_col,
                ascending=ascending_sort,
            ).drop(columns=[temp_sort_col]).reset_index(drop=True)


            # Add rank number
            ranking_df_sorted.index = ranking_df_sorted.index + 1
            ranking_df_sorted.index.name = 'رتبه'

            # Apply the determine_status function using .apply
            ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(
                lambda row: determine_status(row, selected_index), axis=1
            )

            # Apply status badge HTML
            ranking_df_sorted['وضعیت_نمایش'] = ranking_df_sorted['وضعیت'].apply(lambda s: status_badge(s))

            # Format numbers for better readability
            cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
            for col in cols_to_format:
                if col in ranking_df_sorted.columns:
                     # Check if column exists before formatting and use pd.notna
                     ranking_df_sorted[col] = ranking_df_sorted[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

            # Select columns to display, including 'گروه', 'سن', 'واریته'
            display_columns = ['مزرعه', 'گروه', 'سن', 'واریته'] + cols_to_format + ['وضعیت_نمایش']
            # Ensure only existing columns are selected and in the correct order
            # Prioritize the order specified in display_columns
            final_display_columns = [col for col in display_columns if col in ranking_df_sorted.columns]

            # Rename the 'وضعیت_نمایش' column header for display
            ranking_df_display = ranking_df_sorted[final_display_columns].rename(columns={'وضعیت_نمایش': 'وضعیت'})


            # Display the table with color coding and selected columns
            st.write("<style>td {vertical-align: middle !important;}</style>", unsafe_allow_html=True)
            # Use to_html with escape=False because 'وضعیت_نمایش' already contains HTML
            st.write(ranking_df_display.to_html(escape=False, index=True), unsafe_allow_html=True)

            # Add a summary of farm statuses below the table
            st.subheader("📊 خلاصه وضعیت مزارع (بر اساس رتبه‌بندی)")

            # Calculate status counts from the raw 'وضعیت' column (not the HTML one)
            status_counts = ranking_df_sorted['وضعیت'].value_counts()

            # Dynamically find positive and negative status terms used
            positive_terms = [s for s in status_counts.index if "بهبود" in s or "رشد مثبت" in s]
            negative_terms = [s for s in status_counts.index if any(sub in s for sub in ["تنش", "کاهش", "بدتر"])]
            neutral_term = "ثابت"
            nodata_term = "بدون داده"

            col1, col2, col3, col4 = st.columns(4) # Added column for No Data

            with col1:
                pos_count = sum(status_counts.get(term, 0) for term in positive_terms)
                pos_label = "🟢 بهبود" if positive_terms else "🟢 بهبود" # Use generic label if specific not found
                st.metric(pos_label, pos_count)

            with col2:
                neutral_count = status_counts.get(neutral_term, 0)
                st.metric(f"⚪ {neutral_term}", neutral_count)

            with col3:
                neg_count = sum(status_counts.get(term, 0) for term in negative_terms)
                neg_label = "🔴 تنش" if negative_terms else "🔴 تنش" # Use generic label if specific not found
                st.metric(neg_label, neg_count)

            with col4:
                 nodata_count = status_counts.get(nodata_term, 0)
                 st.metric(f"🟡 {nodata_term}", nodata_count) # Use yellow for no data

            # Add explanation for statuses
            st.info(f"""
            **توضیحات وضعیت:**
            - **🟢 بهبود/رشد مثبت**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش شاخص‌هایی مانند NDVI یا کاهش شاخص‌هایی مانند MSI).
            - **⚪ ثابت**: مزارعی که تغییر معناداری در شاخص نداشته‌اند (درون آستانه تغییر).
            - **🔴 تنش/کاهش/بدتر شدن**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند (کاهش شاخص‌هایی مانند NDVI یا افزایش شاخص‌هایی مانند MSI).
            - **🟡 بدون داده**: مزارعی که به دلیل عدم دسترسی به تصاویر ماهواره‌ای بدون ابر در یک یا هر دو بازه زمانی، امکان محاسبه تغییرات وجود نداشته است.
            """)

            # Add AI summary for the ranking/map
            st.markdown("---")
            st.subheader("🤖 خلاصه هوش مصنوعی از وضعیت مزارع")
            if gemini_model:
                 # Call the AI map summary function
                 ai_map_summary = get_ai_map_summary(gemini_model, ranking_df_sorted, selected_index, selected_day)
                 st.markdown(ai_map_summary)
            else:
                 st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست.")


            # Add download button for the table
            # Provide the clean DataFrame for download, not the one with HTML badges
            ranking_df_clean = ranking_df_sorted.drop(columns=['وضعیت_نمایش'])
            # Ensure original 'وضعیت' column is included in clean data
            ranking_df_clean['وضعیت'] = ranking_df_sorted['وضعیت']

            csv_data = ranking_df_clean.to_csv(index=True).encode('utf-8')
            st.download_button(
                label="📥 دانلود جدول رتبه‌بندی (CSV)",
                data=csv_data,
                file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv',
                mime='text/csv',
            )
        else:
            st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس شاخص {selected_index} در این بازه زمانی یافت نشد (احتمالاً به دلیل عدم دسترسی به تصاویر ماهواره‌ای بدون ابر).")


    st.markdown("---")
    st.sidebar.markdown("---")
    st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")


# --- Tab 2: Analysis Data Visualization ---
with tab2:
    st.header("📈 تحلیل داده‌های فایل محاسبات")
    st.markdown("نمایش گرافیکی داده‌های مساحت و تولید به تفکیک اداره و سن از فایل بارگذاری شده.")

    if analysis_area_df is not None or analysis_prod_df is not None:

        # Get unique 'اداره' values from both dataframes if they exist
        available_edareh = []
        if analysis_area_df is not None and 'اداره' in analysis_area_df.index.names:
            available_edareh.extend(analysis_area_df.index.get_level_values('اداره').unique().tolist())
        if analysis_prod_df is not None and 'اداره' in analysis_prod_df.index.names:
            available_edareh.extend(analysis_prod_df.index.get_level_values('اداره').unique().tolist())

        # Ensure unique and sorted list
        available_edareh = sorted(list(set(available_edareh)))

        if not available_edareh:
            st.warning("⚠️ هیچ اداره‌ای برای نمایش در داده‌های تحلیلی یافت نشد. لطفاً ساختار فایل 'محاسبات 2.csv' را بررسی کنید.")
        else:
            selected_edareh = st.selectbox(
                "اداره مورد نظر را انتخاب کنید:",
                options=available_edareh,
                key='analysis_edareh_select' # Unique key for this widget
            )

            # --- Display Data for Selected Edareh ---
            st.subheader(f"داده‌های اداره: {selected_edareh}")

            col1, col2 = st.columns(2)

            # --- Area Data Visualization ---
            with col1:
                st.markdown("#### مساحت (هکتار)")
                # Check if analysis_area_df exists and the selected_edareh is in its index
                if analysis_area_df is not None and selected_edareh in analysis_area_df.index.get_level_values('اداره').unique():
                    try:
                        df_area_selected = analysis_area_df.loc[selected_edareh].copy()

                        # Prepare data for 3D surface plot
                        # X = سن, Y = واریته (ستون ها), Z = مقدار
                        # Ensure index 'سن' and columns (varieties) are suitable for plotting
                        ages = df_area_selected.index.tolist()
                        varieties = df_area_selected.columns.tolist()
                        z_data = df_area_selected.values

                        # Check if enough data points for a meaningful surface plot
                        # Requires at least 2 unique ages and 2 unique varieties (columns)
                        if len(ages) > 1 and len(varieties) > 1 and z_data.shape[0] > 1 and z_data.shape[1] > 1:
                             try:
                                 fig_3d_area = go.Figure(data=[go.Surface(z=z_data, x=ages, y=varieties, colorscale='Viridis')])
                                 fig_3d_area.update_layout(
                                     title=f'نمودار سطح مساحت - اداره {selected_edareh}',
                                     scene=dict(
                                         xaxis_title='سن',
                                         yaxis_title='واریته',
                                         zaxis_title='مساحت (هکتار)'),
                                     autosize=True, height=500)
                                 st.plotly_chart(fig_3d_area, use_container_width=True)
                                 st.caption("نمایش توزیع مساحت بر اساس سن و واریته در یک سطح سه بعدی.")
                             except Exception as e:
                                 st.error(f"❌ خطا در ایجاد نمودار Surface Plot مساحت: {e}")
                                 st.dataframe(df_area_selected) # Show table as fallback
                        else:
                             st.info("⚠️ داده کافی برای رسم نمودار Surface Plot مساحت وجود ندارد (نیاز به بیش از یک مقدار سن و یک واریته با داده).")
                             st.dataframe(df_area_selected) # Show table if not enough data for 3D


                        # Histogram of Area per Variety (Melted DataFrame)
                        # Ensure the DataFrame is reset_index correctly for melting if multi-indexed
                        if 'سن' in df_area_selected.index.names:
                             df_area_melt = df_area_selected.reset_index().melt(id_vars='سن', var_name='واریته', value_name='مساحت')
                        else:
                             # If index is not 'سن', assume it's a simple index or column that needs to be an ID var
                             # This case might need adjustment based on actual data structure if multi-index fails
                              st.warning("⚠️ ساختار داده مساحت برای هیستوگرام غیرمنتظره است.")
                              df_area_melt = pd.DataFrame() # Empty DataFrame to prevent error


                        df_area_melt = df_area_melt.dropna(subset=['مساحت', 'واریته', 'سن']) # Drop NA values for plotting
                        # Filter out potential non-numeric 'سن' if needed, though preprocess should handle this
                        df_area_melt = df_area_melt[pd.to_numeric(df_area_melt['سن'], errors='coerce').notna()]


                        if not df_area_melt.empty:
                            try:
                                fig_hist_area = px.histogram(df_area_melt, x='واریته', y='مساحت', color='سن',
                                                           title=f'هیستوگرام مساحت بر اساس واریته - اداره {selected_edareh}',
                                                           labels={'مساحت':'مجموع مساحت (هکتار)'})
                                st.plotly_chart(fig_hist_area, use_container_width=True)
                                st.caption("توزیع مساحت هر واریته به تفکیک سن.")
                            except Exception as e:
                                 st.error(f"❌ خطا در ایجاد نمودار هیستوگرام مساحت: {e}")
                                 st.dataframe(df_area_melt) # Show data as fallback
                        else:
                            st.info(f"⚠️ داده معتبری برای هیستوگرام مساحت در اداره {selected_edareh} یافت نشد.")

                    except KeyError:
                        st.error(f"❌ خطای دسترسی به داده اداره '{selected_edareh}' در داده مساحت.")
                    except Exception as e:
                         st.error(f"❌ خطای غیرمنتظره در پردازش داده مساحت برای اداره '{selected_edareh}': {e}")
                         st.error(traceback.format_exc())

                else:
                    st.info(f"⚠️ داده مساحت برای اداره {selected_edareh} یافت نشد یا بارگذاری نشده است.")

            # --- Production Data Visualization ---
            with col2:
                st.markdown("#### تولید (تن)")
                # Check if analysis_prod_df exists and the selected_edareh is in its index
                if analysis_prod_df is not None and selected_edareh in analysis_prod_df.index.get_level_values('اداره').unique():
                    try:
                        df_prod_selected = analysis_prod_df.loc[selected_edareh].copy()

                        # Prepare data for 3D surface plot (similar logic to area)
                        ages_prod = df_prod_selected.index.tolist()
                        varieties_prod = df_prod_selected.columns.tolist()
                        z_data_prod = df_prod_selected.values

                        if len(ages_prod) > 1 and len(varieties_prod) > 1 and z_data_prod.shape[0] > 1 and z_data_prod.shape[1] > 1:
                             try:
                                 fig_3d_prod = go.Figure(data=[go.Surface(z=z_data_prod, x=ages_prod, y=varieties_prod, colorscale='Plasma')])
                                 fig_3d_prod.update_layout(
                                     title=f'نمودار سطح تولید - اداره {selected_edareh}',
                                     scene=dict(
                                         xaxis_title='سن',
                                         yaxis_title='واریته',
                                         zaxis_title='تولید (تن)'),
                                     autosize=True, height=500)
                                 st.plotly_chart(fig_3d_prod, use_container_width=True)
                                 st.caption("نمایش توزیع تولید بر اساس سن و واریته در یک سطح سه بعدی.")
                             except Exception as e:
                                  st.error(f"❌ خطا در ایجاد نمودار Surface Plot تولید: {e}")
                                  st.dataframe(df_prod_selected) # Show table as fallback
                        else:
                             st.info("⚠️ داده کافی برای رسم نمودار Surface Plot تولید وجود ندارد (نیاز به بیش از یک مقدار سن و یک واریته با داده).")
                             st.dataframe(df_prod_selected) # Show table if not enough data for 3D


                        # Histogram of Production per Variety (Melted DataFrame)
                        if 'سن' in df_prod_selected.index.names:
                            df_prod_melt = df_prod_selected.reset_index().melt(id_vars='سن', var_name='واریته', value_name='تولید')
                        else:
                             st.warning("⚠️ ساختار داده تولید برای هیستوگرام غیرمنتظره است.")
                             df_prod_melt = pd.DataFrame() # Empty DataFrame

                        df_prod_melt = df_prod_melt.dropna(subset=['تولید', 'واریته', 'سن']) # Drop NA values for plotting
                        # Filter out potential non-numeric 'سن'
                        df_prod_melt = df_prod_melt[pd.to_numeric(df_prod_melt['سن'], errors='coerce').notna()]


                        if not df_prod_melt.empty:
                            try:
                                fig_hist_prod = px.histogram(df_prod_melt, x='واریته', y='تولید', color='سن',
                                                           title=f'هیستوگرام تولید بر اساس واریته - اداره {selected_edareh}',
                                                           labels={'تولید':'مجموع تولید (تن)'})
                                st.plotly_chart(fig_hist_prod, use_container_width=True)
                                st.caption("توزیع تولید هر واریته به تفکیک سن.")
                            except Exception as e:
                                 st.error(f"❌ خطا در ایجاد نمودار هیستوگرام تولید: {e}")
                                 st.dataframe(df_prod_melt) # Show data as fallback
                        else:
                             st.info(f"⚠️ داده معتبری برای هیستوگرام تولید در اداره {selected_edareh} یافت نشد.")

                    except KeyError:
                         st.error(f"❌ خطای دسترسی به داده اداره '{selected_edareh}' در داده تولید.")
                    except Exception as e:
                         st.error(f"❌ خطای غیرمنتظره در پردازش داده تولید برای اداره '{selected_edareh}': {e}")
                         st.error(traceback.format_exc())
                else:
                    st.info(f"⚠️ داده تولید برای اداره {selected_edareh} یافت نشد یا بارگذاری نشده است.")

    else:
        st.error("❌ خطا در بارگذاری یا پردازش داده‌های تحلیل از فایل 'محاسبات 2.csv'. لطفاً فایل را بررسی کنید.")


    st.markdown("---")
    st.sidebar.markdown("---")
    st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")


# --- Tab 3: Needs Analysis ---
with tab3:
    st.header("💧 تحلیل نیاز آبیاری و کوددهی")

    if selected_farm_name == "همه مزارع":
        st.info("⚠️ لطفاً یک مزرعه خاص را از پنل کناری (سمت چپ) انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif selected_farm_geom and selected_farm_details is not None:
        # Check if it's a point geometry by checking the stored property
        is_point = selected_farm_details.get('geometry_type') == 'Point'

        if not is_point:
            st.warning("⚠️ تحلیل نیازها فقط برای مزارع با مختصات نقطه‌ای (تک مزرعه) در دسترس است.")
        elif not start_date_current_str or not end_date_current_str or not start_date_previous_str or not end_date_previous_str:
             st.warning("⚠️ بازه‌های زمانی معتبر برای تحلیل نیازها در دسترس نیست. لطفاً روز هفته را انتخاب کنید.")
        else:
            st.subheader(f"تحلیل برای مزرعه: {selected_farm_name}")

            # Define thresholds (allow user adjustment)
            st.markdown("---")
            st.markdown("#### تنظیم آستانه‌ها برای تحلیل")
            st.write("این آستانه‌ها برای ارائه توصیه‌های اولیه بر اساس قوانین ساده استفاده می‌شوند.")

            # Use Streamlit number_input for potentially more precise control than slider
            ndmi_threshold = st.number_input(
                 "آستانه پایین NDMI برای هشدار نیاز آبیاری:",
                 min_value=-1.0, max_value=1.0, value=0.25, step=0.01,
                 format="%.2f",
                 help="اگر مقدار NDMI در هفته جاری کمتر یا مساوی این مقدار باشد، هشدار نیاز به آبیاری صادر می‌شود. (محدوده: [-1, 1])"
             )

            ndvi_drop_threshold_percent = st.number_input(
                 "آستانه افت NDVI برای بررسی نیاز کوددهی (%):",
                 min_value=0.0, max_value=100.0, value=5.0, step=0.5,
                 format="%.1f",
                 help="اگر مقدار NDVI در هفته جاری نسبت به هفته قبل بیش از این درصد کاهش یابد، هشدار نیاز به بررسی کوددهی صادر می‌شود."
             )


            # Get the required index data for the selected farm
            # Reuse get_farm_needs_data which fetches NDVI, NDMI, EVI, SAVI for two periods
            farm_needs_data = get_farm_needs_data(
                selected_farm_geom,
                start_date_current_str, end_date_current_str,
                start_date_previous_str, end_date_previous_str
            )

            st.markdown("---")
            st.markdown("#### نتایج شاخص‌ها")
            if farm_needs_data.get('error'): # Check if error key exists and is not None/empty
                st.error(f"❌ خطا در دریافت داده‌های شاخص برای تحلیل نیازها: {farm_needs_data['error']}")
            elif pd.isna(farm_needs_data.get('NDMI_curr')) and pd.isna(farm_needs_data.get('NDVI_curr')):
                st.warning("⚠️ داده‌های شاخص لازم (NDMI و NDVI) برای تحلیل در دوره فعلی یافت نشد. (ممکن است به دلیل پوشش ابری باشد).")
            else:
                # --- Display Current Indices ---
                st.markdown("**مقادیر شاخص‌ها (هفته جاری):**")
                idx_cols = st.columns(4)
                with idx_cols[0]:
                    display_val = f"{farm_needs_data['NDVI_curr']:.3f}" if pd.notna(farm_needs_data.get('NDVI_curr')) else "N/A"
                    st.metric("NDVI", display_val)
                with idx_cols[1]:
                    display_val = f"{farm_needs_data['NDMI_curr']:.3f}" if pd.notna(farm_needs_data.get('NDMI_curr')) else "N/A"
                    st.metric("NDMI", display_val)
                with idx_cols[2]:
                    display_val = f"{farm_needs_data.get('EVI_curr', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('EVI_curr')) else "N/A"
                    st.metric("EVI", display_val)
                with idx_cols[3]:
                    display_val = f"{farm_needs_data.get('SAVI_curr', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('SAVI_curr')) else "N/A"
                    st.metric("SAVI", display_val)


                st.markdown("**مقادیر شاخص‌ها (هفته قبل):**")
                idx_prev_cols = st.columns(4)
                with idx_prev_cols[0]:
                     display_val_prev = f"{farm_needs_data['NDVI_prev']:.3f}" if pd.notna(farm_needs_data.get('NDVI_prev')) else "N/A"
                     st.metric("NDVI (هفته قبل)", display_val_prev)
                with idx_prev_cols[1]:
                     display_val_prev = f"{farm_needs_data['NDMI_prev']:.3f}" if pd.notna(farm_needs_data.get('NDMI_prev')) else "N/A"
                     st.metric("NDMI (هفته قبل)", display_val_prev)
                with idx_prev_cols[2]:
                     display_val_prev = f"{farm_needs_data.get('EVI_prev', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('EVI_prev')) else "N/A"
                     st.metric("EVI (هفته قبل)", display_val_prev)
                with idx_prev_cols[3]:
                     display_val_prev = f"{farm_needs_data.get('SAVI_prev', 'N/A'):.3f}" if pd.notna(farm_needs_data.get('SAVI_prev')) else "N/A"
                     st.metric("SAVI (هفته قبل)", display_val_prev)


                # --- Generate Recommendations (Rule-Based) ---
                st.markdown("---")
                st.markdown("#### توصیه‌های اولیه (بر اساس آستانه‌ها)")
                recommendations = []

                # 1. Irrigation Check (based on current NDMI)
                if pd.notna(farm_needs_data.get('NDMI_curr')) and farm_needs_data['NDMI_curr'] <= ndmi_threshold:
                    recommendations.append(f"💧 نیاز به آبیاری (NDMI = {farm_needs_data['NDMI_curr']:.3f} <= آستانه {ndmi_threshold:.2f})")

                # 2. Fertilization Check (based on NDVI drop)
                # Ensure both current and previous NDVI are available and valid
                if pd.notna(farm_needs_data.get('NDVI_curr')) and pd.notna(farm_needs_data.get('NDVI_prev')):
                     # Avoid division by zero if previous NDVI is zero or close to zero
                     if farm_needs_data['NDVI_prev'] is not None and farm_needs_data['NDVI_prev'] > 0.01: # Check for small positive value
                          ndvi_change = farm_needs_data['NDVI_curr'] - farm_needs_data['NDVI_prev']
                          ndvi_change_percent = (ndvi_change / farm_needs_data['NDVI_prev']) * 100 # Calculate percentage change relative to previous

                          if ndvi_change < 0 and abs(ndvi_change_percent) > ndvi_drop_threshold_percent:
                              recommendations.append(f"⚠️ نیاز به بررسی کوددهی (افت NDVI: {ndvi_change:.3f}, معادل {abs(ndvi_change_percent):.1f}% افت نسبت به هفته قبل)")
                          elif ndvi_change > 0:
                             st.caption(f"✅ NDVI نسبت به هفته قبل افزایش یافته است (+{ndvi_change_percent:.1f}%).")
                          else: # Change is 0 or very small
                             st.caption("ℹ️ NDVI نسبت به هفته قبل تغییر قابل توجهی نداشته است.")

                     elif farm_needs_data['NDVI_prev'] is not None and farm_needs_data['NDVI_prev'] <= 0.01:
                         # Handle case where previous NDVI is very low (close to zero)
                         st.caption("ℹ️ مقدار NDVI هفته قبل بسیار پایین است. محاسبه درصد تغییر ممکن نیست.")

                elif pd.isna(farm_needs_data.get('NDVI_prev')):
                     st.caption("ℹ️ داده NDVI هفته قبل برای بررسی افت در دسترس نیست.")
                elif pd.isna(farm_needs_data.get('NDVI_curr')):
                     st.caption("ℹ️ داده NDVI هفته جاری برای بررسی افت در دسترس نیست.")


                # 3. Default if no issues detected by rules
                if not recommendations:
                    recommendations.append("✅ بر اساس شاخص‌های فعلی و آستانه‌ها، وضعیت مزرعه مطلوب به نظر می‌رسد.")

                # Display Recommendations
                for rec in recommendations:
                    if "نیاز به آبیاری" in rec: st.error(rec)
                    elif "نیاز به بررسی کوددهی" in rec: st.warning(rec)
                    else: st.success(rec)

                # --- Get and Display AI Analysis ---
                st.markdown("---")
                st.markdown("#### تحلیل هوش مصنوعی")
                if gemini_model:
                    ai_explanation = get_ai_needs_analysis(gemini_model, selected_farm_name, farm_needs_data, recommendations)
                    st.markdown(ai_explanation)
                else:
                    st.info("⚠️ سرویس تحلیل هوش مصنوعی پیکربندی نشده یا در دسترس نیست.")

    else:
         st.info("⚠️ لطفاً یک مزرعه معتبر با مختصات نقطه‌ای و روز هفته را از پنل کناری انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")


st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")
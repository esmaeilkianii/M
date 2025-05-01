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
#TODO: Add 'import pyproj' here after installing it
import pyproj

def fix_farm_name_display(farm_name):
    """Fixes the display order of farm names like XX-YY to maintain original order."""
    if isinstance(farm_name, str) and '-' in farm_name:
        try:
            # Split the farm name and preserve the order
            parts = farm_name.split('-')
            if len(parts) == 2 and all(part.strip().isdigit() for part in parts):
                # Keep original order by using Unicode control characters
                return f"{parts[0]}-{parts[1]}"
        except:
            pass
    return farm_name

# --- Custom CSS ---
st.set_page_config(
    page_title="سامانه پایش هوشمند نیشکر",
    page_icon="🌾",
    layout="wide"
)

# Custom CSS for Persian text alignment, professional styling, and animations
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');
        
        /* Main container with animation */
        .main {
            font-family: 'Vazirmatn', sans-serif;
            animation: fadeIn 1s ease-in;
        }
        
        /* Animated sugarcane background */
        .stApp::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(rgba(255,255,255,0.95), rgba(255,255,255,0.95)),
                        url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M30,90 Q50,20 70,90" stroke="green" fill="none" stroke-width="2"><animate attributeName="d" dur="3s" repeatCount="indefinite" values="M30,90 Q50,20 70,90;M30,90 Q50,30 70,90;M30,90 Q50,20 70,90"/></path></svg>');
            background-size: 100px 100px;
            opacity: 0.1;
            z-index: -1;
            animation: sway 3s ease-in-out infinite;
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes sway {
            0% { background-position: 0 0; }
            50% { background-position: -50px 0; }
            100% { background-position: 0 0; }
        }
        
        /* Cards with hover effect */
        .element-container {
            background: rgba(255,255,255,0.8);
            border-radius: 10px;
            padding: 1rem;
            margin: 0.5rem 0;
            transition: all 0.3s ease;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        
        .element-container:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        }
        
        /* Headers with animation */
        h1, h2, h3 {
            font-family: 'Vazirmatn', sans-serif;
            color: #2c3e50;
            text-align: right;
            position: relative;
            overflow: hidden;
        }
        
        h1::after, h2::after, h3::after {
            content: '';
            position: absolute;
            bottom: 0;
            right: 0;
            width: 100%;
            height: 2px;
            background: linear-gradient(to left, #2ecc71, transparent);
            animation: slideIn 1s ease-out;
        }
        
        @keyframes slideIn {
            from { transform: translateX(100%); }
            to { transform: translateX(0); }
        }
        
        /* Metrics with animation */
        .css-1xarl3l {
            font-family: 'Vazirmatn', sans-serif;
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            animation: scaleIn 0.5s ease-out;
        }
        
        @keyframes scaleIn {
            from { transform: scale(0.95); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        
        /* Other existing styles... */
        
        /* Fix for farm name display */
        .farm-name {
            unicode-bidi: plaintext;
            text-align: right;
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
# GEOJSON_FILE_PATH = 'farm_geodata_ready.geojson' # Old GeoJSON path
CSV_FILE_PATH = 'farm_geodata_ready (1).csv' # Use the new CSV file
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# --- GEE Authentication ---
@st.cache_resource # Cache the GEE initialization
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
            
        # Try to read and validate the service account file
        try:
            with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                creds_json = json.load(f)
                required_keys = ['type', 'project_id', 'private_key', 'client_email']
                if not all(key in creds_json for key in required_keys):
                    st.error("خطا: فایل Service Account ناقص است. لطفاً از صحت محتویات فایل اطمینان حاصل کنید.")
                    st.stop()
                st.info(f"Service Account Email: {creds_json['client_email']}")
        except json.JSONDecodeError:
            st.error("خطا: فایل Service Account قابل خواندن نیست. لطفاً از صحت فرمت JSON اطمینان حاصل کنید.")
            st.stop()
            
        # Initialize with more detailed error handling
        try:
            credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
            ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
            
            # Test the connection by making a simple API call
            ee.Number(1).getInfo()
            
            print("GEE Initialized Successfully using Service Account.")
            st.success("✅ اتصال به Google Earth Engine با موفقیت برقرار شد.")
            return True
            
        except ee.EEException as e:
            error_msg = str(e)
            if "permission" in error_msg.lower() or "forbidden" in error_msg.lower():
                st.error("""
                خطای دسترسی به Google Earth Engine. لطفاً موارد زیر را بررسی کنید:
                1. آیا Service Account در Earth Engine ثبت شده است؟ (https://code.earthengine.google.com/register)
                2. آیا API های لازم در Google Cloud Console فعال هستند؟
                3. آیا Service Account دسترسی‌های لازم را دارد؟
                
                خطای اصلی: {}
                """.format(error_msg))
            else:
                st.error(f"خطای Google Earth Engine: {error_msg}")
            st.stop()
            
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.error(traceback.format_exc())
        st.stop()


# --- Load Farm Data ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع (CSV با گوشه‌ها)...")
def load_farm_data(csv_path=CSV_FILE_PATH):
    """Loads farm data from CSV including corner coordinates and creates ee.Geometry.Polygon."""
    try:
        # Read CSV, handle potential BOM in the first column name
        df = pd.read_csv(csv_path)
        # Clean column names (remove BOM if present)
        df.columns = df.columns.str.replace('\ufeff', '', regex=True)
        st.info(f"Columns from CSV: {list(df.columns)}")

        # --- Column Validation ---
        required_cols = [
            'مزرعه', 'سن', 'واریته', 'روز', 'گروه',
            'lat1', 'lon1', 'lat2', 'lon2',
            'lat3', 'lon3', 'lat4', 'lon4'
        ]
        if not all(col in df.columns for col in required_cols):
            missing_cols = [col for col in required_cols if col not in df.columns]
            st.error(f"❌ فایل CSV باید شامل ستون‌های ضروری باشد. ستون‌های یافت نشده: {', '.join(missing_cols)}")
            st.stop()

        # --- Data Cleaning and Conversion ---
        coord_cols = ['lat1', 'lon1', 'lat2', 'lon2', 'lat3', 'lon3', 'lat4', 'lon4']
        # Replace Persian decimal separators and slashes with periods IN COORDINATE COLUMNS ONLY
        for col in coord_cols:
            if col in df.columns:
                # Ensure column is string type before replacing
                df[col] = df[col].astype(str)
                df[col] = df[col].str.replace(',', '.', regex=False) # Replace Persian comma (momayyez)
                df[col] = df[col].str.replace('/', '.', regex=False) # Replace slash
                # Add replacement for standard comma if necessary
                # df[col] = df[col].str.replace(',', '.', regex=False) 
                
        # Convert coordinate columns to numeric after replacement
        for col in coord_cols:
            if col in df.columns: # Check again in case a column was missing
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Drop rows with missing coordinates or essential identifiers
        initial_count = len(df)
        essential_check_cols = ['مزرعه', 'روز'] + coord_cols
        df = df.dropna(subset=essential_check_cols)
        dropped_count = initial_count - len(df)
        if dropped_count > 0:
            st.warning(f"⚠️ {dropped_count} رکورد به دلیل مقادیر خالی یا نامعتبر در ستون‌های 'مزرعه', 'روز' یا مختصات حذف شدند.")

        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای نامعتبر).")
            st.stop()

        # Ensure 'روز' and 'گروه' are strings and normalized
        df['روز'] = df['روز'].astype(str).str.replace(r'\s+', ' ', regex=True).str.strip()
        df['گروه'] = df['گروه'].astype(str).str.strip()
        # Convert other attributes if needed (e.g., سن, مساحت if it existed)
        # df['سن'] = pd.to_numeric(df['سن'], errors='coerce') # Example

        # --- Coordinate System Conversion (UTM to Lat/Lon) ---
        # The coordinates in the CSV appear to be UTM (likely Zone 39N for this region).
        # Google Earth Engine requires geographic coordinates (Latitude/Longitude, WGS84).
        # We need to convert them using the pyproj library.
        # Make sure 'pyproj' is installed (pip install pyproj) and added to requirements.txt
        try:
            import pyproj
        except ImportError:
            st.error("❌ کتابخانه 'pyproj' برای تبدیل مختصات UTM به جغرافیایی مورد نیاز است.")
            st.error("لطفاً آن را نصب کنید: pip install pyproj و به requirements.txt اضافه کنید و برنامه را مجددا اجرا کنید.")
            st.stop()

        # Define the UTM projection (Zone 39N, WGS84 datum) and the target geographic projection (WGS84)
        # Confirmed Khuzestan is typically Zone 39N.
        utm_proj = pyproj.Proj(proj='utm', zone=39, ellps='WGS84', south=False)
        wgs84_proj = pyproj.Proj(proj='latlong', datum='WGS84')
        transformer = pyproj.Transformer.from_proj(utm_proj, wgs84_proj, always_xy=True) # Ensure lon, lat output order

        # Convert corner coordinates
        try:
            # Apply the transformation - note the input order might be easting (lon-like), northing (lat-like) from UTM
            # pyproj expects x, y input, which corresponds to lon, lat for geographic but easting, northing for UTM
            df['lon1_geo'], df['lat1_geo'] = transformer.transform(df['lon1'].values, df['lat1'].values)
            df['lon2_geo'], df['lat2_geo'] = transformer.transform(df['lon2'].values, df['lat2'].values)
            df['lon3_geo'], df['lat3_geo'] = transformer.transform(df['lon3'].values, df['lat3'].values)
            df['lon4_geo'], df['lat4_geo'] = transformer.transform(df['lon4'].values, df['lat4'].values)
            st.info("Coordinates successfully converted from UTM to Geographic (Lat/Lon).")
        except Exception as proj_err:
            st.error(f"❌ خطا در تبدیل مختصات UTM به جغرافیایی: {proj_err}")
            st.error(traceback.format_exc())
            st.error("لطفاً از صحت فرمت ستون‌های مختصات و انتخاب زون UTM صحیح (39N) اطمینان حاصل کنید.")
            st.stop()
        # --- End Coordinate Conversion ---


        # --- Create ee.Geometry.Polygon for each farm ---
        def create_ee_polygon(row):
            try:
                # Coordinates must be in counter-clockwise order for GEE Polygons
                # Ensure the order [lon, lat] for GEE, using the CONVERTED coordinates
                coords = [
                    [row['lon1_geo'], row['lat1_geo']],
                    [row['lon2_geo'], row['lat2_geo']],
                    [row['lon3_geo'], row['lat3_geo']],
                    [row['lon4_geo'], row['lat4_geo']],
                    [row['lon1_geo'], row['lat1_geo']] # Close the loop
                ]

                # --- DEBUGGING: Print CONVERTED coordinates ---
                if row.name < 2: # Print for first 2 rows
                    # st.info(f"Row {row.name} - Original UTM Coords (lon1, lat1): {row['lon1']}, {row['lat1']}")
                    st.info(f"Row {row.name} - Converted Geo Coords for {row['مزرعه']}: {coords}")
                    # coord_types = [(type(lon), type(lat)) for lon, lat in coords[:-1]]
                    # st.info(f"Row {row.name} - Converted Coord Types: {coord_types}")
                # --- END DEBUGGING ---

                # Basic check for valid CONVERTED coordinates (e.g., within expected range and numeric)
                # Use pd.isna explicitly to check for NaN after coercion
                is_valid = True
                for i, (lon, lat) in enumerate(coords[:-1]): # Check points 1 to 4
                    if pd.isna(lon) or pd.isna(lat) or not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                         if row.name < 5: # Log details for first few failures
                             st.warning(f"Invalid CONVERTED coordinate found in row {row.name} for {row['مزرعه']} at point {i+1}: lon={lon}, lat={lat}")
                         is_valid = False
                         break # No need to check further points in this row

                if not is_valid:
                     st.warning(f"Skipping row {row.name} ({row['مزرعه']}) due to invalid converted coordinates.")
                     return None # Return None if any coordinate is invalid

                return ee.Geometry.Polygon(coords)
            except Exception as e:
                # Log the error with more details for the first few rows
                if row.name < 5:
                    st.error(f"Error creating polygon for مزرعه {row['مزرعه']} (Row {row.name}) using converted coords: {e}")
                    st.error(f"Converted Data: lon1_geo={row.get('lon1_geo', 'N/A')}, lat1_geo={row.get('lat1_geo', 'N/A')}, ...")
                    st.error(traceback.format_exc()) # Add traceback for detailed debugging
                # else: # Optionally log a generic warning for subsequent errors to avoid flooding the UI
                    # st.warning(f"Failed to create polygon for مزرعه {row['مزرعه']}")
                return None

        df['ee_geometry'] = df.apply(create_ee_polygon, axis=1)

        # Drop rows where polygon creation failed
        initial_count_geom = len(df)
        df = df.dropna(subset=['ee_geometry']) # Ensure we have a valid geometry object
        dropped_geom_count = initial_count_geom - len(df)
        if dropped_geom_count > 0:
             st.warning(f"⚠️ {dropped_geom_count} رکورد به دلیل خطا در ایجاد هندسه چندضلعی حذف شدند.")

        if df.empty:
            st.warning("⚠️ هیچ مزرعه‌ای با هندسه معتبر یافت نشد.")
            st.stop()

        st.success(f"✅ داده‌های {len(df)} مزرعه (با هندسه چندضلعی از CSV) با موفقیت بارگذاری شد.")
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
    farm_data_df = load_farm_data() # Now returns DataFrame with ee_geometry column

# Load Analysis Data
analysis_area_df, analysis_prod_df = load_analysis_data()

# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Day of the Week Selection ---
available_days = sorted(farm_data_df['روز'].unique()) # Use df
selected_day = st.sidebar.selectbox(
    "📅 روز هفته را انتخاب کنید:",
    options=available_days,
    index=0, # Default to the first day
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

# --- Filter Data Based on Selected Day ---
filtered_farms_df = farm_data_df[farm_data_df['روز'] == selected_day].copy() # Use df

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

# --- Farm Selection ---
available_farms = sorted(filtered_farms_df['مزرعه'].unique()) # Use df
# Add an option for "All Farms"
farm_options = ["همه مزارع"] + [fix_farm_name_display(farm) for farm in available_farms]
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه مورد نظر را انتخاب کنید:",
    options=farm_options,
    index=0,
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
    "NI": "شاخص نیتروژن (تخمینی)",
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
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)', {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('B11'),
        'NIR': image.select('B8')
    }).rename('MSI')
    lai = ndvi.multiply(3.5).rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)', {
        'NIR': image.select('B8'),
        'GREEN': green_safe,
        'RED': image.select('B4')
    }).rename('CVI')
    ni = image.expression(
        '((RE3 - RE1) / (RE3 + RE1)) * ((RE2) / (NIR))', {
            'RE1': image.select('B5'),
            'RE2': image.select('B6'),
            'RE3': image.select('B7'),
            'NIR': image.select('B8')
        }).rename('NI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi, ni])

# --- Function to get processed image for a date range and geometry ---
@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    """
    Gets cloud-masked, index-calculated Sentinel-2 median composite for a given geometry and date range.
    _geometry: ee.Geometry (Polygon, MultiPolygon, Point, Rectangle)
    start_date, end_date: YYYY-MM-DD strings
    index_name: Name of the primary index band to return (e.g., 'NDVI')
    """
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry) # Works with polygons too
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)) # Apply cloud masking

        # Check if any images are available after filtering
        count = s2_sr_col.size().getInfo()
        if count == 0:
            # st.warning(f"هیچ تصویر Sentinel-2 بدون ابر در بازه {start_date} تا {end_date} یافت نشد.")
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date}."

        # Calculate indices for each image in the collection
        indexed_col = s2_sr_col.map(add_indices)

        # Create a median composite image
        median_image = indexed_col.median() # Use median to reduce noise/outliers

        # Select the desired index band
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
@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_geometry, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    """
    Gets a time series of a specified index for a geometry (calculates mean over the area).
    _geometry: ee.Geometry (Polygon, MultiPolygon, Point)
    """
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))

        def extract_value(image):
            # Extract the mean index value over the geometry
            # Use reduceRegion for polygons; scale should match sensor resolution (e.g., 10m for S2 NDVI)
            value = image.reduceRegion(
                reducer=ee.Reducer.mean(), # Use mean for polygon average
                geometry=_geometry,
                scale=10, # Scale in meters (10m for Sentinel-2 RGB/NIR)
                maxPixels=1e9 # Increase maxPixels for potentially larger geometries
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
# NEW: Function to get all relevant indices for a farm point for two periods
# ==============================================================================
@st.cache_data(show_spinner="در حال محاسبه شاخص‌های نیازسنجی...", persist=True)
def get_farm_needs_data(_geometry, start_curr, end_curr, start_prev, end_prev):
    """
    Calculates mean NDVI, NDMI, EVI for current and previous periods over a geometry.
     _geometry: ee.Geometry (Polygon, MultiPolygon, Point)
     """
    results = {
        'NDVI_curr': None, 'NDMI_curr': None, 'EVI_curr': None,
        'NDVI_prev': None, 'NDMI_prev': None, 'EVI_prev': None,
        'error': None
    }
    # Remove SAVI from the list of indices to get
    indices_to_get = ['NDVI', 'NDMI', 'EVI']

    def get_mean_values_for_period(start, end):
        period_values = {index: None for index in indices_to_get}
        error_msg = None
        try:
            # Get median composite image with all indices calculated
            s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                         .filterBounds(_geometry) # Use polygon
                         .filterDate(start, end)
                         .map(maskS2clouds)
                         .map(add_indices)) # add_indices already updated to exclude SAVI

            count = s2_sr_col.size().getInfo()
            if count == 0:
                return period_values, f"هیچ تصویری در بازه {start}-{end} یافت نشد"

            median_image = s2_sr_col.median()

            # Reduce region to get the mean value at the point for all required indices
            mean_dict = median_image.select(indices_to_get).reduceRegion(
                reducer=ee.Reducer.mean(), # Use mean for polygon average
                geometry=_geometry, # Use polygon
                scale=10,  # Scale in meters
                maxPixels=1e9 # Increase maxPixels
            ).getInfo()

            if mean_dict:
                for index in indices_to_get:
                    period_values[index] = mean_dict.get(index)
            return period_values, None
        except ee.EEException as e:
            error_msg = f"خطای GEE در بازه {start}-{end}: {e}"
            return period_values, error_msg
        except Exception as e:
            error_msg = f"خطای ناشناخته در بازه {start}-{end}: {e}"
            return period_values, error_msg

    # Get data for current period
    curr_values, err_curr = get_mean_values_for_period(start_curr, end_curr)
    if err_curr:
        results['error'] = err_curr
    else:
        results['NDVI_curr'] = curr_values['NDVI']
        results['NDMI_curr'] = curr_values['NDMI']
        results['EVI_curr'] = curr_values['EVI']
        # Remove SAVI from results assignment
        # results['SAVI_curr'] = curr_values['SAVI']

    # Get data for previous period
    prev_values, err_prev = get_mean_values_for_period(start_prev, end_prev)
    if err_prev:
        results['error'] = f"{results.get('error', '')} | {err_prev}" # Append errors
    else:
        results['NDVI_prev'] = prev_values['NDVI']
        results['NDMI_prev'] = prev_values['NDMI']
        results['EVI_prev'] = prev_values['EVI']
        # Remove SAVI from results assignment
        # results['SAVI_prev'] = prev_values['SAVI']

    return results

# ==============================================================================
# NEW: Gemini AI Helper Functions
# ==============================================================================

# Configure Gemini API
@st.cache_resource
def configure_gemini():
    """Configures the Gemini API client using a hardcoded API key (NOT RECOMMENDED)."""
    try:
        # --- WARNING: Hardcoding API keys is insecure! Use Streamlit secrets instead. ---
        api_key = "AIzaSyC6ntMs3XDa3JTk07-6_BRRCduiQaRmQFQ" # <-- HARDCODED API KEY
        # ---------------------------------------------------------------------------

        if not api_key:
             st.error("❌ کلید API جمینای به صورت مستقیم در کد وارد نشده است.")
             return None

        genai.configure(api_key=api_key)
        # Optional: Add safety settings configuration here if needed
        # safety_settings = [...]
        # model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)
        model = genai.GenerativeModel('gemini-1.5-flash') # Use the latest flash model
        print("Gemini Configured Successfully (using hardcoded key).")
        return model
    # except KeyError: # No longer reading from secrets
    #     st.error("❌ کلید API جمینای (GEMINI_API_KEY) در فایل secrets.toml یافت نشد.")
    #     st.info("لطفاً فایل .streamlit/secrets.toml را ایجاد کرده و کلید خود را در آن قرار دهید.")
    #     return None
    except Exception as e:
        st.error(f"❌ خطا در تنظیم Gemini API: {e}")
        return None

# Function to get AI analysis
@st.cache_data(show_spinner="در حال دریافت تحلیل هوش مصنوعی...", persist=True)
def get_ai_analysis(_model, farm_name, index_data, recommendations):
    """Generates AI analysis for the farm's condition."""
    if _model is None:
        return "سرویس هوش مصنوعی در دسترس نیست."

    # Prepare data string
    data_str = ""
    if index_data['NDVI_curr'] is not None: data_str += f"NDVI فعلی: {index_data['NDVI_curr']:.3f} (قبلی: {index_data.get('NDVI_prev', 'N/A'):.3f})\n"
    if index_data['NDMI_curr'] is not None: data_str += f"NDMI فعلی: {index_data['NDMI_curr']:.3f} (قبلی: {index_data.get('NDMI_prev', 'N/A'):.3f})\n"
    if index_data['EVI_curr'] is not None: data_str += f"EVI فعلی: {index_data['EVI_curr']:.3f} (قبلی: {index_data.get('EVI_prev', 'N/A'):.3f})\n"
    if index_data['SAVI_curr'] is not None: data_str += f"SAVI فعلی: {index_data['SAVI_curr']:.3f} (قبلی: {index_data.get('SAVI_prev', 'N/A'):.3f})\n"

    prompt = f"""
    شما یک متخصص کشاورزی نیشکر هستید. لطفاً وضعیت مزرعه '{farm_name}' را بر اساس داده‌های شاخص و توصیه‌های اولیه زیر تحلیل کنید و یک توضیح کوتاه و کاربردی به زبان فارسی ارائه دهید. تمرکز تحلیل بر نیاز آبیاری و کودی باشد.

    داده‌های شاخص:
    {data_str}
    توصیه‌های اولیه:
    {', '.join(recommendations) if recommendations else 'هیچ توصیه‌ای وجود ندارد.'}

    تحلیل شما:
    """

    try:
        response = _model.generate_content(prompt)
        # Accessing response text might differ slightly based on exact library version
        # Check response object structure if needed
        return response.text
    except Exception as e:
        st.warning(f"⚠️ خطا در ارتباط با Gemini API: {e}")
        return "خطا در دریافت تحلیل هوش مصنوعی."



# ==============================================================================
# Main Application Layout (Using Tabs)
# ==============================================================================

# Configure Gemini Model at the start
gemini_model = configure_gemini()

tab1, tab3 = st.tabs(["📊 پایش مزارع", "💧کود و آبیاری"])

with tab1:
    # ==============================================================================
    # Main Panel Display
    # ==============================================================================

    # --- Get Selected Farm Geometry and Details ---
    selected_farm_details = None
    selected_farm_geom_ee = None # GEE geometry object
    selected_farm_geometry_shapely = None # Shapely geometry object (from GeoDataFrame)

    if selected_farm_name == "همه مزارع":
        # Create a FeatureCollection of all filtered farms for GEE processing/clipping
        try:
            # Convert DataFrame rows to ee.Features with geometry
            features = []
            for index, row in filtered_farms_df.iterrows():
                if row['ee_geometry']:
                    # Create feature with geometry and properties
                    feature = ee.Feature(row['ee_geometry'], row.drop(['ee_geometry']).to_dict())
                    features.append(feature)
            if features:
                 selected_farm_geom_ee = ee.FeatureCollection(features).geometry() # Use combined geometry
                 # For map extent, get bounds from the df coordinates
                 min_lon = filtered_farms_df[['lon1', 'lon2', 'lon3', 'lon4']].min().min()
                 min_lat = filtered_farms_df[['lat1', 'lat2', 'lat3', 'lat4']].min().min()
                 max_lon = filtered_farms_df[['lon1', 'lon2', 'lon3', 'lon4']].max().max()
                 max_lat = filtered_farms_df[['lat1', 'lat2', 'lat3', 'lat4']].max().max()
                 map_bounds = [[min_lat, min_lon], [max_lat, max_lon]]
            else:
                 st.warning("هندسه‌ای برای نمایش کلی مزارع یافت نشد.")
                 selected_farm_geom_ee = None
                 map_bounds = None
        except Exception as e:
            st.error(f"خطا در ایجاد هندسه ترکیبی برای همه مزارع: {e}")
            selected_farm_geom_ee = None
            map_bounds = None

        # Store the DataFrame for map plotting
        selected_farms_df_for_map = filtered_farms_df
        st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
        st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
    else:
        # Get the row for the selected farm
        selected_farm_details_series = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name.replace('\u202B', '').replace('\u202C', '')].iloc[0]
        selected_farm_details = selected_farm_details_series.to_dict() # Convert Series to Dict for easier access
        selected_farm_geom_ee = selected_farm_details['ee_geometry'] # Get the pre-calculated ee.Geometry

        if not selected_farm_geom_ee:
             st.error(f"هندسه GEE برای مزرعه '{selected_farm_name}' یافت نشد یا نامعتبر است.")
             # Optionally try to recalculate it here if needed

        st.subheader(f"جزئیات مزرعه: {fix_farm_name_display(selected_farm_name)} (روز: {selected_day})")
        # Display farm details (use .get for safety)
        details_cols = st.columns(3)
        with details_cols[0]:
            # مساحت might not be in the new CSV, handle gracefully
            st.metric("مساحت داشت (هکتار)", f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A")
            st.metric("واریته", f"{selected_farm_details.get('واریته', 'N/A')}")
        with details_cols[1]:
            st.metric("گروه", f"{selected_farm_details.get('گروه', 'N/A')}")
            st.metric("سن", f"{selected_farm_details.get('سن', 'N/A')}")
        with details_cols[2]:
             # Display centroid coordinates (calculate from ee_geometry if needed)
             try:
                 if selected_farm_geom_ee:
                    centroid_ee = selected_farm_geom_ee.centroid(maxError=1).coordinates().getInfo()
                    st.metric("مرکز مزرعه", f"{centroid_ee[1]:.5f}, {centroid_ee[0]:.5f}")
                 else:
                    st.metric("مرکز مزرعه", "N/A")
             except Exception:
                  st.metric("مرکز مزرعه", "خطا در محاسبه")


    # --- Map Display ---
    st.markdown("---")
    st.subheader(" نقشه وضعیت مزارع")

    # Define visualization parameters based on the selected index
    vis_params = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'NDMI': {'min': -1, 'max': 1, 'palette': ['brown', 'white', 'blue']},
        'LAI': {'min': 0, 'max': 6, 'palette': ['white', 'lightgreen', 'darkgreen']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['blue', 'white', 'brown']},
        'CVI': {'min': 0, 'max': 20, 'palette': ['yellow', 'lightgreen', 'darkgreen']},
        'NI': {'min': -1, 'max': 1, 'palette': ['red', 'yellow', 'green']},  # Red indicates nitrogen deficiency
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

    # Get the processed image for the current week using ee.Geometry
    if selected_farm_geom_ee:
        gee_image_current, error_msg_current = get_processed_image(
            selected_farm_geom_ee, start_date_current_str, end_date_current_str, selected_index
        )

        if gee_image_current:
            # Add the GEE layer to the map
            try:
                m.addLayer(
                    gee_image_current.clip(selected_farm_geom_ee), # Clip the image to the farm boundary(ies)
                    vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}), # Default vis
                    f"{selected_index} (محدوده مزارع)"
                )

                # Remove the problematic add_legend call and replace with a custom legend
                # Create a custom legend using folium
                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI', 'NI']:
                    legend_html = '''
                    <div style="position: fixed; bottom: 50px; right: 50px; z-index: 1000; background-color: white; padding: 10px; border: 2px solid grey; border-radius: 5px;">
                        <p style="margin: 0;"><strong>{} Legend</strong></p>
                        <p style="margin: 0; color: red;">کمبود/بحرانی</p>
                        <p style="margin: 0; color: yellow;">متوسط</p>
                        <p style="margin: 0; color: green;">مطلوب/بالا</p>
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

                # Add farm boundaries to the map using folium.Polygon
                if selected_farm_name == "همه مزارع":
                     # Add all filtered farms as polygons
                     if not selected_farms_df_for_map.empty:
                         for idx, farm in selected_farms_df_for_map.iterrows():
                             coords = [
                                [farm['lat1'], farm['lon1']], [farm['lat2'], farm['lon2']],
                                [farm['lat3'], farm['lon3']], [farm['lat4'], farm['lon4']]
                                # No need to close the loop for folium.Polygon
                             ]
                             # Check for NaN coords before plotting
                             if not any(pd.isna(c) for point in coords for c in point):
                                 folium.Polygon(
                                     locations=coords,
                                     popup=f"مزرعه: {farm['مزرعه']}\nگروه: {farm.get('گروه', 'N/A')}",
                                     tooltip=farm['مزرعه'],
                                     color='cyan',
                                     fill=True,
                                     fill_color='cyan',
                                     fill_opacity=0.1,
                                     weight=2
                                 ).add_to(m)
                         # Adjust map bounds to fit all farms
                         if map_bounds:
                             m.fit_bounds(map_bounds, padding=(30, 30))

                elif selected_farm_geom_ee:
                    # Add single selected farm polygon
                    try:
                        # Get coordinates from the ee.Geometry object
                        poly_coords_ee = selected_farm_geom_ee.coordinates().get(0).getInfo() # Get outer ring
                        # Convert [[lon, lat], ...] to [[lat, lon], ...] for folium
                        poly_coords_folium = [[lat, lon] for lon, lat in poly_coords_ee]
                        folium.Polygon(
                            locations=poly_coords_folium,
                            popup=f"مزرعه: {selected_farm_name}",
                            tooltip=selected_farm_name,
                            color='red',
                            fill=True,
                            fill_color='red',
                            fill_opacity=0.2,
                            weight=3
                        ).add_to(m)
                        # Center map on the selected farm's centroid
                        centroid_ee = selected_farm_geom_ee.centroid(maxError=1).coordinates().getInfo()
                        m.location = [centroid_ee[1], centroid_ee[0]] # lat, lon
                        m.zoom = 15 # Zoom closer for a single polygon
                    except Exception as poly_err:
                        st.error(f"خطا در رسم چندضلعی مزرعه {selected_farm_name} روی نقشه: {poly_err}")
                         # Fallback: use corner coordinates if ee geometry fails for folium
                        coords = [
                            [selected_farm_details['lat1'], selected_farm_details['lon1']],
                            [selected_farm_details['lat2'], selected_farm_details['lon2']],
                            [selected_farm_details['lat3'], selected_farm_details['lon3']],
                            [selected_farm_details['lat4'], selected_farm_details['lon4']]
                         ]
                        if not any(pd.isna(c) for point in coords for c in point):
                            folium.Polygon(locations=coords, color='red', fill=True, fill_color='red', fill_opacity=0.2, weight=3, tooltip=selected_farm_name).add_to(m)
                            # Center based on average coordinates
                            avg_lat = (selected_farm_details['lat1'] + selected_farm_details['lat2'] + selected_farm_details['lat3'] + selected_farm_details['lat4']) / 4
                            avg_lon = (selected_farm_details['lon1'] + selected_farm_details['lon2'] + selected_farm_details['lon3'] + selected_farm_details['lon4']) / 4
                            m.location = [avg_lat, avg_lon]
                            m.zoom = 15

                m.add_layer_control() # Add layer control to toggle base maps and layers

            except Exception as map_err:
                st.error(f"خطا در افزودن لایه به نقشه: {map_err}")
                st.error(traceback.format_exc())
        else:
            st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")

    # Display the map in Streamlit
    st_folium(m, width=None, height=500, use_container_width=True)
    st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها برای تغییر نقشه پایه استفاده کنید.")
    # Note: Direct PNG download from st_folium/geemap isn't built-in easily.
    st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


    # --- Time Series Chart ---
    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom_ee: # Use the ee.Geometry object
        # Define a longer period for the time series chart (e.g., last 6 months)
        timeseries_end_date = today.strftime('%Y-%m-%d')
        timeseries_start_date = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d')

        # Pass the ee.Geometry (could be polygon) to the time series function
        ts_df, ts_error = get_index_time_series(
            selected_farm_geom_ee,
            selected_index,
            start_date=timeseries_start_date,
            end_date=timeseries_end_date
        )

        if ts_error:
            st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
        elif not ts_df.empty:
            st.line_chart(ts_df[selected_index])
            st.caption(f"نمودار تغییرات میانگین شاخص {selected_index} برای کل مساحت مزرعه {selected_farm_name} در 6 ماه گذشته.")
        else:
            st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
    # Remove the old geometry type check
    # else:
    #     st.warning("نوع هندسه مزرعه برای نمودار سری زمانی پشتیبانی نمی‌شود (فقط نقطه).")
    else:
        st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست.")


    # ==============================================================================
    # Helper Function for Status Determination
    # ==============================================================================

    def determine_status(row, index_name):
        """Determines the status based on change in index value."""
        if pd.isna(row['تغییر']) or pd.isna(row[f'{index_name} (هفته جاری)']) or pd.isna(row[f'{index_name} (هفته قبل)']):
            return "بدون داده"

        change_val = row['تغییر']
        # Threshold for significant change
        threshold = 0.05

        # For indices where higher is better (NDVI, EVI, LAI, CVI, NDMI)
        if index_name in ['NDVI', 'EVI', 'LAI', 'CVI', 'NDMI']:
            if change_val > threshold:
                return "رشد مثبت / بهبود"
            elif change_val < -threshold:
                return "تنش / کاهش"
            else:
                return "ثابت"
        # For indices where lower is better (MSI)
        elif index_name in ['MSI']:
            if change_val < -threshold: # Negative change means improvement (less stress)
                return "بهبود"
            elif change_val > threshold: # Positive change means deterioration (more stress)
                return "تنش / بدتر شدن"
            else:
                return "ثابت"
        else:
            # Default case if index type is unknown
            return "نامشخص"

    # ==============================================================================
    # Ranking Table
    # ==============================================================================
    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
        """Calculates the average index value for the current and previous week for a list of farms using their ee.Geometry."""
        results = []
        errors = []
        total_farms = len(_farms_df)
        progress_bar = st.progress(0)

        # Geometries are already in 'ee_geometry' column

        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            farm_name = farm['مزرعه']
            ee_geom = farm['ee_geometry'] # Get the ee.Geometry object

            if not ee_geom:
                # This should ideally be caught during loading, but double-check
                errors.append(f"هندسه نامعتبر برای {farm_name} در محاسبه هفتگی.")
                progress_bar.progress((i + 1) / total_farms) # Update progress even on error
                continue # Skip this farm

            def get_mean_value(start, end):
                try:
                    image, error = get_processed_image(ee_geom, start, end, index_name)
                    if image:
                        # Reduce region to get the mean value over the polygon
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=ee_geom,
                            scale=10,  # Scale in meters
                            maxPixels=1e9 # Increase maxPixels
                        ).getInfo()
                        # Handle potential null result from reduceRegion
                        if mean_dict is None:
                            return None, f"reduceRegion نتیجه‌ای برای {farm_name} ({start}-{end}) برنگرداند."
                        return mean_dict.get(index_name), None
                    else:
                        return None, error
                except ee.EEException as e_ee:
                     error_msg = f"خطای GEE در محاسبه مقدار برای {farm_name} ({start}-{end}): {e_ee}"
                     return None, error_msg
                except Exception as e_other:
                     # Catch other errors during reduceRegion or getInfo
                     error_msg = f"خطای ناشناخته در محاسبه مقدار برای {farm_name} ({start}-{end}): {e_other}"
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
                'گروه': farm.get('گروه', 'N/A'),
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
        filtered_farms_df, # Pass the filtered DataFrame
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
        # Sort by the current week's index value (descending for NDVI/EVI/LAI/CVI/NDMI, ascending for MSI)
        ascending_sort = selected_index not in ['MSI'] # Simpler logic: Ascending only if MSI
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)',
            ascending=ascending_sort,
            na_position='last'
        ).reset_index(drop=True)

        # Add rank number
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        # Apply the determine_status function using .apply
        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(
            lambda row: determine_status(row, selected_index), axis=1
        )

        # Format numbers for better readability
        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col in cols_to_format:
            if col in ranking_df_sorted.columns:
                 # Check if column exists before formatting
                 ranking_df_sorted[col] = ranking_df_sorted[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")

        # Select columns to display, including 'گروه'
        display_columns = ['مزرعه', 'گروه'] + cols_to_format + ['وضعیت']
        # Ensure only existing columns are selected
        display_columns = [col for col in display_columns if col in ranking_df_sorted.columns]

        # Display the table with color coding and selected columns
        st.dataframe(ranking_df_sorted[display_columns], use_container_width=True)
        
        # Add a summary of farm statuses
        st.subheader("📊 خلاصه وضعیت مزارع")
        
        # Display status counts with appropriate colors
        col1, col2, col3 = st.columns(3)
        
        # Dynamically find positive and negative status terms used
        status_counts = ranking_df_sorted['وضعیت'].value_counts()
        positive_terms = [s for s in status_counts.index if "بهبود" in s]
        negative_terms = [s for s in status_counts.index if any(sub in s for sub in ["تنش", "کاهش", "بدتر"])]
        neutral_term = "ثابت"
        nodata_term = "بدون داده"

        with col1:
            pos_count = sum(status_counts.get(term, 0) for term in positive_terms)
            if pos_count > 0:
                pos_label = positive_terms[0] if positive_terms else "بهبود"
                st.metric(f"🟢 {pos_label}", pos_count)
            else:
                 st.metric("🟢 بهبود", 0) # Show 0 if none

        with col2:
            neutral_count = status_counts.get(neutral_term, 0)
            st.metric(f"⚪ {neutral_term}", neutral_count)

        with col3:
            neg_count = sum(status_counts.get(term, 0) for term in negative_terms)
            if neg_count > 0:
                neg_label = negative_terms[0] if negative_terms else "تنش"
                st.metric(f"🔴 {neg_label}", neg_count)
            else:
                st.metric("🔴 تنش", 0) # Show 0 if none

        # Add explanation
        st.info(f"""
        **توضیحات:**
        - **🟢 رشد مثبت / بهبود**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش NDVI/EVI/LAI/CVI/NDMI یا کاهش MSI).
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش / کاهش / بدتر شدن**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند (کاهش NDVI/EVI/LAI/CVI/NDMI یا افزایش MSI).
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


    st.markdown("---")
    st.sidebar.markdown("---")
    st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap") # Removed geopandas


# --- New Tab for Needs Analysis ---
with tab3:
    st.header("تحلیل نیاز آبیاری و کوددهی")

    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا تحلیل نیازهای آن نمایش داده شود.")
    elif selected_farm_geom_ee: # Use the ee.Geometry object
        st.subheader(f"تحلیل برای مزرعه: {fix_farm_name_display(selected_farm_name)}")

        # Define thresholds (allow user adjustment)
        st.markdown("**تنظیم آستانه‌ها:**")
        ndmi_threshold = st.slider("آستانه NDMI برای هشدار آبیاری:", 0.0, 0.5, 0.25, 0.01,
                                     help="اگر NDMI کمتر از این مقدار باشد، نیاز به آبیاری اعلام می‌شود.")
        ndvi_drop_threshold = st.slider("آستانه افت NDVI برای بررسی کوددهی (%):", 0.0, 20.0, 5.0, 0.5,
                                        help="اگر NDVI نسبت به هفته قبل بیش از این درصد افت کند، نیاز به بررسی کوددهی اعلام می‌شود.")

        # Get the required index data for the selected farm using its ee.Geometry
        farm_needs_data = get_farm_needs_data(
            selected_farm_geom_ee, # Pass ee.Geometry
            start_date_current_str, end_date_current_str,
            start_date_previous_str, end_date_previous_str
        )

        if farm_needs_data['error']:
            st.error(f"خطا در دریافت داده‌های شاخص برای تحلیل نیازها: {farm_needs_data['error']}")
        elif farm_needs_data['NDMI_curr'] is None or farm_needs_data['NDVI_curr'] is None:
            st.warning("داده‌های شاخص لازم (NDMI/NDVI) برای تحلیل در دوره فعلی یافت نشد.")
        else:
            # --- Display Current Indices ---
            st.markdown("**مقادیر شاخص‌ها (هفته جاری):**")
            idx_cols = st.columns(3)
            with idx_cols[0]:
                st.metric("NDVI", f"{farm_needs_data['NDVI_curr']:.3f}")
            with idx_cols[1]:
                st.metric("NDMI", f"{farm_needs_data['NDMI_curr']:.3f}")
            with idx_cols[2]:
                st.metric("EVI", f"{farm_needs_data.get('EVI_curr', 'N/A'):.3f}" if farm_needs_data.get('EVI_curr') else "N/A")

            # --- Generate Recommendations ---
            recommendations = []
            # 1. Irrigation Check
            if farm_needs_data['NDMI_curr'] < ndmi_threshold:
                recommendations.append("💧 نیاز به آبیاری")

            # 2. Fertilization Check (NDVI drop)
            if farm_needs_data['NDVI_prev'] is not None and farm_needs_data['NDVI_curr'] < farm_needs_data['NDVI_prev']:
                ndvi_change_percent = ((farm_needs_data['NDVI_prev'] - farm_needs_data['NDVI_curr']) / farm_needs_data['NDVI_prev']) * 100
                if ndvi_change_percent > ndvi_drop_threshold:
                    recommendations.append(f"⚠️ نیاز به بررسی کوددهی (افت {ndvi_change_percent:.1f}% در NDVI)")
            elif farm_needs_data['NDVI_prev'] is None:
                 st.caption("داده NDVI هفته قبل برای بررسی افت در دسترس نیست.")

            # 3. Default if no issues
            if not recommendations:
                recommendations.append("✅ وضعیت فعلی مطلوب به نظر می‌رسد.")

            # Display Recommendations
            st.markdown("**توصیه‌های اولیه:**")
            for rec in recommendations:
                if "آبیاری" in rec: st.error(rec)
                elif "کوددهی" in rec: st.warning(rec)
                else: st.success(rec)

            # --- Get and Display AI Analysis ---
            if gemini_model:
                st.markdown("**تحلیل هوش مصنوعی:**")
                ai_explanation = get_ai_analysis(gemini_model, selected_farm_name, farm_needs_data, recommendations)
                st.markdown(ai_explanation)
            else:
                st.info("سرویس تحلیل هوش مصنوعی پیکربندی نشده است.")

    else:
         st.info("ابتدا یک مزرعه را از پنل کناری انتخاب کنید.")


st.markdown("---")
st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")
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
# import base64 # Not explicitly used in current Gemini text-only flow
import google.generativeai as genai

# --- New Imports for KML/GeoJSON processing ---
import geopandas as gpd
# Fiona is often a dependency for geopandas KML driver, ensure it's importable
try:
    import fiona
except ImportError:
    st.warning("کتابخانه Fiona یافت نشد. پردازش فایل‌های KML ممکن است با مشکل مواجه شود.")


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
        .css-1xarl3l { /* Streamlit's default metric class, adjust if needed */
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
        .css-1d391kg { /* Streamlit's default sidebar class, adjust if needed */
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
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # Ganti dengan نام فایل خودتان


# --- Session State Initialization for Uploaded Geometry ---
if "uploaded_geometry" not in st.session_state:
    st.session_state.uploaded_geometry = None
if "uploaded_geometry_name" not in st.session_state:
    st.session_state.uploaded_geometry_name = None
if "uploaded_geometry_area_ha" not in st.session_state:
    st.session_state.uploaded_geometry_area_ha = None


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
# Helper Function to Parse KML/GeoJSON
# ==============================================================================
@st.cache_data(show_spinner="در حال پردازش فایل مرز...", persist=True)
def parse_vector_file_to_ee_geometry(_uploaded_file_obj):
    """Parses KML or GeoJSON file to an ee.Geometry object and its name."""
    bytes_data = _uploaded_file_obj.getvalue()
    file_name_lower = _uploaded_file_obj.name.lower()

    try:
        if file_name_lower.endswith(".kml"):
            # Ensure KML driver is available for geopandas
            gpd.io.file.fiona.drvsupport.supported_drivers['KML'] = 'rw'
            gdf = gpd.read_file(BytesIO(bytes_data), driver='KML')
        elif file_name_lower.endswith(".geojson"):
            gdf = gpd.read_file(BytesIO(bytes_data))
        else:
            raise ValueError("فرمت فایل پشتیبانی نمی‌شود. لطفاً KML یا GeoJSON آپلود کنید.")
    except Exception as e:
        raise ValueError(f"خطا در خواندن فایل وکتور با GeoPandas: {e}. ممکن است فایل پیچیده باشد یا درایور KML مشکل داشته باشد.")


    if gdf.empty:
        raise ValueError("فایل وکتور خالی است یا هندسه‌ای در آن یافت نشد.")

    # Reproject to WGS84 (EPSG:4326) if not already, GEE expects this for GeoJSON
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    # For simplicity, using the union of all geometries if multiple, or the first one.
    # A more robust approach might involve letting user select if multiple main features exist.
    combined_geom = gdf.geometry.unary_union # Combines all geometries into one
    
    # Convert to GeoJSON dictionary
    try:
        geojson_geom_dict = json.loads(gpd.GeoSeries([combined_geom]).to_json())['features'][0]['geometry']
    except Exception as e:
        raise ValueError(f"خطا در تبدیل هندسه به GeoJSON: {e}")

    # Convert GeoJSON dictionary to ee.Geometry using geemap
    try:
        ee_geometry = geemap.geojson_to_ee(geojson_geom_dict)
    except Exception as e:
        raise ValueError(f"خطا در تبدیل GeoJSON به ee.Geometry با geemap: {e}")

    # Try to get a name from KML/GeoJSON properties
    feature_name = "Uploaded Geometry"
    name_col_candidates = ['name', 'Name', 'NAME', 'id', 'ID', 'نام', 'FarmName'] # Added Persian
    # Check columns in the original GeoDataFrame
    for col in name_col_candidates:
        if col in gdf.columns:
            # Try to get the first non-null name
            valid_names = gdf[col].dropna()
            if not valid_names.empty:
                feature_name = str(valid_names.iloc[0])
                break
    if not feature_name or feature_name == "Uploaded Geometry": # Fallback if no name found
        feature_name = os.path.splitext(_uploaded_file_obj.name)[0]


    # Calculate area in hectares
    area_ha = None
    try:
        if ee_geometry.type().getInfo() in ['Polygon', 'MultiPolygon']:
            area_m2 = ee_geometry.area(maxError=1).getInfo()  # MaxError for performance
            area_ha = area_m2 / 10000
    except Exception as e:
        st.warning(f"امکان محاسبه مساحت برای هندسه بارگذاری شده وجود نداشت: {e}")

    return ee_geometry, feature_name, area_ha


# ==============================================================================
# Gemini API Configuration
# ==============================================================================
st.sidebar.subheader("✨ تنظیمات هوش مصنوعی Gemini")
GEMINI_API_KEY = st.sidebar.text_input("🔑 کلید API جمینای خود را وارد کنید:", type="password", help="برای استفاده از قابلیت‌های هوشمند، کلید API خود را از Google AI Studio دریافت و وارد کنید.")

gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        st.sidebar.success("✅ اتصال به Gemini برقرار شد.")
    except Exception as e:
        st.sidebar.error(f"خطا در اتصال به Gemini: {e}")
        gemini_model = None
else:
    st.sidebar.info("قابلیت‌های هوشمند Gemini با وارد کردن کلید API فعال می‌شوند.")

def ask_gemini(prompt_text, temperature=0.7, top_p=1.0, top_k=40):
    """Sends a prompt to Gemini and returns the response."""
    if not gemini_model:
        return "خطا: مدل Gemini مقداردهی اولیه نشده است. لطفاً کلید API را بررسی کنید."
    try:
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=3072 # Increased for longer reports
        )
        response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini API: {e}\n{traceback.format_exc()}"


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

# --- Geometry Upload ---
st.sidebar.subheader("🗺️ بارگذاری مرز مزرعه (اختیاری)")
uploaded_file = st.sidebar.file_uploader(
    "فایل KML یا GeoJSON مرز مزرعه را برای تحلیل دقیق‌تر یک قطعه انتخاب کنید:",
    type=['kml', 'geojson'],
    key="farm_boundary_uploader"
)

if uploaded_file:
    if st.session_state.get('last_uploaded_filename') != uploaded_file.name: # Process only if new file
        try:
            geom, name, area_ha = parse_vector_file_to_ee_geometry(uploaded_file)
            st.session_state.uploaded_geometry = geom
            st.session_state.uploaded_geometry_name = name
            st.session_state.uploaded_geometry_area_ha = area_ha
            st.session_state.last_uploaded_filename = uploaded_file.name
            st.sidebar.success(f"مرز '{name}' (مساحت: {area_ha:,.2f} هکتار) با موفقیت بارگذاری شد.")
        except Exception as e:
            st.sidebar.error(f"خطا در پردازش فایل مرز: {e}")
            st.session_state.uploaded_geometry = None
            st.session_state.uploaded_geometry_name = None
            st.session_state.uploaded_geometry_area_ha = None
            st.session_state.last_uploaded_filename = None # Reset
elif 'last_uploaded_filename' in st.session_state and st.session_state.last_uploaded_filename is not None:
    # File was removed by user
    st.session_state.uploaded_geometry = None
    st.session_state.uploaded_geometry_name = None
    st.session_state.uploaded_geometry_area_ha = None
    st.session_state.last_uploaded_filename = None
    # st.sidebar.info("فایل مرز حذف شد.") # Optional message

if st.session_state.uploaded_geometry:
    if st.sidebar.button("🗑️ پاک کردن مرز بارگذاری شده"):
        st.session_state.uploaded_geometry = None
        st.session_state.uploaded_geometry_name = None
        st.session_state.uploaded_geometry_area_ha = None
        st.session_state.last_uploaded_filename = None
        st.sidebar.info("مرز بارگذاری شده پاک شد. برای اعمال تغییر، صفحه ممکن است نیاز به بارگذاری مجدد داشته باشد.")
        st.experimental_rerun()


available_days = sorted(farm_data_df['روزهای هفته'].unique())
selected_day = st.sidebar.selectbox(
    "📅 روز هفته را انتخاب کنید:",
    options=available_days,
    index=0,
    help="داده‌های مزارع بر اساس این روز فیلتر می‌شوند."
)

filtered_farms_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

if filtered_farms_df.empty:
    st.warning(f"⚠️ هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
    st.stop()

available_farms = sorted(filtered_farms_df['مزرعه'].unique())
farm_options = ["همه مزارع"] + available_farms
selected_farm_name = st.sidebar.selectbox(
    "🌾 مزرعه مورد نظر را انتخاب کنید:",
    options=farm_options,
    index=0,
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی. اگر مرز بارگذاری کرده‌اید، برای مشاهده آن یک مزرعه خاص (غیر از 'همه مزارع') انتخاب کنید."
)

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
    index=0
)

today = datetime.date.today()
persian_to_weekday = {
    "شنبه": 5, "یکشنبه": 6, "دوشنبه": 0, "سه شنبه": 1,
    "چهارشنبه": 2, "پنجشنبه": 3, "جمعه": 4,
}
try:
    target_weekday = persian_to_weekday[selected_day]
    days_to_subtract = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today - datetime.timedelta(days=days_to_subtract if days_to_subtract !=0 else 0)
    if today.weekday() == target_weekday and days_to_subtract == 0: # If today is the selected day
        end_date_current = today
    elif days_to_subtract == 0 and today.weekday() != target_weekday : # If today is not the selected day, but calculation resulted in 0, means it was 7 days ago
        end_date_current = today - datetime.timedelta(days=7)


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
# Google Earth Engine Functions
# ==============================================================================
def maskS2clouds(image):
    qa = image.select('QA60')
    cloudBitMask = 1 << 10
    cirrusBitMask = 1 << 11
    mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
    scl = image.select('SCL')
    # Include shadow (3), vegetation (4), not vegetated (5), water (6), unclassified (7), cloud medium prob (8), cloud high prob (9), cirrus (10), snow/ice (11)
    # We want clear vegetation, soil, water. Exclude clouds, shadow, snow.
    # SCL values: 1 (saturated/defective), 2 (dark area pixels), 3 (cloud shadows), 4 (vegetation), 5 (bare soils),
    # 6 (water), 7 (clouds low probability / unclassified), 8 (clouds medium probability), 9 (clouds high probability), 10 (cirrus), 11 (snow/ice)
    good_quality_scl = scl.remap([4, 5, 6], [1, 1, 1], 0) # Keep only vegetation, bare soil, water
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality_scl)


def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai_expr = ndvi.multiply(3.5).clamp(0,8) # Clamping LAI to a reasonable range
    lai = lai_expr.rename('LAI')

    # Handle potential division by zero for CVI by adding a small epsilon or using .max()
    green_safe = image.select('B3').max(ee.Image(0.0001)) # Ensure green band is not zero
    red_safe = image.select('B4').max(ee.Image(0.0001))   # Ensure red band is not zero
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
        {'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': red_safe}
    ).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi])

@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))

        # Check image count after cloud masking
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date} after masking."

        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median() # Use median to further reduce noise/outliers

        # Check if the selected index band exists in the median image
        if index_name not in median_image.bandNames().getInfo():
             return None, f"شاخص '{index_name}' پس از پردازش در تصویر میانه یافت نشد. ممکن است همه تصاویر ورودی فاقد داده معتبر باشند."

        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        error_details = e.args[0] if e.args else str(e)
        if isinstance(error_details, str):
            if 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی یا منطقه بزرگ)"
            elif 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
            elif 'image.select: Pattern' in error_details and 'did not match any bands' in error_details:
                error_message += f"\n(یکی از باندهای مورد نیاز برای محاسبه شاخص {index_name} یافت نشد. ممکن است تصاویر اولیه مشکل داشته باشند.)"
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))

        geom_type = _geom.type().getInfo()
        scale = 30  # Default for Sentinel-2 bands used in indices
        reducer = ee.Reducer.mean()

        if geom_type == 'Point':
            # For a single point, a smaller scale can be used if desired, but 10/20m is native for S2 bands
            # Using mean over a 10m or 20m pixel for robustness.
            scale = 10 # Sentinel B4,B8 are 10m. B2,B3,B11,B12 are 20m. Stick to 10m for point mean.
                       # If using indices with 20m bands, GEE handles resampling.
        
        def extract_value(image):
            # Ensure the image has the band before reducing
            value = ee.Algorithms.If(
                image.bandNames().contains(index_name),
                image.reduceRegion(
                    reducer=reducer, geometry=_geom, scale=scale, maxPixels=1e9, bestEffort=True, tileScale=4 # Added bestEffort and tileScale
                ).get(index_name),
                None
            )
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})

        ts_features = s2_sr_col.map(extract_value).filter(ee.Filter.notNull([index_name]))
        ts_info = ts_features.getInfo()['features']

        if not ts_info:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد."

        ts_data = []
        for f in ts_info:
            if f['properties'] and index_name in f['properties'] and f['properties'][index_name] is not None:
                 ts_data.append({'date': f['properties']['date'], index_name: f['properties'][index_name]})

        if not ts_data:
            return pd.DataFrame(columns=['date', index_name]), "داده‌ای برای سری زمانی یافت نشد (پس از فیلتر مقادیر نامعتبر)."

        ts_df = pd.DataFrame(ts_data)
        ts_df['date'] = pd.to_datetime(ts_df['date'])
        ts_df = ts_df.sort_values('date').set_index('date')
        return ts_df, None
    except ee.EEException as e:
        error_details = str(e)
        if " কোলেশন خیلی بزرگ است" in error_details or "Collection query aborted" in error_details : # Common GEE errors for large requests
             return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی (احتمالا حجم درخواست بالا بوده): {e}"
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Determine current farm geometry for single-farm view (map, timeseries, Gemini)
# ==============================================================================
# This will be used for map display, single farm GEE image processing, time series, and Gemini context for a single farm.
# The ranking table (calculate_weekly_indices) will *always* use the point data from the CSV for all farms in the selected day.

active_farm_geom = None
active_farm_name = selected_farm_name
is_polygon_analysis_active = False
active_farm_area_ha = None # This will hold area from uploaded KML or from CSV

if st.session_state.uploaded_geometry and selected_farm_name != "همه مزارع":
    active_farm_geom = st.session_state.uploaded_geometry
    active_farm_name = st.session_state.uploaded_geometry_name if st.session_state.uploaded_geometry_name else "Uploaded Area"
    is_polygon_analysis_active = True
    active_farm_area_ha = st.session_state.uploaded_geometry_area_ha
    st.sidebar.success(f"نمایش و تحلیل برای مرز بارگذاری شده '{active_farm_name}' فعال است.")
elif selected_farm_name != "همه مزارع":
    selected_farm_details_for_active = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat_active = selected_farm_details_for_active['عرض جغرافیایی']
    lon_active = selected_farm_details_for_active['طول جغرافیایی']
    active_farm_geom = ee.Geometry.Point([lon_active, lat_active])
    active_farm_name = selected_farm_name # Name from CSV
    is_polygon_analysis_active = False # Point from CSV
    if 'مساحت' in selected_farm_details_for_active and pd.notna(selected_farm_details_for_active['مساحت']):
        active_farm_area_ha = selected_farm_details_for_active['مساحت']
else: # "همه مزارع"
    min_lon_df, min_lat_df = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
    max_lon_df, max_lat_df = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
    active_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
    active_farm_name = "همه مزارع"
    is_polygon_analysis_active = True # The bounds of all farms is a polygon


# ==============================================================================
# Main Panel Display
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["📊 داشبورد اصلی", "🗺️ نقشه و نمودارها", "💡 تحلیل هوشمند با Gemini"])

with tab1:
    st.header(APP_TITLE)
    st.subheader(APP_SUBTITLE)

    # Display details for the farm selected in dropdown, even if a KML is uploaded for map view
    # The dashboard's farm details section always refers to the CSV selected farm
    if selected_farm_name == "همه مزارع":
        st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
        st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
        if st.session_state.uploaded_geometry:
            st.info(f"یک مرز با نام '{st.session_state.uploaded_geometry_name}' بارگذاری شده است. برای مشاهده و تحلیل آن، لطفاً یک مزرعه خاص (غیر از 'همه مزارع') از منوی کشویی انتخاب کنید. سپس نقشه و تحلیل‌ها برای آن مرز بارگذاری شده نمایش داده خواهند شد.")

    else: # A specific farm is selected from dropdown
        selected_farm_details_tab1 = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        lat_tab1 = selected_farm_details_tab1['عرض جغرافیایی']
        lon_tab1 = selected_farm_details_tab1['طول جغرافیایی']
        
        st.subheader(f"جزئیات مزرعه (از CSV): {selected_farm_name} (روز: {selected_day})")
        if st.session_state.uploaded_geometry:
            st.info(f"توجه: یک مرز با نام '{st.session_state.uploaded_geometry_name}' (مساحت: {st.session_state.uploaded_geometry_area_ha:,.2f} هکتار) بارگذاری شده است. نقشه، نمودار سری زمانی و تحلیل‌های Gemini در تب‌های دیگر برای این مرز بارگذاری شده نمایش داده خواهند شد (نه نقطه مرکزی {selected_farm_name} از CSV).")

        details_cols = st.columns(3)
        with details_cols[0]:
            area_display = f"{selected_farm_details_tab1.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details_tab1.get('مساحت')) else "N/A"
            st.metric("مساحت داشت (هکتار - از CSV)", area_display)
            st.metric("واریته", f"{selected_farm_details_tab1.get('واریته', 'N/A')}")
        with details_cols[1]:
            st.metric("کانال", f"{selected_farm_details_tab1.get('کانال', 'N/A')}")
            st.metric("سن", f"{selected_farm_details_tab1.get('سن', 'N/A')}")
        with details_cols[2]:
            st.metric("اداره", f"{selected_farm_details_tab1.get('اداره', 'N/A')}")
            st.metric("مختصات مرکز (از CSV)", f"{lat_tab1:.5f}, {lon_tab1:.5f}")


    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص (بر اساس **نقاط مرکزی از CSV**) در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices_for_ranking_table(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
        results = []
        errors = []
        total_farms = len(_farms_df)
        # progress_bar = st.progress(0) # Can be too slow if many farms
        status_placeholder = st.empty()

        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            status_placeholder.text(f"پردازش مزرعه {i+1} از {total_farms}: {farm['مزرعه']}")
            farm_name = farm['مزرعه']
            _lat = farm['عرض جغرافیایی']
            _lon = farm['طول جغرافیایی']
            point_geom = ee.Geometry.Point([_lon, _lat]) # Always use point for ranking table

            def get_mean_value(start, end):
                try:
                    # For ranking table, _geometry is always point_geom
                    image, error = get_processed_image(point_geom, start, end, index_name)
                    if image:
                        # Use a slightly larger region (e.g., 3x3 pixels) for more stable point-based value
                        buffer_radius = 15 # meters, for a 30m pixel, this covers roughly the central pixel
                        buffered_point = point_geom.buffer(buffer_radius)
                        mean_dict = image.reduceRegion(
                            reducer=ee.Reducer.mean(), 
                            geometry=buffered_point, # Use buffered point
                            scale=10, # Scale of the bands being reduced (e.g. 10m for NDVI)
                            maxPixels=1e9
                        ).getInfo()
                        return mean_dict.get(index_name) if mean_dict else None, None
                    return None, error
                except Exception as e_reduce:
                     return None, f"خطا در محاسبه مقدار برای {farm_name} ({start}-{end}): {e_reduce}"

            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")

            change = None
            if current_val is not None and previous_val is not None:
                try:
                    change = float(current_val) - float(previous_val)
                except (TypeError, ValueError):
                    change = None # If conversion fails

            results.append({
                'مزرعه': farm_name, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                f'{index_name} (هفته جاری)': current_val, f'{index_name} (هفته قبل)': previous_val, 'تغییر': change
            })
            # progress_bar.progress((i + 1) / total_farms)
        # progress_bar.empty()
        status_placeholder.empty()
        return pd.DataFrame(results), errors

    ranking_df, calculation_errors = calculate_weekly_indices_for_ranking_table(
        filtered_farms_df, selected_index,
        start_date_current_str, end_date_current_str,
        start_date_previous_str, end_date_previous_str
    )

    if calculation_errors:
        with st.expander("⚠️ مشاهده خطاهای محاسبه شاخص‌ها برای جدول", expanded=False):
            for error in calculation_errors: st.caption(f"- {error}")

    ranking_df_sorted = pd.DataFrame()
    if not ranking_df.empty:
        ascending_sort = selected_index in ['MSI'] # Lower MSI is better
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        def determine_status(row, index_name_col):
            change_val = row['تغییر']
            if pd.isna(change_val) or pd.isna(row[f'{index_name_col} (هفته جاری)']) or pd.isna(row[f'{index_name_col} (هفته قبل)']):
                return "بدون داده"

            # Ensure change_val is float for comparison
            try:
                change_val = float(change_val)
            except (ValueError, TypeError):
                return "خطا در داده تغییر"


            threshold = 0.05 # General threshold, can be index-specific
            if index_name_col in ['NDVI', 'EVI', 'LAI', 'CVI']: # Higher is better
                if change_val > threshold: return "رشد مثبت"
                elif change_val < -threshold: return "تنش/کاهش"
                else: return "ثابت"
            elif index_name_col in ['MSI']: # Lower is better (less stress)
                if change_val < -threshold: return "بهبود (تنش کمتر)"
                elif change_val > threshold: return "تنش بیشتر"
                else: return "ثابت"
            elif index_name_col in ['NDMI']: # Higher is better (more moisture)
                if change_val > threshold: return "بهبود (رطوبت بیشتر)"
                elif change_val < -threshold: return "کاهش رطوبت"
                else: return "ثابت"
            return "نامشخص"

        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)
        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col_format in cols_to_format:
            if col_format in ranking_df_sorted.columns:
                 ranking_df_sorted[col_format] = ranking_df_sorted[col_format].apply(lambda x: f"{float(x):.3f}" if pd.notna(x) and isinstance(x, (int, float)) else ("N/A" if pd.isna(x) else x))

        st.dataframe(ranking_df_sorted, use_container_width=True)

        st.subheader("📊 خلاصه وضعیت مزارع (بر اساس جدول رتبه‌بندی)")
        status_counts = ranking_df_sorted['وضعیت'].value_counts()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            count_positive = status_counts.get("رشد مثبت", 0) + status_counts.get("بهبود (تنش کمتر)", 0) + status_counts.get("بهبود (رطوبت بیشتر)", 0)
            st.metric("🟢 بهبود/رشد", count_positive)
        with col2:
            st.metric("⚪ ثابت", status_counts.get("ثابت", 0))
        with col3:
            count_negative = status_counts.get("تنش/کاهش", 0) + status_counts.get("تنش بیشتر", 0) + status_counts.get("کاهش رطوبت", 0)
            st.metric("🔴 تنش/کاهش", count_negative)
        with col4:
            st.metric("❔ بدون داده/خطا", status_counts.get("بدون داده", 0) + status_counts.get("خطا در داده تغییر",0) + status_counts.get("نامشخص",0) )


        st.info("""
        **توضیحات وضعیت (برای جدول رتبه‌بندی):**
        - **🟢 رشد مثبت/بهبود**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند.
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت نامطلوب‌تری داشته‌اند.
        - **❔ بدون داده/خطا**: اطلاعات کافی برای ارزیابی وضعیت موجود نیست یا خطایی در داده‌ها وجود دارد.
        """)

        csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8-sig') # Added sig for Excel
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")

with tab2:
    st.subheader(f"🗺️ نقشه وضعیت مزارع ({active_farm_name})")
    if is_polygon_analysis_active and active_farm_name != "همه مزارع":
        st.info(f"نمایش نقشه برای مرز بارگذاری شده '{active_farm_name}' (مساحت: {active_farm_area_ha:,.2f} هکتار).")
    elif not is_polygon_analysis_active and active_farm_name != "همه مزارع":
         st.info(f"نمایش نقشه برای نقطه مرکزی مزرعه '{active_farm_name}' (از CSV).")


    vis_params_map = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301']},
        'NDMI': {'min': -1, 'max': 1, 'palette': ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac']}, # Red-Blue
        'LAI': {'min': 0, 'max': 7, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']}, # Sequential Yellow-Orange-Brown
        'MSI': {'min': 0, 'max': 3.5, 'palette': ['#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7', '#fddbc7', '#f4a582', '#d6604d', '#b2182b']}, # Blue-Red (Low stress blue, high stress red)
        'CVI': {'min': 0, 'max': 25, 'palette': ['#FFFFE5', '#FFF7BC', '#FEE391', '#FEC44F', '#FE9929', '#EC7014', '#CC4C02', '#993404', '#662506']},
    }
    
    map_center_lat = INITIAL_LAT
    map_center_lon = INITIAL_LON
    initial_zoom_map_val = INITIAL_ZOOM

    if active_farm_geom:
        try:
            if active_farm_geom.type().getInfo() == 'Point':
                coords = active_farm_geom.coordinates().getInfo()
                map_center_lon, map_center_lat = coords[0], coords[1]
                initial_zoom_map_val = 15 if not is_polygon_analysis_active else 14 # Zoom closer for point
            else: # Polygon or Rectangle
                centroid = active_farm_geom.centroid(maxError=1).coordinates().getInfo()
                map_center_lon, map_center_lat = centroid[0], centroid[1]
                initial_zoom_map_val = 14 # Default for polygons
        except Exception as e_map_center:
            st.warning(f"خطا در تعیین مرکز نقشه: {e_map_center}. از مقادیر پیشفرض استفاده می‌شود.")


    m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=initial_zoom_map_val, add_google_map=True) # Changed to True
    m.add_basemap("HYBRID")
    m.add_basemap("SATELLITE")


    if active_farm_geom:
        gee_image_current, error_msg_current = get_processed_image(
            active_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )
        if gee_image_current:
            try:
                # Clip the image to the farm geometry if it's a polygon for cleaner display
                display_image = gee_image_current
                if is_polygon_analysis_active and active_farm_geom.type().getInfo() != 'Point' and active_farm_name != "همه مزارع":
                    display_image = gee_image_current.clip(active_farm_geom)

                m.addLayer(
                    display_image,
                    vis_params_map.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}),
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )
                
                # Custom Legend
                # ... (legend HTML code from original, ensure it's correct for vis_params_map)
                legend_html_content = ""
                palette_map = vis_params_map.get(selected_index, {})
                # Simpler legend based on common interpretations
                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                    legend_html_content = f'<p style="margin:0; background-color:{palette_map["palette"][-1]}; color:white; padding: 2px;">بالا (مطلوب)</p>' \
                                          f'<p style="margin:0; background-color:{palette_map["palette"][len(palette_map["palette"])//2]}; color:black; padding: 2px;">متوسط</p>' \
                                          f'<p style="margin:0; background-color:{palette_map["palette"][0]}; color:white; padding: 2px;">پایین (نامطلوب)</p>'
                elif selected_index == 'NDMI': # NDMI: Blue for wet, red for dry (using a diverging palette)
                     legend_html_content = f'<p style="margin:0; background-color:{palette_map["palette"][-1]}; color:white; padding: 2px;">مرطوب</p>' \
                                           f'<p style="margin:0; background-color:{palette_map["palette"][len(palette_map["palette"])//2]}; color:black; padding: 2px;">متوسط</p>' \
                                           f'<p style="margin:0; background-color:{palette_map["palette"][0]}; color:white; padding: 2px;">خشک</p>'
                elif selected_index == 'MSI': # MSI: Red for high stress (dry), Blue for low stress (wet)
                     legend_html_content = f'<p style="margin:0; background-color:{palette_map["palette"][-1]}; color:white; padding: 2px;">تنش زیاد (خشک)</p>' \
                                           f'<p style="margin:0; background-color:{palette_map["palette"][len(palette_map["palette"])//2]}; color:black; padding: 2px;">متوسط</p>' \
                                           f'<p style="margin:0; background-color:{palette_map["palette"][0]}; color:white; padding: 2px;">تنش کم (مرطوب)</p>'


                if legend_html_content:
                    legend_html = f'''
                    <div style="position: fixed; bottom: 60px; left: 10px; z-index: 1000; background-color: rgba(255,255,255,0.8); padding: 10px; border: 1px solid grey; border-radius: 5px; font-family: Vazirmatn, sans-serif;">
                        <p style="margin: 0 0 5px 0; font-weight: bold;">راهنمای {selected_index}</p>
                        {legend_html_content}
                    </div>
                    '''
                    m.get_root().html.add_child(folium.Element(legend_html))


                if active_farm_name == "همه مزارع":
                     # For "همه مزارع", show markers from CSV
                     for idx_farm, farm_row in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm_row['عرض جغرافیایی'], farm_row['طول جغرافیایی']],
                             popup=f"مزرعه: {farm_row['مزرعه']}<br>کانال: {farm_row['کانال']}<br>اداره: {farm_row['اداره']}",
                             tooltip=farm_row['مزرعه'], icon=folium.Icon(color='blue', icon='info-sign')
                         ).add_to(m)
                     if active_farm_geom: m.center_object(active_farm_geom, zoom=INITIAL_ZOOM) # Center on bounds
                
                # Handling single farm display (either point from CSV or uploaded polygon)
                elif active_farm_geom:
                    if is_polygon_analysis_active and active_farm_geom.type().getInfo() != 'Point': # Uploaded Polygon
                        try:
                            simplified_geom = active_farm_geom.simplify(maxError=30) # Simplify for display
                            farm_geojson = geemap.ee_to_geojson(ee.FeatureCollection(simplified_geom))
                            folium.GeoJson(
                                farm_geojson,
                                name=f"مرز: {active_farm_name}",
                                style_function=lambda x: {'color': 'yellow', 'weight': 2.5, 'fillOpacity': 0.05}
                            ).add_to(m)
                            m.center_object(active_farm_geom, zoom=initial_zoom_map_val)
                        except Exception as e_geojson:
                            st.error(f"خطا در نمایش مرز مزرعه '{active_farm_name}' روی نقشه: {e_geojson}")
                    
                    elif not is_polygon_analysis_active and active_farm_geom.type().getInfo() == 'Point': # Point from CSV
                        point_coords = active_farm_geom.coordinates().getInfo()
                        folium.Marker(
                             location=[point_coords[1], point_coords[0]], tooltip=f"مزرعه (مرکزی): {active_farm_name}",
                             icon=folium.Icon(color='red', icon='star')
                         ).add_to(m)
                        m.center_object(active_farm_geom, zoom=initial_zoom_map_val)

                m.add_layer_control(position='topright')

            except ee.EEException as map_ee_err:
                st.error(f"خطای GEE در افزودن لایه به نقشه: {map_ee_err}")
            except Exception as map_err:
                st.error(f"خطا در افزودن لایه به نقشه: {map_err}\n{traceback.format_exc()}")
        else:
            st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")
        
        # Display map
        st_folium(m, width=None, height=550, use_container_width=True, returned_objects=[])
        st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها (بالا سمت راست نقشه) برای تغییر نقشه پایه استفاده کنید.")
    else:
        st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده یا خطایی رخ داده است.")


    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index} برای '{active_farm_name}'")
    
    if active_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید (یا مرز آن را بارگذاری نمایید) تا نمودار روند زمانی آن نمایش داده شود.")
    elif active_farm_geom:
        # Time series can be generated for both Point (from CSV) and Polygon (uploaded)
        # get_index_time_series is already adapted for this.
        timeseries_end_date = today.strftime('%Y-%m-%d')
        # Default to 1 year, can be made configurable
        timeseries_start_date_user = st.date_input("تاریخ شروع برای سری زمانی:", 
                                                   value=today - datetime.timedelta(days=365),
                                                   min_value=datetime.date(2015,1,1), # Sentinel-2a launch
                                                   max_value=today - datetime.timedelta(days=14), # At least 2 weeks
                                                   key="ts_start_date")
        
        if st.button("نمایش/به‌روزرسانی نمودار سری زمانی", key="btn_ts_chart"):
            with st.spinner(f"در حال دریافت و ترسیم سری زمانی {selected_index} برای '{active_farm_name}'..."):
                ts_df, ts_error = get_index_time_series(
                    active_farm_geom, selected_index,
                    start_date=timeseries_start_date_user.strftime('%Y-%m-%d'),
                    end_date=timeseries_end_date
                )
                if ts_error:
                    st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
                elif not ts_df.empty:
                    fig = px.line(ts_df, y=selected_index, markers=True,
                                  title=f"روند زمانی {selected_index} برای '{active_farm_name}'")
                    fig.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index, font=dict(family="Vazirmatn"))
                    st.plotly_chart(fig, use_container_width=True)
                    st.caption(f"نمودار تغییرات شاخص {selected_index} برای '{active_farm_name}' از {timeseries_start_date_user.strftime('%Y-%m-%d')} تا {timeseries_end_date}.")
                    if is_polygon_analysis_active and active_farm_geom.type().getInfo() != 'Point':
                        st.caption("مقادیر سری زمانی بر اساس میانگین شاخص در کل سطح مرز بارگذاری شده محاسبه شده‌اند.")
                    else:
                        st.caption("مقادیر سری زمانی بر اساس نقطه مرکزی مزرعه (یا میانگین پیکسل‌های اطراف آن) محاسبه شده‌اند.")
                else:
                    st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
    else:
        st.warning("هندسه مزرعه برای نمودار سری زمانی در دسترس نیست.")


with tab3:
    st.header("💡 تحلیل هوشمند با Gemini")
    st.markdown("""
    **توجه:** پاسخ‌های ارائه شده توسط هوش مصنوعی Gemini بر اساس داده‌های موجود و الگوهای کلی تولید می‌شوند و نباید جایگزین نظر کارشناسان کشاورزی شوند. همیشه برای تصمیم‌گیری‌های مهم با متخصصین مشورت کنید.
    """)

    if not gemini_model:
        st.warning("⚠️ برای استفاده از قابلیت‌های هوشمند، لطفاً کلید API جمینای خود را در نوار کناری وارد کنید.")
    else:
        # Determine context for Gemini based on active_farm_name and active_farm_geom
        # selected_farm_details_tab1 is still relevant for CSV data if selected_farm_name is not "همه مزارع"
        # active_farm_name, is_polygon_analysis_active, active_farm_area_ha are key for Gemini context.
        
        # Prepare farm details string for Gemini prompts
        farm_details_for_gemini = ""
        analysis_basis_str_gemini = ""
        
        if active_farm_name != "همه مزارع":
            farm_details_for_gemini = f"مزرعه مورد نظر: '{active_farm_name}'.\n"
            if is_polygon_analysis_active:
                analysis_basis_str_gemini = f"تحلیل بر اساس مرز دقیق ارائه شده (پلیگون) با مساحت حدود {active_farm_area_ha:,.2f} هکتار انجام می‌شود." if active_farm_area_ha else "تحلیل بر اساس مرز دقیق ارائه شده (پلیگون) انجام می‌شود."
            else: # Point from CSV
                analysis_basis_str_gemini = "تحلیل بر اساس نقطه مرکزی مزرعه از داده‌های CSV انجام می‌شود."
                if active_farm_area_ha: # Area from CSV
                    farm_details_for_gemini += f"مساحت ثبت شده در CSV: {active_farm_area_ha:,.2f} هکتار.\n"

            # Try to get variety from original CSV if a farm is selected
            if not is_polygon_analysis_active and selected_farm_name != "همه مزارع": # i.e. point from CSV
                 csv_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
                 variety_str_gemini = csv_farm_details.get('واریته', 'N/A')
                 farm_details_for_gemini += f"واریته (از CSV): {variety_str_gemini}.\n"
            elif is_polygon_analysis_active and st.session_state.uploaded_geometry_name:
                 # If polygon uploaded, variety might not be known unless user inputs it
                 farm_details_for_gemini += f"واریته: (نا مشخص برای مرز بارگذاری شده، مگر اینکه کاربر ذکر کند).\n"


        st.subheader("💬 پاسخ هوشمند به سوالات در مورد داده‌های مزارع")
        user_farm_q = st.text_input(f"سوال خود را در مورد وضعیت '{active_farm_name}' یا وضعیت کلی مزارع روز '{selected_day}' بپرسید:", key="gemini_farm_q")
        if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q"):
            if not user_farm_q:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. {analysis_basis_str_gemini}\n"
                context_data = ""

                if active_farm_name != "همه مزارع":
                    context_data += farm_details_for_gemini
                    # Try to get current week's data for this farm from the ranking table
                    # Note: ranking_df_sorted is based on selected_farm_name (from CSV), not active_farm_name (which could be uploaded KML name)
                    # So we need to match selected_farm_name if we want data from the table.
                    farm_data_for_prompt = pd.DataFrame() # Initialize
                    if selected_farm_name != "همه مزارع" and not ranking_df_sorted.empty: # Check if a CSV farm is selected
                        farm_data_for_prompt = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                    
                    if not farm_data_for_prompt.empty:
                        current_val_str = farm_data_for_prompt[f'{selected_index} (هفته جاری)'].iloc[0]
                        prev_val_str = farm_data_for_prompt[f'{selected_index} (هفته قبل)'].iloc[0]
                        change_str = farm_data_for_prompt['تغییر'].iloc[0]
                        status_str = farm_data_for_prompt['وضعیت'].iloc[0]
                        context_data += f"داده‌های مزرعه '{selected_farm_name}' (از جدول رتبه‌بندی نقاط مرکزی) برای شاخص {selected_index} (هفته منتهی به {end_date_current_str}):\n" \
                                       f"- مقدار هفته جاری: {current_val_str}\n" \
                                       f"- مقدار هفته قبل: {prev_val_str}\n" \
                                       f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                                       f"- وضعیت کلی: {status_str}\n"
                        if is_polygon_analysis_active:
                             context_data += f"توجه: تحلیل درخواستی شما برای '{active_farm_name}' بر اساس مرز دقیق آن است، در حالی که این داده‌های هفتگی از نقطه مرکزی '{selected_farm_name}' در CSV استخراج شده‌اند. این دو ممکن است متفاوت باشند.\n"
                    else:
                        context_data += f"داده‌های عددی هفتگی (مقدار جاری، قبلی، تغییر) برای '{active_farm_name}' از جدول رتبه‌بندی در دسترس نیست (ممکن است مرز بارگذاری شده با نام‌های جدول مطابقت نداشته باشد یا جدول خالی باشد).\n"
                    
                    prompt += f"کاربر در مورد '{active_farm_name}' سوالی پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."

                else: # "همه مزارع"
                    context_data = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{selected_index}' در حال بررسی است. تعداد {len(filtered_farms_df)} مزرعه در این روز فیلتر شده‌اند."
                    if not ranking_df_sorted.empty:
                        context_data += f"\nخلاصه وضعیت مزارع (بر اساس نقاط مرکزی از CSV) برای شاخص {selected_index}:\n"
                        # Re-fetch status counts as they might have been updated
                        status_counts_gemini = ranking_df_sorted['وضعیت'].value_counts()
                        count_positive_gemini = status_counts_gemini.get("رشد مثبت", 0) + status_counts_gemini.get("بهبود (تنش کمتر)", 0) + status_counts_gemini.get("بهبود (رطوبت بیشتر)", 0)
                        count_negative_gemini = status_counts_gemini.get("تنش/کاهش", 0) + status_counts_gemini.get("تنش بیشتر", 0) + status_counts_gemini.get("کاهش رطوبت", 0)
                        count_nodata_gemini = status_counts_gemini.get("بدون داده", 0) + status_counts_gemini.get("خطا در داده تغییر",0) + status_counts_gemini.get("نامشخص",0)

                        context_data += f"- تعداد مزارع با بهبود/رشد: {count_positive_gemini}\n"
                        context_data += f"- تعداد مزارع با وضعیت ثابت: {status_counts_gemini.get('ثابت', 0)}\n"
                        context_data += f"- تعداد مزارع با تنش/کاهش: {count_negative_gemini}\n"
                        context_data += f"- تعداد مزارع بدون داده/خطا: {count_nodata_gemini}\n"
                    prompt += f"کاربر سوالی در مورد وضعیت کلی مزارع پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."

                with st.spinner("در حال پردازش پاسخ با Gemini..."):
                    response = ask_gemini(prompt)
                    st.markdown(response)
        st.markdown("---")

        st.subheader("📄 تولید گزارش خودکار هفتگی")
        if active_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تولید گزارش انتخاب کنید (یا مرز آن را بارگذاری نمایید).")
        # elif selected_farm_details_tab1 is None and not is_polygon_analysis_active: # This condition needs review
        #     st.info(f"داده‌های جزئی برای مزرعه {active_farm_name} یافت نشد.")
        elif ranking_df_sorted.empty and selected_farm_name == "همه مزارع": # Check if ranking data available
             st.info(f"داده‌های رتبه‌بندی برای هفته جاری جهت تولید گزارش کلی موجود نیست.")
        elif selected_farm_name == "همه مزارع" and st.session_state.uploaded_geometry is None:
             st.info(f"لطفا یک مزرعه خاص را انتخاب کنید یا مرز آن را بارگذاری کنید.")

        else: # A specific farm (CSV or uploaded) is active
            # We need data from ranking_df_sorted for current/prev values
            # This data is tied to 'selected_farm_name' (the one from CSV dropdown)
            farm_data_for_report = pd.DataFrame()
            if selected_farm_name != "همه مزارع" and not ranking_df_sorted.empty:
                farm_data_for_report = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]

            if farm_data_for_report.empty and not is_polygon_analysis_active :
                st.info(f"داده‌های رتبه‌بندی (مقادیر هفتگی) برای مزرعه '{selected_farm_name}' از CSV جهت تولید گزارش موجود نیست.")
            # Allow report generation for uploaded polygon even if no matching CSV data, but it will be limited
            elif st.button(f"📝 تولید گزارش برای '{active_farm_name}'", key="btn_gemini_report"):
                report_context = farm_details_for_gemini # Already has name, area, analysis_basis
                
                if not farm_data_for_report.empty:
                    current_val_str = farm_data_for_report[f'{selected_index} (هفته جاری)'].iloc[0]
                    prev_val_str = farm_data_for_report[f'{selected_index} (هفته قبل)'].iloc[0]
                    change_str = farm_data_for_report['تغییر'].iloc[0]
                    status_str = farm_data_for_report['وضعیت'].iloc[0]
                    report_context += f"داده‌های شاخص {selected_index} ({index_options[selected_index]}) برای '{selected_farm_name}' (از نقطه مرکزی CSV) در هفته منتهی به {end_date_current_str}:\n" \
                                      f"- مقدار شاخص در هفته جاری: {current_val_str}\n" \
                                      f"- مقدار شاخص در هفته قبل: {prev_val_str}\n" \
                                      f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                                      f"- وضعیت کلی بر اساس تغییرات: {status_str}\n"
                    if is_polygon_analysis_active and active_farm_name != selected_farm_name:
                         report_context += f"توجه: گزارش برای '{active_farm_name}' (مرز بارگذاری شده) است، اما داده‌های عددی هفتگی از نقطه مرکزی '{selected_farm_name}' در CSV هستند.\n"
                else:
                     report_context += f"داده‌های عددی هفتگی (مقدار جاری، قبلی، تغییر) برای شاخص {selected_index} از جدول رتبه‌بندی در دسترس نیست. تحلیل را بر اساس اطلاعات کلی {active_farm_name} انجام دهید.\n"


                prompt = f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت '{active_farm_name}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n" \
                         f"اطلاعات موجود:\n{report_context}\n" \
                         f"{analysis_basis_str_gemini}\n\n" \
                         f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت (با توجه به شاخص {selected_index}) ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی و قطعی) برای بهبود یا حفظ وضعیت مطلوب بیان کنید. اگر داده‌های عددی هفتگی موجود نیست، بر اهمیت پایش میدانی تاکید کنید. گزارش باید رسمی و قابل فهم برای مدیران کشاورزی باشد."

                with st.spinner(f"در حال تولید گزارش برای '{active_farm_name}' با Gemini..."):
                    response = ask_gemini(prompt, temperature=0.6, top_p=0.9)
                    st.markdown(f"### گزارش هفتگی '{active_farm_name}' (شاخص {selected_index})")
                    st.markdown(f"**تاریخ گزارش:** {datetime.date.today().strftime('%Y-%m-%d')}")
                    st.markdown(f"**بازه زمانی مورد بررسی:** {start_date_current_str} الی {end_date_current_str}")
                    st.markdown(response)
        st.markdown("---")

        st.subheader(f"📉 تحلیل تغییرات شاخص {selected_index} (سری زمانی) برای '{active_farm_name}'")
        if active_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تحلیل سری زمانی انتخاب کنید (یا مرز آن را بارگذاری نمایید).")
        elif active_farm_geom:
            if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{active_farm_name}'", key="btn_gemini_timeseries"):
                # Use a fixed period for Gemini analysis for consistency, e.g., last 6 months
                timeseries_end_date_gemini = today.strftime('%Y-%m-%d')
                timeseries_start_date_gemini = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d')
                
                with st.spinner(f"در حال دریافت داده‌های سری زمانی برای تحلیل Gemini..."):
                    ts_df_gemini, ts_error_gemini = get_index_time_series(
                        active_farm_geom, selected_index,
                        start_date=timeseries_start_date_gemini, end_date=timeseries_end_date_gemini
                    )

                if ts_error_gemini:
                    st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini}")
                elif not ts_df_gemini.empty:
                    ts_summary = f"داده‌های سری زمانی شاخص {selected_index} برای '{active_farm_name}' در 6 ماه گذشته (از {timeseries_start_date_gemini} تا {timeseries_end_date_gemini}):\n"
                    # Provide a sample of the data to Gemini to keep prompt concise
                    sample_freq = max(1, len(ts_df_gemini) // 10) # Aim for ~10 data points
                    ts_summary += ts_df_gemini.iloc[::sample_freq].to_string(header=True, index=True)
                    ts_summary += f"\nمقدار اولیه حدود {ts_df_gemini[selected_index].iloc[0]:.3f} و مقدار نهایی حدود {ts_df_gemini[selected_index].iloc[-1]:.3f} بوده است."
                    ts_summary += f"\n میانگین مقدار در این دوره: {ts_df_gemini[selected_index].mean():.3f}, کمترین مقدار: {ts_df_gemini[selected_index].min():.3f}, بیشترین مقدار: {ts_df_gemini[selected_index].max():.3f}."
                    
                    prompt = f"شما یک تحلیلگر داده‌های کشاورزی خبره هستید. {analysis_basis_str_gemini}\n بر اساس داده‌های سری زمانی زیر برای شاخص {selected_index} ({index_options[selected_index]}) مزرعه '{active_farm_name}' طی 6 ماه گذشته:\n{ts_summary}\n" \
                             f"۱. روند کلی تغییرات شاخص (افزایشی، کاهشی، نوسانی، ثابت) را توصیف کنید.\n" \
                             f"۲. آیا دوره‌های خاصی از رشد سریع، کاهش شدید یا ثبات طولانی مدت مشاهده می‌شود؟ اگر بله، در چه بازه‌های زمانی تقریبی؟\n" \
                             f"۳. با توجه به ماهیت شاخص {selected_index} و روند مشاهده شده، چه تفسیرهای اولیه‌ای می‌توان داشت؟ (مثلاً آیا با مراحل رشد گیاه نیشکر یا تغییرات فصلی معمول همخوانی دارد؟)\n" \
                             f"۴. چه نوع مشاهدات میدانی یا اطلاعات تکمیلی می‌تواند به درک بهتر این روند کمک کند؟\n" \
                             f"پاسخ به زبان فارسی، ساختاریافته، تحلیلی و کاربردی باشد."
                    with st.spinner(f"در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.5)
                        st.markdown(response)
                else:
                    st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای '{active_farm_name}' در 6 ماه گذشته یافت نشد.")
        st.markdown("---")

        # New Section: Anomaly Discussion
        st.subheader(f"🚨 بحث در مورد ناهنجاری‌های احتمالی شاخص {selected_index} برای '{selected_farm_name}'")
        if active_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای این تحلیل انتخاب کنید (یا مرز آن را بارگذاری نمایید).")
        elif selected_farm_name == "همه مزارع" and not st.session_state.uploaded_geometry : # User has "همه مزارع" and no KML
             st.info("لطفاً یک مزرعه خاص از لیست CSV انتخاب کنید تا داده‌های هفتگی آن برای بحث بارگذاری شود.")
        elif ranking_df_sorted.empty:
            st.info(f"داده‌های رتبه‌بندی (مقادیر هفتگی از CSV) برای مزارع جهت تحلیل ناهنجاری موجود نیست.")
        else:
            # Data for anomaly discussion always comes from the ranking table (CSV point data)
            # because it's about week-to-week *change* which is calculated there.
            farm_data_for_anomaly = pd.DataFrame()
            if selected_farm_name != "همه مزارع": # A specific farm is selected from CSV dropdown
                farm_data_for_anomaly = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]

            if not farm_data_for_anomaly.empty:
                current_val_str_anom = farm_data_for_anomaly[f'{selected_index} (هفته جاری)'].iloc[0]
                prev_val_str_anom = farm_data_for_anomaly[f'{selected_index} (هفته قبل)'].iloc[0]
                change_str_anom = farm_data_for_anomaly['تغییر'].iloc[0]
                status_str_anom = farm_data_for_anomaly['وضعیت'].iloc[0]

                st.markdown(f"""
                تحلیل ناهنجاری برای مزرعه **'{selected_farm_name}'** (بر اساس داده‌های نقطه مرکزی از CSV):
                - شاخص **{selected_index}** هفته جاری: **{current_val_str_anom}**
                - شاخص **{selected_index}** هفته قبل: **{prev_val_str_anom}**
                - تغییر محاسبه شده: **{change_str_anom}**
                - وضعیت ارزیابی شده: **{status_str_anom}**
                """)
                if is_polygon_analysis_active:
                    st.caption(f"توجه: شما در حال مشاهده نقشه و سری زمانی برای '{active_farm_name}' (مرز بارگذاری شده) هستید، اما این بخش از تحلیل ناهنجاری از داده‌های هفتگی نقطه مرکزی '{selected_farm_name}' در CSV استفاده می‌کند.")


                if st.button(f"بحث در مورد تغییرات شاخص {selected_index} برای '{selected_farm_name}' با Gemini", key="btn_gemini_anomaly"):
                    # Context for Gemini about the basis of its current view vs anomaly data
                    anomaly_context_prompt = f"تحلیل زیر مربوط به مزرعه '{selected_farm_name}' است و داده‌های تغییرات هفتگی از نقطه مرکزی آن در CSV استخراج شده‌اند.\n"
                    if is_polygon_analysis_active and active_farm_name != selected_farm_name:
                        anomaly_context_prompt += f"کاربر همچنین در حال بررسی مرز دقیق '{active_farm_name}' است که ممکن است با '{selected_farm_name}' متفاوت باشد.\n"
                    elif is_polygon_analysis_active and active_farm_name == selected_farm_name: # KML uploaded has same name as CSV entry
                         anomaly_context_prompt = f"تحلیل زیر مربوط به مزرعه '{selected_farm_name}' است. داده‌های تغییرات هفتگی از نقطه مرکزی آن در CSV استخراج شده‌اند, اما کاربر مرز دقیق این مزرعه را نیز برای تحلیل‌های دیگر بارگذاری کرده است (مساحت: {active_farm_area_ha:,.2f} هکتار).\n"


                    prompt = f"شما یک کارشناس کشاورزی و تحلیلگر داده‌های سنجش از دور هستید.\n" \
                             f"{anomaly_context_prompt}" \
                             f"برای مزرعه '{selected_farm_name}', شاخص {selected_index} ({index_options[selected_index]}) اطلاعات زیر را داریم (از داده‌های نقطه مرکزی CSV):\n" \
                             f"- مقدار هفته جاری: {current_val_str_anom}\n" \
                             f"- مقدار هفته قبل: {prev_val_str_anom}\n" \
                             f"- تغییر محاسبه شده: {change_str_anom}\n" \
                             f"- وضعیت کلی ارزیابی شده: {status_str_anom}\n\n" \
                             f"با توجه به این تغییرات، لطفاً به سوالات زیر پاسخ دهید:\n" \
                             f"1. آیا این میزان تغییر برای شاخص {selected_index} در یک هفته برای نیشکر قابل توجه یا نگران کننده تلقی می‌شود؟ چرا؟ (توضیح دهید که چه عواملی طبیعی یا غیرطبیعی می‌توانند باعث چنین تغییری شوند).\n" \
                             f"2. اگر این تغییر نشانه‌ای از یک مشکل یا بهبود ناگهانی (ناهنجاری) باشد، چه نوع بررسی‌های میدانی یا اقدامات اولیه برای تأیید و شناسایی علت اصلی پیشنهاد می‌کنید؟\n" \
                             f"3. چه اطلاعات تکمیلی (مثلاً داده‌های هواشناسی دقیق برای منطقه، نوع و تاریخ عملیات زراعی اخیر، مشاهدات آفات و بیماری‌ها) می‌تواند به تفسیر بهتر این تغییر کمک کند؟\n" \
                             f"پاسخ به زبان فارسی، ساختاریافته، کاربردی و با در نظر گرفتن مراحل مختلف رشد نیشکر (در صورت امکان) باشد."

                    with st.spinner(f"در حال تحلیل تغییرات با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.65, top_k=35)
                        st.markdown(response)
            else:
                st.info(f"داده‌های رتبه‌بندی (مقادیر هفتگی) برای مزرعه '{selected_farm_name}' از CSV جهت بحث در مورد ناهنجاری یافت نشد. لطفاً یک مزرعه از لیست انتخاب کنید.")

        st.markdown("---")
        st.subheader("🌱 پیشنهاد اقدامات کشاورزی عمومی")
        if active_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای دریافت پیشنهادات انتخاب کنید (یا مرز آن را بارگذاری نمایید).")
        elif selected_farm_name == "همه مزارع" and not st.session_state.uploaded_geometry :
             st.info(f"لطفاً یک مزرعه خاص از لیست CSV انتخاب کنید تا داده‌های هفتگی آن برای ارائه پیشنهاد بارگذاری شود.")
        elif ranking_df_sorted.empty :
             st.info(f"داده‌های رتبه‌بندی (مقادیر هفتگی از CSV) برای ارائه پیشنهاد موجود نیست.")
        else:
            farm_data_for_actions = pd.DataFrame()
            if selected_farm_name != "همه مزارع": # A specific farm is selected from CSV dropdown
                farm_data_for_actions = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]

            if not farm_data_for_actions.empty:
                if st.button(f"💡 دریافت پیشنهادات برای '{selected_farm_name}' (بر اساس داده CSV)", key="btn_gemini_actions"):
                    current_val_act_str = farm_data_for_actions[f'{selected_index} (هفته جاری)'].iloc[0]
                    status_act_str = farm_data_for_actions['وضعیت'].iloc[0]
                    
                    action_context_prompt = f"تحلیل زیر مربوط به مزرعه '{selected_farm_name}' است و داده‌های شاخص از نقطه مرکزی آن در CSV استخراج شده‌اند.\n"
                    if is_polygon_analysis_active and active_farm_name != selected_farm_name:
                        action_context_prompt += f"کاربر همچنین در حال بررسی مرز دقیق '{active_farm_name}' است که ممکن است با '{selected_farm_name}' متفاوت باشد. پیشنهادات را برای '{selected_farm_name}' ارائه دهید.\n"
                    elif is_polygon_analysis_active and active_farm_name == selected_farm_name:
                         action_context_prompt = f"تحلیل زیر مربوط به مزرعه '{selected_farm_name}' است. داده‌های شاخص از نقطه مرکزی آن در CSV استخراج شده‌اند, اما کاربر مرز دقیق این مزرعه را نیز برای تحلیل‌های دیگر بارگذاری کرده است (مساحت: {active_farm_area_ha:,.2f} هکتار).\n"


                    prompt = f"شما یک مشاور کشاورزی هوشمند برای کشت نیشکر هستید.\n" \
                             f"{action_context_prompt}" \
                             f"برای مزرعه '{selected_farm_name}', شاخص {selected_index} ({index_options[selected_index]}) در هفته جاری (بر اساس داده نقطه مرکزی CSV) مقدار {current_val_act_str} را نشان می‌دهد و وضعیت کلی آن '{status_act_str}' ارزیابی شده است.\n" \
                             f"بر اساس این اطلاعات:\n" \
                             f"۱. تفسیر مختصری از مقدار فعلی شاخص {selected_index} ارائه دهید (مثلاً اگر NDVI پایین است، به چه معناست؟ اگر MSI بالاست، چه مفهومی دارد؟ اهمیت این مقدار برای نیشکر چیست؟).\n" \
                             f"۲. با توجه به مقدار شاخص و وضعیت ارزیابی شده ('{status_act_str}'), چه نوع بررسی‌های میدانی یا اقدامات عمومی کشاورزی (مانند نیاز به بررسی آبیاری، احتمال نیاز به عناصر غذایی خاص، اهمیت پایش آفات و بیماری‌ها، مدیریت بقایای گیاهی اگر مرتبط است) ممکن است لازم باشد؟ لطفاً پیشنهادات کلی، عملیاتی و غیر تخصصی (بدون توصیه دوز دقیق کود یا سم) ارائه دهید.\n" \
                             f"۳. تاکید کنید که این پیشنهادات کلی هستند و تصمیم نهایی باید با بازدید میدانی و نظر کارشناس مزرعه باشد.\n" \
                             f"پاسخ به زبان فارسی و به صورت عملیاتی و شماره‌گذاری شده باشد."

                    with st.spinner("در حال دریافت پیشنهادات کشاورزی با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.7, top_k=30)
                        st.markdown(response)
            else:
                st.info(f"داده‌های رتبه‌بندی (مقادیر هفتگی) برای مزرعه '{selected_farm_name}' از CSV جهت ارائه پیشنهاد یافت نشد. لطفاً یک مزرعه از لیست انتخاب کنید.")
        st.markdown("---")

        st.subheader("🗣️ پاسخ به سوالات عمومی کاربران")
        user_general_q = st.text_input("سوال عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور، نیشکر یا این سامانه بپرسید:", key="gemini_general_q")
        if st.button("❓ پرسیدن سوال از Gemini", key="btn_gemini_general_q"):
            if not user_general_q:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی (با تمرکز بر نیشکر) و سنجش از دور هستید. لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. سعی کنید پاسخ شما ساده، قابل فهم، دقیق و در حد امکان جامع باشد.\n\nسوال کاربر: '{user_general_q}'"
                
                # Heuristic for common questions about map colors
                if ("قرمز" in user_general_q or "زرد" in user_general_q or "سبز" in user_general_q) and \
                   ("نقشه" in user_general_q or "مزرعه من" in user_general_q) and \
                   selected_index in ['NDVI', 'EVI', 'LAI', 'CVI', 'MSI', 'NDMI']: # Indices with color palettes
                    
                    color_prompt_context = f"کاربر در مورد رنگ‌ها روی نقشه سوالی پرسیده: '{user_general_q}'.\n"
                    color_prompt_context += f"شاخص فعال روی نقشه {selected_index} ({index_options[selected_index]}) است.\n"
                    color_prompt_context += f"پالت رنگی مورد استفاده برای {selected_index} بدین شرح است:\n"
                    palette_info = vis_params_map.get(selected_index, {})
                    if palette_info:
                         color_prompt_context += f"- مقادیر پایین شاخص به سمت رنگ(های) ابتدای لیست مانند '{palette_info['palette'][0]}' نمایش داده می‌شوند.\n"
                         color_prompt_context += f"- مقادیر بالای شاخص به سمت رنگ(های) انتهای لیست مانند '{palette_info['palette'][-1]}' نمایش داده می‌شوند.\n"

                    if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']: # Higher is better (often green)
                        color_prompt_context += f"برای این شاخص‌ها، مقادیر بالاتر (معمولاً سبزتر) نشان دهنده پوشش گیاهی سالم‌تر و بیشتر است و مقادیر پایین‌تر (معمولاً به سمت زرد/قرمز) نشان دهنده پوشش گیاهی کمتر یا تحت تنش است.\n"
                    elif selected_index == 'NDMI': # Higher (blue) is more moisture
                        color_prompt_context += f"برای NDMI، مقادیر بالاتر (معمولاً آبی‌تر) نشان دهنده رطوبت بیشتر و مقادیر پایین‌تر (معمولاً به سمت قرمز/قهوه‌ای) نشان دهنده خشکی بیشتر است.\n"
                    elif selected_index == 'MSI': # Lower (blue) is less stress (more moisture)
                        color_prompt_context += f"برای MSI، مقادیر پایین‌تر (معمولاً آبی‌تر) نشان دهنده تنش رطوبتی کمتر (رطوبت بیشتر) و مقادیر بالاتر (معمولاً به سمت قرمز/قهوه‌ای) نشان دهنده تنش رطوبتی بیشتر (خشکی) است.\n"

                    if active_farm_name != "همه مزارع" and not ranking_df_sorted.empty and selected_farm_name != "همه مزارع":
                        farm_data_color = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                        if not farm_data_color.empty:
                            current_val_color = farm_data_color[f'{selected_index} (هفته جاری)'].iloc[0]
                            color_prompt_context += f"مقدار فعلی شاخص {selected_index} برای مزرعه '{selected_farm_name}' (از نقطه مرکزی CSV) حدود {current_val_color} است.\n"
                    
                    prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید.\n{color_prompt_context}\n لطفاً با توجه به این اطلاعات، توضیح دهید که رنگ‌های مختلف روی نقشه برای شاخص {selected_index} چه مفهومی دارند و اگر کاربر رنگ خاصی (مثلاً قرمز) را برای مزرعه‌اش مشاهده می‌کند، به چه معنا می‌تواند باشد و چه بررسی‌های عمومی ممکن است لازم باشد. پاسخ به زبان فارسی."

                with st.spinner("در حال جستجو برای پاسخ با Gemini..."):
                    response = ask_gemini(prompt, temperature=0.4)
                    st.markdown(response)

st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط [اسماعیل کیانی] با استفاده از Streamlit, Google Earth Engine, geemap و Gemini API")
st.sidebar.markdown("🌾 شرکت کشت و صنعت دهخدا")
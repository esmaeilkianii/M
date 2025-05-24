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
import google.generativeai as genai # Added for Gemini

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

html, body, .main {
    font-family: 'Vazirmatn', sans-serif;
    background: linear-gradient(to top right, #d0f0ff, #ffffff);
    color: #2c3e50;
}

h1, h2, h3 {
    text-align: right;
    font-weight: 700;
    color: #1a1a1a;
}

.stMetric, .css-1xarl3l {
    background: rgba(255, 255, 255, 0.25);
    border-radius: 20px;
    padding: 1rem;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.18);
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.stButton > button {
    background: rgba(255, 255, 255, 0.2);
    border: none;
    border-radius: 12px;
    padding: 0.6rem 1.2rem;
    color: #1a1a1a;
    font-weight: bold;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    transition: all 0.3s ease;
}

.stButton > button:hover {
    background: rgba(255, 255, 255, 0.35);
    transform: translateY(-2px);
}

.stDataFrame, .dataframe {
    background: rgba(255, 255, 255, 0.35);
    border-radius: 10px;
    backdrop-filter: blur(6px);
    text-align: right;
    font-family: 'Vazirmatn', sans-serif;
}

.css-1d391kg {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255, 255, 255, 0.3);
}

.stTabs [data-baseweb="tab"] {
    background: rgba(255, 255, 255, 0.2);
    color: #1a1a1a;
    border-radius: 12px 12px 0 0;
    font-family: 'Vazirmatn', sans-serif;
    padding: 0.8rem 1.2rem;
    font-weight: 600;
}

.stTabs [data-baseweb="tab"]:hover {
    background: rgba(255, 255, 255, 0.4);
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
def load_farm_data():
    """Loads farm data from GEE FeatureCollection."""
    try:
        # Load Shapefile from GEE Assets
        fc = ee.FeatureCollection('projects/ee-esmaeilkiani13877/assets/Croplogging-Farm')
        
        # Extract features and properties
        features = fc.getInfo()['features']
        
        farm_data = []
        for f in features:
            props = f['properties']
            geom = f['geometry']
            
            # Extract coordinates (assuming Point geometry)
            # Handle cases where geometry might be missing or not a Point
            lon, lat = (None, None)
            if geom and geom.get('type') == 'Point' and geom.get('coordinates'):
                coords = geom['coordinates']
                if len(coords) == 2:
                    lon, lat = coords[0], coords[1]
            
            farm_data.append({
                'مزرعه': props.get('farm', 'N/A'),
                'طول جغرافیایی': lon,
                'عرض جغرافیایی': lat,
                'روزهای هفته': props.get('Day', 'N/A'), # Assuming 'Day' field exists
                'مساحت': props.get('Area', 0), # Assuming 'Area' field exists
                'واریته': props.get('Variety', 'N/A'), # Assuming 'Variety' field exists
                'اداره': props.get('edare', 'N/A'), # Assuming 'edare' field exists
                'کانال': props.get('group', 'N/A'), # Assuming 'group' field exists
                'سن': props.get('Age', 'N/A'), # Assuming 'Age' field exists
                'coordinates_missing': lon is None or lat is None
            })
        
        df = pd.DataFrame(farm_data)
        
        # Data cleaning
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
        if not all(col in df.columns for col in required_cols):
            st.error(f"❌ داده‌های بارگذاری شده از GEE شامل ستون‌های ضروری نیست: {', '.join(required_cols)}")
            # Attempt to create missing columns with default values if appropriate
            for col in required_cols:
                if col not in df.columns:
                    if col == 'coordinates_missing':
                        df[col] = True # Default to True if other coordinate columns are missing
                    elif col in ['طول جغرافیایی', 'عرض جغرافیایی']:
                        df[col] = pd.NA # Use pandas NA for numeric missing
                    else:
                        df[col] = 'N/A' # Default string for other missing text columns
            # Re-check after attempting to fix
            if not all(col in df.columns for col in required_cols):
                 st.error("بعضی از ستون‌های ضروری پس از تلاش برای ایجاد پیش‌فرض، هنوز موجود نیستند.")
                 return None


        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['coordinates_missing'] = df['coordinates_missing'].fillna(True).astype(bool) # Default to True if missing
        
        # Ensure 'روزهای هفته' is string and stripped, handle potential NaN before astype(str)
        df['روزهای هفته'] = df['روزهای هفته'].fillna('N/A').astype(str).str.strip()

        df = df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی']) # Keep this
        df = df[~df['coordinates_missing']] # Keep this
        
        if df.empty:
            st.warning("⚠️ داده معتبری برای مزارع یافت نشد (پس از حذف رکوردهای بدون مختصات یا با مختصات نامعتبر از GEE).")
            return None

        st.success(f"✅ داده‌های {len(df)} مزرعه با موفقیت از Google Earth Engine بارگذاری شد.")
        return df
        
    except ee.EEException as e:
        st.error(f"خطا در بارگذاری داده از GEE: {e}")
        st.error("لطفاً از صحت نام Asset در GEE و دسترسی به آن اطمینان حاصل کنید.")
        return None
    except Exception as e:
        st.error(f"❌ خطا در پردازش داده‌های مزارع از GEE: {e}")
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
# Gemini API Configuration
# ==============================================================================
st.sidebar.subheader("✨ تنظیمات هوش مصنوعی Gemini")
GEMINI_API_KEY = st.sidebar.text_input("🔑 کلید API جمینای خود را وارد کنید:", type="password", help="برای استفاده از قابلیت‌های هوشمند، کلید API خود را از Google AI Studio دریافت و وارد کنید.")

gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest') # Using a recent model
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
        # Configuration for generation
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_output_tokens=2048 # Adjust as needed
        )
        response = gemini_model.generate_content(prompt_text, generation_config=generation_config)
        return response.text
    except Exception as e:
        return f"خطا در ارتباط با Gemini API: {e}\n{traceback.format_exc()}"


# ==============================================================================
# Sidebar Filters
# ==============================================================================
st.sidebar.header("تنظیمات نمایش")

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
    help="مزرعه‌ای که می‌خواهید جزئیات آن را ببینید یا 'همه مزارع' برای نمایش کلی."
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
    days_ago = (today.weekday() - target_weekday + 7) % 7
    end_date_current = today - datetime.timedelta(days=days_ago if days_ago !=0 else 0) # Corrected logic for today
    if today.weekday() == target_weekday: # If today is the selected day
        end_date_current = today
    else: # Find the most recent past selected_day
        days_to_subtract = (today.weekday() - target_weekday + 7) % 7
        end_date_current = today - datetime.timedelta(days=days_to_subtract)


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
    good_quality = scl.remap([4, 5, 6, 7, 11], [1, 1, 1, 1, 1], 0)
    opticalBands = image.select('B.*').multiply(0.0001)
    return image.addBands(opticalBands, None, True).updateMask(mask).updateMask(good_quality)

def add_indices(image):
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        {'NIR': image.select('B8'), 'RED': image.select('B4'), 'BLUE': image.select('B2')}
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.expression('SWIR1 / NIR', {'SWIR1': image.select('B11'), 'NIR': image.select('B8')}).rename('MSI')
    lai = ndvi.multiply(3.5).rename('LAI')
    green_safe = image.select('B3').max(ee.Image(0.0001))
    cvi = image.expression('(NIR / GREEN) * (RED / GREEN)',
        {'NIR': image.select('B8'), 'GREEN': green_safe, 'RED': image.select('B4')}
    ).rename('CVI')
    return image.addBands([ndvi, evi, ndmi, msi, lai, cvi])

@st.cache_data(show_spinner="در حال پردازش تصاویر ماهواره‌ای...", persist=True)
def get_processed_image(_geometry, start_date, end_date, index_name):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds))
        count = s2_sr_col.size().getInfo()
        if count == 0:
            return None, f"No cloud-free Sentinel-2 images found for {start_date} to {end_date}."
        indexed_col = s2_sr_col.map(add_indices)
        median_image = indexed_col.median()
        output_image = median_image.select(index_name)
        return output_image, None
    except ee.EEException as e:
        error_message = f"خطای Google Earth Engine: {e}"
        try:
            error_details = e.args[0] if e.args else str(e)
            if isinstance(error_details, str) and 'computation timed out' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل حجم بالای پردازش یا بازه زمانی طولانی)"
            elif isinstance(error_details, str) and 'user memory limit exceeded' in error_details.lower():
                 error_message += "\n(احتمالاً به دلیل پردازش منطقه بزرگ یا عملیات پیچیده)"
        except Exception: pass
        return None, error_message
    except Exception as e:
        return None, f"خطای ناشناخته در پردازش GEE: {e}\n{traceback.format_exc()}"

@st.cache_data(show_spinner="در حال دریافت سری زمانی شاخص...", persist=True)
def get_index_time_series(_point_geom, index_name, start_date='2023-01-01', end_date=today.strftime('%Y-%m-%d')):
    try:
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_point_geom)
                     .filterDate(start_date, end_date)
                     .map(maskS2clouds)
                     .map(add_indices))
        def extract_value(image):
            value = image.reduceRegion(
                reducer=ee.Reducer.first(), geometry=_point_geom, scale=10
            ).get(index_name)
            return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), index_name: value})
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
        return pd.DataFrame(columns=['date', index_name]), f"خطای GEE در دریافت سری زمانی: {e}"
    except Exception as e:
        return pd.DataFrame(columns=['date', index_name]), f"خطای ناشناخته در دریافت سری زمانی: {e}\n{traceback.format_exc()}"

# ==============================================================================
# Main Panel Display
# ==============================================================================
tab1, tab2, tab3 = st.tabs(["📊 داشبورد اصلی", "🗺️ نقشه و نمودارها", "💡 تحلیل هوشمند با Gemini"])

with tab1:
    st.header(APP_TITLE)
    st.subheader(APP_SUBTITLE)

    selected_farm_details = None
    selected_farm_geom = None
    lat, lon = INITIAL_LAT, INITIAL_LON # Default values

    if selected_farm_name == "همه مزارع":
        min_lon_df, min_lat_df = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
        max_lon_df, max_lat_df = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
        selected_farm_geom = ee.Geometry.Rectangle([min_lon_df, min_lat_df, max_lon_df, max_lat_df])
        st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
        st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
    else:
        selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
        lat = selected_farm_details['عرض جغرافیایی']
        lon = selected_farm_details['طول جغرافیایی']
        selected_farm_geom = ee.Geometry.Point([lon, lat])
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

    st.markdown("---")
    st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
    st.markdown("مقایسه مقادیر متوسط شاخص در هفته جاری با هفته قبل.")

    @st.cache_data(show_spinner=f"در حال محاسبه {selected_index} برای مزارع...", persist=True)
    def calculate_weekly_indices(_farms_df, index_name, start_curr, end_curr, start_prev, end_prev):
        results = []
        errors = []
        total_farms = len(_farms_df)
        progress_bar = st.progress(0)
        for i, (idx, farm) in enumerate(_farms_df.iterrows()):
            farm_name = farm['مزرعه']
            _lat = farm['عرض جغرافیایی']
            _lon = farm['طول جغرافیایی']
            point_geom = ee.Geometry.Point([_lon, _lat])
            def get_mean_value(start, end):
                try:
                    image, error = get_processed_image(point_geom, start, end, index_name)
                    if image:
                        mean_dict = image.reduceRegion(reducer=ee.Reducer.mean(), geometry=point_geom, scale=10).getInfo()
                        return mean_dict.get(index_name) if mean_dict else None, None
                    return None, error
                except Exception as e:
                     return None, f"خطا در محاسبه مقدار برای {farm_name} ({start}-{end}): {e}"
            current_val, err_curr = get_mean_value(start_curr, end_curr)
            if err_curr: errors.append(f"{farm_name} (هفته جاری): {err_curr}")
            previous_val, err_prev = get_mean_value(start_prev, end_prev)
            if err_prev: errors.append(f"{farm_name} (هفته قبل): {err_prev}")
            change = None
            if current_val is not None and previous_val is not None:
                try: change = current_val - previous_val
                except TypeError: change = None
            results.append({
                'مزرعه': farm_name, 'کانال': farm.get('کانال', 'N/A'), 'اداره': farm.get('اداره', 'N/A'),
                f'{index_name} (هفته جاری)': current_val, f'{index_name} (هفته قبل)': previous_val, 'تغییر': change
            })
            progress_bar.progress((i + 1) / total_farms)
        progress_bar.empty()
        return pd.DataFrame(results), errors

    ranking_df, calculation_errors = calculate_weekly_indices(
        filtered_farms_df, selected_index,
        start_date_current_str, end_date_current_str,
        start_date_previous_str, end_date_previous_str
    )

    if calculation_errors:
        st.warning("⚠️ برخی خطاها در حین محاسبه شاخص‌ها رخ داد:")
        for error in calculation_errors[:5]: st.caption(f"- {error}") # Show limited errors
        if len(calculation_errors) > 5: st.caption(f"... و {len(calculation_errors) - 5} خطای دیگر.")

    ranking_df_sorted = pd.DataFrame() # Initialize to avoid NameError if ranking_df is empty
    if not ranking_df.empty:
        ascending_sort = selected_index in ['MSI']
        ranking_df_sorted = ranking_df.sort_values(
            by=f'{selected_index} (هفته جاری)', ascending=ascending_sort, na_position='last'
        ).reset_index(drop=True)
        ranking_df_sorted.index = ranking_df_sorted.index + 1
        ranking_df_sorted.index.name = 'رتبه'

        def determine_status(row, index_name):
            if pd.isna(row['تغییر']) or pd.isna(row[f'{index_name} (هفته جاری)']) or pd.isna(row[f'{index_name} (هفته قبل)']):
                return "بدون داده"
            if index_name in ['NDVI', 'EVI', 'LAI', 'CVI']:
                if row['تغییر'] > 0.05: return "رشد مثبت"
                elif row['تغییر'] < -0.05: return "تنش/کاهش"
                else: return "ثابت"
            elif index_name in ['MSI', 'NDMI']: # NDMI was missing, MSI logic might need adjustment
                if row['تغییر'] < -0.05: return "بهبود" # Lower MSI/NDMI is better, so negative change is improvement
                elif row['تغییر'] > 0.05: return "تنش/بدتر شدن"
                else: return "ثابت"
            return "نامشخص"

        ranking_df_sorted['وضعیت'] = ranking_df_sorted.apply(lambda row: determine_status(row, selected_index), axis=1)
        cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
        for col_format in cols_to_format:
            if col_format in ranking_df_sorted.columns:
                 ranking_df_sorted[col_format] = ranking_df_sorted[col_format].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")
        st.dataframe(ranking_df_sorted, use_container_width=True)

        st.subheader("📊 خلاصه وضعیت مزارع")
        status_counts = ranking_df_sorted['وضعیت'].value_counts()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            count_positive = status_counts.get("رشد مثبت", 0) + status_counts.get("بهبود", 0)
            st.metric("🟢 بهبود/رشد", count_positive)
        with col2:
            st.metric("⚪ ثابت", status_counts.get("ثابت", 0))
        with col3:
            count_negative = status_counts.get("تنش/کاهش", 0) + status_counts.get("تنش/بدتر شدن", 0)
            st.metric("🔴 تنش/کاهش", count_negative)
        with col4:
            st.metric("❔ بدون داده", status_counts.get("بدون داده", 0))

        st.info("""
        **توضیحات وضعیت:**
        - **🟢 رشد مثبت/بهبود**: مزارعی که نسبت به هفته قبل بهبود قابل توجهی داشته‌اند (افزایش در شاخص‌های مثبت مانند NDVI، یا کاهش در شاخص‌های تنش مانند MSI).
        - **⚪ ثابت**: مزارعی که تغییر معناداری نداشته‌اند.
        - **🔴 تنش/کاهش**: مزارعی که نسبت به هفته قبل وضعیت بدتری داشته‌اند.
        - **❔ بدون داده**: اطلاعات کافی برای ارزیابی وضعیت موجود نیست.
        """)

        csv_data = ranking_df_sorted.to_csv(index=True).encode('utf-8')
        st.download_button(
            label="📥 دانلود جدول رتبه‌بندی (CSV)", data=csv_data,
            file_name=f'ranking_{selected_index}_{selected_day}_{end_date_current_str}.csv', mime='text/csv',
        )
    else:
        st.info(f"داده‌ای برای جدول رتبه‌بندی بر اساس {selected_index} در این بازه زمانی یافت نشد.")

with tab2:
    st.subheader("🗺️ نقشه وضعیت مزارع")
    vis_params = {
        'NDVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'EVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
        'NDMI': {'min': -1, 'max': 1, 'palette': ['brown', 'white', 'blue']},
        'LAI': {'min': 0, 'max': 6, 'palette': ['white', 'lightgreen', 'darkgreen']},
        'MSI': {'min': 0, 'max': 3, 'palette': ['blue', 'white', 'brown']}, # Low MSI = high moisture (blue), High MSI = low moisture (brown)
        'CVI': {'min': 0, 'max': 20, 'palette': ['yellow', 'lightgreen', 'darkgreen']},
    }
    map_center_lat = lat if selected_farm_name != "همه مزارع" else INITIAL_LAT
    map_center_lon = lon if selected_farm_name != "همه مزارع" else INITIAL_LON
    initial_zoom_map = 14 if selected_farm_name != "همه مزارع" else INITIAL_ZOOM

    m = geemap.Map(location=[map_center_lat, map_center_lon], zoom=initial_zoom_map, add_google_map=False)
    m.add_basemap("HYBRID")

    if selected_farm_geom:
        gee_image_current, error_msg_current = get_processed_image(
            selected_farm_geom, start_date_current_str, end_date_current_str, selected_index
        )
        if gee_image_current:
            try:
                m.addLayer(
                    gee_image_current,
                    vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}),
                    f"{selected_index} ({start_date_current_str} to {end_date_current_str})"
                )
                # Custom Legend
                legend_html_content = ""
                if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']:
                    legend_html_content = '<p style="margin: 0; color: red;">بحرانی/پایین</p><p style="margin: 0; color: yellow;">متوسط</p><p style="margin: 0; color: green;">سالم/بالا</p>'
                elif selected_index == 'NDMI': # NDMI: Blue for wet, brown for dry
                     legend_html_content = '<p style="margin: 0; color: brown;">خشک</p><p style="margin: 0; color: white;">متوسط</p><p style="margin: 0; color: blue;">مرطوب</p>'
                elif selected_index == 'MSI': # MSI: Brown for high stress (dry), Blue for low stress (wet)
                     legend_html_content = '<p style="margin: 0; color: blue;">رطوبت بالا / تنش کم</p><p style="margin: 0; color: white;">متوسط</p><p style="margin: 0; color: brown;">رطوبت پایین / تنش زیاد</p>'

                if legend_html_content:
                    legend_html = f'''
                    <div style="position: fixed; bottom: 50px; left: 10px; z-index: 1000; background-color: white; padding: 10px; border: 1px solid grey; border-radius: 5px; font-family: Vazirmatn, sans-serif;">
                        <p style="margin: 0; font-weight: bold;">راهنمای {selected_index}</p>
                        {legend_html_content}
                    </div>
                    '''
                    m.get_root().html.add_child(folium.Element(legend_html))

                if selected_farm_name == "همه مزارع":
                     for idx_farm, farm_row in filtered_farms_df.iterrows():
                         folium.Marker(
                             location=[farm_row['عرض جغرافیایی'], farm_row['طول جغرافیایی']],
                             popup=f"مزرعه: {farm_row['مزرعه']}<br>کانال: {farm_row['کانال']}<br>اداره: {farm_row['اداره']}",
                             tooltip=farm_row['مزرعه'], icon=folium.Icon(color='blue', icon='info-sign')
                         ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=INITIAL_ZOOM)
                else:
                     folium.Marker(
                         location=[lat, lon], tooltip=selected_farm_name,
                         icon=folium.Icon(color='red', icon='star')
                     ).add_to(m)
                     m.center_object(selected_farm_geom, zoom=14)
                m.add_layer_control()
            except Exception as map_err:
                st.error(f"خطا در افزودن لایه به نقشه: {map_err}\n{traceback.format_exc()}")
        else:
            st.warning(f"تصویری برای نمایش روی نقشه یافت نشد. {error_msg_current}")
        st_folium(m, width=None, height=500, use_container_width=True)
        st.caption("برای مشاهده جزئیات روی مارکرها کلیک کنید. از کنترل لایه‌ها برای تغییر نقشه پایه استفاده کنید.")
    else:
        st.warning("هندسه مزرعه برای نمایش نقشه انتخاب نشده است.")


    st.markdown("---")
    st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")
    if selected_farm_name == "همه مزارع":
        st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
    elif selected_farm_geom:
        # Check if the geometry is a Point
        is_point_geom = False
        try:
            if selected_farm_geom.type().getInfo() == 'Point':
                is_point_geom = True
        except Exception: # Fallback for non-EE geometry or error in getInfo
            if isinstance(selected_farm_geom, ee.geometry.Point):
                 is_point_geom = True


        if is_point_geom:
            timeseries_end_date = today.strftime('%Y-%m-%d')
            timeseries_start_date = (today - datetime.timedelta(days=365*2)).strftime('%Y-%m-%d') # 2 years of data
            ts_df, ts_error = get_index_time_series(
                selected_farm_geom, selected_index,
                start_date=timeseries_start_date, end_date=timeseries_end_date
            )
            if ts_error:
                st.warning(f"خطا در دریافت داده‌های سری زمانی: {ts_error}")
            elif not ts_df.empty:
                fig = px.line(ts_df, y=selected_index, title=f"روند زمانی {selected_index} برای {selected_farm_name}")
                fig.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index, font=dict(family="Vazirmatn"))
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 2 سال گذشته.")
            else:
                st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
        else:
            st.warning("نمودار سری زمانی فقط برای مزارع منفرد (نقطه‌ای) قابل نمایش است.")
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
        st.subheader("💬 پاسخ هوشمند به سوالات در مورد داده‌های مزارع")
        user_farm_q = st.text_input("سوال خود را در مورد مزرعه انتخاب شده یا وضعیت کلی مزارع بپرسید:", key="gemini_farm_q")
        if st.button("✉️ ارسال سوال به Gemini", key="btn_gemini_farm_q"):
            if not user_farm_q:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt = ""
                context_data = ""
                if selected_farm_name != "همه مزارع" and selected_farm_details is not None and not ranking_df_sorted.empty:
                    farm_data_for_prompt = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                    if not farm_data_for_prompt.empty:
                        current_val_str = farm_data_for_prompt[f'{selected_index} (هفته جاری)'].iloc[0]
                        prev_val_str = farm_data_for_prompt[f'{selected_index} (هفته قبل)'].iloc[0]
                        change_str = farm_data_for_prompt['تغییر'].iloc[0]
                        status_str = farm_data_for_prompt['وضعیت'].iloc[0]
                        context_data = f"داده‌های مزرعه '{selected_farm_name}' برای شاخص {selected_index} (هفته منتهی به {end_date_current_str}):\n" \
                                       f"- مقدار هفته جاری: {current_val_str}\n" \
                                       f"- مقدار هفته قبل: {prev_val_str}\n" \
                                       f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                                       f"- وضعیت کلی: {status_str}\n"
                        prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این داده‌ها و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."
                    else:
                        prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر در مورد مزرعه '{selected_farm_name}' سوالی پرسیده است: '{user_farm_q}'. داده‌های رتبه‌بندی برای این مزرعه در دسترس نیست. لطفاً به صورت کلی و بر اساس سوال کاربر پاسخ دهید. پاسخ به زبان فارسی."

                else: # "همه مزارع" or no specific farm data
                    context_data = f"وضعیت کلی مزارع برای روز '{selected_day}' و شاخص '{selected_index}' در حال بررسی است. تعداد {len(filtered_farms_df)} مزرعه در این روز فیلتر شده‌اند."
                    if not ranking_df_sorted.empty:
                        context_data += f"\nخلاصه وضعیت مزارع بر اساس شاخص {selected_index}:\n"
                        status_counts = ranking_df_sorted['وضعیت'].value_counts()
                        context_data += f"- تعداد مزارع با بهبود/رشد: {status_counts.get('رشد مثبت', 0) + status_counts.get('بهبود', 0)}\n"
                        context_data += f"- تعداد مزارع با وضعیت ثابت: {status_counts.get('ثابت', 0)}\n"
                        context_data += f"- تعداد مزارع با تنش/کاهش: {status_counts.get('تنش/کاهش', 0) + status_counts.get('تنش/بدتر شدن', 0)}\n"
                        context_data += f"- تعداد مزارع بدون داده: {status_counts.get('بدون داده', 0)}\n"

                    prompt = f"شما یک دستیار هوشمند برای تحلیل داده‌های کشاورزی نیشکر هستید. کاربر سوالی در مورد وضعیت کلی مزارع پرسیده است: '{user_farm_q}'.\n{context_data}\nلطفاً بر اساس این اطلاعات و سوال کاربر، یک پاسخ جامع و مفید به زبان فارسی ارائه دهید."

                with st.spinner("در حال پردازش پاسخ با Gemini..."):
                    response = ask_gemini(prompt)
                    st.markdown(response)
        st.markdown("---")

        st.subheader("📄 تولید گزارش خودکار هفتگی برای مزرعه")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تولید گزارش انتخاب کنید.")
        elif selected_farm_details is None:
            st.info(f"داده‌های جزئی برای مزرعه {selected_farm_name} یافت نشد.")
        elif ranking_df_sorted.empty:
            st.info(f"داده‌های رتبه‌بندی برای مزرعه {selected_farm_name} جهت تولید گزارش موجود نیست.")
        else:
            if st.button(f"📝 تولید گزارش برای مزرعه '{selected_farm_name}'", key="btn_gemini_report"):
                farm_data_for_report = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                if not farm_data_for_report.empty:
                    current_val_str = farm_data_for_report[f'{selected_index} (هفته جاری)'].iloc[0]
                    prev_val_str = farm_data_for_report[f'{selected_index} (هفته قبل)'].iloc[0]
                    change_str = farm_data_for_report['تغییر'].iloc[0]
                    status_str = farm_data_for_report['وضعیت'].iloc[0]
                    area_str = f"{selected_farm_details.get('مساحت', 'N/A'):,.2f}" if pd.notna(selected_farm_details.get('مساحت')) else "N/A"
                    variety_str = selected_farm_details.get('واریته', 'N/A')

                    prompt = f"شما یک دستیار هوشمند برای تهیه گزارش‌های کشاورزی هستید. لطفاً یک گزارش توصیفی و ساختاریافته به زبان فارسی در مورد وضعیت مزرعه '{selected_farm_name}' برای هفته منتهی به {end_date_current_str} تهیه کنید.\n" \
                             f"اطلاعات مزرعه:\n" \
                             f"- مساحت: {area_str} هکتار\n" \
                             f"- واریته: {variety_str}\n" \
                             f"- شاخص مورد بررسی: {selected_index} ({index_options[selected_index]})\n" \
                             f"- مقدار شاخص در هفته جاری: {current_val_str}\n" \
                             f"- مقدار شاخص در هفته قبل: {prev_val_str}\n" \
                             f"- تغییر نسبت به هفته قبل: {change_str}\n" \
                             f"- وضعیت کلی بر اساس تغییرات: {status_str}\n\n" \
                             f"در گزارش به موارد فوق اشاره کنید، تحلیل مختصری از وضعیت ارائه دهید و در صورت امکان، پیشنهادهای کلی (نه تخصصی) برای بهبود یا حفظ وضعیت مطلوب بیان کنید. گزارش باید رسمی و قابل فهم برای مدیران کشاورزی باشد."

                    with st.spinner("در حال تولید گزارش با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.6, top_p=0.9)
                        st.markdown(f"### گزارش هفتگی مزرعه {selected_farm_name} (شاخص {selected_index})")
                        st.markdown(f"**تاریخ گزارش:** {datetime.date.today().strftime('%Y-%m-%d')}")
                        st.markdown(f"**بازه زمانی مورد بررسی:** {start_date_current_str} الی {end_date_current_str}")
                        st.markdown(response)
                else:
                    st.error(f"داده‌های کافی برای تولید گزارش برای مزرعه {selected_farm_name} یافت نشد.")
        st.markdown("---")

        st.subheader(f"📉 تحلیل تغییرات شاخص {selected_index} (سری زمانی)")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای تحلیل سری زمانی انتخاب کنید.")
        elif selected_farm_geom:
            is_point_geom_gemini = False
            try:
                if selected_farm_geom.type().getInfo() == 'Point': is_point_geom_gemini = True
            except Exception:
                if isinstance(selected_farm_geom, ee.geometry.Point): is_point_geom_gemini = True

            if is_point_geom_gemini:
                if st.button(f"🔍 تحلیل روند زمانی {selected_index} برای '{selected_farm_name}'", key="btn_gemini_timeseries"):
                    timeseries_end_date_gemini = today.strftime('%Y-%m-%d')
                    timeseries_start_date_gemini = (today - datetime.timedelta(days=180)).strftime('%Y-%m-%d') # Last 6 months
                    ts_df_gemini, ts_error_gemini = get_index_time_series(
                        selected_farm_geom, selected_index,
                        start_date=timeseries_start_date_gemini, end_date=timeseries_end_date_gemini
                    )
                    if ts_error_gemini:
                        st.error(f"خطا در دریافت داده‌های سری زمانی برای Gemini: {ts_error_gemini}")
                    elif not ts_df_gemini.empty:
                        # Prepare a summary of time series for the prompt
                        ts_summary = f"داده‌های سری زمانی شاخص {selected_index} برای مزرعه '{selected_farm_name}' در 6 ماه گذشته (از {timeseries_start_date_gemini} تا {timeseries_end_date_gemini}):\n"
                        ts_summary += ts_df_gemini.iloc[::len(ts_df_gemini)//5 if len(ts_df_gemini)>5 else 1].to_string(header=True, index=True) # Sample ~5 points
                        ts_summary += f"\nمقدار اولیه حدود {ts_df_gemini[selected_index].iloc[0]:.3f} و مقدار نهایی حدود {ts_df_gemini[selected_index].iloc[-1]:.3f} بوده است."
                        
                        prompt = f"شما یک تحلیلگر داده‌های کشاورزی هستید. بر اساس داده‌های سری زمانی زیر برای شاخص {selected_index} مزرعه '{selected_farm_name}' طی 6 ماه گذشته:\n{ts_summary}\n" \
                                 f"۱. روند کلی تغییرات شاخص (افزایشی، کاهشی، نوسانی، ثابت) را توصیف کنید.\n" \
                                 f"۲. نقاط عطف یا تغییرات قابل توجه در روند را شناسایی کنید (اگر وجود دارد).\n" \
                                 f"۳. دلایل احتمالی کلی (مانند تغییرات فصلی، مراحل رشد گیاه، تنش‌های محیطی عمومی) برای این روندها چه می‌تواند باشد؟\n" \
                                 f"پاسخ به زبان فارسی، ساختاریافته و تحلیلی باشد."
                        with st.spinner(f"در حال تحلیل روند زمانی {selected_index} با Gemini..."):
                            response = ask_gemini(prompt, temperature=0.5)
                            st.markdown(response)
                    else:
                        st.info(f"داده‌ای برای تحلیل سری زمانی {selected_index} برای مزرعه {selected_farm_name} یافت نشد.")
            else:
                st.info("تحلیل سری زمانی فقط برای مزارع منفرد (نقطه‌ای) امکان‌پذیر است.")
        st.markdown("---")

        st.subheader("🌱 پیشنهاد اقدامات کشاورزی")
        if selected_farm_name == "همه مزارع":
            st.info("لطفاً یک مزرعه خاص را برای دریافت پیشنهادات انتخاب کنید.")
        elif selected_farm_details is None or ranking_df_sorted.empty :
             st.info(f"داده‌های کافی برای ارائه پیشنهاد برای مزرعه {selected_farm_name} موجود نیست.")
        else:
            if st.button(f"💡 دریافت پیشنهادات برای مزرعه '{selected_farm_name}'", key="btn_gemini_actions"):
                farm_data_for_actions = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                if not farm_data_for_actions.empty:
                    current_val_str = farm_data_for_actions[f'{selected_index} (هفته جاری)'].iloc[0]
                    status_str = farm_data_for_actions['وضعیت'].iloc[0]

                    prompt = f"شما یک مشاور کشاورزی هوشمند هستید. برای مزرعه '{selected_farm_name}'، شاخص {selected_index} ({index_options[selected_index]}) در هفته جاری مقدار {current_val_str} را نشان می‌دهد و وضعیت کلی آن '{status_str}' ارزیابی شده است.\n" \
                             f"بر اساس این اطلاعات:\n" \
                             f"۱. تفسیر مختصری از مقدار فعلی شاخص {selected_index} ارائه دهید (مثلاً اگر NDVI پایین است، یعنی چه؟ اگر MSI بالاست یعنی چه؟).\n" \
                             f"۲. با توجه به مقدار شاخص و وضعیت، چه نوع بررسی‌ها یا اقدامات عمومی کشاورزی (مانند بررسی آبیاری، نیاز به عناصر غذایی، پایش آفات و بیماری‌ها، مدیریت بقایا) ممکن است لازم باشد؟ لطفاً پیشنهادات کلی و غیر تخصصی ارائه دهید.\n" \
                             f"پاسخ به زبان فارسی و به صورت عملیاتی باشد."

                    with st.spinner("در حال دریافت پیشنهادات کشاورزی با Gemini..."):
                        response = ask_gemini(prompt, temperature=0.8, top_k=30)
                        st.markdown(response)
                else:
                    st.error(f"داده‌های رتبه‌بندی برای مزرعه {selected_farm_name} جهت ارائه پیشنهاد یافت نشد.")
        st.markdown("---")

        st.subheader("🗣️ پاسخ به سوالات عمومی کاربران")
        user_general_q = st.text_input("سوال عمومی خود را در مورد مفاهیم کشاورزی، شاخص‌های سنجش از دور یا این سامانه بپرسید:", key="gemini_general_q")
        if st.button("❓ پرسیدن سوال از Gemini", key="btn_gemini_general_q"):
            if not user_general_q:
                st.info("لطفاً سوال خود را وارد کنید.")
            else:
                prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید. لطفاً به سوال زیر که توسط یک کاربر سامانه پایش نیشکر پرسیده شده است، به زبان فارسی پاسخ دهید. سعی کنید پاسخ شما ساده، قابل فهم و دقیق باشد.\n\nسوال کاربر: '{user_general_q}'"
                if "مزرعه من قرمز شده" in user_general_q or "مزرعه قرمز" in user_general_q: # Heuristic
                     if selected_farm_name != "همه مزارع" and not ranking_df_sorted.empty:
                        farm_data_color = ranking_df_sorted[ranking_df_sorted['مزرعه'] == selected_farm_name]
                        if not farm_data_color.empty and selected_index in ['NDVI', 'EVI', 'LAI', 'CVI']: # Indices where red is bad
                            current_val_color = farm_data_color[f'{selected_index} (هفته جاری)'].iloc[0]
                            prompt = f"شما یک دانشنامه هوشمند در زمینه کشاورزی و سنجش از دور هستید. کاربر پرسیده: '{user_general_q}'. در این سامانه، رنگ قرمز روی نقشه برای شاخص‌هایی مانند NDVI معمولاً نشان‌دهنده مقدار پایین و وضعیت نامطلوب پوشش گیاهی است. برای مزرعه '{selected_farm_name}'، مقدار فعلی شاخص {selected_index} برابر {current_val_color} است. لطفاً توضیح دهید که چه عواملی می‌توانند باعث پایین بودن این شاخص و 'قرمز' دیده شدن مزرعه در نقشه شوند و چه بررسی‌هایی ممکن است لازم باشد. پاسخ به زبان فارسی."


                with st.spinner("در حال جستجو برای پاسخ با Gemini..."):
                    response = ask_gemini(prompt, temperature=0.3)
                    st.markdown(response)

st.sidebar.markdown("---")
st.sidebar.markdown("ساخته شده با 💻 توسط [اسماعیل کیانی] با استفاده از Streamlit, Google Earth Engine, geemap و Gemini API")
st.sidebar.markdown("🌾 شرکت کشت و صنعت دهخدا")
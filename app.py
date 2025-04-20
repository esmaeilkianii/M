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
import time # For potential delays/retries
from dateutil.relativedelta import relativedelta # For date calculations

# --- Configuration ---
APP_TITLE = "داشبورد مانیتورینگ مزارع نیشکر دهخدا"
INITIAL_LAT = 31.534442 # مختصات اولیه نقشه - عرض جغرافیایی
INITIAL_LON = 48.724416 # مختصات اولیه نقشه - طول جغرافیایی
INITIAL_ZOOM = 12 # زوم اولیه نقشه

# --- File Paths (Ensure these paths are correct relative to your script) ---
# --- مسیر فایل‌ها (اطمینان حاصل کنید این مسیرها نسبت به اسکریپت شما صحیح هستند) ---
CSV_FILE_PATH = 'cleaned_output.csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # فایل کلید حساب سرویس GEE

# --- Constants ---
DAYS_OF_WEEK_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]
# Define standard color palettes for indices (example for NDVI)
# تعریف پالت‌های رنگی استاندارد برای شاخص‌ها (مثال برای NDVI)
NDVI_PALETTE = 'RdYlGn' # Example palette, you can choose others like 'viridis', 'plasma' etc.

# --- GEE Authentication ---
@st.cache_resource # Cache the GEE initialization
def initialize_gee():
    """Initializes Google Earth Engine using the Service Account."""
    """راه اندازی اولیه Google Earth Engine با استفاده از حساب سرویس."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.stop()
        # Attempt initialization with specified opt_url for high volume endpoint
        # تلاش برای راه اندازی اولیه با opt_url مشخص شده برای نقطه پایانی حجم بالا
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully using Service Account.")
        st.success("اتصال به Google Earth Engine با موفقیت برقرار شد.")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()

# --- Data Loading ---
@st.cache_data # Cache the loaded data
def load_data(csv_path):
    """Loads farm data from the CSV file."""
    """بارگذاری داده‌های مزارع از فایل CSV."""
    try:
        if not os.path.exists(csv_path):
            st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
            st.stop()
        df = pd.read_csv(csv_path)
        # Data Cleaning and Type Conversion
        # پاکسازی داده‌ها و تبدیل نوع
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        # Handle potential missing coordinates - Drop rows where essential coordinates are missing
        # مدیریت مختصات گمشده احتمالی - حذف ردیف‌هایی که مختصات ضروری آن‌ها گمشده است
        df.dropna(subset=['عرض جغرافیایی', 'طول جغرافیایی'], inplace=True)
        # Ensure 'روزهای هفته' is string type for filtering
        # اطمینان از اینکه ستون 'روزهای هفته' از نوع رشته است برای فیلتر کردن
        df['روزهای هفته'] = df['روزهای هفته'].astype(str)
        st.success(f"داده‌های مزارع از {csv_path} با موفقیت بارگذاری شد.")
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except pd.errors.EmptyDataError:
        st.error(f"خطا: فایل CSV '{csv_path}' خالی است.")
        st.stop()
    except KeyError as e:
        st.error(f"خطا: ستون مورد نیاز '{e}' در فایل CSV یافت نشد. ستون‌های مورد نیاز: مزرعه, طول جغرافیایی, عرض جغرافیایی, روزهای هفته")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

# --- GEE Calculation Functions ---

def get_sentinel2_collection(start_date, end_date, geometry, cloud_pixel_percentage=20):
    """Gets Sentinel-2 SR collection filtered by date, bounds, and cloud cover."""
    """دریافت مجموعه داده Sentinel-2 SR فیلتر شده بر اساس تاریخ، محدوده و پوشش ابر."""
    s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                 .filterBounds(geometry)
                 .filterDate(ee.Date(start_date), ee.Date(end_date))
                 # Pre-filter based on metadata cloud cover (less reliable but faster)
                 # پیش‌فیلتر بر اساس پوشش ابر متادیتا (کمتر قابل اعتماد اما سریعتر)
                 .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', cloud_pixel_percentage)))

    # Function to mask clouds using the SCL band
    # تابع برای پوشاندن ابرها با استفاده از باند SCL
    def mask_s2_clouds(image):
        scl = image.select('SCL')
        # Cloud Shadow (3), Cloud Medium Probability (8), Cloud High Probability (9), Cirrus (10)
        # سایه ابر (3)، ابر با احتمال متوسط (8)، ابر با احتمال بالا (9)، سیروس (10)
        cloud_mask = scl.eq(3).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
        # Apply the mask - pixels that are clouds become masked
        # اعمال ماسک - پیکسل‌هایی که ابر هستند ماسک می‌شوند
        return image.updateMask(cloud_mask.Not())

    # Apply cloud masking and select/scale bands
    # اعمال ماسک ابر و انتخاب/مقیاس‌بندی باندها
    return s2_sr_col.map(mask_s2_clouds).map(lambda img: img.select(
            ['B2', 'B3', 'B4', 'B8', 'B11', 'B12'], # Blue, Green, Red, NIR, SWIR1, SWIR2
            ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']
        ).multiply(0.0001).copyProperties(img, ['system:time_start'])) # Scale factor

def calculate_ndvi(image):
    """Calculates NDVI."""
    """محاسبه NDVI."""
    return image.normalizedDifference(['NIR', 'Red']).rename('NDVI')

def calculate_evi(image):
    """Calculates EVI."""
    """محاسبه EVI."""
    evi = image.expression(
        '2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1)', {
            'NIR': image.select('NIR'),
            'Red': image.select('Red'),
            'Blue': image.select('Blue')
    }).rename('EVI')
    return evi

def calculate_ndmi(image):
    """Calculates NDMI (Normalized Difference Moisture Index)."""
    """محاسبه NDMI (شاخص نرمال شده تفاوت رطوبت)."""
    return image.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')

def calculate_msi(image):
    """Calculates MSI (Moisture Stress Index)."""
    """محاسبه MSI (شاخص تنش رطوبتی)."""
    # Using the formula MSI = SWIR1 / NIR
    # استفاده از فرمول MSI = SWIR1 / NIR
    return image.select('SWIR1').divide(image.select('NIR')).rename('MSI')

# Note: LAI, Biomass, ET, Chlorophyll often require more complex models or specific GEE apps/modules.
# توجه: LAI، Biomass، ET، کلروفیل اغلب به مدل‌های پیچیده‌تر یا برنامه‌ها/ماژول‌های خاص GEE نیاز دارند.
# Implementing basic versions or placeholders here.
# پیاده‌سازی نسخه‌های پایه یا جایگزین در اینجا.

def calculate_lai_simple(image):
    """Placeholder/Simple LAI calculation (e.g., related to NDVI). Needs calibration."""
    """محاسبه LAI ساده/جایگزین (مثلاً مرتبط با NDVI). نیاز به کالیبراسیون دارد."""
    # Example: Simple linear relationship with NDVI (highly approximate)
    # مثال: رابطه خطی ساده با NDVI (بسیار تقریبی)
    return calculate_ndvi(image).multiply(5.0).rename('LAI') # Needs proper coefficients

def calculate_biomass_simple(image):
    """Placeholder/Simple Biomass calculation based on LAI. Needs calibration."""
    """محاسبه Biomass ساده/جایگزین بر اساس LAI. نیاز به کالیبراسیون دارد."""
    # Example: Biomass = a * LAI + b. Using placeholder coefficients.
    # مثال: Biomass = a * LAI + b. استفاده از ضرایب جایگزین.
    a = 1000 # Placeholder coefficient (e.g., kg/ha per LAI unit) - نیاز به کالیبراسیون
    b = 50   # Placeholder coefficient (e.g., base biomass kg/ha) - نیاز به کالیبراسیون
    lai = calculate_lai_simple(image)
    return lai.multiply(a).add(b).rename('Biomass')

# Dictionary mapping index names to calculation functions
# دیکشنری نگاشت نام شاخص‌ها به توابع محاسبه
INDEX_FUNCTIONS = {
    'NDVI': calculate_ndvi,
    'EVI': calculate_evi,
    'NDMI': calculate_ndmi,
    'MSI': calculate_msi,
    'LAI': calculate_lai_simple, # Using simple version
    'Biomass': calculate_biomass_simple, # Using simple version
    # 'ET': calculate_et, # Requires specific ET model implementation
    # 'Chlorophyll': calculate_chlorophyll # Requires specific Chlorophyll model
}

# Dictionary for index visualization parameters (min, max, palette)
# دیکشنری برای پارامترهای تجسم شاخص (حداقل، حداکثر، پالت)
# These ranges might need adjustment based on typical values for sugarcane
# این محدوده‌ها ممکن است نیاز به تنظیم بر اساس مقادیر معمول برای نیشکر داشته باشند
VIS_PARAMS = {
    'NDVI': {'min': 0, 'max': 1, 'palette': 'RdYlGn'},
    'EVI': {'min': 0, 'max': 1, 'palette': 'RdYlGn'},
    'NDMI': {'min': -1, 'max': 1, 'palette': 'viridis'},
    'MSI': {'min': 0, 'max': 3, 'palette': 'RdBu'}, # Lower MSI indicates less moisture stress
    'LAI': {'min': 0, 'max': 8, 'palette': 'Greens'},
    'Biomass': {'min': 0, 'max': 15000, 'palette': 'YlGn'}, # Example range in kg/ha
}

def get_latest_image_value(geometry, index_name='NDVI', days_back=90):
    """Gets the value of a specific index from the latest cloud-free image."""
    """دریافت مقدار یک شاخص خاص از آخرین تصویر بدون ابر."""
    try:
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days_back)

        collection = get_sentinel2_collection(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), geometry)

        # Check if the index function exists
        # بررسی وجود تابع شاخص
        if index_name not in INDEX_FUNCTIONS:
            st.warning(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return None, None # Return None for value and date

        # Calculate the desired index
        # محاسبه شاخص مورد نظر
        index_collection = collection.map(INDEX_FUNCTIONS[index_name])

        # Get the latest image
        # دریافت آخرین تصویر
        latest_image = index_collection.sort('system:time_start', False).first()

        if latest_image is None:
            # st.warning(f"هیچ تصویر بدون ابری در {days_back} روز گذشته برای این مکان یافت نشد.")
            return None, None # Return None for value and date

        # Reduce the region to get the mean value
        # کاهش منطقه برای دریافت مقدار میانگین
        # Use a small buffer around the point for calculation
        # استفاده از یک بافر کوچک اطراف نقطه برای محاسبه
        mean_value = latest_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry.buffer(10), # Buffer by 10 meters
            scale=10, # Sentinel-2 scale for relevant bands
            maxPixels=1e9
        ).get(index_name) # Get the calculated index value

        # Need to evaluate the result
        # نیاز به ارزیابی نتیجه
        value = mean_value.getInfo()
        date = ee.Date(latest_image.get('system:time_start')).format('YYYY-MM-dd').getInfo()

        return value, date
    except ee.EEException as e:
        # Log the error instead of stopping the app for every GEE issue
        # لاگ کردن خطا به جای متوقف کردن برنامه برای هر مشکل GEE
        print(f"GEE Error in get_latest_image_value for {geometry.getInfo()}: {e}") # Log to console/server logs
        # Optionally show a less intrusive warning in UI
        # st.warning(f"خطای GEE هنگام دریافت آخرین مقدار شاخص رخ داد. ممکن است برخی داده‌ها نمایش داده نشوند.")
        return None, None
    except Exception as e:
        print(f"Unexpected Error in get_latest_image_value for {geometry.getInfo()}: {e}") # Log to console/server logs
        # st.error(f"خطای غیرمنتظره هنگام دریافت آخرین مقدار شاخص: {e}") # Avoid stopping if possible
        return None, None

def get_recent_mean_value(geometry, index_name='NDVI', days=7):
    """Calculates the mean value of an index over the specified recent period."""
    """محاسبه مقدار میانگین یک شاخص در دوره اخیر مشخص شده."""
    try:
        end_date = datetime.datetime.now()
        start_date = end_date - datetime.timedelta(days=days)

        collection = get_sentinel2_collection(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), geometry)

        if index_name not in INDEX_FUNCTIONS:
            st.warning(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return None

        index_collection = collection.map(INDEX_FUNCTIONS[index_name])

        # Calculate the mean over the collection
        # محاسبه میانگین در مجموعه
        mean_image = index_collection.mean() # Creates a single image representing the mean

        # Check if the mean image has the required band (it might be empty if no images were found)
        # بررسی اینکه آیا تصویر میانگین باند مورد نیاز را دارد (ممکن است خالی باشد اگر تصویری یافت نشود)
        if mean_image is None or not mean_image.bandNames().getInfo():
             # st.warning(f"هیچ تصویری در {days} روز گذشته برای محاسبه میانگین یافت نشد.")
             return None

        # Reduce the region
        # کاهش منطقه
        mean_value = mean_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry.buffer(10),
            scale=10,
            maxPixels=1e9
        ).get(index_name)

        value = mean_value.getInfo()
        return value
    except ee.EEException as e:
        # Don't flood the UI with errors for every farm, maybe log instead
        # رابط کاربری را با خطا برای هر مزرعه پر نکنید، شاید به جای آن لاگ کنید
        print(f"GEE Error calculating recent mean for {index_name} at {geometry.getInfo()}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected Error calculating recent mean for {index_name} at {geometry.getInfo()}: {e}")
        return None


def get_index_time_series(geometry, index_name, start_date, end_date):
    """Gets time series data for a specific index."""
    """دریافت داده‌های سری زمانی برای یک شاخص خاص."""
    try:
        if index_name not in INDEX_FUNCTIONS:
            st.error(f"تابع محاسبه برای شاخص '{index_name}' تعریف نشده است.")
            return None

        collection = get_sentinel2_collection(start_date, end_date, geometry)
        index_collection = collection.map(INDEX_FUNCTIONS[index_name])

        def get_value(image):
            # Calculate the mean value for the geometry
            # محاسبه مقدار میانگین برای هندسه
            mean_val = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry.buffer(10), # Use buffered point
                scale=30, # Can use coarser scale for time series
                maxPixels=1e9
            ).get(index_name)
            # Return a feature with null geometry, date and value property
            # بازگرداندن یک ویژگی با هندسه تهی، تاریخ و ویژگی مقدار
            return ee.Feature(None, {
                'date': ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'),
                index_name: mean_val
            })

        # Map over the collection to get value for each image
        # نگاشت روی مجموعه برای دریافت مقدار برای هر تصویر
        ts_features = index_collection.map(get_value)

        # Filter out null values which can occur if the entire region was masked or computation failed
        # فیلتر کردن مقادیر تهی که ممکن است در صورت ماسک شدن کل منطقه یا شکست محاسبه رخ دهد
        ts_features = ts_features.filter(ee.Filter.NotNull([index_name]))

        # Evaluate the results
        # ارزیابی نتایج
        info = ts_features.getInfo()

        # Convert to Pandas DataFrame
        # تبدیل به DataFrame پانداس
        data = []
        for f in info['features']:
            props = f['properties']
            # Ensure the index value exists and is not None
            # اطمینان از وجود مقدار شاخص و تهی نبودن آن
            if index_name in props and props[index_name] is not None:
                 data.append({
                    'date': props['date'],
                    index_name: props[index_name]
                 })

        if not data:
            # This is not necessarily an error, just no data found
            # این لزوماً یک خطا نیست، فقط داده‌ای یافت نشد
            # st.warning(f"داده‌ای برای سری زمانی شاخص '{index_name}' در محدوده تاریخ مشخص شده یافت نشد.")
            return pd.DataFrame(columns=['date', index_name]) # Return empty DataFrame

        df = pd.DataFrame(data)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date')
        return df

    except ee.EEException as e:
        st.error(f"خطای GEE هنگام دریافت سری زمانی برای {index_name}: {e}")
        return None # Indicate error with None
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام دریافت سری زمانی برای {index_name}: {e}")
        return None # Indicate error with None

# --- Streamlit App Layout ---

st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Initialize GEE
# راه اندازی اولیه GEE
if not initialize_gee():
    st.stop() # Stop execution if GEE fails

# Load Data
# بارگذاری داده‌ها
farm_data = load_data(CSV_FILE_PATH)
if farm_data is None or farm_data.empty:
    st.warning("داده‌های مزارع بارگذاری نشد یا خالی است.")
    st.stop()

# --- Sidebar ---
st.sidebar.header("فیلترها و تنظیمات")

# Day of the week selection
# انتخاب روز هفته
selected_day = st.sidebar.selectbox(
    "انتخاب روز هفته:",
    options=DAYS_OF_WEEK_FA,
    index=0 # Default to Saturday
)

# Filter data based on selected day
# فیلتر داده‌ها بر اساس روز انتخاب شده
# Handle cases where 'روزهای هفته' might contain multiple days or need cleaning
# مدیریت مواردی که 'روزهای هفته' ممکن است شامل چند روز باشد یا نیاز به پاکسازی داشته باشد
try:
    # Assuming the column contains the exact Persian day name
    # فرض بر اینکه ستون حاوی نام دقیق روز فارسی است
    filtered_farms = farm_data[farm_data['روزهای هفته'].str.contains(selected_day, na=False)].copy()
except KeyError:
    st.error("خطا: ستون 'روزهای هفته' در فایل CSV یافت نشد.")
    st.stop()
except Exception as e:
    st.error(f"خطا در فیلتر کردن داده‌ها بر اساس روز: {e}")
    st.stop()


if filtered_farms.empty:
    st.sidebar.warning(f"هیچ مزرعه‌ای برای '{selected_day}' یافت نشد.")
    # Display map anyway, but maybe centered without markers?
    # نمایش نقشه به هر حال، اما شاید متمرکز و بدون نشانگر؟
else:
    st.sidebar.info(f"تعداد مزارع فیلتر شده برای {selected_day}: {len(filtered_farms)}")


# --- Main Panel ---
tab1, tab2, tab3 = st.tabs(["نقشه مزارع (آخرین NDVI)", "رتبه‌بندی مزارع (NDVI اخیر)", "نمودار سری زمانی"])

with tab1:
    st.header(f"نقشه مزارع برای {selected_day} (بر اساس آخرین NDVI)")

    if not filtered_farms.empty:
        # Create Map
        # ایجاد نقشه
        Map = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM)

        # Add farms to map, colored by latest NDVI
        # اضافه کردن مزارع به نقشه، رنگ‌آمیزی شده بر اساس آخرین NDVI
        ndvi_values = []
        farms_added_to_map = 0
        st.write("در حال محاسبه آخرین NDVI و افزودن مزارع به نقشه...")
        progress_bar_map = st.progress(0)

        # Use itertuples for potentially better performance and cleaner access
        # استفاده از itertuples برای عملکرد بالقوه بهتر و دسترسی تمیزتر
        for i, row in enumerate(filtered_farms.itertuples(index=False)): # index=False prevents adding index to tuple
            farm_name = None # Initialize farm_name for the except block
            row_dict = row._asdict() # Convert namedtuple to dict once

            try:
                # Get farm name safely using .get() with a default value
                # دریافت نام مزرعه به صورت ایمن با استفاده از .get() با مقدار پیش‌فرض
                farm_name = row_dict.get('مزرعه', f'ردیف ناشناس {i+1}')

                lat = row_dict.get('عرض جغرافیایی')
                lon = row_dict.get('طول جغرافیایی')

                # Check for valid coordinates earlier
                # بررسی مختصات معتبر زودتر
                if pd.isna(lat) or pd.isna(lon):
                    st.warning(f"مختصات نامعتبر یا گمشده برای مزرعه: '{farm_name}'. این ردیف رد شد.")
                    continue # Skip to the next iteration

                # Create GEE geometry (Point)
                # ایجاد هندسه GEE (نقطه)
                farm_geom = ee.Geometry.Point([lon, lat])

                # Get latest NDVI value
                # دریافت آخرین مقدار NDVI
                latest_ndvi, image_date = get_latest_image_value(farm_geom, 'NDVI', days_back=90) # Look back 90 days

                if latest_ndvi is not None and image_date is not None:
                    ndvi_values.append(latest_ndvi)
                    # Ensure latest_ndvi is float for palette function
                    # اطمینان از اینکه latest_ndvi از نوع float برای تابع پالت است
                    try:
                        ndvi_float = float(latest_ndvi)
                        color = geemap.normalized_difference_palette(ndvi_float, min=0, max=1, palette=NDVI_PALETTE) # Get color from palette
                    except (ValueError, TypeError):
                         st.warning(f"مقدار NDVI نامعتبر ({latest_ndvi}) برای رنگ‌آمیزی مزرعه {farm_name}. از رنگ پیش‌فرض استفاده می‌شود.")
                         color = 'gray' # Default color if conversion fails

                    tooltip_text = f"""
                    <b>مزرعه:</b> {farm_name}<br>
                    <b>آخرین NDVI:</b> {latest_ndvi:.3f}<br>
                    <b>تاریخ تصویر:</b> {image_date}<br>
                    <b>روز هفته:</b> {row_dict.get('روزهای هفته', 'N/A')}<br>
                    <b>عرض جغرافیایی:</b> {lat:.5f}<br>
                    <b>طول جغرافیایی:</b> {lon:.5f}
                    """
                    # Add marker to map
                    # اضافه کردن نشانگر به نقشه
                    Map.add_marker(
                        location=[lat, lon],
                        tooltip=tooltip_text,
                        icon=folium.Icon(color='white', icon_color=color, icon='leaf', prefix='fa') # Use leaf icon
                    )
                    farms_added_to_map += 1
                else:
                    # Mark farms with no recent data differently
                    # مزارعی که داده اخیر ندارند را متفاوت علامت‌گذاری کنید
                     Map.add_marker(
                        location=[lat, lon],
                        tooltip=f"مزرعه: {farm_name}\n (داده NDVI اخیر یافت نشد)",
                        icon=folium.Icon(color='gray', icon='question-circle', prefix='fa')
                    )

            # Specific exception for missing keys (columns)
            # استثنای خاص برای کلیدهای (ستون‌های) گمشده
            except KeyError as ke:
                 st.warning(f"خطا: ستون ضروری '{ke}' در داده‌های مزرعه '{farm_name or f'ردیف {i+1}'}' یافت نشد. این ردیف رد شد.")
            # Catch other potential errors during processing a single farm
            # گرفتن خطاهای احتمالی دیگر هنگام پردازش یک مزرعه واحد
            except Exception as e:
                # Use farm_name if available, otherwise use the fallback name
                # استفاده از farm_name در صورت وجود، در غیر این صورت از نام جایگزین استفاده کنید
                st.warning(f"خطا در پردازش مزرعه '{farm_name or f'ردیف ناشناس {i+1}'}': {e}")

            # Update progress bar outside the try/except for each iteration
            # به‌روزرسانی نوار پیشرفت خارج از try/except برای هر تکرار
            progress_bar_map.progress((i + 1) / len(filtered_farms))

        if farms_added_to_map > 0:
            # Add NDVI color bar legend
            # اضافه کردن راهنمای نوار رنگی NDVI
             Map.add_colorbar(VIS_PARAMS['NDVI'], label="NDVI (آخرین تصویر)", layer_name="NDVI")
        elif not filtered_farms.empty: # Only show warning if there were farms to process
             st.warning("هیچ داده NDVI معتبری برای نمایش روی نقشه یافت نشد (ممکن است تصاویر اخیر بدون ابر نباشند).")


        # Display Map
        # نمایش نقشه
        Map.to_streamlit(height=600)
    else:
        st.info("هیچ مزرعه‌ای برای نمایش روی نقشه برای روز انتخاب شده وجود ندارد.")
        # Display an empty map centered on the region
        # نمایش یک نقشه خالی متمرکز بر منطقه
        Map = geemap.Map(location=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM)
        Map.to_streamlit(height=600)


with tab2:
    st.header(f"رتبه‌بندی مزارع برای {selected_day} (بر اساس میانگین NDVI 7 روز اخیر)")

    if not filtered_farms.empty:
        ranking_data = []
        st.write("در حال محاسبه میانگین NDVI 7 روز اخیر برای رتبه‌بندی...")
        progress_bar_rank = st.progress(0)

        # Use itertuples for potentially better performance
        # استفاده از itertuples برای عملکرد بالقوه بهتر
        for i, row in enumerate(filtered_farms.itertuples(index=False)):
            farm_name_rank = None # Initialize for except block
            row_dict_rank = row._asdict()
            try:
                farm_name_rank = row_dict_rank.get('مزرعه', f'ردیف ناشناس {i+1}')
                lat = row_dict_rank.get('عرض جغرافیایی')
                lon = row_dict_rank.get('طول جغرافیایی')

                if pd.isna(lat) or pd.isna(lon):
                    st.warning(f"مختصات نامعتبر برای رتبه‌بندی مزرعه: '{farm_name_rank}'. رد شد.")
                    # Add entry with N/A to keep row count consistent? Or skip? Skipping for now.
                    # اضافه کردن ورودی با N/A برای حفظ شمارش ردیف؟ یا رد کردن؟ فعلاً رد می‌شود.
                    continue # Skip this farm

                farm_geom = ee.Geometry.Point([lon, lat])

                # Get recent mean NDVI
                # دریافت میانگین NDVI اخیر
                recent_ndvi = get_recent_mean_value(farm_geom, 'NDVI', days=7)

                ranking_data.append({
                    'مزرعه': farm_name_rank,
                    'عرض جغرافیایی': lat,
                    'طول جغرافیایی': lon,
                    'میانگین NDVI (7 روز اخیر)': recent_ndvi # Keep None if calculation failed
                })
            except KeyError as ke:
                 st.warning(f"خطا در ستون مورد نیاز '{ke}' برای رتبه‌بندی مزرعه '{farm_name_rank or f'ردیف {i+1}'}'")
                 # Optionally add a row indicating the error
                 ranking_data.append({
                    'مزرعه': farm_name_rank or f'ردیف {i+1}',
                    'عرض جغرافیایی': row_dict_rank.get('عرض جغرافیایی'), # Keep coords if available
                    'طول جغرافیایی': row_dict_rank.get('طول جغرافیایی'),
                    'میانگین NDVI (7 روز اخیر)': 'خطای ستون'
                 })
            except Exception as e:
                 st.warning(f"خطا در محاسبه NDVI اخیر برای رتبه‌بندی مزرعه '{farm_name_rank or f'ردیف {i+1}'}': {e}")
                 ranking_data.append({
                    'مزرعه': farm_name_rank or f'ردیف {i+1}',
                    'عرض جغرافیایی': lat if 'lat' in locals() else None, # Include coords if available
                    'طول جغرافیایی': lon if 'lon' in locals() else None,
                    'میانگین NDVI (7 روز اخیر)': 'خطای محاسبه'
                })
            # Update progress bar
            # به‌روزرسانی نوار پیشرفت
            progress_bar_rank.progress((i + 1) / len(filtered_farms))


        if ranking_data:
            rank_df = pd.DataFrame(ranking_data)
            # Convert NDVI column to numeric, coercing errors (like None, 'خطا') to NaN
            # تبدیل ستون NDVI به عددی، تبدیل خطاها (مانند None، 'خطا') به NaN
            rank_df['میانگین NDVI (7 روز اخیر)'] = pd.to_numeric(rank_df['میانگین NDVI (7 روز اخیر)'], errors='coerce')

            # Sort by NDVI (descending), NaNs will be placed last by default
            # مرتب‌سازی بر اساس NDVI (نزولی)، NaN ها به طور پیش‌فرض در آخر قرار می‌گیرند
            rank_df = rank_df.sort_values(by='میانگین NDVI (7 روز اخیر)', ascending=False, na_position='last')

            # Reset index for display ranking
            # بازنشانی ایندکس برای نمایش رتبه‌بندی
            rank_df.reset_index(drop=True, inplace=True)
            rank_df.index += 1 # Start ranking from 1

            st.dataframe(rank_df.style.format({'عرض جغرافیایی': "{:.5f}",
                                               'طول جغرافیایی': "{:.5f}",
                                               'میانگین NDVI (7 روز اخیر)': "{:.3f}"},
                                              na_rep='N/A') # Display NaN as N/A
                                     .highlight_null(null_color='lightgrey') # Highlight missing/failed values
                                     .background_gradient(cmap=NDVI_PALETTE, subset=['میانگین NDVI (7 روز اخیر)'], vmin=0, vmax=1) # Add color gradient
                        , use_container_width=True)
        else:
            st.info("داده‌ای برای رتبه‌بندی مزارع یافت نشد (ممکن است به دلیل خطاهای پردازش یا مختصات نامعتبر باشد).")

    else:
        st.info("هیچ مزرعه‌ای برای رتبه‌بندی برای روز انتخاب شده وجود ندارد.")


with tab3:
    st.header("نمودار سری زمانی شاخص‌ها")

    if not filtered_farms.empty:
        # Select farm for time series analysis
        # انتخاب مزرعه برای تحلیل سری زمانی
        # Use unique farm names in case of duplicates
        # استفاده از نام‌های منحصر به فرد مزارع در صورت وجود تکرار
        farm_names = filtered_farms['مزرعه'].unique().tolist()
        selected_farm_name = st.selectbox("انتخاب مزرعه برای نمایش سری زمانی:", farm_names)

        # Select index for time series analysis
        # انتخاب شاخص برای تحلیل سری زمانی
        available_indices = list(INDEX_FUNCTIONS.keys())
        # Default to NDVI if available, otherwise first index
        # پیش‌فرض به NDVI در صورت وجود، در غیر این صورت اولین شاخص
        default_index_ts = available_indices.index('NDVI') if 'NDVI' in available_indices else 0
        selected_index = st.selectbox("انتخاب شاخص:", available_indices, index=default_index_ts)

        # Select time range
        # انتخاب محدوده زمانی
        today = datetime.date.today()
        default_start = today - relativedelta(years=1) # Default to last 1 year

        col1, col2 = st.columns(2)
        with col1:
            start_date_ts = st.date_input("تاریخ شروع:", value=default_start, max_value=today - datetime.timedelta(days=1))
        with col2:
            end_date_ts = st.date_input("تاریخ پایان:", value=today, min_value=start_date_ts + datetime.timedelta(days=1), max_value=today)

        # Button to trigger time series calculation
        # دکمه برای شروع محاسبه سری زمانی
        if st.button(f"نمایش نمودار سری زمانی {selected_index} برای {selected_farm_name}"):
            if selected_farm_name and selected_index and start_date_ts < end_date_ts:
                # Get the first matching farm's info (in case of duplicate names)
                # دریافت اطلاعات اولین مزرعه منطبق (در صورت وجود نام‌های تکراری)
                farm_info_list = filtered_farms[filtered_farms['مزرعه'] == selected_farm_name]
                if not farm_info_list.empty:
                    farm_info = farm_info_list.iloc[0]
                    lat = farm_info['عرض جغرافیایی']
                    lon = farm_info['طول جغرافیایی']

                    if pd.notna(lat) and pd.notna(lon):
                        farm_geom_ts = ee.Geometry.Point([lon, lat])

                        with st.spinner(f"در حال محاسبه سری زمانی {selected_index} برای {selected_farm_name}..."):
                            ts_df = get_index_time_series(farm_geom_ts, selected_index,
                                                          start_date_ts.strftime('%Y-%m-%d'),
                                                          end_date_ts.strftime('%Y-%m-%d'))

                        # Check if ts_df is a DataFrame (even if empty) or None (indicating error)
                        # بررسی اینکه آیا ts_df یک DataFrame است (حتی اگر خالی باشد) یا None (نشان دهنده خطا)
                        if isinstance(ts_df, pd.DataFrame):
                            if not ts_df.empty:
                                fig = px.line(ts_df, x='date', y=selected_index,
                                              title=f"روند زمانی شاخص {selected_index} برای مزرعه {selected_farm_name}",
                                              labels={'date': 'تاریخ', selected_index: f'مقدار {selected_index}'},
                                              markers=True) # Add markers to see individual points
                                fig.update_layout(xaxis_title="تاریخ", yaxis_title=f"مقدار {selected_index}")
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                # No error, but no data points found
                                # بدون خطا، اما هیچ نقطه داده‌ای یافت نشد
                                st.warning(f"هیچ داده‌ای برای سری زمانی {selected_index} در محدوده تاریخ انتخاب شده برای مزرعه {selected_farm_name} یافت نشد (ممکن است تصاویر بدون ابر وجود نداشته باشند).")
                        else:
                            # An error occurred during time series fetching (already shown by get_index_time_series)
                            # خطایی هنگام دریافت سری زمانی رخ داده است (قبلاً توسط get_index_time_series نشان داده شده است)
                            st.error("خطا در دریافت داده‌های سری زمانی.")
                    else:
                        st.error(f"مختصات نامعتبر برای مزرعه {selected_farm_name}.")
                else:
                     st.error(f"اطلاعات مزرعه برای {selected_farm_name} یافت نشد.") # Should not happen if name is from list
            else:
                st.warning("لطفاً یک مزرعه، شاخص و محدوده تاریخ معتبر انتخاب کنید (تاریخ شروع باید قبل از تاریخ پایان باشد).")
    else:
        st.info("هیچ مزرعه‌ای برای تحلیل سری زمانی برای روز انتخاب شده وجود ندارد.")

st.sidebar.markdown("---")
st.sidebar.info("ساخته شده با Streamlit و Google Earth Engine")

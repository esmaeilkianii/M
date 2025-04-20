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

# --- Configuration ---
APP_TITLE = "داشبورد مانیتورینگ مزارع نیشکر دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- File Paths (Relative to the script location in Hugging Face) ---
CSV_FILE_PATH = 'output (1).csv'
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
def load_farm_data(csv_path="cleaned_output.csv"):
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
    st.stop() # Stop if GEE initialization failed

if farm_data_df is None:
    st.error("❌ امکان ادامه کار بدون داده‌های مزارع وجود ندارد.")
    st.stop() # Stop if data loading failed


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
    thermalBands = image.select('ST_B.*').multiply(0.00341802).add(149.0) # If using thermal

    return image.addBands(opticalBands, None, True)\
                .addBands(thermalBands, None, True)\
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
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(_geometry)
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

# --- Get Selected Farm Geometry and Details ---
selected_farm_details = None
selected_farm_geom = None

if selected_farm_name == "همه مزارع":
    # Use the bounding box of all filtered farms for the map view
    min_lon, min_lat = filtered_farms_df['طول جغرافیایی'].min(), filtered_farms_df['عرض جغرافیایی'].min()
    max_lon, max_lat = filtered_farms_df['طول جغرافیایی'].max(), filtered_farms_df['عرض جغرافیایی'].max()
    # Create a bounding box geometry
    selected_farm_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    st.subheader(f"نمایش کلی مزارع برای روز: {selected_day}")
    st.info(f"تعداد مزارع در این روز: {len(filtered_farms_df)}")
else:
    selected_farm_details = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name].iloc[0]
    lat = selected_farm_details['عرض جغرافیایی']
    lon = selected_farm_details['طول جغرافیایی']
    selected_farm_geom = ee.Geometry.Point([lon, lat])
    st.subheader(f"جزئیات مزرعه: {selected_farm_name} (روز: {selected_day})")
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


# --- Map Display ---
st.markdown("---")
st.subheader(" نقشه وضعیت مزارع")

# Define visualization parameters based on the selected index
vis_params = {
    'NDVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
    'EVI': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']},
    'NDMI': {'min': -1, 'max': 1, 'palette': ['brown', 'white', 'blue']},
    'LAI': {'min': 0, 'max': 6, 'palette': ['white', 'lightgreen', 'darkgreen']}, # Adjust max based on expected values
    'MSI': {'min': 0, 'max': 3, 'palette': ['blue', 'white', 'brown']}, # Lower values = more moisture
    'CVI': {'min': 0, 'max': 20, 'palette': ['yellow', 'lightgreen', 'darkgreen']}, # Adjust max based on expected values
    # Add vis params for other indices if implemented
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

            # Add legend
            m.add_legend(
                title=f"{selected_index} Legend",
                builtin_legend=None, # Use custom labels if needed or rely on palette
                palette=vis_params.get(selected_index, {}).get('palette', []),
                labels=['بحرانی/پایین', 'متوسط', 'سالم/بالا'] if selected_index in ['NDVI', 'EVI', 'LAI', 'CVI'] else ['مرطوب/بالا', 'متوسط', 'خشک/پایین'] if selected_index in ['NDMI', 'MSI'] else None, # Basic labels
                position='bottomright'
            )

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
# Note: Direct PNG download from st_folium/geemap isn't built-in easily.
st.info("💡 برای ذخیره نقشه، می‌توانید از ابزار عکس گرفتن از صفحه (Screenshot) مرورگر یا سیستم عامل خود استفاده کنید.")


# --- Time Series Chart ---
st.markdown("---")
st.subheader(f"📈 نمودار روند زمانی شاخص {selected_index}")

if selected_farm_name == "همه مزارع":
    st.info("لطفاً یک مزرعه خاص را از پنل کناری انتخاب کنید تا نمودار روند زمانی آن نمایش داده شود.")
elif selected_farm_geom and isinstance(selected_farm_geom, ee.Geometry.Point):
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
        st.line_chart(ts_df[selected_index])
        st.caption(f"نمودار تغییرات شاخص {selected_index} برای مزرعه {selected_farm_name} در 6 ماه گذشته.")
    else:
        st.info(f"داده‌ای برای نمایش نمودار سری زمانی {selected_index} در بازه مشخص شده یافت نشد.")
else:
    st.warning("نوع هندسه مزرعه برای نمودار سری زمانی پشتیبانی نمی‌شود (فقط نقطه).")


# --- Ranking Table ---
st.markdown("---")
st.subheader(f"📊 جدول رتبه‌بندی مزارع بر اساس {selected_index} (روز: {selected_day})")
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

    # Format numbers for better readability
    cols_to_format = [f'{selected_index} (هفته جاری)', f'{selected_index} (هفته قبل)', 'تغییر']
    for col in cols_to_format:
        if col in ranking_df_sorted.columns:
             # Check if column exists before formatting
             ranking_df_sorted[col] = ranking_df_sorted[col].map(lambda x: f"{x:.3f}" if pd.notna(x) else "N/A")


    st.dataframe(ranking_df_sorted, use_container_width=True)

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
st.sidebar.markdown("ساخته شده با استفاده از Streamlit, Google Earth Engine, و geemap")

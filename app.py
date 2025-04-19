import streamlit as st
import locale
# Set locale to handle Persian characters properly
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
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

# --- Data Loading ---
@st.cache_data # Cache the loaded data
def load_data(csv_path):
    """Loads farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        df['مزرعه'] = df['مزرعه'].str.strip()
        for col in ['کانال', 'اداره', 'واریته', 'سن ', 'روزهای هفته']:
             if col in df.columns:
                df[col] = df[col].fillna('نامشخص').astype(str)
        print(f"Data loaded successfully. Shape: {df.shape}")
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

# --- GEE Image Processing Functions ---

COMMON_BAND_NAMES = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']

# --- Masking Functions ---
# These now operate on images with ORIGINAL sensor band names
# and return images with only the necessary DATA bands, scaled, and masked.

def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 SR images using QA60.
       Returns scaled, masked data bands ONLY (B2, B3, B4, B5, B8, B11, B12).
             qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    # Select necessary data bands using original names, apply mask, scale
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12'] # S2 bands needed for indices
    return image.select(data_bands).updateMask(mask).divide(10000.0)\
        .copyProperties(image, ["system:time_start"])



def mask_landsat_clouds(image):
    """Masks clouds in Landsat 8/9 SR images using QA_PIXEL.
       Returns scaled, masked data bands ONLY (SR_B2-SR_B7).
    """
    qa = image.select('QA_PIXEL')


    # Bits 3 (Cloud Shadow), 4 (Snow), 5 (Cloud)
    cloud_shadow_bit = 1 << 3
    snow_bit = 1 << 4

    # Select SR bands (optical/SWIR), apply scaling, apply mask
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'] # L8/9 bands needed
    scaled_bands = image.select(sr_bands).multiply(0.0000275).add(-0.2)

    return scaled_bands.updateMask(mask)\
        .copyProperties(image, ["system:time_start"])


# --- Index Calculation Functions ---
# These functions now expect images with COMMON band names
# (Blue, Green, Red, NIR, SWIR1, etc.)

def calculate_ndvi(image):
    return image.normalizedDifference(['NIR', 'Red']).rename('NDVI')






def calculate_evi(image):
    # EVI calculation requires Blue band
    return image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': image.select('NIR'),
            'RED': image.select('Red'),
            'BLUE': image.select('Blue') # Make sure Blue is available
        }).rename('EVI')


def calculate_ndmi(image):
    return image.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')



def calculate_msi(image):
    # Using SWIR1 / NIR definition
    return image.expression('SWIR1 / NIR', {
        'SWIR1': image.select('SWIR1'),
        'NIR': image.select('NIR')
    }).rename('MSI')


def calculate_lai_simple(image):
    # Use EVI if available, otherwise NDVI as fallback
    try:
        evi = calculate_evi(image).select('EVI')
        lai = evi.multiply(3.5).add(0.1) # Placeholder EVI-based LAI
    except ee.EEException: # Handle potential error if Blue band missing for EVI
        st.warning("EVI calculation failed (Blue band might be missing), using NDVI for LAI.", icon="⚠️")
        ndvi = calculate_ndvi(image).select('NDVI')






        lai = ndvi.multiply(5.0).add(0.1) # Placeholder NDVI-based LAI

    return lai.clamp(0, 8).rename('LAI')


def calculate_biomass_simple(image):
    lai = calculate_lai_simple(image).select('LAI')




    a = 1.5
    b = 0.2
    biomass = lai.multiply(a).add(b)

    return biomass.clamp(0, 50).rename('Biomass')

def calculate_chlorophyll_mcari(image):
    # MCARI requires RedEdge1, only reliably available from Sentinel-2
    try:
        # Check if RedEdge1 exists before attempting calculation
        image.select('RedEdge1') # This will throw an error if band doesn't exist
        mcari = image.expression(
            '((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)', {
                'RE1': image.select('RedEdge1'),
                'RED': image.select('Red'),
                'GREEN': image.select('Green')
            }).rename('Chlorophyll')
        return mcari

    except ee.EEException:
         st.warning("MCARI requires Sentinel-2 Red Edge band. Using NDVI as Chlorophyll proxy.", icon="⚠️")
         return calculate_ndvi(image).rename('Chlorophyll') # Fallback




def calculate_et_placeholder(image):

    st.warning("ET calculation is complex. Using NDMI as a proxy for moisture status.", icon="⚠️")
    return calculate_ndmi(image).rename('ET_proxy')




# Dictionary mapping index names to functions and visualization params
INDEX_FUNCTIONS = {
    'NDVI': {'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'EVI': {'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'ET_proxy': {'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}}
}


# --- GEE Data Retrieval ---
def get_image_collection(start_date, end_date, geometry=None, sensor='Sentinel-2'):
    """Gets, filters, masks, scales, and renames Sentinel-2 or Landsat images."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')






    if sensor == 'Sentinel-2':
        collection_id = 'COPERNICUS/S2_SR_HARMONIZED'
        mask_func = mask_s2_clouds
        # Original band names needed by mask_s2_clouds + QA
        bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
        # Corresponding common names for the data bands AFTER masking/scaling
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']
        collection = ee.ImageCollection(collection_id)

        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
        collection = l9.merge(l8)
        mask_func = mask_landsat_clouds
        # Original band names needed by mask_landsat_clouds + QA
        bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
        # Corresponding common names for the data bands AFTER masking/scaling
        bands_to_rename_to = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'] # No RedEdge in Landsat

    else:
        st.error("Sensor not supported")
    if geometry:
        collection = collection.filterBounds(geometry)

    # Check initial collection size
    initial_count = collection.size().getInfo()
    if initial_count == 0:
        st.warning(f"No images found for the selected period and area using {sensor} before cloud masking.")
        return None

    # --- Processing Function ---
    def process_image(image):
        # 1. Select original bands needed for masking and data



        img_selected_orig = image.select(bands_to_select_orig)

        # 2. Apply masking and scaling (mask_func returns scaled data bands)
        img_processed = mask_func(img_selected_orig)




        # 3. Rename the processed bands to common names
        # Note: bands_to_rename_to count must match bands returned by mask_func
        img_renamed = img_processed.rename(bands_to_rename_to)


        return img_renamed.copyProperties(image, ["system:time_start"])

    # Map the processing function over the collection
    processed_collection = collection.map(process_image)

    # Check if collection is empty after filtering/masking
    count = processed_collection.size().getInfo()
    if count == 0:
        st.warning(f"No cloud-free images found for the selected period and area using {sensor}.")
        return None

    # Verify bands in the first image after processing
    try:
        first_image = processed_collection.first()
        if first_image is None:
             st.error("Collection became empty after processing map function.")
             return None
        final_bands = first_image.bandNames().getInfo()
        print(f"Final bands in processed collection: {final_bands}")

        # Basic check if expected bands are present (adjust for Landsat vs S2)
        expected_check = bands_to_rename_to
        if not all(name in final_bands for name in expected_check):
            st.warning(f"Warning: Not all expected common bands ({expected_check}) found. Available: {final_bands}", icon="⚠️")

    except ee.EEException as e:
        st.error(f"Error verifying processed bands: {e}")
        # May happen if collection is truly empty or other GEE issue
        return None


    return processed_collection


def calculate_indices_for_collection(collection, index_list):
    """Maps index calculation functions over a processed collection."""
    if collection is None:



















        return None

    calculated_collection = collection
    bands_available = ee.Image(collection.first()).bandNames().getInfo() # Check bands AFTER processing

    for index_name in index_list:
        if index_name in INDEX_FUNCTIONS:
            # Basic check if necessary bands likely exist (can be improved)
            req_bands_guess = [] # Simplistic check, refine if needed
            if index_name in ['NDVI', 'NDMI', 'MSI', 'EVI']: req_bands_guess = ['NIR', 'Red']
            if index_name == 'EVI': req_bands_guess.append('Blue')
            if index_name == 'Chlorophyll': req_bands_guess.append('RedEdge1') # Will fail gracefully in func if missing
            # Add more checks if needed

            if all(b in bands_available for b in req_bands_guess if b != 'RedEdge1') or index_name == 'LAI' or index_name == 'Biomass' or index_name == 'ET_proxy': # LAI/Biomass handle fallback
                 try:
                     calculated_collection = calculated_collection.map(INDEX_FUNCTIONS[index_name]['func'])
                     print(f"Calculated {index_name}")
                 except Exception as e:
                     st.warning(f"Could not calculate {index_name}. Error: {e}. Required bands might be missing.", icon="⚠️")
                     # Add dummy band? Or let it fail downstream? For now, let it proceed.
                     # calculated_collection = calculated_collection.map(lambda img: img.addBands(ee.Image(0).rename(index_name)))
            else:
                 st.warning(f"Skipping {index_name}: Required bands {req_bands_guess} not fully available in {bands_available}", icon="⚠️")







        else:
            st.warning(f"Index function for '{index_name}' not defined.")

    return calculated_collection



@st.cache_data(ttl=3600)
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    """Retrieves the time series for a specific index and farm geometry."""
    if collection is None:
        return pd.DataFrame(columns=['Date', index_name])

    # Check if index calculation is feasible before proceeding
    first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail:
         st.error(f"Index function for {index_name} not found.")
         return pd.DataFrame(columns=['Date', index_name])

    # Crude check for band requirements before mapping - prevents unnecessary calculation
    # Add more specific checks based on index_name if needed
    bands_needed = ['NIR', 'Red'] # Base requirement for most
    if index_name == 'EVI': bands_needed.append('Blue')
    if index_name == 'Chlorophyll' and sensor == 'Sentinel-2': bands_needed.append('RedEdge1') # Only if S2






    if not all(b in first_image_bands for b in bands_needed if b != 'RedEdge1' or sensor == 'Sentinel-2'):
         st.warning(f"Cannot calculate timeseries for {index_name}: Required bands missing after processing.", icon="⚠️")
         return pd.DataFrame(columns=['Date', index_name])








    # Calculate *only* the required index for the timeseries
    indexed_collection = collection.map(index_func_detail['func'])

    # Check if the target index band exists after mapping
    try:
         first_img_check = indexed_collection.first()
         if first_img_check is None or index_name not in first_img_check.bandNames().getInfo():
              st.warning(f"Index band '{index_name}' not found after calculation for timeseries.", icon="⚠️")
              return pd.DataFrame(columns=['Date', index_name])
    except ee.EEException as e:
         st.error(f"GEE Error checking index band for timeseries: {e}")
         return pd.DataFrame(columns=['Date', index_name])


    def extract_value(image):
        stats = image.select(index_name).reduceRegion(


            reducer=ee.Reducer.mean(),
            geometry=farm_geom,
            scale=30,  # Use 30m for potentially better performance/less timeouts
            maxPixels=1e9,
            tileScale=4 # Increase tileScale to potentially avoid memory errors
        )
        val = stats.get(index_name)


        return ee.Feature(None, {
            'time': image.get('system:time_start'),
            index_name: ee.Algorithms.If(val, val, -9999)
            })


    try:
        ts_info = indexed_collection.map(extract_value).getInfo()
    except ee.EEException as e:
        st.info("This might be due to GEE memory limits or timeouts. Try a smaller date range or area.")
        return pd.DataFrame(columns=['Date', index_name])


    data = []
    for feature in ts_info['features']:
        value = feature['properties'].get(index_name)
        time_ms = feature['properties'].get('time')
        # Check if value and time are valid before processing
        if value is not None and value != -9999 and time_ms is not None:
            try:
                dt = datetime.datetime.fromtimestamp(time_ms / 1000.0)
                data.append([dt, value])
            except TypeError:
                 st.warning(f"Skipping invalid timestamp in timeseries data: {time_ms}", icon="⚠️")




    if not data:
    ts_df = ts_df.sort_values(by='Date')
    return ts_df





@st.cache_data(ttl=3600)
def get_latest_index_for_ranking(_farms_df_json, selected_day, start_date, end_date, index_name, sensor):
    "Gets the median index value for ranking farms active on a selected day.""
    features = []
    for idx, row in farms_df_filtered.iterrows():
        try:
             geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
             # Buffer slightly - 50m radius might be reasonable for farm center point
             buffered_geom = geom.buffer(50)
             feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
             features.append(feature)





        except Exception as e:
             st.warning(f"Skipping farm {row.get('مزرعه', 'Unknown')} due to invalid geometry data: {e}", icon="⚠️")

    if not features:
         st.warning("No valid farm geometries found for ranking.", icon="⚠️")

    collection = get_image_collection(start_date, end_date, farm_fc.geometry(), sensor)
    if collection is None:

        return pd.DataFrame(columns=['مزرعه', index_name])

    # Check if index calculation is feasible
    first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail:
        st.error(f"Index function for {index_name} not found.")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # Similar band check as in timeseries
    bands_needed = ['NIR', 'Red']
    if index_name == 'EVI': bands_needed.append('Blue')
    if index_name == 'Chlorophyll' and sensor == 'Sentinel-2': bands_needed.append('RedEdge1')

    if not all(b in first_image_bands for b in bands_needed if b != 'RedEdge1' or sensor == 'Sentinel-2'):
        st.warning(f"Cannot calculate ranking for {index_name}: Required bands missing after processing.", icon="⚠️")


        return pd.DataFrame(columns=['مزرعه', index_name])








    # Calculate only the required index
    indexed_collection = collection.map(index_func_detail['func'])

     # Check if the target index band exists after mapping
    try:
         first_img_check = indexed_collection.first()
         if first_img_check is None or index_name not in first_img_check.bandNames().getInfo():




              st.warning(f"Index band '{index_name}' not found after calculation for ranking.", icon="⚠️")
              return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as e:
         return pd.DataFrame(columns=['مزرعه', index_name])


    # Create a median composite over the period for robustness

    median_image = indexed_collection.select(index_name).median()

    # Reduce the composite image over the farm geometries
        farm_values = median_image.reduceRegions(
            collection=farm_fc,
            reducer=ee.Reducer.mean(),
            scale=30, # Use 30m scale
            tileScale=4 # Increase tileScale
        ).getInfo()
    except ee.EEException as e:
        st.error(f"Error during reduceRegions for ranking: {e}")
        st.info("Trying again with larger tileScale...")
        try:
             farm_values = median_image.reduceRegions(
                collection=farm_fc,
                reducer=ee.Reducer.mean(),
                scale=30,
                tileScale=8 # Further increase tileScale
             ).getInfo()
        except ee.EEException as e2:
             st.error(f"ReduceRegions failed again: {e2}")
             st.warning("Could not calculate farm rankings. Try reducing the date range or number of farms.")
             return pd.DataFrame(columns=['مزرعه', index_name])



    ranking_data = []
    for feature in farm_values['features']:
        farm_id = feature['properties'].get('farm_id')
        value = feature['properties'].get('mean') # Default output name is 'mean'
        if farm_id is not None and value is not None:
            ranking_data.append({'مزرعه': farm_id, index_name: value})
        else:
            # Optionally log farms where reduction failed
            # print(f"Warning: Could not get ranking value for farm_id: {farm_id}")
             pass




    if not ranking_data:
         st.warning("No ranking data could be extracted after GEE processing.", icon="⚠️")
         return pd.DataFrame(columns=['مزرعه', index_name])


    ranking_df = pd.DataFrame(ranking_data)
    ascending_sort = False if index_name not in ['MSI'] else True # Higher MSI is usually worse
    ranking_df = ranking_df.sort_values(by=index_name, ascending=ascending_sort, na_position='last').reset_index(drop=True)

    return ranking_df


# --- Streamlit App Layout ---





st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# Initialize GEE
if initialize_gee():
    # Load data after successful GEE initialization
    farm_data_df = load_data(CSV_FILE_PATH)

    # --- Sidebar ---
    st.sidebar.header("تنظیمات نمایش")

    # Date Range Selector
    default_end_date = datetime.date.today()
    # Default to last 7 days for weekly report focus
    default_start_date = default_end_date - datetime.timedelta(days=7)
    start_date = st.sidebar.date_input("تاریخ شروع", value=default_start_date, max_value=default_end_date)
    end_date = st.sidebar.date_input("تاریخ پایان", value=default_end_date, min_value=start_date, max_value=default_end_date)

    # Day of the Week Filter
    days_list = ["همه روزها"] + sorted(farm_data_df['روزهای هفته'].unique().tolist())
    selected_day = st.sidebar.selectbox("فیلتر بر اساس روز هفته", options=days_list)

    # Filter DataFrame based on selected day
    if selected_day == "همه روزها":
        filtered_df = farm_data_df.copy()
    else:
        filtered_df = farm_data_df[farm_data_df['روزهای هفته'] == selected_day].copy()

    # Farm Selection Dropdown
    farm_list = ["همه مزارع"] + sorted(filtered_df['مزرعه'].unique().tolist())
    selected_farm = st.sidebar.selectbox("انتخاب مزرعه", options=farm_list)

    # Index Selection Dropdown
    # Ensure index list is dynamically generated from the INDEX_FUNCTIONS keys
    available_indices = list(INDEX_FUNCTIONS.keys())
    selected_index = st.sidebar.selectbox("انتخاب شاخص", options=available_indices)

    # Sensor Selection
    selected_sensor = st.sidebar.radio("انتخاب سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, key='sensor_select')


    # --- Main Panel ---
    col1, col2 = st.columns([3, 1])

        m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
        m.add_basemap('HYBRID')

        # Get visualization parameters
        vis_params = INDEX_FUNCTIONS.get(selected_index, {}).get('vis')
        if not vis_params:
            st.error(f"Visualization parameters not found for index: {selected_index}")
            # Provide default vis_params or stop execution
            vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'gray']} # Basic default


        # --- Display Logic ---
        # Define geometry for fetching data - either single farm or bounds of all
        display_geom = None
        target_object_for_map = None # GEE object to center map on


        if selected_farm == "همه مزارع":
            if not filtered_df.empty:
                 min_lon, min_lat = filtered_df['طول جغرافیایی'].min(), filtered_df['عرض جغرافیایی'].min()
                 max_lon, max_lat = filtered_df['طول جغرافیایی'].max(), filtered_df['عرض جغرافیایی'].max()
                 # Create bounds geometry only if coordinates are valid
                 if pd.notna(min_lon) and pd.notna(min_lat) and pd.notna(max_lon) and pd.notna(max_lat):
                     display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                     target_object_for_map = display_geom
                 else:
                     st.warning("Could not determine valid bounds for selected farms.", icon="⚠️")
            else:
                 st.info("هیچ مزرعه‌ای برای نمایش با فیلترهای انتخاب شده یافت نشد.")
        else: # Single farm selected
            farm_info_rows = filtered_df[filtered_df['مزرعه'] == selected_farm]
            if not farm_info_rows.empty:
                 farm_info = farm_info_rows.iloc[0]
                 farm_lat = farm_info['عرض جغرافیایی']
                 farm_lon = farm_info['طول جغرافیایی']
                 if pd.notna(farm_lat) and pd.notna(farm_lon):
                     farm_geom = ee.Geometry.Point([farm_lon, farm_lat])
                     display_geom = farm_geom.buffer(150) # Buffer for visualization
                     target_object_for_map = farm_geom # Center on the point
                 else:
                      st.warning(f"مختصات نامعتبر برای مزرعه {selected_farm}.", icon="⚠️")

            else:
                 st.warning(f"اطلاعات مزرعه {selected_farm} یافت نشد (ممکن است مربوط به روز هفته دیگری باشد).", icon="⚠️")

        # Proceed only if we have a valid geometry to display
        if display_geom:
            with st.spinner(f"در حال پردازش تصویر {selected_index} برای منطقه/مزرعه..."):
                 collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)

                 if collection:
                    # Check feasibility before calculating all indices
                     first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
                     index_func_detail = INDEX_FUNCTIONS.get(selected_index)

                     bands_needed = ['NIR', 'Red']
                     if selected_index == 'EVI': bands_needed.append('Blue')
                     if selected_index == 'Chlorophyll' and selected_sensor == 'Sentinel-2': bands_needed.append('RedEdge1')

                     if index_func_detail and all(b in first_image_bands for b in bands_needed if b != 'RedEdge1' or selected_sensor == 'Sentinel-2'):
                         # Calculate only the selected index for display
                         indexed_collection = collection.map(index_func_detail['func'])

                         # Check if index band exists after calculation
                         first_img_check = indexed_collection.first()
                         if first_img_check and selected_index in first_img_check.bandNames().getInfo():
                             median_image = indexed_collection.select(selected_index).median()
                             # Clip layer if single farm selected for cleaner view
                             layer_image = median_image.clip(display_geom) if selected_farm != "همه مزارع" else median_image

                             m.addLayer(layer_image, vis_params, f'{selected_index} (Median)')
                             try:
                                m.add_legend(title=f'{selected_index}', builtin_legend=None, palette=vis_params['palette'], min=vis_params['min'], max=vis_params['max'])
                             except Exception as legend_e:
                                 st.warning(f"Could not add legend: {legend_e}", icon="⚠️")

                             # Add download button (use display_geom for region)
                             try:
                                 thumb_url = median_image.getThumbURL({
                                     'region': display_geom.toGeoJson(),
                                     'bands': selected_index,
                                     'palette': vis_params['palette'],
                                     'min': vis_params['min'],
                                     'max': vis_params['max'],
                                     'dimensions': 512
                                 })
                                 response = requests.get(thumb_url)
                                 if response.status_code == 200:
                                     img_bytes = BytesIO(response.content)
                                     st.sidebar.download_button(
                                         label=f"دانلود نقشه ({selected_index})",
                                         data=img_bytes,
                                         file_name=f"map_{selected_farm if selected_farm != 'همه مزارع' else 'all'}_{selected_index}.png",
                                         mime="image/png",
                                         key=f"download_{selected_index}" # Add key to avoid issues
                                     )
                                 else:
                                     st.sidebar.warning(f"Link generation failed (Status: {response.status_code}).", icon="⚠️")
                             except Exception as thumb_e:
                                 st.sidebar.warning(f"Error generating download link: {thumb_e}", icon="⚠️")
                         else:
                             st.warning(f"Index band '{selected_index}' not found after calculation for map.", icon="⚠️")




                     else:
                          st.warning(f"Cannot display {selected_index}: Required bands missing after processing for this sensor/index.", icon="⚠️")

                 else:
                    st.warning(f"No suitable satellite images found for the selected period/area.", icon="⚠️")


            # Add markers AFTER adding the layer
            if selected_farm == "همه مزارع" and not filtered_df.empty:
                 for idx, row in filtered_df.iterrows():
                      if pd.notna(row['عرض جغرافیایی']) and pd.notna(row['طول جغرافیایی']):
                               tooltip=f"مزرعه {row['مزرعه']}",
                               icon=folium.Icon(color='blue', icon='info-sign')
                           ).add_to(m)
            elif selected_farm != "همه مزارع":
                farm_info_rows = filtered_df[filtered_df['مزرعه'] == selected_farm]
                if not farm_info_rows.empty:
                    farm_info = farm_info_rows.iloc[0]
                    if pd.notna(farm_info['عرض جغرافیایی']) and pd.notna(farm_info['طول جغرافیایی']):
                         popup_html = f"<b>مزرعه:</b> {farm_info['مزرعه']}<br><b>کانال:</b> {farm_info['کانال']}<br><b>اداره:</b> {farm_info['اداره']}<br><b>مساحت:</b> {farm_info['مساحت داشت']:.2f}<br><b>واریته:</b> {farm_info['واریته']}<br><b>سن:</b> {farm_info['سن ']}"
                         folium.Marker(
                             location=[farm_info['عرض جغرافیایی'], farm_info['طول جغرافیایی']],
                             popup=folium.Popup(popup_html, max_width=250),
                             tooltip=f"مزرعه {farm_info['مزرعه']}",
                             icon=folium.Icon(color='red', icon='star')
                         ).add_to(m)

            # Center the map
            if target_object_for_map:
                zoom_level = INITIAL_ZOOM + 2 if selected_farm != "همه مزارع" else INITIAL_ZOOM
                m.center_object(target_object_for_map, zoom=zoom_level)

        # Render the map in the placeholder
        with map_placeholder:
             m.to_streamlit(height=500)


    with col2:
        if selected_farm != "همه مزارع":

            st.subheader(f"جزئیات مزرعه: {selected_farm}")
            farm_info_rows = filtered_df[filtered_df['مزرعه'] == selected_farm]
            if not farm_info_rows.empty:
                farm_info = farm_info_rows.iloc[0]
                st.metric("کانال", str(farm_info['کانال'])) # Ensure string
                st.metric("اداره", str(farm_info['اداره'])) # Ensure string
                st.metric("مساحت داشت (هکتار)", f"{farm_info['مساحت داشت']:.2f}" if pd.notna(farm_info['مساحت داشت']) else "N/A")
                st.metric("واریته", str(farm_info['واریته']))
                st.metric("سن", str(farm_info['سن ']))
                st.metric("روز آبیاری", str(farm_info['روزهای هفته']))
                st.metric("وضعیت مختصات", "موجود" if farm_info['coordinates_missing'] == 0 else "گمشده")


                st.subheader(f"روند شاخص {selected_index}")
                # Check coordinates before fetching timeseries
                if pd.notna(farm_info['عرض جغرافیایی']) and pd.notna(farm_info['طول جغرافیایی']):
                    with st.spinner(f"در حال دریافت سری زمانی {selected_index} برای مزرعه {selected_farm}..."):
                        farm_geom = ee.Geometry.Point([farm_info['طول جغرافیایی'], farm_info['عرض جغرافیایی']])
                        # Pass geom as GeoJSON string for caching
                        ts_df = get_timeseries_for_farm(farm_geom.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)

                    if not ts_df.empty:
                else:
                    st.warning("مختصات نامعتبر برای دریافت سری زمانی.", icon="📍")
            else:
                 st.info("اطلاعات این مزرعه برای روز هفته انتخاب شده موجود نیست.")


        else: # "همه مزارع" is selected
            st.subheader(f"رتبه‌بندی مزارع بر اساس {selected_index}")
            st.info(f"نمایش میانگین مقدار شاخص '{selected_index}' در بازه زمانی برای مزارع فعال در '{selected_day}'.")

            with st.spinner(f"در حال محاسبه رتبه‌بندی مزارع بر اساس {selected_index}..."):
                 # Pass DataFrame as JSON for caching
                ranking_df = get_latest_index_for_ranking(filtered_df.to_json(), selected_day, start_date, end_date, selected_index, selected_sensor)

            if not ranking_df.empty:
                # Ensure index column exists before formatting
                if selected_index in ranking_df.columns:
                     st.dataframe(ranking_df.style.format({selected_index: "{:.3f}"}), use_container_width=True)
                else:
                     st.dataframe(ranking_df, use_container_width=True) # Display without formatting if index column missing

                # Allow downloading ranking data
                csv = ranking_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                   label=f"دانلود جدول رتبه‌بندی ({selected_index})",
else:
    st.warning("لطفا صبر کنید تا اتصال به Google Earth Engine برقرار شود یا خطاهای نمایش داده شده را بررسی کنید.", icon="⏳")

import streamlit as st
import ee
import geemap.foliumap as geemap # Using foliumap backend for Streamlit compatibility
import pandas as pd
import plotly.express as px
import os
import json # To potentially read the service account file format

# --- Configuration ---
st.set_page_config(layout="wide", page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا", page_icon="🌱")

# Define paths for input files
GEE_KEY_FILENAME = "ee-esmaeilkiani13877-cfdea6eaf411 (4).json" # Ensure this is the correct filename
CSV_FILENAME = "farm_data.csv" # Ensure this is the correct filename

# Service Account Email (from the JSON file or provided)
SERVICE_ACCOUNT_EMAIL = "dehkhodamap-e9f0da4ce9f6514021@ee-esmaeilkiani13877.iam.gserviceaccount.com"

# Initial map center and zoom (Dehkhoda area)
INITIAL_CENTER = [31.534442, 48.724416] # [Lat, Lon]
INITIAL_ZOOM = 12

# --- GEE Authentication ---
@st.cache_resource
def authenticate_gee(key_filename, email):
    """Authenticates GEE using a service account key file."""
    key_path = os.path.join(".", key_filename) # Look for the key file in the current directory

    if not os.path.exists(key_path):
        st.error(f"فایل کلید سرویس GEE یافت نشد: {os.path.abspath(key_path)}")
        st.info("لطفاً مطمئن شوید فایل کلید GEE با نام صحیح در کنار فایل اسکریپت قرار دارد.")
        return False

    try:
        # The service account JSON file itself contains the required information
        # We just need its path. The ee.ServiceAccountCredentials will read it.
        credentials = ee.ServiceAccountCredentials(email, key_path)
        ee.Initialize(credentials)
        st.success("Google Earth Engine با موفقیت احراز هویت شد.")
        return True
    except Exception as e:
        st.error(f"خطا در احراز هویت Google Earth Engine: {e}")
        st.warning("لطفاً مطمئن شوید سرویس اکانت شما فعال است و دسترسی‌های لازم را دارد.")
        return False

# --- Data Loading ---
@st.cache_data
def load_farm_data(csv_filename):
    """Loads farm data from the CSV file."""
    csv_path = os.path.join(".", csv_filename) # Look for the CSV file in the current directory

    if not os.path.exists(csv_path):
        st.error(f"فایل داده‌های مزارع یافت نشد: {os.path.abspath(csv_path)}")
        st.info("لطفاً مطمئن شوید فایل CSV با نام صحیح در کنار فایل اسکریپت قرار دارد.")
        return pd.DataFrame()

    try:
        # Assuming UTF-8 encoding, adjust if necessary
        df = pd.read_csv(csv_path, encoding='utf-8')

        # Check for essential columns using their Persian names
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
        for col in required_cols:
            if col not in df.columns:
                st.error(f"ستون ضروری '{col}' در فایل CSV یافت نشد.")
                return pd.DataFrame()

        # Clean data: remove rows with missing coordinates
        original_rows = len(df)
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        if len(df) < original_rows:
            st.warning(f"حذف {original_rows - len(df)} ردیف به دلیل نداشتن مختصات معتبر.")

        return df
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        return pd.DataFrame()

# --- GEE Processing Functions ---

def add_s2_indices(image):
    """Adds common agricultural index bands to a Sentinel-2 image."""
    # Sentinel-2 bands (approximate wavelengths in nm):
    # B1: Coastal aerosol (443)
    # B2: Blue (490)
    # B3: Green (560)
    # B4: Red (665)
    # B5: Red Edge 1 (705)
    # B6: Red Edge 2 (740)
    # B7: Red Edge 3 (783)
    # B8: NIR (842)
    # B8A: Narrow NIR (865)
    # B9: Water vapor (940)
    # B10: SWIR 1 (1375) - Used for cloud screening
    # B11: SWIR 1 (1610) - Used for moisture/agriculture
    # B12: SWIR 2 (2190) - Used for moisture/geology

    # Check if necessary bands exist
    band_names = image.bandNames()
    needed_bands = ['B2', 'B3', 'B4', 'B5', 'B7', 'B8', 'B11'] # Required for most indices below
    if not all(b in band_names.getInfo() for b in needed_bands):
         st.warning("تصویر ماهواره‌ای فاقد برخی باندهای ضروری برای محاسبه همه شاخص‌ها است.")
         # Return image with only the bands that are present, subsequent selections will handle missing ones.


    # NDVI = (NIR - Red) / (NIR + Red) -> (B8 - B4) / (B8 + B4)
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    # EVI = 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1) -> 2.5 * (B8 - B4) / (B8 + 6*B4 - 7.5*B2 + 1)
    # Coefficients C1=6, C2=7.5, L=1 (adjustment factor for canopy background signal)
    evi = image.expression(
        '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1.0)', {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }).rename('EVI')

    # NDMI = (NIR - SWIR1) / (NIR + SWIR1) -> (B8 - B11) / (B8 + B11)
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')

    # MSI = SWIR1 / NIR -> B11 / B8 (Higher MSI = more water stress)
    # Handle potential division by zero (e.g., water bodies where NIR is 0)
    msi = image.select('B11').divide(image.select('B8')).rename('MSI').clamp(0, 100) # Clamp to prevent extreme values


    # LAI (Leaf Area Index) - Placeholder, needs calibration. Simple linear model example based on NDVI: LAI = p * NDVI + q
    # A more common approach relates LAI non-linearly to NDVI/EVI or uses look-up tables.
    # Here, using a simple linear proxy.
    LAI_p = 6.0 # Hypothetical coefficient, NEEDS CALIBRATION
    LAI_q = 0.0 # Hypothetical coefficient, NEEDS CALIBRATION
    # Ensure NDVI is used after it's calculated in this function
    lai = ndvi.multiply(LAI_p).add(LAI_q).rename('LAI')
    # Clamp LAI to a reasonable range (e.g., 0 to 7 for most crops)
    lai = lai.max(0).min(7)


    # Biomass - Placeholder, needs calibration. Using the requested formula: Biomass = a * LAI + b
    # Here, using the LAI calculated above.
    Biomass_a = 12.0 # Hypothetical coefficient (e.g., tonnes/ha per LAI unit), NEEDS CALIBRATION
    Biomass_b = 0.0 # Hypothetical intercept, NEEDS CALIBRATION
    biomass = lai.multiply(Biomass_a).add(Biomass_b).rename('Biomass')
    # Ensure Biomass is not negative
    biomass = biomass.max(0)

    # Chlorophyll Indices - Several exist. Common ones use Red Edge bands (B5, B6, B7).
    # Example 1: Chlorophyll Index Red Edge (CIRE) = (NIR / RedEdge1) - 1 -> (B8 / B5) - 1
    if 'B5' in band_names.getInfo() and 'B8' in band_names.getInfo():
        cire = image.expression('(NIR / RE1) - 1', {
             'NIR': image.select('B8'),
             'RE1': image.select('B5')
        }).rename('CIRE')
    else:
        cire = ee.Image(-9999).rename('CIRE') # Placeholder if bands are missing

    # Example 2: Green Chlorophyll Index (CIG) = (NIR / Green) - 1 -> (B8 / B3) - 1
    if 'B3' in band_names.getInfo() and 'B8' in band_names.getInfo():
        cig = image.expression('(NIR / GREEN) - 1', {
             'NIR': image.select('B8'),
             'GREEN': image.select('B3')
        }).rename('CIG')
    else:
        cig = ee.Image(-9999).rename('CIG') # Placeholder if bands are missing


    # ET (Evapotranspiration) is not a simple band math index. It requires complex models
    # or specific GEE datasets (like MODIS ET or EEFLUX).
    # Adding a placeholder band for ET is not meaningful without a calculation method.
    # We will skip ET calculation via simple band math.

    # Combine all calculated indices into a single image
    # Filter out placeholder bands if underlying bands were missing
    indices = [ndvi, evi, ndmi, msi, lai, biomass, cire, cig]
    valid_indices = [idx for idx in indices if idx.getInfo()['bands'][0]['id'] != -9999]

    return image.addBands(valid_indices)

def get_index_time_series(image_collection, geometry, index_name, scale=10):
    """Extracts time series for a given index over a geometry (e.g., a farm point buffer)."""
    def reduce_region_on_image(image):
        # Select the desired index band
        # Ensure the band exists in the image (added by add_s2_indices)
        if index_name not in image.bandNames().getInfo():
             # print(f"Warning: Index band '{index_name}' not found in image {image.id().getInfo()}")
             return None # Skip images where the index wasn't calculated successfully

        index_band = image.select(index_name)

        # Reduce the region. Use 'mean' reducer over the specified geometry.
        try:
            mean_value = index_band.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale, # Use appropriate scale, 10m for Sentinel-2 optical
                maxPixels=1e9 # Increase maxPixels for potentially larger reduction areas
            ).get(index_name) # Get the value for the specific band name

            # Check if the result is null (e.g., geometry outside image bounds, or all pixels masked)
            if mean_value.getInfo() is None:
                return None

            # Get the image date
            date = image.date().format('YYYY-MM-dd')

            # Return as a Feature for easy conversion to a list later
            return ee.Feature(None, {
                'date': date,
                'value': mean_value
            })
        except Exception as e:
            # Catch potential GEE errors during reduction for a specific image
            print(f"Error reducing region for image {image.id().getInfo()}: {e}")
            return None

    # Map the reduction function over the image collection
    # Use .flatten() to get rid of potential None results from the map function before getInfo
    time_series_fc = image_collection.map(reduce_region_on_image).flatten()

    # Get info from GEE - this is a blocking call
    time_series_list = time_series_fc.getInfo()

    # Process the list of results into a Pandas DataFrame
    data = []
    for item in time_series_list:
        if item and item.get('properties'): # Check if item is valid and has properties
            props = item['properties']
            # Ensure 'date' and 'value' keys exist and value is not None
            if 'date' in props and 'value' in props and props['value'] is not None:
                data.append({'date': props['date'], 'value': props['value']})

    df = pd.DataFrame(data)

    # Convert 'date' column to datetime objects and sort
    if not df.empty:
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

    return df

# --- Visualization Palettes ---
# Define color palettes for different indices. Palettes go from min to max value.
# Use geemap.get_palette or define custom ones.
# We assume Bad -> Good or Dry -> Wet mapping
palettes = {
    'NDVI': ['red', 'orange', 'yellow', 'green', 'darkgreen'],      # Low Veg Health -> High Veg Health
    'EVI': ['red', 'orange', 'yellow', 'green', 'darkgreen'],       # Low Veg Health -> High Veg Health
    'NDMI': ['brown', 'yellow', 'lightblue', 'blue', 'darkblue'],   # Dry -> Wet
    'MSI': ['darkblue', 'blue', 'lightblue', 'yellow', 'brown'],    # Wet -> Dry (Higher MSI is drier)
    'LAI': ['red', 'orange', 'yellow', 'green', 'darkgreen'],       # Low LAI -> High LAI
    'Biomass': ['red', 'orange', 'yellow', 'green', 'darkgreen'],   # Low Biomass -> High Biomass
    'CIRE': ['red', 'orange', 'yellow', 'lightgreen', 'green'],     # Low Chlorophyll -> High Chlorophyll
    'CIG': ['red', 'orange', 'yellow', 'lightgreen', 'green'],      # Low Chlorophyll -> High Chlorophyll
}

# Define visualization parameters (min, max, palette) for display
vis_params = {
    'NDVI': {'min': 0.0, 'max': 0.9, 'palette': palettes['NDVI']},
    'EVI': {'min': 0.0, 'max': 0.9, 'palette': palettes['EVI']},
    'NDMI': {'min': -1.0, 'max': 1.0, 'palette': palettes['NDMI']}, # NDMI ranges from -1 to 1
    'MSI': {'min': 0.5, 'max': 3.0, 'palette': palettes['MSI']},   # Typical range for vegetation
    'LAI': {'min': 0.0, 'max': 6.0, 'palette': palettes['LAI']},   # Typical LAI for dense crops
    'Biomass': {'min': 0.0, 'max': 50.0, 'palette': palettes['Biomass']}, # Example biomass range (tonnes/ha)
    'CIRE': {'min': -0.5, 'max': 4.0, 'palette': palettes['CIRE']}, # Example range
    'CIG': {'min': -0.5, 'max': 4.0, 'palette': palettes['CIG']}, # Example range
}

# --- Streamlit App Layout ---

st.title("🌱 داشبورد پیشرفته مانیتورینگ مزارع نیشکر دهخدا")
st.write("این داشبورد وضعیت مزارع نیشکر را با استفاده از داده‌های ماهواره‌ای Sentinel-2 و Google Earth Engine نمایش می‌دهد.")

# --- GEE Authentication Check ---
gee_authenticated = authenticate_gee(GEE_KEY_FILENAME, SERVICE_ACCOUNT_EMAIL)

if not gee_authenticated:
    st.stop() # Stop the app execution if GEE authentication fails

# --- Load Data ---
df_farms = load_farm_data(CSV_FILENAME)

if df_farms.empty:
    st.warning("داده‌ای برای مزارع بارگذاری نشد یا خالی است. لطفاً فایل CSV را بررسی کنید.")
    st.stop() # Stop if no farm data is loaded

# --- Sidebar for Filtering ---
st.sidebar.header("تنظیمات داشبورد")

# Day of Week Filter (assuming 'روزهای هفته' contains comma-separated days or a single day)
# We'll get unique entries and let the user select one. A more advanced filter
# would check if the entry *contains* the selected day.
# For simplicity here, we'll filter rows where 'روزهای هفته' *exactly matches* or *contains* the selected day string.
# Let's use str.contains for better flexibility.
all_days_in_csv = sorted(df_farms['روزهای هفته'].unique().tolist())
# Create a list of unique individual days mentioned in the CSV
individual_days = set()
for entry in all_days_in_csv:
    if isinstance(entry, str):
        # Split by common separators like ',', '/', or spaces if needed
        days = [d.strip() for d in entry.replace('/', ',').split(',')]
        individual_days.update(days)

day_options = ['همه روزها'] + sorted(list(individual_days))

selected_day = st.sidebar.selectbox(
    "انتخاب روز هفته:",
    day_options
)

# Filter farms based on selected day using string contains
if selected_day != 'همه روزها':
    # Use a boolean mask where 'روزهای هفته' column contains the selected_day string
    filtered_farms_df = df_farms[
        df_farms['روزهای هفته'].astype(str).str.contains(selected_day, na=False)
    ].copy() # Use .copy() to avoid SettingWithCopyWarning
else:
    filtered_farms_df = df_farms.copy()


# Farm Name Filter
farm_names = filtered_farms_df['مزرعه'].unique().tolist()
if not farm_names:
     st.sidebar.warning("هیچ مزرعه‌ای برای روز انتخاب شده یافت نشد.")
     selected_farm_name = None
else:
    # Add a default "Select a Farm" option
    farm_names = ["--- انتخاب مزرعه ---"] + farm_names
    selected_farm_name = st.sidebar.selectbox(
        "انتخاب مزرعه:",
        farm_names
    )

selected_farm_data = None
farm_point_geometry = None

# Find the data row and create GEE geometry if a farm is selected (and not the placeholder)
if selected_farm_name and selected_farm_name != "--- انتخاب مزرعه ---":
    selected_farm_data = filtered_farms_df[filtered_farms_df['مزرعه'] == selected_farm_name]

    if not selected_farm_data.empty:
        selected_farm_data = selected_farm_data.iloc[0]
        lat = selected_farm_data['عرض جغرافیایی']
        lon = selected_farm_data['طول جغرافیایی']
        # Create GEE point geometry for the selected farm
        try:
            # GEE expects [lon, lat] for Points
            farm_point_geometry = ee.Geometry.Point(lon, lat)
        except Exception as e:
            st.error(f"مختصات مزرعه '{selected_farm_name}' معتبر نیست: طول={lon}, عرض={lat}. خطا: {e}")
            farm_point_geometry = None
            selected_farm_data = None # Invalidate farm data if geometry fails
    else:
         # This case should theoretically not happen if selected_farm_name is in farm_names,
         # but added for robustness.
         st.warning(f"اطلاعات مزرعه '{selected_farm_name}' در داده‌های فیلتر شده یافت نشد.")
         selected_farm_name = None # Reset selection
         selected_farm_data = None
         farm_point_geometry = None


# Display message or map if no farm is selected or data is invalid
if selected_farm_name is None or selected_farm_name == "--- انتخاب مزرعه ---" or selected_farm_data is None or farm_point_geometry is None:
    st.info("لطفاً از پنل سمت چپ (نوار کناری) یک روز و سپس یک مزرعه را انتخاب کنید.")
    # Display a general map centered on the initial location
    m = geemap.Map(center=INITIAL_CENTER, zoom=INITIAL_ZOOM)
    m.add_basemap('HYBRID')
    m.add_colorbar(palettes['NDVI'], 0, 1, caption='NDVI Placeholder Legend', layer_name='NDVI Placeholder')
    st.write("نقشه کلی منطقه دهخدا.")
    m.to_streamlit(height=500) # Set a default height for the map
    st.stop() # Stop execution until a valid farm is selected


# --- Display Selected Farm Info ---
st.header(f"وضعیت مزرعه: {selected_farm_name}")
st.write(f"**مختصات:** عرض جغرافیایی: {selected_farm_data['عرض جغرافیایی']}, طول جغرافیایی: {selected_farm_data['طول جغرافیایی']}")
# Use .get() with a default value in case columns are missing in some CSV rows
st.write(f"**اطلاعات:** کانال: {selected_farm_data.get('کانال', 'نامعلوم')}, اداره: {selected_farm_data.get('اداره', 'نامعلوم')}, مساحت: {selected_farm_data.get('مساحت داشت', 'نامعلوم')} هکتار, واریته: {selected_farm_data.get('واریته', 'نامعلوم')}, سن: {selected_farm_data.get('سن', 'نامعلوم')}")


# --- GEE Processing for Map and Current Status ---

st.subheader("نقشه‌های وضعیت فعلی")
st.info("در حال پردازش داده‌های ماهواره‌ای اخیر برای نمایش نقشه‌ها... این عملیات ممکن است چند لحظه طول بکشد.")

# Define date range for current status map (e.g., look back 45 days to find a recent cloud-free image)
now = ee.Date(ee.Algorithms.TemporalComposite.NOW)
start_date_map = now.advance(-45, 'day') # Look back 45 days
end_date_map = now

# Load Sentinel-2 collection for the map area
# Filter bounds by a slightly larger area around the farm point for context
map_area = farm_point_geometry.buffer(2000) # Buffer by 2000 meters

s2_collection_map = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                      .filterDate(start_date_map, end_date_map) \
                      .filterBounds(map_area)

# Simple cloud filter using QA60 band (bits 10 and 11 are clouds)
def mask_s2_clouds(image):
    qa = image.select('QA60')
    # Both flags should be zero, indicating clear conditions.
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    # Return the masked image and add the original bands
    # Also scale bands 2-12 by 0.0001 (Surface Reflectance)
    return image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"]) # Scale SR bands


s2_collection_map_masked = s2_collection_map.map(mask_s2_clouds) \
                                            .select(['B2', 'B3', 'B4', 'B5', 'B7', 'B8', 'B11']) # Select relevant bands before adding indices

# Select the latest image from the filtered, masked collection
# Sort by time_start descending and take the first one
latest_image = s2_collection_map_masked.sort('system:time_start', False).first()


# --- Display Map ---
m = geemap.Map(center=[lat, lon], zoom=15) # Center map on the selected farm
m.add_basemap('HYBRID') # Add a base map

if latest_image is None:
    st.warning("تصویر ماهواره‌ای اخیر و بدون ابر برای این منطقه در بازه زمانی انتخابی یافت نشد. نمایش نقشه‌های شاخص ممکن نیست.")
    st.info("نقشه روی موقعیت مزرعه انتخابی نمایش داده می‌شود.")
    m.add_marker([lat, lon], tooltip=selected_farm_name) # Add a marker for the farm
else:
    st.info(f"نقشه بر اساس تصویر ماهواره‌ای از تاریخ: {ee.Date(latest_image.get('system:time_start')).format('YYYY-MM-dd').getInfo()} نمایش داده می‌شود.")
    # Add index bands to the latest image
    image_with_indices = add_s2_indices(latest_image)

    # Get list of actual bands (indices) present in the image after adding them
    available_indices = image_with_indices.bandNames().getInfo()

    # Add the calculated index layers to the map
    for index_name, viz in vis_params.items():
        # Only try to add the layer if the index band is actually present in the image
        if index_name in available_indices:
            try:
                m.addLayer(image_with_indices.select(index_name), viz, index_name)
                # Add legend for this layer
                # Adjust legend caption based on whether palette is low->high or high->low
                legend_caption = f'{index_name} (مقادیر پایین \u2192 مقادیر بالا)' # Default: Low -> High
                if index_name == 'MSI':
                     legend_caption = f'{index_name} (تنش آبی کم \u2192 تنش آبی زیاد)' # MSI is High -> Low Water
                elif index_name in ['NDMI']:
                    legend_caption = f'{index_name} (خشک \u2192 مرطوب)' # NDMI is Low -> High Water

                m.add_colorbar(viz['palette'], viz['min'], viz['max'], caption=legend_caption, layer_name=index_name)

            except Exception as e:
                 st.error(f"Error adding layer {index_name} to map: {e}")
        else:
            # This warning is already shown inside add_s2_indices, but useful here too
            # st.warning(f"باند '{index_name}' در تصویر یافت نشد و لایه آن اضافه نشد.")
            pass # Ignore if the band wasn't successfully created


    # Add the farm point to the map
    m.addLayer(farm_point_geometry, {'color': 'red'}, selected_farm_name)

# Display the map using geemap's Streamlit component
m.to_streamlit(height=600) # Set map height


st.write("""
**راهنمای شاخص‌ها و رنگ‌بندی:**
-   **NDVI (شاخص نرمال‌شده پوشش گیاهی):** سلامت و تراکم پوشش گیاهی (قرمز: کم \u2192 سبز تیره: زیاد)
-   **EVI (شاخص پوشش گیاهی تقویت‌شده):** مشابه NDVI، اما در مناطق پر پوشش یا با تداخل خاک بهتر عمل می‌کند. (قرمز: کم \u2192 سبز تیره: زیاد)
-   **NDMI (شاخص نرمال‌شده رطوبت تفاضلی):** میزان رطوبت پوشش گیاهی (قهوه‌ای: خشک \u2192 آبی تیره: مرطوب)
-   **MSI (شاخص تنش رطوبتی):** میزان تنش آبی در گیاه (آبی تیره: رطوبت زیاد \u2192 قهوه‌ای: تنش زیاد)
-   **LAI (شاخص سطح برگ):** مجموع سطح برگ در واحد سطح زمین (قرمز: کم \u2192 سبز تیره: زیاد) *(نیاز به کالیبراسیون)*
-   **Biomass (زیست‌توده):** مقدار ماده خشک پوشش گیاهی در واحد سطح (قرمز: کم \u2192 سبز تیره: زیاد) *(نیاز به کالیبراسیون)*
-   **CIRE & CIG (شاخص‌های کلروفیل):** میزان کلروفیل در برگ‌ها، مرتبط با سلامت و نیتروژن گیاه (قرمز: کم \u2192 سبز: زیاد)
""")

st.warning("""
**توجه مهم در مورد LAI و Biomass:**
شاخص‌های LAI و Biomass در این داشبورد بر اساس مدل‌های ساده‌ی جایگزین از NDVI/LAI محاسبه شده‌اند (Biomass = a * LAI + b و LAI = p * NDVI + q). **ضرایب این مدل‌ها (a, b, p, q) کالیبره *نشده‌اند* و مقادیر آن‌ها صرفاً جهت نمایش روند تقریبی در طول زمان می‌باشند.** برای دستیابی به مقادیر دقیق و قابل اتکا برای LAI و Biomass، این مدل‌ها باید با اندازه‌گیری‌های زمینی در منطقه مزارع نیشکر دهخدا کالیبره شوند یا از محصولات آماده GEE که کالیبراسیون بهتری دارند استفاده گردد. شاخص ET در حال حاضر پیاده‌سازی نشده است.
""")

# --- Time Series Analysis ---
st.subheader("تحلیل زمانی شاخص‌ها")

# Define date range for time series (e.g., last 1-2 years)
ts_years_lookback = st.slider("بازه‌ی زمانی (سال) برای نمودارها:", 1, 5, 1)
ts_start_date = now.advance(-ts_years_lookback, 'year')
ts_end_date = now # Up to today

st.write(f"استخراج سری زمانی از {ts_start_date.format('YYYY-MM-dd').getInfo()} تا {ts_end_date.format('YYYY-MM-dd').getInfo()}")
st.info("در حال استخراج داده‌های سری زمانی برای شاخص‌ها از Google Earth Engine. این عملیات ممکن است بسته به بازه‌ی زمانی انتخاب‌شده و حجم داده‌ها کمی زمان‌بر باشد. لطفاً صبور باشید.")

# Define the buffer size for time series extraction around the point (in meters)
# Using a small buffer is often a compromise between point accuracy and avoiding single-pixel noise/errors
ts_buffer_size = 30 # meters - Adjust as needed (e.g., 10m is Sentinel pixel size, 30m-50m covers a small area)
ts_geometry = farm_point_geometry.buffer(ts_buffer_size)


# Load Sentinel-2 collection for time series (wider date range, focus on farm area)
ts_collection_raw = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                      .filterDate(ts_start_date, ts_end_date) \
                      .filterBounds(ts_geometry.buffer(100)) # Filter slightly beyond the reduction area


# Apply cloud masking and scale before adding indices
ts_collection_masked = ts_collection_raw.map(mask_s2_clouds) \
                                        .select(['B2', 'B3', 'B4', 'B5', 'B7', 'B8', 'B11']) # Select relevant bands


# Map the function to add indices over the *entire* collection
# This adds index bands to every image in the collection
ts_collection_with_indices = ts_collection_masked.map(add_s2_indices)


# Select indices to plot time series for
indices_to_plot = ['NDVI', 'EVI', 'NDMI', 'MSI', 'LAI', 'Biomass', 'CIRE', 'CIG']
# Filter to only include indices that were potentially added by add_s2_indices (based on bands existing)
# A simpler way here is to just try to extract for all and handle empty results.

# Use a list to store dataframes for each index's time series
all_time_series_dfs = []

# Get time series for each index
progress_bar = st.progress(0)
status_text = st.empty()
total_indices = len(indices_to_plot)

for i, index_name in enumerate(indices_to_plot):
    status_text.text(f"در حال استخراج سری زمانی برای شاخص: {index_name} ({i+1}/{total_indices})")
    progress_bar.progress((i + 1) / total_indices)

    try:
        # Get the time series for the current index
        # Note: get_index_time_series handles filtering images that have the specific band
        index_ts_df = get_index_time_series(ts_collection_with_indices.select(index_name), # Select only the band needed to speed up reduction
                                            ts_geometry,
                                            index_name)

        if not index_ts_df.empty:
            index_ts_df['شاخص'] = index_name # Add a column to identify the index
            all_time_series_dfs.append(index_ts_df)
            # st.write(f"استخراج داده برای {index_name} موفقیت‌آمیز بود. تعداد نقاط: {len(index_ts_df)}")
        # else:
            # st.info(f"هیچ نقطه داده‌ای برای شاخص {index_name} در بازه زمانی یافت نشد.")

    except Exception as e:
         st.error(f"خطا در استخراج سری زمانی برای شاخص {index_name}: {e}")
         # Continue to the next index

progress_bar.empty()
status_text.empty()


# Combine all time series dataframes
if all_time_series_dfs:
    combined_ts_df = pd.concat(all_time_series_dfs, ignore_index=True)

    # Create Plotly time series chart
    fig = px.line(combined_ts_df, x='date', y='value', color='شاخص',
                  title=f'سری زمانی شاخص‌ها برای مزرعه {selected_farm_name}',
                  labels={'date': 'تاریخ', 'value': 'مقدار شاخص', 'شاخص': 'شاخص'},
                  template='plotly_white') # Use a clean template

    fig.update_layout(
        hovermode='x unified', # Improves hover experience
        xaxis_title="تاریخ",
        yaxis_title="مقدار شاخص",
        legend_title="شاخص"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Optional: Show raw time series data
    if st.checkbox("نمایش جدول داده‌های سری زمانی استخراج شده"):
         st.dataframe(combined_ts_df)

    # Optional: Download time series data
    # Pivot the data for easier download if preferred, or keep combined
    # combined_ts_pivot = combined_ts_df.pivot(index='date', columns='شاخص', values='value')
    csv_data = combined_ts_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="دانلود داده‌های سری زمانی (CSV)",
        data=csv_data,
        file_name=f'{selected_farm_name}_time_series.csv',
        mime='text/csv',
    )

else:
    st.warning("داده‌های سری زمانی برای شاخص‌های انتخابی در بازه زمانی مشخص دریافت نشد. لطفاً بازه زمانی یا فیلتر ابرها را بررسی کنید.")


# --- Farm Ranking (Simplified) ---
# Implementing a full ranking table for ALL farms dynamically would require processing
# the latest image/data for ALL farms whenever the app runs, which can be slow and
# hit GEE limits for many farms.
# A simplified approach is to show the values for the *selected* farm from the latest image.
st.subheader("خلاصه وضعیت شاخص‌ها برای مزرعه انتخابی (آخرین تصویر)")

if latest_image is not None and farm_point_geometry is not None:
    st.info("در حال استخراج مقادیر شاخص‌ها از آخرین تصویر برای مزرعه انتخابی...")
    try:
        # Reduce region for the selected point on the latest image with calculated indices
        # Use the same buffer size as time series or smaller/larger based on desired area
        reduction_geometry = farm_point_geometry.buffer(ts_buffer_size) # Use same buffer as TS
        reduction_scale = 10 # Sentinel-2 resolution

        # Ensure we only try to reduce bands that were actually added
        available_indices_in_latest = [idx for idx in vis_params.keys() if idx in image_with_indices.bandNames().getInfo()]

        if available_indices_in_latest:
             latest_values = image_with_indices.select(available_indices_in_latest).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=reduction_geometry,
                scale=reduction_scale,
                maxPixels=1e9
             ).getInfo()

             if latest_values:
                 # Display values in a nice format
                 st.write("مقادیر میانگین شاخص‌ها در اطراف نقطه مرکزی مزرعه از آخرین تصویر ماهواره‌ای:")
                 values_df = pd.DataFrame([latest_values]).T.reset_index()
                 values_df.columns = ['شاخص', 'مقدار']
                 # Add basic interpretation based on typical ranges and good/bad
                 values_df['تفسیر (تقریبی)'] = values_df.apply(lambda row:
                     f"({vis_params.get(row['شاخص'], {}).get('min', '-')} تا {vis_params.get(row['شاخص'], {}).get('max', '-')})"
                     + (f" | رنگ در نقشه: {'سبز/آبی تیره (خوب/مرطوب)' if row['مقدار'] > vis_params.get(row['شاخص'], {}).get('max', 1)/2 else 'قرمز/قهوه ای (بد/خشک)'}" if row['شاخص'] in ['NDVI', 'EVI', 'LAI', 'Biomass', 'NDMI', 'CIG', 'CIRE'] else f" | رنگ در نقشه: {'قهوه ای (تنش زیاد)' if row['مقشاخص'] > vis_params.get(row['شاخص'], {}).get('max', 3)/2 else 'آبی تیره (تنش کم)'}" if row['شاخص'] == 'MSI' else ""),
                     axis=1
                 )

                 st.dataframe(values_df)

             else:
                 st.warning("مقادیر شاخص از آخرین تصویر برای مزرعه انتخابی استخراج نشد (ممکن است منطقه پوشش ابر داشته باشد).")
        else:
             st.warning("هیچ باندی برای استخراج مقادیر از آخرین تصویر موجود نیست.")

    except Exception as e:
        st.error(f"خطا در استخراج مقادیر شاخص‌ها از آخرین تصویر: {e}")
else:
    st.info("برای نمایش خلاصه وضعیت شاخص‌ها، تصویر ماهواره‌ای اخیر باید موجود باشد.")

st.markdown("---")

st.markdown("""
### راهنمای استفاده
1.  از نوار کناری سمت راست، "روز هفته" مورد نظر را انتخاب کنید. لیست مزارع بر اساس روز فیلتر می‌شود.
2.  از نوار کناری، "مزرعه" مورد نظر خود را انتخاب کنید.
3.  داشبورد اطلاعات مزرعه، نقشه‌های شاخص‌های مختلف بر اساس آخرین تصویر ماهواره‌ای موجود، و نمودارهای سری زمانی تغییرات شاخص‌ها در بازه زمانی مشخص را نمایش می‌دهد.
4.  با استفاده از چرخ ماوس یا ابزارهای روی نقشه، روی نقشه زوم و پَن کنید. می‌توانید لایه‌های مختلف شاخص را روشن/خاموش کنید.
5.  می‌توانید بازه زمانی نمودارهای سری زمانی را تغییر دهید.
6.  داده‌های سری زمانی را می‌توانید به فرمت CSV دانلود کنید.
""")

# --- Footer ---
st.sidebar.markdown("---")
st.sidebar.write("طراحی و توسعه برای مزارع نیشکر دهخدا")
st.sidebar.write("توسط اسماعیل کیانی")

st.sidebar.markdown("---")
st.sidebar.subheader("نحوه اجرا:")
st.sidebar.write(f"۱. فایل `{GEE_KEY_FILENAME}` و `{CSV_FILENAME}` را در کنار فایل اسکریپت پایتون قرار دهید.")
st.sidebar.write("۲. مطمئن شوید کتابخانه‌های مورد نیاز نصب شده‌اند: `streamlit geemap earthengine-api pandas plotly`")
st.sidebar.write("۳. در ترمینال، به پوشه پروژه رفته و دستور زیر را اجرا کنید:")
st.sidebar.code("streamlit run dehkhoda_dashboard.py") # Replace dehkhoda_dashboard.py with your script name
st.sidebar.write("۴. سرویس اکانت GEE باید دسترسی کافی به داده‌های Sentinel-2 داشته باشد.")
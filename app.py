import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap # Using foliumap backend for Streamlit compatibility
import folium
import os
import json
from datetime import datetime, timedelta

# ==============================================================================
# Configuration and Initialization
# ==============================================================================

# --- Page Configuration ---
st.set_page_config(
    page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا",
    page_icon="🌾",
    layout="wide", # Use wide layout for better map display
    initial_sidebar_state="expanded" # Keep sidebar open initially
)

# --- Constants ---
CSV_FILE_PATH = 'output (1).csv'
SERVICE_ACCOUNT_KEY_PATH = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
SERVICE_ACCOUNT_EMAIL = 'dehkhodamap-e9f0da4ce9f6514021@ee-esmaeilkiani13877.iam.gserviceaccount.com'
DEFAULT_LATITUDE = 31.534442
DEFAULT_LONGITUDE = 48.724416
DEFAULT_ZOOM = 13
AOI_BUFFER_METERS = 500 # Buffer radius around the farm point for analysis
DATE_RANGE_MONTHS = 3 # Analyze data for the last 3 months

# --- GEE Authentication ---
@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def authenticate_gee(service_account_key_path, service_account_email):
    """Authenticates Google Earth Engine using a Service Account."""
    try:
        # Check if the key file exists
        if not os.path.exists(service_account_key_path):
            st.error(f"خطا: فایل کلید سرویس در مسیر '{service_account_key_path}' یافت نشد.")
            st.stop()

        # Load credentials from the file
        with open(service_account_key_path) as f:
            credentials_dict = json.load(f)

        credentials = ee.ServiceAccountCredentials(service_account_email, service_account_key_path)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Authenticated Successfully using Service Account.")
        return True # Indicate successful authentication
    except ee.EEException as e:
        st.error(f"خطا در احراز هویت Google Earth Engine: {e}")
        st.error("لطفاً مطمئن شوید فایل کلید سرویس معتبر است و دسترسی‌های لازم را دارد.")
        st.stop() # Stop execution if authentication fails
    except FileNotFoundError:
        st.error(f"خطا: فایل کلید سرویس در مسیر '{service_account_key_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"یک خطای غیرمنتظره در هنگام احراز هویت رخ داد: {e}")
        st.stop()

# --- Data Loading ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path):
    """Loads farm data from the CSV file."""
    try:
        df = pd.read_csv(csv_path, encoding='utf-8') # Specify UTF-8 encoding for Persian characters
        # Basic data cleaning/validation
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
        if not all(col in df.columns for col in required_cols):
            st.error(f"خطا: فایل CSV باید شامل ستون‌های {required_cols} باشد.")
            st.stop()
        # Convert coordinate columns to numeric, coercing errors
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        # Handle potential missing coordinates indicated by the flag or NaN values
        df['coordinates_missing'] = df['coordinates_missing'].fillna(False).astype(bool) | df['طول جغرافیایی'].isna() | df['عرض جغرافیایی'].isna()
        # Fill NaN in 'روزهای هفته' with a placeholder if necessary, or handle appropriately
        df['روزهای هفته'] = df['روزهای هفته'].fillna('نامشخص') # Or drop rows: df.dropna(subset=['روزهای هفته'])
        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطا در بارگذاری یا پردازش فایل CSV: {e}")
        st.stop()

# --- GEE Image Processing Functions ---

def mask_s2_clouds(image):
    """Masks clouds in Sentinel-2 SR images using the SCL band."""
    scl = image.select('SCL')
    # Select clear (4), vegetation (5), and non-vegetated (6) pixels. Also include water (7).
    # Avoid cloud shadows (3), clouds medium probability (8), clouds high probability (9), cirrus (10).
    mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7))
    # Also mask based on QA60 band if needed (though SCL is generally better for SR)
    # qa = image.select('QA60')
    # cloud_bit_mask = 1 << 10
    # cirrus_bit_mask = 1 << 11
    # mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"]) # Scale factor for SR

def calculate_ndvi(image):
    """Calculates NDVI."""
    # NDVI = (NIR - Red) / (NIR + Red)
    # Sentinel-2 Bands: NIR=B8, Red=B4
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    return image.addBands(ndvi)

def calculate_evi(image):
    """Calculates EVI."""
    # EVI = 2.5 * (NIR - Red) / (NIR + 6 * Red - 7.5 * Blue + 1)
    # Sentinel-2 Bands: NIR=B8, Red=B4, Blue=B2
    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }).rename('EVI')
    return image.addBands(evi)

def calculate_ndmi(image):
    """Calculates NDMI (Normalized Difference Moisture Index)."""
    # NDMI = (NIR - SWIR1) / (NIR + SWIR1)
    # Sentinel-2 Bands: NIR=B8, SWIR1=B11
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    return image.addBands(ndmi)

def estimate_lai(image):
    """Estimates LAI using a simple NDVI-based formula (requires calibration)."""
    # Example formula: LAI = sqrt(NDVI * (1 + NDVI)) - This is highly empirical!
    # A more common simple approach might be linear or exponential based on NDVI
    # LAI = a * NDVI + b OR LAI = exp(c * NDVI + d)
    # Using a simple placeholder: LAI directly proportional to NDVI (for demonstration)
    # For a slightly more standard empirical approach (e.g., based on SNAP toolbox relations):
    # lai = image.expression('3.618 * EVI - 0.118', {'EVI': image.select('EVI')}).rename('LAI_EVI') # If EVI is calculated
    # Or based on NDVI:
    lai_ndvi = image.expression('sqrt(NDVI * (1 + NDVI))', {'NDVI': image.select('NDVI')}).rename('LAI') # Placeholder
    # Ensure LAI is not negative
    lai_ndvi = lai_ndvi.where(lai_ndvi.gt(0), 0)
    return image.addBands(lai_ndvi)

def estimate_biomass(image):
    """Estimates Biomass using NDVI as a proxy (requires calibration)."""
    # Biomass is often correlated with NDVI or LAI.
    # Using NDVI directly as a proxy indicator.
    biomass_proxy = image.select('NDVI').rename('Biomass_Proxy')
    return image.addBands(biomass_proxy)

def get_image_collection(aoi, start_date, end_date):
    """Gets, filters, masks, and processes Sentinel-2 image collection."""
    s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') # Use Harmonized SR
               .filterBounds(aoi)
               .filterDate(start_date, end_date)
               .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) # Pre-filter by metadata
               .map(mask_s2_clouds) # Apply cloud masking
               .map(calculate_ndvi)
               .map(calculate_evi)
               .map(calculate_ndmi)
               .map(estimate_lai) # Add estimated LAI
               .map(estimate_biomass) # Add Biomass proxy
               )
    return s2_sr_col

# --- Visualization Parameters ---
ndvi_vis = {
    'min': 0.0, 'max': 1.0,
    'palette': ['#FF0000', '#FFA500', '#FFFF00', '#ADFF2F', '#008000'] # Red -> Orange -> Yellow -> GreenYellow -> Green
}
evi_vis = {
    'min': 0.0, 'max': 1.0,
    'palette': ['#FF0000', '#FFA500', '#FFFF00', '#ADFF2F', '#008000'] # Similar palette for EVI
}
ndmi_vis = {
    'min': -0.5, 'max': 0.8, # Typical range for NDMI
    'palette': ['#FF0000', '#FFA500', '#FFFF00', '#ADD8E6', '#0000FF'] # Red -> Orange -> Yellow -> LightBlue -> Blue
}
lai_vis = {
    'min': 0.0, 'max': 6.0, # Typical LAI range
    'palette': ['#FFFFFF', '#CE7E45', '#DF923D', '#F1B555', '#FCD163', '#99B718', '#74A901', '#66A000', '#529400', '#3E8601', '#207401', '#056201', '#004C00', '#023B01', '#012E01', '#011D01', '#011301'] # Common LAI palette
}
biomass_proxy_vis = {
    'min': 0.0, 'max': 1.0, # Same range as NDVI proxy
    'palette': ['#FDE725', '#7AD151', '#22A884', '#2A788E', '#414487', '#440154'] # Viridis palette often used for biomass/productivity
}
rgb_vis = {
    'min': 0.0, 'max': 0.3, # Max value for SR reflectance (adjust as needed)
    'bands': ['B4', 'B3', 'B2'] # Red, Green, Blue
}

# --- Main Application Logic ---
def main():
    """Main function to run the Streamlit application."""

    # --- Authentication ---
    if 'gee_authenticated' not in st.session_state:
        st.session_state.gee_authenticated = authenticate_gee(SERVICE_ACCOUNT_KEY_PATH, SERVICE_ACCOUNT_EMAIL)

    if not st.session_state.gee_authenticated:
        st.warning("اتصال به Google Earth Engine برقرار نشد. لطفاً صفحه را رفرش کنید یا تنظیمات را بررسی نمایید.")
        st.stop()

    # --- Load Data ---
    df_farms = load_farm_data(CSV_FILE_PATH)

    # --- Sidebar ---
    st.sidebar.title("تنظیمات نمایش")
    st.sidebar.header("فیلتر مزارع")

    # -- Day of the Week Filter --
    available_days = sorted(df_farms['روزهای هفته'].unique())
    selected_day = st.sidebar.selectbox(
        "انتخاب روز هفته:",
        options=available_days,
        index=0 # Default to the first day
    )

    # Filter farms based on selected day
    df_filtered_by_day = df_farms[df_farms['روزهای هفته'] == selected_day].copy()

    # Check if any farms are available for the selected day
    if df_filtered_by_day.empty:
        st.sidebar.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.")
        st.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' در فایل CSV تعریف نشده است. لطفاً روز دیگری را انتخاب کنید یا فایل داده را بررسی نمایید.")
        st.stop() # Stop if no farms match the day

    # Remove farms with missing coordinates from selection
    df_valid_farms = df_filtered_by_day[~df_filtered_by_day['coordinates_missing']].copy()
    if df_valid_farms.empty:
         st.sidebar.warning(f"تمام مزارع برای روز '{selected_day}' فاقد مختصات معتبر هستند.")
         st.warning(f"تمام مزارع برای روز '{selected_day}' فاقد مختصات معتبر در فایل CSV هستند.")
         st.stop()

    # -- Farm Selection Dropdown --
    available_farms = sorted(df_valid_farms['مزرعه'].unique())
    selected_farm_name = st.sidebar.selectbox(
        "انتخاب مزرعه:",
        options=available_farms,
        index=0 # Default to the first farm in the filtered list
    )

    # Get selected farm details
    selected_farm_data = df_valid_farms[df_valid_farms['مزرعه'] == selected_farm_name].iloc[0]
    farm_lat = selected_farm_data['عرض جغرافیایی']
    farm_lon = selected_farm_data['طول جغرافیایی']

    # --- Display Selected Farm Info ---
    st.sidebar.header("اطلاعات مزرعه انتخاب شده")
    st.sidebar.markdown(f"**نام مزرعه:** {selected_farm_data['مزرعه']}")
    st.sidebar.markdown(f"**کانال:** {selected_farm_data.get('کانال', 'N/A')}") # Use .get for optional columns
    st.sidebar.markdown(f"**اداره:** {selected_farm_data.get('اداره', 'N/A')}")
    st.sidebar.markdown(f"**مساحت داشت:** {selected_farm_data.get('مساحت داشت', 'N/A')}")
    st.sidebar.markdown(f"**واریته:** {selected_farm_data.get('واریته', 'N/A')}")
    st.sidebar.markdown(f"**سن:** {selected_farm_data.get('سن', 'N/A')}")
    st.sidebar.markdown(f"**روز هفته:** {selected_farm_data['روزهای هفته']}")
    st.sidebar.markdown(f"**مختصات:** ({farm_lat:.6f}, {farm_lon:.6f})")

    # --- Map Section ---
    st.header(f"نقشه و شاخص‌های مزرعه: {selected_farm_name}")

    # Create AOI (Area of Interest) point and buffer
    farm_point = ee.Geometry.Point([farm_lon, farm_lat])
    aoi = farm_point.buffer(AOI_BUFFER_METERS)

    # Define date range for analysis
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DATE_RANGE_MONTHS * 30) # Approximate months
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    st.info(f"دوره زمانی تحلیل: {start_date_str} تا {end_date_str}")

    # Get processed image collection
    with st.spinner("در حال پردازش تصاویر ماهواره‌ای... لطفاً منتظر بمانید."):
        image_collection = get_image_collection(aoi, start_date_str, end_date_str)

        # Check if the collection is empty
        collection_size = image_collection.size().getInfo()
        if collection_size == 0:
            st.warning("هیچ تصویر ماهواره‌ای مناسبی (بدون ابر) در محدوده زمانی و مکانی انتخاب شده یافت نشد.")
            st.warning("لطفاً دوره زمانی را تغییر دهید یا منتظر تصاویر جدید بمانید.")
            # Display a basic map without GEE layers if no images found
            Map = geemap.Map(location=[farm_lat, farm_lon], zoom=DEFAULT_ZOOM, add_google_map=False)
            Map.add_basemap("HYBRID")
            # Add marker for the farm
            folium.Marker(
                location=[farm_lat, farm_lon],
                popup=f"مزرعه: {selected_farm_name}\nLat: {farm_lat:.4f}, Lon: {farm_lon:.4f}",
                tooltip=selected_farm_name,
                icon=folium.Icon(color='green')
            ).add_to(Map)
            Map.add_layer_control()
            Map.to_streamlit(height=600)
            st.stop() # Stop further processing if no images

        # Create a median composite image for visualization
        median_image = image_collection.median().clip(aoi) # Clip to AOI for cleaner display

    # --- Initialize Map ---
    Map = geemap.Map(location=[farm_lat, farm_lon], zoom=DEFAULT_ZOOM, add_google_map=False)
    Map.add_basemap("HYBRID") # Use Satellite Hybrid basemap

    # --- Add Layers to Map ---
    try:
        # Add RGB Layer
        Map.addLayer(median_image, rgb_vis, 'تصویر واقعی (RGB)')

        # Add Index Layers
        Map.addLayer(median_image.select('NDVI'), ndvi_vis, 'شاخص NDVI', True) # Show NDVI by default
        Map.addLayer(median_image.select('EVI'), evi_vis, 'شاخص EVI', False)
        Map.addLayer(median_image.select('NDMI'), ndmi_vis, 'شاخص رطوبت NDMI', False)
        Map.addLayer(median_image.select('LAI'), lai_vis, 'شاخص سطح برگ (LAI تخمینی)', False)
        Map.addLayer(median_image.select('Biomass_Proxy'), biomass_proxy_vis, 'پروکسی بیوماس (مبتنی بر NDVI)', False)

        # Add marker for the selected farm
        folium.Marker(
            location=[farm_lat, farm_lon],
            popup=f"مزرعه: {selected_farm_name}\nLat: {farm_lat:.4f}, Lon: {farm_lon:.4f}",
            tooltip=selected_farm_name,
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(Map)

        # Add AOI boundary (optional)
        Map.add_geojson(aoi.getInfo(), layer_name="محدوده تحلیل (AOI)", style={'color': 'yellow', 'fillOpacity': 0.0})

        # Add Layer Control
        Map.add_layer_control()

        # Add Legends
        Map.add_legend(title="NDVI", builtin_legend='NDVI', palette=ndvi_vis['palette'])
        # Add other legends if needed, position them carefully
        # Map.add_legend(title="EVI", palette=evi_vis['palette'], min=evi_vis['min'], max=evi_vis['max'], position='bottomright')
        # Map.add_legend(title="NDMI", palette=ndmi_vis['palette'], min=ndmi_vis['min'], max=ndmi_vis['max'], position='bottomright')

        # --- Display Map ---
        Map.to_streamlit(height=600) # Adjust height as needed

    except ee.EEException as e:
        st.error(f"خطا در پردازش یا نمایش لایه‌های نقشه: {e}")
        st.error("ممکن است مشکلی در داده‌های GEE یا محاسبه شاخص‌ها وجود داشته باشد.")
    except Exception as e:
         st.error(f"یک خطای غیرمنتظره در نمایش نقشه رخ داد: {e}")


    # --- Time Series Charts Section ---
    st.header("نمودارهای زمانی شاخص‌ها")
    st.markdown(f"روند تغییرات شاخص‌ها برای مزرعه **{selected_farm_name}** در {DATE_RANGE_MONTHS} ماه گذشته")

    # Select indices for charting
    indices_to_chart = ['NDVI', 'EVI', 'NDMI', 'LAI', 'Biomass_Proxy']
    selected_indices = st.multiselect(
        "انتخاب شاخص‌ها برای نمایش در نمودار:",
        options=indices_to_chart,
        default=['NDVI', 'EVI'] # Default selections
    )

    if selected_indices:
        with st.spinner("در حال تولید نمودارهای زمانی..."):
            try:
                # Use geemap's built-in charting capabilities if possible, or extract data
                # geemap's chart functions might require different setup for streamlit
                # Alternative: Extract data and plot with Streamlit/Altair/Plotly

                # Extract time series data
                ts_data = image_collection.select(selected_indices).map(lambda image: image.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=30 # Adjust scale based on data resolution (10m for Sentinel-2 relevant bands)
                ).set('system:time_start', image.get('system:time_start')))

                # Filter out null results
                ts_data_filtered = ts_data.filter(ee.Filter.notNull(ts_data.first().keys()))

                # Get data to client-side (can be slow for long series/many indices)
                ts_list = ts_data_filtered.getInfo()['features']

                if not ts_list:
                    st.warning("داده‌ای برای رسم نمودار در این دوره یافت نشد.")
                else:
                    # Convert to Pandas DataFrame for easier plotting
                    data_for_df = []
                    for feature in ts_list:
                        props = feature['properties']
                        row = {'date': datetime.fromtimestamp(props['system:time_start'] / 1000.0)}
                        for index_name in selected_indices:
                            # Check if index exists in properties (might be null if calculation failed for that image)
                            row[index_name] = props.get(index_name)
                        data_for_df.append(row)

                    df_chart = pd.DataFrame(data_for_df)
                    df_chart = df_chart.set_index('date')
                    df_chart = df_chart.dropna(axis=1, how='all') # Drop columns if all values are NaN
                    df_chart = df_chart.dropna(axis=0, how='any') # Drop rows with any NaN for cleaner plot

                    if not df_chart.empty and not df_chart.columns.intersection(selected_indices).empty:
                         # Melt DataFrame for Altair/Streamlit native charts
                        df_melt = df_chart.reset_index().melt('date', var_name='شاخص', value_name='مقدار')

                        # Display line chart using Streamlit's native charting
                        st.line_chart(df_chart[selected_indices])

                        # Or use Altair for more customization (optional)
                        # import altair as alt
                        # chart = alt.Chart(df_melt).mark_line(point=True).encode(
                        #     x='date:T',
                        #     y='مقدار:Q',
                        #     color='شاخص:N',
                        #     tooltip=['date:T', 'شاخص:N', 'مقدار:Q']
                        # ).interactive()
                        # st.altair_chart(chart, use_container_width=True)

                        # Display data table
                        st.subheader("داده‌های نمودار")
                        st.dataframe(df_chart.style.format("{:.3f}"))
                    else:
                         st.warning("داده معتبری برای رسم نمودار پس از پردازش یافت نشد.")


            except ee.EEException as e:
                st.error(f"خطا در دریافت داده‌های سری زمانی از GEE: {e}")
            except Exception as e:
                st.error(f"خطا در پردازش یا نمایش نمودار: {e}")
    else:
        st.info("لطفاً حداقل یک شاخص را برای نمایش نمودار انتخاب کنید.")

    # --- Farm Ranking Table (Placeholder/Simplified) ---
    # Note: Calculating indices for ALL farms dynamically can be very slow.
    # This section shows data for the SELECTED farm as an example.
    # A full ranking would require pre-calculation or a different architecture.
    st.header("مقایسه شاخص‌ها (مزرعه انتخاب شده)")
    try:
        # Calculate average values for the selected farm over the period
        mean_values = median_image.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=30 # Match chart scale
        ).getInfo() # GetInfo fetches the result

        if mean_values:
            # Prepare data for table display
            farm_summary_data = {
                "شاخص": list(mean_values.keys()),
                "مقدار میانگین (در دوره)": [f"{v:.3f}" if isinstance(v, (int, float)) else v for v in mean_values.values()]
            }
            df_summary = pd.DataFrame(farm_summary_data)
            st.dataframe(df_summary)
        else:
            st.warning("مقادیر میانگین برای مزرعه انتخاب شده قابل محاسبه نبود.")

    except ee.EEException as e:
        st.error(f"خطا در محاسبه مقادیر میانگین برای جدول: {e}")
    except Exception as e:
        st.error(f"خطای غیرمنتظره در بخش جدول مقایسه: {e}")

    # --- Download Map (Placeholder) ---
    # Note: Downloading the current map view from geemap/folium within Streamlit
    # can be complex. Offering download of the composite image might be more feasible.
    # st.header("دانلود نقشه")
    # st.info("قابلیت دانلود مستقیم نقشه در حال توسعه است.")
    # Add a button to download the mean values data as CSV
    try:
        if 'df_summary' in locals() and not df_summary.empty:
             csv_summary = df_summary.to_csv(index=False).encode('utf-8')
             st.download_button(
                 label="دانلود خلاصه شاخص‌ها (CSV)",
                 data=csv_summary,
                 file_name=f'summary_{selected_farm_name}_{selected_day}.csv',
                 mime='text/csv',
             )
    except NameError: # df_summary might not exist if calculation failed
         pass
    except Exception as e:
         st.error(f"خطا در ایجاد دکمه دانلود CSV: {e}")


# ==============================================================================
# Run the App
# ==============================================================================
if __name__ == "__main__":
    main()

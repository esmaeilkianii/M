import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import folium
import json
import os
from datetime import datetime, timedelta
import io
# from PIL import Image
# import urllib.request
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib.colors as mcolors

# ==============================================================================
# Configuration & Initial Setup
# ==============================================================================
st.set_page_config(layout="wide", page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا", page_icon="📊")

# --- Farsi UI Text ---
TEXT = {
    "title": "📊 داشبورد هوشمند مانیتورینگ هفتگی مزارع نیشکر دهخدا",
    "sidebar_header": "تنظیمات و فیلترها",
    "gee_status": "وضعیت اتصال به Google Earth Engine:",
    "gee_connected": "✅ متصل شد",
    "gee_error": "❌ خطا در اتصال",
    "csv_load_error": "خطا در بارگذاری فایل CSV مزارع",
    "select_day": "انتخاب روز هفته:",
    "select_farm": "انتخاب مزرعه:",
    "no_farm_selected": "لطفا یک مزرعه را انتخاب کنید.",
    "no_farms_for_day": "مزرعه‌ای برای این روز هفته یافت نشد.",
    "farm_info_header": "اطلاعات مزرعه انتخاب شده",
    "farm_name": "نام مزرعه",
    "channel": "کانال",
    "department": "اداره",
    "area": "مساحت داشت (هکتار)",
    "variety": "واریته",
    "age": "سن",
    "coordinates": "مختصات (Lat, Lon)",
    "data_status": "وضعیت داده‌ها",
    "coords_missing": "مختصات ناموجود",
    "coords_available": "مختصات موجود",
    "date_range_label": "انتخاب بازه زمانی:",
    "map_header": "نقشه تعاملی شاخص‌ها",
    "timeseries_header": "نمودار زمانی شاخص‌ها",
    "ranking_header": "جدول رتبه‌بندی مزارع (بر اساس NDVI)",
    "download_map_button": "دانلود نقشه فعلی (PNG)",
    "download_data_button": "دانلود جدول رتبه‌بندی (CSV)",
    "legend_title": "راهنمای رنگی (وضعیت سلامت)",
    "healthy": "سالم",
    "medium": "متوسط",
    "critical": "بحرانی",
    "calculating_indices": "در حال محاسبه شاخص‌ها...",
    "calculating_timeseries": "در حال محاسبه سری زمانی...",
    "calculating_ranking": "در حال محاسبه رتبه‌بندی...",
    "cloud_cover_warning": "توجه: ممکن است برخی تصاویر تحت تاثیر پوشش ابر باشند.",
    "layer_select": "انتخاب لایه شاخص:",
    "initial_zoom": 11,
    "initial_lat": 31.534442,
    "initial_lon": 48.724416,
    "required_columns": ['نام مزرعه', 'طول', 'عرض', 'کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن', 'روز هفته', 'coordinates_missing']
}

# --- File Paths ---
# Assume these files are in the root directory of the Hugging Face Space
CSV_PATH = "output (1).csv" # Needs to be uploaded to the HF Space
JSON_KEY_PATH = "ee-esmaeilkiani13877-cfdea6eaf411 (4).json" # Needs to be uploaded to the HF Space

# --- GEE & Map Settings ---
DEFAULT_START_DATE = datetime.now() - timedelta(days=90)
DEFAULT_END_DATE = datetime.now()
INITIAL_CENTER = [TEXT["initial_lat"], TEXT["initial_lon"]]
INITIAL_ZOOM = TEXT["initial_zoom"]
BUFFER_RADIUS_METERS = 100 # Buffer around point coordinates for zonal stats

# --- Index Definitions & Visualization ---
# Palettes go from Red (Low/Critical) -> Yellow (Medium) -> Green (High/Healthy)
INDEX_INFO = {
    'NDVI': {
        'formula': '(NIR - RED) / (NIR + RED)',
        'bands': ['B8', 'B4'], # Sentinel-2 specific
        'vis': {'min': 0.1, 'max': 0.9, 'palette': ['#CE1212', '#FCE700', '#008000']}, # Red, Yellow, Green
        'description': 'Normalized Difference Vegetation Index'
    },
    'EVI': {
        'formula': '2.5 * (NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1)',
        'bands': ['B8', 'B4', 'B2'], # Sentinel-2 specific
        'vis': {'min': 0.1, 'max': 0.8, 'palette': ['#CE1212', '#FCE700', '#008000']},
        'description': 'Enhanced Vegetation Index'
    },
    'NDMI': {
        'formula': '(NIR - SWIR1) / (NIR + SWIR1)',
        'bands': ['B8', 'B11'], # Sentinel-2 specific
        'vis': {'min': 0.0, 'max': 0.7, 'palette': ['#8B4513', '#FCE700', '#006400']}, # Brownish, Yellow, Dark Green (Water Stress)
        'description': 'Normalized Difference Moisture Index'
    },
     'LAI': {
        # Simple empirical relationship with NDVI (needs calibration!)
        # This is a placeholder - a proper LAI model is complex
        'formula': '3.618 * NDVI - 0.118', # Example, replace with a calibrated formula
        'depends_on': 'NDVI',
        'vis': {'min': 0, 'max': 6, 'palette': ['#FBF0B2', '#FFD700', '#008000']}, # Light Yellow to Green
        'description': 'Leaf Area Index (تخمینی)'
    },
     'Biomass': {
        # Simple empirical relationship with LAI (needs calibration!)
        # Placeholder: Biomass = a * LAI + b
        'formula': '2.5 * LAI + 0.5', # Example, replace with calibrated a and b
        'depends_on': 'LAI',
        'vis': {'min': 0, 'max': 15, 'palette': ['#FBF0B2', '#90EE90', '#006400']}, # Light yellow -> Light Green -> Dark Green
        'description': 'Biomass (تخمینی تن در هکتار)'
    },
    'MSI': {
        'formula': 'SWIR1 / NIR',
        'bands': ['B11', 'B8'], # Sentinel-2 specific
        'vis': {'min': 0.2, 'max': 1.0, 'palette': ['#006400', '#FCE700', '#8B0000']}, # Green(Low Stress) -> Yellow -> Dark Red (High Stress)
        'description': 'Moisture Stress Index'
    },
    # Add more indices here (ET, Chlorophyll) - Requires more complex models/collections
}

# ==============================================================================
# Utility Functions
# ==============================================================================

@st.cache_resource(show_spinner=TEXT['gee_status'])
def authenticate_gee(json_key_path):
    """Authenticates to GEE using a service account."""
    try:
        if not os.path.exists(json_key_path):
            st.error(f"فایل کلید سرویس اکانت یافت نشد: {json_key_path}")
            st.stop()

        with open(json_key_path) as f:
            key_info = json.load(f)

        credentials = ee.ServiceAccountCredentials(key_info['client_email'], json_key_path)
        ee.Initialize(credentials=credentials, project=key_info.get('project_id'))
        st.sidebar.success(TEXT['gee_connected'])
        # st.sidebar.caption(f"Project: {key_info.get('project_id')}")
        st.sidebar.caption(f"Service Account: {key_info['client_email']}")
        return True
    except Exception as e:
        st.sidebar.error(TEXT['gee_error'])
        st.sidebar.error(f"Details: {e}")
        st.error("امکان اتصال به Google Earth Engine وجود ندارد. لطفا تنظیمات سرویس اکانت را بررسی کنید.")
        st.stop() # Stop execution if GEE fails
        return False

@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(csv_path):
    """Loads farm data from CSV."""
    try:
        df = pd.read_csv(csv_path, encoding='utf-8') # Specify UTF-8 encoding
        # Basic validation
        if not all(col in df.columns for col in TEXT['required_columns']):
             missing = [col for col in TEXT['required_columns'] if col not in df.columns]
             st.error(f"{TEXT['csv_load_error']}: ستون‌های الزامی یافت نشدند: {', '.join(missing)}")
             st.stop()
        # Ensure coordinate columns are numeric, handle errors
        df['عرض'] = pd.to_numeric(df['عرض'], errors='coerce')
        df['طول'] = pd.to_numeric(df['طول'], errors='coerce')
        # Update coordinates_missing based on conversion success
        df['coordinates_missing'] = df['عرض'].isna() | df['طول'].isna() | (df['coordinates_missing'] == True) # Combine checks
        return df
    except FileNotFoundError:
        st.error(f"{TEXT['csv_load_error']}: فایل در مسیر '{csv_path}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"{TEXT['csv_load_error']}: {e}")
        st.stop()

def get_sentinel2_sr_cld_col(aoi, start_date, end_date):
    """Loads, filters, and masks Sentinel-2 Surface Reflectance data."""
    # Import and filter S2 SR.
    s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', 25))) # Pre-filter low cloud cover

    # Import and filter s2cloudless.
    s2_cloudless_col = (ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
        .filterBounds(aoi)
        .filterDate(start_date, end_date))

    # Join the two collections.
    s2_sr_cld_col = ee.Join.saveFirst('s2cloudless').apply(
        **{
            'primary': s2_sr_col,
            'secondary': s2_cloudless_col,
            'condition': ee.Filter.equals(
                **{'leftField': 'system:index', 'rightField': 'system:index'}
            ),
        }
    )

    # Function to mask clouds using the s2cloudless probability.
    def mask_s2_clouds(img):
        s2cloudless = ee.Image(img.get('s2cloudless')).select('probability')
        is_cloud = s2cloudless.gt(50) # Threshold for cloud probability
        # Apply mask, converting optical bands to float first if necessary
        return img.updateMask(is_cloud.Not()).select("B.*").toFloat()

    return ee.ImageCollection(s2_sr_cld_col).map(mask_s2_clouds)

def calculate_index(image, index_name):
    """Calculates a specific index on a GEE image."""
    info = INDEX_INFO[index_name]

    # Handle dependencies (like LAI depending on NDVI)
    if 'depends_on' in info:
        dependency_index = calculate_index(image, info['depends_on']).rename(info['depends_on'])
        image = image.addBands(dependency_index)

    # Prepare parameters for expression
    params = {}
    if 'bands' in info: # Indices like NDVI, EVI
        band_map = {'RED': 'B4', 'NIR': 'B8', 'BLUE': 'B2', 'SWIR1': 'B11', 'SWIR2': 'B12'} # Sentinel-2 Mapping
        for formula_band, gee_band in band_map.items():
             if formula_band in info['formula']:
                 params[formula_band] = image.select(gee_band).divide(10000) # Scale factor for S2 SR
    elif 'depends_on' in info: # Indices like LAI, Biomass
         params[info['depends_on']] = image.select(info['depends_on'])

    # Add NDVI explicitly if needed by a dependent index but not directly calculated
    if 'NDVI' in info['formula'] and 'NDVI' not in params:
        ndvi_img = calculate_index(image, 'NDVI').rename('NDVI')
        image = image.addBands(ndvi_img)
        params['NDVI'] = image.select('NDVI')

    # Calculate the index using expression
    try:
      index_image = image.expression(info['formula'], params).rename(index_name)
      return index_image
    except Exception as e:
        st.warning(f"Error calculating index '{index_name}': {e}. Check formula and bands.")
        # Return a dummy image or band to avoid breaking downstream processes
        return image.select(0).rename(index_name).multiply(0) # Return a zero image

# Function to generate legend HTML
def create_folium_legend(title, palette, min_val, max_val, labels):
    """Creates an HTML legend for Folium maps."""
    steps = len(palette)
    gradient = "linear-gradient(to right, " + ", ".join(palette) + ")"

    legend_html = f'''
     <div style="
         position: fixed;
         bottom: 50px;
         left: 50px;
         width: 200px; /* Adjusted width */
         height: auto; /* Auto height */
         z-index: 9999;
         border:2px solid grey;
         background-color:white;
         padding: 10px;
         font-size:14px;
         ">
     <b>{title}</b><br>
     <div style="display: flex; justify-content: space-between; margin-bottom: 5px; margin-top: 5px;">
         <span>{min_val:.1f} ({labels[0]})</span>
         <span>{max_val:.1f} ({labels[-1]})</span>
     </div>
     <div style="
         background: {gradient};
         height: 20px; /* Height of the color bar */
         width: 100%; /* Full width */
         border-radius: 5px;
         ">
     </div>
     </div>
     '''
    return legend_html

# ==============================================================================
# Main Application Logic
# ==============================================================================

# --- 1. Authentication and Data Loading ---
gee_authenticated = authenticate_gee(JSON_KEY_PATH)
df_farms_all = load_farm_data(CSV_PATH)

# --- 2. Sidebar Filters ---
st.sidebar.header(TEXT["sidebar_header"])

# Day of the week filter
available_days = sorted(df_farms_all['روز هفته'].unique())
selected_day = st.sidebar.selectbox(TEXT["select_day"], options=available_days, index=0)

# Filter farms based on selected day
df_farms_filtered = df_farms_all[df_farms_all['روز هفته'] == selected_day].copy()
# Reset index for easier lookup later if needed
df_farms_filtered.reset_index(drop=True, inplace=True)

# Farm selection dropdown
if not df_farms_filtered.empty:
    farm_names = [""] + sorted(df_farms_filtered['نام مزرعه'].unique()) # Add empty option
    selected_farm_name = st.sidebar.selectbox(
        TEXT["select_farm"],
        options=farm_names,
        index=0 # Default to empty selection
    )
    if selected_farm_name:
        selected_farm_info = df_farms_filtered[df_farms_filtered['نام مزرعه'] == selected_farm_name].iloc[0]
    else:
        selected_farm_info = None
else:
    st.sidebar.warning(TEXT["no_farms_for_day"])
    selected_farm_name = None
    selected_farm_info = None

# Date range selector
start_date, end_date = st.sidebar.date_input(
    TEXT["date_range_label"],
    value=(DEFAULT_START_DATE, DEFAULT_END_DATE),
    min_value=datetime(2015, 1, 1), # Approx start of Sentinel-2
    max_value=datetime.now()
)
start_date_str = start_date.strftime('%Y-%m-%d')
end_date_str = end_date.strftime('%Y-%m-%d')


# --- 3. Display Selected Farm Info ---
if selected_farm_info is not None:
    with st.sidebar.expander(TEXT["farm_info_header"], expanded=True):
        st.metric(label=TEXT["farm_name"], value=selected_farm_info['نام مزرعه'])
        col1, col2 = st.columns(2)
        with col1:
            st.metric(label=TEXT["channel"], value=selected_farm_info['کانال'])
            st.metric(label=TEXT["department"], value=selected_farm_info['اداره'])
            st.metric(label=TEXT["area"], value=f"{selected_farm_info['مساحت داشت']:.2f}")
        with col2:
            st.metric(label=TEXT["variety"], value=selected_farm_info['واریته'])
            st.metric(label=TEXT["age"], value=selected_farm_info['سن'])

        if selected_farm_info['coordinates_missing']:
            st.warning(f"{TEXT['data_status']}: {TEXT['coords_missing']}")
            st.caption(TEXT["coordinates"], help="مختصات برای این مزرعه در فایل ورودی موجود نیست.")
        else:
            st.success(f"{TEXT['data_status']}: {TEXT['coords_available']}")
            st.caption(f"{TEXT['coordinates']}: ({selected_farm_info['عرض']:.6f}, {selected_farm_info['طول']:.6f})")
else:
    st.sidebar.info(TEXT["no_farm_selected"])

# --- App Title ---
st.title(TEXT["title"])
st.markdown("---")

# --- 4. Map Display ---
st.header(TEXT["map_header"])
map_col, control_col = st.columns([4, 1]) # Allocate more space to map

with control_col:
     # Layer selector
     index_options = list(INDEX_INFO.keys())
     selected_index_name = st.selectbox(TEXT["layer_select"], index_options, index=0) # Default to NDVI


# Initialize map
m = geemap.Map(center=INITIAL_CENTER, zoom=INITIAL_ZOOM, add_google_map=False) # Start with OSM
m.add_basemap('SATELLITE') # Add Google Satellite basemap


if selected_farm_info is not None and not selected_farm_info['coordinates_missing']:
    lat = selected_farm_info['عرض']
    lon = selected_farm_info['طول']
    farm_point_geom = ee.Geometry.Point([lon, lat])
    farm_buffer_geom = farm_point_geom.buffer(BUFFER_RADIUS_METERS * 2) # Larger buffer for vis

    # Center map on selected farm
    m.set_center(lon, lat, 14) # Zoom in closer on selection

    # Add marker for selected farm
    popup_html = f"""
    <b>{TEXT['farm_name']}:</b> {selected_farm_info['نام مزرعه']}<br>
    <b>{TEXT['channel']}:</b> {selected_farm_info['کانال']}<br>
    <b>{TEXT['area']}:</b> {selected_farm_info['مساحت داشت']:.2f} ha<br>
    <b>{TEXT['variety']}:</b> {selected_farm_info['واریته']} ({selected_farm_info['سن']})<br>
    <b>Lat:</b> {lat:.5f}, <b>Lon:</b> {lon:.5f}
    """
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=250),
        tooltip=selected_farm_info['نام مزرعه'],
        icon=folium.Icon(color='blue', icon='info-sign')
    ).add_to(m)

    # Calculate and display selected index
    try:
        with st.spinner(f"{TEXT['calculating_indices']} ({selected_index_name})..."):
            # Get Sentinel-2 data
            s2_col = get_sentinel2_sr_cld_col(farm_buffer_geom, start_date_str, end_date_str)

            # Check if collection is empty
            if s2_col.size().getInfo() == 0:
                 st.warning(f"هیچ تصویر Sentinel-2 بدون ابر در بازه زمانی انتخاب شده برای این منطقه یافت نشد.")
            else:
                # Create a median composite for robustness
                median_image = s2_col.median().clip(farm_buffer_geom.bounds())

                # Calculate the selected index
                index_image = calculate_index(median_image, selected_index_name)

                # Add layer to map
                vis_params = INDEX_INFO[selected_index_name]['vis']
                m.addLayer(
                    index_image,
                    vis_params,
                    name=f"{selected_index_name} ({TEXT['healthy']}/{TEXT['medium']}/{TEXT['critical']})"
                )

                # Add Legend
                legend = create_folium_legend(
                    title=f"{selected_index_name} - {TEXT['legend_title']}",
                    palette=vis_params['palette'],
                    min_val=vis_params['min'],
                    max_val=vis_params['max'],
                    labels=[TEXT['critical'], TEXT['medium'], TEXT['healthy']] # Assuming palette order red->yellow->green
                )
                m.get_root().html.add_child(folium.Element(legend))

    except ee.EEException as e:
        st.error(f"خطا در پردازش GEE: {e}")
    except Exception as e:
        st.error(f"خطای غیرمنتظره در پردازش نقشه: {e}")
    finally:
        # Ensure map is always displayed, even if layers fail
        with map_col:
             m.to_streamlit(height=600)

else:
    # Display default map if no farm is selected or coords are missing
    with map_col:
        if selected_farm_name and selected_farm_info['coordinates_missing']:
             st.warning(f"مختصات برای مزرعه '{selected_farm_name}' موجود نیست. نقشه پیش‌فرض نمایش داده می‌شود.")
        st.info("یک مزرعه با مختصات معتبر از پنل کناری انتخاب کنید تا شاخص‌ها روی نقشه نمایش داده شوند.")
        m.to_streamlit(height=600)


# --- 5. Time Series Charts ---
st.markdown("---")
st.header(TEXT["timeseries_header"])
st.caption(TEXT["cloud_cover_warning"])

if selected_farm_info is not None and not selected_farm_info['coordinates_missing']:
    lat = selected_farm_info['عرض']
    lon = selected_farm_info['طول']
    farm_point_geom = ee.Geometry.Point([lon, lat])
    # Use a smaller buffer for zonal stats to represent the field area
    farm_stat_geom = farm_point_geom.buffer(BUFFER_RADIUS_METERS)

    try:
        with st.spinner(TEXT['calculating_timeseries']):
            # Get Sentinel-2 data for the time series
            s2_ts_col = get_sentinel2_sr_cld_col(farm_stat_geom, start_date_str, end_date_str)

            if s2_ts_col.size().getInfo() == 0:
                 st.warning(f"هیچ تصویر Sentinel-2 بدون ابر در بازه زمانی انتخاب شده برای محاسبه سری زمانی یافت نشد.")
            else:
                # Function to calculate indices and add time property
                def calc_indices_for_ts(image):
                    date = image.date().format('YYYY-MM-dd')
                    ndvi = calculate_index(image, 'NDVI').rename('NDVI')
                    evi = calculate_index(image, 'EVI').rename('EVI')
                    ndmi = calculate_index(image, 'NDMI').rename('NDMI')
                    # Add more indices if needed for charts

                    # Combine indices into one image with multiple bands
                    indices_image = ndvi.addBands(evi).addBands(ndmi)

                    # Calculate mean value within the farm geometry
                    stats = indices_image.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=farm_stat_geom,
                        scale=10, # Sentinel-2 resolution
                        maxPixels=1e9
                    )
                    # Return a feature with null geometry and properties
                    return ee.Feature(None, stats.set('date', date))

                # Map over the collection
                ts_data_fc = s2_ts_col.map(calc_indices_for_ts)

                # Filter out null results (can happen if image is fully masked over the geometry)
                ts_data_fc = ts_data_fc.filter(ee.Filter.notNull(INDEX_INFO.keys()))


                # Fetch data to client side - Use getInfo() - potentially slow for long series/many farms
                # For production, consider Export tasks or ee.batch.computeFeatures
                ts_data_list = ts_data_fc.getInfo()['features']


                if not ts_data_list:
                     st.warning("داده‌ای برای رسم نمودار سری زمانی پس از فیلترها یافت نشد.")
                else:
                    # Convert to Pandas DataFrame
                    data = []
                    for feature in ts_data_list:
                        props = feature['properties']
                        # Ensure date is present
                        if 'date' in props:
                             row = {'date': props['date']}
                             # Add index values if they exist in the properties
                             for idx in INDEX_INFO.keys():
                                 if idx in props and props[idx] is not None:
                                     row[idx] = props[idx]
                             data.append(row)


                    if not data:
                         st.warning("داده معتبری برای رسم نمودار سری زمانی یافت نشد.")
                    else:
                        df_ts = pd.DataFrame(data)
                        df_ts['date'] = pd.to_datetime(df_ts['date'])
                        df_ts = df_ts.sort_values('date').set_index('date')


                        # Plotting - Select only available indices
                        available_indices_for_plot = [col for col in ['NDVI', 'EVI', 'NDMI'] if col in df_ts.columns]

                        if not available_indices_for_plot:
                             st.warning("هیچ‌یک از شاخص‌های اصلی (NDVI, EVI, NDMI) برای رسم نمودار محاسبه نشد.")
                        else:
                             st.line_chart(df_ts[available_indices_for_plot])


    except ee.EEException as e:
        st.error(f"خطا در محاسبه سری زمانی GEE: {e}")
    except Exception as e:
        st.error(f"خطای غیرمنتظره در محاسبه سری زمانی: {e}")

else:
    st.info("یک مزرعه با مختصات معتبر انتخاب کنید تا نمودار زمانی شاخص‌ها نمایش داده شود.")


# --- 6. Ranking Table ---
st.markdown("---")
st.header(TEXT["ranking_header"])
st.caption(f"بر اساس میانگین NDVI در بازه زمانی {start_date_str} تا {end_date_str} برای مزارع '{selected_day}'")

# Filter farms for the selected day that have coordinates
df_farms_rank = df_farms_filtered[df_farms_filtered['coordinates_missing'] == False].copy()

if df_farms_rank.empty:
    st.warning(f"هیچ مزرعه‌ای با مختصات معتبر برای روز '{selected_day}' جهت رتبه‌بندی یافت نشد.")
else:
    try:
        with st.spinner(TEXT['calculating_ranking']):
            features = []
            for idx, row in df_farms_rank.iterrows():
                point = ee.Geometry.Point(row['طول'], row['عرض'])
                # Use a buffer for the area of interest for each farm
                feature = ee.Feature(point.buffer(BUFFER_RADIUS_METERS), {
                    'farm_name': row['نام مزرعه'],
                    'area': row['مساحت داشت'],
                    'variety': row['واریته']
                })
                features.append(feature)

            farm_fc = ee.FeatureCollection(features)

            # Get Sentinel-2 data covering all farms for the period
            aoi_all_farms = farm_fc.geometry().bounds()
            s2_col_rank = get_sentinel2_sr_cld_col(aoi_all_farms, start_date_str, end_date_str)

            if s2_col_rank.size().getInfo() == 0:
                st.warning(f"هیچ تصویر Sentinel-2 بدون ابر در بازه زمانی انتخاب شده برای رتبه‌بندی یافت نشد.")
            else:
                 # Create a median composite over the period
                median_image_rank = s2_col_rank.median()

                # Calculate NDVI on the composite
                ndvi_rank_image = calculate_index(median_image_rank, 'NDVI')

                # Reduce regions to get mean NDVI for each farm feature
                rank_results = ndvi_rank_image.reduceRegions(
                    collection=farm_fc,
                    reducer=ee.Reducer.mean(),
                    scale=10 # Sentinel-2 resolution
                )

                # Fetch results
                rank_data_list = rank_results.getInfo()['features']

                if not rank_data_list:
                     st.warning("نتیجه‌ای برای رتبه‌بندی مزارع یافت نشد.")
                else:
                    rank_data = []
                    for feature in rank_data_list:
                        props = feature['properties']
                        # Ensure 'mean' (NDVI value) exists
                        if 'mean' in props and props['mean'] is not None:
                            rank_data.append({
                                TEXT['farm_name']: props.get('farm_name', 'N/A'),
                                'NDVI': props['mean'],
                                TEXT['area']: props.get('area', 'N/A'),
                                TEXT['variety']: props.get('variety', 'N/A')
                            })

                    if not rank_data:
                        st.warning("داده معتبری برای رتبه‌بندی پس از محاسبه NDVI یافت نشد.")
                    else:
                        df_rank = pd.DataFrame(rank_data)
                        df_rank = df_rank.sort_values('NDVI', ascending=False).reset_index(drop=True)
                        df_rank['رتبه'] = df_rank.index + 1
                        # Reorder columns for display
                        df_rank = df_rank[['رتبه', TEXT['farm_name'], 'NDVI', TEXT['area'], TEXT['variety']]]

                        st.dataframe(df_rank.style.format({'NDVI': "{:.3f}", TEXT['area']: "{:.2f}"}))

                        # --- 7. Download Data ---
                        csv_buffer = io.StringIO()
                        df_rank.to_csv(csv_buffer, index=False, encoding='utf-8-sig') # Use utf-8-sig for Excel compatibility

                        st.download_button(
                            label=TEXT["download_data_button"],
                            data=csv_buffer.getvalue(),
                            file_name=f"dehkhoda_farm_ranking_{selected_day}_{start_date_str}_to_{end_date_str}.csv",
                            mime="text/csv",
                        )

    except ee.EEException as e:
        st.error(f"خطا در محاسبه رتبه‌بندی GEE: {e}")
    except Exception as e:
        st.error(f"خطای غیرمنتظره در محاسبه رتبه‌بندی: {e}")


# --- 8. Map Download Placeholder ---
# Note: Direct map PNG download with legend from geemap/folium in Streamlit is complex.
# This is a placeholder. A more robust solution might involve server-side rendering (e.g., using puppeteer)
# or using GEE's getThumbURL, but integrating the Folium markers/legend is tricky.
# st.markdown("---")
# st.header("دانلود نقشه")
# st.warning("قابلیت دانلود مستقیم نقشه با راهنما در حال حاضر پیاده‌سازی نشده است. می‌توانید از صفحه اسکرین‌شات بگیرید.")
# Add a disabled button or omit for now.
# st.download_button(TEXT["download_map_button"], data="", file_name="map.png", mime="image/png", disabled=True)


st.markdown("---")
st.caption("طراحی و توسعه توسط [نام شما/تیم شما]") # Add your credits here
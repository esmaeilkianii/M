import streamlit as st
import ee
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium
import json # Added to read the service account file
from google.oauth2 import service_account # ee.ServiceAccountCredentials handles this

# --- Configuration & GEE Initialization ---
st.set_page_config(layout="wide")
st.title("سامانه پایش و پشتیبانی تصمیم آبیاری نیشکر")
st.subheader("Sugarcane Irrigation Monitoring & Decision Support")

SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
GEE_PROJECT_ID = "ee-esmaeilkiani13877" # Extract from JSON or set manually
FEATURE_COLLECTION_ID = "projects/ee-esmaeilkiani13877/assets/Croplogging-Farm"

@st.cache_resource
def initialize_gee():
    """Initializes GEE with service account credentials."""
    try:
        # Read client_email from the service account file
        with open(SERVICE_ACCOUNT_FILE, 'r') as f:
            sa_info = json.load(f)
        client_email = sa_info.get('client_email')
        if not client_email:
            st.error("Client email not found in service account file.")
            st.stop()

        credentials = ee.ServiceAccountCredentials(client_email, SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, project=GEE_PROJECT_ID, opt_url='https://earthengine-highvolume.googleapis.com')
        st.success("GEE Authenticated Successfully!")
        return True
    except Exception as e:
        st.error(f"GEE Authentication Failed: {e}")
        st.stop()

if not initialize_gee():
    st.stop()

# --- Load Field Geometry and Attributes ---
@st.cache_data
def load_farm_data():
    """Loads farm data from GEE Feature Collection."""
    try:
        fc = ee.FeatureCollection(FEATURE_COLLECTION_ID)
        # Convert to Pandas DataFrame for easier manipulation in Streamlit
        # Need to get properties. This can be slow for large FCs.
        # For performance, it's often better to do this server-side or get only needed props.
        props = fc.aggregate_array('.all') # Gets all properties, might be slow

        # A more efficient way to get specific properties if fc.getInfo() is too large
        def get_fc_properties(feature):
            return ee.Feature(feature).toDictionary()
        
        fc_list = fc.toList(fc.size())
        
        data = []
        # We need to execute .getInfo() to bring data client-side for Streamlit
        # For very large feature collections, consider alternatives or pagination
        # For now, let's assume the number of farms is manageable
        
        # Efficiently get a list of dictionaries
        farm_features = fc.toList(fc.size()).map(lambda f: ee.Feature(f).toDictionary(['farm', 'group', 'Variety', 'Age', 'Area', 'calculated_area_ha', 'Field', 'Day', 'centroid_lon', 'centroid_lat']))
        farm_data_list = farm_features.getInfo() # This is the server call

        df = pd.DataFrame(farm_data_list)
        
        # Ensure required columns are present, fill with None if not
        required_cols = ['farm', 'group', 'Variety', 'Age', 'Area', 'calculated_area_ha', 'Field', 'Day', 'centroid_lon', 'centroid_lat']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None
        
        # Use 'calculated_area_ha' if 'Area' is missing or prefer 'calculated_area_ha'
        df['display_area'] = df['calculated_area_ha'].fillna(df['Area'])

        return df, fc # Return both DataFrame for UI and GEE FC for spatial operations
    except Exception as e:
        st.error(f"Error loading farm data: {e}")
        return pd.DataFrame(), None

farm_df, farm_fc_gee = load_farm_data()

if farm_df.empty or farm_fc_gee is None:
    st.warning("Farm data could not be loaded. Please check the Feature Collection ID and GEE permissions.")
    st.stop()

farm_names = sorted(farm_df['farm'].astype(str).unique().tolist())

# --- Sidebar for User Inputs ---
st.sidebar.header("⚙️ User Inputs")

selected_farm_name = st.sidebar.selectbox("Select Farm (انتخاب مزرعه):", farm_names)

# Auto-fill farm data
selected_farm_data = farm_df[farm_df['farm'] == selected_farm_name].iloc[0] if selected_farm_name else None

if selected_farm_data is not None:
    st.sidebar.subheader("Farm Details (مشخصات مزرعه)")
    st.sidebar.text(f"Group (گروه): {selected_farm_data.get('group', 'N/A')}")
    st.sidebar.text(f"Variety (واریته): {selected_farm_data.get('Variety', 'N/A')}")
    st.sidebar.text(f"Age (سن): {selected_farm_data.get('Age', 'N/A')} months")
    st.sidebar.text(f"Area (مساحت): {selected_farm_data.get('display_area', 0):.2f} ha")
    # Get the GEE geometry for the selected farm
    selected_farm_geometry_gee = farm_fc_gee.filter(ee.Filter.eq('farm', selected_farm_name)).first().geometry()
else:
    selected_farm_geometry_gee = None # Default to some full region or handle error

# Irrigation parameters
st.sidebar.subheader("Irrigation Parameters (پارامترهای آبیاری)")
Q = st.sidebar.number_input("Q: Irrigation flow rate (نرخ جریان آبیاری) (liters/second)", value=25.0, min_value=0.1, step=0.5)
t = st.sidebar.number_input("t: Irrigation time (زمان آبیاری) (hours)", value=12.0, min_value=0.1, step=0.5)
efficiency = st.sidebar.number_input("Efficiency (ضریب راندمان آبیاری)", value=1.05, min_value=0.1, max_value=2.0, step=0.01)
hydromodule = st.sidebar.number_input("Hydromodule (هیدرومدول) (m³/hour/ha)", value=3.6, min_value=0.1, step=0.1)
days_in_month = st.sidebar.number_input("Days in current month (تعداد روزهای ماه)", value=30, min_value=1, max_value=31, step=1)

# --- Irrigation Calculations ---
st.sidebar.subheader("Irrigation Calculations (محاسبات آبیاری)")
calculated_area_ha = selected_farm_data['display_area'] if selected_farm_data is not None else 0

if calculated_area_ha > 0:
    volume_per_hectare = (Q * t * 3.6) / calculated_area_ha
    interval_target = 1450 / (efficiency * 24 * hydromodule) if (efficiency * hydromodule) > 0 else 0
    rounds_target = days_in_month / interval_target if interval_target > 0 else 0
    area_month_target = 511.3 * rounds_target
    area_day_target = area_month_target / days_in_month if days_in_month > 0 else 0

    st.sidebar.metric("Volume per Hectare (حجم در هکتار)", f"{volume_per_hectare:.2f} m³/ha")
    st.sidebar.metric("Interval Target (تناوب هدف)", f"{interval_target:.2f} days")
    st.sidebar.metric("Rounds Target (دور هدف)", f"{rounds_target:.2f}")
    st.sidebar.metric("Area Month Target (سطح زیر کشت ماهانه هدف)", f"{area_month_target:.2f} ha")
    st.sidebar.metric("Area Day Target (سطح زیر کشت روزانه هدف)", f"{area_day_target:.2f} ha/day")
else:
    st.sidebar.warning("Select a farm with valid area to see calculations.")


# --- Main Panel: Map and Indices ---
col1, col2 = st.columns([3, 1]) # Map column, Output panel column

with col1:
    st.header("🗺️ Interactive Map & Indices")
    
    # Default map center (e.g., first farm's centroid or a general area)
    if selected_farm_data is not None and pd.notna(selected_farm_data.get('centroid_lon')) and pd.notna(selected_farm_data.get('centroid_lat')):
        map_center = [selected_farm_data['centroid_lat'], selected_farm_data['centroid_lon']]
        zoom_start = 13
    else: # Fallback if no farm selected or centroid missing
        map_center = [20, 0] # Default to a global view or a known region
        zoom_start = 2
        if not farm_df.empty and pd.notna(farm_df['centroid_lat'].iloc[0]) and pd.notna(farm_df['centroid_lon'].iloc[0]):
             map_center = [farm_df['centroid_lat'].iloc[0], farm_df['centroid_lon'].iloc[0]] # Center on first farm
             zoom_start = 10


    m = folium.Map(location=map_center, zoom_start=zoom_start, tiles="OpenStreetMap")

    # Add all farm boundaries for context (optional, can be slow)
    # To make it lighter, consider simplifying geometries or showing only nearby farms
    # For now, let's try adding all. If slow, this needs optimization.
    # farm_boundaries_geojson = farm_fc_gee.geometry().getInfo() # This gets ALL geometries combined
    # folium.GeoJson(farm_boundaries_geojson, name="All Farm Boundaries").add_to(m)

    if selected_farm_geometry_gee and selected_farm_data is not None:
        # Highlight selected farm
        try:
            selected_farm_geojson = selected_farm_geometry_gee.getInfo() # Get GeoJSON for the specific geometry
            folium.GeoJson(
                selected_farm_geojson,
                name=f"Selected Farm: {selected_farm_name}",
                style_function=lambda x: {'fillColor': 'yellow', 'color': 'orange', 'weight': 2.5, 'fillOpacity': 0.3}
            ).add_to(m)
            
            # Fit map to selected farm bounds
            bounds = selected_farm_geometry_gee.bounds().getInfo()['coordinates'][0]
            # bounds is like [[min_lon, min_lat], [max_lon, min_lat], [max_lon, max_lat], [min_lon, max_lat], [min_lon, min_lat]]
            # folium needs [[min_lat, min_lon], [max_lat, max_lon]]
            map_bounds = [[min(p[1] for p in bounds), min(p[0] for p in bounds)],
                          [max(p[1] for p in bounds), max(p[0] for p in bounds)]]
            m.fit_bounds(map_bounds)

        except Exception as e:
            st.error(f"Error adding selected farm geometry to map: {e}")
            # Fallback to centroid if bounds fail
            m.location = map_center
            m.zoom_start = zoom_start


    # --- Placeholder for GEE Indices ---
    st.subheader("🛰️ Remote Sensing Indices")
    index_options = ["NDVI", "NDWI", "LSWI", "NDMI"] # Add "Soil Moisture" later
    selected_indices_display = st.multiselect("Select Indices to Display on Map:", index_options, default=["NDVI"])

    # Date for indices
    from datetime import datetime, timedelta
    # Default to most recent data, e.g., last 30 days for Sentinel-2
    end_date = datetime.now()
    start_date_s2 = end_date - timedelta(days=30)
    start_date_modis = end_date - timedelta(days=8) # Modis has more frequent data

    def get_sentinel2_sr_collection(aoi, start_date, end_date):
        s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(aoi)
            .filterDate(ee.Date(start_date.strftime('%Y-%m-%d')), ee.Date(end_date.strftime('%Y-%m-%d')))
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))) # Basic cloud filter
        return s2_sr_col

    def calculate_ndvi(image):
        return image.normalizedDifference(['B8', 'B4']).rename('NDVI')

    def calculate_ndwi(image): # Using Green and NIR (McFeeters)
        return image.normalizedDifference(['B3', 'B8']).rename('NDWI')

    def calculate_lswi(image): # Using NIR and SWIR1
        return image.normalizedDifference(['B8', 'B11']).rename('LSWI') # B8A might be better (narrow NIR) but B8 is common

    def calculate_ndmi(image): # Normalized Difference Moisture Index (uses NIR and SWIR1)
        return image.normalizedDifference(['B8', 'B11']).rename('NDMI') # Same as LSWI for Sentinel-2

    # Visualization parameters
    ndvi_vis = {'min': -0.2, 'max': 0.9, 'palette': ['red', 'yellow', 'green']}
    water_vis = {'min': -0.5, 'max': 0.5, 'palette': ['brown', 'tan', 'lightblue', 'blue']}


    if selected_farm_geometry_gee and selected_farm_data is not None:
        s2_collection = get_sentinel2_sr_collection(selected_farm_geometry_gee, start_date_s2, end_date)
        latest_s2_image = s2_collection.mosaic().clip(selected_farm_geometry_gee) # Use mosaic of recent images

        if "NDVI" in selected_indices_display:
            ndvi_image = calculate_ndvi(latest_s2_image)
            try:
                map_id_dict = ndvi_image.getMapId(ndvi_vis)
                folium.TileLayer(
                    tiles=map_id_dict['tile_fetcher'].url_format,
                    attr='Google Earth Engine (NDVI)',
                    name='NDVI',
                    overlay=True,
                    control=True,
                    show=("NDVI" == selected_indices_display[0] if selected_indices_display else False) # Show first selected by default
                ).add_to(m)
            except Exception as e:
                st.warning(f"Could not display NDVI: {e}")

        if "NDWI" in selected_indices_display:
            ndwi_image = calculate_ndwi(latest_s2_image)
            try:
                map_id_dict = ndwi_image.getMapId(water_vis)
                folium.TileLayer(
                    tiles=map_id_dict['tile_fetcher'].url_format,
                    attr='Google Earth Engine (NDWI)',
                    name='NDWI',
                    overlay=True,
                    control=True,
                    show=("NDWI" == selected_indices_display[0] if selected_indices_display else False)
                ).add_to(m)
            except Exception as e:
                st.warning(f"Could not display NDWI: {e}")

        if "LSWI" in selected_indices_display:
            lswi_image = calculate_lswi(latest_s2_image) # Often similar to NDMI with S2 bands
            try:
                map_id_dict = lswi_image.getMapId(water_vis)
                folium.TileLayer(
                    tiles=map_id_dict['tile_fetcher'].url_format,
                    attr='Google Earth Engine (LSWI)',
                    name='LSWI',
                    overlay=True,
                    control=True,
                    show=("LSWI" == selected_indices_display[0] if selected_indices_display else False)
                ).add_to(m)
            except Exception as e:
                st.warning(f"Could not display LSWI: {e}")
        
        if "NDMI" in selected_indices_display: # Note: For S2, NDMI with B8 & B11 is same as LSWI used
            ndmi_image = calculate_ndmi(latest_s2_image)
            try:
                map_id_dict = ndmi_image.getMapId(water_vis)
                folium.TileLayer(
                    tiles=map_id_dict['tile_fetcher'].url_format,
                    attr='Google Earth Engine (NDMI)',
                    name='NDMI',
                    overlay=True,
                    control=True,
                    show=("NDMI" == selected_indices_display[0] if selected_indices_display else False)
                ).add_to(m)
            except Exception as e:
                st.warning(f"Could not display NDMI: {e}")
    
    folium.LayerControl().add_to(m)
    st_folium(m, width=None, height=600) # Use st_folium

with col2:
    st.header("📊 Output Panel (خروجی)")
    if selected_farm_data is not None:
        st.subheader("مشخصات مزرعه:")
        st.write(f"**نام مزرعه (Farm Name):** {selected_farm_data.get('farm', 'N/A')}")
        st.write(f"**سن (Age):** {selected_farm_data.get('Age', 'N/A')} ماه (months)")
        st.write(f"**واریته (Variety):** {selected_farm_data.get('Variety', 'N/A')}")
        st.write(f"**مساحت (Area):** {selected_farm_data.get('display_area', 0):.2f} هکتار (ha)")
        st.markdown("---")
        st.subheader("نتایج محاسبات آبیاری:")
        if calculated_area_ha > 0:
            st.write(f"**مقدار آب به ازای هر هکتار (Volume per Hectare):** {volume_per_hectare:.2f} m³/ha")
            st.write(f"**تناوب آبیاری (Irrigation Interval):** {interval_target:.2f} روز (days)")
            st.write(f"**مساحت قابل آبیاری ماهانه (Target Monthly Area):** {area_month_target:.2f} هکتار (ha)")
            st.write(f"**مساحت قابل آبیاری روزانه (Target Daily Area):** {area_day_target:.2f} هکتار/روز (ha/day)")
        else:
            st.warning("اطلاعات آبیاری برای نمایش در دسترس نیست (مساحت نامعتبر است).")
    else:
        st.info("یک مزرعه را از نوار کناری انتخاب کنید تا اطلاعات آن نمایش داده شود.")

# --- Time Series Charts ---
st.markdown("---")
st.header("📈 Time Series Charts (نمودارهای سری زمانی)")

@st.cache_data(ttl=3600) # Cache for 1 hour
def get_indices_time_series(farm_geometry, farm_name_for_cache_key):
    # farm_name_for_cache_key is to help streamlit differentiate cache if farm_geometry object changes subtly
    if farm_geometry is None:
        return pd.DataFrame()

    end_date = ee.Date(datetime.now())
    start_date = end_date.advance(-6, 'month') # Last 6 months

    def GEE_s2_proc(img):
        ndvi = calculate_ndvi(img).select('NDVI')
        ndwi = calculate_ndwi(img).select('NDWI')
        lswi = calculate_lswi(img).select('LSWI')
        # For S2, NDMI (B8, B11) is the same as LSWI. If different bands are intended, adjust.
        ndmi = calculate_ndmi(img).select('NDMI')
        return img.addBands([ndvi, ndwi, lswi, ndmi]) \
                  .set('system:time_start', img.get('system:time_start'))

    s2_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
              .filterBounds(farm_geometry)
              .filterDate(start_date, end_date)
              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)) # Looser cloud filter for time series
              .map(GEE_s2_proc))

    def create_time_series(image_collection, band_name):
        def reduce_region_function(image):
            median_val = image.reduceRegion(
                reducer=ee.Reducer.median(),
                geometry=farm_geometry,
                scale=20, # Scale for Sentinel-2 bands used in indices
                maxPixels=1e9,
                bestEffort=True # Use bestEffort for large geometries or complex reductions
            ).get(band_name)
            return ee.Feature(None, {'date': ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'), band_name: median_val})

        ts = image_collection.select(band_name).map(reduce_region_function).filter(ee.Filter.NotNull([band_name]))
        
        try:
            ts_info = ts.getInfo()['features']
            df_list = []
            for f in ts_info:
                props = f['properties']
                if props[band_name] is not None: # Ensure value is not None
                     df_list.append({'date': props['date'], band_name: props[band_name]})
            df = pd.DataFrame(df_list)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date').sort_index()
                # Resample to weekly median if enough data, otherwise just plot available
                # df = df.resample('W').median() # This might lead to many NaNs if data is sparse
            return df
        except Exception as e:
            st.warning(f"Could not generate time series for {band_name}: {e}")
            return pd.DataFrame(columns=['date', band_name]).set_index('date')


    if selected_farm_geometry_gee and selected_farm_data is not None:
        st.subheader(f"Indices for {selected_farm_name} (Last 6 Months)")
        
        chart_data_ndvi = get_indices_time_series(selected_farm_geometry_gee, f"{selected_farm_name}_NDVI")
        if not chart_data_ndvi.empty:
            st.line_chart(chart_data_ndvi['NDVI'], use_container_width=True)
            st.caption("NDVI Time Series (Median over farm, weekly resample if dense)")
        else:
            st.write(f"No NDVI data found for {selected_farm_name} in the last 6 months.")

        # Add other indices similarly
        index_to_chart = st.selectbox("Select index for time series chart:", index_options, index=0)

        if index_to_chart == "NDVI": # Already displayed above
            pass
        elif index_to_chart: # For NDWI, LSWI, NDMI
            chart_data_other = get_indices_time_series(selected_farm_geometry_gee, f"{selected_farm_name}_{index_to_chart}")
            if not chart_data_other.empty:
                st.line_chart(chart_data_other[index_to_chart], use_container_width=True)
                st.caption(f"{index_to_chart} Time Series (Median over farm)")
            else:
                st.write(f"No {index_to_chart} data found for {selected_farm_name} in the last 6 months.")
    else:
        st.info("Select a farm to view time series charts.")

st.sidebar.markdown("---")
st.sidebar.info("Developed with GEE & Streamlit.")

# --- Future improvements: ---
# 1. Soil Moisture (SMAP or ERA5-Land) - requires different collections and processing.
# 2. More robust cloud masking for Sentinel-2.
# 3. Option for user to select date range for indices on map.
# 4. Progress indicators for GEE computations.
# 5. Error handling for GEE calls (e.g., no image found).
# 6. Optimization for loading farm data if FeatureCollection is very large.
# 7. Better map layer control (e.g., radio buttons for exclusive display of one index at a time).
# 8. Allow drawing AOI if farm not in list.
# 9. Caching of GEE map tiles if possible or GEE results.
# 10. More sophisticated time series analysis (e.g. smoothing, trend lines).
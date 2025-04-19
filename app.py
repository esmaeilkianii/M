import streamlit as st
import pandas as pd
import ee
import geemap.foliumap as geemap
import plotly.express as px
import json
from datetime import datetime, timedelta
import io
import time  # برای شبیه‌سازی مارکر چشمک‌زن

# ==============================================================================
# تنظیمات صفحه Streamlit
# ==============================================================================
st.set_page_config(layout="wide", page_title="داشبورد مانیتورینگ مزارع نیشکر دهخدا", page_icon="🌾")

# ==============================================================================
# توابع کمکی و هسته GEE
# ==============================================================================

# --- احراز هویت Google Earth Engine ---
@st.cache_resource(show_spinner="در حال اتصال به Google Earth Engine...")
def authenticate_gee(service_account_file):
    """Authenticate and initialize Google Earth Engine using a service account."""
    try:
        # مسیر فایل کلید JSON را در نظر بگیرید
        # در محیط Hugging Face Spaces، فایل باید در ریشه پروژه باشد
        with open(service_account_file) as f:
            credentials_dict = json.load(f)
        credentials = ee.ServiceAccountCredentials(credentials_dict['client_email'], service_account_file)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        st.success("اتصال به Google Earth Engine با موفقیت انجام شد.", icon="✅")
        return True # نشان دهنده موفقیت
    except FileNotFoundError:
        st.error(f"خطا: فایل service_account.json در مسیر '{service_account_file}' یافت نشد. لطفاً فایل را در دایرکتوری پروژه قرار دهید.", icon="🚨")
        return False
    except Exception as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}", icon="🚨")
        # نمایش جزئیات بیشتر برای دیباگ
        st.exception(e)
        return False

# --- بارگذاری داده‌های مزارع ---
@st.cache_data(show_spinner="در حال بارگذاری داده‌های مزارع...")
def load_farm_data(uploaded_file):
    """Load farm data from the uploaded CSV file."""
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            # اطمینان از وجود ستون‌های ضروری
            required_columns = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته', 'coordinates_missing']
            if not all(col in df.columns for col in required_columns):
                st.error(f"خطا: فایل CSV باید شامل ستون‌های {', '.join(required_columns)} باشد.", icon="🚨")
                return None
            # تبدیل مختصات به عددی، مدیریت خطا
            df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
            df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
            # ایجاد یک شناسه منحصر به فرد برای هر مزرعه (مهم برای استخراج داده GEE)
            df['farm_id'] = df.index
            return df
        except Exception as e:
            st.error(f"خطا در خواندن یا پردازش فایل CSV: {e}", icon="🚨")
            return None
    else:
        st.info("لطفاً فایل CSV داده‌های مزارع را بارگذاری کنید.")
        return None

# --- توابع محاسبه شاخص‌های GEE ---
# (توابع برای Sentinel-2 SR به دلیل رزولوشن بهتر و باندهای مورد نیاز)

def add_indices_sentinel2(image):
    """Calculate and add multiple agricultural indices to a Sentinel-2 image."""
    # NDVI: (NIR - Red) / (NIR + Red) --- B8, B4
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    # NDMI (Normalized Difference Moisture Index): (NIR - SWIR1) / (NIR + SWIR1) --- B8, B11
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    # EVI (Enhanced Vegetation Index) - using coefficients for Sentinel-2
    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
            'NIR': image.select('B8').divide(10000), # Reflectance values
            'RED': image.select('B4').divide(10000),
            'BLUE': image.select('B2').divide(10000)
    }).rename('EVI')
    # MSI (Moisture Stress Index): SWIR1 / NIR --- B11, B8
    msi = image.select('B11').divide(image.select('B8')).rename('MSI')
    # LAI (Leaf Area Index) - Empirical relationship with NDVI (can be refined)
    # This is a simplified example; more complex models exist.
    lai = image.expression(
        '3.618 * exp(5.15 * NDVI - 0.118)', {'NDVI': ndvi}
    ).rename('LAI')
    # Chlorophyll Index (using Red Edge bands - B5, B6, B7 for Sentinel-2)
    # Example: CIre (Chlorophyll Index Red Edge) = (B7 / B5) - 1
    clre = image.expression('(B7 / B5) - 1', {
        'B7': image.select('B7'),
        'B5': image.select('B5')
    }).rename('Chlorophyll')

    # Biomass - Empirical relationship often with NDVI or SAVI (requires calibration)
    # Simplified example using NDVI
    biomass = ndvi.multiply(10).rename('Biomass') # Placeholder scaling, needs research/calibration

    # ET (Evapotranspiration) is complex, often requires meteorological data and models like SSEBop or METRIC.
    # A very rough proxy can be derived from temperature and NDVI, but it's not standard GEE practice without external data.
    # We'll skip ET for this example due to complexity.

    return image.addBands([ndvi, ndmi, evi, msi, lai, clre, biomass])

def mask_s2_clouds(image):
    """Mask clouds in Sentinel-2 SR images using the SCL band."""
    scl = image.select('SCL')
    # Keep clear (4), water (5 -> maybe keep?), vegetation (6), and non-vegetated (7) pixels.
    # Mask out clouds (8, 9, 10), cloud shadow (3), saturated/defective (1), dark area (2), snow (11).
    mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7))
    # QA60 band can also be used for cloud masking (less accurate than SCL but sometimes useful)
    # qa = image.select('QA60')
    # cloud_bit_mask = 1 << 10
    # cirrus_bit_mask = 1 << 11
    # mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(qa.bitwiseAnd(cirrus_bit_mask).eq(0))
    return image.updateMask(mask).divide(10000).copyProperties(image, ["system:time_start"])

@st.cache_data(ttl=3600, show_spinner="در حال پردازش تصاویر ماهواره‌ای و محاسبه شاخص‌ها...") # Cache for 1 hour
def get_weekly_mean_image(_aoi, start_date_str, end_date_str, index_name):
    """Get the mean image for a specific index over a week for a given AOI."""
    try:
        start_date = ee.Date(start_date_str)
        end_date = ee.Date(end_date_str)

        # Use Sentinel-2 Surface Reflectance data
        s2_sr_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                            .filterBounds(_aoi)
                            .filterDate(start_date, end_date)
                            .map(mask_s2_clouds)) # Apply cloud masking first

        # Calculate indices for the collection
        indices_collection = s2_sr_collection.map(add_indices_sentinel2)

        # Calculate the mean composite for the week
        mean_image = indices_collection.select(index_name).mean().clip(_aoi)

        # Apply a mask for visualization (e.g., mask out low NDVI values if index is NDVI)
        # if index_name == 'NDVI':
        #     mean_image = mean_image.updateMask(mean_image.gte(0.1)) # Mask pixels with NDVI < 0.1

        return mean_image # Returns an ee.Image
    except ee.EEException as e:
        st.error(f"خطای Google Earth Engine در محاسبه تصویر هفتگی: {e}", icon="🚨")
        return None
    except Exception as e:
        st.error(f"خطای غیرمنتظره در محاسبه تصویر هفتگی: {e}", icon="🚨")
        return None

@st.cache_data(ttl=3600, show_spinner="در حال استخراج داده‌های سری زمانی...")
def get_index_time_series(_geometry, start_date_str, end_date_str, index_name, frequency='week'):
    """Extract time series data for a specific index and geometry."""
    try:
        start_date = ee.Date(start_date_str)
        end_date = ee.Date(end_date_str)

        s2_sr_collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                            .filterBounds(_geometry)
                            .filterDate(start_date, end_date)
                            .map(mask_s2_clouds)
                            .map(add_indices_sentinel2))

        def get_mean_value(image):
            # Calculate the mean value of the index within the geometry
            # Use 'first' reducer if geometry is a point, 'mean' if it's a polygon
            reducer = ee.Reducer.mean()
            if isinstance(_geometry, ee.geometry.Point):
                 reducer = ee.Reducer.first() # Use 'first' for points to get exact pixel value

            stats = image.select(index_name).reduceRegion(
                reducer=reducer,
                geometry=_geometry,
                scale=10,  # Sentinel-2 scale
                maxPixels=1e9,
                bestEffort=True # Use bestEffort to avoid computation timeouts on larger geometries
            )
            # Return the value, add time information
            value = stats.get(index_name)
            return ee.Feature(None, {
                'date': image.date().format('YYYY-MM-dd'),
                index_name: value
            })

        # Map over the collection to get mean values for each image date
        ts_data = s2_sr_collection.map(get_mean_value).filter(ee.Filter.notNull([index_name]))

        # Convert to a Pandas DataFrame
        ts_list = ts_data.getInfo()['features']
        df_list = [{'date': f['properties']['date'], index_name: f['properties'][index_name]} for f in ts_list]

        if not df_list:
            return pd.DataFrame(columns=['date', index_name]) # Return empty if no data

        df = pd.DataFrame(df_list)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values(by='date').reset_index(drop=True)

        # Aggregate by week if requested
        if frequency == 'week':
             # Set date as index, resample weekly (starting Monday 'W-MON'), calculate mean, reset index
             df = df.set_index('date').resample('W-MON')[index_name].mean().reset_index()
             df['date'] = df['date'].dt.strftime('%Y-%W') # Format date as Year-WeekNumber

        return df

    except ee.EEException as e:
        st.error(f"خطای Google Earth Engine در استخراج سری زمانی: {e}", icon="🚨")
        return pd.DataFrame(columns=['date', index_name])
    except Exception as e:
        st.error(f"خطای غیرمنتظره در استخراج سری زمانی: {e}", icon="🚨")
        return pd.DataFrame(columns=['date', index_name])


@st.cache_data(ttl=3600, show_spinner="در حال محاسبه میانگین شاخص برای مزارع...")
def get_farm_mean_values(_farm_features, _index_image, index_name):
    """Calculate the mean index value for multiple farm geometries using reduceRegions."""
    if _index_image is None or not _farm_features.size().getInfo():
        st.warning("تصویر شاخص یا داده‌های مزرعه برای محاسبه میانگین در دسترس نیست.", icon="⚠️")
        return pd.DataFrame() # Return empty DataFrame

    try:
        # Use reduceRegions for efficiency
        farm_stats = _index_image.select(index_name).reduceRegions(
            collection=_farm_features,
            reducer=ee.Reducer.mean(),
            scale=10, # Sentinel-2 scale
            #crs='EPSG:4326' # Optional: Specify Coordinate Reference System if needed
        )

        # Extract data and convert to Pandas DataFrame
        stats_list = farm_stats.getInfo()['features']

        # Debug: Print raw stats list
        # print("Raw stats_list from reduceRegions:", stats_list)

        data = []
        for feature in stats_list:
            props = feature.get('properties', {})
            # Check if 'mean' is present and not None
            mean_value = props.get('mean')
            if mean_value is not None:
                 # Ensure 'farm_id' exists, otherwise fallback might be needed
                 farm_id = props.get('farm_id')
                 if farm_id is not None:
                    data.append({'farm_id': farm_id, f'{index_name}_mean': mean_value})
                 else:
                     # Fallback if 'farm_id' wasn't transferred correctly, maybe use another unique ID if available
                     st.warning(f"Farm ID missing for feature: {feature.get('id', 'N/A')}")
            # else: # Optional: Log features where mean calculation failed or returned null
            #     st.warning(f"Mean value calculation failed or returned null for farm_id: {props.get('farm_id', 'N/A')}")


        if not data:
            st.warning(f"داده‌ای برای شاخص '{index_name}' پس از پردازش reduceRegions یافت نشد.", icon="⚠️")
            return pd.DataFrame()

        return pd.DataFrame(data)

    except ee.EEException as e:
        st.error(f"خطای Google Earth Engine در reduceRegions: {e}", icon="🚨")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"خطای غیرمنتظره در محاسبه میانگین مزارع: {e}", icon="🚨")
        return pd.DataFrame()


# --- تعریف پالت رنگ و پارامترهای بصری ---
# Define color palettes for different indices
# Palettes should go from Red (bad) -> Yellow (medium) -> Green (good)
# NDVI/EVI/Biomass/Chlorophyll/LAI: Lower is worse
vis_params = {
    'NDVI': {'min': 0.1, 'max': 0.9, 'palette': ['red', 'yellow', 'green']},
    'EVI': {'min': 0.0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']},
    'LAI': {'min': 0, 'max': 6, 'palette': ['brown', 'yellow', 'green']},
    'Chlorophyll': {'min': 0, 'max': 5, 'palette': ['yellow', 'lightgreen', 'darkgreen']}, # Example, adjust range
    'Biomass': {'min': 0, 'max': 10, 'palette': ['brown', 'yellow', 'darkgreen']}, # Example, adjust range
    # NDMI/MSI: Higher NDMI is good (more moisture), Higher MSI is bad (more stress)
    'NDMI': {'min': -0.2, 'max': 0.6, 'palette': ['red', 'yellow', 'blue']}, # Blue for moisture
    'MSI': {'min': 0.5, 'max': 2.5, 'palette': ['green', 'yellow', 'red']}, # Higher MSI = more stress (Red)
    'ET': {'min': 0, 'max': 10, 'palette': ['brown', 'yellow', 'blue']} # Placeholder
}


# ==============================================================================
# رابط کاربری Streamlit
# ==============================================================================

st.title("🌾 داشبورد مانیتورینگ هفتگی مزارع نیشکر شرکت دهخدا")
st.markdown("مانیتورینگ وضعیت رشد و تنش مزارع با استفاده از تصاویر ماهواره‌ای و Google Earth Engine")

# --- ورودی‌ها ---
st.sidebar.header(" تنظیمات و ورودی‌ها ")

# 1. احراز هویت GEE
SERVICE_ACCOUNT_JSON = 'service_account.json' # نام فایل کلید در ریشه پروژه
gee_authenticated = authenticate_gee(SERVICE_ACCOUNT_JSON)

# 2. بارگذاری فایل CSV
uploaded_csv = st.sidebar.file_uploader("۱. بارگذاری فایل CSV مزارع", type=['csv'])
df_farms = None
if gee_authenticated and uploaded_csv:
    df_farms = load_farm_data(uploaded_csv)
elif not gee_authenticated:
    st.sidebar.warning("ابتدا باید اتصال به GEE برقرار شود.")

# --- ادامه فقط در صورت موفقیت‌آمیز بودن مراحل اولیه ---
if gee_authenticated and df_farms is not None:

    # 3. فیلتر روز هفته
    available_days = sorted(df_farms['روزهای هفته'].unique())
    selected_day = st.sidebar.selectbox("۲. انتخاب روز هفته برای نمایش مزارع:", options=available_days)

    # فیلتر کردن مزارع بر اساس روز انتخاب شده
    df_filtered_farms = df_farms[df_farms['روزهای هفته'] == selected_day].copy()
    # حذف مزارعی که مختصات ندارند یا پرچم coordinates_missing دارند
    df_display_farms = df_filtered_farms[
        (df_filtered_farms['طول جغرافیایی'].notna()) &
        (df_filtered_farms['عرض جغرافیایی'].notna()) &
        (df_filtered_farms['coordinates_missing'] != True) # فرض بر این است که ستون بولی یا قابل ارزیابی است
    ].copy()


    st.sidebar.info(f"تعداد مزارع یافت شده برای روز '{selected_day}': {len(df_filtered_farms)}")
    st.sidebar.info(f"تعداد مزارع معتبر برای نمایش روی نقشه: {len(df_display_farms)}")

    # 4. انتخاب شاخص کشاورزی
    available_indices = ['NDVI', 'NDMI', 'EVI', 'LAI', 'MSI', 'Biomass', 'Chlorophyll'] # ET حذف شد
    selected_index = st.sidebar.selectbox("۳. انتخاب شاخص کشاورزی برای نمایش:", options=available_indices, index=0) # NDVI پیش‌فرض

    # --- محاسبه تاریخ‌ها ---
    today = datetime.now()
    # today = datetime(2024, 4, 19) # برای تست با تاریخ ثابت
    end_date_last_week = today - timedelta(days=today.weekday() + 1) # آخرین یکشنبه
    start_date_last_week = end_date_last_week - timedelta(days=6) # دوشنبه هفته قبل
    end_date_prev_week = start_date_last_week - timedelta(days=1) # یکشنبه دو هفته قبل
    start_date_prev_week = end_date_prev_week - timedelta(days=6) # دوشنبه دو هفته قبل
    # برای سری زمانی (مثلا 6 ماه گذشته)
    start_date_timeseries = today - timedelta(days=180)

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**دوره زمانی هفتگی جاری:**")
    st.sidebar.markdown(f"شروع: `{start_date_last_week.strftime('%Y-%m-%d')}`")
    st.sidebar.markdown(f"پایان: `{end_date_last_week.strftime('%Y-%m-%d')}`")

    # --- محاسبه AOI کلی (بر اساس مزارع معتبر) ---
    # محاسبه Bounding Box مزارع نمایش داده شده
    if not df_display_farms.empty:
         min_lon, max_lon = df_display_farms['طول جغرافیایی'].min(), df_display_farms['طول جغرافیایی'].max()
         min_lat, max_lat = df_display_farms['عرض جغرافیایی'].min(), df_display_farms['عرض جغرافیایی'].max()
         # افزودن یک بافر کوچک
         buffer = 0.01
         _aoi_bounds = ee.Geometry.Rectangle([min_lon - buffer, min_lat - buffer, max_lon + buffer, max_lat + buffer])
         # مرکز نقشه را می‌توان روی میانگین مختصات تنظیم کرد
         center_lat = df_display_farms['عرض جغرافیایی'].mean()
         center_lon = df_display_farms['طول جغرافیایی'].mean()
         initial_zoom = 12 # زوم اولیه
    else:
         # استفاده از مختصات پیش‌فرض اگر مزرعه‌ای برای نمایش وجود نداشت
         center_lat = 31.534442
         center_lon = 48.724416
         initial_zoom = 11
         _aoi_bounds = ee.Geometry.Point([center_lon, center_lat]).buffer(5000) # یک بافر اطراف نقطه مرکزی
         st.warning("هیچ مزرعه معتبری برای نمایش در روز انتخاب شده یافت نشد. از مختصات پیش‌فرض استفاده می‌شود.", icon="⚠️")


    # --- محاسبه تصویر شاخص برای هفته اخیر ---
    last_week_image = get_weekly_mean_image(
        _aoi_bounds,
        start_date_last_week.strftime('%Y-%m-%d'),
        end_date_last_week.strftime('%Y-%m-%d'),
        selected_index
    )

    # --- نمایش نقشه تعاملی ---
    st.header(" نقشه وضعیت مزارع ")
    st.markdown(f"نمایش شاخص **{selected_index}** برای هفته منتهی به `{end_date_last_week.strftime('%Y-%m-%d')}`")

    m = geemap.Map(
        center=[center_lat, center_lon],
        zoom=initial_zoom,
        add_google_map=False # استفاده نکردن از نقشه پایه گوگل برای کنترل بهتر
    )
    m.add_basemap("SATELLITE") # اضافه کردن نقشه ماهواره‌ای

    # اضافه کردن لایه شاخص به نقشه
    map_legend_title = f"{selected_index} (میانگین هفتگی)"
    if last_week_image:
        try:
            current_vis_params = vis_params.get(selected_index, {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']})
            m.addLayer(
                last_week_image,
                current_vis_params,
                f'{selected_index} - Last Week Mean'
            )
            # اضافه کردن Legend (Colorbar)
            m.add_colorbar(current_vis_params, label=map_legend_title, layer_name=f'{selected_index} - Last Week Mean')
        except Exception as map_err:
             st.error(f"خطا در افزودن لایه GEE به نقشه: {map_err}", icon="🚨")
             # st.exception(map_err) # نمایش جزئیات خطا برای دیباگ
    else:
        st.warning(f"تصویر شاخص '{selected_index}' برای هفته اخیر محاسبه نشد یا خطایی رخ داده است.", icon="⚠️")

    # اضافه کردن مارکر برای مزارع فیلتر شده
    # شبیه سازی مارکر چشمک زن با نمایش/عدم نمایش موقت (ساده سازی شده)
    # توجه: این روش در geemap استاندارد نیست و ممکن است کند باشد یا خوب کار نکند.
    # روش بهتر استفاده از پلاگین‌های Folium یا JS سفارشی است.
    # ما از مارکرهای استاندارد با tooltip استفاده می‌کنیم.

    farm_points_list = []
    if not df_display_farms.empty:
        for idx, row in df_display_farms.iterrows():
            popup_html = f"""
            <b>مزرعه:</b> {row.get('مزرعه', 'N/A')}<br>
            <b>کانال:</b> {row.get('کانال', 'N/A')}<br>
            <b>اداره:</b> {row.get('اداره', 'N/A')}<br>
            <b>مساحت:</b> {row.get('مساحت داشت', 'N/A')} هکتار<br>
            <b>واریته:</b> {row.get('واریته', 'N/A')}<br>
            <b>سن:</b> {row.get('سن', 'N/A')}
            """
            # ایجاد نقطه هندسی GEE برای هر مزرعه
            point = ee.Geometry.Point(row['طول جغرافیایی'], row['عرض جغرافیایی'])
            # ایجاد Feature با مشخصات و شناسه منحصر به فرد
            feature = ee.Feature(point, {
                'name': row.get('مزرعه', f'Farm {idx}'),
                'popup': popup_html,
                'farm_id': row['farm_id'] # انتقال شناسه منحصر به فرد
                })
            farm_points_list.append(feature)

        # تبدیل لیست Feature ها به FeatureCollection
        farm_features = ee.FeatureCollection(farm_points_list)

        # افزودن FeatureCollection به نقشه به عنوان نقاط
        m.addLayer(farm_features, {'color': 'blue'}, f'مزارع روز {selected_day}') # آبی به عنوان رنگ پیش فرض مارکر

        # افزودن tooltip (وقتی روی نقطه هاور می‌کنید نمایش داده شود)
        # متاسفانه add_points_from_xy در geemap.foliumap برای این کار ساده‌تر نیست
        # و افزودن popup با addLayer به ee.FeatureCollection کمی پیچیده است.
        # از روش استاندارد Folium برای افزودن مارکرها استفاده می کنیم.
        # این باعث می شود کمی از GEE خالص دور شویم اما قابلیت های بهتری دارد.

        # پاک کردن لایه قبلی farm_features اگر لازم باشد
        # m.remove_layer(f'مزارع روز {selected_day}')

        import folium
        fg = folium.FeatureGroup(name=f"مزارع {selected_day}", show=True) # گروه لایه برای مدیریت بهتر

        for idx, row in df_display_farms.iterrows():
              popup_html = f"""
                <b>مزرعه:</b> {row.get('مزرعه', 'N/A')}<br>
                <b>کانال:</b> {row.get('کانال', 'N/A')}<br>
                <b>اداره:</b> {row.get('اداره', 'N/A')}<br>
                <b>مساحت:</b> {row.get('مساحت داشت', 'N/A')} هکتار<br>
                <b>واریته:</b> {row.get('واریته', 'N/A')}<br>
                <b>سن:</b> {row.get('سن', 'N/A')}
                """
              folium.Marker(
                    location=[row['عرض جغرافیایی'], row['طول جغرافیایی']],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip=f"مزرعه: {row.get('مزرعه', 'N/A')}",
                    icon=folium.Icon(color='blue', icon='info-sign') # آیکون استاندارد آبی
                ).add_to(fg)
        m.add_child(fg) # اضافه کردن گروه مارکرها به نقشه

        # # کد برای مارکر چشمک زن (اگر نیاز بود و کتابخانه پشتیبانی می‌کرد)
        # # from folium.plugins import MarkerCluster, BeautifyIcon
        # # نیاز به تحقیق بیشتر برای پیاده سازی چشمک زدن دارد.


    # نمایش نقشه در Streamlit
    # ممکن است نیاز به تنظیم ارتفاع باشد
    map_output = m.to_streamlit(height=500)

    # قابلیت دانلود نقشه به صورت PNG (نیاز به کتابخانه اضافی دارد مانند selenium یا playwright)
    # geemap به تنهایی قابلیت دانلود مستقیم PNG در Streamlit را ندارد.
    # راه حل جایگزین: نمایش یک تصویر ثابت و دکمه دانلود برای آن
    # یا راهنمایی کاربر برای استفاده از ابزار screenshot مرورگر
    st.markdown("*(برای ذخیره نقشه، از ابزار Screenshot مرورگر خود استفاده کنید)*")


    # --- نمودار سری زمانی ---
    st.header(f"📈 روند زمانی شاخص {selected_index}")
    st.markdown(f"نمایش میانگین هفتگی شاخص **{selected_index}** برای **کلیه مزارع فیلتر شده** در 6 ماه گذشته.")

    # محاسبه میانگین هندسه برای کلیه مزارع فیلتر شده (برای سادگی)
    # توجه: این یک میانگین مکانی است و ممکن است دقیق‌ترین نماینده نباشد اگر مزارع پراکندگی زیادی داشته باشند.
    # جایگزین: محاسبه سری زمانی برای هر مزرعه و سپس میانگین گرفتن (پیچیده‌تر و کندتر)
    if farm_features and farm_features.size().getInfo() > 0:
         # استفاده از centroid کلیه نقاط یا bounding box
         _combined_geometry = farm_features.geometry().centroid(maxError=1) # یا .geometry() برای bounding box
         # _combined_geometry = _aoi_bounds # یا استفاده از AOI کلی

         df_timeseries = get_index_time_series(
             _combined_geometry,
             start_date_timeseries.strftime('%Y-%m-%d'),
             today.strftime('%Y-%m-%d'),
             selected_index,
             frequency='week' # دریافت داده با فرکانس هفتگی
         )

         if not df_timeseries.empty:
             # اطمینان از اینکه ستون تاریخ و شاخص وجود دارند
             if 'date' in df_timeseries.columns and selected_index in df_timeseries.columns:
                  # ایجاد نمودار با Plotly
                  fig_ts = px.line(
                      df_timeseries,
                      x='date',
                      y=selected_index,
                      title=f'روند میانگین هفتگی {selected_index} (6 ماه اخیر)',
                      labels={'date': 'هفته (سال-شماره هفته)', selected_index: f'میانگین {selected_index}'},
                      markers=True # نمایش نقاط داده
                  )
                  fig_ts.update_layout(xaxis_title="تاریخ (هفته)", yaxis_title=f"مقدار {selected_index}")
                  st.plotly_chart(fig_ts, use_container_width=True)

                  # قابلیت دانلود داده‌های نمودار
                  csv_buffer = io.StringIO()
                  df_timeseries.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
                  st.download_button(
                       label="📥 دانلود داده‌های نمودار (CSV)",
                       data=csv_buffer.getvalue(),
                       file_name=f'timeseries_{selected_index}_{selected_day}.csv',
                       mime='text/csv',
                  )
             else:
                 st.warning(f"داده‌های سری زمانی برای شاخص '{selected_index}' دارای ستون‌های نامعتبر است.", icon="⚠️")
         else:
             st.warning(f"داده‌ای برای نمودار سری زمانی '{selected_index}' یافت نشد.", icon="⚠️")
    else:
         st.warning("هیچ مزرعه معتبری برای محاسبه سری زمانی یافت نشد.", icon="⚠️")


    # --- جدول رتبه‌بندی مزارع ---
    st.header("📊 جدول رتبه‌بندی مزارع")
    st.markdown(f"بر اساس میانگین شاخص **{selected_index}** در هفته منتهی به `{end_date_last_week.strftime('%Y-%m-%d')}`")

    if last_week_image and farm_features and farm_features.size().getInfo() > 0:
        df_farm_means = get_farm_mean_values(farm_features, last_week_image, selected_index)

        if not df_farm_means.empty and 'farm_id' in df_farm_means.columns and f'{selected_index}_mean' in df_farm_means.columns:
             # ادغام با داده‌های اصلی مزارع برای نمایش اطلاعات بیشتر
             df_ranking = pd.merge(df_display_farms, df_farm_means, on='farm_id', how='left')

             # حذف ردیف‌هایی که میانگین محاسبه نشده
             df_ranking = df_ranking.dropna(subset=[f'{selected_index}_mean'])

             # تعیین وضعیت رشد/تنش بر اساس شاخص
             # این بخش نیاز به تعریف دقیق آستانه‌ها دارد. مثال:
             # برای NDVI: > 0.6 خوب (سبز), 0.3 - 0.6 متوسط (زرد), < 0.3 تنش (قرمز)
             # برای MSI: < 1 خوب (سبز), 1 - 1.5 متوسط (زرد), > 1.5 تنش (قرمز)
             # تعیین جهت مرتب‌سازی (صعودی یا نزولی بهتر است؟)
             ascending_order = False # پیش‌فرض: مقادیر بالاتر بهتر است (NDVI, EVI, ...)
             status_col = f'{selected_index}_status'

             if selected_index in ['NDVI', 'EVI', 'LAI', 'Chlorophyll', 'Biomass', 'NDMI']:
                 ascending_order = False # بالاتر بهتر
                 threshold_good = vis_params[selected_index]['palette'].index('green') * (vis_params[selected_index]['max'] - vis_params[selected_index]['min']) / (len(vis_params[selected_index]['palette']) -1) + vis_params[selected_index]['min'] # تقریبی
                 threshold_stress = vis_params[selected_index]['palette'].index('red') * (vis_params[selected_index]['max'] - vis_params[selected_index]['min']) / (len(vis_params[selected_index]['palette']) -1) + vis_params[selected_index]['min'] # تقریبی
                 df_ranking[status_col] = df_ranking[f'{selected_index}_mean'].apply(lambda x: 'رشد خوب' if x >= threshold_good else ('تنش' if x <= threshold_stress else 'متوسط'))

             elif selected_index == 'MSI':
                 ascending_order = True # پایین‌تر بهتر
                 threshold_good = vis_params[selected_index]['palette'].index('green') * (vis_params[selected_index]['max'] - vis_params[selected_index]['min']) / (len(vis_params[selected_index]['palette']) -1) + vis_params[selected_index]['min'] # تقریبی
                 threshold_stress = vis_params[selected_index]['palette'].index('red') * (vis_params[selected_index]['max'] - vis_params[selected_index]['min']) / (len(vis_params[selected_index]['palette']) -1) + vis_params[selected_index]['min'] # تقریبی
                 df_ranking[status_col] = df_ranking[f'{selected_index}_mean'].apply(lambda x: 'وضعیت خوب' if x <= threshold_good else ('تنش رطوبتی' if x >= threshold_stress else 'متوسط'))


             # مرتب‌سازی جدول
             df_ranking = df_ranking.sort_values(by=f'{selected_index}_mean', ascending=ascending_order).reset_index(drop=True)
             df_ranking['رتبه'] = df_ranking.index + 1

             # انتخاب ستون‌های مورد نظر برای نمایش
             display_cols = ['رتبه', 'مزرعه', 'کانال', 'اداره', 'مساحت داشت', 'واریته', 'سن', f'{selected_index}_mean', status_col]
             df_display_ranking = df_ranking[display_cols]

             # تابع رنگ‌آمیزی ردیف‌ها
             def highlight_status(row):
                 status = row[status_col]
                 color = ''
                 if 'خوب' in status:
                     color = 'background-color: #c8e6c9' # Green light
                 elif 'تنش' in status:
                      color = 'background-color: #ffcdd2' # Red light
                 elif 'متوسط' in status:
                      color = 'background-color: #fff9c4' # Yellow light
                 return [color] * len(row)

             # نمایش جدول با رنگ‌بندی
             st.dataframe(df_display_ranking.style.apply(highlight_status, axis=1)
                          .format({f'{selected_index}_mean': "{:.3f}"}), # فرمت نمایش عدد شاخص
                           use_container_width=True)

             # قابلیت دانلود جدول
             csv_buffer_ranking = io.StringIO()
             # ذخیره DataFrame بدون استایل
             df_ranking.to_csv(csv_buffer_ranking, index=False, encoding='utf-8-sig')
             st.download_button(
                 label="📥 دانلود جدول رتبه‌بندی (CSV)",
                 data=csv_buffer_ranking.getvalue(),
                 file_name=f'ranking_{selected_index}_{selected_day}.csv',
                 mime='text/csv',
             )

        else:
            st.warning(f"محاسبه میانگین شاخص '{selected_index}' برای مزارع با خطا مواجه شد یا داده‌ای برنگشت.", icon="⚠️")
            # نمایش ستون های خالی df_ranking اگر فقط merge شده باشد
            if 'df_ranking' in locals() and not df_ranking.empty:
                 st.dataframe(df_display_farms[['مزرعه', 'کانال', 'اداره']]) # نمایش اطلاعات پایه
    else:
         st.warning(f"پیش‌نیازهای محاسبه رتبه‌بندی (تصویر شاخص یا مزارع معتبر) فراهم نیست.", icon="⚠️")


    # --- مقایسه هفته اخیر با هفته قبل ---
    st.header("🔍 مقایسه و تحلیل هفتگی")
    st.markdown(f"مقایسه میانگین شاخص **{selected_index}** برای **کلیه مزارع فیلتر شده** بین هفته اخیر و هفته قبل.")

    # محاسبه تصویر شاخص برای هفته قبل
    prev_week_image = get_weekly_mean_image(
        _aoi_bounds,
        start_date_prev_week.strftime('%Y-%m-%d'),
        end_date_prev_week.strftime('%Y-%m-%d'),
        selected_index
    )

    if last_week_image and prev_week_image and farm_features and farm_features.size().getInfo() > 0:
         # محاسبه میانگین کلی شاخص برای هفته اخیر و هفته قبل روی مزارع فیلتر شده
         last_week_mean_val = last_week_image.reduceRegion(
             reducer=ee.Reducer.mean(),
             geometry=farm_features.geometry(), # میانگین روی هندسه کلی مزارع
             scale=30, # مقیاس بزرگتر برای محاسبه سریعتر میانگین کلی
             maxPixels=1e9,
             bestEffort=True
         ).get(selected_index)

         prev_week_mean_val = prev_week_image.reduceRegion(
             reducer=ee.Reducer.mean(),
             geometry=farm_features.geometry(),
             scale=30,
             maxPixels=1e9,
             bestEffort=True
         ).get(selected_index)

         # دریافت مقادیر عددی
         try:
             last_mean = last_week_mean_val.getInfo()
             prev_mean = prev_week_mean_val.getInfo()

             if last_mean is not None and prev_mean is not None:
                 change = last_mean - prev_mean
                 change_percent = (change / prev_mean) * 100 if prev_mean != 0 else 0

                 # تحلیل به زبان فارسی
                 analysis_text = f"میانگین شاخص **{selected_index}** برای مزارع منتخب در هفته اخیر (`{last_mean:.3f}`) "
                 if change > 0.001: # آستانه تغییر مثبت
                     analysis_text += f"نسبت به هفته قبل (`{prev_mean:.3f}`) **افزایش** داشته است (تغییر: `{change:+.3f}`, حدود `{change_percent:+.1f}%`). "
                     if selected_index not in ['MSI']: # افزایش برای اکثر شاخص ها مثبت است
                         analysis_text += "این می‌تواند نشان‌دهنده **بهبود وضعیت رشد** یا پوشش گیاهی باشد."
                     else: # افزایش MSI منفی است
                         analysis_text += "این می‌تواند نشان‌دهنده **افزایش تنش رطوبتی** باشد."
                 elif change < -0.001: # آستانه تغییر منفی
                     analysis_text += f"نسبت به هفته قبل (`{prev_mean:.3f}`) **کاهش** داشته است (تغییر: `{change:.3f}`, حدود `{change_percent:.1f}%`). "
                     if selected_index not in ['MSI']: # کاهش برای اکثر شاخص ها منفی است
                         analysis_text += "این می‌تواند نشان‌دهنده **کاهش رشد** یا بروز تنش در مزارع باشد."
                     else: # کاهش MSI مثبت است
                         analysis_text += "این می‌تواند نشان‌دهنده **کاهش تنش رطوبتی** یا بهبود وضعیت آبیاری باشد."
                 else:
                      analysis_text += f"نسبت به هفته قبل (`{prev_mean:.3f}`) تقریباً **بدون تغییر** بوده است."

                 st.markdown(analysis_text)

                 # نمایش با Metric برای وضوح بیشتر
                 col1, col2, col3 = st.columns(3)
                 col1.metric(label=f"میانگین {selected_index} (هفته اخیر)", value=f"{last_mean:.3f}")
                 col2.metric(label=f"میانگین {selected_index} (هفته قبل)", value=f"{prev_mean:.3f}")
                 col3.metric(label="درصد تغییر هفتگی", value=f"{change_percent:.1f}%", delta=f"{change:.3f}")

             else:
                 st.warning("محاسبه میانگین شاخص برای یک یا هر دو هفته با خطا مواجه شد.", icon="⚠️")

         except ee.EEException as reduce_err:
              st.error(f"خطای GEE در محاسبه میانگین کلی برای مقایسه هفتگی: {reduce_err}", icon="🚨")
         except Exception as general_err:
              st.error(f"خطای نامشخص در مقایسه هفتگی: {general_err}", icon="🚨")

    else:
         st.warning("داده‌های کافی برای مقایسه هفتگی (تصاویر شاخص هر دو هفته یا مزارع معتبر) موجود نیست.", icon="⚠️")


    # --- نمایش اطلاعات دقیق مزرعه انتخاب شده (در صورت نیاز) ---
    # می‌توان یک منوی کشویی دیگر برای انتخاب یک مزرعه خاص و نمایش جزئیات آن اضافه کرد.
    # st.header("اطلاعات دقیق مزرعه")
    # selected_farm_name = st.selectbox("انتخاب مزرعه برای نمایش جزئیات:", options=df_display_farms['مزرعه'].tolist())
    # if selected_farm_name:
    #     farm_details = df_display_farms[df_display_farms['مزرعه'] == selected_farm_name].iloc[0]
    #     st.write(f"**نام مزرعه:** {farm_details['مزرعه']}")
    #     # ... نمایش سایر جزئیات ...


elif not gee_authenticated:
    st.error("اتصال به Google Earth Engine برقرار نشد. لطفاً از صحت فایل service_account.json و دسترسی‌های لازم اطمینان حاصل کنید.", icon="🚨")
elif gee_authenticated and uploaded_csv is None:
     st.info("لطفاً فایل CSV داده‌های مزارع را از طریق منوی کناری بارگذاری کنید.", icon="ℹ️")
elif gee_authenticated and df_farms is None: # اگر فایل بارگذاری شد اما خطا داشت
     st.error("فایل CSV بارگذاری شده معتبر نیست یا در پردازش آن خطایی رخ داده است. لطفاً فایل را بررسی کنید.", icon="🚨")

st.sidebar.markdown("---")
st.sidebar.markdown("طراحی و پیاده‌سازی: [نام شما/تیم شما]")
st.sidebar.markdown(f"تاریخ گزارش: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
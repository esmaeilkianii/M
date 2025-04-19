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
import requests
import traceback

# --- پیکربندی ---
APP_TITLE = "داشبورد مانیتورینگ مزارع نیشکر دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- مسیر فایل‌ها ---
CSV_FILE_PATH = 'output (1).csv'
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'

# --- توابع ---

def initialize_gee():
    """اتصال به Google Earth Engine."""
    try:
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.error("لطفاً فایل کلید JSON را در کنار فایل اصلی برنامه قرار دهید.")
            st.stop()
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE Initialized Successfully.")
        st.success("اتصال به Google Earth Engine با موفقیت برقرار شد.", icon="✅")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()
    return False

def load_data(csv_path):
    """بارگذاری و پردازش داده‌های مزارع."""
    try:
        # خواندن CSV، با فرض اینکه ستون اول ایندکس ناخواسته است
        # اگر فایل CSV واقعاً ستون اول بی‌نام را ندارد، index_col=None را استفاده کنید
        df = pd.read_csv(csv_path, index_col=0) # فرض بر ایندکس بودن ستون اول
        # اگر با index_col=0 خطا دارید یا ستون اول معنی دار است:
        # df = pd.read_csv(csv_path)

        if df.empty:
            st.error("فایل CSV خالی است یا به درستی خوانده نشد.")
            return None

        # 1. تمیز کردن نام ستون‌ها (حذف فواصل)
        original_columns = df.columns.tolist()
        df.columns = df.columns.str.strip()
        stripped_columns = df.columns.tolist()
        print(f"نام ستون‌های اصلی: {original_columns}")
        print(f"نام ستون‌های تصحیح شده: {stripped_columns}")

        # بررسی وجود ستون‌های کلیدی
        required_cols = ['مزرعه', 'طول جغرافیایی', 'عرض جغرافیایی', 'روزهای هفته']
        for col in required_cols:
            if col not in df.columns:
                st.error(f"ستون ضروری '{col}' پس از پاکسازی نام‌ها در فایل CSV یافت نشد. ستون‌های موجود: {df.columns.tolist()}")
                return None

        # 2. تبدیل مختصات به عدد
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')

        # 3. حذف ردیف‌های با مختصات نامعتبر (NaN یا (0,0))
        rows_before_filter = len(df)
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)
        # حذف صریح مختصات (0,0)
        df = df[~((df['طول جغرافیایی'] == 0.0) & (df['عرض جغرافیایی'] == 0.0))].copy() # استفاده از .copy() برای جلوگیری از SettingWithCopyWarning
        rows_after_filter = len(df)
        print(f"تعداد ردیف‌ها قبل از فیلتر مختصات: {rows_before_filter}, بعد: {rows_after_filter}")

        if df.empty:
            st.warning("پس از حذف مختصات نامعتبر یا (0,0)، هیچ ردیف معتبری باقی نماند.")
            return None

        # 4. مساحت
        if 'مساحت داشت' in df.columns:
            df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')
        else:
             st.warning("ستون 'مساحت داشت' یافت نشد.")
             df['مساحت داشت'] = pd.NA

        # 5. پردازش ستون‌های متنی (اطمینان از رشته بودن و هندلینگ مقادیر ناخواسته)
        string_columns = ['مزرعه', 'کانال', 'اداره', 'واریته', 'سن', 'روزهای هفته']
        print("\nپردازش ستون‌های رشته‌ای:")
        for col in string_columns:
            if col in df.columns:
                print(f"  پردازش ستون: {col}")
                # الف) تبدیل صریح به رشته
                df[col] = df[col].astype(str)
                # ب) جایگزینی مقادیر ناخواسته
                replace_map = {
                    'nan': 'نامشخص', 'NaN': 'نامشخص', 'None': 'نامشخص', 'none': 'نامشخص', '': 'نامشخص'
                }
                # برای روزهای هفته، '0' را هم نامشخص کن
                if col == 'روزهای هفته':
                     replace_map['0'] = 'نامشخص'
                df[col] = df[col].replace(replace_map)
                # ج) حذف فواصل اضافی
                df[col] = df[col].str.strip()
                 # د) اطمینان از اینکه مقادیر خالی باقی‌مانده هم 'نامشخص' شوند (مجدد)
                df[col] = df[col].replace('', 'نامشخص')

                if col == 'روزهای هفته':
                    print(f"    مقادیر یکتا در ستون '{col}' پس از پردازش: {df[col].unique().tolist()}")
            else:
                 st.warning(f"ستون مورد انتظار '{col}' یافت نشد.")
                 df[col] = 'نامشخص'

        print(f"\nداده با موفقیت بارگذاری و پردازش شد. تعداد ردیف‌های نهایی: {df.shape[0]}")
        # print("نمونه داده‌های نهایی:")
        # print(df.head())
        # print("\nاطلاعات نوع داده ستون‌ها:")
        # df.info(verbose=True, show_counts=True)

        return df

    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.error("لطفاً فایل CSV را در کنار فایل اصلی برنامه قرار دهید.")
        st.stop()
        return None
    except KeyError as e:
        st.error(f"خطای KeyError: ستون '{e}' یافت نشد یا پس از پاکسازی نام‌ها قابل دسترسی نیست.")
        st.error(f"ستون‌های خوانده شده اولیه: {original_columns if 'original_columns' in locals() else 'نامشخص'}")
        st.error(f"ستون‌های پس از پاکسازی: {stripped_columns if 'stripped_columns' in locals() else 'نامشخص'}")
        st.stop()
        return None
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام بارگذاری یا پردازش داده‌های CSV: {e}")
        st.error(traceback.format_exc())
        st.stop()
        return None

# --- توابع پردازش تصویر GEE ---
COMMON_BAND_NAMES_S2 = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']
COMMON_BAND_NAMES_L8L9 = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2']

def mask_s2_clouds(image):
    qa = image.select('QA60')
    mask = qa.bitwiseAnd(1 << 10).eq(0).And(qa.bitwiseAnd(1 << 11).eq(0))
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12']
    return image.select(data_bands).updateMask(mask).divide(10000.0).copyProperties(image, ["system:time_start"])

def mask_landsat_clouds(image):
    qa = image.select('QA_PIXEL')
    mask = qa.bitwiseAnd(1 << 3).eq(0).And(qa.bitwiseAnd(1 << 4).eq(0)).And(qa.bitwiseAnd(1 << 5).eq(0))
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7']
    scaled_bands = image.select(sr_bands).multiply(0.0000275).add(-0.2)
    return scaled_bands.updateMask(mask).copyProperties(image, ["system:time_start"])

# --- توابع محاسبه شاخص ---
def calculate_ndvi(image): return image.normalizedDifference(['NIR', 'Red']).rename('NDVI')
def calculate_evi(image):
    try: image.select('Blue'); return image.expression('2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {'NIR': image.select('NIR'),'RED': image.select('Red'),'BLUE': image.select('Blue')}).rename('EVI')
    except: return image.addBands(ee.Image(0).rename('EVI').updateMask(image.mask().reduce(ee.Reducer.first())))
def calculate_ndmi(image):
    try: image.select('SWIR1'); return image.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')
    except: return image.addBands(ee.Image(0).rename('NDMI').updateMask(image.mask().reduce(ee.Reducer.first())))
def calculate_msi(image):
    try: image.select('SWIR1'); return image.expression('SWIR1 / NIR', {'SWIR1': image.select('SWIR1'), 'NIR': image.select('NIR')}).rename('MSI')
    except: return image.addBands(ee.Image(0).rename('MSI').updateMask(image.mask().reduce(ee.Reducer.first())))
def calculate_lai_simple(image):
    lai = None
    try:
        if 'Blue' in image.bandNames().getInfo(): lai = calculate_evi(image).select('EVI').multiply(3.5).add(0.1)
        else: raise ee.EEException("Blue band not available for EVI-based LAI.")
    except:
        try: lai = calculate_ndvi(image).select('NDVI').multiply(5.0).add(0.1)
        except Exception as ndvi_e: print(f"خطا NDVI LAI: {ndvi_e}"); pass
    return lai.clamp(0, 8).rename('LAI') if lai else image.addBands(ee.Image(0).rename('LAI').updateMask(image.mask().reduce(ee.Reducer.first())))
def calculate_biomass_simple(image):
    try: lai = calculate_lai_simple(image).select('LAI'); biomass = lai.multiply(1.5).add(0.2); return biomass.clamp(0, 50).rename('Biomass')
    except Exception as e: print(f"خطا بیومس: {e}"); return image.addBands(ee.Image(0).rename('Biomass').updateMask(image.mask().reduce(ee.Reducer.first())))
def calculate_chlorophyll_mcari(image):
    try: image.select('RedEdge1'); image.select('Red'); image.select('Green'); return image.expression('((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)', {'RE1': image.select('RedEdge1'), 'RED': image.select('Red'), 'GREEN': image.select('Green')}).rename('Chlorophyll')
    except:
        try: return calculate_ndvi(image).rename('Chlorophyll')
        except: return image.addBands(ee.Image(0).rename('Chlorophyll').updateMask(image.mask().reduce(ee.Reducer.first())))
def calculate_et_placeholder(image):
    try: return calculate_ndmi(image).rename('ET_proxy')
    except: return image.addBands(ee.Image(0).rename('ET_proxy').updateMask(image.mask().reduce(ee.Reducer.first())))

INDEX_FUNCTIONS = {
    'NDVI': {'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'EVI': {'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['#FEE8C8', '#FDBB84', '#E34A33', '#A50F15', '#4C061D']}, 'requires_blue': True},
    'NDMI': {'func': calculate_ndmi, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}, 'requires_swir1': True},
    'MSI': {'func': calculate_msi, 'vis': {'min': 0.5, 'max': 3.0, 'palette': ['#006837', '#A6D96A', '#FFFFBF', '#FDAE61', '#D73027']}, 'requires_swir1': True},
    'LAI': {'func': calculate_lai_simple, 'vis': {'min': 0, 'max': 8, 'palette': ['#FEF0D9', '#FDCC8A', '#FC8D59', '#E34A33', '#B30000']}, 'requires_blue_optional': True},
    'Biomass': {'func': calculate_biomass_simple, 'vis': {'min': 0, 'max': 30, 'palette': ['#FFFFD4', '#FED98E', '#FE9929', '#D95F0E', '#993404']}, 'requires_blue_optional': True},
    'Chlorophyll': {'func': calculate_chlorophyll_mcari, 'vis': {'min': 0, 'max': 1.2, 'palette': ['#FFFFE5', '#F7FCB9', '#D9F0A3', '#ADDD8E', '#78C679', '#41AB5D', '#238443', '#005A32']}, 'requires_rededge': True},
    'ET_proxy': {'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}, 'requires_swir1': True}
}

# --- دریافت داده GEE ---
def get_image_collection(start_date, end_date, geometry, sensor='Sentinel-2'):
    start_date_str = start_date.strftime('%Y-%m-%d'); end_date_str = end_date.strftime('%Y-%m-%d')
    collection = None; mask_func = None; bands_to_select_orig = None; bands_to_rename_to = None
    try:
        if sensor == 'Sentinel-2':
            collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            mask_func = mask_s2_clouds
            bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
            bands_to_rename_to = COMMON_BAND_NAMES_S2
        elif sensor == 'Landsat':
            l9 = ee.ImageCollection('LANDSAT/LC09/C02/T1_L2'); l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')
            collection = l9.merge(l8)
            mask_func = mask_landsat_clouds
            bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
            bands_to_rename_to = COMMON_BAND_NAMES_L8L9
        else: st.error(f"سنسور '{sensor}' پشتیبانی نمی‌شود."); return None

        collection = collection.filterDate(start_date_str, end_date_str)
        if geometry: collection = collection.filterBounds(geometry)
        if collection.size().getInfo() == 0: return None
        processed_collection = collection.map(lambda image: mask_func(image.select(bands_to_select_orig)).rename(bands_to_rename_to).copyProperties(image, ["system:time_start"]))
        if processed_collection.size().getInfo() == 0: return None
        return processed_collection
    except ee.EEException as e: st.error(f"خطای GEE در get_image_collection: {e}"); return None
    except Exception as e: st.error(f"خطای غیرمنتظره در get_image_collection: {e}"); return None

# --- توابع تحلیل GEE (با کش) ---
@st.cache_data(ttl=3600)
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    try: farm_geom = ee.Geometry(json.loads(_farm_geom_geojson)) if _farm_geom_geojson else None
    except: farm_geom = None
    if not farm_geom: st.error("هندسه مزرعه برای سری زمانی نامعتبر است."); return pd.DataFrame(columns=['Date', index_name])

    collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if collection is None or collection.size().getInfo() == 0: return pd.DataFrame(columns=['Date', index_name])

    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail: st.error(f"تابع شاخص {index_name} یافت نشد."); return pd.DataFrame(columns=['Date', index_name])

    bands_ok_for_index = True
    try:
        first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
        if index_func_detail.get('requires_blue') and 'Blue' not in first_image_bands: bands_ok_for_index = False
        if index_func_detail.get('requires_swir1') and 'SWIR1' not in first_image_bands: bands_ok_for_index = False
        # RedEdge چک نمی‌شود چون تابع خودش هندل می‌کند
    except: bands_ok_for_index = False

    if not bands_ok_for_index: st.warning(f"سری زمانی {index_name} با {sensor} ممکن نیست.", icon="⚠️"); return pd.DataFrame(columns=['Date', index_name])

    def calculate_single_index(image):
        try:
            calc_img = index_func_detail['func'](image)
            if selected_index in calc_img.bandNames().getInfo(): return calc_img.select(index_name).copyProperties(image, ["system:time_start"])
            else: return ee.Image().rename(index_name).updateMask(ee.Image(0)).set('system:time_start', image.get('system:time_start'))
        except: return ee.Image().set('system:time_start', image.get('system:time_start'))
    indexed_collection = collection.map(calculate_single_index)

    def extract_value(image):
        image_with_band = ee.Algorithms.If(image.bandNames().contains(index_name),image,ee.Image().set('system:time_start', image.get('system:time_start')))
        image = ee.Image(image_with_band)
        val = ee.Algorithms.If(image.bandNames().contains(index_name),image.select(index_name).reduceRegion(reducer=ee.Reducer.mean(),geometry=farm_geom,scale=30,maxPixels=1e9,tileScale=4).get(index_name),-9999)
        return ee.Feature(None, {'time': image.get('system:time_start'), index_name: ee.Algorithms.If(val, val, -9999)})

    try: ts_info = indexed_collection.map(extract_value).getInfo()
    except ee.EEException as e:
        print(f"خطای reduceRegion سری زمانی، تلاش مجدد: {e}")
        try:
            def extract_value_large_tile(image):
                 image_with_band = ee.Algorithms.If(image.bandNames().contains(index_name),image,ee.Image().set('system:time_start', image.get('system:time_start')))
                 image = ee.Image(image_with_band)
                 val = ee.Algorithms.If(image.bandNames().contains(index_name),image.select(index_name).reduceRegion(reducer=ee.Reducer.mean(), geometry=farm_geom, scale=30, maxPixels=1e9, tileScale=8).get(index_name),-9999)
                 return ee.Feature(None, {'time': image.get('system:time_start'), index_name: ee.Algorithms.If(val, val, -9999)})
            ts_info = indexed_collection.map(extract_value_large_tile).getInfo()
        except ee.EEException as e2: st.error(f"تلاش مجدد سری زمانی ناموفق: {e2}"); return pd.DataFrame(columns=['Date', index_name])

    data = []
    for feature in ts_info['features']:
        props = feature.get('properties', {})
        value = props.get(index_name); time_ms = props.get('time')
        if value is not None and value != -9999 and time_ms is not None:
            try: dt = datetime.datetime.fromtimestamp(time_ms / 1000.0).date(); data.append([dt, value])
            except: pass
    if not data: return pd.DataFrame(columns=['Date', index_name])
    ts_df = pd.DataFrame(data, columns=['Date', index_name])
    ts_df['Date'] = pd.to_datetime(ts_df['Date'])
    ts_df = ts_df.groupby('Date')[index_name].mean().reset_index()
    return ts_df.sort_values(by='Date')

@st.cache_data(ttl=3600)
def get_latest_index_for_ranking(_farms_df_json, selected_day_filter, start_date, end_date, index_name, sensor):
    try: farms_df = pd.read_json(_farms_df_json)
    except: st.error("خطا خواندن دیتافریم رتبه‌بندی."); return pd.DataFrame(columns=['مزرعه', index_name])

    if selected_day_filter != "همه روزها":
        if 'روزهای هفته' in farms_df.columns: farms_df_filtered = farms_df[farms_df['روزهای هفته'] == selected_day_filter].copy()
        else: farms_df_filtered = farms_df
    else: farms_df_filtered = farms_df.copy()
    if farms_df_filtered.empty: return pd.DataFrame(columns=['مزرعه', index_name])

    features = []; valid_farm_ids = []
    for idx, row in farms_df_filtered.iterrows():
        try:
             if pd.notna(row['طول جغرافیایی']) and pd.notna(row['عرض جغرافیایی']) and not (row['طول جغرافیایی'] == 0.0 and row['عرض جغرافیایی'] == 0.0):
                 geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
                 buffered_geom = geom.buffer(50)
                 feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
                 features.append(feature)
                 valid_farm_ids.append(row['مزرعه'])
        except Exception as e: print(f"خطا در ایجاد هندسه رتبه‌بندی برای {row.get('مزرعه', 'NA')}: {e}")
    if not features: return pd.DataFrame(columns=['مزرعه', index_name])

    farm_fc = ee.FeatureCollection(features)
    try: bounds = farm_fc.geometry().bounds()
    except ee.EEException as bound_e: st.error(f"خطای GEE در محدوده رتبه‌بندی: {bound_e}"); return pd.DataFrame(columns=['مزرعه', index_name])

    collection = get_image_collection(start_date, end_date, bounds, sensor)
    if collection is None or collection.size().getInfo() == 0: return pd.DataFrame(columns=['مزرعه', index_name])

    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail: st.error(f"تابع شاخص {index_name} یافت نشد."); return pd.DataFrame(columns=['مزرعه', index_name])
    bands_ok_for_index = True
    try:
        first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
        if index_func_detail.get('requires_blue') and 'Blue' not in first_image_bands: bands_ok_for_index = False
        if index_func_detail.get('requires_swir1') and 'SWIR1' not in first_image_bands: bands_ok_for_index = False
    except: bands_ok_for_index = False
    if not bands_ok_for_index: st.warning(f"رتبه‌بندی {index_name} با {sensor} ممکن نیست.", icon="⚠️"); return pd.DataFrame(columns=['مزرعه', index_name])

    def calculate_single_index_rank(image):
        try:
            calc_img = index_func_detail['func'](image)
            if selected_index in calc_img.bandNames().getInfo(): return calc_img.select(selected_index).copyProperties(image, ["system:time_start"])
            else: return ee.Image().rename(selected_index).updateMask(ee.Image(0)).set('system:time_start', image.get('system:time_start'))
        except: return ee.Image().set('system:time_start', image.get('system:time_start'))
    indexed_collection = collection.map(calculate_single_index_rank)

    try:
        median_image = indexed_collection.select(index_name).median()
        if index_name not in median_image.bandNames().getInfo(): st.warning(f"باند '{index_name}' در تصویر میانه رتبه‌بندی یافت نشد.", icon="⚠️"); return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as e: st.error(f"خطا در تصویر میانه رتبه‌بندی: {e}"); return pd.DataFrame(columns=['مزرعه', index_name])

    try: farm_values = median_image.reduceRegions(collection=farm_fc, reducer=ee.Reducer.mean(), scale=30, tileScale=4).getInfo()
    except ee.EEException as e:
        print(f"خطای reduceRegions رتبه‌بندی، تلاش مجدد: {e}")
        try: farm_values = median_image.reduceRegions(collection=farm_fc, reducer=ee.Reducer.mean(), scale=30, tileScale=8).getInfo()
        except ee.EEException as e2: st.error(f"تلاش مجدد رتبه‌بندی ناموفق: {e2}"); return pd.DataFrame(columns=['مزرعه', index_name])

    ranking_data = {}; farm_values_features = farm_values.get('features', [])
    for feature in farm_values_features:
        props = feature.get('properties', {})
        farm_id = props.get('farm_id'); value = props.get('mean')
        if farm_id is not None and value is not None and farm_id in valid_farm_ids: ranking_data[farm_id] = value
    for farm_id in valid_farm_ids:
        if farm_id not in ranking_data: ranking_data[farm_id] = None
    if not ranking_data: return pd.DataFrame(columns=['مزرعه', index_name])

    ranking_df = pd.DataFrame(list(ranking_data.items()), columns=['مزرعه', index_name])
    ascending_sort = True if index_name in ['MSI'] else False
    ranking_df = ranking_df.sort_values(by=index_name, ascending=ascending_sort, na_position='last')
    ranking_df['رتبه'] = ranking_df[index_name].rank(method='first', ascending=ascending_sort).astype('Int64')
    return ranking_df[['رتبه', 'مزرعه', index_name]]


# --- اجرای برنامه Streamlit ---
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# ۱. اتصال به GEE
gee_initialized = initialize_gee()

if gee_initialized:
    # ۲. بارگذاری داده‌های CSV
    df = load_data(CSV_FILE_PATH)

    if df is None or df.empty:
        st.error("بارگذاری داده‌های مزارع ناموفق بود یا هیچ داده معتبری یافت نشد.")
        st.stop()

    # --- نوار کناری (Sidebar) ---
    st.sidebar.header("تنظیمات نمایش")

    # انتخابگر بازه زمانی
    today = datetime.date.today(); default_end_date = today
    default_start_date = default_end_date - datetime.timedelta(days=7)
    start_date = st.sidebar.date_input("تاریخ شروع", value=default_start_date, max_value=default_end_date)
    end_date = st.sidebar.date_input("تاریخ پایان", value=default_end_date, min_value=start_date, max_value=default_end_date)
    if start_date > end_date: st.sidebar.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد."); st.stop()

    # فیلتر بر اساس روز هفته
    # استفاده از مقادیر ستون 'روزهای هفته' که توسط load_data پردازش شده
    unique_weekdays = df['روزهای هفته'].unique()
    filtered_weekdays = sorted([day for day in unique_weekdays if day != 'نامشخص'])
    available_days = ["همه روزها"] + filtered_weekdays
    if not filtered_weekdays and 'نامشخص' in unique_weekdays: # اگر فقط 'نامشخص' یا هیچ روزی نبود
        available_days = ["همه روزها"] + (['نامشخص'] if 'نامشخص' in unique_weekdays else [])
    elif not filtered_weekdays: # اگر هیچ مقداری در روز هفته نبود
         available_days = ["همه روزها"]

    selected_day = st.sidebar.selectbox("فیلتر بر اساس روز هفته", options=available_days, help="این فیلتر روی لیست مزارع قابل انتخاب و جدول رتبه‌بندی تاثیر می‌گذارد.")

    # فیلتر کردن دیتافریم اصلی بر اساس روز هفته انتخابی
    if selected_day == "همه روزها":
        filtered_df_day = df.copy()
    else:
        filtered_df_day = df[df['روزهای هفته'] == selected_day].copy()

    # انتخاب مزرعه (بر اساس مزارع موجود در filtered_df_day)
    farm_list = ["همه مزارع"] + sorted(filtered_df_day['مزرعه'].unique().tolist())
    if len(farm_list) == 1 and selected_day != "همه روزها":
         st.sidebar.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد.", icon="⚠️")
         # در این حالت farm_list فقط شامل "همه مزارع" از لیست بالا خواهد بود که صحیح است.


    selected_farm = st.sidebar.selectbox("انتخاب مزرعه", options=farm_list)

    # انتخاب شاخص و سنسور
    available_indices = list(INDEX_FUNCTIONS.keys())
    selected_index = st.sidebar.selectbox("انتخاب شاخص", options=available_indices)
    selected_sensor = st.sidebar.radio("انتخاب سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, key='sensor_select', help="...")

    # --- پنل اصلی ---
    col1, col2 = st.columns([3, 1.5])

    with col1:
        st.subheader(f"نقشه وضعیت شاخص '{selected_index}'")
        map_placeholder = st.empty()

        # --- منطق نمایش نقشه ---
        display_geom = None; target_object_for_map = None; zoom_level = INITIAL_ZOOM
        map_df = filtered_df_day if selected_farm == "همه مزارع" else df[df['مزرعه'] == selected_farm]

        try:
            if selected_farm == "همه mزارع":
                if not map_df.empty:
                    # *** هندل کردن حالت یک مزرعه در نمایش همه مزارع ***
                    if map_df.shape[0] == 1:
                        # اگر فقط یک مزرعه بود، مثل حالت تک مزرعه عمل کن
                        farm_info_row = map_df.iloc[0]
                        farm_lat = farm_info_row['عرض جغرافیایی']; farm_lon = farm_info_row['طول جغرافیایی']
                        if pd.notna(farm_lat) and pd.notna(farm_lon):
                            farm_point = ee.Geometry.Point([farm_lon, farm_lat])
                            display_geom = farm_point.buffer(200)
                            target_object_for_map = farm_point
                            zoom_level = INITIAL_ZOOM + 3 # زوم بیشتر
                        else: st.warning("مختصات نامعتبر برای تنها مزرعه موجود.", icon="📍")
                    elif map_df.shape[0] > 1:
                         # اگر چند مزرعه بود، محدوده کلی را بگیر
                         min_lon, min_lat = map_df['طول جغرافیایی'].min(), map_df['عرض جغرافیایی'].min()
                         max_lon, max_lat = map_df['طول جغرافیایی'].max(), map_df['عرض جغرافیایی'].max()
                         if pd.notna(min_lon) and pd.notna(min_lat) and pd.notna(max_lon) and pd.notna(max_lat):
                             display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                             target_object_for_map = display_geom
                             zoom_level = INITIAL_ZOOM
                         else: st.warning("محدوده معتبری برای نمایش مزارع یافت نشد.", icon="🗺️")
                else: st.info(f"هیچ مزرعه‌ای برای نمایش با فیلتر روز '{selected_day}' یافت نشد.")

            else: # تک مزرعه انتخاب شده است
                if not map_df.empty:
                    farm_info_row = map_df.iloc[0]
                    farm_lat = farm_info_row['عرض جغرافیایی']; farm_lon = farm_info_row['طول جغرافیایی']
                    # چک مختصات قبلا در load_data انجام شده ولی برای اطمینان تکرار می‌شود
                    if pd.notna(farm_lat) and pd.notna(farm_lon):
                        farm_point = ee.Geometry.Point([farm_lon, farm_lat])
                        display_geom = farm_point.buffer(200)
                        target_object_for_map = farm_point
                        zoom_level = INITIAL_ZOOM + 3
                    else: st.warning(f"مختصات نامعتبر برای مزرعه {selected_farm}.", icon="📍")
                else: st.warning(f"اطلاعات مزرعه {selected_farm} یافت نشد.", icon="❓")

            # اگر هیچ هدفی تعیین نشد، از پیش‌فرض استفاده کن
            if target_object_for_map is None:
                target_object_for_map = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT])

        except Exception as e:
            st.error(f"خطا در تعیین هندسه نقشه: {e}")
            st.error(traceback.format_exc())
            target_object_for_map = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # بازگشت به پیش‌فرض

        # --- دریافت و نمایش لایه شاخص ---
        gee_layer_added = False; layer_image_for_download = None; vis_params = None
        if display_geom:
            with st.spinner(f"در حال پردازش تصویر '{selected_index}' ..."):
                collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)
                if collection and collection.size().getInfo() > 0:
                    index_func_detail = INDEX_FUNCTIONS.get(selected_index)
                    bands_ok = True
                    try:
                        first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
                        if index_func_detail.get('requires_blue') and 'Blue' not in first_image_bands: bands_ok = False
                        if index_func_detail.get('requires_swir1') and 'SWIR1' not in first_image_bands: bands_ok = False
                    except: bands_ok = False

                    if index_func_detail and bands_ok:
                        def calculate_selected_index_map(image):
                            try:
                                calc_img = index_func_detail['func'](image)
                                if selected_index in calc_img.bandNames().getInfo(): return calc_img.select(selected_index).copyProperties(image, ["system:time_start"])
                                else: return ee.Image().rename(selected_index).updateMask(ee.Image(0)).set('system:time_start', image.get('system:time_start'))
                            except: return ee.Image().set('system:time_start', image.get('system:time_start'))
                        indexed_collection = collection.map(calculate_selected_index_map)
                        try:
                            median_image = indexed_collection.select(selected_index).median()
                            if selected_index in median_image.bandNames().getInfo():
                                layer_image = median_image.clip(display_geom)
                                vis_params = index_func_detail.get('vis')
                                if not vis_params: vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'gray']}
                                # ایجاد نقشه و افزودن لایه
                                m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False); m.add_basemap('HYBRID')
                                try:
                                    m.addLayer(layer_image, vis_params, f'{selected_index} ({selected_sensor} - Median)')
                                    layer_image_for_download = layer_image; gee_layer_added = True
                                    try: m.add_colorbar(vis_params, label=selected_index, layer_name=f'{selected_index} ({selected_sensor} - Median)')
                                    except Exception as legend_e: print(f"خطا لجند: {legend_e}")
                                except Exception as addlayer_e: st.error(f"خطا افزودن لایه: {addlayer_e}")
                            else: st.warning(f"باند '{selected_index}' در تصویر میانه یافت نشد.", icon="⚠️")
                        except ee.EEException as median_e: st.error(f"خطای تصویر میانه: {median_e}")
                    # else: # پیام‌های خطا قبلا داده شده‌اند
                else: st.info(f"هیچ تصویر مناسبی ({selected_sensor}) یافت نشد.", icon="🛰️☁️")

        # --- ایجاد نقشه پایه اگر لایه اضافه نشد ---
        if not gee_layer_added:
             m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
             m.add_basemap('HYBRID')
             if not display_geom and target_object_for_map is None: st.info("هندسه معتبری برای نمایش لایه GEE وجود ندارد.")

        # --- افزودن مارکرها ---
        try:
            if not map_df.empty:
                 for idx, row in map_df.iterrows():
                      if pd.notna(row['عرض جغرافیایی']) and pd.notna(row['طول جغرافیایی']):
                           popup_html = f"""
                           <div style="font-family: Tahoma; font-size: 10pt; direction: rtl;">
                           <b>مزرعه:</b> {row['مزرعه']}<br>
                           <b>کانال:</b> {row['کانال']}<br>
                           <b>اداره:</b> {row['اداره']}<br>
                           <b>مساحت:</b> {row['مساحت داشت']:.2f} هکتار<br>
                           <b>واریته:</b> {row['واریته']}<br>
                           <b>سن:</b> {row['سن']}<br>
                           <b>روز آبیاری:</b> {row['روزهای هفته']}
                           </div>
                           """
                           icon_color = 'red' if selected_farm != "همه مزارع" and row['مزرعه'] == selected_farm else 'blue'
                           icon_type = 'star' if selected_farm != "همه مزارع" and row['مزرعه'] == selected_farm else 'info-sign'
                           folium.Marker(
                               location=[row['عرض جغرافیایی'], row['طول جغرافیایی']],
                               popup=folium.Popup(popup_html, max_width=300),
                               tooltip=f"مزرعه {row['مزرعه']}",
                               icon=folium.Icon(color=icon_color, icon=icon_type)
                           ).add_to(m)
        except Exception as marker_e: st.warning(f"خطا در افزودن مارکر: {marker_e}", icon="⚠️")

        # --- مرکز نقشه ---
        if target_object_for_map:
            try: m.center_object(target_object_for_map, zoom=zoom_level)
            except Exception as center_e: print(f"خطا مرکز نقشه: {center_e}")

        # --- نمایش نقشه ---
        with map_placeholder:
             try: m.to_streamlit(height=550)
             except Exception as map_render_e: st.error(f"خطا نمایش نقشه: {map_render_e}")

        # --- دکمه دانلود تصویر نقشه ---
        if gee_layer_added and layer_image_for_download and vis_params and display_geom:
            try:
                # استفاده از geometry().bounds().getInfo() برای GeoJSON معتبر
                region = display_geom.geometry().bounds().getInfo()['coordinates']
                thumb_url = layer_image_for_download.getThumbURL({
                    'region': region, 'bands': selected_index, 'palette': vis_params['palette'],
                    'min': vis_params['min'], 'max': vis_params['max'], 'dimensions': 512
                })
                response = requests.get(thumb_url, stream=True)
                if response.status_code == 200:
                    img_bytes = BytesIO(response.content)
                    st.sidebar.download_button( label=f"دانلود نقشه ({selected_index})", data=img_bytes,
                        file_name=f"map_{selected_farm.replace(' ', '_') if selected_farm != 'همه مزارع' else 'all'}_{selected_index}.png",
                        mime="image/png", key=f"download_map_{selected_index}")
            except Exception as thumb_e: print(f"خطای لینک دانلود نقشه: {thumb_e}")

    with col2:
        # --- جزئیات، نمودار یا رتبه‌بندی ---
        if selected_farm != "همه مزارع":
            st.subheader(f"جزئیات مزرعه: {selected_farm}")
            # پیدا کردن اطلاعات مزرعه از df اصلی
            farm_info_row_detail = df[df['مزرعه'] == selected_farm].iloc[0] if not df[df['مزرعه'] == selected_farm].empty else None
            if farm_info_row_detail is not None:
                details_cols = st.columns(2)
                with details_cols[0]:
                    st.metric("کانال", str(farm_info_row_detail['کانال']))
                    st.metric("مساحت", f"{farm_info_row_detail['مساحت داشت']:.2f} هکتار" if pd.notna(farm_info_row_detail['مساحت داشت']) else "N/A")
                    st.metric("سن", str(farm_info_row_detail['سن']))
                with details_cols[1]:
                    st.metric("اداره", str(farm_info_row_detail['اداره']))
                    st.metric("واریته", str(farm_info_row_detail['واریته']))
                    st.metric("روز آبیاری", str(farm_info_row_detail['روزهای هفته']))

                st.subheader(f"روند شاخص '{selected_index}'")
                if pd.notna(farm_info_row_detail['عرض جغرافیایی']) and pd.notna(farm_info_row_detail['طول جغرافیایی']):
                    with st.spinner(f"در حال دریافت سری زمانی {selected_index}..."):
                        try:
                            farm_geom = ee.Geometry.Point([farm_info_row_detail['طول جغرافیایی'], farm_info_row_detail['عرض جغرافیایی']])
                            ts_df = get_timeseries_for_farm(farm_geom.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)
                            if ts_df is not None and not ts_df.empty:
                                fig = px.line(ts_df, x='Date', y=selected_index, title=f"روند زمانی {selected_index}", markers=True, labels={'Date': 'تاریخ', selected_index: selected_index})
                                st.plotly_chart(fig, use_container_width=True)
                            elif ts_df is not None: st.info(f"داده‌ای برای نمودار {selected_index} یافت نشد.", icon="📉")
                        except Exception as ts_e: st.error(f"خطای نمایش سری زمانی: {ts_e}")
                else: st.warning("مختصات نامعتبر برای دریافت سری زمانی.", icon="📍")
            else: st.info(f"اطلاعات مزرعه '{selected_farm}' یافت نشد.")

        else: # "همه مزارع"
            st.subheader(f"رتبه‌بندی مزارع بر اساس '{selected_index}'")
            st.info(f"نمایش رتبه‌بندی '{selected_index}' ({selected_sensor}) از {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} برای روز: '{selected_day}'.")

            if not filtered_df_day.empty:
                 with st.spinner(f"در حال محاسبه رتبه‌بندی مزارع..."):
                    try:
                        ranking_df = get_latest_index_for_ranking(filtered_df_day.to_json(), selected_day, start_date, end_date, selected_index, selected_sensor)
                        if ranking_df is not None and not ranking_df.empty:
                            st.dataframe(ranking_df.style.format({'رتبه': "{:}", 'مزرعه': "{:}", selected_index: "{:.3f}"}).hide(axis="index"), use_container_width=True)
                            csv = ranking_df.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(label=f"دانلود جدول رتبه‌بندی ({selected_index})", data=csv,
                               file_name=f'ranking_{selected_index}_{selected_day}_{start_date}_{end_date}.csv',
                               mime='text/csv', key='download_ranking_csv')
                        elif ranking_df is not None: st.warning("اطلاعاتی برای رتبه‌بندی یافت نشد.", icon="📊")
                    except Exception as rank_e: st.error(f"خطای نمایش رتبه‌بندی: {rank_e}")
            else: st.info(f"هیچ مزرعه‌ای برای رتبه‌بندی در روز '{selected_day}' یافت نشد.")

else:
    st.warning("در انتظار اتصال به Google Earth Engine...", icon="⏳")

# --- فوتر ---
st.sidebar.markdown("---")
st.sidebar.info("راهنما: از منوهای بالا برای انتخاب تنظیمات استفاده کنید.")
if gee_initialized: st.sidebar.markdown(f"**سنسور فعال:** {selected_sensor}")
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
import requests # برای دانلود getThumbUrl لازم است

# --- پیکربندی ---
APP_TITLE = "داشبورد مانیتورینگ مزارع نیشکر دهخدا"
INITIAL_LAT = 31.534442
INITIAL_LON = 48.724416
INITIAL_ZOOM = 12

# --- مسیر فایل‌ها (نسبت به مکان اسکریپت در هاگینگ فیس) ---
# !!! مهم: این فایل‌ها باید در کنار فایل app.py در ریپازیتوری هاگینگ فیس شما باشند !!!
CSV_FILE_PATH = 'output (1).csv' # نام فایل CSV شما
SERVICE_ACCOUNT_FILE = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json' # نام فایل کلید خود را اینجا قرار دهید

# --- توابع ---

def initialize_gee():
    """اتصال به Google Earth Engine با استفاده از Service Account."""
    try:
        # بررسی وجود فایل کلید
        if not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.error(f"خطا: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
            st.error("لطفاً فایل کلید JSON را در کنار فایل اصلی برنامه در ریپازیتوری هاگینگ فیس قرار دهید.")
            st.stop()

        # استفاده از فایل کلید برای احراز هویت
        credentials = ee.ServiceAccountCredentials(None, key_file=SERVICE_ACCOUNT_FILE)
        ee.Initialize(credentials=credentials, opt_url='https://earthengine-highvolume.googleapis.com')
        print("GEE با موفقیت با استفاده از Service Account متصل شد.")
        st.success("اتصال به Google Earth Engine با موفقیت برقرار شد.", icon="✅")
        return True
    except ee.EEException as e:
        st.error(f"خطا در اتصال به Google Earth Engine: {e}")
        st.error("لطفاً از صحت فایل Service Account و فعال بودن آن در پروژه GEE اطمینان حاصل کنید.")
        st.stop()
    except FileNotFoundError: # این خطا دیگر نباید رخ دهد چون در بالا چک می‌شود
        st.error(f"خطای مسیر فایل: فایل Service Account در مسیر '{SERVICE_ACCOUNT_FILE}' یافت نشد.")
        st.stop()
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام اتصال به GEE: {e}")
        st.stop()
    return False # اگر به هر دلیلی موفقیت‌آمیز نبود

def load_data(csv_path):
    """بارگذاری داده‌های مزارع از فایل CSV با هندلینگ خطای .str accessor."""
    try:
        df = pd.read_csv(csv_path)

        # 1. تمیز کردن نام ستون‌ها (حذف فواصل اضافی از نام ستون‌ها)
        # این کار 'سن ' را به 'سن' تبدیل می‌کند
        df.columns = df.columns.str.strip()
        print("نام ستون‌های تصحیح شده:", df.columns.tolist()) # نمایش نام ستون‌های نهایی

        # 2. تبدیل مختصات به عدد و مدیریت مقادیر نامعتبر
        df['طول جغرافیایی'] = pd.to_numeric(df['طول جغرافیایی'], errors='coerce')
        df['عرض جغرافیایی'] = pd.to_numeric(df['عرض جغرافیایی'], errors='coerce')
        # ایجاد ستون برای بررسی وجود مختصات قبل از حذف NaNها
        df['coordinates_missing'] = df[['طول جغرافیایی', 'عرض جغرافیایی']].isnull().any(axis=1).astype(int)
        # حذف ردیف‌هایی که مختصات معتبر ندارند
        df.dropna(subset=['طول جغرافیایی', 'عرض جغرافیایی'], inplace=True)

        # 3. تبدیل مساحت به عدد
        df['مساحت داشت'] = pd.to_numeric(df['مساحت داشت'], errors='coerce')

        # 4. پردازش ستون‌های متنی (کلید رفع خطای .str accessor)
        string_columns = ['مزرعه', 'کانال', 'اداره', 'واریته', 'سن', 'روزهای هفته']
        for col in string_columns:
            if col in df.columns:
                # الف) تبدیل صریح به رشته برای جلوگیری از خطای .str accessor
                df[col] = df[col].astype(str)
                # ب) جایگزینی مقادیر 'nan' (که از NaNهای عددی آمده) و رشته‌های خالی با 'نامشخص'
                # و حذف فواصل اضافی از ابتدا و انتهای مقادیر رشته‌ای
                df[col] = df[col].replace(['nan', 'NaN', '', None], 'نامشخص').str.strip()
            else:
                 st.warning(f"ستون مورد انتظار '{col}' در فایل CSV یافت نشد.")
                 df[col] = 'نامشخص' # ایجاد ستون با مقدار پیش‌فرض اگر وجود نداشت

        print(f"داده با موفقیت بارگذاری و پردازش شد. تعداد ردیف‌های معتبر: {df.shape[0]}, ستون‌ها: {df.shape[1]}")
        print("نمونه داده‌های پردازش شده:")
        print(df.head())
        print("\nاطلاعات نوع داده ستون‌ها:")
        print(df.info())

        return df
    except FileNotFoundError:
        st.error(f"خطا: فایل CSV در مسیر '{csv_path}' یافت نشد.")
        st.error("لطفاً فایل CSV را در کنار فایل اصلی برنامه در ریپازیتوری هاگینگ فیس قرار دهید.")
        st.stop()
        return None # اضافه شد برای وضوح
    except KeyError as e:
        st.error(f"خطا: ستون مورد انتظار '{e}' در فایل CSV یافت نشد یا پس از تمیز کردن نام‌ها قابل دسترسی نیست. لطفاً فرمت فایل و نام ستون‌ها را بررسی کنید.")
        st.stop()
        return None # اضافه شد برای وضوح
    except Exception as e:
        st.error(f"خطای غیرمنتظره هنگام بارگذاری یا پردازش داده‌های CSV: {e}")
        import traceback
        st.error(traceback.format_exc()) # نمایش جزئیات کامل خطا برای دیباگ
        st.stop()
        return None # اضافه شد برای وضوح

# --- توابع پردازش تصویر GEE ---

# تعریف نام باندهای مشترک (که بعد از پردازش استفاده می‌شوند)
COMMON_BAND_NAMES_S2 = ['Blue', 'Green', 'Red', 'RedEdge1', 'NIR', 'SWIR1', 'SWIR2']
COMMON_BAND_NAMES_L8L9 = ['Blue', 'Green', 'Red', 'NIR', 'SWIR1', 'SWIR2'] # لندست RedEdge ندارد

# --- توابع ماسک کردن ---
# این توابع حالا روی تصاویر با نام باندهای اصلی سنسور کار می‌کنند
# و تصاویری را با تنها باندهای داده مورد نیاز، مقیاس‌شده و ماسک‌شده برمی‌گردانند.

def mask_s2_clouds(image):
    """ماسک کردن ابرها در تصاویر Sentinel-2 SR با استفاده از QA60.
       باندهای داده مقیاس‌شده و ماسک‌شده را برمی‌گرداند (B2, B3, B4, B5, B8, B11, B12).
    """
    qa = image.select('QA60')
    # بیت‌های 10 و 11 به ترتیب برای ابرها و ابرهای سیروس هستند
    cloud_bit_mask = 1 << 10
    cirrus_bit_mask = 1 << 11
    # هر دو بیت باید 0 باشند (بدون ابر و سیروس)
    mask = qa.bitwiseAnd(cloud_bit_mask).eq(0).And(
             qa.bitwiseAnd(cirrus_bit_mask).eq(0))

    # انتخاب باندهای داده لازم با نام اصلی، اعمال ماسک، اعمال مقیاس
    data_bands = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12'] # باندهای S2 لازم برای شاخص‌ها
    # تقسیم بر 10000 برای تبدیل به بازتاب سطحی (0-1)
    return image.select(data_bands).updateMask(mask).divide(10000.0)\
        .copyProperties(image, ["system:time_start"]) # کپی کردن زمان تصویر

def mask_landsat_clouds(image):
    """ماسک کردن ابرها در تصاویر Landsat 8/9 SR با استفاده از QA_PIXEL.
       باندهای داده مقیاس‌شده و ماسک‌شده را برمی‌گرداند (SR_B2 تا SR_B7).
    """
    qa = image.select('QA_PIXEL')
    # بیت‌های 3 (سایه ابر)، 4 (برف)، 5 (ابر) باید 0 باشند
    cloud_shadow_bit = 1 << 3
    snow_bit = 1 << 4
    cloud_bit = 1 << 5
    mask = qa.bitwiseAnd(cloud_shadow_bit).eq(0)\
             .And(qa.bitwiseAnd(snow_bit).eq(0))\
             .And(qa.bitwiseAnd(cloud_bit).eq(0))

    # انتخاب باندهای SR (اپتیکال/SWIR)، اعمال ضریب مقیاس و آفست، اعمال ماسک
    sr_bands = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7'] # باندهای L8/9 لازم
    # اعمال ضریب مقیاس و آفست طبق مستندات Landsat Collection 2 Level 2
    scaled_bands = image.select(sr_bands).multiply(0.0000275).add(-0.2)

    return scaled_bands.updateMask(mask)\
        .copyProperties(image, ["system:time_start"])

# --- توابع محاسبه شاخص ---
# این توابع حالا انتظار دارند تصاویر با نام‌های باند مشترک باشند
# (Blue, Green, Red, NIR, SWIR1, و غیره)

def calculate_ndvi(image):
    """محاسبه NDVI."""
    # NDVI = (NIR - Red) / (NIR + Red)
    return image.normalizedDifference(['NIR', 'Red']).rename('NDVI')

def calculate_evi(image):
    """محاسبه EVI (نیاز به باند Blue دارد)."""
    try:
        # اطمینان از وجود باند Blue
        image.select('Blue')
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))', {
                'NIR': image.select('NIR'),
                'RED': image.select('Red'),
                'BLUE': image.select('Blue')
            }).rename('EVI')
        return evi
    except ee.EEException as e:
        # اگر باند Blue موجود نباشد (مثلاً در برخی پردازش‌های لندست)، خطا می‌دهد
        # print(f"محاسبه EVI ممکن نیست (باند Blue یافت نشد): {e}") # چاپ در لاگ به جای هشدار استریملیت
        # برگرداندن یک تصویر خالی یا مقدار پیش‌فرض برای جلوگیری از خطای بعدی
        return image.addBands(ee.Image(0).rename('EVI').updateMask(image.mask().reduce(ee.Reducer.first()))) # ایجاد باند EVI با ماسک تصویر اصلی

def calculate_ndmi(image):
    """محاسبه NDMI (شاخص نرمال‌شده تفاوت رطوبت)."""
    # NDMI = (NIR - SWIR1) / (NIR + SWIR1)
    try:
        image.select('SWIR1')
        return image.normalizedDifference(['NIR', 'SWIR1']).rename('NDMI')
    except ee.EEException:
        # print("محاسبه NDMI ممکن نیست (باند SWIR1 یافت نشد)")
        return image.addBands(ee.Image(0).rename('NDMI').updateMask(image.mask().reduce(ee.Reducer.first())))


def calculate_msi(image):
    """محاسبه MSI (شاخص تنش رطوبتی)."""
    # MSI = SWIR1 / NIR
    try:
        image.select('SWIR1')
        msi = image.expression('SWIR1 / NIR', {
            'SWIR1': image.select('SWIR1'),
            'NIR': image.select('NIR')
        }).rename('MSI')
        return msi
    except ee.EEException:
         # print("محاسبه MSI ممکن نیست (باند SWIR1 یافت نشد)")
         return image.addBands(ee.Image(0).rename('MSI').updateMask(image.mask().reduce(ee.Reducer.first())))


def calculate_lai_simple(image):
    """محاسبه ساده LAI (شاخص سطح برگ) با استفاده از EVI یا NDVI."""
    lai = None
    try:
        # اولویت با EVI
        # بررسی کنیم آیا باند Blue برای محاسبه EVI موجود است
        if 'Blue' in image.bandNames().getInfo():
            evi_band = calculate_evi(image).select('EVI')
             # فرمول تقریبی بر اساس EVI (نیاز به کالیبراسیون دارد)
            lai = evi_band.multiply(3.5).add(0.1)
            # print("LAI calculated using EVI")
        else:
             raise ee.EEException("Blue band not available for EVI-based LAI.")

    except Exception as e: # اگر EVI ممکن نبود یا خطا داد
        # print(f"محاسبه EVI برای LAI ممکن نبود ({e}), از NDVI استفاده می‌شود.")
        try:
            ndvi_band = calculate_ndvi(image).select('NDVI')
             # فرمول تقریبی بر اساس NDVI (نیاز به کالیبراسیون دارد)
            lai = ndvi_band.multiply(5.0).add(0.1)
            # print("LAI calculated using NDVI fallback")
        except Exception as ndvi_e:
             print(f"محاسبه NDVI برای LAI نیز با خطا مواجه شد: {ndvi_e}")
             return image.addBands(ee.Image(0).rename('LAI').updateMask(image.mask().reduce(ee.Reducer.first()))) # بازگشت مقدار پیش‌فرض

    # محدود کردن مقدار LAI در بازه منطقی
    return lai.clamp(0, 8).rename('LAI')

def calculate_biomass_simple(image):
    """محاسبه ساده بیومس با استفاده از LAI."""
    try:
        lai = calculate_lai_simple(image).select('LAI')
        # فرمول خطی ساده (نیاز به کالیبراسیون دارد)
        a = 1.5 # ضریب تبدیل LAI به بیومس (بسیار تقریبی)
        b = 0.2 # مقدار پایه بیومس
        biomass = lai.multiply(a).add(b)
        # محدود کردن مقدار بیومس (واحد نامشخص، تن در هکتار؟)
        return biomass.clamp(0, 50).rename('Biomass')
    except Exception as e:
        print(f"خطا در محاسبه بیومس: {e}")
        return image.addBands(ee.Image(0).rename('Biomass').updateMask(image.mask().reduce(ee.Reducer.first())))


def calculate_chlorophyll_mcari(image):
    """محاسبه تقریبی کلروفیل با MCARI (نیاز به باند RedEdge1 از Sentinel-2 دارد)."""
    try:
        # بررسی وجود باندهای لازم برای MCARI (مخصوصا RedEdge1)
        image.select('RedEdge1')
        image.select('Red')
        image.select('Green')
        # فرمول MCARI (Modified Chlorophyll Absorption in Reflectance Index)
        mcari = image.expression(
            '((RE1 - RED) - 0.2 * (RE1 - GREEN)) * (RE1 / RED)', {
                'RE1': image.select('RedEdge1'),
                'RED': image.select('Red'),
                'GREEN': image.select('Green')
            }).rename('Chlorophyll')
        # print("Chlorophyll calculated using MCARI (Sentinel-2).")
        return mcari
    except ee.EEException:
        # اگر RedEdge1 موجود نباشد (مثلا در لندست) یا خطای دیگری رخ دهد
        # print("MCARI نیاز به باند Red Edge (Sentinel-2) دارد. از NDVI به عنوان پراکسی کلروفیل استفاده می‌شود.")
        try:
             # استفاده از NDVI به عنوان جایگزین ساده
             ndvi_proxy = calculate_ndvi(image).rename('Chlorophyll')
             # print("Chlorophyll proxied using NDVI.")
             return ndvi_proxy
        except Exception as ndvi_e:
             print(f"محاسبه NDVI برای پراکسی کلروفیل نیز با خطا مواجه شد: {ndvi_e}")
             return image.addBands(ee.Image(0).rename('Chlorophyll').updateMask(image.mask().reduce(ee.Reducer.first())))


def calculate_et_placeholder(image):
    """محاسبه جایگزین برای تبخیر و تعرق (ET). از NDMI به عنوان پراکسی وضعیت رطوبت استفاده می‌کند."""
    # print("محاسبه دقیق ET پیچیده است. از NDMI به عنوان پراکسی وضعیت رطوبت استفاده می‌شود.")
    try:
        ndmi_proxy = calculate_ndmi(image).rename('ET_proxy')
        return ndmi_proxy
    except Exception as e:
        print(f"خطا در محاسبه پراکسی ET (NDMI): {e}")
        return image.addBands(ee.Image(0).rename('ET_proxy').updateMask(image.mask().reduce(ee.Reducer.first())))


# دیکشنری نگاشت نام شاخص‌ها به توابع و پارامترهای نمایش
INDEX_FUNCTIONS = {
    'NDVI': {'func': calculate_ndvi, 'vis': {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}},
    'EVI': {'func': calculate_evi, 'vis': {'min': 0, 'max': 1, 'palette': ['#FEE8C8', '#FDBB84', '#E34A33', '#A50F15', '#4C061D']}, 'requires_blue': True}, # پالت متفاوت برای EVI
    'NDMI': {'func': calculate_ndmi, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}, 'requires_swir1': True},
    'MSI': {'func': calculate_msi, 'vis': {'min': 0.5, 'max': 3.0, 'palette': ['#006837', '#A6D96A', '#FFFFBF', '#FDAE61', '#D73027']}, 'requires_swir1': True}, # پالت و بازه بهتر برای MSI
    'LAI': {'func': calculate_lai_simple, 'vis': {'min': 0, 'max': 8, 'palette': ['#FEF0D9', '#FDCC8A', '#FC8D59', '#E34A33', '#B30000']}, 'requires_blue_optional': True}, # پالت بهتر برای LAI
    'Biomass': {'func': calculate_biomass_simple, 'vis': {'min': 0, 'max': 30, 'palette': ['#FFFFD4', '#FED98E', '#FE9929', '#D95F0E', '#993404']}, 'requires_blue_optional': True}, # پالت بهتر برای بیومس
    'Chlorophyll': {'func': calculate_chlorophyll_mcari, 'vis': {'min': 0, 'max': 1.2, 'palette': ['#FFFFE5', '#F7FCB9', '#D9F0A3', '#ADDD8E', '#78C679', '#41AB5D', '#238443', '#005A32']}, 'requires_rededge': True}, # پالت سبز برای کلروفیل
    'ET_proxy': {'func': calculate_et_placeholder, 'vis': {'min': -0.5, 'max': 0.8, 'palette': ['brown', 'white', 'blue']}, 'requires_swir1': True} # همانند NDMI
}


# --- دریافت داده GEE ---
def get_image_collection(start_date, end_date, geometry, sensor='Sentinel-2'):
    """دریافت، فیلتر، ماسک، مقیاس‌بندی و تغییر نام تصاویر Sentinel-2 یا Landsat."""
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    collection = None
    mask_func = None
    bands_to_select_orig = None
    bands_to_rename_to = None
    collection_id = None # برای پیام خطا

    try:
        if sensor == 'Sentinel-2':
            collection_id = 'COPERNICUS/S2_SR_HARMONIZED'
            mask_func = mask_s2_clouds
            bands_to_select_orig = ['B2', 'B3', 'B4', 'B5', 'B8', 'B11', 'B12', 'QA60']
            bands_to_rename_to = COMMON_BAND_NAMES_S2
            collection = ee.ImageCollection(collection_id)

        elif sensor == 'Landsat':
            l9_id = 'LANDSAT/LC09/C02/T1_L2'
            l8_id = 'LANDSAT/LC08/C02/T1_L2'
            collection_id = f"{l9_id} & {l8_id}"
            l9 = ee.ImageCollection(l9_id)
            l8 = ee.ImageCollection(l8_id)
            collection = l9.merge(l8)
            mask_func = mask_landsat_clouds
            bands_to_select_orig = ['SR_B2', 'SR_B3', 'SR_B4', 'SR_B5', 'SR_B6', 'SR_B7', 'QA_PIXEL']
            bands_to_rename_to = COMMON_BAND_NAMES_L8L9
        else:
            st.error(f"سنسور '{sensor}' پشتیبانی نمی‌شود.")
            return None

        # فیلتر زمانی و مکانی
        collection = collection.filterDate(start_date_str, end_date_str)
        if geometry:
            collection = collection.filterBounds(geometry)

        # بررسی تعداد تصاویر اولیه
        initial_count = collection.size().getInfo()
        if initial_count == 0:
            # print(f"هیچ تصویری با سنسور {sensor} ({collection_id}) برای دوره {start_date_str} تا {end_date_str} و منطقه انتخابی قبل از ماسک ابر یافت نشد.")
            # st.warning(f"هیچ تصویری با سنسور {sensor} برای دوره و منطقه انتخابی قبل از ماسک ابر یافت نشد.", icon="🛰️") # هشدار را در اینجا نمی‌دهیم تا UI شلوغ نشود
            return None
        # print(f"{initial_count} تصویر {sensor} قبل از ماسک ابر یافت شد.")

        # --- تابع پردازش برای اعمال روی هر تصویر ---
        def process_image(image):
            img_selected_orig = image.select(bands_to_select_orig)
            img_processed = mask_func(img_selected_orig)
            img_renamed = img_processed.rename(bands_to_rename_to)
            return img_renamed.copyProperties(image, ["system:time_start"])

        # اعمال تابع پردازش روی کالکشن
        processed_collection = collection.map(process_image)

        # بررسی خالی بودن کالکشن بعد از فیلتر/ماسک
        count = processed_collection.size().getInfo()
        if count == 0:
            # print(f"هیچ تصویر بدون ابری با سنسور {sensor} برای دوره و منطقه انتخابی یافت نشد.")
            # st.warning(f"هیچ تصویر بدون ابری با سنسور {sensor} برای دوره و منطقه انتخابی یافت نشد.", icon="☁️") # هشدار را در اینجا نمی‌دهیم
            return None
        # print(f"{count} تصویر {sensor} پس از ماسک ابر باقی ماند.")

        # بررسی باندهای اولین تصویر بعد از پردازش برای اطمینان
        first_image = processed_collection.first()
        if first_image is None:
             # print("کالکشن پس از اعمال تابع پردازش خالی شد.") # نباید اتفاق بیافتد اگر count > 0
             return None # یا کالکشن خالی برگردانیم؟
        final_bands = first_image.bandNames().getInfo()
        # print(f"باندهای نهایی در کالکشن پردازش شده ({sensor}): {final_bands}")

        expected_check = bands_to_rename_to
        if not all(name in final_bands for name in expected_check):
            print(f"هشدار: همه باندهای مشترک مورد انتظار ({expected_check}) یافت نشدند. باندهای موجود: {final_bands}")
            # st.warning(f"هشدار: همه باندهای مشترک مورد انتظار ({expected_check}) یافت نشدند. باندهای موجود: {final_bands}", icon="⚠️")

        return processed_collection

    except ee.EEException as e:
        st.error(f"خطای Google Earth Engine در تابع get_image_collection: {e}")
        st.info(f"جزئیات: سنسور={sensor}, دوره={start_date_str} تا {end_date_str}, کالکشن={collection_id}")
        return None
    except Exception as e:
        st.error(f"خطای غیرمنتظره در تابع get_image_collection: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None


# --- توابع تحلیل GEE (با استفاده از کش) ---

@st.cache_data(ttl=3600) # کش برای ۱ ساعت
def get_timeseries_for_farm(_farm_geom_geojson, start_date, end_date, index_name, sensor):
    """دریافت سری زمانی برای یک شاخص و هندسه مزرعه خاص."""
    if not _farm_geom_geojson:
        st.error("هندسه مزرعه برای سری زمانی نامعتبر است.")
        return pd.DataFrame(columns=['Date', index_name])

    try:
        farm_geom = ee.Geometry(json.loads(_farm_geom_geojson))
    except Exception as e:
        st.error(f"خطا در تبدیل GeoJSON هندسه مزرعه: {e}")
        return pd.DataFrame(columns=['Date', index_name])

    # 1. دریافت کالکشن پردازش شده (ماسک شده، مقیاس شده، تغییر نام یافته)
    collection = get_image_collection(start_date, end_date, farm_geom, sensor)
    if collection is None or collection.size().getInfo() == 0:
        # پیام هشدار در اینجا داده نمی‌شود، تابع فراخواننده مدیریت می‌کند
        # st.warning(f"داده تصویری برای محاسبه سری زمانی {index_name} یافت نشد.", icon="📉")
        return pd.DataFrame(columns=['Date', index_name])

    # 2. بررسی امکان محاسبه شاخص درخواستی
    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail:
         st.error(f"تابع محاسبه شاخص برای {index_name} یافت نشد.")
         return pd.DataFrame(columns=['Date', index_name])

    # بررسی وجود باندهای لازم بر اساس سنسور و شاخص
    bands_ok_for_index = True
    try:
        first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
        if index_func_detail.get('requires_blue') and 'Blue' not in first_image_bands:
            # st.warning(f"شاخص {index_name} به باند 'Blue' نیاز دارد که در داده‌های {sensor} موجود نیست.", icon="⚠️")
            bands_ok_for_index = False
        if index_func_detail.get('requires_swir1') and 'SWIR1' not in first_image_bands:
            # st.warning(f"شاخص {index_name} به باند 'SWIR1' نیاز دارد که ممکن است در داده‌های پردازش شده موجود نباشد.", icon="⚠️")
            bands_ok_for_index = False
        if index_func_detail.get('requires_rededge') and sensor != 'Sentinel-2':
            # st.warning(f"شاخص {index_name} به باند 'RedEdge1' نیاز دارد که فقط در Sentinel-2 موجود است (از جایگزین استفاده می‌شود).", icon="⚠️")
            # تابع محاسبه خودش جایگزین را هندل می‌کند، پس False نمی‌کنیم
             pass
    except ee.EEException as e:
        st.error(f"خطا در بررسی باندهای اولیه برای سری زمانی: {e}")
        return pd.DataFrame(columns=['Date', index_name])
    except Exception as e: # خطای غیر GEE مثل bandNames().getInfo() روی کالکشن خالی
        st.error(f"خطای غیرمنتظره در بررسی باندها برای سری زمانی: {e}")
        return pd.DataFrame(columns=['Date', index_name])

    if not bands_ok_for_index:
         st.warning(f"محاسبه سری زمانی برای {index_name} با سنسور {sensor} ممکن نیست (باندهای لازم موجود نیستند).", icon="⚠️")
         return pd.DataFrame(columns=['Date', index_name])


    # 3. محاسبه *فقط* شاخص مورد نیاز برای سری زمانی
    def calculate_single_index(image):
        try:
            # فقط باند مورد نظر را برگردان
            calculated_image = index_func_detail['func'](image)
            # اطمینان از وجود باند پس از محاسبه
            if index_name in calculated_image.bandNames().getInfo():
                 return calculated_image.select(index_name).copyProperties(image, ["system:time_start"])
            else:
                 # اگر محاسبه شاخص به دلایلی باند را ایجاد نکرد (مثلا EVI بدون Blue)
                 return ee.Image().rename(index_name).updateMask(ee.Image(0)).set('system:time_start', image.get('system:time_start'))
        except Exception as e:
             # print(f"خطا در محاسبه {index_name} برای یک تصویر: {e}. این تصویر نادیده گرفته می‌شود.")
             # برگرداندن یک تصویر خالی (بدون باند) با زمان
             return ee.Image().set('system:time_start', image.get('system:time_start'))


    indexed_collection = collection.map(calculate_single_index)

    # فیلتر کردن تصاویری که باند مورد نظر را ندارند (اختیاری، چون calculate_single_index هندل می‌کند)
    # indexed_collection = indexed_collection.filter(ee.Filter.listContains('system:band_names', index_name))
    # if indexed_collection.size().getInfo() == 0:
    #     st.warning(f"هیچ تصویری پس از محاسبه شاخص {index_name} باند مورد نظر را نداشت.", icon="⚠️")
    #     return pd.DataFrame(columns=['Date', index_name])

    # 4. استخراج مقدار میانگین شاخص برای هر تصویر در هندسه مزرعه
    def extract_value(image):
        # اطمینان از وجود باند قبل از reduceRegion
        image_with_band = ee.Algorithms.If(
            image.bandNames().contains(index_name),
            image,
            ee.Image().set('system:time_start', image.get('system:time_start')) # تصویر خالی اگر باند نبود
        )
        image = ee.Image(image_with_band)

        # فقط روی تصاویری که باند دارند اجرا کن
        val = ee.Algorithms.If(
            image.bandNames().contains(index_name),
            image.select(index_name).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=farm_geom,
                scale=30,
                maxPixels=1e9,
                tileScale=4
            ).get(index_name),
            -9999 # مقدار پیش‌فرض اگر باند نبود یا reduceRegion ناموفق بود
        )

        return ee.Feature(None, {
            'time': image.get('system:time_start'),
            index_name: ee.Algorithms.If(val, val, -9999) # هندل کردن null احتمالی
            })

    try:
        # اعمال تابع استخراج روی کالکشن شاخص‌دار و دریافت نتایج
        ts_info = indexed_collection.map(extract_value).getInfo()
    except ee.EEException as e:
        st.error(f"خطا در استخراج مقادیر سری زمانی (reduceRegion): {e}")
        st.info("این مشکل ممکن است به دلیل محدودیت‌های حافظه یا زمان GEE باشد. سعی کنید بازه زمانی یا منطقه کوچک‌تری را انتخاب کنید یا tileScale را در کد افزایش دهید.")
        # تلاش مجدد با tileScale بزرگتر
        try:
            st.info("تلاش مجدد با tileScale = 8 ...")
            def extract_value_large_tile(image):
                 image_with_band = ee.Algorithms.If(image.bandNames().contains(index_name),image,ee.Image().set('system:time_start', image.get('system:time_start')))
                 image = ee.Image(image_with_band)
                 val = ee.Algorithms.If(image.bandNames().contains(index_name),image.select(index_name).reduceRegion(reducer=ee.Reducer.mean(), geometry=farm_geom, scale=30, maxPixels=1e9, tileScale=8).get(index_name),-9999)
                 return ee.Feature(None, {'time': image.get('system:time_start'), index_name: ee.Algorithms.If(val, val, -9999)})
            ts_info = indexed_collection.map(extract_value_large_tile).getInfo()
            st.success("تلاش مجدد موفق بود.")
        except ee.EEException as e2:
             st.error(f"تلاش مجدد نیز ناموفق بود: {e2}")
             return pd.DataFrame(columns=['Date', index_name])


    # 5. تبدیل نتایج به دیتافریم Pandas
    data = []
    for feature in ts_info['features']:
        props = feature.get('properties', {})
        value = props.get(index_name)
        time_ms = props.get('time')
        # بررسی معتبر بودن مقدار و زمان قبل از پردازش
        if value is not None and value != -9999 and time_ms is not None:
            try:
                # تبدیل timestamp میلی‌ثانیه به datetime
                dt = datetime.datetime.fromtimestamp(time_ms / 1000.0).date() # فقط تاریخ را نگه دار
                data.append([dt, value])
            except (TypeError, ValueError):
                 # نادیده گرفتن مقادیر نامعتبر زمان
                 print(f"نادیده گرفتن داده با زمان نامعتبر: {time_ms}")

    if not data:
        # st.warning(f"هیچ داده معتبری برای سری زمانی {index_name} پس از پردازش GEE یافت نشد.", icon="📉") # پیام در UI نمی‌دهیم
        return pd.DataFrame(columns=['Date', index_name])

    ts_df = pd.DataFrame(data, columns=['Date', index_name])
    # مرتب‌سازی بر اساس تاریخ و حذف داده‌های تکراری احتمالی برای یک روز (میانگین‌گیری)
    ts_df['Date'] = pd.to_datetime(ts_df['Date'])
    ts_df = ts_df.groupby('Date')[index_name].mean().reset_index()
    ts_df = ts_df.sort_values(by='Date')
    return ts_df

@st.cache_data(ttl=3600) # کش برای ۱ ساعت
def get_latest_index_for_ranking(_farms_df_json, selected_day_filter, start_date, end_date, index_name, sensor):
    """دریافت مقدار متوسط شاخص برای رتبه‌بندی مزارع فعال در روز انتخابی."""
    try:
        # خواندن دیتافریم از JSON کش شده
        farms_df = pd.read_json(_farms_df_json)
    except Exception as e:
        st.error(f"خطا در خواندن دیتافریم JSON برای رتبه‌بندی: {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # فیلتر کردن دیتافریم بر اساس روز هفته انتخابی
    # این فیلتر باید قبل از فراخوانی این تابع انجام شود، اما برای اطمینان اینجا هم چک می‌کنیم
    if selected_day_filter != "همه روزها":
        if 'روزهای هفته' in farms_df.columns:
            farms_df_filtered = farms_df[farms_df['روزهای هفته'] == selected_day_filter].copy()
        else:
            # st.error("ستون 'روزهای هفته' برای فیلتر کردن رتبه‌بندی یافت نشد.")
            farms_df_filtered = farms_df # اگر ستون نبود، همه را در نظر بگیر
    else:
        farms_df_filtered = farms_df.copy()

    if farms_df_filtered.empty:
        # st.warning(f"هیچ مزرعه‌ای برای روز '{selected_day_filter}' جهت رتبه‌بندی یافت نشد.", icon="📊")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # 1. ایجاد FeatureCollection از هندسه مزارع (با بافر)
    features = []
    valid_farm_ids = [] # برای پیگیری مزارعی که هندسه معتبر دارند
    for idx, row in farms_df_filtered.iterrows():
        try:
             # اطمینان از معتبر بودن مختصات
             if pd.notna(row['طول جغرافیایی']) and pd.notna(row['عرض جغرافیایی']):
                 geom = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
                 buffered_geom = geom.buffer(50) # شعاع 50 متری
                 feature = ee.Feature(buffered_geom, {'farm_id': row['مزرعه']})
                 features.append(feature)
                 valid_farm_ids.append(row['مزرعه'])
             # else:
                  # print(f"مختصات نامعتبر برای مزرعه {row.get('مزرعه', 'ناشناخته')}، از رتبه‌بندی حذف شد.")
        except Exception as e:
             print(f"خطا در ایجاد هندسه برای مزرعه {row.get('مزرعه', 'ناشناخته')}: {e}")

    if not features:
         # st.warning("هیچ هندسه معتبری برای مزارع جهت رتبه‌بندی یافت نشد.", icon="📊")
         return pd.DataFrame(columns=['مزرعه', index_name])

    farm_fc = ee.FeatureCollection(features)
    bounds = farm_fc.geometry().bounds() # محدوده کلی برای فیلتر اولیه

    # 2. دریافت کالکشن پردازش شده برای محدوده مزارع
    collection = get_image_collection(start_date, end_date, bounds, sensor)
    if collection is None or collection.size().getInfo() == 0:
        # st.warning(f"داده تصویری برای محاسبه رتبه‌بندی {index_name} یافت نشد.", icon="📊")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # 3. بررسی امکان محاسبه شاخص درخواستی
    index_func_detail = INDEX_FUNCTIONS.get(index_name)
    if not index_func_detail:
        st.error(f"تابع محاسبه شاخص برای {index_name} یافت نشد.")
        return pd.DataFrame(columns=['مزرعه', index_name])

    bands_ok_for_index = True
    try:
        first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
        if index_func_detail.get('requires_blue') and 'Blue' not in first_image_bands: bands_ok_for_index = False
        if index_func_detail.get('requires_swir1') and 'SWIR1' not in first_image_bands: bands_ok_for_index = False
        if index_func_detail.get('requires_rededge') and sensor != 'Sentinel-2': pass # تابع خودش هندل می‌کند
    except ee.EEException as e:
        st.error(f"خطا در بررسی باندهای اولیه برای رتبه‌بندی: {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])
    except Exception as e:
        st.error(f"خطای غیرمنتظره در بررسی باندها برای رتبه‌بندی: {e}")
        return pd.DataFrame(columns=['مزرعه', index_name])


    if not bands_ok_for_index:
        st.warning(f"محاسبه رتبه‌بندی برای {index_name} با سنسور {sensor} ممکن نیست (باندهای لازم موجود نیستند).", icon="⚠️")
        return pd.DataFrame(columns=['مزرعه', index_name])

    # 4. محاسبه *فقط* شاخص مورد نیاز
    def calculate_single_index_rank(image):
        try:
            calculated_image = index_func_detail['func'](image)
            if index_name in calculated_image.bandNames().getInfo():
                 return calculated_image.select(index_name).copyProperties(image, ["system:time_start"])
            else:
                 return ee.Image().rename(index_name).updateMask(ee.Image(0)).set('system:time_start', image.get('system:time_start'))
        except Exception:
             return ee.Image().set('system:time_start', image.get('system:time_start'))

    indexed_collection = collection.map(calculate_single_index_rank)

    # 5. ایجاد تصویر ترکیبی میانه
    try:
         median_image = indexed_collection.select(index_name).median()
         # اطمینان از وجود باند در تصویر میانه
         if index_name not in median_image.bandNames().getInfo():
              st.warning(f"باند '{index_name}' در تصویر میانه برای رتبه‌بندی یافت نشد.", icon="⚠️")
              return pd.DataFrame(columns=['مزرعه', index_name])
    except ee.EEException as e:
         st.error(f"خطا در ایجاد تصویر میانه برای رتبه‌بندی: {e}")
         return pd.DataFrame(columns=['مزرعه', index_name])


    # 6. استخراج مقدار میانگین شاخص از تصویر ترکیبی برای هر مزرعه
    try:
        farm_values = median_image.reduceRegions(
            collection=farm_fc,
            reducer=ee.Reducer.mean(), # میانگین در هر هندسه
            scale=30,
            tileScale=4
        ).getInfo()
    except ee.EEException as e:
        st.error(f"خطا حین اجرای reduceRegions برای رتبه‌بندی: {e}")
        st.info("تلاش مجدد با tileScale بزرگتر...")
        try:
             farm_values = median_image.reduceRegions(
                collection=farm_fc,
                reducer=ee.Reducer.mean(),
                scale=30,
                tileScale=8
             ).getInfo()
             st.success("تلاش مجدد برای reduceRegions موفق بود.")
        except ee.EEException as e2:
             st.error(f"اجرای reduceRegions دوباره با شکست مواجه شد: {e2}")
             st.warning("محاسبه رتبه‌بندی مزارع ممکن نیست. سعی کنید بازه زمانی یا تعداد مزارع را کاهش دهید.")
             return pd.DataFrame(columns=['مزرعه', index_name])

    # 7. تبدیل نتایج به دیتافریم Pandas
    ranking_data = {} # استفاده از دیکشنری برای دسترسی سریعتر
    for feature in farm_values['features']:
        props = feature.get('properties', {})
        farm_id = props.get('farm_id')
        value = props.get('mean') # خروجی reduceRegions با Reducer.mean()
        if farm_id is not None and value is not None and farm_id in valid_farm_ids: # فقط مزارع با هندسه معتبر
            ranking_data[farm_id] = value
        # else:
            # print(f"هشدار: دریافت مقدار رتبه‌بندی برای مزرعه {farm_id} ناموفق بود یا هندسه نامعتبر داشت.")

    # اضافه کردن مزارعی که هندسه معتبر داشتند ولی در reduceRegions مقداری نگرفتند (مقدار NaN)
    for farm_id in valid_farm_ids:
        if farm_id not in ranking_data:
            ranking_data[farm_id] = None # یا pd.NA

    if not ranking_data:
         # st.warning("هیچ داده‌ای برای رتبه‌بندی پس از پردازش GEE استخراج نشد.", icon="📊")
         return pd.DataFrame(columns=['مزرعه', index_name])

    # 8. ایجاد دیتافریم و مرتب‌سازی
    ranking_df = pd.DataFrame(list(ranking_data.items()), columns=['مزرعه', index_name])

    # مرتب‌سازی: معمولا مقادیر بالاتر بهتر است، به جز برای شاخص‌هایی مثل MSI
    ascending_sort = False # پیش‌فرض: نزولی (مقدار بیشتر بهتر)
    if index_name in ['MSI']: # برای MSI، مقدار کمتر بهتر است
        ascending_sort = True

    # مرتب‌سازی با قرار دادن NaNها در انتها
    ranking_df = ranking_df.sort_values(by=index_name, ascending=ascending_sort, na_position='last')
    # اضافه کردن ستون رتبه (فقط برای مقادیر غیر NaN)
    ranking_df['رتبه'] = ranking_df[index_name].rank(method='first', ascending=ascending_sort).astype('Int64') # نوع عدد صحیح قابل تهی

    # جابجایی ستون رتبه به اول
    ranking_df = ranking_df[['رتبه', 'مزرعه', index_name]]

    return ranking_df


# --- اجرای برنامه Streamlit ---
st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(APP_TITLE)

# ۱. اتصال به GEE
gee_initialized = initialize_gee()

# فقط در صورت اتصال موفق به GEE ادامه بده
if gee_initialized:
    # ۲. بارگذاری داده‌های CSV
    df = load_data(CSV_FILE_PATH)

    if df is None or df.empty:
        st.error("بارگذاری داده‌های مزارع ناموفق بود یا فایل خالی است.")
        st.stop()

    # --- نوار کناری (Sidebar) ---
    st.sidebar.header("تنظیمات نمایش")

    # انتخابگر بازه زمانی
    today = datetime.date.today()
    default_end_date = today
    default_start_date = default_end_date - datetime.timedelta(days=7) # پیش‌فرض: ۷ روز گذشته
    start_date = st.sidebar.date_input("تاریخ شروع", value=default_start_date, max_value=default_end_date)
    end_date = st.sidebar.date_input("تاریخ پایان", value=default_end_date, min_value=start_date, max_value=default_end_date)

    if start_date > end_date:
        st.sidebar.error("تاریخ شروع نمی‌تواند بعد از تاریخ پایان باشد.")
        st.stop()

    # فیلتر بر اساس روز هفته
    available_days = ["همه روزها"] + sorted(df['روزهای هفته'].unique().tolist())
    selected_day = st.sidebar.selectbox("فیلتر بر اساس روز هفته", options=available_days, help="این فیلتر روی لیست مزارع قابل انتخاب و جدول رتبه‌بندی تاثیر می‌گذارد.")

    # فیلتر کردن دیتافریم بر اساس روز هفته انتخابی
    if selected_day == "همه روزها":
        filtered_df_day = df.copy()
    else:
        filtered_df_day = df[df['روزهای هفته'] == selected_day].copy()

    # انتخاب مزرعه
    farm_list = ["همه مزارع"] + sorted(filtered_df_day['مزرعه'].unique().tolist())
    if len(farm_list) == 1 and selected_day != "همه روزها": # فقط گزینه "همه مزارع" مانده
         st.sidebar.warning(f"هیچ مزرعه‌ای برای روز '{selected_day}' یافت نشد. لطفاً 'همه روزها' را انتخاب کنید یا روز دیگری را امتحان کنید.", icon="⚠️")
         # اجازه می‌دهیم 'همه مزارع' انتخاب شود، اما filtered_df_day خالی خواهد بود
         farm_list = ["همه مزارع"] + sorted(df['مزرعه'].unique().tolist()) # نمایش همه مزارع در لیست اصلی

    selected_farm = st.sidebar.selectbox("انتخاب مزرعه", options=farm_list)

    # انتخاب شاخص
    available_indices = list(INDEX_FUNCTIONS.keys())
    selected_index = st.sidebar.selectbox("انتخاب شاخص", options=available_indices)

    # انتخاب سنسور
    selected_sensor = st.sidebar.radio("انتخاب سنسور ماهواره", ('Sentinel-2', 'Landsat'), index=0, key='sensor_select', help="Sentinel-2 رزولوشن بالاتر و باند RedEdge دارد. Landsat بازه زمانی طولانی‌تری را پوشش می‌دهد.")

    # --- پنل اصلی ---
    col1, col2 = st.columns([3, 1.5]) # نسبت عرض ستون‌ها

    with col1:
        st.subheader(f"نقشه وضعیت شاخص '{selected_index}'")
        map_placeholder = st.empty() # Placeholder برای نقشه

        # --- منطق نمایش نقشه ---
        display_geom = None # هندسه برای دریافت داده GEE
        target_object_for_map = None # شیء GEE برای مرکز نقشه
        zoom_level = INITIAL_ZOOM
        # دیتافریم برای استفاده در نقشه (مارکرها و تعیین محدوده)
        map_df = filtered_df_day if selected_farm == "همه مزارع" else df[df['مزرعه'] == selected_farm] # اگر تک مزرعه است، از df اصلی برداریم

        # تعیین هندسه و هدف نقشه
        if selected_farm == "همه مزارع":
            if not map_df.empty:
                 try:
                     min_lon, min_lat = map_df['طول جغرافیایی'].min(), map_df['عرض جغرافیایی'].min()
                     max_lon, max_lat = map_df['طول جغرافیایی'].max(), map_df['عرض جغرافیایی'].max()
                     if pd.notna(min_lon) and pd.notna(min_lat) and pd.notna(max_lon) and pd.notna(max_lat):
                         display_geom = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
                         target_object_for_map = display_geom
                         zoom_level = INITIAL_ZOOM
                     else:
                         st.warning("مختصات معتبری برای تعیین محدوده مزارع (همه مزارع) یافت نشد.", icon="🗺️")
                 except Exception as e:
                      st.warning(f"خطا در تعیین محدوده مزارع (همه مزارع): {e}", icon="🗺️")
            else:
                 st.info(f"هیچ مزرعه‌ای برای نمایش با فیلتر روز '{selected_day}' یافت نشد.")
                 target_object_for_map = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT]) # مرکز پیش‌فرض
                 zoom_level = INITIAL_ZOOM -1

        else: # تک مزرعه
            if not map_df.empty:
                 farm_info_row = map_df.iloc[0]
                 farm_lat = farm_info_row['عرض جغرافیایی']
                 farm_lon = farm_info_row['طول جغرافیایی']
                 if pd.notna(farm_lat) and pd.notna(farm_lon):
                     farm_point = ee.Geometry.Point([farm_lon, farm_lat])
                     display_geom = farm_point.buffer(200) # بافر برای نمایش لایه
                     target_object_for_map = farm_point # مرکز روی نقطه
                     zoom_level = INITIAL_ZOOM + 3
                 else:
                      st.warning(f"مختصات نامعتبر برای مزرعه {selected_farm}. امکان نمایش لایه شاخص وجود ندارد.", icon="📍")
                      target_object_for_map = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT])
            else:
                 st.warning(f"اطلاعات مزرعه {selected_farm} یافت نشد.", icon="❓")
                 target_object_for_map = ee.Geometry.Point([INITIAL_LON, INITIAL_LAT])

        # --- دریافت و نمایش لایه شاخص ---
        gee_layer_added = False
        layer_image_for_download = None # برای دکمه دانلود
        vis_params = None # برای دکمه دانلود

        if display_geom:
            with st.spinner(f"در حال پردازش تصویر '{selected_index}' برای منطقه/مزرعه با سنسور {selected_sensor}..."):
                 collection = get_image_collection(start_date, end_date, display_geom, selected_sensor)

                 if collection and collection.size().getInfo() > 0:
                    index_func_detail = INDEX_FUNCTIONS.get(selected_index)
                    bands_ok = True
                    try:
                        first_image_bands = ee.Image(collection.first()).bandNames().getInfo()
                        if index_func_detail.get('requires_blue') and 'Blue' not in first_image_bands: bands_ok = False
                        if index_func_detail.get('requires_swir1') and 'SWIR1' not in first_image_bands: bands_ok = False
                        if index_func_detail.get('requires_rededge') and sensor != 'Sentinel-2': pass
                    except Exception: bands_ok = False

                    if index_func_detail and bands_ok:
                         def calculate_selected_index_map(image):
                             try:
                                 calc_img = index_func_detail['func'](image)
                                 if selected_index in calc_img.bandNames().getInfo():
                                     return calc_img.select(selected_index).copyProperties(image, ["system:time_start"])
                                 else: return ee.Image().rename(selected_index).updateMask(ee.Image(0)).set('system:time_start', image.get('system:time_start'))
                             except Exception: return ee.Image().set('system:time_start', image.get('system:time_start'))

                         indexed_collection = collection.map(calculate_selected_index_map)

                         try:
                             median_image = indexed_collection.select(selected_index).median()
                             if selected_index in median_image.bandNames().getInfo():
                                 layer_image = median_image.clip(display_geom) # برش به هندسه
                                 vis_params = index_func_detail.get('vis')
                                 if not vis_params: vis_params = {'min': 0, 'max': 1, 'palette': ['white', 'gray']}

                                 # --- مقداردهی اولیه نقشه ---
                                 m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
                                 m.add_basemap('HYBRID')

                                 # افزودن لایه GEE
                                 try:
                                     m.addLayer(layer_image, vis_params, f'{selected_index} ({selected_sensor} - Median)')
                                     layer_image_for_download = layer_image # ذخیره برای دانلود
                                     gee_layer_added = True
                                     # افزودن لجند (راهنمای رنگ)
                                     try: m.add_colorbar(vis_params, label=selected_index, layer_name=f'{selected_index} ({selected_sensor} - Median)')
                                     except Exception as legend_e: print(f"امکان افزودن لجند وجود نداشت: {legend_e}")
                                 except Exception as addlayer_e: st.error(f"خطا در افزودن لایه GEE به نقشه: {addlayer_e}")

                             else: st.warning(f"باند شاخص '{selected_index}' در تصویر میانه پس از محاسبه یافت نشد.", icon="⚠️")
                         except ee.EEException as median_e: st.error(f"خطا در محاسبه تصویر میانه: {median_e}")
                    else:
                        if not index_func_detail: st.error(f"تعریف شاخص {selected_index} یافت نشد.")
                        elif not bands_ok: st.warning(f"نمایش نقشه {selected_index} با سنسور {selected_sensor} ممکن نیست: باندهای لازم موجود نیستند.", icon="✖️")

                 else:
                    st.info(f"هیچ تصویر ماهواره‌ای مناسبی با سنسور {selected_sensor} برای دوره و منطقه انتخابی جهت نمایش نقشه یافت نشد.", icon="🛰️☁️")

        # --- ایجاد نقشه پایه اگر لایه GEE اضافه نشد ---
        if not gee_layer_added:
             m = geemap.Map(center=[INITIAL_LAT, INITIAL_LON], zoom=INITIAL_ZOOM, add_google_map=False)
             m.add_basemap('HYBRID')
             if not display_geom: st.info("لطفا یک مزرعه یا روزی با مزارع فعال انتخاب کنید تا نقشه نمایش داده شود.")

        # --- افزودن مارکرها به نقشه ---
        # استفاده از map_df که بر اساس selected_farm تعیین شده
        try:
            if not map_df.empty:
                 for idx, row in map_df.iterrows():
                      if pd.notna(row['عرض جغرافیایی']) and pd.notna(row['طول جغرافیایی']):
                           # استفاده از نام ستون‌های پاک شده ('سن' به جای 'سن ')
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
                           icon_color = 'red' if selected_farm != "همه مزارع" else 'blue'
                           icon_type = 'star' if selected_farm != "همه مزارع" else 'info-sign'
                           folium.Marker(
                               location=[row['عرض جغرافیایی'], row['طول جغرافیایی']],
                               popup=folium.Popup(popup_html, max_width=300),
                               tooltip=f"مزرعه {row['مزرعه']}",
                               icon=folium.Icon(color=icon_color, icon=icon_type)
                           ).add_to(m)

        except Exception as marker_e:
             st.warning(f"خطا در افزودن مارکرها به نقشه: {marker_e}", icon="⚠️")


        # --- مرکز نقشه ---
        if target_object_for_map:
            try: m.center_object(target_object_for_map, zoom=zoom_level)
            except Exception as center_e: print(f"خطا در مرکز کردن نقشه: {center_e}")

        # --- نمایش نقشه در Streamlit ---
        with map_placeholder:
             try: m.to_streamlit(height=550)
             except Exception as map_render_e: st.error(f"خطا در نمایش نقشه Folium: {map_render_e}")

        # --- دکمه دانلود تصویر نقشه (خارج از with map_placeholder) ---
        if gee_layer_added and layer_image_for_download and vis_params and display_geom:
            try:
                thumb_url = layer_image_for_download.getThumbURL({
                    'region': display_geom.geometry().bounds().toGeoJson(),
                    'bands': selected_index,
                    'palette': vis_params['palette'],
                    'min': vis_params['min'],
                    'max': vis_params['max'],
                    'dimensions': 512
                })
                response = requests.get(thumb_url, stream=True)
                if response.status_code == 200:
                    img_bytes = BytesIO(response.content)
                    st.sidebar.download_button(
                        label=f"دانلود نقشه ({selected_index})",
                        data=img_bytes,
                        file_name=f"map_{selected_farm.replace(' ', '_') if selected_farm != 'همه مزارع' else 'all'}_{selected_index}.png",
                        mime="image/png",
                        key=f"download_map_{selected_index}"
                    )
                # else: print(f"ایجاد لینک دانلود نقشه ناموفق (وضعیت: {response.status_code}).")
            except Exception as thumb_e: print(f"خطای GEE/غیرمنتظره در ایجاد لینک دانلود نقشه: {thumb_e}")


    with col2:
        # --- نمایش جزئیات، نمودار یا رتبه‌بندی ---
        # استفاده از filtered_df_day برای رتبه‌بندی و df اصلی برای جزئیات تک مزرعه

        if selected_farm != "همه مزارع":
            # نمایش جزئیات و نمودار برای تک مزرعه
            st.subheader(f"جزئیات مزرعه: {selected_farm}")
            # پیدا کردن اطلاعات مزرعه از df اصلی (چون ممکن است در روز فیلتر شده نباشد)
            farm_info_row_detail = df[df['مزرعه'] == selected_farm].iloc[0] if not df[df['مزرعه'] == selected_farm].empty else None

            if farm_info_row_detail is not None:
                # نمایش جزئیات با st.metric (استفاده از نام ستون‌های پاک شده)
                details_cols = st.columns(2)
                with details_cols[0]:
                    st.metric("کانال", str(farm_info_row_detail['کانال']))
                    st.metric("مساحت داشت", f"{farm_info_row_detail['مساحت داشت']:.2f} هکتار" if pd.notna(farm_info_row_detail['مساحت داشت']) else "نامشخص")
                    st.metric("سن", str(farm_info_row_detail['سن'])) # 'سن' بدون فاصله
                with details_cols[1]:
                    st.metric("اداره", str(farm_info_row_detail['اداره']))
                    st.metric("واریته", str(farm_info_row_detail['واریته']))
                    st.metric("روز آبیاری", str(farm_info_row_detail['روزهای هفته']))

                # نمایش نمودار سری زمانی
                st.subheader(f"روند شاخص '{selected_index}'")
                if pd.notna(farm_info_row_detail['عرض جغرافیایی']) and pd.notna(farm_info_row_detail['طول جغرافیایی']):
                    with st.spinner(f"در حال دریافت سری زمانی {selected_index} برای مزرعه {selected_farm}..."):
                        try:
                            farm_geom = ee.Geometry.Point([farm_info_row_detail['طول جغرافیایی'], farm_info_row_detail['عرض جغرافیایی']])
                            ts_df = get_timeseries_for_farm(farm_geom.toGeoJsonString(), start_date, end_date, selected_index, selected_sensor)

                            if ts_df is not None and not ts_df.empty:
                                fig = px.line(ts_df, x='Date', y=selected_index,
                                              title=f"روند زمانی {selected_index} برای {selected_farm}", markers=True,
                                              labels={'Date': 'تاریخ', selected_index: selected_index})
                                fig.update_layout(xaxis_title="تاریخ", yaxis_title=selected_index)
                                st.plotly_chart(fig, use_container_width=True)
                            elif ts_df is not None:
                                st.info(f"داده‌ای برای نمایش نمودار روند زمانی {selected_index} در بازه انتخابی یافت نشد.", icon="📉")
                            # اگر ts_df is None بود، پیام خطا قبلا داده شده
                        except Exception as ts_e: st.error(f"خطای غیرمنتظره هنگام دریافت یا نمایش سری زمانی: {ts_e}")
                else: st.warning("مختصات جغرافیایی معتبری برای این مزرعه جهت دریافت سری زمانی ثبت نشده است.", icon="📍")
            else: st.info(f"اطلاعات مزرعه '{selected_farm}' یافت نشد.")

        else: # "همه مزارع" انتخاب شده است
            # نمایش جدول رتبه‌بندی
            st.subheader(f"رتبه‌بندی مزارع بر اساس '{selected_index}'")
            st.info(f"نمایش مقدار متوسط شاخص '{selected_index}' ({selected_sensor}) در بازه {start_date.strftime('%Y-%m-%d')} تا {end_date.strftime('%Y-%m-%d')} برای مزارع فعال در روز '{selected_day}'.")

            if not filtered_df_day.empty: # استفاده از دیتافریم فیلتر شده بر اساس روز
                 with st.spinner(f"در حال محاسبه رتبه‌بندی مزارع بر اساس {selected_index}..."):
                    try:
                        # ارسال دیتافریم فیلتر شده به صورت JSON برای کش شدن
                        ranking_df = get_latest_index_for_ranking(filtered_df_day.to_json(), selected_day, start_date, end_date, selected_index, selected_sensor)

                        if ranking_df is not None and not ranking_df.empty:
                            # نمایش جدول با فرمت بهتر و پنهان کردن ایندکس
                            st.dataframe(ranking_df.style.format({'رتبه': "{:}", 'مزرعه': "{:}", selected_index: "{:.3f}"}).hide(axis="index"), use_container_width=True)

                            # دکمه دانلود جدول رتبه‌بندی
                            csv = ranking_df.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                               label=f"دانلود جدول رتبه‌بندی ({selected_index})",
                               data=csv,
                               file_name=f'ranking_{selected_index}_{selected_day}_{start_date}_{end_date}.csv',
                               mime='text/csv',
                               key='download_ranking_csv'
                             )
                        elif ranking_df is not None:
                             st.warning("اطلاعاتی برای رتبه‌بندی مزارع با فیلترهای انتخابی یافت نشد.", icon="📊")
                        # اگر ranking_df is None بود، پیام خطا قبلا داده شده
                    except Exception as rank_e: st.error(f"خطای غیرمنتظره هنگام دریافت یا نمایش رتبه‌بندی: {rank_e}")
            else:
                st.info(f"هیچ مزرعه‌ای برای رتبه‌بندی در روز '{selected_day}' یافت نشد.")

else:
    st.warning("لطفاً منتظر بمانید تا اتصال به Google Earth Engine برقرار شود یا خطاهای نمایش داده شده در بالا را بررسی کنید.", icon="⏳")

# --- فوتر یا توضیحات اضافی ---
st.sidebar.markdown("---")
st.sidebar.info("راهنما: از منوهای بالا برای انتخاب بازه زمانی، روز هفته، مزرعه، شاخص و سنسور ماهواره‌ای استفاده کنید.")
# نمایش سنسور فعال در صورت اتصال موفق
if gee_initialized:
    st.sidebar.markdown(f"**سنسور فعال:** {selected_sensor}")
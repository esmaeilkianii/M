import streamlit as st
import geemap
import ee
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import datetime
from google.oauth2 import service_account
import folium
import uuid

# تنظیم عنوان و توضیحات داشبورد
st.title('داشبورد مانیتورینگ مزارع نیشکر دهخدا')
st.write('این داشبورد برای مانیتورینگ هفتگی وضعیت مزارع نیشکر شرکت دهخدا طراحی شده است. با استفاده از تصاویر ماهواره‌ای Sentinel-2، شاخص‌های کشاورزی محاسبه و نمایش داده می‌شوند.')

# احراز هویت Google Earth Engine
key_file = 'ee-esmaeilkiani13877-cfdea6eaf411 (4).json'
email = 'dehkhodamap-e9f0da4ce9f6514021@ee-esmaeilkiani13877.iam.gserviceaccount.com'
credentials = ee.ServiceAccountCredentials(email, key_file)
ee.Initialize(credentials)

# بارگذاری داده‌های مزارع از فایل CSV
farms_df = pd.read_csv('output (1).csv', encoding='utf-8')

# فیلتر مزارعی که مختصات گمشده ندارند
farms_df = farms_df[farms_df['coordinates_missing'] == 0]

# منوی کشویی برای انتخاب روز هفته
days = farms_df['روزهای هفته'].unique().tolist()
selected_day = st.sidebar.selectbox('انتخاب روز هفته', days)

# فیلتر مزارع بر اساس روز هفته
filtered_farms = farms_df[farms_df['روزهای هفته'] == selected_day]
farm_names = filtered_farms['مزرعه'].tolist()
selected_farm = st.sidebar.selectbox('انتخاب مزرعه', farm_names)

# انتخاب تاریخ برای نمایش داده‌ها
selected_date = st.sidebar.date_input('انتخاب تاریخ', value=datetime.date.today())
start_date = (selected_date - datetime.timedelta(days=5)).strftime('%Y-%m-%d')
end_date = (selected_date + datetime.timedelta(days=5)).strftime('%Y-%m-%d')

# نمایش اطلاعات مزرعه انتخاب‌شده
farm_data = filtered_farms[filtered_farms['مزرعه'] == selected_farm].iloc[0]
st.write(f"**نام مزرعه:** {farm_data['مزرعه']}")
st.write(f"**کانال:** {farm_data['کانال']}")
st.write(f"**اداره:** {farm_data['اداره']}")
st.write(f"**مساحت داشت:** {farm_data['مساحت داشت']} هکتار")
st.write(f"**واریته:** {farm_data['واریته']}")
st.write(f"**سن:** {farm_data['سن']} ماه")
st.write(f"**مختصات:** ({farm_data['عرض جغرافیایی']}, {farm_data['طول جغرافیایی']})")

# تعریف منطقه جغرافیایی برای نمایش نقشه
region = ee.Geometry.Rectangle([48.724416 - 0.5, 31.534442 - 0.5, 48.724416 + 0.5, 31.534442 + 0.5])

# فیلتر تصاویر Sentinel-2
collection = ee.ImageCollection('COPERNICUS/S2') \
    .filterDate(start_date, end_date) \
    .filterBounds(region) \
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20)) \
    .sort('CLOUDY_PIXEL_PERCENTAGE')

# بررسی وجود تصاویر
if collection.size().getInfo() == 0:
    st.warning('هیچ تصویری برای بازه زمانی انتخاب‌شده یافت نشد.')
else:
    image = collection.median()

    # اعمال ماسک ابر
    scl = image.select('SCL')
    cloud_mask = scl.eq(8).Or(scl.eq(9)).Or(scl.eq(10)).Or(scl.eq(3))
    image = image.updateMask(cloud_mask.Not())

    # محاسبه شاخص‌های کشاورزی
    ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
    evi = image.expression(
        '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
        {
            'NIR': image.select('B8'),
            'RED': image.select('B4'),
            'BLUE': image.select('B2')
        }
    ).rename('EVI')
    ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
    msi = image.select('B11').divide(image.select('B8')).rename('MSI')
    cigreen = image.select('B8').divide(image.select('B3')).subtract(1).rename('CIgreen')

    # طبقه‌بندی NDVI برای نمایش
    ndvi_class = ee.Image(0).where(ndvi.lt(0.3), 1).where(ndvi.gte(0.3).And(ndvi.lt(0.6)), 2).where(ndvi.gte(0.6), 3)
    ndvi_class_vis = {
        'min': 1,
        'max': 3,
        'palette': ['red', 'yellow', 'green']
    }

    # ایجاد نقشه با geemap
    Map = geemap.Map(center=[31.534442, 48.724416], zoom=10)
    Map.addLayer(image, {'bands': ['B4', 'B3', 'B2'], 'min': 0, 'max': 3000}, 'رنگ واقعی')
    Map.addLayer(ndvi_class, ndvi_class_vis, 'طبقه‌بندی NDVI')

    # افزودن نشانگر برای مزرعه انتخاب‌شده
    lat = farm_data['عرض جغرافیایی']
    lon = farm_data['طول جغرافیایی']
    marker = folium.Marker([lat, lon], popup=selected_farm)
    Map.add_child(marker)

    # نمایش نقشه در Streamlit
    st.write(Map.to_streamlit(height=600))

    # نمودارهای زمانی
    farm_point = ee.Geometry.Point([farm_data['طول جغرافیایی'], farm_data['عرض جغرافیایی']])
    farm_area = farm_point.buffer(300)
    past_year_start = (selected_date - datetime.timedelta(days=365)).strftime('%Y-%m-%d')
    collection_year = ee.ImageCollection('COPERNICUS/S2') \
        .filterDate(past_year_start, end_date) \
        .filterBounds(farm_area)

    def compute_ndvi(image):
        scl = image.select('SCL')
        cloud_mask = scl.eq(8).Or(scl.eq(9)).Or(scl.eq(10)).Or(scl.eq(3))
        image = image.updateMask(cloud_mask.Not())
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        return ndvi.set('system:time_start', image.get('system:time_start'))

    ndvi_collection = collection_year.map(compute_ndvi)
    def get_mean(image):
        mean = image.reduceRegion(reducer=ee.Reducer.mean(), geometry=farm_area, scale=10).get('NDVI')
        return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd'), 'NDVI': mean})

    time_series = ndvi_collection.map(get_mean).filter(ee.Filter.notNull(['NDVI']))
    time_series_list = time_series.getInfo()['features']
    dates = [feature['properties']['date'] for feature in time_series_list]
    ndvi_values = [feature['properties']['NDVI'] for feature in time_series_list]

    # رسم نمودار
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, ndvi_values, marker='o')
    ax.set_xlabel('تاریخ')
    ax.set_ylabel('NDVI')
    ax.set_title(f'روند NDVI برای مزرعه {selected_farm}')
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)

    # جدول رتبه‌بندی مزارع
    past_seven_start = (selected_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    collection_seven = ee.ImageCollection('COPERNICUS/S2') \
        .filterDate(past_seven_start, end_date) \
        .filterBounds(region)
    if collection_seven.size().getInfo() > 0:
        image_seven = collection_seven.median()
        scl_seven = image_seven.select('SCL')
        cloud_mask_seven = scl_seven.eq(8).Or(scl_seven.eq(9)).Or(scl_seven.eq(10)).Or(scl_seven.eq(3))
        image_seven = image_seven.updateMask(cloud_mask_seven.Not())
        ndvi_seven = image_seven.normalizedDifference(['B8', 'B4']).rename('NDVI')

        farm_geometries = []
        for index, row in farms_df.iterrows():
            point = ee.Geometry.Point([row['طول جغرافیایی'], row['عرض جغرافیایی']])
            area = point.buffer(300)
            farm_geometries.append({'name': row['مزرعه'], 'geometry': area})

        means = []
        for farm in farm_geometries:
            mean = ndvi_seven.reduceRegion(reducer=ee.Reducer.mean(), geometry=farm['geometry'], scale=10).get('NDVI')
            mean_value = mean.getInfo() if mean.getInfo() is not None else np.nan
            means.append({'مزرعه': farm['name'], 'NDVI': mean_value})

        means_df = pd.DataFrame(means)
        means_df = means_df.dropna().sort_values('NDVI', ascending=False)
        st.subheader('جدول رتبه‌بندی مزارع بر اساس NDVI')
        st.write(means_df)

    # مقایسه تغییرات هفتگی
    period1_start = (selected_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')
    period1_end = selected_date.strftime('%Y-%m-%d')
    period2_start = (selected_date - datetime.timedelta(days=14)).strftime('%Y-%m-%d')
    period2_end = (selected_date - datetime.timedelta(days=7)).strftime('%Y-%m-%d')

    collection_period1 = ee.ImageCollection('COPERNICUS/S2') \
        .filterDate(period1_start, period1_end) \
        .filterBounds(region)
    collection_period2 = ee.ImageCollection('COPERNICUS/S2') \
        .filterDate(period2_start, period2_end) \
        .filterBounds(region)

    changes = []
    if collection_period1.size().getInfo() > 0 and collection_period2.size().getInfo() > 0:
        image_period1 = collection_period1.median()
        image_period1 = image_period1.updateMask(image_period1.select('SCL').eq(8).Or(image_period1.select('SCL').eq(9)).Or(image_period1.select('SCL').eq(10)).Or(image_period1.select('SCL').eq(3)).Not())
        ndvi_period1 = image_period1.normalizedDifference(['B8', 'B4']).rename('NDVI')

        image_period2 = collection_period2.median()
        image_period2 = image_period2.updateMask(image_period2.select('SCL').eq(8).Or(image_period2.select('SCL').eq(9)).Or(image_period2.select('SCL').eq(10)).Or(image_period2.select('SCL').eq(3)).Not())
        ndvi_period2 = image_period2.normalizedDifference(['B8', 'B4']).rename('NDVI')

        for farm in farm_geometries:
            mean1 = ndvi_period1.reduceRegion(reducer=ee.Reducer.mean(), geometry=farm['geometry'], scale=10).get('NDVI').getInfo()
            mean2 = ndvi_period2.reduceRegion(reducer=ee.Reducer.mean(), geometry=farm['geometry'], scale=10).get('NDVI').getInfo()
            if mean1 is not None and mean2 is not None:
                change = mean1 - mean2
                changes.append({'مزرعه': farm['name'], 'تغییر NDVI': change})

        changes_df = pd.DataFrame(changes)
        significant = changes_df[abs(changes_df['تغییر NDVI']) > 0.1]
        st.subheader('تغییرات قابل‌توجه در NDVI')
        for index, row in significant.iterrows():
            if row['تغییر NDVI'] > 0:
                st.write(f"مزرعه {row['مزرعه']} در NDVI افزایش داشته است.")
            else:
                st.write(f"مزرعه {row['مزرعه']} در NDVI کاهش داشته است.")

    # دانلود نقشه‌ها
    vis_params = {'min': 0, 'max': 1, 'palette': ['red', 'yellow', 'green']}
    url = ndvi.getThumbURL({'region': region.toGeoJSONString(), 'dimensions': 512, 'format': 'png', **vis_params})
    st.markdown(f"[دانلود نقشه NDVI]({url})")
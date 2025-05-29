import pandas as pd
import numpy as np
from scipy.interpolate import interp1d
import plotly.graph_objects as go
from sklearn.ensemble import RandomForestRegressor

class ClimateBasedIrrigation:
    def __init__(self):
        self.rf_model = RandomForestRegressor(n_estimators=100)
        
    def calculate_water_requirement(self, temperature, humidity, wind_speed, solar_radiation):
        """Calculate daily water requirement using Penman-Monteith equation"""
        # Constants
        albedo = 0.23
        lat_heat_vap = 2.45  # MJ/kg
        psychro_const = 0.067  # kPa/°C
        
        # Calculate vapor pressure deficit
        sat_vapor_press = 0.6108 * np.exp(17.27 * temperature / (temperature + 237.3))
        actual_vapor_press = sat_vapor_press * humidity / 100
        vapor_press_deficit = sat_vapor_press - actual_vapor_press
        
        # Calculate net radiation
        net_radiation = (1 - albedo) * solar_radiation
        
        # Calculate ET0 (reference evapotranspiration)
        numerator = 0.408 * net_radiation + psychro_const * (900 / (temperature + 273)) * wind_speed * vapor_press_deficit
        denominator = 1 + psychro_const * (1 + 0.34 * wind_speed)
        et0 = numerator / denominator
        
        return et0
    
    def optimize_irrigation_schedule(self, climate_data, soil_moisture, crop_coefficient):
        """Optimize irrigation schedule based on climate and soil conditions"""
        # Calculate daily water requirements
        daily_requirements = []
        for idx, row in climate_data.iterrows():
            et0 = self.calculate_water_requirement(
                row['temperature'],
                row['humidity'],
                row['wind_speed'],
                row['solar_radiation']
            )
            daily_requirements.append(et0 * crop_coefficient)
        
        # Optimize schedule using soil moisture thresholds
        schedule = self._generate_schedule(daily_requirements, soil_moisture)
        return schedule
    
    def _generate_schedule(self, requirements, soil_moisture):
        """Generate optimized irrigation schedule"""
        schedule = []
        current_moisture = soil_moisture
        
        for daily_req in requirements:
            if current_moisture - daily_req < 0.4:  # Critical threshold
                irrigation_amount = 1.2 * daily_req  # Add 20% buffer
                schedule.append({
                    'irrigation_needed': True,
                    'amount': irrigation_amount,
                    'priority': 'High'
                })
                current_moisture = 1.0  # Reset to field capacity
            else:
                schedule.append({
                    'irrigation_needed': False,
                    'amount': 0,
                    'priority': 'Low'
                })
                current_moisture -= daily_req
        
        return schedule
    
    def visualize_schedule(self, schedule, climate_data):
        """Create interactive visualization of irrigation schedule"""
        fig = go.Figure()
        
        # Add irrigation amounts
        fig.add_trace(go.Bar(
            x=climate_data.index,
            y=[s['amount'] if s['irrigation_needed'] else 0 for s in schedule],
            name='مقدار آبیاری',
            marker_color='blue'
        ))
        
        # Add soil moisture line
        fig.add_trace(go.Scatter(
            x=climate_data.index,
            y=[0.4] * len(climate_data),  # Critical threshold line
            name='حد بحرانی رطوبت خاک',
            line=dict(color='red', dash='dash')
        ))
        
        fig.update_layout(
            title='برنامه بهینه آبیاری',
            xaxis_title='تاریخ',
            yaxis_title='مقدار آب (میلی‌متر)',
            barmode='overlay'
        )
        
        return fig
    
    def generate_irrigation_report(self, schedule, climate_data):
        """Generate comprehensive irrigation report"""
        total_water = sum(s['amount'] for s in schedule if s['irrigation_needed'])
        high_priority_days = sum(1 for s in schedule if s['priority'] == 'High')
        
        report = {
            'total_water_required': total_water,
            'irrigation_days': high_priority_days,
            'average_daily_requirement': total_water / len(schedule),
            'recommendations': self._generate_irrigation_recommendations(schedule, climate_data)
        }
        
        return report
    
    def _generate_irrigation_recommendations(self, schedule, climate_data):
        """Generate specific irrigation recommendations"""
        recommendations = []
        
        # Analyze patterns
        high_priority_periods = [i for i, s in enumerate(schedule) if s['priority'] == 'High']
        
        if len(high_priority_periods) > 0:
            recommendations.append(
                f"نیاز به آبیاری در {len(high_priority_periods)} روز آینده"
            )
            
            # Check for consecutive high priority days
            consecutive_days = self._find_consecutive_days(high_priority_periods)
            if consecutive_days > 2:
                recommendations.append(
                    f"توصیه به افزایش حجم آبیاری در {consecutive_days} روز متوالی"
                )
        
        return recommendations
    
    def _find_consecutive_days(self, days):
        """Find longest sequence of consecutive days"""
        if not days:
            return 0
        
        max_consecutive = current_consecutive = 1
        for i in range(1, len(days)):
            if days[i] == days[i-1] + 1:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 1
        
        return max_consecutive
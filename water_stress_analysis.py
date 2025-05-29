import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import DBSCAN
from scipy import stats
import plotly.express as px
import plotly.graph_objects as go

class WaterStressAnalyzer:
    def __init__(self):
        self.scaler = StandardScaler()
        
    def analyze_water_stress(self, ndvi_data, et_data, soil_moisture=None):
        """Analyze water stress using multiple indicators"""
        # Normalize data
        normalized_ndvi = self.scaler.fit_transform(ndvi_data.reshape(-1, 1))
        normalized_et = self.scaler.fit_transform(et_data.reshape(-1, 1))
        
        # Calculate water stress index
        wsi = 1 - (normalized_et / normalized_ndvi)
        
        # Identify stress clusters using DBSCAN
        clustering = DBSCAN(eps=0.3, min_samples=3).fit(wsi.reshape(-1, 1))
        
        return {
            'water_stress_index': wsi,
            'stress_clusters': clustering.labels_,
            'stress_severity': self._calculate_stress_severity(wsi)
        }
    
    def _calculate_stress_severity(self, wsi):
        """Calculate stress severity levels"""
        thresholds = {
            'severe': np.percentile(wsi, 90),
            'moderate': np.percentile(wsi, 75),
            'mild': np.percentile(wsi, 50)
        }
        return thresholds

    def visualize_stress_map(self, coordinates, stress_data):
        """Create an interactive stress map"""
        fig = go.Figure(data=go.Scattermapbox(
            lat=coordinates[:, 0],
            lon=coordinates[:, 1],
            mode='markers',
            marker=dict(
                size=10,
                color=stress_data,
                colorscale='RdYlBu_r',
                showscale=True
            ),
            text=['Stress Level: {:.2f}'.format(s) for s in stress_data]
        ))
        
        fig.update_layout(
            mapbox_style="carto-positron",
            mapbox=dict(
                zoom=10,
                center=dict(
                    lat=np.mean(coordinates[:, 0]),
                    lon=np.mean(coordinates[:, 1])
                )
            )
        )
        
        return fig

    def generate_stress_report(self, farm_data, stress_analysis):
        """Generate a comprehensive water stress report"""
        report = {
            'summary': {
                'total_area_affected': np.sum(stress_analysis['water_stress_index'] > 0.5),
                'average_stress_level': np.mean(stress_analysis['water_stress_index']),
                'high_risk_zones': np.sum(stress_analysis['stress_clusters'] == -1)
            },
            'recommendations': self._generate_recommendations(stress_analysis)
        }
        return report
    
    def _generate_recommendations(self, stress_analysis):
        """Generate irrigation recommendations based on stress analysis"""
        wsi = stress_analysis['water_stress_index']
        recommendations = []
        
        if np.mean(wsi) > 0.7:
            recommendations.append("نیاز فوری به آبیاری در مناطق با تنش شدید")
        elif np.mean(wsi) > 0.5:
            recommendations.append("افزایش دور آبیاری در هفته آینده")
        else:
            recommendations.append("ادامه برنامه آبیاری فعلی")
            
        return recommendations
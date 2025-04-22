import numpy as np
import pandas as pd
from typing import Dict, Tuple, List, Optional
import ee

class SugarcaneAnalysis:
    def __init__(self):
        # Constants for sugarcane analysis
        self.NDVI_THRESHOLDS = {
            'poor': 0.3,
            'fair': 0.5,
            'good': 0.7,
            'excellent': 0.8
        }
        
        self.GROWTH_STAGES = {
            'initial': (0, 30),  # days after planting
            'vegetative': (31, 120),
            'grand_growth': (121, 240),
            'maturity': (241, 365)
        }
        
        self.WATER_REQUIREMENT = {
            'initial': 2.5,  # mm/day
            'vegetative': 5.0,
            'grand_growth': 7.5,
            'maturity': 4.0
        }

    def calculate_sugar_content(self, ndvi: float, age_days: int, temperature: float) -> float:
        """
        Calculate estimated sugar content based on NDVI, age, and temperature
        Returns sugar content as percentage
        """
        # Base sugar content calculation
        base_sugar = 0.5 * ndvi + 0.3 * (age_days / 365)
        
        # Temperature adjustment factor
        temp_factor = 1.0
        if temperature > 30:
            temp_factor = 0.9
        elif temperature < 20:
            temp_factor = 0.8
            
        return base_sugar * temp_factor * 100

    def estimate_yield(self, ndvi: float, age_days: int, area_hectares: float) -> float:
        """
        Estimate sugarcane yield in tons per hectare
        """
        # Get growth stage
        growth_stage = self._get_growth_stage(age_days)
        
        # Base yield calculation
        base_yield = 80 * ndvi  # tons/ha
        
        # Growth stage adjustment
        stage_factor = {
            'initial': 0.3,
            'vegetative': 0.6,
            'grand_growth': 1.0,
            'maturity': 0.9
        }
        
        adjusted_yield = base_yield * stage_factor[growth_stage]
        return adjusted_yield * area_hectares

    def calculate_water_requirement(self, age_days: int, et0: float) -> float:
        """
        Calculate daily water requirement based on growth stage and reference evapotranspiration
        """
        growth_stage = self._get_growth_stage(age_days)
        base_requirement = self.WATER_REQUIREMENT[growth_stage]
        return base_requirement * et0

    def detect_stress(self, ndvi: float, ndmi: float, msi: float) -> Dict[str, str]:
        """
        Detect various types of stress in sugarcane
        Returns dictionary with stress types and severity
        """
        stresses = {}
        
        # Water stress
        if msi > 1.5:
            stresses['water_stress'] = 'high'
        elif msi > 1.2:
            stresses['water_stress'] = 'moderate'
            
        # Nutrient stress
        if ndvi < 0.4:
            stresses['nutrient_stress'] = 'high'
        elif ndvi < 0.5:
            stresses['nutrient_stress'] = 'moderate'
            
        # Disease stress (using NDMI as indicator)
        if ndmi < -0.2:
            stresses['disease_stress'] = 'high'
        elif ndmi < -0.1:
            stresses['disease_stress'] = 'moderate'
            
        return stresses

    def calculate_growth_rate(self, current_ndvi: float, previous_ndvi: float, 
                            days_between: int) -> float:
        """
        Calculate daily growth rate based on NDVI change
        """
        if days_between == 0:
            return 0
        return (current_ndvi - previous_ndvi) / days_between

    def _get_growth_stage(self, age_days: int) -> str:
        """
        Determine growth stage based on days after planting
        """
        for stage, (start, end) in self.GROWTH_STAGES.items():
            if start <= age_days <= end:
                return stage
        return 'maturity'  # default to maturity if beyond defined stages

    def analyze_field_health(self, ndvi: float, ndmi: float, msi: float, 
                           age_days: int) -> Dict[str, any]:
        """
        Comprehensive field health analysis
        """
        health_status = {
            'growth_stage': self._get_growth_stage(age_days),
            'stresses': self.detect_stress(ndvi, ndmi, msi),
            'health_score': self._calculate_health_score(ndvi, ndmi, msi),
            'recommendations': self._generate_recommendations(ndvi, ndmi, msi, age_days)
        }
        return health_status

    def _calculate_health_score(self, ndvi: float, ndmi: float, msi: float) -> float:
        """
        Calculate overall health score (0-100)
        """
        # Normalize indices to 0-1 range
        ndvi_score = min(max(ndvi, 0), 1)
        ndmi_score = min(max((ndmi + 1) / 2, 0), 1)
        msi_score = min(max(1 - (msi / 2), 0), 1)
        
        # Weighted average
        return (ndvi_score * 0.4 + ndmi_score * 0.3 + msi_score * 0.3) * 100

    def _generate_recommendations(self, ndvi: float, ndmi: float, msi: float, 
                                age_days: int) -> List[str]:
        """
        Generate recommendations based on field conditions
        """
        recommendations = []
        growth_stage = self._get_growth_stage(age_days)
        
        # Water recommendations
        if msi > 1.2:
            recommendations.append("نیاز به آبیاری فوری")
        elif msi > 1.0:
            recommendations.append("برنامه‌ریزی برای آبیاری در روزهای آینده")
            
        # Nutrient recommendations
        if ndvi < 0.5:
            recommendations.append("نیاز به کوددهی")
            
        # Disease control
        if ndmi < -0.1:
            recommendations.append("بررسی وضعیت آفات و بیماری‌ها")
            
        # Growth stage specific recommendations
        if growth_stage == 'vegetative':
            recommendations.append("مطلوب برای کوددهی نیتروژن")
        elif growth_stage == 'maturity':
            recommendations.append("آماده برای برداشت")
            
        return recommendations

    def calculate_harvest_readiness(self, ndvi: float, age_days: int, 
                                  temperature: float) -> Dict[str, any]:
        """
        Calculate harvest readiness indicators
        """
        sugar_content = self.calculate_sugar_content(ndvi, age_days, temperature)
        
        readiness = {
            'sugar_content': sugar_content,
            'optimal_harvest': sugar_content >= 12.0,
            'harvest_window': self._calculate_harvest_window(age_days, sugar_content)
        }
        
        return readiness

    def _calculate_harvest_window(self, age_days: int, sugar_content: float) -> Dict[str, int]:
        """
        Calculate optimal harvest window
        """
        if sugar_content >= 12.0:
            return {
                'start_days': max(0, age_days - 7),
                'end_days': age_days + 14
            }
        return {
            'start_days': age_days + 7,
            'end_days': age_days + 30
        } 
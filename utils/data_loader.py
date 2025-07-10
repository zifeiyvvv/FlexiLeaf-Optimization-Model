import pandas as pd
import numpy as np

def load_weather_forecast(file_path):
    """加载气象预测数据"""
    df = pd.read_csv(file_path)
    # 处理数据：转换为光伏出力预测
    # 实际实现应包括辐照度到光伏出力的转换模型
    return df['pv_forecast'].values

def load_load_profile(file_path):
    """加载负荷曲线数据"""
    df = pd.read_csv(file_path)
    return df['load_kw'].values

def generate_sample_data(num_points=96):
    """生成样本数据用于测试"""
    # 光伏曲线 (白天有出力)
    pv = np.zeros(num_points)
    pv[20:60] = np.random.uniform(50, 150, 40)  # 5:00-15:00
    
    # 负荷曲线 (白天高，夜间低)
    load = np.random.normal(200, 50, num_points)
    load[:20] *= 0.5  # 0:00-5:00
    load[60:] *= 0.7  # 15:00-24:00
    
    return pv, load

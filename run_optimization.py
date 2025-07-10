import pandas as pd
from models.optimization_model import MicrogridOptimizer
from utils.data_loader import load_weather_forecast, load_load_profile

def main():
    # 加载配置和数据
    config_path = "configs/system_params.yaml"
    optimizer = MicrogridOptimizer(config_path)
    
    # 加载预测数据 (实际应用中替换为真实数据)
    pv_forecast = load_weather_forecast("data/hk_weather_forecast.csv")
    load_forecast = load_load_profile("data/load_profiles/commercial_load.csv")
    
    # 构建并求解模型
    optimizer.build_model(pv_forecast, load_forecast)
    results = optimizer.solve()
    
    # 获取并保存结果
    df_results = optimizer.get_results()
    df_results.to_csv("results/optimization_results.csv")
    
    # 打印关键指标
    print(f"优化目标值: {df_results['objective'].iloc[-1]:.2f} 港元")
    print(f"峰值负荷: {df_results['P_peak'].iloc[-1]:.2f} kW")
    
    # 可视化结果
    from utils.results_visualizer import plot_results
    plot_results(df_results)

if __name__ == "__main__":
    main()

# FlexiLeaf-Optimization-Model

## 项目概述
本代码库实现香港高密度社区微电网的动态优化调度模型，核心功能：
- 基于混合整数规划（MILP）的分钟级能源调度
- 光伏发电与负荷预测集成
- 储能与V2G协同优化
- 香港分时电价与FiT政策支持

## 数学模型
$$\min \sum_{t=1}^{T} \left( C_{grid}^t P_{grid}^t - C_{sell}P_{sell}^t + C_{deg} |P_{bat}^t| \right) + \lambda \cdot \max(P_{peak})$$

**约束条件包括**：
1. 功率平衡
2. 储能SOC动态
3. V2G充放电限制
4. 电网交互限制

## 快速开始
1. 安装依赖：`pip install -r requirements.txt`
2. 配置系统参数：`configs/system_params.yaml`
3. 准备输入数据：
   - 光伏预测：`data/hk_weather_forecast.csv`
   - 负荷曲线：`data/load_profiles/`
4. 运行优化：`python run_optimization.py`

## 关键功能
- `models/optimization_model.py`：核心优化模型
- `models/prediction_models.py`：LSTM/CNN预测模型
- `utils/data_loader.py`：数据加载工具
- `utils/results_visualizer.py`：结果可视化

## 香港场景验证
使用香港天文台历史数据验证，典型结果：
- 峰电削减：35.2%
- 成本节约：24.7%
- 求解时间：<800ms/24小时周期

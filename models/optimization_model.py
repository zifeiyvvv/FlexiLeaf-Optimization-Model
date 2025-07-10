import pyomo.environ as pyo
from pyomo.opt import SolverFactory
import pandas as pd
import numpy as np

class MicrogridOptimizer:
    def __init__(self, config_path):
        """
        初始化微电网优化模型
        :param config_path: YAML配置文件路径
        """
        self.config = self._load_config(config_path)
        self.model = None
        
    def _load_config(self, path):
        """加载YAML配置文件"""
        import yaml
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    
    def build_model(self, pv_forecast, load_forecast):
        """
        构建优化模型
        :param pv_forecast: 光伏预测出力序列 [kW]
        :param load_forecast: 负荷预测序列 [kW]
        """
        # 模型初始化
        self.model = pyo.ConcreteModel()
        
        # 时间集合 (15分钟间隔)
        time_slots = range(len(pv_forecast))
        self.model.T = pyo.Set(initialize=time_slots)
        
        # 定义变量
        self._define_variables()
        
        # 设置参数
        self._set_parameters(pv_forecast, load_forecast)
        
        # 构建目标函数
        self._build_objective_function()
        
        # 添加约束
        self._add_constraints()
    
    def _define_variables(self):
        """定义决策变量"""
        m = self.model
        
        # 电网交互
        m.P_grid_buy = pyo.Var(m.T, within=pyo.NonNegativeReals)  # 购电功率 [kW]
        m.P_grid_sell = pyo.Var(m.T, within=pyo.NonNegativeReals)  # 售电功率 [kW]
        
        # 储能系统
        m.P_bat_chg = pyo.Var(m.T, within=pyo.NonNegativeReals)  # 充电功率 [kW]
        m.P_bat_dis = pyo.Var(m.T, within=pyo.NonNegativeReals)  # 放电功率 [kW]
        m.SOC = pyo.Var(m.T, bounds=(self.config['battery']['soc_min'], 
                                  self.config['battery']['soc_max']))  # SOC状态
        
        # V2G系统
        m.P_v2g_chg = pyo.Var(m.T, within=pyo.NonNegativeReals)  # V2G充电 [kW]
        m.P_v2g_dis = pyo.Var(m.T, within=pyo.NonNegativeReals)  # V2G放电 [kW]
        m.u_v2g_chg = pyo.Var(m.T, within=pyo.Binary)  # 充电状态指示
        m.u_v2g_dis = pyo.Var(m.T, within=pyo.Binary)  # 放电状态指示
        
        # 峰值负荷
        m.P_peak = pyo.Var(within=pyo.NonNegativeReals)  # 周期内峰值负荷 [kW]
    
    def _set_parameters(self, pv_forecast, load_forecast):
        """设置预测参数"""
        m = self.model
        
        # 光伏预测出力
        m.P_PV = {t: pv_forecast[t] for t in m.T}
        
        # 负荷预测
        m.P_load = {t: load_forecast[t] for t in m.T}
        
        # 电价参数
        m.C_buy = {t: self.config['pricing']['buy_prices'][t] for t in m.T}
        m.C_sell = self.config['pricing']['sell_price']
        
        # 系统参数
        params = self.config
        m.eta_chg = params['battery']['eff_chg']  # 充电效率
        m.eta_dis = params['battery']['eff_dis']  # 放电效率
        m.E_bat = params['battery']['capacity']  # 电池容量 [kWh]
        m.P_bat_max = params['battery']['max_power']  # 最大充放电功率 [kW]
        m.dt = params['time']['interval']  # 时间间隔 [小时]
        
        # V2G参数
        m.N_v2g = params['v2g']['num_chargers']  # 充电桩数量
        m.P_v2g_rated = params['v2g']['rated_power']  # 单桩额定功率 [kW]
    
    def _build_objective_function(self):
        """构建目标函数：最小化总成本"""
        m = self.model
        
        # 购电成本
        cost_buy = sum(m.C_buy[t] * m.P_grid_buy[t] * m.dt for t in m.T)
        
        # 售电收益（负成本）
        cost_sell = -sum(m.C_sell * m.P_grid_sell[t] * m.dt for t in m.T)
        
        # 电池损耗成本
        cost_bat_deg = self.config['costs']['bat_deg'] * sum(
            (m.P_bat_chg[t] + m.P_bat_dis[t]) * m.dt for t in m.T
        )
        
        # 峰值惩罚项
        cost_peak = self.config['costs']['peak_penalty'] * m.P_peak
        
        # 总目标函数
        m.obj = pyo.Objective(
            expr = cost_buy + cost_sell + cost_bat_deg + cost_peak,
            sense = pyo.minimize
        )
    
    def _add_constraints(self):
        """添加所有约束条件"""
        m = self.model
        
        # 功率平衡约束
        def power_balance(m, t):
            return (m.P_PV[t] + m.P_bat_dis[t] + m.P_v2g_dis[t] == 
                    m.P_load[t] + m.P_grid_buy[t] - m.P_grid_sell[t] + 
                    m.P_bat_chg[t] + m.P_v2g_chg[t])
        m.power_balance = pyo.Constraint(m.T, rule=power_balance)
        
        # 储能动态约束
        def soc_dynamics(m, t):
            if t == m.T.first():
                return m.SOC[t] == self.config['battery']['soc_init']
            else:
                return m.SOC[t] == (m.SOC[t-1] + 
                                    (m.eta_chg * m.P_bat_chg[t-1] * m.dt - 
                                     m.P_bat_dis[t-1] * m.dt / m.eta_dis) / m.E_bat)
        m.soc_dynamics = pyo.Constraint(m.T, rule=soc_dynamics)
        
        # 储能功率限制
        def bat_chg_limit(m, t):
            return m.P_bat_chg[t] <= m.P_bat_max
        m.bat_chg_limit = pyo.Constraint(m.T, rule=bat_chg_limit)
        
        def bat_dis_limit(m, t):
            return m.P_bat_dis[t] <= m.P_bat_max
        m.bat_dis_limit = pyo.Constraint(m.T, rule=bat_dis_limit)
        
        # V2G状态互斥约束
        def v2g_state(m, t):
            return m.u_v2g_chg[t] + m.u_v2g_dis[t] <= 1
        m.v2g_state = pyo.Constraint(m.T, rule=v2g_state)
        
        # V2G充电功率约束
        def v2g_chg_limit(m, t):
            return m.P_v2g_chg[t] <= m.N_v2g * m.P_v2g_rated * m.u_v2g_chg[t]
        m.v2g_chg_limit = pyo.Constraint(m.T, rule=v2g_chg_limit)
        
        # V2G放电功率约束
        def v2g_dis_limit(m, t):
            return m.P_v2g_dis[t] <= m.N_v2g * m.P_v2g_rated * m.u_v2g_dis[t]
        m.v2g_dis_limit = pyo.Constraint(m.T, rule=v2g_dis_limit)
        
        # 峰值负荷定义
        def peak_definition(m, t):
            return m.P_peak >= m.P_grid_buy[t]
        m.peak_definition = pyo.Constraint(m.T, rule=peak_definition)
        
        # 电网售电约束
        def sell_limit(m, t):
            return m.P_grid_sell[t] <= m.P_PV[t] + m.P_v2g_dis[t] - m.P_load[t]
        m.sell_limit = pyo.Constraint(m.T, rule=sell_limit)
    
    def solve(self):
        """求解优化问题"""
        solver = SolverFactory('cplex')
        results = solver.solve(self.model)
        return results
    
    def get_results(self):
        """获取优化结果"""
        if not self.model:
            raise ValueError("Model not built yet. Call build_model() first.")
        
        results = {}
        for t in self.model.T:
            results[t] = {
                'P_grid_buy': pyo.value(self.model.P_grid_buy[t]),
                'P_grid_sell': pyo.value(self.model.P_grid_sell[t]),
                'P_bat_chg': pyo.value(self.model.P_bat_chg[t]),
                'P_bat_dis': pyo.value(self.model.P_bat_dis[t]),
                'SOC': pyo.value(self.model.SOC[t]),
                'P_v2g_chg': pyo.value(self.model.P_v2g_chg[t]),
                'P_v2g_dis': pyo.value(self.model.P_v2g_dis[t]),
            }
        
        results['objective'] = pyo.value(self.model.obj)
        results['P_peak'] = pyo.value(self.model.P_peak)
        
        return pd.DataFrame.from_dict(results, orient='index')

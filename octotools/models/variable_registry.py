# octotools/models/variable_registry.py

from typing import Dict, List, Set


class StandardVariables:
    """
    标准化变量名定义
    定义 TFIM-VQE 工作流中使用的标准变量名，确保工具间变量传递的一致性。
    """
    
    # ===============================
    # 标准变量名定义
    # ===============================
    
    # TFIM 规格
    SPEC_IR = "spec_ir"
    
    # 量子计算组件
    HAMILTONIAN = "hamiltonian"
    ANSATZ = "ansatz" 
    OPTIMIZER = "optimizer"
    ESTIMATOR = "estimator"
    
    # VQE 相关
    VQE_RESULT = "vqe_result"
    GROUND_STATE_ENERGY = "ground_state_energy"
    
    # 代码组装
    CODE_FRAGMENTS = "code_fragments"
    COMPLETE_CODE = "complete_code"
    
    # ===============================
    # 工具输出映射
    # ===============================
    
    TOOL_OUTPUTS: Dict[str, List[str]] = {
        "Qiskit_TFIM_Spec_Tool": [SPEC_IR],
        "Qiskit_TFIM_Hamiltonian_Tool": [HAMILTONIAN],
        "Qiskit_TFIM_Ansatz_Tool": [ANSATZ],
        "Qiskit_TFIM_Optimizer_Tool": [OPTIMIZER, ESTIMATOR],
        "Qiskit_VQE_Tool": [VQE_RESULT, GROUND_STATE_ENERGY],
        "qiskit_Code_Assembler_Tool": [COMPLETE_CODE],
    }
    
    # ===============================
    # 工具输入映射
    # ===============================
    
    TOOL_INPUTS: Dict[str, List[str]] = {
        "Qiskit_TFIM_Spec_Tool": [],
        "Qiskit_TFIM_Hamiltonian_Tool": [SPEC_IR],
        "Qiskit_TFIM_Ansatz_Tool": [SPEC_IR],
        "Qiskit_TFIM_Optimizer_Tool": [SPEC_IR],
        "Qiskit_VQE_Tool": [HAMILTONIAN, ANSATZ, OPTIMIZER, ESTIMATOR],
        "qiskit_Code_Assembler_Tool": [CODE_FRAGMENTS],
    }


class VariableRegistry:
    """
    变量注册管理器
    提供便捷的方法来查询工具的输入输出变量。
    """
    
    def __init__(self):
        self.vars = StandardVariables
    
    def get_tool_outputs(self, tool_name: str) -> List[str]:
        """获取指定工具预期产出的变量列表"""
        return self.vars.TOOL_OUTPUTS.get(tool_name, [])
    
    def get_tool_inputs(self, tool_name: str) -> List[str]:
        """获取指定工具需要的输入变量列表"""
        return self.vars.TOOL_INPUTS.get(tool_name, [])
    
    def validate_tool_inputs(self, tool_name: str, available_vars: Set[str]) -> tuple[bool, List[str]]:
        """
        验证指定工具是否具备所需的输入变量
        
        Args:
            tool_name: 工具名称
            available_vars: 当前可用的变量集合
            
        Returns:
            (is_valid, missing_vars): 是否满足要求，缺失的变量列表
        """
        required_vars = self.get_tool_inputs(tool_name)
        missing_vars = [var for var in required_vars if var not in available_vars]
        return len(missing_vars) == 0, missing_vars


# 全局实例
variable_registry = VariableRegistry()

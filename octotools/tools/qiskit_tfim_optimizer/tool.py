# octotools/tools/qiskit_tfim_optimizer/tool.py

from typing import Any, Dict, Optional

from octotools.tools.base import BaseTool

class Qiskit_TFIM_Optimizer_Tool(BaseTool):
    """
    TFIM VQE优化器和估计器配置工具
    生成Qiskit优化器和估计器配置代码
    """
    
    require_llm_engine = False

    def __init__(self):
        super().__init__(
            tool_name="Qiskit_TFIM_Optimizer_Tool",
            tool_description="Generate Qiskit optimizer and estimator setup for TFIM VQE.",
            tool_version="1.1.0",
            input_types={
                "spec_ir": 'dict - SpecIR from previous tools',
                "optimizer_type": 'str - "l_bfgs_b" (default), "cobyla", "spsa"',
                "estimator_type": 'str - "statevector" (default), "primitive"',
                "max_iter": "int - Maximum iterations (default: 1000)",
                "tolerance": "float - Convergence tolerance (default: 1e-6)",
                "include_objects": "bool - Whether to return actual objects (default: False)"
            },
            output_type='dict - {"optimizer": obj?, "estimator": obj?, "Code": str, "metadata": {...}}',
            demo_commands=[
                {
                    "command": 'tool.execute(spec_ir=spec_ir)',
                    "description": "Generate default L-BFGS-B optimizer with StatevectorEstimator"
                },
                {
                    "command": 'tool.execute(spec_ir=spec_ir, optimizer_type="cobyla", max_iter=500)',
                    "description": "Generate COBYLA optimizer with custom iterations"
                }
            ],
            user_metadata={
                "routing": {
                    "task_type": "TFIM_VQE",
                    "backend": "qiskit",
                    "model": "TFIM",
                    "position": "intermediate",
                    "requires_llm_engine": False,
                    "consumes": ["spec_ir"],
                    "produces": ["optimizer", "estimator"],
                    "next_tools": ["Qiskit_VQE_Tool"]
                },
                "inputs": {
                    "required_fields": ["spec_ir"],
                    "optional_fields": ["optimizer_type", "estimator_type", "max_iter", "tolerance", "include_objects"],
                    "defaults": {
                        "optimizer_type": "l_bfgs_b",
                        "estimator_type": "statevector",
                        "max_iter": 10000,
                        "tolerance": 1e-06,
                        "include_objects": False
                    }
                },
                "outputs": {
                    "output_type": "dict",
                    "standard_variables": ["optimizer", "estimator"]
                }
            }
        )

    def get_metadata(self):
        """获取工具元数据"""
        metadata = super().get_metadata()
        return metadata

    def _validate_inputs(self, spec_ir: Dict[str, Any], optimizer_type: str, 
                        estimator_type: str, max_iter: int, tolerance: float):
        """验证输入参数"""
        # 验证SpecIR
        required_fields = ["Model", "N"]
        missing_fields = [field for field in required_fields if field not in spec_ir]
        if missing_fields:
            raise ValueError(f"Missing required fields in SpecIR: {', '.join(missing_fields)}")
        
        if spec_ir["Model"] != "TFIM":
            raise ValueError("Only TFIM model is supported")
        
        if not isinstance(spec_ir["N"], int) or spec_ir["N"] < 2:
            raise ValueError("Invalid N in SpecIR")
        
        # 验证优化器类型
        supported_optimizers = ["l_bfgs_b", "cobyla", "spsa"]
        if optimizer_type not in supported_optimizers:
            raise ValueError(f"Unsupported optimizer: {optimizer_type}. Supported: {supported_optimizers}")
        
        # 验证估计器类型
        supported_estimators = ["statevector", "primitive"]
        if estimator_type not in supported_estimators:
            raise ValueError(f"Unsupported estimator: {estimator_type}. Supported: {supported_estimators}")
        
        # 验证参数
        if not isinstance(max_iter, int) or max_iter <= 0:
            raise ValueError("max_iter must be positive integer")
        
        if not isinstance(tolerance, (int, float)) or tolerance <= 0:
            raise ValueError("tolerance must be positive number")

    def _generate_l_bfgs_b_code(self, max_iter: int, tolerance: float) -> str:
        """生成L-BFGS-B优化器代码"""
        return f'''# L-BFGS-B: Gradient-based optimizer for smooth landscapes
from qiskit_algorithms.optimizers import L_BFGS_B

optimizer = L_BFGS_B(
    maxiter={max_iter},
    ftol={tolerance},
)'''

    def _generate_cobyla_code(self, max_iter: int, tolerance: float) -> str:
        """生成COBYLA优化器代码"""
        return f'''# COBYLA: Derivative-free optimizer, robust to noise
from qiskit_algorithms.optimizers import COBYLA

optimizer = COBYLA(
    maxiter={max_iter},
    tol={tolerance}
)'''

    def _generate_spsa_code(self, max_iter: int, tolerance: float) -> str:
        """生成SPSA优化器代码"""
        return f'''# SPSA: Noise-tolerant optimizer for hardware execution
from qiskit_algorithms.optimizers import SPSA

optimizer = SPSA(
    maxiter={max_iter},
    learning_rate=0.01,
    perturbation=0.01
)'''

    def _generate_statevector_estimator_code(self) -> str:
        """生成StatevectorEstimator代码"""
        return f'''# StatevectorEstimator: Exact simulation (noiseless)
from qiskit.primitives import StatevectorEstimator

estimator = StatevectorEstimator()'''

    def _generate_primitive_estimator_code(self) -> str:
        """生成Estimator primitive代码"""
        return f'''# Estimator: Hardware-compatible primitive
from qiskit.primitives import Estimator

estimator = Estimator()'''

    def _generate_combined_code(
        self,
        optimizer_code: str,
        estimator_code: str,
        optimizer_type: str,
        estimator_type: str,
        max_iter: int,
        tolerance: float
    ) -> str:
        """生成组合的优化器和估计器设置代码"""
        
        code = f'''# Generated by Qiskit_TFIM_Optimizer_Tool
# Configuration: {optimizer_type} optimizer + {estimator_type} estimator

{estimator_code}

{optimizer_code}

# Optimizer configuration summary
print(f"Optimizer: {optimizer_type.upper()}")
print(f"Max iterations: {max_iter}")
print(f"Tolerance: {tolerance}")
print(f"Estimator: {estimator_type.upper()}")

# Ready for VQE usage
# Usage: vqe = VQE(estimator, ansatz, optimizer)
'''
        
        return code

    def _create_optimizer_object(self, optimizer_type: str, max_iter: int, tolerance: float):
        """创建实际的优化器对象（当include_objects=True时使用）"""
        try:
            if optimizer_type == "l_bfgs_b":
                from qiskit_algorithms.optimizers import L_BFGS_B
                return L_BFGS_B(maxiter=max_iter, ftol=tolerance, gtol=tolerance)
            elif optimizer_type == "cobyla":
                from qiskit_algorithms.optimizers import COBYLA
                return COBYLA(maxiter=max_iter, tol=tolerance)
            elif optimizer_type == "spsa":
                from qiskit_algorithms.optimizers import SPSA
                return SPSA(maxiter=max_iter, learning_rate=0.01, perturbation=0.01)
        except ImportError:
            raise ImportError(f"Cannot import {optimizer_type} optimizer from qiskit_algorithms")

    def _create_estimator_object(self, estimator_type: str):
        """创建实际的估计器对象（当include_objects=True时使用）"""
        try:
            if estimator_type == "statevector":
                from qiskit.primitives import StatevectorEstimator
                return StatevectorEstimator()
            elif estimator_type == "primitive":
                from qiskit.primitives import Estimator
                return Estimator()
        except ImportError:
            raise ImportError(f"Cannot import {estimator_type} estimator from qiskit.primitives")

    def execute(
        self,
        spec_ir: Dict[str, Any],
        optimizer_type: str = "l_bfgs_b",
        estimator_type: str = "statevector",
        max_iter: int = 1000,
        tolerance: float = 1e-6,
        include_objects: bool = False
    ) -> Dict[str, Any]:
        """
        生成Qiskit优化器和估计器配置
        
        Args:
            spec_ir: SpecIR字典
            optimizer_type: 优化器类型
            estimator_type: 估计器类型
            max_iter: 最大迭代次数
            tolerance: 收敛容差
            include_objects: 是否返回实际的对象
            
        Returns:
            dict: 生成的代码和可选对象
        """
        
        # 验证输入
        if not isinstance(spec_ir, dict):
            raise ValueError("spec_ir must be a dictionary")
            
        self._validate_inputs(spec_ir, optimizer_type, estimator_type, max_iter, tolerance)
        
        # 提取系统信息
        N = spec_ir["N"]
        
        # 生成代码
        optimizer_code_generators = {
            "l_bfgs_b": self._generate_l_bfgs_b_code,
            "cobyla": self._generate_cobyla_code,
            "spsa": self._generate_spsa_code
        }
        
        estimator_code_generators = {
            "statevector": self._generate_statevector_estimator_code,
            "primitive": self._generate_primitive_estimator_code
        }
        
        optimizer_code = optimizer_code_generators[optimizer_type](max_iter, tolerance)
        estimator_code = estimator_code_generators[estimator_type]()
        
        # 组合代码
        combined_code = self._generate_combined_code(
            optimizer_code, estimator_code, optimizer_type, estimator_type, max_iter, tolerance
        )
        
        result = {
            "Code": combined_code,
            "metadata": {
                "backend": "qiskit",
                "model": "TFIM",
                "optimizer_type": optimizer_type,
                "estimator_type": estimator_type,
                "parameters": {
                    "max_iter": max_iter,
                    "tolerance": tolerance,
                    "N": N
                }
            }
        }
        
        # 可选：包含实际的对象
        if include_objects:
            try:
                optimizer_obj = self._create_optimizer_object(optimizer_type, max_iter, tolerance)
                estimator_obj = self._create_estimator_object(estimator_type)
                result["optimizer"] = optimizer_obj  # 使用标准变量名
                result["estimator"] = estimator_obj  # 使用标准变量名
            except ImportError:
                # 如果无法导入Qiskit，不返回对象但继续执行
                pass
        
        return result

# octotools/tools/qiskit_tfim_optimizer/tool.py
from typing import Any, Dict, Optional, Union
from octotools.tools.base import BaseTool
from octotools.models.semantic import SemanticCodeFragment
from octotools.models.semantic_types import SemanticTypes

class Qiskit_TFIM_Optimizer_Tool(BaseTool):
    """
    TFIM VQE优化器和估计器配置工具 - 语义化版本
    生成包含optimizer和estimator定义的代码片段
    """
    
    require_llm_engine = False
    
    # 新增语义属性（特殊：一个工具生成两个语义组件）
    semantic_type = SemanticTypes.OPTIMIZER  # 主要类型
    dependencies = [SemanticTypes.SPEC]
    provides = ["optimizer", "estimator"]  # 提供两个变量

    def __init__(self):
        super().__init__(
            tool_name="Qiskit_TFIM_Optimizer_Tool",
            tool_description="Generate Qiskit optimizer and estimator setup for TFIM VQE.",
            tool_version="2.0.0",
            input_types={
                "spec_fragment": 'SemanticCodeFragment - Spec fragment from previous tool',
                "spec_ir": 'dict - SpecIR (legacy compatibility)',
                "optimizer_type": 'str - "l_bfgs_b" (default), "cobyla", "spsa"',
                "estimator_type": 'str - "statevector" (default), "primitive"',
                "max_iter": "int - Maximum iterations (default: 1000)",
                "tolerance": "float - Convergence tolerance (default: 1e-6)"
            },
            output_type='SemanticCodeFragment - optimizer and estimator definition code',
            demo_commands=[
                {
                    "command": 'tool.execute(spec_fragment=spec_fragment)',
                    "description": "Generate default L-BFGS-B optimizer with StatevectorEstimator"
                },
                {
                    "command": 'tool.execute(spec_fragment=spec_fragment, optimizer_type="cobyla", max_iter=500)',
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
                    "consumes": [SemanticTypes.SPEC],
                    "produces": [SemanticTypes.OPTIMIZER, SemanticTypes.ESTIMATOR],
                    "next_tools": ["Qiskit_VQE_Tool"]
                }
            }
        )

    def _extract_spec_ir(self, input_data: Union[SemanticCodeFragment, Dict[str, Any]]) -> Dict[str, Any]:
        """从输入中提取spec_ir数据"""
        if isinstance(input_data, SemanticCodeFragment):
            if input_data.execution_context and "spec_ir" in input_data.execution_context:
                return input_data.execution_context["spec_ir"]
            else:
                context = {}
                exec(input_data.code, globals(), context)
                return context.get("spec_ir")
        elif isinstance(input_data, dict):
            return input_data
        else:
            raise ValueError("Invalid input: expected SemanticCodeFragment or dict")

    def _validate_inputs(self, spec_ir: Dict[str, Any], optimizer_type: str, 
                        estimator_type: str, max_iter: int, tolerance: float):
        """验证输入参数（保持原逻辑）"""
        required_fields = ["Model", "N"]
        missing_fields = [field for field in required_fields if field not in spec_ir]
        if missing_fields:
            raise ValueError(f"Missing required fields in SpecIR: {', '.join(missing_fields)}")
        
        if spec_ir["Model"] != "TFIM":
            raise ValueError("Only TFIM model is supported")
        
        if not isinstance(spec_ir["N"], int) or spec_ir["N"] < 2:
            raise ValueError("Invalid N in SpecIR")
        
        supported_optimizers = ["l_bfgs_b", "cobyla", "spsa"]
        if optimizer_type not in supported_optimizers:
            raise ValueError(f"Unsupported optimizer: {optimizer_type}. Supported: {supported_optimizers}")
        
        supported_estimators = ["statevector", "primitive"]
        if estimator_type not in supported_estimators:
            raise ValueError(f"Unsupported estimator: {estimator_type}. Supported: {supported_estimators}")
        
        if not isinstance(max_iter, int) or max_iter <= 0:
            raise ValueError("max_iter must be positive integer")
        
        if not isinstance(tolerance, (int, float)) or tolerance <= 0:
            raise ValueError("tolerance must be positive number")

    def _generate_optimizer_code(self, optimizer_type: str, max_iter: int, tolerance: float) -> str:
        """生成优化器代码（保持原逻辑）"""
        if optimizer_type == "l_bfgs_b":
            return f'''# L-BFGS-B: Gradient-based optimizer for smooth landscapes
from qiskit_algorithms.optimizers import L_BFGS_B

optimizer = L_BFGS_B(
    maxiter={max_iter},
    ftol={tolerance},
)'''
        elif optimizer_type == "cobyla":
            return f'''# COBYLA: Derivative-free optimizer, robust to noise
from qiskit_algorithms.optimizers import COBYLA

optimizer = COBYLA(
    maxiter={max_iter},
    tol={tolerance}
)'''
        elif optimizer_type == "spsa":
            return f'''# SPSA: Noise-tolerant optimizer for hardware execution
from qiskit_algorithms.optimizers import SPSA

optimizer = SPSA(
    maxiter={max_iter},
    learning_rate=0.01,
    perturbation=0.01
)'''

    def _generate_estimator_code(self, estimator_type: str) -> str:
        """生成估计器代码（保持原逻辑）"""
        if estimator_type == "statevector":
            return '''# StatevectorEstimator: Exact simulation (noiseless)
from qiskit.primitives import StatevectorEstimator

estimator = StatevectorEstimator()'''
        elif estimator_type == "primitive":
            return '''# Estimator: Hardware-compatible primitive
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
        """生成组合的优化器和估计器设置代码（保持原逻辑）"""
        
        code = f'''# Generated by Qiskit_TFIM_Optimizer_Tool
# Configuration: {optimizer_type} optimizer + {estimator_type} estimator

{estimator_code}

{optimizer_code}

# Optimizer configuration summary
print(f"Optimizer: {optimizer_type.upper()}")
print(f"Max iterations: {max_iter}")
print(f"Tolerance: {tolerance}")
print(f"Estimator: {estimator_type.upper()}")
print("VQE components ready!")
'''
        
        return code

    def execute(
        self,
        spec_fragment: Optional[SemanticCodeFragment] = None,
        spec_ir: Optional[Dict[str, Any]] = None,  # 向后兼容
        optimizer_type: str = "l_bfgs_b",
        estimator_type: str = "statevector",
        max_iter: int = 1000,
        tolerance: float = 1e-6
    ) -> SemanticCodeFragment:
        """
        生成Qiskit优化器和估计器配置代码
        
        Args:
            spec_fragment: 来自Spec工具的语义片段
            spec_ir: SpecIR字典（向后兼容）
            optimizer_type: 优化器类型
            estimator_type: 估计器类型
            max_iter: 最大迭代次数
            tolerance: 收敛容差
            
        Returns:
            SemanticCodeFragment: 包含optimizer和estimator定义的代码片段
        """
        
        # 确定输入源
        if spec_fragment is not None:
            input_data = spec_fragment
        elif spec_ir is not None:
            input_data = spec_ir
        else:
            raise ValueError("Either spec_fragment or spec_ir must be provided")
        
        # 提取spec_ir数据
        spec_ir_data = self._extract_spec_ir(input_data)
        
        # 验证输入（保持原逻辑）
        self._validate_inputs(spec_ir_data, optimizer_type, estimator_type, max_iter, tolerance)
        
        # 提取系统信息
        N = spec_ir_data["N"]
        
        # 生成代码（保持原逻辑）
        optimizer_code = self._generate_optimizer_code(optimizer_type, max_iter, tolerance)
        estimator_code = self._generate_estimator_code(estimator_type)
        
        # 组合代码
        combined_code = self._generate_combined_code(
            optimizer_code, estimator_code, optimizer_type, estimator_type, max_iter, tolerance
        )
        
        # 返回语义片段
        return self.create_semantic_fragment(
            code=combined_code,
            variable_name="optimizer",  # 主要变量名
            metadata={
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
        )
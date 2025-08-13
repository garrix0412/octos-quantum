# 简化版 qiskit_tfim_ansatz_tool.py

from typing import Any, Dict, Optional
import json

from octotools.tools.base import BaseTool

CONTRACT_VERSION = "ansatz.tfim.qiskit/v1"

class Qiskit_TFIM_Ansatz_Tool(BaseTool):
    """
    TFIM Ansatz代码生成工具
    职责：将SpecIR转换为Qiskit ansatz代码，支持多种ansatz类型，自动修复输入格式问题
    """
    
    require_llm_engine = False

    def __init__(self):
        super().__init__(
            tool_name="Qiskit_TFIM_Ansatz_Tool",
            tool_description="Generate Qiskit TFIM ansatz code with proper boundary conditions. Auto-fixes missing fields.",
            tool_version="1.1.0",
            input_types={
                "spec": 'dict - SpecIR from previous tools',
                "ansatz_type": 'str - Ansatz type: "hamiltonian_informed" (default), "efficient_su2"',
                "reps": "int - Number of repetitions (default: 2)",
                "include_object": "bool - Whether to return circuit object (default: False)"
            },
            output_type='dict - {"Code": str, "CircuitObject": QuantumCircuit?, "metadata": {...}}',
            demo_commands=[
                {
                    "command": 'tool.execute(spec=spec_ir)',
                    "description": "Generate default Hamiltonian-informed ansatz with reps=2"
                },
                {
                    "command": 'tool.execute(spec=spec_ir, ansatz_type="efficient_su2", reps=3)',
                    "description": "Generate EfficientSU2 ansatz with 3 repetitions"
                }
            ],
            user_metadata={
                "routing": {
                    "task_type": "TFIM_VQE",
                    "backend": "qiskit",
                    "model": "TFIM",
                    "position": "intermediate",
                    "requires_llm_engine": False,
                    "consumes": ["SpecIR"],
                    "produces": ["QiskitCode", "CircuitObject"],
                    "next_tools": ["Qiskit_TFIM_Optimizer_Tool"]
                },
                "inputs": {
                    "required_fields": ["spec"],
                    "optional_fields": ["ansatz_type", "reps", "include_object"],
                    "defaults": {
                        "ansatz_type": "hamiltonian_informed",
                        "reps": 2,
                        "include_object": False
                    },
                    "ansatz_selection_guide": {
                        "hamiltonian_informed": {
                            "description": "Physics-informed ansatz tailored for TFIM Hamiltonian structure",
                            "advantages": ["Better initial convergence for TFIM", "Fewer parameters", "Physically motivated"],
                            "best_for": ["Small systems (N≤8)", "High accuracy requirements", "Research/educational purposes"],
                            "parameters_scaling": "Linear: OBC=(2N-1)*reps, PBC=2N*reps"
                        },
                        "efficient_su2": {
                            "description": "General-purpose hardware-efficient ansatz from Qiskit library",
                            "advantages": ["Hardware optimized", "Well-tested", "Robust for various problems"],
                            "best_for": ["Larger systems (N>8)", "Hardware execution", "Production use"],
                            "parameters_scaling": "2N*reps + N (rotation + entanglement layers)"
                        }
                    }
                },
                "outputs": {
                    "output_type": "dict",
                    "artifacts": [],
                    "contract_version": CONTRACT_VERSION
                },
                "error_codes": [
                    "INVALID_SPEC",
                    "UNSUPPORTED_ANSATZ_TYPE",
                    "INVALID_REPS",
                    "MISSING_REQUIRED_FIELD"
                ],
                "execution_profile": {
                    "deterministic": True,
                    "idempotent": True,
                    "side_effects": []
                }
            }
        )

    def get_metadata(self):
        """获取工具元数据"""
        metadata = super().get_metadata()
        return metadata

    def _auto_complete_spec_ir(self, spec_ir: Dict[str, Any]) -> Dict[str, Any]:
        """自动补全SpecIR的缺失字段，增强容错性"""
        completed_spec = spec_ir.copy()
        
        # 关键修复：自动补充Backend字段
        if "Backend" not in completed_spec:
            completed_spec["Backend"] = "qiskit"
        
        # 补充其他常见的缺失字段
        if "Sites" not in completed_spec:
            completed_spec["Sites"] = {
                "Type": "Qubit", 
                "PauliConvention": "±1 eigenvalues"
            }
            
        if "DType" not in completed_spec:
            completed_spec["DType"] = "Float64"
            
        if "Indexing" not in completed_spec:
            completed_spec["Indexing"] = {"Convention": "python-0"}
            
        if "HamiltonianForm" not in completed_spec:
            completed_spec["HamiltonianForm"] = "H = -J Σ Z_i Z_{i+1} - h Σ X_i"
            
        return completed_spec

    def _validate_inputs(self, spec_ir: Dict[str, Any], ansatz_type: str, reps: int):
        """验证输入参数（在自动补全后进行）"""
        # 核心字段验证
        required_fields = ["Model", "N", "Boundary"]
        missing_fields = [field for field in required_fields if field not in spec_ir]
        if missing_fields:
            raise ValueError(f"MISSING_REQUIRED_FIELD: {', '.join(missing_fields)}")
        
        if spec_ir["Model"] != "TFIM":
            raise ValueError("UNSUPPORTED_MODEL")
        
        if not isinstance(spec_ir["N"], int) or spec_ir["N"] < 2:
            raise ValueError("INVALID_SPEC")
        
        # 验证ansatz类型
        supported_ansatz = ["hamiltonian_informed", "efficient_su2"]
        if ansatz_type not in supported_ansatz:
            raise ValueError(f"UNSUPPORTED_ANSATZ_TYPE: {ansatz_type}")
        
        # 验证重复次数
        if not isinstance(reps, int) or reps < 1:
            raise ValueError("INVALID_REPS")

    def _generate_hamiltonian_informed_code(self, N: int, boundary: str, reps: int) -> str:
        """生成哈密顿量导向的ansatz代码"""
        
        # 根据边界条件确定参数计算
        if boundary == "PBC":
            zz_comment = "# ZZ interactions (periodic boundary)"
            zz_range = f"range({N})"
            next_i_expr = "(i + 1) % num_qubits"
            params_per_layer = 2 * N  # N ZZ + N X
        else:  # OBC
            zz_comment = "# ZZ interactions (open boundary)"
            zz_range = f"range({N - 1})"
            next_i_expr = "i + 1"
            params_per_layer = (N - 1) + N  # (N-1) ZZ + N X
        
        total_params = reps * params_per_layer
        
        code = f'''# Generated by Qiskit_TFIM_Ansatz_Tool (Hamiltonian-informed)
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector
import numpy as np

def build_tfim_ansatz(num_qubits: int = {N}, reps: int = {reps}) -> QuantumCircuit:
    """
    Build Hamiltonian-informed TFIM ansatz.
    Boundary condition: {boundary}
    
    Parameters:
        num_qubits: Number of qubits
        reps: Number of repetition layers
        
    Returns:
        QuantumCircuit: Parameterized ansatz circuit
    """
    qc = QuantumCircuit(num_qubits)
    
    # Initialize to superposition
    for i in range(num_qubits):
        qc.h(i)
    
    # Parameters
    num_params_per_layer = {params_per_layer}
    total_params = reps * num_params_per_layer
    params = ParameterVector('θ', total_params)
    param_idx = 0
    
    # Build repetition layers
    for layer in range(reps):
        {zz_comment}
        for i in {zz_range}:
            next_i = {next_i_expr}
            qc.cx(i, next_i)
            qc.rz(params[param_idx], next_i)
            qc.cx(i, next_i)
            param_idx += 1
        
        # X field rotations
        for i in range(num_qubits):
            qc.rx(params[param_idx], i)
            param_idx += 1
    
    return qc

# Create ansatz with default parameters
ansatz = build_tfim_ansatz({N}, {reps})
print(f"Ansatz parameters: {{ansatz.num_parameters}}")
'''
        return code

    def _generate_efficient_su2_code(self, N: int, boundary: str, reps: int) -> str:
        """生成EfficientSU2 ansatz代码"""
        
        code = f'''# Generated by Qiskit_TFIM_Ansatz_Tool (EfficientSU2)
from qiskit import QuantumCircuit
from qiskit.circuit.library import EfficientSU2
from qiskit.circuit import ParameterVector
import numpy as np

def build_tfim_ansatz(num_qubits: int = {N}, reps: int = {reps}) -> QuantumCircuit:
    """
    Build EfficientSU2 ansatz for TFIM.
    Hardware-efficient ansatz suitable for NISQ devices.
    
    Parameters:
        num_qubits: Number of qubits
        reps: Number of repetition layers
        
    Returns:
        QuantumCircuit: Parameterized ansatz circuit
    """
    # Create EfficientSU2 ansatz
    ansatz = EfficientSU2(num_qubits, reps=reps, entanglement='linear')
    
    # Add initial state preparation (superposition)
    qc = QuantumCircuit(num_qubits)
    for i in range(num_qubits):
        qc.h(i)
    
    # Combine with ansatz
    qc.compose(ansatz, inplace=True)
    
    return qc

# Create ansatz with default parameters
ansatz = build_tfim_ansatz({N}, {reps})
print(f"Ansatz parameters: {{ansatz.num_parameters}}")
'''
        return code

    def _create_circuit_object(self, N: int, boundary: str, ansatz_type: str, reps: int):
        """创建实际的量子电路对象（当include_object=True时使用）"""
        try:
            from qiskit import QuantumCircuit
            from qiskit.circuit import ParameterVector
        except ImportError:
            raise ImportError("Qiskit is required to create circuit object")
        
        if ansatz_type == "hamiltonian_informed":
            # 创建哈密顿量导向的ansatz
            qc = QuantumCircuit(N)
            
            # 初始化为叠加态
            for i in range(N):
                qc.h(i)
            
            # 计算参数数量
            if boundary == "PBC":
                params_per_layer = 2 * N
            else:
                params_per_layer = (N - 1) + N
            
            total_params = reps * params_per_layer
            params = ParameterVector('θ', total_params)
            param_idx = 0
            
            # 构建重复层
            for layer in range(reps):
                # ZZ相互作用
                if boundary == "PBC":
                    for i in range(N):
                        next_i = (i + 1) % N
                        qc.cx(i, next_i)
                        qc.rz(params[param_idx], next_i)
                        qc.cx(i, next_i)
                        param_idx += 1
                else:
                    for i in range(N - 1):
                        qc.cx(i, i + 1)
                        qc.rz(params[param_idx], i + 1)
                        qc.cx(i, i + 1)
                        param_idx += 1
                
                # X场旋转
                for i in range(N):
                    qc.rx(params[param_idx], i)
                    param_idx += 1
            
            return qc
            
        elif ansatz_type == "efficient_su2":
            # 创建EfficientSU2 ansatz
            try:
                from qiskit.circuit.library import EfficientSU2
            except ImportError:
                raise ImportError("Qiskit circuit library is required for EfficientSU2")
            
            # 初始化
            qc = QuantumCircuit(N)
            for i in range(N):
                qc.h(i)
            
            # 添加EfficientSU2
            ansatz = EfficientSU2(N, reps=reps, entanglement='linear')
            qc.compose(ansatz, inplace=True)
            
            return qc

    def execute(
        self,
        spec: Dict[str, Any],
        ansatz_type: str = "hamiltonian_informed",
        reps: int = 2,
        include_object: bool = False
    ) -> Dict[str, Any]:
        """
        生成Qiskit TFIM ansatz代码
        
        Args:
            spec: SpecIR字典或包含SpecIR的字典
            ansatz_type: ansatz类型 ("hamiltonian_informed" 或 "efficient_su2")
            reps: 重复层数
            include_object: 是否返回实际的QuantumCircuit对象
            
        Returns:
            dict: 生成的代码、可选对象和元数据
        """
        
        # 处理不同的输入格式，增强兼容性
        if not isinstance(spec, dict):
            raise ValueError("INVALID_SPEC: spec must be a dictionary")
            
        # 支持两种格式：直接SpecIR或包含SpecIR的字典
        if "SpecIR" in spec:
            spec_ir = spec["SpecIR"]
        elif "Model" in spec:
            spec_ir = spec  # 直接是SpecIR格式
        else:
            raise ValueError("MISSING_REQUIRED_FIELD: SpecIR or Model")
        
        # 关键改进：先自动补全，再验证
        completed_spec_ir = self._auto_complete_spec_ir(spec_ir)
        self._validate_inputs(completed_spec_ir, ansatz_type, reps)
        
        # 提取参数
        N = completed_spec_ir["N"]
        boundary = completed_spec_ir["Boundary"]  # "OBC" 或 "PBC"
        
        # 生成ansatz代码
        if ansatz_type == "hamiltonian_informed":
            code = self._generate_hamiltonian_informed_code(N, boundary, reps)
        elif ansatz_type == "efficient_su2":
            code = self._generate_efficient_su2_code(N, boundary, reps)
        else:
            raise ValueError(f"UNSUPPORTED_ANSATZ_TYPE: {ansatz_type}")
        
        result = {
            "Code": code,
            "metadata": {
                "backend": "qiskit",
                "model": "TFIM",
                "ansatz_type": ansatz_type,
                "parameters": {"N": N, "boundary": boundary, "reps": reps},
                "contract_version": CONTRACT_VERSION
            }
        }
        
        # 可选：包含实际的电路对象
        if include_object:
            try:
                circuit_obj = self._create_circuit_object(N, boundary, ansatz_type, reps)
                result["CircuitObject"] = circuit_obj
            except ImportError as e:
                # 如果无法导入Qiskit，提供友好的错误信息
                result["warnings"] = [f"Cannot create circuit object: {str(e)}"]
        
        return result




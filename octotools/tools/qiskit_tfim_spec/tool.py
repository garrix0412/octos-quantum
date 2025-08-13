# octotools/tools/qiskit_tfim_spec/tool.py

from typing import Any, Dict, Optional

from octotools.tools.base import BaseTool

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)

class Qiskit_TFIM_Spec_Tool(BaseTool):
    """
    TFIM规格标准化工具
    将TFIM参数标准化为SpecIR格式，确保数据完整性
    """
    
    require_llm_engine = False

    def __init__(self):
        super().__init__(
            tool_name="Qiskit_TFIM_Spec_Tool",
            tool_description="Normalize TFIM spec for Qiskit backend. Ensures complete SpecIR with all required fields.",
            tool_version="1.1.0",
            input_types={
                "spec": 'dict - Optional structured input. Minimal {"model":"TFIM","N":int}.',
                "model": 'str - MUST be "TFIM" (used if spec not provided).',
                "N": "int - number of qubits, N >= 2 (used if spec not provided).",
                "boundary": 'str - "open"/"periodic" or "OBC"/"PBC" (default: "open").',
                "J": "float - ZZ coupling strength (default 1.0).",
                "h": "float - transverse field strength (default 1.0).",
            },
            output_type='dict - {"spec_ir": {...}}',
            demo_commands=[
                {
                    "command": 'tool.execute(spec={"model":"TFIM","N":8})', 
                    "description": "Minimal input → normalized SpecIR (OBC, J=1.0, h=1.0)"
                },
                {
                    "command": 'tool.execute(model="TFIM", N=4, boundary="PBC", J=0.5)', 
                    "description": "Named args → PBC boundary with custom J coupling"
                }
            ],
            user_metadata={
                "routing": {
                    "task_type": "TFIM_VQE",
                    "backend": "qiskit",
                    "model": "TFIM",
                    "position": "initial",
                    "requires_llm_engine": False,
                    "produces": ["spec_ir"],
                    "next_tools": ["Qiskit_TFIM_Hamiltonian_Tool"]
                },
                "inputs": {
                    "required_fields": ["model", "N"],
                    "optional_fields": ["boundary", "J", "h"],
                    "defaults": {
                        "boundary": "open",
                        "J": 1.0,
                        "h": 1.0,
                        "backend": "qiskit"
                    }
                },
                "outputs": {
                    "output_type": "dict",
                    "standard_variable": "spec_ir"
                }
            }
        )

    def get_metadata(self):
        """获取工具元数据"""
        metadata = super().get_metadata()
        return metadata

    def _merge_args_to_spec(
        self,
        spec: Optional[Dict[str, Any]],
        model: Optional[str],
        N: Optional[int],
        boundary: Optional[str],
        J: Optional[float],
        h: Optional[float]
    ) -> Dict[str, Any]:
        """合并参数到统一的spec字典"""
        if spec is not None:
            return dict(spec)
        
        result = {"model": model, "N": N}
        if boundary is not None:
            result["boundary"] = boundary
        if J is not None:
            result["J"] = J
        if h is not None:
            result["h"] = h
        return result

    def _normalize_boundary(self, boundary_input: Optional[str]) -> str:
        """标准化边界条件"""
        if boundary_input is None:
            return "open"
        
        b = str(boundary_input).strip().upper()
        if b in ("OBC", "OPEN"):
            return "open"
        elif b in ("PBC", "PERIODIC"):
            return "periodic"
        else:
            raise ValueError(f"Invalid boundary condition: {boundary_input}")

    def execute(
        self,
        spec: Optional[Dict[str, Any]] = None,
        *,
        model: Optional[str] = None,
        N: Optional[int] = None,
        boundary: Optional[str] = None,
        J: Optional[float] = None,
        h: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Execute TFIM spec normalization for Qiskit backend.
        
        Returns:
            dict: {"spec_ir": {...}} - 使用标准变量名
        """
        
        # 合并所有输入到统一spec
        merged_spec = self._merge_args_to_spec(spec, model, N, boundary, J, h)
        
        # 基础验证
        if not isinstance(merged_spec, dict):
            raise ValueError("Invalid input: spec must be a dictionary")
        
        if merged_spec.get("model") != "TFIM":
            raise ValueError("Only TFIM model is supported")
        
        # 验证N (number of qubits)
        N_val = merged_spec.get("N")
        if not isinstance(N_val, int):
            raise ValueError("N (number of qubits) is required and must be an integer")
        if not (2 <= N_val <= 20):
            raise ValueError("N must be between 2 and 20")
        
        # 处理边界条件
        boundary_val = self._normalize_boundary(merged_spec.get("boundary"))
        
        # 处理耦合参数，使用默认值
        J_val = merged_spec.get("J", 1.0)
        h_val = merged_spec.get("h", 1.0)
        
        # 验证耦合参数
        for name, val in {"J": J_val, "h": h_val}.items():
            if not _is_number(val):
                raise ValueError(f"Invalid coupling parameter {name}: must be a number")
        
        J_val = float(J_val)
        h_val = float(h_val)
        
        # 构建标准SpecIR
        spec_ir = {
            "Model": "TFIM",
            "N": N_val,
            "Boundary": "OBC" if boundary_val == "open" else "PBC",
            "Couplings": {"J": J_val, "h": h_val},
            "Backend": "qiskit",
            "Sites": {"Type": "Qubit", "PauliConvention": "±1 eigenvalues"},
            "DType": "Float64",
            "Indexing": {"Convention": "python-0"},
            "HamiltonianForm": "H = -J Σ Z_i Z_{i+1} - h Σ X_i"
        }
        
        # 返回结果，使用标准变量名
        return {"spec_ir": spec_ir}

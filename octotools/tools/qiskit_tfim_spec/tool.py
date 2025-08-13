# 简化版 qiskit_tfim_spec_tool.py

from typing import Any, Dict, Optional
import os
import json

from octotools.tools.base import BaseTool

CONTRACT_VERSION = "spec.tfim.qiskit/v1"

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)

class Qiskit_TFIM_Spec_Tool(BaseTool):
    """
    TFIM规格标准化工具
    职责：将TFIM参数标准化为SpecIR格式，确保数据完整性
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
                "output_dir": "str - Optional: if set, write spec.json here."
            },
            output_type='dict - {"SpecIR": {...}, "warnings": [...]}',
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
                    "produces": ["SpecIR"],
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
                    },
                    "constraints": {
                        "model": ["TFIM"],
                        "boundary": ["open", "periodic", "OBC", "PBC"],
                        "N_min": 2,
                        "N_max": 20
                    }
                },
                "outputs": {
                    "output_type": "dict",
                    "artifacts": ["spec.json"],
                    "contract_version": CONTRACT_VERSION
                },
                "error_codes": [
                    "UNSUPPORTED_MODEL",
                    "MISSING_FIELD:N",
                    "OUT_OF_RANGE:N",
                    "OUT_OF_RANGE:boundary",
                    "INVALID_COUPLING"
                ],
                "execution_profile": {
                    "deterministic": True,
                    "idempotent": True,
                    "side_effects": ["write:spec.json?"]
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
            raise ValueError("OUT_OF_RANGE:boundary")

    def execute(
        self,
        spec: Optional[Dict[str, Any]] = None,
        *,
        model: Optional[str] = None,
        N: Optional[int] = None,
        boundary: Optional[str] = None,
        J: Optional[float] = None,
        h: Optional[float] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute TFIM spec normalization for Qiskit backend.
        
        Returns:
            dict: {"SpecIR": {...}, "warnings": [...]}
        """
        
        # 合并所有输入到统一spec
        merged_spec = self._merge_args_to_spec(spec, model, N, boundary, J, h)
        
        # 基础验证
        if not isinstance(merged_spec, dict):
            raise ValueError("MISSING_FIELD:N")
        
        if merged_spec.get("model") != "TFIM":
            raise ValueError("UNSUPPORTED_MODEL")
        
        # 验证N (number of qubits)
        N_val = merged_spec.get("N")
        if not isinstance(N_val, int):
            raise ValueError("MISSING_FIELD:N")
        if not (2 <= N_val <= 20):
            raise ValueError("OUT_OF_RANGE:N")
        
        # 处理边界条件
        boundary_val = self._normalize_boundary(merged_spec.get("boundary"))
        
        # 处理耦合参数，使用默认值
        J_val = merged_spec.get("J", 1.0)
        h_val = merged_spec.get("h", 1.0)
        
        # 验证耦合参数
        for name, val in {"J": J_val, "h": h_val}.items():
            if not _is_number(val):
                raise ValueError(f"INVALID_COUPLING")
        
        J_val = float(J_val)
        h_val = float(h_val)
        
        # 记录应用的默认值
        assumptions = []
        if "boundary" not in merged_spec:
            assumptions.append("Boundary=OBC (default)")
        if "J" not in merged_spec:
            assumptions.append("J=1.0 (default)")
        if "h" not in merged_spec:
            assumptions.append("h=1.0 (default)")
        
        # 构建标准SpecIR - 重点确保Backend字段存在
        spec_ir = {
            "Model": "TFIM",
            "N": N_val,
            "Boundary": "OBC" if boundary_val == "open" else "PBC",
            "Couplings": {"J": J_val, "h": h_val},
            "Backend": "qiskit",  # 关键修复：确保Backend字段总是存在
            "Sites": {"Type": "Qubit", "PauliConvention": "±1 eigenvalues"},
            "DType": "Float64",
            "Indexing": {"Convention": "python-0"},
            "HamiltonianForm": "H = -J Σ Z_i Z_{i+1} - h Σ X_i",
            "Assumptions": assumptions,
            "contract_version": CONTRACT_VERSION
        }
        
        warnings = []  # 保持简洁
        
        result = {"SpecIR": spec_ir, "warnings": warnings}
        
        # 可选文件输出
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            spec_file = os.path.join(output_dir, "spec.json")
            with open(spec_file, "w") as f:
                json.dump(spec_ir, f, indent=2)
        
        return result


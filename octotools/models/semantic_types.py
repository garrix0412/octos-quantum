# octotools/models/semantic_types.py
from typing import Dict, List, Set, Tuple

class SemanticTypes:
    """标准语义类型定义"""
    
    # 核心语义类型
    SPEC = "spec"   # 问题规格：也就是上下文传递的问题参数
    HAMILTONIAN = "hamiltonian" 
    ANSATZ = "ansatz"
    OPTIMIZER = "optimizer"
    ESTIMATOR = "estimator"
    VQE_EXECUTION = "vqe_execution"
    COMPLETE_SOLUTION = "complete_solution"
    
    # 语义类型的依赖关系图
    DEPENDENCIES = {
        SPEC: [],
        HAMILTONIAN: [SPEC],
        ANSATZ: [SPEC], 
        OPTIMIZER: [SPEC],
        ESTIMATOR: [SPEC],
        VQE_EXECUTION: [HAMILTONIAN, ANSATZ, OPTIMIZER, ESTIMATOR],
        COMPLETE_SOLUTION: [VQE_EXECUTION]
    }
    
    # 工具到语义类型的映射
    TOOL_SEMANTIC_MAPPING = {
        "Qiskit_TFIM_Spec_Tool": SPEC,
        "Qiskit_TFIM_Hamiltonian_Tool": HAMILTONIAN,
        "Qiskit_TFIM_Ansatz_Tool": ANSATZ,
        "Qiskit_TFIM_Optimizer_Tool": [OPTIMIZER, ESTIMATOR],
        "Qiskit_VQE_Tool": VQE_EXECUTION,
        "qiskit_Code_Assembler_Tool": COMPLETE_SOLUTION
    }

def topological_sort(types_to_sort: List[str]) -> List[str]:    #确保代码片段的输入输出是正确的
    """简单的拓扑排序"""
    dependencies = SemanticTypes.DEPENDENCIES
    result = []
    remaining = set(types_to_sort)
    
    while remaining:
        ready = []
        for stype in remaining:
            deps = dependencies.get(stype, [])
            if all(dep not in remaining for dep in deps):
                ready.append(stype)
        
        if not ready:
            ready = [min(remaining)]  # 防止死循环
        
        for stype in ready:
            result.append(stype)
            remaining.remove(stype)
    
    return result

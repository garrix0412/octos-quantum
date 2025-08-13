#!/usr/bin/env python3
"""测试notebook环境下的octotools导入和路径解析"""

import sys
import os
from pathlib import Path

def test_notebook_import():
    """模拟notebook中的导入过程"""
    print("=== Notebook环境测试 ===")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"当前Python路径: {sys.path[:5]}")
    
    # 方案1：直接导入（如原notebook）
    try:
        from octotools.solver import construct_solver
        print("✓ 方案1成功：直接导入octotools")
        return True
    except ImportError as e:
        print(f"✗ 方案1失败：{e}")
    
    # 方案2：添加相对路径
    try:
        notebook_dir = Path.cwd()
        octo_root = notebook_dir.parent.parent
        sys.path.insert(0, str(octo_root))
        print(f"添加路径: {octo_root}")
        
        from octotools.solver import construct_solver
        print("✓ 方案2成功：添加相对路径后导入")
        return True
    except ImportError as e:
        print(f"✗ 方案2失败：{e}")
    
    # 方案3：添加octotools目录
    try:
        octotools_dir = octo_root / "octotools"
        sys.path.insert(0, str(octotools_dir))
        print(f"添加octotools目录: {octotools_dir}")
        
        from solver import construct_solver
        print("✓ 方案3成功：添加octotools目录后导入")
        return True
    except ImportError as e:
        print(f"✗ 方案3失败：{e}")
    
    return False

def test_path_resolution():
    """测试路径解析功能"""
    print("\n=== 路径解析测试 ===")
    
    try:
        # 导入成功后测试路径解析
        from octotools.models.initializer import Initializer
        
        # 创建Initializer实例但不完全初始化
        init = Initializer.__new__(Initializer)
        
        # 测试get_project_root
        root_path = init.get_project_root()
        print(f"✓ get_project_root()返回: {root_path}")
        
        # 验证路径正确性
        solver_py = os.path.join(root_path, 'solver.py')
        tools_dir = os.path.join(root_path, 'tools')
        
        print(f"✓ solver.py存在: {os.path.exists(solver_py)}")
        print(f"✓ tools目录存在: {os.path.exists(tools_dir)}")
        
        # 检查期望路径
        expected = "/Users/garrixma/Desktop/octo/octotools"
        if root_path == expected:
            print("✅ 路径解析完全正确!")
            return True
        else:
            print(f"⚠️  路径不匹配。期望: {expected}, 实际: {root_path}")
            return False
            
    except Exception as e:
        print(f"✗ 路径解析测试失败: {e}")
        return False

if __name__ == "__main__":
    import_success = test_notebook_import()
    if import_success:
        path_success = test_path_resolution()
        if path_success:
            print("\n🎉 所有测试通过！路径问题已完全修复。")
        else:
            print("\n⚠️  导入成功但路径解析有问题。")
    else:
        print("\n❌ 导入失败，无法进行路径测试。")
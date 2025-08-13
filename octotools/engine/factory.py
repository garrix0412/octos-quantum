from typing import Any

"""
它是LLM 引擎工厂，根据你传入的 model_string 决定用哪个后端类
"""

def create_llm_engine(model_string: str, use_cache: bool = False, is_multimodal: bool = True, **kwargs) -> Any:
    """
    Factory function to create appropriate LLM engine instance.
    """
    # model_string: 约定好的一段字符串，用来判定后端
    # use_cache: 引擎内部是否启用响应缓存（具体实现看各引擎类）。


    if "azure" in model_string:
        from .azure import ChatAzureOpenAI
        model_string = model_string.replace("azure-", "")
        return ChatAzureOpenAI(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)

    elif any(x in model_string for x in ["gpt", "o1", "o3", "o4"]):
        from .openai import ChatOpenAI
        return ChatOpenAI(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)



    elif "vllm" in model_string:
        from .vllm import ChatVLLM
        model_string = model_string.replace("vllm-", "")
        return ChatVLLM(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)


    elif "together" in model_string:
        from .together import ChatTogether
        model_string = model_string.replace("together-", "")
        return ChatTogether(model_string=model_string, use_cache=use_cache, is_multimodal=is_multimodal, **kwargs)



    else:
        raise ValueError(
            f"Engine {model_string} not supported. "
            "If you are using Azure OpenAI models, please ensure the model string has the prefix 'azure-'. "
            "For Together models, use 'together-'. For VLLM models, use 'vllm-'. For LiteLLM models, use 'litellm-'. "
            "For Ollama models, use 'ollama-'. "
            "For other custom engines, you can edit the factory.py file and add its interface file. "
            "Your pull request will be warmly welcomed!"
        )
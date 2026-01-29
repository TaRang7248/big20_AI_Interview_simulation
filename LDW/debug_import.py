
import sys
import importlib

print(sys.executable)
try:
    import langchain_community
    print(f"langchain_community file: {langchain_community.__file__}")
    print(f"langchain_community version: {langchain_community.__version__}")
    
    try:
        from langchain_community.chat_message_histories import ChatMessageHistory
        print("Import langchain_community.chat_message_histories.ChatMessageHistory successful")
    except ImportError as e:
        print(f"Import ChatMessageHistory failed: {e}")

except ImportError as e:
    print(f"Import langchain_community failed: {e}")

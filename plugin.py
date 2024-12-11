import os
from binaryninja import PluginCommand, BinaryView, log_info, show_message_box, MessageBoxButtonSet, MessageBoxIcon
from .ollama_client import OllamaClient
from .ui import OllamaConnectionDialog, OllamaModelDialog

def set_server_dialog(bv):
    """
    Display a dialog to set the server connection details for the Ollama client.

    Args:
        bv (BinaryView): The current BinaryView instance.

    Returns:
        bool: True if the server details were set successfully, False otherwise.
    """
    client = OllamaClient(bv)
    dialog = OllamaConnectionDialog(client.get_host(), client.get_port())
    if dialog.exec_():
        host = dialog.host.text()
        port = dialog.port.text()
        client.set_host(host)
        client.set_port(port)
        client.init_client()
        return True
    return False

def set_model_dialog(bv):
    """
    Display a dialog to set the model for the Ollama client.

    Args:
        bv (BinaryView): The current BinaryView instance.

    Returns:
        bool: True if the model was set successfully, False otherwise.
    """
    ollama_models = {
    "gemma2:latest": 8192,
    "mistral-nemo:latest":  (1024000/8), 
    "llama3.2:latest": (131072/2),
    "deepseek-coder-v2:latest": (163840/4),#163840
    "mistral:latest":  32768,
    "phi3.5:latest": (131072/2)
    } 

    client = OllamaClient(bv)
    if not client.is_set():
        set_server_dialog(bv)
    model_dialog = OllamaModelDialog(client.get_model(), client.get_available_models(), client.get_contextlength())
    if model_dialog.exec_():
        model = model_dialog.model_combo.currentText()
        client.set_model(model)
        num_ctx = ollama_models.get(model, client.get_contextlength()) 
        client.set_num_ctx(num_ctx)
        return True
    return False

def rename_function_variables_command(bv, func):
    """
    Rename the variables of a function using the Ollama client.

    Args:
        bv (BinaryView): The current BinaryView instance.
        func (Function): The function whose variables are to be renamed.
    """
    client = OllamaClient(bv)
    if not client.is_set():
        set_model_dialog(bv)
    client.rename_function_variables(func)

def rename_variable_command(bv, inst):
    """
    Rename a target variable using the Ollama client.

    Args:
        bv (BinaryView): The current BinaryView instance.
        inst (Instruction): The instruction containing the variable to be renamed.
    """
    client = OllamaClient(bv)
    if not client.is_set():
        set_model_dialog(bv)
    client.rename_target_variable(inst)

def rename_function_HLIL_command(bv, func):
    """
    Rename a function using the Ollama client based on its HLIL representation.

    Args:
        bv (BinaryView): The current BinaryView instance.
        func (Function): The function to be renamed.
    """
    client = OllamaClient(bv)
    if not client.is_set():
        set_model_dialog(bv)
    client.rename_target_function(func)

def rename_all_functions_command(bv):
    """
    Rename all functions in the current BinaryView using the Ollama client.

    Args:
        bv (BinaryView): The current BinaryView instance.
    """
    client = OllamaClient(bv)
    if not client.is_set():
        set_model_dialog(bv)
    client.rename_all_functions()

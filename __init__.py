from .plugin import *

PluginCommand.register(r"Ollama\Rename all functions", "Rename all functions based on (HLIL)", rename_all_functions_command)

PluginCommand.register_for_high_level_il_function(r"Ollama\Rename target function", "Rename target function based on (HLIL)",
                            rename_function_HLIL_command)

PluginCommand.register_for_high_level_il_function(r"Ollama\Rename all function variables", "Rename target function variables based on (HLIL)",
                            rename_function_variables_command)

PluginCommand.register_for_high_level_il_instruction(r"Ollama\Rename target variable", "Rename target variable based on (HLIL)",
                            rename_variable_command)

PluginCommand.register(r"Ollama\Settings\Set ollama model", "set the model you want to run", set_model_dialog)

PluginCommand.register(r"Ollama\Settings\Set ollama server", "set the server where you want to access ollama", set_server_dialog)


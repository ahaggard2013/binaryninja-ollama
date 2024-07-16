from binaryninja import PluginCommand, BackgroundTaskThread, log_info, show_message_box, MessageBoxButtonSet, MessageBoxIcon
from .utils import traverse_functions_bottom_up

class RenameAllFunctions(BackgroundTaskThread):
    """
    A background task to rename all functions in the current BinaryView.

    Attributes:
        client (OllamaClient): The Ollama client instance.
        bv (BinaryView): The current BinaryView instance.
    """
    def __init__(self, client, bv):
        """
        Initialize the RenameAllFunctions task.

        Args:
            client (OllamaClient): The Ollama client instance.
            bv (BinaryView): The current BinaryView instance.
        """
        super().__init__("Starting renaming task...", True)
        self.bv = bv
        self.client = client

    def run(self):
        """
        Execute the task to rename all functions in the BinaryView.
        """
        self.bv.begin_undo_actions()
        sorted_functions = traverse_functions_bottom_up(self.bv)
        name_counter = {}

        for function in sorted_functions:
            if function.hlil_if_available == None:
                continue

            if function.name.startswith("sub_") or function.name.startswith("func_"):  # Ignore functions that are already named
                hlil = function.hlil
                function_hlil = "\n".join([str(instr) for instr in hlil.instructions])
                new_name = self.client.get_function_name(function_hlil)

                if new_name:
                    if new_name in name_counter:
                        name_counter[new_name] += 1
                        new_name = f"{new_name}_{name_counter[new_name]}"
                    else:
                        name_counter[new_name] = 1
                    self.progress = f'Renamed {function.name} to {new_name}'
                    log_info(f'Renamed {function.name} to {new_name}')
                    function.name = new_name
                else:
                    self.progress = f"Ollama didn't identify a proper name for {function.name}"
                    log_info(f"Ollama didn't identify a proper name for {function.name}")
        self.bv.commit_undo_actions()

class RenameFunction(BackgroundTaskThread):
    """
    A background task to rename a function in the current BinaryView.

    Attributes:
        client (OllamaClient): The Ollama client instance.
        bv (BinaryView): The current BinaryView instance.
        hlil (HighLevelILFunction): The HighLevelIL representation of the function.
    """
    def __init__(self, client, bv, hlil):
        """
        Initialize the RenameFunction task.

        Args:
            client (OllamaClient): The Ollama client instance.
            bv (BinaryView): The current BinaryView instance.
            hlil (HighLevelILFunction): The HighLevelIL representation of the function.
        """
        super().__init__("Starting renaming task...", True)
        self.hlil = hlil
        self.bv = bv
        self.client = client

    def run(self):
        """
        Execute the task to rename the function in the BinaryView.
        """
        self.bv.begin_undo_actions()
        function_hlil = "\n".join([str(instr) for instr in self.hlil.instructions])
        new_name = self.client.get_function_name(function_hlil)
        if new_name:
            self.progress = f"Renamed function to {new_name}."
            log_info(f"Renamed function to {new_name}.")
            self.hlil.source_function.name = new_name.strip()
        else:
            self.progress = f"ollama didn't identify a proper name"
            log_info(f"ollama didn't identify a proper name")
        self.bv.commit_undo_actions()


class RenameFunctionVariables(BackgroundTaskThread):
    """
    A background task to rename variables in a function in the current BinaryView.

    Attributes:
        client (OllamaClient): The Ollama client instance.
        bv (BinaryView): The current BinaryView instance.
        hlil (HighLevelILFunction): The HighLevelIL representation of the function.
    """
    def __init__(self, client, bv, hlil):
        """
        Initialize the RenameFunctionVariables task.

        Args:
            client (OllamaClient): The Ollama client instance.
            bv (BinaryView): The current BinaryView instance.
            hlil (HighLevelILFunction): The HighLevelIL representation of the function.
        """
        super().__init__("Starting renaming task...", True)
        self.hlil = hlil
        self.bv = bv 
        self.client = client

    def run(self):
        """
        Execute the task to rename variables in the function in the BinaryView.
        """
        self.bv.begin_undo_actions()
        function_hlil = "\n".join([str(instr) for instr in self.hlil.instructions])

        vars = []
        for inst in self.hlil.instructions:
            for var in inst.vars:
                vars.append(var)

        unique_vars = list(set(vars))
        name_counter = {}

        for var in unique_vars:
            name = self.client.get_variable_name(var, function_hlil)
            if name:
                if name in name_counter:
                    name_counter[name] += 1
                    name = f"{name}_{name_counter[name]}"
                else:
                    name_counter[name] = 1
                self.progress = f'Renamed {var.name} to {name}'
                log_info(f'Renamed {var.name} to {name}') 
                var.name = name
            else:
                self.progress = f"ollama didn't identify a proper name for {var.name}"
                log_info(f"ollama didn't identify a proper name for {var.name}")
        self.bv.commit_undo_actions()

class RenameVariable(BackgroundTaskThread):
    """
    A background task to rename a specific variable in the current BinaryView.

    Attributes:
        client (OllamaClient): The Ollama client instance.
        bv (BinaryView): The current BinaryView instance.
        inst (Instruction): The instruction containing the variable to be renamed.
    """
    def __init__(self, client, bv, inst):
        """
        Initialize the RenameVariable task.

        Args:
            client (OllamaClient): The Ollama client instance.
            bv (BinaryView): The current BinaryView instance.
            inst (Instruction): The instruction containing the variable to be renamed.
        """
        super().__init__("Starting renaming task...", True)
        self.inst = inst
        self.bv = bv 
        self.client = client

    def run(self):
        """
        Execute the task to rename the variable in the BinaryView.
        """
        self.bv.begin_undo_actions()
        func = self.bv.get_functions_containing(self.inst.address)[0]
        function_hlil = "\n".join([str(instr) for instr in func.hlil.instructions])

        unique_vars = list(set(self.inst.vars))
        for var in unique_vars:
            name = self.client.get_variable_name(var, function_hlil) 
            if name:
                self.progress = f'Renamed {var.name} to {name}'
                log_info(f'Renamed {var.name} to {name}') 
                var.name = name
            else:
                self.progress = f"Ollama didn't identify a proper name for {var.name}"
                log_info(f"Ollama didn't identify a proper name for {var.name}")
        self.bv.commit_undo_actions()

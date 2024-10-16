from ollama import Client
from binaryninja import log_info
from .rename_tasks import RenameAllFunctions, RenameVariable, RenameFunction, RenameFunctionVariables


class OllamaClient:
    """
    A singleton class to interact with the Ollama server for renaming functions and variables.
    """
    _instance = None

    def __new__(cls, bv):
        """
        Ensure that only one instance of the class is created.

        Args:
            bv (BinaryView): The current BinaryView instance.

        Returns:
            OllamaClient: The single instance of the OllamaClient class.
        """
        if cls._instance is None:
            cls._instance = super(OllamaClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, bv):
        """
        Initialize the OllamaClient instance.

        Args:
            bv (BinaryView): The current BinaryView instance.
        """
        if not self._initialized:
            self.bv = bv
            self.host = None
            self.port = None
            self.client = None
            self.model = None
            self.contextlength = None 
            self._initialized = True

    def get_host(self):
        """
        Get the current host.

        Returns:
            str: The current host.
        """
        return self.host

    def get_port(self):
        """
        Get the current port.

        Returns:
            str: The current port.
        """
        return self.port

    def get_model(self):
        """
        Get the current model.

        Returns:
            str: The current model.
        """
        return self.model

    def get_contextlength(self):
        return self.contextlength

    def set_host(self, host):
        """
        Set the host.

        Args:
            host (str): The host to be set.
        """
        self.host = host

    def set_port(self, port):
        """
        Set the port.

        Args:
            port (str): The port to be set.
        """
        self.port = port 

    def set_model(self, model):
        """
        Set the model.

        Args:
            model (str): The model to be set.
        """
        self.model = model

    def set_num_ctx(self, contextlength):
        """
        Set the number of context length tokens

        Args: contextlength (int): Context length to be set.
        """
        self.contextlength = contextlength
    
    def init_client(self):
        """
        Initialize the Ollama client.
        """
        if self.host is not None and self.port is not None:
            self.client = Client(host=f"{self.host}:{self.port}")

    def is_set(self):
        """
        Check if the host, port, and model are set.

        Returns:
            bool: True if all are set, False otherwise.
        """
        if all(x is not None for x in (self.host, self.port, self.model)):
            return True
        return False

    def get_available_models(self):
        """
        Get the available models from the Ollama server.

        Returns:
            list: A list of available models.
        """
        if self.host is not None and self.port is not None:
            return [model['name'] for model in self.client.list()['models']]

    def get_variable_name(self, variable, hlil):
        """
        Get a suggested name for a variable.

        Args:
            variable (str): The current variable name.
            hlil (str): The HLIL decompiled code snippet.

        Returns:
            str: The suggested variable name.
        """
        prompt = (
                     f"In one word, what should the variable '{variable}' be named in the below Function? "
                     f"The name must meet the following criteria: all lowercase letters, usable in Python code"
        )
        options={'num_ctx': self.contextlength}
        prompt += f"Function:\n{hlil}\n\n"
        response = self.generate(
            model=self.model,
            prompt=prompt,
            stream=False,
            options=options
        ) 
        variable_name = response['response']
        
        # Check if the variable name is a single word with no spaces
        if " " not in variable_name.strip():
            return variable_name.strip()
        else:
            return None

    def get_function_name(self, hlil):
        """
        Get a suggested name for a function.

        Args:
            hlil (str): The HLIL decompiled code snippet.

        Returns:
            str: The suggested function name.
        """
        prompt = (
            f"Given the following HLIL decompiled code snippet, provide a Python-style function name that describes what the code is doing. "
            f"The name must meet the following criteria: all lowercase letters, usable in Python code, with underscores between words. "
            f"Only return the function name and no other explanation or text data included."
        )
        options={'num_ctx': self.contextlength}
        prompt += f"Function:\n{hlil}\n\n"
        response = self.generate(
            model=self.model,
            prompt=prompt,
            stream=False,
            options=options
        ) 
        function_name = response['response']
        
        # Check if the function name is a single word with no spaces
        if " " not in function_name.strip():
            return function_name.strip()
        else:
            return None
    
    def generate(self, model, prompt, stream, options):
        """
        Generate a response from the Ollama server.

        Args:
            model (str): The model to be used.
            prompt (str): The prompt to be sent.
            stream (bool): Whether to stream the response.

        Returns:
            dict: The response from the server.
        """
        return self.client.generate(model=model, prompt=prompt, stream=stream, options=options)

    def rename_function_variables(self, hlil):
        """
        Rename the variables of a function.

        Args:
            hlil (str): The HLIL decompiled code snippet.
        """
        rename_function_variables = RenameFunctionVariables(self, self.bv, hlil)
        rename_function_variables.start()

    def rename_target_variable(self, inst):
        """
        Rename a target variable.

        Args:
            inst (Instruction): The instruction containing the variable to be renamed.
        """
        rename_target_variable = RenameVariable(self, self.bv, inst)
        rename_target_variable.start()

    def rename_target_function(self, hlil):
        """
        Rename a target function.

        Args:
            hlil (str): The HLIL decompiled code snippet.
        """
        rename_target_function = RenameFunction(self, self.bv, hlil)
        rename_target_function.start()

    def rename_all_functions(self):
        """
        Rename all functions in the current BinaryView.
        """
        rename_all_functions = RenameAllFunctions(self, self.bv)
        rename_all_functions.start()


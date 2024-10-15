from PySide5.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox, QComboBox

class OllamaConnectionDialog(QDialog):
    """
    A dialog to set the connection settings for the Ollama client.

    Attributes:
        host (QLineEdit): A QLineEdit widget for the host input.
        port (QLineEdit): A QLineEdit widget for the port input.
    """
    def __init__(self, host, port):
        """
        Initialize the OllamaConnectionDialog.

        Args:
            host (str): The initial host value.
            port (str): The initial port value.
        """
        super().__init__()
        self.setWindowTitle("Ollama Client Settings")

        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Host:"))
        if host is not None:
            self.host = QLineEdit(host)
        else:
            self.host = QLineEdit("http://localhost")
        layout.addWidget(self.host)

        layout.addWidget(QLabel("Port:"))
        if port is not None:
            self.port = QLineEdit(port)
        else:
            self.port = QLineEdit("11433")
        layout.addWidget(self.port)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

class OllamaModelDialog(QDialog):
    """
    A dialog to select the model for the Ollama client.

    Attributes:
        model_combo (QComboBox): A QComboBox widget to display available models.
    """
    def __init__(self, cur_model, models, num_ctx):
        """
        Initialize the OllamaModelDialog.

        Args:
            cur_model (str): The currently selected model.
            models (list): A list of available models.
        """
        super().__init__()
        self.setWindowTitle("Ollama Available Models")

        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("Models:"))
        self.model_combo = QComboBox()
        self.model_combo.addItems(models)
        if cur_model is not None:
            self.model_combo.setCurrentIndex(self.model_combo.findText(cur_model))
        layout.addWidget(self.model_combo)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        layout.addWidget(QLabel("Context Length: placebo edition"))
        layout.addWidget(QLineEdit())

        self.setLayout(layout)

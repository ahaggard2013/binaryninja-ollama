[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/ahaggard)

# BinaryNinja-Ollama

Ollama is a tool that allows you to pull open source AI models and run them locally.
Some models require extensive computing power, while others can be ran on your personal laptop.
Results will vary greatly depending on the model you choose to use :).

Why use this over sidekick/openai?
1. It's FREE and easy to setup locally.
2. Did I say it's FREE?
3. FREEE!
4. It can be ran anywhere without internet!
5. Your data kept between you and your ollama server with no third party.

# Features
This plugin integrates Ollama with Binary Ninja and supports the actions listed below:

- Setting which server/port binary ninja should use to connect to ollama.
  - Have a (very) high powered gaming PC? Use it to host ollama and point binja to llama3:70b/gemma2:27b.
  - Running this on a laptop? Host it locally, set it to localhost and run gemma2:latest/llama3:latest.
  - There are tons of other models to try, but I've primarily tested this with varients of llama3/gemma2 with decent results.
- Query your locally hosted ollama server to determine what a given function does.
  - This can be utilized to rename all function in bulk, or individually targeted functions.
- Allows users to rename variables in HLIL using ollama.
  - This can be utilized to rename individual variables within an instruction.
  - This can be used to rename all variables within a function.

# Installation

If you're installing this as a standalone plugin, you can place (or sym-link)
this in Binary Ninja's plugin path. Default paths are detailed on
[Vector 35's documentation](https://docs.binary.ninja/guide/plugins.html).

# Dependencies

- Python 3.10+
- `ollama` installed with `pip3 install ollama`

# Ollama Server 

This requires you to have access to or host your own ollama server and pull down any models you would like to use.

Follow the instructions on https://ollama.com to setup your server and pull any models you would like to try.
Once this is done a server should be automatically started and accessed via localhost:11434.

# Usage

## Rename all function variables

The rename all function variables option will parse all varaibles within a function and attempt to rename them based on the following prompt:

```
prompt = (
             f"In one word, what should the variable '{variable}' be named in the below Function? "
             f"The name must meet the following criteria: all lowercase letters, usable in Python code"
)

```

![Before variables renaming](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/ls-rename-all-variables-before.png?raw=true)
![After variables renaming](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/ls-rename-all-variables-after.png?raw=true)

## Rename all functions
The rename all functions option will loop through all functions, smallest to largest, within a binaryview and rename them based on the prompt:

```
prompt = (
    f"Given the following HLIL decompiled code snippet, provide a Python-style function name that describes what the code is doing. "
    f"The name must meet the following criteria: all lowercase letters, usable in Python code, with underscores between words. "
    f"Only return the function name and no other explanation or text data included."
)
```

![Before functions renaming](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/ls-rename-all-func-before.png?raw=true)
![After functions renaming](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/ls-rename-all-func-after.png?raw=true)
![After functions renaming](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/ls-rename-all-func-after2.png?raw=true)

## Rename target function
Renaming a target function uses the same prompt as renaming all functions, but limits it the selected function when triggering the plugin.

## Rename target function variable
Renaming a target variable uses the same prompt as renaming all variables, but limits it the selected function when triggering the plugin.

## Settings
Settings is triggered at the first call to any renaming operation when binary ninja is first started, or by triggering it manually. The appplied settings will persist within a binary ninja session.

The settings window allows you to set the IP, port, and model to use within ollama. Only downloaded models are selectable.


![Plugin settings option](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/settings-options.png?raw=true)
![Plugin connection options](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/settings-connection.png?raw=true)
![Plugin model options](https://github.com/ahaggard2013/binaryninja-ollama/blob/main/resources/settings-model.png?raw=true)

## Known Issues
- On larger functions AI will ignore the prompt and return large blocks of text describing the function. This is mitigated by ignoring the returned value and throwing a "can't rename function' log, but could be further investigated
-The chosen server being non-existent could be handled better.

## Feature Request
- Anything you are intesested in that is not included? 
    - Open an issue!
    - Make a pull request.

- Ideas:
    - Improved 'all function' renaming (see code comments)
    - create comments describing code functionality
    - Structure Recovery

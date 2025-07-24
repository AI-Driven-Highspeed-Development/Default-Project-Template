# Default Project Template for AI Driven Highspeed Development Framework

This is the default project template for the ADHD (AI-Driven High-speed Development) Framework. It provides a complete setup for rapid project initialization, module management, and development workflow automation.

## Features

- 🚀 **Project Initialization**: Automatically clone and set up project modules from git repositories
- 🔄 **Module Refresh**: Update and refresh existing modules with new versions
- 📦 **Module Management**: Discover, list, and manage project modules
- ⚙️ **Configuration-Driven**: YAML-based configuration for easy customization
- 🎯 **Dependency Resolution**: Recursive dependency handling for complex projects

## Quick Start

### Using the CLI

The ADHD CLI provides a simple interface to all framework functionality:

```bash
# Initialize a new project
python adhd_cli.py init

# Initialize with custom config
python adhd_cli.py init --config my-config.yaml

# List all discovered modules
python adhd_cli.py list

# Refresh all modules
python adhd_cli.py refresh

# Refresh specific module
python adhd_cli.py refresh --module config-manager

# Show detailed module information
python adhd_cli.py info --module config-manager

# Get help
python adhd_cli.py --help
python adhd_cli.py init --help
```

### Direct Script Usage (Legacy)

You can still use the scripts directly if needed:

```bash
# Initialize project
python framework/project_init.py

# Refresh all modules
python framework/project_refresh.py

# Refresh specific module
python framework/project_refresh.py module_name
```

## Configuration

Create an `init.yaml` file in your project root to specify modules to install:

```yaml
modules:
  - https://github.com/AI-Driven-Highspeed-Development/Config-Manager.git
  - https://github.com/AI-Driven-Highspeed-Development/Logger-Util.git
  - https://github.com/AI-Driven-Highspeed-Development/Path-Resolver-Util.git
```

## Project Structure

After initialization, your project will have the following structure:

```
your-project/
├── adhd_cli.py           # Main CLI interface
├── init.yaml             # Project configuration
├── framework/            # Core framework modules
│   ├── __init__.py
│   ├── modules_control.py
│   ├── project_init.py
│   └── project_refresh.py
├── managers/             # Management modules
├── utils/                # Utility modules
└── plugins/              # Plugin modules
```

## Module Features

Each module can provide the following capabilities:

- ✅ **Init**: Automatic initialization via `__init__.py`
- 🔄 **Refresh**: Update capability via `refresh.py`
- ⚙️ **Config**: Configuration via `init.yaml`

## CLI Commands

### `init`
Initialize a new ADHD project by cloning and setting up modules from the configuration file.

**Options:**
- `--config, -c`: Path to YAML configuration file (default: init.yaml)
- `--clone-dir`: Directory for temporary clones (default: clone_temp)

### `refresh`
Refresh project modules to update them with the latest changes.

**Options:**
- `--module, -m`: Refresh specific module by name

### `list`
List all discovered modules and their capabilities.

### `info`
Show detailed information about a specific module.

**Options:**
- `--module, -m`: Module name to show information for (required)

## Examples

### Basic Project Setup
```bash
# 1. Create project directory
mkdir my-adhd-project
cd my-adhd-project

# 2. Copy this template
cp -r /path/to/Default-Project-Template/* .

# 3. Customize init.yaml with your modules
nano init.yaml

# 4. Initialize project
python adhd_cli.py init
```

### Working with Modules
```bash
# See what modules are available
python adhd_cli.py list

# Get detailed info about a module
python adhd_cli.py info --module config-manager

# Refresh a specific module after updates
python adhd_cli.py refresh --module config-manager

# Refresh all modules
python adhd_cli.py refresh
```

## Troubleshooting

### Import Errors
If you encounter import errors, ensure you're running commands from the project root directory where `adhd_cli.py` is located.

### Module Not Found
Use `python adhd_cli.py list` to see available modules and their exact names.

### Permission Issues
Make sure the CLI script is executable:
```bash
chmod +x adhd_cli.py
```

## Contributing

This template is part of the ADHD Framework ecosystem. For contributions and issues, please refer to the main framework repository.

## License

See LICENSE file for details.
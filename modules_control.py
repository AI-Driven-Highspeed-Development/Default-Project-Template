import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional

class ModulesController:
    """Controller for managing and providing information about project modules."""
    
    def __init__(self):
        self.base_dirs = ["managers", "utils", "plugins"]
        self.modules_info = {}
        self._scan_modules()
    
    def _scan_modules(self):
        """Scan for modules in the base directories."""
        # print("Scanning for modules...")  # Uncomment for debugging
        
        for base_dir in self.base_dirs:
            if os.path.exists(base_dir):
                self._scan_directory(base_dir)
        
        # print(f"Found {len(self.modules_info)} modules")  # Uncomment for debugging
    
    def _scan_directory(self, directory: str):
        """Scan a specific directory for modules."""
        for item in os.listdir(directory):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                module_info = self._get_module_info(item_path)
                if module_info:
                    self.modules_info[item_path] = module_info
    
    def _get_module_info(self, module_path: str) -> Optional[Dict]:
        """Get information about a specific module."""
        info = {
            "path": module_path,
            "name": os.path.basename(module_path),
            "has_init": os.path.exists(os.path.join(module_path, "__init__.py")),
            "has_refresh": os.path.exists(os.path.join(module_path, "refresh.py")),
            "has_config": os.path.exists(os.path.join(module_path, "init.yaml")),
        }
        
        # Try to read init.yaml for additional information
        init_yaml_path = os.path.join(module_path, "init.yaml")
        if os.path.exists(init_yaml_path):
            try:
                with open(init_yaml_path, 'r') as file:
                    yaml_data = yaml.safe_load(file)
                    if yaml_data:
                        info.update({
                            "folder_path": yaml_data.get("folder_path", ""),
                            "type": yaml_data.get("type", ""),
                            "requirements": yaml_data.get("requirement", []),
                        })
            except Exception as e:
                print(f"Warning: Failed to read init.yaml for {module_path}: {e}")
        
        return info
    
    def get_all_modules(self) -> Dict:
        """Get information about all discovered modules."""
        return self.modules_info
    
    def get_modules_with_refresh(self) -> List[str]:
        """Get paths of all modules that have refresh.py files."""
        return [path for path, info in self.modules_info.items() if info.get("has_refresh", False)]
    
    def get_module_info(self, module_path: str) -> Optional[Dict]:
        """Get information about a specific module."""
        return self.modules_info.get(module_path)
    
    def list_modules(self):
        """Print a formatted list of all modules."""
        if not self.modules_info:
            print("No modules found.")
            return
        
        print(f"\nFound {len(self.modules_info)} modules:")
        print("-" * 80)
        
        for path, info in self.modules_info.items():
            print(f"📁 {info['name']} ({path})")
            if info.get("type"):
                print(f"   📂 Type: {info['type']}")
            if info.get("description"):
                print(f"   📝 {info['description']}")
            if info.get("version"):
                print(f"   📦 Version: {info['version']}")
            if info.get("folder_path"):
                print(f"   🎯 Target Path: {info['folder_path']}")
            
            # Show requirements if they exist
            requirements = info.get("requirements", [])
            if requirements:
                print(f"   🔗 Requirements:")
                for req in requirements:
                    print(f"      • {req}")
            
            features = []
            if info.get("has_init"):
                features.append("✅ Init")
            if info.get("has_refresh"):
                features.append("🔄 Refresh")
            if info.get("has_config"):
                features.append("⚙️  Config")
            
            if features:
                print(f"   🔧 Features: {', '.join(features)}")
            print()

def get_modules_controller() -> ModulesController:
    """Get the modules controller instance."""
    return ModulesController()

if __name__ == "__main__":
    controller = ModulesController()
    controller.list_modules()

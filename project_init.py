from typing import List
import yaml
import os
import subprocess
import sys
from pathlib import Path
import shutil
from modules_control import ModulesController

class ProjectInitializer:
    """A class to handle the initialization of a project by cloning repositories."""
    
    def __init__(self, yaml_file="init.yaml", clone_dir="clone_temp"):
        print(f"\n{'='*60}")
        print("🚀 ADHD PROJECT INITIALIZATION")
        print(f"{'='*60}")
        print("📂 Creating project directory structure...")
        
        os.makedirs("managers", exist_ok=True)
        os.makedirs("utils", exist_ok=True)
        os.makedirs("plugins", exist_ok=True)
        print("✅ Directory structure ready")
        
        self.yaml_loader = InitYamlLoader(yaml_file)
        repo_urls = self.yaml_loader.load_modules()
        if repo_urls:
            self.rc = RepositoryCloner(repo_urls, clone_dir)
        else:
            print("\n⚠️  No repositories to clone.")
        
        self.modules_placer = ModulesPlacer(clone_dir)
        modules_paths = self.modules_placer.place_modules()
        
        # Use ModulesController to get better module information
        self.modules_controller = ModulesController()
        self.modules_initializer = ModulesInitializer(modules_paths, self.modules_controller)
        self.modules_initializer.initialize_modules()

        print(f"\n🧹 Cleaning up temporary files...")
        shutil.rmtree(clone_dir, ignore_errors=True)
        print("✅ Cleanup complete")
        
        print(f"\n{'='*60}")
        print("🎉 PROJECT INITIALIZATION COMPLETE!")
        print(f"{'='*60}")
        print("🎯 Your ADHD project template is ready to use!")
        print("📝 Check the modules above for available functionality.")
        print(f"{'='*60}")
        print("💡 Next steps:")
        print("   • Review the initialized modules")
        print("   • Configure settings as needed")
        print("   • Start building your project!")
        print(f"{'='*60}")

class ModulesInitializer:
    """A class to handle the initialization of modules."""
    def __init__(self, modules: List[str], modules_controller: ModulesController):
        self.modules = modules
        self.modules_controller = modules_controller

    def initialize_modules(self):
        """Initialize each module using ModulesController for better information."""
        print(f"\n{'='*60}")
        print("🔍 SCANNING MODULES AND CAPABILITIES")
        print(f"{'='*60}")
        
        # Get updated module information after placement
        self.modules_controller._scan_modules()  # Refresh module information
        all_modules_info = self.modules_controller.get_all_modules()
        
        uninitialized_modules = []
        
        for module_path in self.modules:
            # Get module info from controller
            module_info = all_modules_info.get(module_path, {})
            module_name = module_info.get('name', os.path.basename(module_path))
            module_type = module_info.get('type', '')
            
            # Calculate dynamic width based on content
            content_lines = [
                "🔧 INITIALIZING MODULE",
                f"📁 Module: {module_name}",
                f"📍 Path: {module_path}"
            ]
            
            if module_type:
                content_lines.append(f"📂 Type: {module_type}")
            
            # Find the longest content line and add padding
            max_content_width = max(len(line) for line in content_lines)
            table_width = max(max_content_width + 4, 60)  # Minimum 60 chars, +4 for padding and borders
            
            print(f"\n┌{'─'*table_width}┐")
            print(f"│ 🔧 INITIALIZING MODULE{' '*(table_width-24)} │")
            print(f"├{'─'*table_width}┤")
            
            print(f"│ 📁 Module: {module_name:<{table_width-13}} │")
            if module_info.get('type'):
                print(f"│ 📂 Type: {module_info['type']:<{table_width-11}} │")
            print(f"│ 📍 Path: {module_path:<{table_width-11}} │")
            print(f"└{'─'*table_width}┘")
            
            # Check for initialization capabilities
            has_init = module_info.get('has_init', False)
            
            initialized = False
            
            # Try __init__.py first if it exists
            if has_init:
                init_path = os.path.join(module_path, '__init__.py')
                try:
                    print(f"   🔄 Running __init__.py...")
                    subprocess.run([sys.executable, init_path], 
                                   capture_output=True,
                                   text=True,
                                   check=True)
                    print(f"   ✅ Successfully initialized {module_name}")
                    initialized = True
                except subprocess.CalledProcessError as e:
                    print(f"   ❌ Error initializing {module_name}: {e}")
                    uninitialized_modules.append(module_path)
            
            if not initialized and not has_init:
                print(f"   ℹ️  No initialization needed for {module_name}")
        
        # Summary
        print(f"\n{'='*60}")
        print("📊 INITIALIZATION SUMMARY")
        print(f"{'='*60}")
        
        if uninitialized_modules:
            print(f"❌ {len(uninitialized_modules)} modules could not be initialized:")
            for module in uninitialized_modules:
                print(f"   • {os.path.basename(module)}")
            print()
        
        successful_modules = len(self.modules) - len(uninitialized_modules)
        print(f"✅ {successful_modules} out of {len(self.modules)} modules processed successfully")
        
        # Show final module status
        print(f"\n{'='*60}")
        print("📋 FINAL MODULE STATUS")
        print(f"{'='*60}")
        self.modules_controller.list_modules()
                

class ModulesPlacer:
    """A class to handle placing modules in the appropriate directories."""
    
    def __init__(self, clone_dir="clone_temp"):
        self.clone_dir = clone_dir
        self.modules = []
    
    def _format_error_for_table(self, error_msg: str, table_width: int) -> str:
        """Format error message to fit in table, truncating if necessary."""
        max_width = table_width - 4  # Account for borders and padding
        if len(error_msg) <= max_width:
            return error_msg
        return error_msg[:max_width-3] + "..."
    
    def place_modules(self) -> List[str]:
        """Place cloned modules into the appropriate directories."""
        modules_dir = []
        
        for dir in os.listdir(self.clone_dir):
            full_path = os.path.join(self.clone_dir, dir)
            if os.path.isdir(full_path):
                modules_dir.append(full_path)
                
        if not modules_dir:
            print("⚠️  No modules found to place.")
            return
    
        print(f"\n{'='*60}")
        print("📦 MODULE PLACEMENT")
        print(f"{'='*60}")
        print(f"🔍 Found {len(modules_dir)} modules to place")
        
        for module_dir in modules_dir:
            module_info = self.read_module_inityaml(module_dir)
            module_name = os.path.basename(module_dir)
            
            # Calculate dynamic width based on content
            content_lines = [
                f"📁 Processing: {module_name}",
                "⚠️  Module already exists, skipping...",
                "✅ Successfully moved to target location",
                "⚠️  No init.yaml found, skipping module"
            ]
            
            if module_info:
                folder_path = module_info.get('folder_path', module_dir)
                content_lines.extend([
                    f"📂 Created directory: {folder_path}",
                    f"🎯 Target: {folder_path}"
                ])
            
            # Find the longest content line and add padding
            max_content_width = max(len(line) for line in content_lines)
            table_width = max(max_content_width + 4, 60)  # Minimum 60 chars, +4 for padding and borders
            
            print(f"\n┌{'─'*table_width}┐")
            print(f"│ 📁 Processing: {module_name:<{table_width-17}} │")
            print(f"├{'─'*table_width}┤")
            
            if module_info:
                folder_path = module_info.get('folder_path', module_dir)
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)
                    print(f"│ 📂 Created directory: {folder_path:<{table_width-23}} │")
                    
                print(f"│ 🎯 Target: {folder_path:<{table_width-13}} │")
                
                if os.path.exists(os.path.join(folder_path, os.path.basename(module_dir))):
                    print(f"│ ⚠️  Module already exists, skipping...{' '*(table_width-39)} │")
                else:
                    try:
                        os.rename(module_dir, folder_path)
                        print(f"│ ✅ Successfully moved to target location{' '*(table_width-43)} │")
                        self.modules.append(folder_path)    
                    except OSError as e:
                        error_msg = f"❌ Error moving module: {str(e)}"
            else:
                print(f"│ ⚠️  No init.yaml found, skipping module{' '*(table_width-39)} │")
            
            print(f"└{'─'*table_width}┘")

            if error_msg:
                print(error_msg)

        print(f"\n🎉 Module placement complete! Processed {len(self.modules)} modules.")
        return self.modules
    
    def read_module_inityaml(self, module_path):
        """Read the init.yaml file from a module directory."""
        init_yaml_path = os.path.join(module_path, 'init.yaml')
        if os.path.exists(init_yaml_path):
            try:
                with open(init_yaml_path, 'r') as file:
                    data = yaml.safe_load(file)
                    return data
            except yaml.YAMLError as e:
                # Format error message for display, allowing reasonable length
                yaml_error_msg = f"❌ Error parsing YAML: {str(e)}"
                # Truncate only if extremely long (over 80 chars) to avoid breaking table
                if len(yaml_error_msg) > 77:
                    yaml_error_msg = yaml_error_msg[:74] + "..."
                # Use minimum padding to accommodate varying table widths
                min_width = max(len(yaml_error_msg), 55)
                print(f"│ {yaml_error_msg:<{min_width}} │")
        else:
            print(f"│ ℹ️  No init.yaml configuration found               │")
        return None

class InitYamlLoader(yaml.SafeLoader):
    """A class to handle loading and parsing the init.yaml configuration file."""
    
    def __init__(self, yaml_file="init.yaml"):
        self.yaml_file = yaml_file
        self.modules = []
    
    def load_modules(self) -> List[str]:
        """
        Load the modules list from the YAML file.
        
        Returns:
            List[str]: List of repository URLs
        """
        print(f"\n{'='*60}")
        print("📄 LOADING CONFIGURATION")
        print(f"{'='*60}")
        
        try:
            with open(self.yaml_file, 'r') as file:
                data = yaml.safe_load(file)
                self.modules = data.get('modules', [])
                print(f"✅ Successfully loaded {len(self.modules)} repositories from {self.yaml_file}")
                
                if self.modules:
                    print(f"\n📋 Repository List:")
                    for i, repo in enumerate(self.modules, 1):
                        repo_name = repo.split('/')[-1].replace('.git', '')
                        print(f"   {i:2d}. 🔗 {repo_name}")
                        print(f"       └─ {repo}")
                
                return self.modules
        except FileNotFoundError:
            print(f"❌ Error: Configuration file '{self.yaml_file}' not found.")
            return []
        except yaml.YAMLError as e:
            print(f"❌ Error parsing YAML file: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error reading {self.yaml_file}: {e}")
            return []

class RepositoryCloner:
    """A class to handle cloning repositories from a list of URLs."""
    
    def __init__(self, repo_urls: List[str] = [], clone_dir="clone_temp"):
        self.repo_urls = repo_urls
        self.clone_dir = clone_dir
        self.successful_clones = 0
        
        # Create clone directory
        Path(self.clone_dir).mkdir(exist_ok=True)
        print(f"\n📁 Clone directory '{self.clone_dir}' ready.")
        
        # Clone repositories if URLs are provided
        if self.repo_urls:
            self.clone_all_repositories()
    
    def _format_error_for_table(self, error_msg: str, table_width: int) -> str:
        """Format error message to fit in table, truncating if necessary."""
        max_width = table_width - 4  # Account for borders and padding
        if len(error_msg) <= max_width:
            return error_msg
        return error_msg[:max_width-3] + "..."
    
    def clone_all_repositories(self):
        """Clone all repositories in the repo_urls list."""
        print(f"\n{'='*60}")
        print("⬇️  REPOSITORY CLONING")
        print(f"{'='*60}")
        print(f"🎯 Target: {len(self.repo_urls)} repositories to clone")
        
        # Clone each repository
        for i, repo_url in enumerate(self.repo_urls, 1):
            # Extract repository name from URL for width calculation
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            clone_path = os.path.join(self.clone_dir, repo_name)
            
            # Calculate dynamic width based on content
            content_lines = [
                f"📦 CLONING REPOSITORY {i:2d}/{len(self.repo_urls):2d}",
                f"🔗 Repository: {repo_name}",
                f"🌐 URL: {repo_url}",
                f"📍 Target: {clone_path}",
                "⚠️  Repository already exists, skipping...",
                "🔄 Cloning repository...",
                "✅ Successfully cloned repository"
            ]
            
            # Find the longest content line and add padding
            max_content_width = max(len(line) for line in content_lines)
            table_width = max(max_content_width + 4, 60)  # Minimum 60 chars, +4 for padding and borders
            
            print(f"\n┌{'─'*table_width}┐")
            print(f"│ 📦 CLONING REPOSITORY {i:2d}/{len(self.repo_urls):2d}{' '*(table_width-27-len(str(i))-len(str(len(self.repo_urls))))} │")
            print(f"├{'─'*table_width}┤")
            
            if self.clone_repository(repo_url, i, table_width):
                self.successful_clones += 1

        print(f"\n{'='*60}")
        print("📊 CLONING SUMMARY")
        print(f"{'='*60}")
        print(f"✅ Successfully cloned: {self.successful_clones}/{len(self.repo_urls)} repositories")
        
        if self.successful_clones < len(self.repo_urls):
            failed = len(self.repo_urls) - self.successful_clones
            print(f"❌ Failed to clone: {failed} repositories")
        
        return self.successful_clones

    def clone_repository(self, repo_url, index=1, table_width=60):
        try:
            # Extract repository name from URL
            repo_name = repo_url.split('/')[-1].replace('.git', '')
            clone_path = os.path.join(self.clone_dir, repo_name)
            
            print(f"│ 🔗 Repository: {repo_name:<{table_width-17}} │")
            print(f"│ 🌐 URL: {repo_url:<{table_width-10}} │")
            print(f"│ 📍 Target: {clone_path:<{table_width-13}} │")
            print(f"├{'─'*table_width}┤")
            
            # Skip if already cloned
            if os.path.exists(clone_path):
                print(f"│ ⚠️  Repository already exists, skipping...{' '*(table_width-42)} │")
                print(f"└{'─'*table_width}┘")
                return True
                
            print(f"│ 🔄 Cloning repository...{' '*(table_width-26)} │")
            result = subprocess.run(
                ['git', 'clone', repo_url, clone_path],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"│ ✅ Successfully cloned repository{' '*(table_width-35)} │")
            print(f"└{'─'*table_width}┘")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Clone failed: {str(e.stderr)}"
            formatted_error = self._format_error_for_table(error_msg, table_width)
            print(f"│ {formatted_error:<{table_width-2}} │")
            print(f"└{'─'*table_width}┘")
            return False
        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)}"
            formatted_error = self._format_error_for_table(error_msg, table_width)
            print(f"│ {formatted_error:<{table_width-2}} │")
            print(f"└{'─'*table_width}┘")
            return False

if __name__ == "__main__":
    project_initializer = ProjectInitializer()

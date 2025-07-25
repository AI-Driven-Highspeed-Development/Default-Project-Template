from typing import List
import yaml
import os
import subprocess
import sys
from pathlib import Path
import shutil
from .modules_control import ModulesController
from .cli_format import TableFormatter, TableRow, StaticPrintout

class ProjectInitializer:
    """A class to handle the initialization of a project by cloning repositories."""
    
    def __init__(self, yaml_file="init.yaml", clone_dir="clone_temp"):
        StaticPrintout.project_init_header()
        print("📂 Creating project directory structure...")
        
        os.makedirs("managers", exist_ok=True)
        os.makedirs("utils", exist_ok=True)
        os.makedirs("plugins", exist_ok=True)
        print("✅ Directory structure ready")
        
        self.yaml_loader = InitYamlLoader(yaml_file)
        repo_urls = self.yaml_loader.load_modules()
        if repo_urls:
            self.rc = RepositoryCloner(repo_urls, clone_dir)
            self.modules_placer = ModulesPlacer(clone_dir)
            # Pass the URL mappings from cloner to placer
            self.modules_placer.set_url_mappings(self.rc.get_url_to_clone_path_mapping())
        else:
            print("\n⚠️  No repositories to clone.")
            self.modules_placer = ModulesPlacer(clone_dir)
        modules_paths = self.modules_placer.place_modules()
        url_to_path_mapping = self.modules_placer.get_url_to_path_mapping()
        
        # Use ModulesController to get better module information
        self.modules_controller = ModulesController()
        self.modules_initializer = ModulesInitializer(modules_paths, self.modules_controller, url_to_path_mapping)
        self.modules_initializer.initialize_modules()

        print(f"\n🧹 Cleaning up temporary files...")
        shutil.rmtree(clone_dir, ignore_errors=True)
        print("✅ Cleanup complete")
        
        StaticPrintout.project_init_complete()

class ModulesInitializer:
    """A class to handle the initialization of modules with dependency resolution."""
    
    def __init__(self, modules: List[str], modules_controller: ModulesController, url_to_path_mapping: dict):
        self.modules = modules
        self.modules_controller = modules_controller
        self.url_to_path_mapping = url_to_path_mapping
        self.initialized_modules = set()  # Track successfully initialized modules
        self.initialization_chain = []    # Track current initialization chain for cycle detection
        self.failed_modules = set()       # Track modules that failed to initialize

    def initialize_modules(self):
        """Initialize all modules with proper dependency resolution."""
        StaticPrintout.modules_scan_header()
        
        # Get updated module information after placement
        self.modules_controller._scan_modules()
        all_modules_info = self.modules_controller.get_all_modules()
        
        print(f"📋 Found {len(self.modules)} modules to initialize")
        print(f"🔗 Dependency mapping contains {len(self.url_to_path_mapping)} URL-to-path mappings")
        
        # Initialize each module (dependencies will be handled recursively)
        for module_path in self.modules:
            if module_path not in self.initialized_modules and module_path not in self.failed_modules:
                self._initialize_module_with_dependencies(module_path, all_modules_info)
        
        self._print_initialization_summary()

    def _initialize_module_with_dependencies(self, module_path: str, all_modules_info: dict) -> bool:
        """Initialize a module and its dependencies recursively."""
        # Check if module is already initialized
        if module_path in self.initialized_modules:
            return True
        
        # Check if module failed before
        if module_path in self.failed_modules:
            return False
        
        # Check for circular dependency
        if module_path in self.initialization_chain:
            self._handle_circular_dependency(module_path)
            return False
        
        # Add to initialization chain for cycle detection
        self.initialization_chain.append(module_path)
        
        try:
            # Get module information
            module_info = all_modules_info.get(module_path)
            if not module_info:
                module_info = ModulesController.get_module_info_from_path(module_path)
            
            module_name = module_info.name if module_info else os.path.basename(module_path)
            
            # Display module initialization header
            self._display_module_header(module_name, module_path, module_info)
            
            # Initialize dependencies first
            if not self._initialize_dependencies(module_info, all_modules_info):
                print(f"   ❌ Dependency initialization failed for {module_name}")
                self.failed_modules.add(module_path)
                return False
            
            # Initialize the module itself
            success = self._perform_module_initialization(module_path, module_info, module_name)
            
            if success:
                self.initialized_modules.add(module_path)
                print(f"   ✅ Successfully initialized {module_name}")
            else:
                self.failed_modules.add(module_path)
                print(f"   ❌ Failed to initialize {module_name}")
            
            return success
            
        finally:
            # Remove from initialization chain
            if module_path in self.initialization_chain:
                self.initialization_chain.remove(module_path)

    def _initialize_dependencies(self, module_info, all_modules_info: dict) -> bool:
        """Initialize all dependencies for a module."""
        if not module_info or not module_info.requirements:
            return True  # No dependencies to initialize
        
        print(f"   🔗 Initializing {len(module_info.requirements)} dependencies...")
        
        for requirement_url in module_info.requirements:
            dependency_path = self._resolve_dependency_path(requirement_url)
            
            if not dependency_path:
                print(f"   ⚠️  Dependency not found: {requirement_url}")
                continue
            
            if not self._initialize_module_with_dependencies(dependency_path, all_modules_info):
                dependency_name = os.path.basename(dependency_path)
                print(f"   ❌ Failed to initialize dependency: {dependency_name}")
                return False
        
        return True

    def _resolve_dependency_path(self, requirement_url: str) -> str:
        """Resolve a requirement URL to its local module path."""
        # Try exact match first
        if requirement_url in self.url_to_path_mapping:
            return self.url_to_path_mapping[requirement_url]
        
        # Try normalized URL matching (remove .git, case insensitive)
        normalized_url = requirement_url.lower().rstrip('.git')
        
        for url, path in self.url_to_path_mapping.items():
            if url.lower().rstrip('.git') == normalized_url:
                return path
        
        # Try repository name matching as fallback
        requirement_name = requirement_url.split('/')[-1].replace('.git', '')
        
        for url, path in self.url_to_path_mapping.items():
            url_name = url.split('/')[-1].replace('.git', '')
            if url_name.lower() == requirement_name.lower():
                return path
        
        return None

    def _perform_module_initialization(self, module_path: str, module_info, module_name: str) -> bool:
        """Perform the actual initialization of a module."""
        if not module_info or not module_info.has_init:
            print(f"   ℹ️  No initialization needed for {module_name}")
            return True
        
        init_path = os.path.join(module_path, '__init__.py')
        
        try:
            print(f"   🔄 Running __init__.py...")
            result = subprocess.run(
                [sys.executable, init_path], 
                capture_output=True,
                text=True,
                check=True,
            )
            
            if result.stdout.strip():
                print(f"   📝 Output: {result.stdout.strip()}")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self._handle_initialization_error(module_name, e)
            return False
        except Exception as e:
            print(f"   ❌ Unexpected error initializing {module_name}: {str(e)}")
            return False

    def _handle_circular_dependency(self, module_path: str):
        """Handle circular dependency detection."""
        module_name = os.path.basename(module_path)
        cycle_start = self.initialization_chain.index(module_path)
        cycle = self.initialization_chain[cycle_start:] + [module_path]
        cycle_names = [os.path.basename(path) for path in cycle]
        
        StaticPrintout.circular_dependency_warning(cycle_names, module_name)

    def _handle_initialization_error(self, module_name: str, error: subprocess.CalledProcessError):
        """Handle module initialization errors with detailed reporting."""
        print(f"   ❌ Error initializing {module_name}")
        print(f"   📋 Return code: {error.returncode}")
        
        if error.stderr and error.stderr.strip():
            print(f"   📋 Error details: {error.stderr.strip()}")
        
        if error.stdout and error.stdout.strip():
            print(f"   📋 Output: {error.stdout.strip()}")
        
        if not error.stderr and not error.stdout:
            print(f"   📋 No error output available")

    def _display_module_header(self, module_name: str, module_path: str, module_info):
        """Display a formatted header for module initialization."""
        table = TableFormatter()
        table.set_title("🔧 INITIALIZING MODULE")
        
        table.add_row(TableRow(f"📁 Module: {module_name}"))
        
        if module_info and module_info.type:
            table.add_row(TableRow(f"📂 Type: {module_info.type}"))
        
        table.add_row(TableRow(f"� Path: {module_path}"))
        
        print(table.render("normal", 60))

    def _print_initialization_summary(self):
        """Print a comprehensive summary of the initialization process."""
        total_modules = len(self.modules)
        successful_modules = len(self.initialized_modules)
        failed_modules = len(self.failed_modules)
        
        StaticPrintout.initialization_summary_header()
        
        print(f"📦 Total modules: {total_modules}")
        print(f"✅ Successfully initialized: {successful_modules}")
        print(f"❌ Failed to initialize: {failed_modules}")
        
        if failed_modules > 0:
            print(f"\n❌ Failed modules:")
            for module_path in self.failed_modules:
                module_name = os.path.basename(module_path)
                print(f"   • {module_name}")
            print()
        
        if successful_modules == total_modules:
            print("🎉 All modules initialized successfully!")
        elif successful_modules > 0:
            print("⚠️  Some modules failed to initialize. Check output above for details.")
        else:
            print("💥 No modules were successfully initialized.")
        
        # Show final module status
        StaticPrintout.final_module_status_header()
        self.modules_controller.list_modules()
                

class ModulesPlacer:
    """A class to handle placing modules in the appropriate directories."""
    
    def __init__(self, clone_dir="clone_temp"):
        self.clone_dir = clone_dir
        self.modules = []
        self.url_to_path_mapping = {}  # Track URL to path mappings for dependency resolution
        
    def get_url_to_path_mapping(self) -> dict:
        """Get the URL to path mapping for dependency resolution."""
        return self.url_to_path_mapping.copy()
    
    def set_url_mappings(self, clone_url_mappings: dict):
        """Set initial URL mappings from the cloner."""
        self.clone_url_mappings = clone_url_mappings
        
    def move_contents(self, module_dir: str, target_dir: str):
        """Move contents of module_dir into target_dir."""
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        
        for item in os.listdir(module_dir):
            src = os.path.join(module_dir, item)
            dst = os.path.join(target_dir, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
    
    def place_modules(self) -> List[str]:
        """Place cloned modules into the appropriate directories."""
        modules_dir = [
            os.path.join(self.clone_dir, dir)
            for dir in os.listdir(self.clone_dir)
            if os.path.isdir(os.path.join(self.clone_dir, dir))
        ]
                
        if not modules_dir:
            print("⚠️  No modules found to place.")
            return []
    
        StaticPrintout.module_placement_header()
        print(f"🔍 Found {len(modules_dir)} modules to place")
        
        for module_dir in modules_dir:
            self._process_module(module_dir)

        print(f"\n🎉 Module placement complete! Processed {len(self.modules)} modules.")
        return self.modules

    def _process_module(self, module_dir: str):
        """Process a single module for placement."""
        module_info = ModulesController.get_module_info_from_path(module_dir)
        module_name = os.path.basename(module_dir)
        
        # Create table for module processing
        table = TableFormatter()
        table.set_title(f"📁 Processing: {module_name}")
        
        if not module_info:
            table.add_row(TableRow("⚠️  No init.yaml found, skipping module"))
            print(table.render("normal", 60))
            return
            
        folder_path = module_info.folder_path
        self._handle_module_placement(module_dir, folder_path, module_info, table)

    def _handle_module_placement(self, module_dir: str, folder_path: str, module_info, table: TableFormatter):
        """Handle the placement logic for a module."""
        old_folder_exists = os.path.exists(folder_path)

        if not old_folder_exists:
            os.makedirs(folder_path, exist_ok=True)
            table.add_row(TableRow(f"📂 Created directory: {folder_path}"))
            
        table.add_row(TableRow(f"🎯 Target: {folder_path}"))
        table.add_row(TableRow(f"📦 Version: {module_info.version}"))
        
        if old_folder_exists:
            self._handle_existing_module(module_dir, folder_path, module_info, table)
        else:
            self._place_new_module(module_dir, folder_path, table)
        
        print(table.render("normal", 80))

    def _handle_existing_module(self, module_dir: str, folder_path: str, module_info, table: TableFormatter):
        """Handle placement when module already exists."""
        existing_module_info = ModulesController.get_module_info_from_path(folder_path)
        
        if not existing_module_info:
            table.add_row(TableRow("⚠️  Module exists but no version info, skipping..."))
            return
            
        existing_version = existing_module_info.version
        new_version = module_info.version
        
        table.add_row(TableRow(f"🔍 Existing version: {existing_version}"))
        table.add_row(TableRow(f"🆕 New version: {new_version}"))
        
        if self._should_replace_module(existing_version, new_version):
            table.add_row(TableRow("🔄 Replacing with newer version..."))
            try:
                shutil.rmtree(folder_path)
                os.makedirs(folder_path, exist_ok=True)
                self.move_contents(module_dir, folder_path)
                table.add_row(TableRow("✅ Successfully replaced module"))
                self.modules.append(folder_path)
                self._update_url_mapping(module_dir, folder_path)
            except OSError as e:
                table.add_row(TableRow(f"❌ Error replacing module: {str(e)}"))
        else:
            table.add_row(TableRow("⚠️  Keeping existing version (newer/same)"))

    def _place_new_module(self, module_dir: str, folder_path: str, table: TableFormatter):
        """Place a new module."""
        try:
            self.move_contents(module_dir, folder_path)
            table.add_row(TableRow("✅ Successfully moved to target location"))
            self.modules.append(folder_path)
            self._update_url_mapping(module_dir, folder_path)
        except OSError as e:
            table.add_row(TableRow(f"❌ Error moving module: {str(e)}"))

    def _update_url_mapping(self, module_dir: str, target_path: str):
        """Update URL to path mapping when a module is placed."""
        module_name = os.path.basename(module_dir)
        
        # Find the corresponding URL from clone mappings
        if hasattr(self, 'clone_url_mappings'):
            for url, clone_path in self.clone_url_mappings.items():
                if os.path.basename(clone_path) == module_name:
                    self.url_to_path_mapping[url] = target_path
                    break

    def _should_replace_module(self, existing_version: str, new_version: str) -> bool:
        """
        Compare two version strings and determine if we should replace the existing module.
        Returns True if new_version is greater than existing_version.
        """
        def parse_version(version_str: str) -> tuple:
            """Parse version string into tuple of integers for comparison."""
            try:
                clean_version = version_str.lower().lstrip('v')
                parts = clean_version.split('.')
                return tuple(int(part) for part in parts[:3])
            except (ValueError, AttributeError):
                return (0, 0, 0)
        
        existing_parsed = parse_version(existing_version)
        new_parsed = parse_version(new_version)
        
        return new_parsed > existing_parsed

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
        StaticPrintout.configuration_loading_header()
        
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
    """A class to handle cloning repositories from a list of URLs with recursive dependency resolution."""
    
    def __init__(self, repo_urls: List[str] = [], clone_dir="clone_temp"):
        self.repo_urls = repo_urls
        self.clone_dir = clone_dir
        self.successful_clones = 0
        self.processed_repos = set()  # Track processed repositories to avoid infinite loops
        self.url_to_clone_path = {}   # Track URL to clone path mappings
        
        # Create clone directory
        Path(self.clone_dir).mkdir(exist_ok=True)
        print(f"\n📁 Clone directory '{self.clone_dir}' ready.")
        
        # Clone repositories if URLs are provided
        if self.repo_urls:
            self.clone_all_repositories_recursive()
    
    def get_url_to_clone_path_mapping(self) -> dict:
        """Get the URL to clone path mapping for dependency resolution."""
        return self.url_to_clone_path.copy()
    
    def _format_error_for_table(self, error_msg: str, table_width: int) -> str:
        """Format error message to fit in table, truncating if necessary."""
        max_width = table_width - 4  # Account for borders and padding
        if len(error_msg) <= max_width:
            return error_msg
        return error_msg[:max_width-3] + "..."
    
    def _normalize_repo_url(self, repo_url: str) -> str:
        """Normalize repository URL to avoid duplicates with different formats."""
        # Remove trailing .git and normalize case
        return repo_url.lower().rstrip('.git')
    
    def _extract_dependencies_from_module(self, module_path: str) -> List[str]:
        """Extract dependency URLs from a cloned module's init.yaml."""
        module_info = ModulesController.get_module_info_from_path(module_path)
        if module_info and module_info.requirements:
            return module_info.requirements
        return []
    
    def clone_all_repositories_recursive(self):
        """Clone all repositories recursively, including their dependencies."""
        StaticPrintout.recursive_cloning_header()
        
        # Start with initial repositories
        repos_to_process = list(self.repo_urls)
        all_discovered_repos = set(self._normalize_repo_url(url) for url in self.repo_urls)
        
        print(f"🎯 Starting with {len(repos_to_process)} initial repositories")
        
        level = 0
        while repos_to_process:
            level += 1
            current_batch = repos_to_process.copy()
            repos_to_process.clear()
            
            StaticPrintout.dependency_level_header(level)
            print(f"🔍 Processing {len(current_batch)} repositories at level {level}")
            
            for i, repo_url in enumerate(current_batch, 1):
                normalized_url = self._normalize_repo_url(repo_url)
                
                # Skip if already processed
                if normalized_url in self.processed_repos:
                    print(f"\n⏭️  Repository already processed: {repo_url}")
                    continue
                
                # Mark as processed
                self.processed_repos.add(normalized_url)
                
                # Extract repository name from URL for width calculation
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                clone_path = os.path.join(self.clone_dir, repo_name)
                
                # Calculate dynamic width based on content
                content_lines = [
                    f"📦 CLONING REPOSITORY {i:2d}/{len(current_batch):2d} (Level {level})",
                    f"🔗 Repository: {repo_name}",
                    f"🌐 URL: {repo_url}",
                    f"📍 Target: {clone_path}",
                    "⚠️  Repository already exists, analyzing dependencies...",
                    "🔄 Cloning repository...",
                    "✅ Successfully cloned repository",
                    "🔍 Scanning for dependencies..."
                ]
                
                # Find the longest content line and add padding
                max_content_width = max(len(line) for line in content_lines)
                table_width = max(max_content_width + 4, 60)  # Minimum 60 chars, +4 for padding and borders
                
                print(f"\n┌{'─'*table_width}┐")
                print(f"│ 📦 CLONING REPOSITORY {i:2d}/{len(current_batch):2d} (Level {level}){' '*(table_width-36-len(str(i))-len(str(len(current_batch)))-len(str(level)))} │")
                print(f"├{'─'*table_width}┤")
                
                clone_success = self.clone_repository(repo_url, i, table_width, clone_path)
                if clone_success:
                    self.successful_clones += 1
                
                # Always check for dependencies, even if the repo already existed
                print(f"│ 🔍 Scanning for dependencies...{' '*(table_width-33)} │")
                dependencies = self._extract_dependencies_from_module(clone_path)
                
                if dependencies:
                    print(f"│ 📋 Found {len(dependencies)} dependencies{' '*(table_width-24-len(str(len(dependencies))))} │")
                    for j, dep_url in enumerate(dependencies, 1):
                        normalized_dep = self._normalize_repo_url(dep_url)
                        if normalized_dep not in all_discovered_repos:
                            all_discovered_repos.add(normalized_dep)
                            repos_to_process.append(dep_url)
                            dep_name = dep_url.split('/')[-1].replace('.git', '')
                            print(f"│   {j:2d}. ➕ New: {dep_name:<{table_width-15}} │")
                        else:
                            dep_name = dep_url.split('/')[-1].replace('.git', '')
                            print(f"│   {j:2d}. ✓ Known: {dep_name:<{table_width-17}} │")
                else:
                    print(f"│ ℹ️  No dependencies found{' '*(table_width-26)} │")
                
                print(f"└{'─'*table_width}┘")
            
            if repos_to_process:
                print(f"\n🔄 {len(repos_to_process)} new dependencies discovered, continuing to level {level+1}...")
            else:
                print(f"\n✅ No more dependencies found. Recursion complete!")

        # Final summary
        StaticPrintout.recursive_cloning_summary_header()
        print(f"🎯 Total repositories discovered: {len(all_discovered_repos)}")
        print(f"✅ Successfully processed: {len(self.processed_repos)}")
        print(f"📦 Successfully cloned: {self.successful_clones}")
        print(f"📈 Dependency levels processed: {level}")
        
        return self.successful_clones
    
    def clone_repository(self, repo_url, index=1, table_width=60, clone_path=None):
        try:
            # Extract repository name from URL if clone_path not provided
            if clone_path is None:
                repo_name = repo_url.split('/')[-1].replace('.git', '')
                clone_path = os.path.join(self.clone_dir, repo_name)
            else:
                repo_name = os.path.basename(clone_path)
            
            print(f"│ 🔗 Repository: {repo_name:<{table_width-17}} │")
            print(f"│ 🌐 URL: {repo_url:<{table_width-10}} │")
            print(f"│ 📍 Target: {clone_path:<{table_width-13}} │")
            print(f"├{'─'*table_width}┤")
            
            # Track URL to clone path mapping
            self.url_to_clone_path[repo_url] = clone_path
            
            # Skip if already cloned (but still return True for dependency analysis)
            if os.path.exists(clone_path):
                print(f"│ ⚠️  Repository already exists, analyzing dependencies...{' '*(table_width-51)} │")
                return True
                
            print(f"│ 🔄 Cloning repository...{' '*(table_width-26)} │")
            result = subprocess.run(
                ['git', 'clone', repo_url, clone_path],
                capture_output=True,
                text=True,
                check=True
            )
            print(f"│ ✅ Successfully cloned repository{' '*(table_width-35)} │")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Clone failed: {str(e.stderr)}"
            formatted_error = self._format_error_for_table(error_msg, table_width)
            print(f"│ {formatted_error:<{table_width-2}} │")
            return False
        except Exception as e:
            error_msg = f"❌ Unexpected error: {str(e)}"
            formatted_error = self._format_error_for_table(error_msg, table_width)
            print(f"│ {formatted_error:<{table_width-2}} │")
            return False

if __name__ == "__main__":
    project_initializer = ProjectInitializer()

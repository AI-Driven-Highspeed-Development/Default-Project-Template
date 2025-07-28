from typing import List, Dict, Optional
import yaml
import os
import subprocess
import sys
from pathlib import Path
import shutil
import requests
from .modules_control import ModulesController
from .cli_format import TableFormatter, TableRow, StaticPrintout

class ProjectInitializer:
    """A class to handle the initialization of a project by cloning repositories."""
    
    def __init__(self, yaml_file="init.yaml", force_update=False):
        StaticPrintout.project_init_header()
        print("📂 Creating project directory structure...")
        
        os.makedirs("managers", exist_ok=True)
        os.makedirs("utils", exist_ok=True)
        os.makedirs("plugins", exist_ok=True)
        print("✅ Directory structure ready")
        
        self.yaml_loader = InitYamlLoader(yaml_file)
        repo_urls = self.yaml_loader.load_modules()
        
        if repo_urls:
            self.rc = RepositoryCloner(repo_urls, force_update=force_update)
            modules_paths = self.rc.clone_all_repositories_recursive()
            url_to_path_mapping = self.rc.get_url_to_path_mapping()
        else:
            print("\n⚠️  No repositories to clone.")
            modules_paths = []
            url_to_path_mapping = {}
        
        # Use ModulesController to get better module information
        self.modules_controller = ModulesController()
        self.modules_initializer = ModulesInitializer(modules_paths, self.modules_controller, url_to_path_mapping)
        self.modules_initializer.initialize_modules()
        # self.append_requirements()
        self.create_vscode_workspace()

        StaticPrintout.project_init_complete()

    def append_requirements(self):
        """Find all requirements.txt files in modules and append them to the main requirements.txt."""
        print("📦 Appending requirements from modules...")
        
        requirements_file = Path("requirements.txt")
        os.makedirs(requirements_file.parent, exist_ok=True)

        with open(requirements_file, 'a') as main_requirements:
            for module_path in self.modules_controller.get_all_modules().keys():
                module_requirements = Path(module_path) / "requirements.txt"
                if module_requirements.exists():
                    with open(module_requirements, 'r') as mod_req:
                        content = mod_req.read()
                        main_requirements.write(content + "\n")
                        print(f"✅ Appended requirements from {module_path}")
        
        print("📦 All module requirements appended successfully!")

    def create_vscode_workspace(self):
        # For the early stage of the framework development,
        # it will be better if we add all modules to the workspace to real time edit them while using them.
        # This is not recommended when the framework is in production use as it somehow defeats the purpose of having isolated modules.
        # But I am the one man army who is single handedly developing this framework,
        # I don't hate myself enough to not include this temporary workaround lol

        print("📝 Creating VSCode workspace with all modules...")
        
        # Get the current project folder name
        project_folder = os.path.basename(os.getcwd())
        workspace_file = f"{project_folder}.code-workspace"
        
        try:
            
            # Find all directories with .git folders and create workspace entries
            result = subprocess.run(
                ['find', '.', '-mindepth', '2', '-type', 'd', '-name', '.git'],
                capture_output=True,
                text=True,
                check=True
            )
            
            if result.stdout.strip():
                # Process the output to create workspace entries
                git_dirs = result.stdout.strip().split('\n')
                git_dirs.append("./.git")
                workspace_entries = []
                
                for git_dir in git_dirs:
                    # Remove /.git suffix to get the module path
                    module_path = git_dir.replace('/.git', '')
                    workspace_entries.append(f'    {{ "path": "{module_path}" }}')
                
                # Create workspace content with proper formatting
                workspace_content = f"""{{\n\t"folders": [\n\t{",\n\t".join(workspace_entries)}\n\t],}}"""
                workspace_content += """\n\t"settings": {\n\t\t"python.analysis.extraPaths": [\n\t\t\t"../../../",\n\t\t\t"../../",\n\t\t\t"../",\n\t\t]\n\t}\n}"""

                # Write workspace file
                with open(workspace_file, 'w') as f:
                    f.write(workspace_content)
                
                print(f"✅ Created VSCode workspace: {workspace_file}")
                print(f"📁 Added {len(workspace_entries)} module(s) to workspace")
            else:
                print("⚠️  No git repositories found to add to workspace")
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating workspace: {e}")
        except Exception as e:
            print(f"❌ Unexpected error creating workspace: {str(e)}")


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
    """A class to handle cloning repositories directly to their target locations using remote init.yaml files."""
    
    def __init__(self, repo_urls: List[str], force_update: bool = False):
        self.repo_urls = repo_urls
        self.force_update = force_update
        self.successful_clones = 0
        self.processed_repos = set()  # Track processed repositories to avoid infinite loops
        self.url_to_path_mapping = {}   # Track URL to final path mappings
        
    def get_url_to_path_mapping(self) -> Dict[str, str]:
        """Get the URL to path mapping for dependency resolution."""
        return self.url_to_path_mapping.copy()
    
    def _normalize_repo_url(self, repo_url: str) -> str:
        """Normalize repository URL to avoid duplicates with different formats."""
        return repo_url.lower().rstrip('.git')
    
    def _convert_github_url_to_raw(self, repo_url: str) -> str:
        """Convert GitHub repository URL to raw init.yaml URL."""
        # Convert https://github.com/owner/repo.git to https://raw.githubusercontent.com/owner/repo/main/init.yaml
        repo_url = repo_url.rstrip('.git')
        if 'github.com' in repo_url:
            raw_url = repo_url.replace('github.com', 'raw.githubusercontent.com') + '/main/init.yaml'
            return raw_url
        return None
    
    def _fetch_remote_init_yaml(self, repo_url: str) -> Optional[Dict]:
        """Fetch and parse remote init.yaml file."""
        raw_url = self._convert_github_url_to_raw(repo_url)
        if not raw_url:
            return None
        
        try:
            response = requests.get(raw_url, timeout=10)
            if response.status_code == 200:
                return yaml.safe_load(response.text)
            return None
        except Exception:
            return None
    
    def _extract_dependencies_from_init_yaml(self, init_data: Dict) -> List[str]:
        """Extract dependency URLs from init.yaml data."""
        if not init_data:
            return []
        
        requirements = init_data.get('requirements', [])
        if isinstance(requirements, str):
            return [requirements]
        elif isinstance(requirements, list):
            return requirements
        return []
    
    def clone_all_repositories_recursive(self) -> List[str]:
        """Clone all repositories recursively, including their dependencies."""
        StaticPrintout.recursive_cloning_header()
        
        repos_to_process = list(self.repo_urls)
        all_discovered_repos = set(self._normalize_repo_url(url) for url in self.repo_urls)
        cloned_paths = []
        
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
                    table = TableFormatter()
                    table.set_title(f"⏭️  REPOSITORY {i:2d}/{len(current_batch):2d} (Level {level})")
                    table.add_row(TableRow(f"� Repository: {repo_url.split('/')[-1].replace('.git', '')}"))
                    table.add_row(TableRow("ℹ️  Status: Already processed"))
                    print(f"\n{table.render('normal', 70)}")
                    continue
                
                # Mark as processed
                self.processed_repos.add(normalized_url)
                
                clone_path = self._clone_single_repository(repo_url, i, len(current_batch), level)
                if clone_path:
                    cloned_paths.append(clone_path)
                    self.successful_clones += 1
                    
                    # Get dependencies from the cloned repository
                    dependencies = self._get_dependencies_from_cloned_repo(clone_path)
                    
                    # Process new dependencies
                    for dep_url in dependencies:
                        normalized_dep = self._normalize_repo_url(dep_url)
                        if normalized_dep not in all_discovered_repos:
                            all_discovered_repos.add(normalized_dep)
                            repos_to_process.append(dep_url)
            
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
        
        return cloned_paths
    
    def _clone_single_repository(self, repo_url: str, index: int, total: int, level: int) -> Optional[str]:
        """Clone a single repository to its correct target location."""
        table = TableFormatter()
        table.set_title(f"📦 CLONING REPOSITORY {index:2d}/{total:2d} (Level {level})")
        
        repo_name = repo_url.split('/')[-1].replace('.git', '')
        table.add_row(TableRow(f"📦 Repository: {repo_name}"))
        table.add_row(TableRow(f"🌐 URL: {repo_url}"))
        
        # Fetch remote init.yaml to determine target location
        table.add_row(TableRow("🔍 Fetching remote init.yaml..."))
        init_data = self._fetch_remote_init_yaml(repo_url)
        
        if not init_data:
            table.add_row(TableRow("⚠️  No init.yaml found, using default location"), -3)
            target_path = f"utils/{repo_name.lower().replace('-', '_')}"
        else:
            folder_path = init_data.get('folder_path', f"utils/{repo_name.lower().replace('-', '_')}")
            target_path = folder_path
            table.add_row(TableRow(f"� Target: {target_path}"))
            
            if 'version' in init_data:
                table.add_row(TableRow(f"🏷️  Version: {init_data['version']}", -3))
        
        # Check if target already exists
        if os.path.exists(target_path):
            if self.force_update:
                table.add_row(TableRow("⚡ Force mode: Removing existing module"))
                shutil.rmtree(target_path, ignore_errors=True)
            else:
                existing_info = ModulesController.get_module_info_from_path(target_path)
                if existing_info and init_data:
                    existing_version = existing_info.version
                    new_version = init_data.get('version', '0.0.1')
                    table.add_row(TableRow(f"🔍 Existing: {existing_version}"))
                    table.add_row(TableRow(f"🆕 New: {new_version}"))
                    
                    if not self._should_update(existing_version, new_version):
                        table.add_row(TableRow("⚠️  Keeping existing (newer/same version)", -3))
                        print(f"\n{table.render('normal', 70)}")
                        return target_path  # Still return path for dependency tracking
                    else:
                        table.add_row(TableRow("✅ Updating to newer version"))
                        shutil.rmtree(target_path, ignore_errors=True)
                else:
                    table.add_row(TableRow("⚠️  Existing module found, keeping", -3))
                    print(f"\n{table.render('normal', 70)}")
                    return target_path
        
        # Ensure target directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        # Clone repository
        table.add_row(TableRow("🔄 Cloning repository..."))

        try:
            result = subprocess.run(
                ['git', 'clone', repo_url, target_path],
                capture_output=True,
                text=True,
                check=True
            )
            table.add_row(TableRow("✅ Successfully cloned"))
            self.url_to_path_mapping[repo_url] = target_path
            print(f"\n{table.render('normal', 70)}")
            return target_path
            
        except subprocess.CalledProcessError as e:
            error_msg = str(e.stderr).strip() if e.stderr else "Unknown error"
            table.add_row(TableRow(f"❌ Clone failed: {error_msg}"))
            print(f"\n{table.render('normal', 70)}")
            return None
        except Exception as e:
            table.add_row(TableRow(f"❌ Unexpected error: {str(e)}"))
            print(f"\n{table.render('normal', 70)}")
            return None
    
    def _get_dependencies_from_cloned_repo(self, repo_path: str) -> List[str]:
        """Get dependencies from a cloned repository."""
        module_info = ModulesController.get_module_info_from_path(repo_path)
        if module_info and module_info.requirements:
            return module_info.requirements
        return []
    
    def _should_update(self, existing_version: str, new_version: str) -> bool:
        """Compare version strings to determine if update is needed."""
        def parse_version(version_str: str) -> tuple:
            try:
                clean_version = version_str.lower().lstrip('v')
                parts = clean_version.split('.')
                return tuple(int(part) for part in parts[:3])
            except (ValueError, AttributeError):
                return (0, 0, 0)
        
        existing_parsed = parse_version(existing_version)
        new_parsed = parse_version(new_version)
        
        return new_parsed > existing_parsed

if __name__ == "__main__":
    project_initializer = ProjectInitializer()

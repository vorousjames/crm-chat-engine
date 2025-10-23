import os
import weaviate
from pathlib import Path
import json
import hashlib
from typing import List, Dict, Optional, Tuple
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import re
import ast
import inspect

# Load environment variables - will be overridden in main for production
load_dotenv('.env')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AppFeatureIndexer:
    def __init__(self):
        # Configure Weaviate client with API key support  
        weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
        
        if weaviate_api_key and weaviate_api_key != 'your-actual-weaviate-api-key-here':
            # Production: Use API key authentication for Weaviate Cloud (same as test_connection.py)
            import weaviate.auth as wv_auth
            
            self.weaviate_client = weaviate.Client(
                url=weaviate_url,
                auth_client_secret=wv_auth.AuthApiKey(api_key=weaviate_api_key),
                timeout_config=(10, 30)  # connection timeout, read timeout
            )
        else:
            # Development: No authentication
            self.weaviate_client = weaviate.Client(url=weaviate_url)
        
        # Test connection
        try:
            logger.info(f"Testing connection to: {weaviate_url}")
            meta = self.weaviate_client.get_meta()
            logger.info(f"✅ Connected to Weaviate version: {meta.get('version', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Weaviate connection failed: {e}")
            raise

        # Load local embedding model
        embedding_model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        logger.info(f"Loading embedding model: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        logger.info("Embedding model loaded successfully!")
        
        self.codebase_path = Path(os.getenv('CODEBASE_PATH', '.'))
        self.max_chunk_size = int(os.getenv('MAX_CHUNK_SIZE', 1000))
        
        self.setup_schema()
    
    def setup_schema(self):
        """Create improved Weaviate schema for app features with detailed context"""
        schema = {
            "class": "AppFeature",
            "description": "Actual app functionality with detailed context and behavior",
            "properties": [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "The actual code that implements this feature"
                },
                {
                    "name": "featureDescription", 
                    "dataType": ["text"],
                    "description": "Detailed description of what this code actually does"
                },
                {
                    "name": "userBenefit",
                    "dataType": ["text"], 
                    "description": "Specific benefit this provides to users"
                },
                {
                    "name": "featureType",
                    "dataType": ["string"],
                    "description": "Specific feature category based on actual functionality"
                },
                {
                    "name": "relatedFeatures",
                    "dataType": ["text"],
                    "description": "Actually related features based on code dependencies"
                },
                {
                    "name": "userActions",
                    "dataType": ["text"],
                    "description": "Specific actions users can take with this feature"
                },
                {
                    "name": "inputs",
                    "dataType": ["text"],
                    "description": "What data/parameters users need to provide"
                },
                {
                    "name": "outputs", 
                    "dataType": ["text"],
                    "description": "What users get back from this feature"
                },
                {
                    "name": "businessLogic",
                    "dataType": ["text"], 
                    "description": "Key business rules and validation logic"
                },
                {
                    "name": "actualWorkflow",
                    "dataType": ["text"],
                    "description": "Step-by-step process for using this feature"
                },
                {
                    "name": "filePath",
                    "dataType": ["string"],
                    "description": "Source file location"
                },
                {
                    "name": "functionName",
                    "dataType": ["string"],
                    "description": "Name of the function or class"
                },
                {
                    "name": "contentHash",
                    "dataType": ["string"],
                    "description": "Hash of content for duplicate detection"
                }
            ],
            "vectorizer": "none"
        }
        
        try:
            # Delete existing schema if it exists
            try:
                self.weaviate_client.schema.delete_class("AppFeature")
                logger.info("Deleted existing AppFeature schema")
            except:
                pass
            
            # Create new schema
            self.weaviate_client.schema.create_class(schema)
            logger.info("Created improved AppFeature schema successfully")
        except Exception as e:
            logger.error(f"Schema creation error: {e}")
            raise
    
    def get_file_language(self, file_path: Path) -> str:
        """Determine programming language from file extension"""
        extension_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.json': 'json',
            '.md': 'markdown',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.vue': 'vue'
        }
        return extension_map.get(file_path.suffix.lower(), 'text')
    
    def extract_function_info(self, node: ast.AST, source_code: str) -> Dict:
        """Extract detailed information from AST node"""
        info = {
            'name': getattr(node, 'name', 'unknown'),
            'docstring': ast.get_docstring(node) or '',
            'args': [],
            'returns': None,
            'decorators': [],
            'calls': [],
            'variables': [],
            'imports': [],
            'is_async': isinstance(node, ast.AsyncFunctionDef)
        }
        
        # Extract arguments
        if hasattr(node, 'args'):
            for arg in node.args.args:
                arg_info = {'name': arg.arg, 'type': None}
                if arg.annotation:
                    try:
                        arg_info['type'] = ast.get_source_segment(source_code, arg.annotation)
                    except:
                        pass
                info['args'].append(arg_info)
        
        # Extract decorators
        if hasattr(node, 'decorator_list'):
            for decorator in node.decorator_list:
                try:
                    decorator_name = ast.get_source_segment(source_code, decorator)
                    if decorator_name:
                        info['decorators'].append(decorator_name)
                except:
                    pass
        
        # Walk through function body to extract calls and variables
        for child in ast.walk(node):
            # Function calls
            if isinstance(child, ast.Call):
                try:
                    if isinstance(child.func, ast.Name):
                        info['calls'].append(child.func.id)
                    elif isinstance(child.func, ast.Attribute):
                        info['calls'].append(child.func.attr)
                except:
                    pass
            
            # Variable assignments
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        info['variables'].append(target.id)
        
        return info
    
    def analyze_code_semantics(self, content: str, file_path: Path, func_info: Dict) -> Dict:
        """Analyze code to understand its actual functionality and user impact"""
        
        func_name = func_info.get('name', '').lower()
        docstring = func_info.get('docstring', '').lower()
        content_lower = content.lower()
        args = func_info.get('args', [])
        calls = func_info.get('calls', [])
        decorators = func_info.get('decorators', [])
        
        # Determine if this is user-facing based on semantic analysis
        user_facing_indicators = {
            # Web framework patterns
            'endpoint': ['@app.route', '@bp.route', 'request', 'response', 'render_template', 'jsonify'],
            'authentication': ['login', 'logout', 'signin', 'signup', 'register', 'password', 'token', 'auth'],
            'data_operations': ['create', 'update', 'delete', 'save', 'add', 'remove', 'edit', 'modify'],
            'user_management': ['user', 'profile', 'account', 'settings', 'preferences'],
            'search_filter': ['search', 'filter', 'find', 'query', 'lookup', 'sort'],
            'file_operations': ['upload', 'download', 'file', 'document', 'media'],
            'communication': ['send', 'email', 'notify', 'message', 'alert'],
            'reporting': ['report', 'export', 'generate', 'download', 'analytics'],
            'validation': ['validate', 'check', 'verify', 'confirm']
        }
        
        # Score each category
        category_scores = {}
        for category, keywords in user_facing_indicators.items():
            score = 0
            for keyword in keywords:
                if keyword in func_name: score += 3
                if keyword in docstring: score += 2
                if keyword in content_lower: score += 1
                if any(keyword in call.lower() for call in calls): score += 2
                if any(keyword in dec.lower() for dec in decorators): score += 3
            category_scores[category] = score
        
        # Get the highest scoring category
        best_category = max(category_scores, key=category_scores.get) if category_scores else 'general'
        best_score = category_scores.get(best_category, 0)
        
        # Only consider it user-facing if it has a reasonable score
        if best_score < 2:
            return None
        
        # Generate specific descriptions based on actual code analysis
        feature_info = self._generate_specific_feature_info(
            best_category, func_info, content, file_path, args, calls
        )
        
        return {
            'category': best_category,
            'score': best_score,
            **feature_info
        }
    
    def _generate_specific_feature_info(self, category: str, func_info: Dict, content: str, 
                                       file_path: Path, args: List, calls: List) -> Dict:
        """Generate specific feature information based on actual code analysis"""
        
        func_name = func_info.get('name', 'function')
        docstring = func_info.get('docstring', '')
        
        # Extract actual inputs from function arguments
        inputs = []
        for arg in args:
            if arg['name'] not in ['self', 'cls', 'request']:
                arg_desc = f"{arg['name']}"
                if arg['type']:
                    arg_desc += f" ({arg['type']})"
                inputs.append(arg_desc)
        
        # Analyze what the function actually does based on its calls
        operations = []
        if any(call in ['save', 'create', 'insert', 'add'] for call in calls):
            operations.append('creates new data')
        if any(call in ['update', 'modify', 'edit', 'change'] for call in calls):
            operations.append('modifies existing data')
        if any(call in ['delete', 'remove', 'destroy'] for call in calls):
            operations.append('removes data')
        if any(call in ['find', 'get', 'fetch', 'query', 'search'] for call in calls):
            operations.append('retrieves data')
        if any(call in ['validate', 'check', 'verify'] for call in calls):
            operations.append('validates information')
        if any(call in ['render', 'redirect', 'jsonify', 'return'] for call in calls):
            operations.append('returns results')
        
        # Generate description based on actual functionality
        if docstring:
            description = docstring.split('.')[0]  # First sentence of docstring
        elif operations:
            description = f"This function {', '.join(operations[:3])}"
        else:
            description = f"Handles {category.replace('_', ' ')} functionality"
        
        # Generate user benefit based on category and operations
        benefit_map = {
            'endpoint': 'Access application features through web interface',
            'authentication': 'Secure access to your account and personal data',
            'data_operations': 'Manage and organize your information',
            'user_management': 'Control your account settings and preferences',
            'search_filter': 'Quickly find specific information',
            'file_operations': 'Upload, download, and manage your files',
            'communication': 'Stay informed with notifications and messages',
            'reporting': 'Generate reports and analyze your data',
            'validation': 'Ensure data accuracy and completeness'
        }
        
        user_benefit = benefit_map.get(category, 'Accomplish tasks efficiently')
        
        # Generate workflow based on inputs and operations
        workflow_steps = []
        if inputs:
            workflow_steps.append(f"Provide: {', '.join(inputs[:3])}")
        if operations:
            workflow_steps.extend([f"System {op}" for op in operations[:2]])
        workflow_steps.append("Receive confirmation or results")
        
        # Determine related features based on file location and calls
        related_features = []
        file_stem = file_path.stem.lower()
        if 'auth' in file_stem or 'login' in file_stem:
            related_features.extend(['user profile', 'account security', 'password reset'])
        if 'user' in file_stem or 'profile' in file_stem:
            related_features.extend(['authentication', 'account settings', 'preferences'])
        if 'data' in file_stem or 'model' in file_stem:
            related_features.extend(['search', 'reporting', 'export'])
        
        return {
            'description': description,
            'user_benefit': user_benefit,
            'user_actions': f"Call {func_name} with required parameters",
            'inputs': ', '.join(inputs) if inputs else 'No user input required',
            'outputs': 'Processed results or confirmation' if operations else 'Function response',
            'business_logic': self._extract_business_logic(content),
            'workflow': ' → '.join(workflow_steps),
            'related_features': ', '.join(related_features[:5]) if related_features else 'Core application features'
        }
    
    def _extract_business_logic(self, content: str) -> str:
        """Extract key business rules from code"""
        logic_patterns = [
            r'if\s+.*?==\s*["\']([^"\']+)["\']',  # String comparisons
            r'if\s+.*?>\s*(\d+)',  # Numeric comparisons
            r'if\s+.*?<\s*(\d+)',  # Numeric comparisons
            r'raise\s+\w+\(["\']([^"\']+)["\']',  # Error conditions
            r'assert\s+.*?,\s*["\']([^"\']+)["\']'  # Assertions
        ]
        
        business_rules = []
        for pattern in logic_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            business_rules.extend(matches[:2])  # Limit to avoid noise
        
        if business_rules:
            return f"Enforces rules: {', '.join(business_rules[:3])}"
        return "Follows standard application logic"
    
    def extract_feature_chunks(self, file_path: Path, content: str) -> List[Dict]:
        """Extract user-facing features using AST analysis"""
        chunks = []
        language = self.get_file_language(file_path)
        
        if language == 'python':
            chunks.extend(self._extract_python_features_ast(content, file_path))
        elif language in ['javascript', 'typescript']:
            chunks.extend(self._extract_js_features_improved(content, file_path))
        elif language == 'markdown':
            chunks.extend(self._extract_markdown_features(content, file_path))
        else:
            # Fallback to improved content analysis
            chunks.extend(self._analyze_general_content_improved(content, file_path))
        
        return chunks
    
    def _extract_python_features_ast(self, content: str, file_path: Path) -> List[Dict]:
        """Extract features using AST parsing for accurate Python analysis"""
        chunks = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    try:
                        # Get the actual source code for this node
                        node_source = ast.get_source_segment(content, node)
                        if not node_source:
                            continue
                        
                        # Extract detailed function information
                        func_info = self.extract_function_info(node, content)
                        
                        # Analyze if this represents user-facing functionality
                        semantic_analysis = self.analyze_code_semantics(node_source, file_path, func_info)
                        
                        if semantic_analysis:
                            feature_chunk = {
                                'content': node_source,
                                'featureDescription': semantic_analysis['description'],
                                'userBenefit': semantic_analysis['user_benefit'],
                                'featureType': semantic_analysis['category'],
                                'relatedFeatures': semantic_analysis['related_features'],
                                'userActions': semantic_analysis['user_actions'],
                                'inputs': semantic_analysis['inputs'],
                                'outputs': semantic_analysis['outputs'],
                                'businessLogic': semantic_analysis['business_logic'],
                                'actualWorkflow': semantic_analysis['workflow'],
                                'filePath': str(file_path.relative_to(self.codebase_path)),
                                'functionName': func_info['name'],
                                'contentHash': hashlib.md5(node_source.encode()).hexdigest()
                            }
                            chunks.append(feature_chunk)
                    
                    except Exception as e:
                        logger.debug(f"Error analyzing node in {file_path}: {e}")
                        continue
        
        except SyntaxError as e:
            logger.debug(f"Syntax error in {file_path}: {e}")
            # Fallback to regex-based analysis
            return self._extract_js_features_improved(content, file_path)
        
        return chunks
    
    def _extract_js_features_improved(self, content: str, file_path: Path) -> List[Dict]:
        """Improved JavaScript/TypeScript feature extraction"""
        chunks = []
        
        # Patterns for JavaScript/TypeScript functions and components
        patterns = [
            r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\([^)]*\)\s*{[^}]*}',
            r'(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*{[^}]*}',
            r'(?:export\s+)?class\s+(\w+)\s*(?:extends\s+\w+)?\s*{[^}]*}',
            r'app\.(?:get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                func_code = match.group(0)
                func_name = match.group(1) if match.lastindex >= 1 else 'anonymous'
                
                # Analyze this code segment
                mock_func_info = {
                    'name': func_name,
                    'docstring': '',
                    'args': self._extract_js_params(func_code),
                    'calls': self._extract_js_calls(func_code),
                    'decorators': []
                }
                
                semantic_analysis = self.analyze_code_semantics(func_code, file_path, mock_func_info)
                
                if semantic_analysis:
                    feature_chunk = {
                        'content': func_code,
                        'featureDescription': semantic_analysis['description'],
                        'userBenefit': semantic_analysis['user_benefit'],
                        'featureType': semantic_analysis['category'],
                        'relatedFeatures': semantic_analysis['related_features'],
                        'userActions': semantic_analysis['user_actions'],
                        'inputs': semantic_analysis['inputs'],
                        'outputs': semantic_analysis['outputs'],
                        'businessLogic': semantic_analysis['business_logic'],
                        'actualWorkflow': semantic_analysis['workflow'],
                        'filePath': str(file_path.relative_to(self.codebase_path)),
                        'functionName': func_name,
                        'contentHash': hashlib.md5(func_code.encode()).hexdigest()
                    }
                    chunks.append(feature_chunk)
        
        return chunks
    
    def _extract_js_params(self, code: str) -> List[Dict]:
        """Extract parameters from JavaScript function"""
        param_pattern = r'\(([^)]*)\)'
        match = re.search(param_pattern, code)
        if match:
            params_str = match.group(1)
            params = [p.strip() for p in params_str.split(',') if p.strip()]
            return [{'name': p, 'type': None} for p in params]
        return []
    
    def _extract_js_calls(self, code: str) -> List[str]:
        """Extract function calls from JavaScript code"""
        call_pattern = r'\.(\w+)\s*\('
        calls = re.findall(call_pattern, code)
        return calls
    
    def _extract_markdown_features(self, content: str, file_path: Path) -> List[Dict]:
        """Extract features from markdown documentation"""
        chunks = []
        sections = re.split(r'\n#+\s+', content)
        
        for i, section in enumerate(sections):
            if len(section.strip()) > 100:  # Only substantial sections
                feature_chunk = {
                    'content': section.strip(),
                    'featureDescription': f"Documentation: {section.split('.')[0][:100]}",
                    'userBenefit': 'Provides guidance and information for users',
                    'featureType': 'documentation',
                    'relatedFeatures': 'User guides, help system',
                    'userActions': 'Read documentation and follow instructions',
                    'inputs': 'User questions or help requests',
                    'outputs': 'Information and guidance',
                    'businessLogic': 'Informational content',
                    'actualWorkflow': 'User reads → understands → takes action',
                    'filePath': str(file_path.relative_to(self.codebase_path)),
                    'functionName': f'section_{i}',
                    'contentHash': hashlib.md5(section.encode()).hexdigest()
                }
                chunks.append(feature_chunk)
        
        return chunks
    
    def _analyze_general_content_improved(self, content: str, file_path: Path) -> List[Dict]:
        """Improved analysis for non-Python files"""
        # Only process if it looks like user-facing configuration or templates
        if any(keyword in content.lower() for keyword in ['user', 'auth', 'login', 'form', 'page']):
            feature_chunk = {
                'content': content[:1000],  # Truncate for readability
                'featureDescription': f'Configuration or template file: {file_path.name}',
                'userBenefit': 'Supports application functionality',
                'featureType': 'configuration',
                'relatedFeatures': 'Application setup and behavior',
                'userActions': 'Indirect - affects user experience',
                'inputs': 'Configuration values',
                'outputs': 'Application behavior',
                'businessLogic': 'System configuration rules',
                'actualWorkflow': 'System reads config → applies settings → affects user experience',
                'filePath': str(file_path.relative_to(self.codebase_path)),
                'functionName': file_path.stem,
                'contentHash': hashlib.md5(content.encode()).hexdigest()
            }
            return [feature_chunk]
        
        return []
    
    def generate_embedding(self, feature_data: Dict) -> List[float]:
        """Generate comprehensive embedding from all feature information"""
        try:
            # Combine all semantic information for better embeddings
            full_context = f"""
            Feature: {feature_data.get('featureDescription', '')}
            User Benefit: {feature_data.get('userBenefit', '')}
            User Actions: {feature_data.get('userActions', '')}
            Inputs: {feature_data.get('inputs', '')}
            Outputs: {feature_data.get('outputs', '')}
            Business Logic: {feature_data.get('businessLogic', '')}
            Workflow: {feature_data.get('actualWorkflow', '')}
            Related: {feature_data.get('relatedFeatures', '')}
            Type: {feature_data.get('featureType', '')}
            """.strip()
            
            # Truncate if too long
            if len(full_context) > 5000:
                full_context = full_context[:5000] + "..."
            
            embedding = self.embedding_model.encode(full_context, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return []
    
    def index_codebase(self):
        """Index the entire codebase for user features with improved analysis"""
        supported_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.md', 
            '.yml', '.yaml', '.html', '.css', '.scss', '.vue'
        }
        
        skip_dirs = {
            '.git', 'node_modules', '__pycache__', '.next', 'venv', 
            'env', 'dist', 'build', '.vscode', '.idea', 'target',
            'bin', 'obj', '.pytest_cache', 'coverage', 'logs'
        }
        
        skip_files = {
            '.DS_Store', 'package-lock.json', 'yarn.lock', '.gitignore',
            'LICENSE', 'Dockerfile', 'docker-compose.yml', 'requirements.txt'
        }
        
        total_files = 0
        indexed_features = 0
        skipped_files = 0
        
        logger.info(f"Starting improved feature indexing: {self.codebase_path}")
        logger.info("Using AST analysis for accurate code understanding...")
        
        for root, dirs, files in os.walk(self.codebase_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # Skip unwanted files
                if file in skip_files:
                    skipped_files += 1
                    continue
                
                if file_path.suffix in supported_extensions:
                    try:
                        total_files += 1
                        relative_path = file_path.relative_to(self.codebase_path)
                        logger.info(f"Analyzing [{total_files}]: {relative_path}")
                        
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        if not content.strip():
                            logger.debug(f"Empty file: {relative_path}")
                            continue
                        
                        # Skip very large files
                        if len(content) > 100000:  # 100KB limit
                            logger.warning(f"Skipping large file: {relative_path} ({len(content)} chars)")
                            skipped_files += 1
                            continue
                        
                        # Extract user-facing features with improved analysis
                        feature_chunks = self.extract_feature_chunks(file_path, content)
                        
                        for chunk in feature_chunks:
                            # Generate comprehensive embedding
                            embedding = self.generate_embedding(chunk)
                            
                            if embedding:
                                try:
                                    # Store in Weaviate with all the detailed information
                                    self.weaviate_client.data_object.create(
                                        data_object=chunk,
                                        class_name="AppFeature",
                                        vector=embedding
                                    )
                                    indexed_features += 1
                                    
                                    if indexed_features % 5 == 0:
                                        logger.info(f"✅ Indexed {indexed_features} features: {chunk['functionName']} ({chunk['featureType']})")
                                
                                except Exception as e:
                                    logger.error(f"Error storing feature from {relative_path}: {e}")
                            else:
                                logger.warning(f"Failed to generate embedding for feature in {relative_path}")
                    
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        skipped_files += 1
        
        logger.info("="*60)
        logger.info("🎉 IMPROVED FEATURE INDEXING COMPLETE!")
        logger.info(f"📁 Total files analyzed: {total_files}")
        logger.info(f"⏭️  Files skipped: {skipped_files}")
        logger.info(f"🎯 User features indexed: {indexed_features}")
        logger.info(f"📊 Average features per file: {indexed_features/max(total_files, 1):.1f}")
        logger.info("="*60)
        logger.info("Your chatbot now has accurate, detailed knowledge of your codebase!")

if __name__ == "__main__":
    try:
        # Load production environment explicitly (override any .env values)
        load_dotenv('.env.production', override=True)
        
        # Debug environment loading
        weaviate_url = os.getenv('WEAVIATE_URL')
        weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
        codebase_path = os.getenv('CODEBASE_PATH')
        
        logger.info(f"🔗 Using Weaviate URL: {weaviate_url}")
        logger.info(f"🔑 API key loaded: {'Yes' if weaviate_api_key else 'No'}")
        logger.info(f"📂 Codebase path: {codebase_path}")
        
        if not weaviate_url or not weaviate_api_key or not codebase_path:
            logger.error("❌ Missing required environment variables")
            logger.error("Please ensure .env.production has WEAVIATE_URL, WEAVIATE_API_KEY, and CODEBASE_PATH")
            exit(1)
        
        indexer = AppFeatureIndexer()
        indexer.index_codebase()
    except KeyboardInterrupt:
        logger.info("Indexing interrupted by user")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise
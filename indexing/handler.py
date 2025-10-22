import os
import weaviate
from pathlib import Path
import json
import hashlib
from typing import List, Dict
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import re

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AppFeatureIndexer:
    def __init__(self):
        # Configure Weaviate client with API key support  
        weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
        
        if weaviate_api_key:
            # Production: Use API key authentication
            self.weaviate_client = weaviate.Client(
                url=weaviate_url,
                auth_client_secret=weaviate.AuthApiKey(api_key=weaviate_api_key)
            )
        else:
            # Development: No authentication
            self.weaviate_client = weaviate.Client(url=weaviate_url)
        
        # Load local embedding model
        embedding_model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        logger.info(f"Loading embedding model: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        logger.info("Embedding model loaded successfully!")
        
        self.codebase_path = Path(os.getenv('CODEBASE_PATH', '.'))
        self.max_chunk_size = int(os.getenv('MAX_CHUNK_SIZE', 1000))
        
        self.setup_schema()
    
    def setup_schema(self):
        """Create Weaviate schema for app features"""
        schema = {
            "class": "AppFeature",
            "description": "App features and functionality for end users",
            "properties": [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "The code that implements this feature"
                },
                {
                    "name": "featureDescription", 
                    "dataType": ["text"],
                    "description": "What this feature does for users"
                },
                {
                    "name": "userBenefit",
                    "dataType": ["text"], 
                    "description": "How this helps users accomplish their goals"
                },
                {
                    "name": "featureType",
                    "dataType": ["string"],
                    "description": "Type of feature: authentication, data-entry, reporting, etc."
                },
                {
                    "name": "relatedFeatures",
                    "dataType": ["text"],
                    "description": "Other features this connects to"
                },
                {
                    "name": "userActions",
                    "dataType": ["text"],
                    "description": "What actions users can take with this feature"
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
            logger.info("Created AppFeature schema successfully")
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
    
    def analyze_user_feature(self, content: str, file_path: Path) -> Dict:
        """Analyze code to extract user-facing feature information"""
        
        content_lower = content.lower()
        file_name = file_path.name.lower()
        
        # Feature pattern matching
        feature_patterns = {
            'authentication': {
                'keywords': ['login', 'signup', 'password', 'auth', 'signin', 'register', 'logout'],
                'description': 'User login and account management',
                'benefit': 'Secure access to your personal data and app features',
                'actions': 'Sign in, sign up, reset password, manage account security',
                'related': 'Profile settings, password reset, account security, user preferences'
            },
            'user_profile': {
                'keywords': ['profile', 'account', 'user', 'personal', 'settings', 'preferences'],
                'description': 'Manage your personal account information',
                'benefit': 'Keep your account information current and customize your experience',
                'actions': 'Update profile, change settings, manage preferences, view account info',
                'related': 'Account security, notification settings, privacy controls'
            },
            'data_management': {
                'keywords': ['create', 'edit', 'delete', 'update', 'save', 'add', 'remove', 'modify'],
                'description': 'Create, edit, and organize your information',
                'benefit': 'Keep your data organized and up-to-date',
                'actions': 'Add new items, edit existing data, delete unwanted information, save changes',
                'related': 'Search and filtering, backup, data export'
            },
            'search_filter': {
                'keywords': ['search', 'filter', 'sort', 'find', 'query', 'lookup'],
                'description': 'Find and organize information quickly',
                'benefit': 'Quickly locate specific data without browsing through everything',
                'actions': 'Search by keywords, apply filters, sort results, find specific items',
                'related': 'Data management, reporting, advanced search options'
            },
            'reporting': {
                'keywords': ['report', 'export', 'download', 'print', 'analytics', 'summary'],
                'description': 'Generate reports and export your data',
                'benefit': 'Get insights from your data and share information with others',
                'actions': 'Generate reports, export to files, print documents, view analytics',
                'related': 'Search and filtering, data visualization, sharing options'
            },
            'communication': {
                'keywords': ['message', 'email', 'notification', 'alert', 'notify', 'contact'],
                'description': 'Stay informed with notifications and messages',
                'benefit': 'Never miss important updates or required actions',
                'actions': 'Receive notifications, send messages, manage communication preferences',
                'related': 'Settings, user preferences, email configuration'
            },
            'dashboard': {
                'keywords': ['dashboard', 'overview', 'summary', 'home', 'main', 'welcome'],
                'description': 'Get an overview of your important information',
                'benefit': 'Quickly see what needs your attention and access key features',
                'actions': 'View summaries, access quick actions, see recent activity',
                'related': 'Navigation, reporting, notifications'
            },
            'navigation': {
                'keywords': ['menu', 'nav', 'route', 'page', 'link', 'navigate'],
                'description': 'Move between different sections of the app',
                'benefit': 'Easily access all features and find what you need',
                'actions': 'Navigate between pages, use menus, access different sections',
                'related': 'Dashboard, search, user interface'
            },
            'forms': {
                'keywords': ['form', 'input', 'field', 'submit', 'validation', 'entry'],
                'description': 'Enter and submit information through forms',
                'benefit': 'Provide information to the system in an organized way',
                'actions': 'Fill out forms, submit data, validate information, save drafts',
                'related': 'Data management, validation, user input'
            },
            'file_management': {
                'keywords': ['upload', 'download', 'file', 'document', 'attachment', 'media'],
                'description': 'Upload, download, and manage files',
                'benefit': 'Store and access your documents and media files',
                'actions': 'Upload files, download documents, organize attachments, manage storage',
                'related': 'Data management, sharing, backup'
            }
        }
        
        # Determine feature type based on content analysis
        feature_type = 'general'
        max_matches = 0
        
        for ftype, info in feature_patterns.items():
            matches = sum(1 for keyword in info['keywords'] 
                         if keyword in content_lower or keyword in file_name)
            if matches > max_matches:
                max_matches = matches
                feature_type = ftype
        
        # Get feature information
        if feature_type in feature_patterns:
            feature_info = feature_patterns[feature_type]
        else:
            feature_info = {
                'description': 'App functionality that helps you accomplish tasks',
                'benefit': 'Provides tools to help you work more efficiently',
                'actions': 'Interact with the app to complete your goals',
                'related': 'Other app features and tools'
            }
        
        return {
            'type': feature_type,
            'description': feature_info['description'],
            'benefit': feature_info['benefit'],
            'actions': feature_info['actions'],
            'related': feature_info['related']
        }
    
    def extract_feature_chunks(self, file_path: Path, content: str) -> List[Dict]:
        """Extract user-facing features from code"""
        chunks = []
        language = self.get_file_language(file_path)
        
        if language == 'python':
            chunks.extend(self._extract_python_features(content, file_path))
        elif language in ['javascript', 'typescript']:
            chunks.extend(self._extract_js_features(content, file_path))
        elif language == 'markdown':
            chunks.extend(self._extract_markdown_features(content, file_path))
        else:
            # Fallback to content analysis
            chunks.extend(self._analyze_general_content(content, file_path))
        
        return chunks
    
    def _extract_python_features(self, content: str, file_path: Path) -> List[Dict]:
        """Extract user features from Python code"""
        chunks = []
        lines = content.split('\n')
        
        current_chunk = []
        current_function = None
        indent_level = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip comments and empty lines for function detection
            if not stripped or stripped.startswith('#'):
                if current_chunk:
                    current_chunk.append(line)
                continue
            
            # Detect function definitions that might be user-facing
            if stripped.startswith(('def ', 'async def ', 'class ')):
                # Save previous chunk if it represents a feature
                if current_chunk and self._is_user_facing_code('\n'.join(current_chunk)):
                    chunks.append(self._create_feature_chunk('\n'.join(current_chunk), file_path))
                
                # Start new chunk
                current_chunk = [line]
                indent_level = len(line) - len(line.lstrip())
                
                # Collect the entire function/class
                i += 1
                while i < len(lines):
                    if i >= len(lines):
                        break
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    
                    # End of function/class
                    if (next_stripped and 
                        len(next_line) - len(next_line.lstrip()) <= indent_level and 
                        not next_stripped.startswith(('#', '"""', "'''", '@'))):
                        break
                    
                    current_chunk.append(next_line)
                    i += 1
                
                # Check if this function represents a user feature
                function_content = '\n'.join(current_chunk)
                if self._is_user_facing_code(function_content):
                    chunks.append(self._create_feature_chunk(function_content, file_path))
                
                current_chunk = []
                continue
            
            # Collect non-function code that might be user-facing
            elif not current_chunk or len(line) - len(line.lstrip()) > indent_level:
                current_chunk.append(line)
        
        # Handle final chunk
        if current_chunk and self._is_user_facing_code('\n'.join(current_chunk)):
            chunks.append(self._create_feature_chunk('\n'.join(current_chunk), file_path))
        
        return chunks
    
    def _extract_js_features(self, content: str, file_path: Path) -> List[Dict]:
        """Extract user features from JavaScript/TypeScript code"""
        chunks = []
        lines = content.split('\n')
        
        current_chunk = []
        brace_count = 0
        in_function = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip empty lines and comments when not in function
            if not stripped or (stripped.startswith('//') and not in_function):
                if current_chunk:
                    current_chunk.append(line)
                continue
            
            # Detect function/component definitions
            if any(keyword in stripped for keyword in [
                'function ', 'const ', 'export default', 'export const',
                'class ', 'component', '=>'
            ]):
                # Save previous chunk if it's user-facing
                if current_chunk and not in_function and self._is_user_facing_code('\n'.join(current_chunk)):
                    chunks.append(self._create_feature_chunk('\n'.join(current_chunk), file_path))
                
                current_chunk = [line]
                in_function = True
                brace_count = line.count('{') - line.count('}')
            
            elif in_function:
                current_chunk.append(line)
                brace_count += line.count('{') - line.count('}')
                
                if brace_count <= 0:
                    # End of function - check if it's user-facing
                    function_content = '\n'.join(current_chunk)
                    if self._is_user_facing_code(function_content):
                        chunks.append(self._create_feature_chunk(function_content, file_path))
                    
                    current_chunk = []
                    in_function = False
                    brace_count = 0
            
            elif not in_function:
                current_chunk.append(line)
        
        # Handle final chunk
        if current_chunk and self._is_user_facing_code('\n'.join(current_chunk)):
            chunks.append(self._create_feature_chunk('\n'.join(current_chunk), file_path))
        
        return chunks
    
    def _extract_markdown_features(self, content: str, file_path: Path) -> List[Dict]:
        """Extract features from markdown documentation"""
        chunks = []
        sections = re.split(r'\n#+\s+', content)
        
        for section in sections:
            if len(section.strip()) > 50:  # Skip very short sections
                # Markdown is likely user documentation
                chunks.append(self._create_feature_chunk(section, file_path))
        
        return chunks
    
    def _analyze_general_content(self, content: str, file_path: Path) -> List[Dict]:
        """Analyze general content for user features"""
        chunks = []
        
        # Only process if content seems user-facing
        if self._is_user_facing_code(content):
            # Split into reasonable chunks
            sentences = re.split(r'[.!?]+', content)
            current_chunk = ""
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                if len(current_chunk) + len(sentence) < self.max_chunk_size:
                    current_chunk += sentence + ". "
                else:
                    if current_chunk:
                        chunks.append(self._create_feature_chunk(current_chunk.strip(), file_path))
                    current_chunk = sentence + ". "
            
            # Add final chunk
            if current_chunk:
                chunks.append(self._create_feature_chunk(current_chunk.strip(), file_path))
        
        return chunks
    
    def _is_user_facing_code(self, content: str) -> bool:
        """Determine if code represents user-facing functionality"""
        content_lower = content.lower()
        
        # User-facing indicators
        user_indicators = [
            'login', 'signup', 'register', 'auth', 'user', 'profile', 'account',
            'form', 'input', 'button', 'click', 'submit', 'save', 'create', 'edit',
            'delete', 'search', 'filter', 'sort', 'export', 'download', 'upload',
            'dashboard', 'report', 'notification', 'message', 'alert', 'menu',
            'navigate', 'page', 'view', 'display', 'show', 'render', 'component'
        ]
        
        # Technical indicators (less likely to be user-facing)
        technical_indicators = [
            'import', 'require', 'module.exports', 'class', 'extends', 'super',
            'constructor', '__init__', 'self.', 'this.', 'prototype', 'async',
            'await', 'promise', 'callback', 'middleware', 'router', 'express'
        ]
        
        user_score = sum(1 for indicator in user_indicators if indicator in content_lower)
        tech_score = sum(1 for indicator in technical_indicators if indicator in content_lower)
        
        # More user indicators than technical ones suggests user-facing code
        return user_score > tech_score and user_score > 0
    
    def _create_feature_chunk(self, content: str, file_path: Path) -> Dict:
        """Create a user-focused feature chunk"""
        content = content.strip()
        feature_analysis = self.analyze_user_feature(content, file_path)
        
        return {
            'content': content,
            'featureDescription': feature_analysis['description'],
            'userBenefit': feature_analysis['benefit'],
            'featureType': feature_analysis['type'],
            'relatedFeatures': feature_analysis['related'],
            'userActions': feature_analysis['actions'],
            'contentHash': hashlib.md5(content.encode()).hexdigest()
        }
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using sentence transformers"""
        try:
            # Create searchable text from feature data
            if isinstance(text, dict):
                searchable_text = f"{text.get('featureDescription', '')} {text.get('userBenefit', '')} {text.get('userActions', '')}"
            else:
                searchable_text = text
            
            # Truncate if too long
            if len(searchable_text) > 5000:
                searchable_text = searchable_text[:5000] + "..."
            
            embedding = self.embedding_model.encode(searchable_text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return []
    
    def index_codebase(self):
        """Index the entire codebase for user features"""
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
        
        logger.info(f"Starting to index app features: {self.codebase_path}")
        logger.info("Looking for user-facing functionality...")
        
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
                        
                        # Extract user-facing features
                        feature_chunks = self.extract_feature_chunks(file_path, content)
                        
                        for chunk in feature_chunks:
                            # Generate embedding for the feature
                            embedding = self.generate_embedding(chunk)
                            
                            if embedding:
                                try:
                                    # Store in Weaviate
                                    self.weaviate_client.data_object.create(
                                        data_object=chunk,
                                        class_name="AppFeature",
                                        vector=embedding
                                    )
                                    indexed_features += 1
                                    
                                    if indexed_features % 10 == 0:
                                        logger.info(f"✅ Indexed {indexed_features} features so far...")
                                
                                except Exception as e:
                                    logger.error(f"Error storing feature from {relative_path}: {e}")
                            else:
                                logger.warning(f"Failed to generate embedding for feature in {relative_path}")
                    
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}")
                        skipped_files += 1
        
        logger.info("="*60)
        logger.info("🎉 FEATURE INDEXING COMPLETE!")
        logger.info(f"📁 Total files analyzed: {total_files}")
        logger.info(f"⏭️  Files skipped: {skipped_files}")
        logger.info(f"🎯 User features indexed: {indexed_features}")
        logger.info(f"📊 Average features per file: {indexed_features/max(total_files, 1):.1f}")
        logger.info("="*60)
        logger.info("Your chatbot is now ready to help users understand app features!")

if __name__ == "__main__":
    try:
        indexer = AppFeatureIndexer()
        indexer.index_codebase()
    except KeyboardInterrupt:
        logger.info("Indexing interrupted by user")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise
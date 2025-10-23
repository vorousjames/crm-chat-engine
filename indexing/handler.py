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

# Load environment variables
load_dotenv('.env')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CRMFeatureIndexer:
    def __init__(self):
        # Weaviate setup (keep your existing code)
        weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
        
        if weaviate_api_key and weaviate_api_key != 'your-actual-weaviate-api-key-here':
            import weaviate.auth as wv_auth
            self.weaviate_client = weaviate.Client(
                url=weaviate_url,
                auth_client_secret=wv_auth.AuthApiKey(api_key=weaviate_api_key),
                timeout_config=(10, 30)
            )
        else:
            self.weaviate_client = weaviate.Client(url=weaviate_url)
        
        # Test connection
        try:
            logger.info(f"Testing connection to: {weaviate_url}")
            meta = self.weaviate_client.get_meta()
            logger.info(f"✅ Connected to Weaviate version: {meta.get('version', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Weaviate connection failed: {e}")
            raise

        # Load embedding model
        embedding_model_name = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
        logger.info(f"Loading embedding model: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        logger.info("Embedding model loaded successfully!")
        
        self.codebase_path = Path(os.getenv('CODEBASE_PATH', '.'))
        
        # YOUR ACTUAL USER WORKFLOWS - Based on your CRM architecture
        self.user_workflows = {
            'customer_estimate_request': {
                'user_goal': 'Get service estimate for construction project',
                'user_type': 'customer',
                'workflow_steps': [
                    'Visit service page (stamped concrete, demolition, etc.)',
                    'Click "Get Free Estimate" button',
                    'Fill out estimate form with name, phone, address, service type',
                    'Submit form and receive confirmation',
                    'Wait for staff callback within 24 hours'
                ],
                'ui_components': ['EstimateForm.tsx', 'EstimateFooter.tsx', 'EstimateHero.tsx'],
                'api_endpoints': ['/api/lead (POST)'],
                'user_inputs': ['Name', 'Phone number', 'Email', 'Property address', 'Service type'],
                'user_outputs': ['Confirmation message', 'Staff callback', 'Project estimate'],
                'business_benefit': 'Get professional estimate for construction needs',
                'keywords': ['estimate', 'quote', 'concrete', 'demolition', 'free estimate', 'service request']
            },
            
            'staff_lead_management': {
                'user_goal': 'Manage customer leads and track sales pipeline',
                'user_type': 'staff',
                'workflow_steps': [
                    'Access admin dashboard at /admin-dashboard',
                    'Click on Leads tab to view all customer inquiries',
                    'Select individual lead to view details',
                    'Update lead stage (inquiry → quote → project → completed)',
                    'Add notes and schedule follow-up activities',
                    'Record project revenue when completed'
                ],
                'ui_components': ['LeadsTab.tsx', 'NewLeadModal.tsx', 'DashboardTabDropdown.tsx'],
                'api_endpoints': ['/api/lead (GET, PUT)', '/api/user'],
                'user_inputs': ['Lead stage updates', 'Notes', 'Revenue amounts', 'Follow-up dates'],
                'user_outputs': ['Updated lead status', 'Pipeline reports', 'Revenue tracking'],
                'business_benefit': 'Convert website visitors into paying customers efficiently',
                'keywords': ['leads', 'pipeline', 'sales', 'follow up', 'customer management', 'revenue']
            },
            
            'service_area_discovery': {
                'user_goal': 'Find out if construction services are available in their area',
                'user_type': 'customer',
                'workflow_steps': [
                    'Visit location-specific page (cleveland-ohio, akron-ohio)',
                    'Read about services available in their city',
                    'View local project examples and testimonials',
                    'Request estimate for their specific location',
                    'Get confirmation of service availability'
                ],
                'ui_components': ['Location pages', 'EstimateFooter.tsx', 'Header.tsx'],
                'api_endpoints': ['/api/lead (POST)', '/api/page'],
                'user_inputs': ['Location/address', 'Service interest'],
                'user_outputs': ['Service availability confirmation', 'Local pricing', 'Area-specific examples'],
                'business_benefit': 'Ensure services are available before requesting estimate',
                'keywords': ['location', 'service area', 'cleveland', 'akron', 'availability', 'local service']
            },
            
            'staff_team_management': {
                'user_goal': 'Manage team members and user permissions',
                'user_type': 'admin',
                'workflow_steps': [
                    'Access admin dashboard',
                    'Navigate to Users tab',
                    'Add new team members with roles and permissions',
                    'Edit existing user access levels',
                    'Track team activity and performance'
                ],
                'ui_components': ['UsersTab.tsx', 'EditUserModal.tsx'],
                'api_endpoints': ['/api/user (GET, POST, PUT)'],
                'user_inputs': ['User name', 'Email', 'Role', 'Permissions'],
                'user_outputs': ['Team roster', 'Access control', 'Activity tracking'],
                'business_benefit': 'Control who can access sensitive business data',
                'keywords': ['users', 'team', 'permissions', 'roles', 'admin', 'staff management']
            },
            
            'marketing_page_creation': {
                'user_goal': 'Create marketing pages without coding',
                'user_type': 'staff',
                'workflow_steps': [
                    'Access Page Builder in admin dashboard',
                    'Choose page template or start blank',
                    'Add sections like hero, gallery, FAQ, contact forms',
                    'Configure content and images',
                    'Preview page before publishing',
                    'Publish live to website'
                ],
                'ui_components': ['Page Builder index.tsx', 'Dynamic page components'],
                'api_endpoints': ['/api/page (GET, POST, PUT)'],
                'user_inputs': ['Page content', 'Images', 'Form configurations'],
                'user_outputs': ['Live marketing pages', 'Lead generation forms', 'SEO-optimized content'],
                'business_benefit': 'Create professional marketing pages quickly without developer',
                'keywords': ['page builder', 'marketing', 'website', 'content', 'publish', 'landing page']
            }
        }
        
        self.setup_schema()
    
    def setup_schema(self):
        """Create user-workflow-focused schema"""
        schema = {
            "class": "AppFeature",
            "description": "User-facing workflows and features in the CRM system",
            "properties": [
                {
                    "name": "content",
                    "dataType": ["text"],
                    "description": "Code or documentation that supports this user workflow"
                },
                {
                    "name": "featureDescription", 
                    "dataType": ["text"],
                    "description": "What users can accomplish with this feature"
                },
                {
                    "name": "userBenefit",
                    "dataType": ["text"], 
                    "description": "Why users would want to use this feature"
                },
                {
                    "name": "featureType",
                    "dataType": ["string"],
                    "description": "Type of user workflow (customer_facing, staff_management, etc.)"
                },
                {
                    "name": "userActions",
                    "dataType": ["text"],
                    "description": "Step-by-step actions users take in the interface"
                },
                {
                    "name": "inputs",
                    "dataType": ["text"],
                    "description": "Information users need to provide"
                },
                {
                    "name": "outputs", 
                    "dataType": ["text"],
                    "description": "What users receive or accomplish"
                },
                {
                    "name": "actualWorkflow",
                    "dataType": ["text"],
                    "description": "Complete user journey from start to finish"
                },
                {
                    "name": "userType",
                    "dataType": ["string"],
                    "description": "Who uses this feature (customer, staff, admin)"
                },
                {
                    "name": "uiComponents",
                    "dataType": ["text"],
                    "description": "Interface components users interact with"
                },
                {
                    "name": "keywords",
                    "dataType": ["text"],
                    "description": "Terms users might use when asking about this feature"
                },
                {
                    "name": "filePath",
                    "dataType": ["string"],
                    "description": "Source file location"
                },
                {
                    "name": "contentHash",
                    "dataType": ["string"],
                    "description": "Hash for duplicate detection"
                }
            ],
            "vectorizer": "none"
        }
        
        try:
            # Delete existing schema
            try:
                self.weaviate_client.schema.delete_class("AppFeature")
                logger.info("Deleted existing AppFeature schema")
            except:
                pass
            
            # Create new schema
            self.weaviate_client.schema.create_class(schema)
            logger.info("Created user-workflow-focused schema successfully")
        except Exception as e:
            logger.error(f"Schema creation error: {e}")
            raise
    
    def extract_ui_workflow_features(self, file_path: Path, content: str) -> List[Dict]:
        """Extract features based on actual UI workflows rather than code analysis"""
        chunks = []
        
        # Identify which user workflow this file supports
        workflow_matches = self.match_file_to_workflows(file_path, content)
        
        for workflow_name, confidence in workflow_matches:
            if confidence > 0.3:  # Only high-confidence matches
                workflow = self.user_workflows[workflow_name]
                
                feature_chunk = {
                    'content': content[:1000],  # Sample of supporting code
                    'featureDescription': f"User workflow: {workflow['user_goal']}",
                    'userBenefit': workflow['business_benefit'],
                    'featureType': workflow_name,
                    'userActions': ' → '.join(workflow['workflow_steps']),
                    'inputs': ', '.join(workflow['user_inputs']),
                    'outputs': ', '.join(workflow['user_outputs']),
                    'actualWorkflow': ' → '.join(workflow['workflow_steps']),
                    'userType': workflow['user_type'],
                    'uiComponents': ', '.join(workflow['ui_components']),
                    'keywords': ', '.join(workflow['keywords']),
                    'filePath': str(file_path.relative_to(self.codebase_path)),
                    'contentHash': hashlib.md5(content.encode()).hexdigest()
                }
                chunks.append(feature_chunk)
        
        return chunks
    
    def match_file_to_workflows(self, file_path: Path, content: str) -> List[Tuple[str, float]]:
        """Match files to user workflows based on your actual CRM structure"""
        matches = []
        
        file_name = file_path.name.lower()
        file_content = content.lower()
        relative_path = str(file_path.relative_to(self.codebase_path)).lower();
        
        for workflow_name, workflow in self.user_workflows.items():
            confidence = 0.0
            
            # Check UI components mentioned in workflow
            for component in workflow['ui_components']:
                component_lower = component.lower()
                if component_lower in file_name or component_lower in relative_path:
                    confidence += 0.4
            
            # Check API endpoints
            for endpoint in workflow['api_endpoints']:
                if endpoint.replace('/api/', '').replace(' (', '').replace(')', '') in relative_path:
                    confidence += 0.3
            
            # Check keywords in content
            keyword_matches = sum(1 for kw in workflow['keywords'] if kw in file_content)
            confidence += (keyword_matches / len(workflow['keywords'])) * 0.3
            
            # Specific file pattern matching for your CRM
            if workflow_name == 'customer_estimate_request':
                if any(name in file_name for name in ['estimate', 'form', 'lead']):
                    confidence += 0.3
                if 'components' in relative_path and any(name in file_name for name in ['estimate', 'form']):
                    confidence += 0.4
            
            elif workflow_name == 'staff_lead_management':
                if any(name in file_name for name in ['leads', 'dashboard', 'modal']):
                    confidence += 0.3
                if 'admin' in relative_path or 'dashboard' in relative_path:
                    confidence += 0.3
            
            elif workflow_name == 'service_area_discovery':
                if any(location in relative_path for location in ['cleveland', 'akron']):
                    confidence += 0.4
                if 'pages' in relative_path and any(ext in file_name for ext in ['.tsx', '.ts']):
                    confidence += 0.2
            
            elif workflow_name == 'staff_team_management':
                if 'user' in file_name or 'team' in file_name:
                    confidence += 0.4
                if 'admin' in relative_path:
                    confidence += 0.2
            
            elif workflow_name == 'marketing_page_creation':
                if 'page' in file_name and 'builder' in relative_path:
                    confidence += 0.5
                if any(name in file_content for name in ['page', 'builder', 'dynamic']):
                    confidence += 0.2
            
            if confidence > 0:
                matches.append((workflow_name, confidence))
        
        # Sort by confidence
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def generate_workflow_embedding(self, feature_data: Dict) -> List[float]:
        """Generate embeddings focused on user language and workflows"""
        try:
            # Focus on user-friendly terms
            embedding_text = f"""
            User Goal: {feature_data.get('featureDescription', '')}
            What Users Do: {feature_data.get('userActions', '')}
            User Benefits: {feature_data.get('userBenefit', '')}
            User Provides: {feature_data.get('inputs', '')}
            User Gets: {feature_data.get('outputs', '')}
            User Type: {feature_data.get('userType', '')}
            Common Terms: {feature_data.get('keywords', '')}
            Interface Elements: {feature_data.get('uiComponents', '')}
            """.strip()
            
            if len(embedding_text) > 5000:
                embedding_text = embedding_text[:5000] + "..."
            
            embedding = self.embedding_model.encode(embedding_text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return []
    
    def index_codebase(self):
        """Index codebase focusing on user workflows rather than code functions"""
        # Target the most important user-facing files
        target_patterns = [
            # React components
            '**/components/**/*.tsx',
            '**/components/**/*.ts',
            
            # Pages
            '**/pages/**/*.tsx', 
            '**/pages/**/*.ts',
            
            # Admin interface
            '**/admin/**/*.tsx',
            '**/admin/**/*.ts',
            
            # API endpoints
            '**/api/**/*.ts',
            
            # Location pages  
            '**/cleveland-ohio/**/*',
            '**/akron-ohio/**/*',
            
            # Service pages
            '**/stamped-concrete/**/*',
            '**/demolition/**/*'
        ]
        
        skip_dirs = {
            '.git', 'node_modules', '.next', 'dist', 'build', 
            '.vscode', '__pycache__', 'logs', 'coverage'
        }
        
        total_files = 0
        indexed_workflows = 0
        
        logger.info(f"Starting USER-WORKFLOW indexing: {self.codebase_path}")
        logger.info("Focusing on actual user experiences in your CRM...")
        
        for pattern in target_patterns:
            for file_path in self.codebase_path.glob(pattern):
                # Skip directories and unwanted files
                if file_path.is_dir():
                    continue
                
                if any(skip_dir in str(file_path) for skip_dir in skip_dirs):
                    continue
                
                try:
                    total_files += 1
                    relative_path = file_path.relative_to(self.codebase_path)
                    logger.info(f"Analyzing workflow file [{total_files}]: {relative_path}")
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if not content.strip() or len(content) > 50000:
                        continue
                    
                    # Extract user workflow features
                    workflow_chunks = self.extract_ui_workflow_features(file_path, content)
                    
                    for chunk in workflow_chunks:
                        # Generate user-focused embedding
                        embedding = self.generate_workflow_embedding(chunk)
                        
                        if embedding:
                            try:
                                self.weaviate_client.data_object.create(
                                    data_object=chunk,
                                    class_name="AppFeature", 
                                    vector=embedding
                                )
                                indexed_workflows += 1
                                
                                logger.info(f"✅ Indexed user workflow: {chunk['featureType']} - {chunk['userType']}")
                            
                            except Exception as e:
                                logger.error(f"Error storing workflow from {relative_path}: {e}")
                
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
        
        logger.info("="*60)
        logger.info("🎉 USER-WORKFLOW INDEXING COMPLETE!")
        logger.info(f"📁 Files analyzed: {total_files}")
        logger.info(f"🎯 User workflows indexed: {indexed_workflows}")
        logger.info("="*60)
        logger.info("Your chatbot now understands actual USER EXPERIENCES!")
        logger.info("Users can ask: 'How do I get an estimate?' or 'How do I manage leads?'")

if __name__ == "__main__":
    try:
        load_dotenv('.env.production', override=True)
        
        indexer = CRMFeatureIndexer() 
        indexer.index_codebase()
    except KeyboardInterrupt:
        logger.info("Indexing interrupted by user")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        raise
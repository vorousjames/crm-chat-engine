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
        # Weaviate setup with improved connection handling
        weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        weaviate_api_key = os.getenv('WEAVIATE_API_KEY')
        
        logger.info(f"🔌 Connecting to Weaviate at: {weaviate_url}")
        
        if weaviate_api_key and weaviate_api_key != 'your-actual-weaviate-api-key-here':
            import weaviate.auth as wv_auth
            # Use additional_headers for Weaviate Cloud compatibility
            self.weaviate_client = weaviate.Client(
                url=weaviate_url,
                auth_client_secret=wv_auth.AuthApiKey(api_key=weaviate_api_key),
                timeout_config=(10, 60),
                startup_period=None,  # Skip startup check for cloud instances
                additional_headers={"X-Weaviate-Api-Key": weaviate_api_key}
            )
        else:
            self.weaviate_client = weaviate.Client(
                url=weaviate_url,
                timeout_config=(10, 60),
                startup_period=None
            )
        
        # Test connection
        try:
            logger.info("Testing connection to Weaviate...")
            meta = self.weaviate_client.get_meta()
            logger.info(f"✅ Connected to Weaviate version: {meta.get('version', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Weaviate connection failed: {e}")
            logger.error(f"Make sure your Weaviate Cloud instance is running and the URL/API key are correct")
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
        """Create dual-mode schema for both 'ask' and 'agent' capabilities"""
        schema = {
            "class": "AppFeature",
            "description": "Dual-mode features supporting both informational queries and agent actions",
            "properties": [
                # Original informational properties (for 'ask' mode)
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
                },
                
                # NEW: Mode-specific capabilities
                {
                    "name": "supportedModes",
                    "dataType": ["text"],
                    "description": "JSON array: which modes support this feature ['ask', 'agent', 'both']"
                },
                {
                    "name": "askModeCapabilities",
                    "dataType": ["text"],
                    "description": "JSON object: what the feature can explain/describe in ask mode"
                },
                {
                    "name": "agentModeCapabilities", 
                    "dataType": ["text"],
                    "description": "JSON object: what actions the agent can execute"
                },
                
                # Agent execution properties
                {
                    "name": "isActionable",
                    "dataType": ["boolean"],
                    "description": "Whether this workflow can be executed by an agent"
                },
                {
                    "name": "primaryApiEndpoint",
                    "dataType": ["string"], 
                    "description": "Main API endpoint for agent execution"
                },
                {
                    "name": "httpMethod",
                    "dataType": ["string"],
                    "description": "HTTP method for the primary action"
                },
                {
                    "name": "requestSchema",
                    "dataType": ["text"],
                    "description": "JSON schema defining required parameters for agent execution"
                },
                {
                    "name": "responseSchema", 
                    "dataType": ["text"],
                    "description": "JSON schema of expected API response"
                },
                {
                    "name": "authenticationRequired",
                    "dataType": ["boolean"],
                    "description": "Whether authentication is required for agent execution"
                },
                {
                    "name": "permissionsRequired",
                    "dataType": ["text"],
                    "description": "JSON array of required user roles/permissions"
                },
                {
                    "name": "safetyLevel",
                    "dataType": ["string"],
                    "description": "Safety classification: safe, caution, restricted, dangerous"
                },
                {
                    "name": "requiresConfirmation",
                    "dataType": ["boolean"],
                    "description": "Whether agent should ask for confirmation before executing"
                },
                {
                    "name": "sideEffects",
                    "dataType": ["text"],
                    "description": "JSON array describing what changes when this action executes"
                },
                {
                    "name": "rateLimits",
                    "dataType": ["text"],
                    "description": "JSON object with execution limits"
                },
                {
                    "name": "errorHandling",
                    "dataType": ["text"],
                    "description": "JSON object describing error scenarios and responses"
                },
                {
                    "name": "businessRules",
                    "dataType": ["text"],
                    "description": "JSON object with business logic and validation rules"
                },
                {
                    "name": "agentInstructions",
                    "dataType": ["text"],
                    "description": "JSON object with detailed agent execution instructions"
                },
                {
                    "name": "serviceContext",
                    "dataType": ["text"],
                    "description": "JSON object with business context and service information"
                },
                {
                    "name": "exampleExecution",
                    "dataType": ["text"],
                    "description": "JSON object showing sample agent execution with parameters"
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
            logger.info("✅ Created dual-mode (ASK + AGENT) schema successfully!")
            logger.info("📋 Schema supports both informational queries and executable actions")
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
    
    def discover_agent_schemas(self) -> Dict[str, Dict]:
        """Discover and load agent schema files from the SaaS codebase"""
        agent_schemas = {}
        
        # Look for agent-schemas directory and .json files
        schema_pattern = "**/agent-schemas/**/*.json"
        
        logger.info("🤖 Discovering agent schema files in your SaaS codebase...")
        
        for schema_file in self.codebase_path.glob(schema_pattern):
            try:
                with open(schema_file, 'r', encoding='utf-8') as f:
                    schema_data = json.load(f)
                
                # Use endpoint as key (e.g., "api_lead")
                endpoint = schema_data.get('endpoint', '').replace('/api/', '').replace('/', '_')
                key = f"api_{endpoint}" if endpoint else schema_file.stem
                
                agent_schemas[key] = {
                    'schema_data': schema_data,
                    'file_path': str(schema_file.relative_to(self.codebase_path)),
                    'last_modified': schema_file.stat().st_mtime
                }
                
                logger.info(f"✅ Loaded agent schema: {key} ({schema_data.get('description', 'No description')})")
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to load schema {schema_file}: {e}")
        
        logger.info(f"🤖 Discovered {len(agent_schemas)} agent schemas")
        return agent_schemas
    
    def create_dual_mode_features_from_schemas(self, agent_schemas: Dict[str, Dict]) -> List[Dict]:
        """Create features that support both ask and agent modes"""
        chunks = []
        
        for schema_key, schema_info in agent_schemas.items():
            schema_data = schema_info['schema_data']
            
            # Extract business context
            service_context = schema_data.get('service_context', {})
            workflow_context = schema_data.get('workflow_context', {})
            agent_instructions = schema_data.get('agent_instructions', {})
            
            for method, method_data in schema_data.get('methods', {}).items():
                # Determine supported modes
                is_agent_capable = method_data.get('agent_capability', False)
                supported_modes = []
                
                if is_agent_capable:
                    supported_modes.append('agent')
                
                # Always support ask mode for informational queries
                supported_modes.append('ask')
                
                # Create ask mode capabilities
                ask_capabilities = {
                    'can_explain_workflow': True,
                    'can_describe_process': True,
                    'can_provide_examples': True,
                    'can_explain_requirements': True,
                    'explanation_topics': [
                        f"How to {workflow_context.get('user_goal', '').lower()}",
                        f"What information is needed",
                        f"What happens after {method_data.get('action_type', '')}",
                        f"Who can {method_data.get('action_type', '')}"
                    ]
                }
                
                # Create agent capabilities (if applicable)
                agent_capabilities = {}
                if is_agent_capable:
                    agent_capabilities = {
                        'can_execute': True,
                        'actions': [method_data.get('action_type')],
                        'information_gathering': agent_instructions.get('required_information_gathering', []),
                        'conversation_flow': agent_instructions.get('conversation_flow', {}),
                        'when_to_use': agent_instructions.get('when_to_use', [])
                    }
                
                # Create rich dual-mode feature chunk
                feature_chunk = {
                    # Core informational data (for ask mode)
                    'content': json.dumps(schema_data, indent=2)[:1000],
                    'featureDescription': f"{method_data.get('description', '')} - {workflow_context.get('user_goal', '')}",
                    'userBenefit': workflow_context.get('business_value', ''),
                    'featureType': f"{method_data.get('action_type', '')}_{schema_key}",
                    'userActions': ' → '.join(workflow_context.get('user_journey', [])),
                    'userType': 'dual_mode_feature',
                    
                    # Standard workflow fields
                    'inputs': ', '.join([prop for prop in method_data.get('request_schema', {}).get('required', [])]),
                    'outputs': f"In ask mode: Detailed explanation. In agent mode: {method_data.get('description', '')}",
                    'actualWorkflow': ' → '.join(workflow_context.get('user_journey', [])),
                    'uiComponents': 'Chat interface supporting both ask and agent modes',
                    'keywords': f"{schema_data.get('endpoint', '')}, {method_data.get('action_type', '')}, {', '.join(service_context.get('services', []))}, help, how to, execute, create, request",
                    
                    # Mode-specific capabilities
                    'supportedModes': json.dumps(supported_modes),
                    'askModeCapabilities': json.dumps(ask_capabilities),
                    'agentModeCapabilities': json.dumps(agent_capabilities),
                    
                    # Agent execution metadata (for agent mode)
                    'isActionable': is_agent_capable,
                    'primaryApiEndpoint': schema_data.get('endpoint', '') if is_agent_capable else '',
                    'httpMethod': method.upper() if is_agent_capable else '',
                    'requestSchema': json.dumps(method_data.get('request_schema', {})) if is_agent_capable else '{}',
                    'responseSchema': json.dumps(method_data.get('response_schema', {})) if is_agent_capable else '{}',
                    'authenticationRequired': method_data.get('authentication_required', False),
                    'permissionsRequired': json.dumps(method_data.get('permissions_required', [])),
                    'safetyLevel': method_data.get('safety_level', 'safe'),
                    'requiresConfirmation': method_data.get('requires_confirmation', False),
                    'sideEffects': json.dumps(method_data.get('side_effects', [])),
                    'rateLimits': json.dumps(method_data.get('rate_limits', {})),
                    'errorHandling': json.dumps(method_data.get('error_scenarios', {})),
                    'businessRules': json.dumps(method_data.get('business_rules', {})),
                    'agentInstructions': json.dumps(agent_instructions),
                    'serviceContext': json.dumps(service_context),
                    'exampleExecution': json.dumps(method_data.get('example_execution', {})),
                    
                    'filePath': schema_info['file_path'],
                    'contentHash': hashlib.md5(json.dumps(schema_data).encode()).hexdigest()
                }
                chunks.append(feature_chunk)
        
        return chunks
    
    def generate_dual_mode_embedding(self, feature_data: Dict) -> List[float]:
        """Generate embeddings that work for both ask and agent modes"""
        try:
            supported_modes = json.loads(feature_data.get('supportedModes', '["ask"]'))
            
            # Base embedding text (works for both modes)
            embedding_text = f"""
            Feature: {feature_data.get('featureDescription', '')}
            User Goal: {feature_data.get('featureDescription', '')}
            What Users Do: {feature_data.get('userActions', '')}
            User Benefits: {feature_data.get('userBenefit', '')}
            User Type: {feature_data.get('userType', '')}
            Keywords: {feature_data.get('keywords', '')}
            """
            
            # Add ask mode specific terms
            if 'ask' in supported_modes:
                ask_caps = json.loads(feature_data.get('askModeCapabilities', '{}'))
                embedding_text += f"""
                
                Ask Mode: User can ask questions about this feature
                Can Explain: {', '.join(ask_caps.get('explanation_topics', []))}
                Provides Information: workflow steps, requirements, examples, process explanation
                """
            
            # Add agent mode specific terms
            if 'agent' in supported_modes and feature_data.get('isActionable'):
                agent_caps = json.loads(feature_data.get('agentModeCapabilities', '{}'))
                embedding_text += f"""
                
                Agent Mode: Agent can execute actions for this feature
                Agent Can Execute: {', '.join(agent_caps.get('actions', []))}
                API Endpoint: {feature_data.get('primaryApiEndpoint', '')}
                Automated Workflow: create, execute, perform, do this for me
                Agent Actions: {', '.join(agent_caps.get('actions', []))}
                """
            
            # Limit length
            if len(embedding_text) > 5000:
                embedding_text = embedding_text[:5000] + "..."
            
            embedding = self.embedding_model.encode(embedding_text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Dual-mode embedding generation error: {e}")
            return []
    
    def index_codebase(self):
        """Index codebase with dual-mode (ask + agent) capabilities"""
        logger.info(f"Starting DUAL-MODE indexing: {self.codebase_path}")
        logger.info("🔄 Creating unified index for both ASK and AGENT modes...")
        
        # Step 1: Index agent-capable features from schemas
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: Discovering Agent-Capable Features")
        logger.info("="*60)
        agent_schemas = self.discover_agent_schemas()
        dual_mode_chunks = self.create_dual_mode_features_from_schemas(agent_schemas)
        
        indexed_dual_features = 0
        for chunk in dual_mode_chunks:
            embedding = self.generate_dual_mode_embedding(chunk)
            if embedding:
                try:
                    self.weaviate_client.data_object.create(
                        data_object=chunk,
                        class_name="AppFeature",
                        vector=embedding
                    )
                    indexed_dual_features += 1
                    modes = json.loads(chunk.get('supportedModes', '[]'))
                    logger.info(f"✅ Indexed dual-mode: {chunk.get('featureType')} (modes: {', '.join(modes)})")
                except Exception as e:
                    logger.error(f"Error storing dual-mode feature: {e}")
        
        # Step 2: Index ask-only features from workflow patterns
        logger.info("\n" + "="*60)
        logger.info("PHASE 2: Indexing Ask-Only Workflow Features")
        logger.info("="*60)
        
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
            '.vscode', '__pycache__', 'logs', 'coverage', 'agent-schemas'
        }
        
        total_files = 0
        indexed_ask_features = 0
        
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
                    
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    if not content.strip() or len(content) > 50000:
                        continue
                    
                    # Extract ask-only workflow features
                    workflow_chunks = self.extract_ui_workflow_features(file_path, content)
                    
                    for chunk in workflow_chunks:
                        # Enhance with ask-mode metadata
                        chunk['supportedModes'] = json.dumps(['ask'])
                        chunk['askModeCapabilities'] = json.dumps({
                            'can_explain_workflow': True,
                            'can_describe_process': True,
                            'can_provide_examples': True,
                            'explanation_topics': [
                                f"How to {chunk.get('featureDescription', '').lower()}",
                                "What steps are involved",
                                "What information is needed"
                            ]
                        })
                        chunk['agentModeCapabilities'] = json.dumps({})
                        chunk['isActionable'] = False
                        
                        # Generate ask-focused embedding
                        embedding = self.generate_dual_mode_embedding(chunk)
                        
                        if embedding:
                            try:
                                self.weaviate_client.data_object.create(
                                    data_object=chunk,
                                    class_name="AppFeature", 
                                    vector=embedding
                                )
                                indexed_ask_features += 1
                                
                            except Exception as e:
                                logger.error(f"Error storing ask-mode feature from {relative_path}: {e}")
                
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
        
        logger.info("\n" + "="*60)
        logger.info("🎉 DUAL-MODE INDEXING COMPLETE!")
        logger.info("="*60)
        logger.info(f"📁 Files analyzed: {total_files}")
        logger.info(f"🤖 Agent-capable features: {indexed_dual_features}")
        logger.info(f"❓ Ask-only features: {indexed_ask_features}")
        logger.info(f"📊 Total features indexed: {indexed_dual_features + indexed_ask_features}")
        logger.info("="*60)
        logger.info("💬 ASK MODE: 'How do I create a lead?' → Explains the process")
        logger.info("🤖 AGENT MODE: 'Create a lead for John Doe' → Executes the action")
        logger.info("🔄 SEAMLESS: Same business context, different interaction modes")
        logger.info("="*60)

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
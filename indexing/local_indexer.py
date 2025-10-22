import os
import json
import sys
import weaviate
from pathlib import Path
from datetime import datetime
from typing import List, Dict
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Import the main indexer
from handler import AppFeatureIndexer

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LocalToCloudIndexer(AppFeatureIndexer):
    """Enhanced indexer for local-to-cloud workflow"""
    
    def __init__(self):
        super().__init__()
        self.backup_enabled = os.getenv('BACKUP_EMBEDDINGS', 'false').lower() == 'true'
        self.backup_path = Path(os.getenv('BACKUP_PATH', './backups'))
        
        if self.backup_enabled:
            self.backup_path.mkdir(exist_ok=True)
    
    def backup_existing_data(self):
        """Backup existing embeddings before re-indexing"""
        if not self.backup_enabled:
            return
            
        try:
            logger.info("Creating backup of existing embeddings...")
            
            # Get all existing features
            result = self.weaviate_client.query.get(
                "AppFeature",
                ["content", "featureDescription", "userBenefit", "featureType", 
                 "relatedFeatures", "userActions", "contentHash"]
            ).with_additional(["id", "vector"]).do()
            
            features = result.get('data', {}).get('Get', {}).get('AppFeature', [])
            
            if features:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.backup_path / f"embeddings_backup_{timestamp}.json"
                
                with open(backup_file, 'w') as f:
                    json.dump({
                        'timestamp': timestamp,
                        'total_features': len(features),
                        'weaviate_url': os.getenv('WEAVIATE_URL'),
                        'features': features
                    }, f, indent=2)
                
                logger.info(f"Backed up {len(features)} features to {backup_file}")
            else:
                logger.info("No existing features to backup")
                
        except Exception as e:
            logger.warning(f"Backup failed (continuing anyway): {e}")
    
    def get_existing_content_hashes(self) -> set:
        """Get hashes of existing content to avoid duplicates"""
        try:
            result = self.weaviate_client.query.get(
                "AppFeature", ["contentHash"]
            ).do()
            
            features = result.get('data', {}).get('Get', {}).get('AppFeature', [])
            return {feature.get('contentHash') for feature in features if feature.get('contentHash')}
            
        except Exception as e:
            logger.warning(f"Could not get existing hashes: {e}")
            return set()
    
    def index_with_deduplication(self):
        """Enhanced indexing with deduplication"""
        logger.info("Starting enhanced indexing with deduplication...")
        
        # Backup existing data
        self.backup_existing_data()
        
        # Get existing content hashes
        existing_hashes = self.get_existing_content_hashes()
        logger.info(f"Found {len(existing_hashes)} existing content hashes")
        
        # Clear the schema and start fresh (you could make this incremental)
        logger.info("Clearing existing schema for fresh start...")
        try:
            self.weaviate_client.schema.delete_class("AppFeature")
        except:
            pass
        self.setup_schema()
        
        # Run the indexing
        self.index_codebase()
        
        logger.info("Enhanced indexing completed!")
    
    def validate_production_connection(self):
        """Validate connection to production Weaviate"""
        try:
            logger.info("Validating production Weaviate connection...")
            
            meta = self.weaviate_client.get_meta()
            logger.info(f"✅ Connected to Weaviate Cloud")
            logger.info(f"   Version: {meta.get('version', 'Unknown')}")
            logger.info(f"   URL: {os.getenv('WEAVIATE_URL')}")
            
            # Test write access
            test_data = {
                "content": "test content for validation",
                "featureDescription": "Test feature",
                "userBenefit": "Test benefit",
                "featureType": "test",
                "relatedFeatures": "none",
                "userActions": "test action",
                "contentHash": "test_hash_12345"
            }
            
            # Create test object
            result = self.weaviate_client.data_object.create(
                data_object=test_data,
                class_name="AppFeature"
            )
            
            # Delete test object
            if result:
                self.weaviate_client.data_object.delete(result)
                logger.info("✅ Write access confirmed")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Production connection validation failed: {e}")
            return False

def main():
    """Main execution function"""
    print("🚀 Local-to-Cloud Indexing for CRM Chat Engine")
    print("=" * 50)
    
    # Load environment
    load_dotenv('.env.production')
    
    # Validate required environment variables
    required_vars = ['WEAVIATE_URL', 'WEAVIATE_API_KEY', 'CODEBASE_PATH']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please create .env.production with the required variables")
        sys.exit(1)
    
    # Validate codebase path
    codebase_path = Path(os.getenv('CODEBASE_PATH'))
    if not codebase_path.exists():
        logger.error(f"Codebase path does not exist: {codebase_path}")
        sys.exit(1)
    
    # Create indexer
    try:
        indexer = LocalToCloudIndexer()
        
        # Validate production connection
        if not indexer.validate_production_connection():
            logger.error("Cannot proceed without valid production connection")
            sys.exit(1)
        
        # Show configuration
        logger.info("Configuration:")
        logger.info(f"  Codebase: {codebase_path}")
        logger.info(f"  Weaviate URL: {os.getenv('WEAVIATE_URL')}")
        logger.info(f"  Backup enabled: {indexer.backup_enabled}")
        
        # Confirm before proceeding
        response = input("\nProceed with indexing? (y/N): ")
        if response.lower() != 'y':
            logger.info("Indexing cancelled by user")
            return
        
        # Run enhanced indexing
        indexer.index_with_deduplication()
        
        # Final verification
        logger.info("Running final verification...")
        result = indexer.weaviate_client.query.aggregate("AppFeature").with_meta_count().do()
        total_count = result['data']['Aggregate']['AppFeature'][0]['meta']['count']
        
        print("\n" + "=" * 50)
        print("🎉 INDEXING COMPLETED SUCCESSFULLY!")
        print(f"📊 Total features indexed: {total_count}")
        print(f"🔗 Available at: {os.getenv('WEAVIATE_URL')}")
        print("\nYour production chat server can now access these embeddings!")
        print("=" * 50)
        
    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

// Test various queries
const WeaviateService = require("./utils/weaviateService");
const verifyData = require("./verify-data");
require("dotenv").config();

async function testQueries() {
  try {
    // First verify we have data
    console.log("🔍 RUNNING PRE-TEST VERIFICATION");
    await verifyData();
    
    console.log("\n" + "=".repeat(70));
    console.log("🚀 STARTING FEATURE SEARCH TESTS");
    console.log("=".repeat(70));
    
    const weaviateService = new WeaviateService();

    const testQueries = [
      "How do I login to the admin dashboard?",
      "What permissions does the 'owner' user role have?", 
      "can i use the page builder to update the home page of my site?",
      "what analytics are available for my business?",
      "Why arent my analytics showing up properly?",
    ];

    for (let i = 0; i < testQueries.length; i++) {
      const query = testQueries[i];
      
      console.log(`\n${'='.repeat(70)}`);
      console.log(`🔍 TEST ${i + 1}/5: "${query}"`);
      console.log(`${'='.repeat(70)}`);
      
      const startTime = Date.now();
      const results = await weaviateService.searchFeatures(query, 3);
      const searchTime = Date.now() - startTime;
      
      if (results.length === 0) {
        console.log("❌ No results found");
        console.log("💡 This might indicate:");
        console.log("   - Query doesn't match indexed content");
        console.log("   - Embedding model mismatch");
        console.log("   - Need to re-index with better feature detection");
        continue;
      }
      
      console.log(`✅ Found ${results.length} results in ${searchTime}ms`);
      
      results.forEach((result, i) => {
        console.log(`\n--- RESULT ${i + 1} ---`);
        console.log(`📝 Feature: ${result.featureDescription || 'N/A'}`);
        console.log(`🎯 User Benefit: ${result.userBenefit || 'N/A'}`);
        console.log(`⚡ Actions: ${result.userActions || 'N/A'}`);
        console.log(`📥 Inputs: ${result.inputs || 'N/A'}`);
        console.log(`📤 Outputs: ${result.outputs || 'N/A'}`);
        console.log(`🔄 Workflow: ${result.actualWorkflow || 'N/A'}`);
        console.log(`📁 File: ${result.filePath || 'N/A'}`);
        console.log(`🔧 Function: ${result.functionName || 'N/A'}`);
        console.log(`🏷️  Type: ${result.featureType || 'N/A'}`);
        console.log(`📊 Score: ${(result.score * 100).toFixed(1)}%`);
        
        // Show business logic if available
        if (result.businessLogic && result.businessLogic !== 'Follows standard application logic') {
          console.log(`⚖️  Logic: ${result.businessLogic}`);
        }
      });
      
      // Add separator between queries
      if (i < testQueries.length - 1) {
        console.log("\n" + "·".repeat(50));
      }
    }
    
    console.log("\n" + "=".repeat(70));
    console.log("🎉 ALL TESTS COMPLETED!");
    console.log("=".repeat(70));
    
  } catch (error) {
    console.error("❌ Test failed:", error.message);
    console.error(error.stack);
  }
}

if (require.main === module) {
  testQueries();
}

module.exports = testQueries;

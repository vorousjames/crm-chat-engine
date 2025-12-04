const WeaviateService = require("./utils/weaviateService");
require("dotenv").config();

async function verifyIndexedData() {
  try {
    console.log("🔍 VERIFYING INDEXED DATA");
    console.log("=" * 50);

    const weaviateService = new WeaviateService();

    // Test connection first
    const connected = await weaviateService.testConnection();
    if (!connected) {
      console.error("❌ Cannot connect to Weaviate");
      return;
    }

    // Get total count
    const totalFeatures = await weaviateService.getFeatureCount();
    console.log(`📊 Total indexed features: ${totalFeatures}`);

    if (totalFeatures === 0) {
      console.log("⚠️  No features found! You may need to run indexing first.");
      console.log("Run: python indexing/handler.py");
      return;
    }

    // Get sample data
    const samples = await weaviateService.getSampleFeatures(5);

    console.log(`\n📋 Sample features (showing ${samples.length}):`);
    console.log("-".repeat(60));

    samples.forEach((feature, i) => {
      console.log(`\n${i + 1}. Function: ${feature.functionName || "N/A"}`);
      console.log(`   Type: ${feature.featureType || "N/A"}`);
      console.log(
        `   Description: ${(feature.featureDescription || "N/A").substring(
          0,
          80
        )}...`
      );
      console.log(`   File: ${feature.filePath || "N/A"}`);
      console.log(
        `   Benefit: ${(feature.userBenefit || "N/A").substring(0, 60)}...`
      );
    });

    console.log("\n" + "=" * 50);
    console.log("✅ Data verification complete!");
  } catch (error) {
    console.error("❌ Verification failed:", error.message);
    console.error(error.stack);
  }
}

if (require.main === module) {
  verifyIndexedData();
}

module.exports = verifyIndexedData;

const axios = require("axios");

const BASE_URL = "http://localhost:3001";
const API_KEY = process.env.API_KEY || "test-key";

async function testEndpoints() {
  console.log("🧪 Testing Express.js Chat API Server...\n");

  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  };

  try {
    // Test 1: Health check
    console.log("1. Testing health check...");
    const healthResponse = await axios.get(`${BASE_URL}/api/health/check`);
    console.log("✅ Health check:", healthResponse.data.status);

    // Test 2: Chat endpoint
    console.log("\n2. Testing chat endpoint...");
    const chatResponse = await axios.post(
      `${BASE_URL}/api/chat/ask`,
      {
        message: "How do I log into my account?",
        userId: "test-user",
      },
      { headers }
    );

    console.log("✅ Chat response received");
    console.log("   Response length:", chatResponse.data.response.length);
    console.log("   Sources found:", chatResponse.data.sources.length);
    console.log("   Processing time:", chatResponse.data.processingTime + "ms");

    // Test 3: Feature types
    console.log("\n3. Testing feature types...");
    const typesResponse = await axios.get(
      `${BASE_URL}/api/chat/features/types`,
      { headers }
    );
    console.log("✅ Feature types:", typesResponse.data.featureTypes.length);

    // Test 4: Suggestions
    console.log("\n4. Testing suggestions...");
    const suggestionsResponse = await axios.get(
      `${BASE_URL}/api/chat/suggestions`,
      { headers }
    );
    console.log("✅ Suggestions:", suggestionsResponse.data.suggestions.length);

    console.log("\n🎉 All tests passed!");
  } catch (error) {
    console.error("❌ Test failed:", error.response?.data || error.message);
  }
}

// Run tests
testEndpoints();

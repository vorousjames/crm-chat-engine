const weaviate = require("weaviate-ts-client").default;
const logger = require("./logger");

class WeaviateService {
  constructor() {
    this.client = this.initWeaviateClient();
    logger.info("WeaviateService initialized successfully");
  }

  initWeaviateClient() {
    const weaviateUrl = process.env.WEAVIATE_URL || "http://localhost:8080";
    const weaviateApiKey = process.env.WEAVIATE_API_KEY;

    logger.info(`Connecting to Weaviate Cloud at: ${weaviateUrl}`);

    try {
      // For Weaviate Cloud, we need to configure it differently
      if (weaviateUrl.includes("weaviate.cloud")) {
        return weaviate.client({
          scheme: "https",
          host: weaviateUrl.replace("https://", ""),
          apiKey: new weaviate.ApiKey(weaviateApiKey),
          headers: {
            "X-OpenAI-Api-Key": "", // Not needed for your setup
          },
        });
      } else {
        // Local Weaviate setup
        return weaviate.client({
          scheme: weaviateUrl.startsWith("https") ? "https" : "http",
          host: weaviateUrl.replace(/https?:\/\//, ""),
          ...(weaviateApiKey &&
            weaviateApiKey !== "your-actual-weaviate-api-key-here" && {
              apiKey: new weaviate.ApiKey(weaviateApiKey),
            }),
        });
      }
    } catch (error) {
      logger.error("Failed to initialize Weaviate client:", error);
      throw error;
    }
  }

  async testConnection() {
    try {
      const meta = await this.client.misc.metaGetter().do();
      logger.info("✅ Weaviate Cloud connection successful", {
        version: meta.version,
      });
      return true;
    } catch (error) {
      logger.error("❌ Weaviate Cloud connection failed", {
        error: error.message,
      });
      return false;
    }
  }

  async searchFeatures(query, limit = 5) {
    try {
      // Test connection first
      const isConnected = await this.testConnection();
      if (!isConnected) {
        throw new Error("Weaviate Cloud connection failed");
      }

      logger.debug("Searching for user workflows", { query, limit });

      // Check if AppFeature class exists first
      try {
        const schema = await this.client.schema
          .classGetter()
          .withClassName("AppFeature")
          .do();
        logger.debug("AppFeature class found", {
          properties: schema.properties?.length,
        });
      } catch (schemaError) {
        logger.error(
          "AppFeature class not found - you may need to re-run the indexer",
          { error: schemaError.message }
        );
        throw new Error(
          "AppFeature class not found in Weaviate. Please re-run the indexing process."
        );
      }

      // Use Weaviate's built-in text search
      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields([
          "featureDescription",
          "userBenefit",
          "featureType",
          "userActions",
          "inputs",
          "outputs",
          "actualWorkflow",
          "userType",
          "uiComponents",
          "keywords",
          "_additional { certainty distance }",
        ])
        .withNearText({
          concepts: [query],
          certainty: 0.6,
        })
        .withLimit(limit)
        .do();

      const features = result?.data?.Get?.AppFeature || [];

      logger.debug(
        `Found ${features.length} relevant workflows for query: "${query}"`
      );

      return features.map((feature) => ({
        featureDescription:
          feature.featureDescription || "No description available",
        userBenefit: feature.userBenefit || "User benefit not specified",
        featureType: feature.featureType || "unknown",
        userActions: feature.userActions || "No actions specified",
        inputs: feature.inputs || "No inputs specified",
        outputs: feature.outputs || "No outputs specified",
        actualWorkflow: feature.actualWorkflow || "No workflow specified",
        userType: feature.userType || "unknown",
        uiComponents: feature.uiComponents || "No components specified",
        keywords: feature.keywords || "No keywords",
        score: feature._additional?.certainty || 0.7,
      }));
    } catch (error) {
      logger.error("Feature search failed", {
        error: error.message,
        weaviateUrl: process.env.WEAVIATE_URL,
      });
      throw error;
    }
  }

  async getFeatureTypes() {
    try {
      const result = await this.client.graphql
        .aggregate()
        .withClassName("AppFeature")
        .withFields("featureType { count value }")
        .do();

      const aggregations = result?.data?.Aggregate?.AppFeature || [];
      return aggregations[0]?.featureType?.map((item) => item.value) || [];
    } catch (error) {
      logger.error("Failed to get feature types", { error: error.message });
      return [];
    }
  }

  async getSuggestedQuestions() {
    try {
      // Get a sample of different workflow types
      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields(["keywords", "featureType", "userType"])
        .withLimit(10)
        .do();

      const features = result?.data?.Get?.AppFeature || [];

      // Generate questions based on keywords and workflow types
      const questions = [];

      features.forEach((feature) => {
        const keywords =
          feature.keywords?.split(",").map((k) => k.trim()) || [];
        const userType = feature.userType;
        const featureType = feature.featureType;

        // Generate contextual questions
        if (featureType === "customer_estimate_request") {
          questions.push(
            "How do I get an estimate?",
            "How do I request a quote?"
          );
        } else if (featureType === "staff_lead_management") {
          questions.push(
            "How do I manage leads?",
            "How do I track customer inquiries?"
          );
        } else if (featureType === "service_area_discovery") {
          questions.push(
            "Do you serve my area?",
            "What locations do you cover?"
          );
        }
      });

      return [...new Set(questions)]; // Remove duplicates
    } catch (error) {
      logger.error("Failed to get suggested questions", {
        error: error.message,
      });
      return [
        "How do I get an estimate?",
        "How do I manage leads?",
        "Do you serve my area?",
        "How do I add team members?",
      ];
    }
  }
}

module.exports = WeaviateService;

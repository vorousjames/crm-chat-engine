const weaviate = require("weaviate-ts-client").default;
const logger = require("./logger");

class WeaviateService {
  constructor() {
    this.client = this.initWeaviateClient();
    // Remove the embedding model initialization - let Weaviate handle it
    logger.info("WeaviateService initialized successfully");
  }

  initWeaviateClient() {
    const weaviateUrl = process.env.WEAVIATE_URL || "http://localhost:8080";
    const weaviateApiKey = process.env.WEAVIATE_API_KEY;

    if (
      weaviateApiKey &&
      weaviateApiKey !== "your-actual-weaviate-api-key-here"
    ) {
      return weaviate.client({
        scheme: "http",
        host: weaviateUrl.replace("http://", "").replace("https://", ""),
        apiKey: new weaviate.ApiKey(weaviateApiKey),
      });
    } else {
      return weaviate.client({
        scheme: "http",
        host: weaviateUrl.replace("http://", "").replace("https://", ""),
      });
    }
  }

  async searchFeatures(query, limit = 5) {
    try {
      logger.debug("Searching for user workflows", { query, limit });

      // Use Weaviate's built-in text search instead of generating embeddings
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

      logger.debug(`Found ${features.length} relevant workflows`);

      return features.map((feature) => ({
        featureDescription: feature.featureDescription,
        userBenefit: feature.userBenefit,
        featureType: feature.featureType,
        userActions: feature.userActions,
        inputs: feature.inputs,
        outputs: feature.outputs,
        actualWorkflow: feature.actualWorkflow,
        userType: feature.userType,
        uiComponents: feature.uiComponents,
        keywords: feature.keywords,
        score: feature._additional?.certainty || 0.7,
      }));
    } catch (error) {
      logger.error("Feature search failed", { error: error.message });
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

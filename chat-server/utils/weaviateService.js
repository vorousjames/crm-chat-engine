const weaviate = require("weaviate-ts-client").default;
const logger = require("./logger");

class WeaviateService {
  constructor() {
    this.client = this.initWeaviateClient();
    this.embedder = null;
    this.embeddingModelReady = false;

    // Initialize embedding model asynchronously but don't wait
    this.initEmbeddingModel().catch((error) => {
      logger.error("Failed to initialize embedding model:", error);
    });

    logger.info("WeaviateService initialized successfully");
  }

  initWeaviateClient() {
    const weaviateUrl = process.env.WEAVIATE_URL || "http://localhost:8080";
    const weaviateApiKey = process.env.WEAVIATE_API_KEY;

    logger.info(`Connecting to Weaviate Cloud at: ${weaviateUrl}`);

    try {
      if (weaviateUrl.includes("weaviate.cloud")) {
        return weaviate.client({
          scheme: "https",
          host: weaviateUrl.replace("https://", ""),
          apiKey: new weaviate.ApiKey(weaviateApiKey),
        });
      } else {
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

  async initEmbeddingModel() {
    try {
      const { pipeline } = require("@xenova/transformers");
      logger.info("Loading embedding model: all-MiniLM-L6-v2");
      this.embedder = await pipeline(
        "feature-extraction",
        "Xenova/all-MiniLM-L6-v2"
      );
      this.embeddingModelReady = true;
      logger.info("Embedding model loaded successfully!");
    } catch (error) {
      logger.error("Failed to load embedding model:", error);
      this.embeddingModelReady = false;
      throw error;
    }
  }

  async generateEmbedding(text) {
    // Wait for embedding model to be ready if it's still loading
    if (!this.embeddingModelReady) {
      logger.info("Waiting for embedding model to finish loading...");

      // Wait up to 30 seconds for the model to load
      let attempts = 0;
      while (!this.embeddingModelReady && attempts < 60) {
        await new Promise((resolve) => setTimeout(resolve, 500));
        attempts++;
      }

      if (!this.embeddingModelReady) {
        throw new Error("Embedding model failed to load within timeout period");
      }
    }

    if (!this.embedder) {
      throw new Error("Embedding model not initialized");
    }

    try {
      const output = await this.embedder(text, {
        pooling: "mean",
        normalize: true,
      });
      return Array.from(output.data);
    } catch (error) {
      logger.error("Embedding generation failed:", error);
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

      // Generate embedding for the query (this will wait if model is still loading)
      logger.debug("Generating embedding for query...");
      const queryEmbedding = await this.generateEmbedding(query);
      logger.debug("Embedding generated successfully");

      // Use nearVector instead of nearText
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
        .withNearVector({
          vector: queryEmbedding,
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
      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields(["keywords", "featureType", "userType"])
        .withLimit(10)
        .do();

      const features = result?.data?.Get?.AppFeature || [];
      const questions = [];

      features.forEach((feature) => {
        const featureType = feature.featureType;

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

      return [...new Set(questions)];
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

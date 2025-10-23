const weaviate = require("weaviate-ts-client").default;
const { SentenceTransformer } = require("@xenova/transformers");

class WeaviateService {
  constructor() {
    this.client = weaviate.client({
      scheme: process.env.WEAVIATE_URL?.startsWith("https") ? "https" : "http",
      host:
        process.env.WEAVIATE_URL?.replace(/^https?:\/\//, "") ||
        "localhost:8080",
      apiKey: process.env.WEAVIATE_API_KEY
        ? new weaviate.ApiKey(process.env.WEAVIATE_API_KEY)
        : undefined,
      timeout: {
        query: 30000,
        insert: 30000,
      },
    });

    this.embeddingModel = null;
    this.initEmbeddingModel();
  }

  async initEmbeddingModel() {
    try {
      // Use the same model as your indexer
      const modelName = process.env.EMBEDDING_MODEL || "all-MiniLM-L6-v2";
      console.log(`Loading embedding model: ${modelName}`);
      this.embeddingModel = await SentenceTransformer.from_pretrained(
        `Xenova/${modelName}`
      );
      console.log("Embedding model loaded successfully!");
    } catch (error) {
      console.error("Failed to load embedding model:", error);
    }
  }

  async generateEmbedding(text) {
    if (!this.embeddingModel) {
      throw new Error("Embedding model not initialized");
    }

    try {
      const output = await this.embeddingModel(text, {
        pooling: "mean",
        normalize: true,
      });
      return Array.from(output.data);
    } catch (error) {
      console.error("Embedding generation failed:", error);
      throw error;
    }
  }

  async searchFeatures(query, limit = 5) {
    try {
      const embedding = await this.generateEmbedding(query);

      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields([
          "content",
          "featureDescription",
          "userBenefit",
          "featureType",
          "relatedFeatures",
          "userActions",
          "inputs",
          "outputs",
          "businessLogic",
          "actualWorkflow",
          "filePath",
          "functionName",
          "contentHash",
          "_additional { certainty distance }",
        ])
        .withNearVector({
          vector: embedding,
          certainty: 0.7,
        })
        .withLimit(limit)
        .do();

      const features = result.data.Get.AppFeature || [];

      // Add score for compatibility with test file
      return features.map((feature) => ({
        ...feature,
        score: feature._additional?.certainty || 0,
      }));
    } catch (error) {
      console.error("Feature search error:", error);
      return [];
    }
  }

  async getFeatureCount() {
    try {
      const result = await this.client.graphql
        .aggregate()
        .withClassName("AppFeature")
        .withFields("meta { count }")
        .do();

      return result.data.Aggregate.AppFeature[0]?.meta?.count || 0;
    } catch (error) {
      console.error("Count query error:", error);
      return 0;
    }
  }

  async getSampleFeatures(limit = 5) {
    try {
      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields([
          "featureDescription",
          "featureType",
          "functionName",
          "filePath",
          "userBenefit",
        ])
        .withLimit(limit)
        .do();

      return result.data.Get.AppFeature || [];
    } catch (error) {
      console.error("Sample query error:", error);
      return [];
    }
  }

  async testConnection() {
    try {
      const meta = await this.client.misc.metaGetter().do();
      console.log(`✅ Connected to Weaviate version: ${meta.version}`);
      return true;
    } catch (error) {
      console.error("❌ Weaviate connection failed:", error);
      return false;
    }
  }
}

module.exports = WeaviateService;

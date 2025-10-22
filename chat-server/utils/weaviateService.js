const weaviate = require("weaviate-ts-client").default;
const logger = require("./logger");

class WeaviateService {
  constructor() {
    this.client = weaviate.client({
      scheme: process.env.WEAVIATE_URL?.includes("https") ? "https" : "http",
      host:
        process.env.WEAVIATE_URL?.replace(/https?:\/\//, "") ||
        "localhost:8080",
      apiKey: process.env.WEAVIATE_API_KEY
        ? new weaviate.ApiKey(process.env.WEAVIATE_API_KEY)
        : undefined,
    });

    this.initialize();
  }

  async initialize() {
    try {
      const meta = await this.client.misc.metaGetter().do();
      logger.info("Weaviate connection established", {
        version: meta.version,
        host: process.env.WEAVIATE_URL,
      });
    } catch (error) {
      logger.error("Failed to connect to Weaviate", { error: error.message });
      throw new Error("Weaviate connection failed");
    }
  }

  async searchFeatures(query, limit = 5) {
    try {
      logger.debug("Searching features", { query, limit });

      // Use hybrid search (vector + keyword) for better results
      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields(
          "featureDescription userBenefit userActions featureType relatedFeatures"
        )
        .withNearText({
          concepts: [query],
          distance: 0.7, // Similarity threshold
          moveAwayFrom: {
            concepts: ["technical", "code", "implementation", "debug"],
            force: 0.2,
          },
          moveTo: {
            concepts: ["user", "help", "how to", "feature", "benefit"],
            force: 0.3,
          },
        })
        .withLimit(limit)
        .withAdditional(["distance", "id"])
        .do();

      const features = result?.data?.Get?.AppFeature || [];

      // Filter and score results
      const scoredFeatures = features
        .filter((feature) => feature._additional.distance < 0.7) // Only high-confidence matches
        .map((feature) => ({
          ...feature,
          score: 1 - feature._additional.distance, // Convert distance to score
          id: feature._additional.id,
        }))
        .sort((a, b) => b.score - a.score);

      logger.debug(`Found ${scoredFeatures.length} relevant features`);

      return scoredFeatures;
    } catch (error) {
      logger.error("Feature search failed", { error: error.message, query });
      throw new Error("Failed to search features");
    }
  }

  async getFeatureTypes() {
    try {
      const result = await this.client.graphql
        .aggregate()
        .withClassName("AppFeature")
        .withFields("featureType")
        .withGroupBy(["featureType"])
        .do();

      const groups = result?.data?.Aggregate?.AppFeature || [];

      return groups.map((group) => ({
        type: group.groupedBy?.value || "unknown",
        count: group.meta?.count || 0,
      }));
    } catch (error) {
      logger.error("Failed to get feature types", { error: error.message });
      return [];
    }
  }

  async getSuggestedQuestions(limit = 10) {
    try {
      // Get diverse sample of features to generate questions
      const result = await this.client.graphql
        .get()
        .withClassName("AppFeature")
        .withFields("featureDescription featureType userActions")
        .withLimit(limit)
        .do();

      const features = result?.data?.Get?.AppFeature || [];

      // Generate questions based on feature types
      const questionTemplates = {
        authentication: ["How do I log in?", "Can I reset my password?"],
        data_management: [
          "How do I edit my information?",
          "Can I delete my data?",
        ],
        search_filter: [
          "How do I search for something?",
          "Can I filter my results?",
        ],
        reporting: ["How do I export my data?", "Can I generate reports?"],
        user_profile: [
          "How do I update my profile?",
          "Where are my account settings?",
        ],
        dashboard: [
          "What can I see on the main page?",
          "How do I navigate the app?",
        ],
      };

      const suggestions = [];
      const usedTypes = new Set();

      for (const feature of features) {
        const type = feature.featureType;
        if (!usedTypes.has(type) && questionTemplates[type]) {
          suggestions.push(...questionTemplates[type]);
          usedTypes.add(type);
        }
      }

      return suggestions.slice(0, limit);
    } catch (error) {
      logger.error("Failed to generate suggestions", { error: error.message });
      return [];
    }
  }

  async getStats() {
    try {
      const countResult = await this.client.graphql
        .aggregate()
        .withClassName("AppFeature")
        .withFields("meta { count }")
        .do();

      const typeResult = await this.client.graphql
        .aggregate()
        .withClassName("AppFeature")
        .withFields("featureType")
        .withGroupBy(["featureType"])
        .do();

      const totalFeatures =
        countResult?.data?.Aggregate?.AppFeature?.[0]?.meta?.count || 0;
      const typeGroups = typeResult?.data?.Aggregate?.AppFeature || [];

      return {
        totalFeatures,
        featureTypes: typeGroups.map((group) => ({
          type: group.groupedBy?.value || "unknown",
          count: group.meta?.count || 0,
        })),
        lastUpdated: new Date().toISOString(),
      };
    } catch (error) {
      logger.error("Failed to get stats", { error: error.message });
      throw new Error("Failed to retrieve statistics");
    }
  }
}

module.exports = WeaviateService;

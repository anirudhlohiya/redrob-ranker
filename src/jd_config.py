"""
Structured rubric distilled from job_description.docx for the
'Senior AI Engineer — Founding Team' role at Redrob AI.

This is the "recruiter reasoning" done ahead of time and encoded as rules,
so the ranking script can run fully offline (CPU-only, no network) at
inference time. See README.md for the design rationale.
"""

JD_TEXT_FOR_SEMANTIC_MATCH = """
Senior AI Engineer Founding Team. Own the intelligence layer of a talent
platform: ranking, retrieval, and matching systems for recruiter search
and candidate search. Production experience with embeddings-based
retrieval systems: sentence-transformers, OpenAI embeddings, BGE, E5.
Production experience with vector databases or hybrid search
infrastructure: Pinecone, Weaviate, Qdrant, Milvus, OpenSearch,
Elasticsearch, FAISS. Strong Python and code quality. Hands-on experience
designing evaluation frameworks for ranking systems: NDCG, MRR, MAP,
offline-to-online correlation, A/B testing. LLM fine-tuning LoRA QLoRA
PEFT. Learning-to-rank models XGBoost neural. HR-tech recruiting tech
marketplace products. Distributed systems large-scale inference
optimization. Open-source contributions in AI/ML. Shipped an end-to-end
ranking search or recommendation system to real users at meaningful
scale. Strong opinions on hybrid vs dense retrieval, offline vs online
evaluation, when to fine-tune vs prompt an LLM.
"""

# Companies the JD explicitly disqualifies if they represent the ENTIRE career
CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
}

# Locations considered a geographic fit (Pune/Noida preferred, others welcome)
PREFERRED_LOCATIONS = {"pune", "noida"}
WELCOME_LOCATIONS = {"pune", "noida", "hyderabad", "mumbai", "delhi", "new delhi",
                      "gurgaon", "gurugram", "faridabad", "ghaziabad", "delhi ncr"}

# Core production ML/retrieval/ranking signal keywords (must-have territory)
PRODUCTION_ML_KEYWORDS = [
    "embeddings", "embedding", "sentence-transformers", "sentence transformers",
    "bge", "e5", "vector database", "vector search", "vector db",
    "pinecone", "weaviate", "qdrant", "milvus", "opensearch",
    "elasticsearch", "faiss", "hybrid search", "hybrid retrieval",
    "retrieval", "ranking system", "ranking model", "recommendation system",
    "recommendation engine", "search system", "search infrastructure",
    "bm25", "semantic search", "dense retrieval", "re-ranking", "reranking",
]

EVAL_FRAMEWORK_KEYWORDS = [
    "ndcg", "mrr", "map@", "mean average precision", "mean reciprocal rank",
    "a/b test", "ab test", "offline evaluation", "online evaluation",
    "evaluation framework", "eval framework", "offline-to-online",
]

NICE_TO_HAVE_KEYWORDS = [
    "lora", "qlora", "peft", "fine-tuning", "fine tuning",
    "learning-to-rank", "learning to rank", "xgboost",
    "hr-tech", "hrtech", "recruiting tech", "marketplace",
    "distributed systems", "large-scale inference", "open-source", "open source",
]

# Recent-hype-only red flag: LangChain/OpenAI-wrapper work with no depth
FRAMEWORK_ENTHUSIAST_KEYWORDS = [
    "langchain", "openai api", "chatgpt", "prompt engineering",
]

PRE_LLM_ML_EVIDENCE_KEYWORDS = [
    "spark", "distributed", "recommendation", "search", "ranking",
    "information retrieval", "nlp", "machine learning", "ml pipeline",
    "feature engineering", "xgboost", "scikit-learn", "tensorflow", "pytorch",
]

CV_SPEECH_ROBOTICS_KEYWORDS = [
    "computer vision", "opencv", "object detection", "image classification",
    "gans", "yolo", "cnn", "speech recognition", "tts", "robotics",
    "autonomous", "lidar", "slam",
]

NLP_IR_KEYWORDS = [
    "nlp", "natural language processing", "information retrieval", "retrieval",
    "ranking", "search", "embeddings", "llm", "transformer", "bert", "text",
]

RESEARCH_ONLY_KEYWORDS = ["research lab", "academic lab", "research scientist",
                           "research institute", "phd thesis", "postdoc", "professor"]
PRODUCTION_EVIDENCE_KEYWORDS = ["production", "deployed", "shipped", "real users",
                                 "scale", "users", "customers", "live system"]

SENIOR_TITLE_WORDS = ["senior", "staff", "principal", "lead"]
NON_CODING_TITLE_WORDS = ["architect", "director", "head of", "vp ", "manager"]
CODING_EVIDENCE_KEYWORDS = ["built", "implemented", "wrote", "shipped", "coded",
                             "developed", "designed and built", "python", "code"]

IDEAL_YOE_MIN, IDEAL_YOE_MAX = 5, 9
IDEAL_YOE_SOFT_MIN, IDEAL_YOE_SOFT_MAX = 4, 12  # outside 5-9 but still considered

MAX_NOTICE_DAYS_PREFERRED = 30

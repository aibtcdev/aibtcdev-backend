"""GraphRAG implementation combining knowledge graphs with vector retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from backend.factory import backend
from lib.logger import configure_logger

logger = configure_logger(__name__)


@dataclass
class GraphNode:
    """Represents a node in the knowledge graph."""

    id: str
    type: str  # e.g., "proposal", "dao", "agent", "concept"
    properties: Dict[str, Any]
    embedding: Optional[List[float]] = None


@dataclass
class GraphEdge:
    """Represents an edge in the knowledge graph."""

    source: str
    target: str
    relation: str
    properties: Dict[str, Any]
    weight: float = 1.0


@dataclass
class GraphRAGResult:
    """Enhanced result combining graph and vector information."""

    document: Document
    vector_score: float
    graph_score: float
    combined_score: float
    graph_context: Dict[str, Any]
    related_entities: List[GraphNode]
    relationship_paths: List[List[str]]


class KnowledgeGraphBuilder:
    """Builds and maintains a knowledge graph from documents."""

    def __init__(self, embeddings: Optional[Embeddings] = None):
        self.embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-large")
        self.graph = nx.DiGraph()
        self.node_embeddings = {}
        self.entity_types = {
            "dao",
            "proposal",
            "agent",
            "token",
            "wallet",
            "concept",
            "action",
            "vote",
            "user",
        }

    def add_document_to_graph(self, document: Document) -> List[GraphNode]:
        """Extract entities and relationships from a document and add to graph."""
        nodes_added = []

        # Extract entities from document
        entities = self._extract_entities(document)

        # Create nodes for entities
        for entity in entities:
            node = self._create_node(entity, document)
            if node:
                self.graph.add_node(
                    node.id,
                    type=node.type,
                    properties=node.properties,
                    embedding=node.embedding,
                )
                nodes_added.append(node)

        # Extract and add relationships
        relationships = self._extract_relationships(entities, document)
        for source, target, relation, properties in relationships:
            self.graph.add_edge(
                source,
                target,
                relation=relation,
                properties=properties,
                weight=properties.get("weight", 1.0),
            )

        # Connect document to its entities
        doc_id = document.metadata.get(
            "proposal_id", f"doc_{hash(document.page_content)}"
        )
        doc_node = GraphNode(
            id=doc_id,
            type="document",
            properties={
                "title": document.metadata.get("title", ""),
                "content_preview": document.page_content[:200],
                **document.metadata,
            },
        )

        self.graph.add_node(
            doc_node.id, type=doc_node.type, properties=doc_node.properties
        )

        # Connect document to extracted entities
        for entity_node in nodes_added:
            self.graph.add_edge(
                doc_node.id,
                entity_node.id,
                relation="mentions",
                properties={"source": "extraction"},
                weight=0.8,
            )

        return nodes_added

    def _extract_entities(self, document: Document) -> List[Dict[str, Any]]:
        """Extract named entities from document content."""
        entities = []
        content = document.page_content.lower()
        metadata = document.metadata

        # Extract entities from metadata
        if "dao_id" in metadata:
            entities.append(
                {
                    "text": metadata.get("dao_name", metadata["dao_id"]),
                    "type": "dao",
                    "id": metadata["dao_id"],
                    "metadata": {"source": "metadata"},
                }
            )

        if "proposal_id" in metadata:
            entities.append(
                {
                    "text": metadata.get(
                        "title", f"proposal_{metadata['proposal_id']}"
                    ),
                    "type": "proposal",
                    "id": metadata["proposal_id"],
                    "metadata": {"source": "metadata"},
                }
            )

        # Simple keyword-based entity extraction
        # In production, use NER models like spaCy or a custom model
        dao_keywords = ["dao", "organization", "governance", "community"]
        proposal_keywords = ["proposal", "vote", "decision", "action"]
        agent_keywords = ["agent", "bot", "ai", "assistant"]

        for keyword in dao_keywords:
            if keyword in content:
                entities.append(
                    {
                        "text": keyword,
                        "type": "concept",
                        "id": f"concept_{keyword}",
                        "metadata": {"source": "extraction"},
                    }
                )

        return entities

    def _create_node(
        self, entity: Dict[str, Any], document: Document
    ) -> Optional[GraphNode]:
        """Create a graph node from an extracted entity."""
        try:
            # Generate embedding for entity
            entity_text = entity["text"]
            embedding = self.embeddings.embed_query(entity_text)

            node = GraphNode(
                id=entity["id"],
                type=entity["type"],
                properties={
                    "text": entity_text,
                    "source_document": document.metadata.get("proposal_id", "unknown"),
                    **entity.get("metadata", {}),
                },
                embedding=embedding,
            )

            return node

        except Exception as e:
            logger.error(f"Failed to create node for entity {entity}: {e}")
            return None

    def _extract_relationships(
        self, entities: List[Dict[str, Any]], document: Document
    ) -> List[Tuple[str, str, str, Dict[str, Any]]]:
        """Extract relationships between entities."""
        relationships = []

        # Simple co-occurrence based relationships
        for i, entity1 in enumerate(entities):
            for entity2 in entities[i + 1 :]:
                # Create relationship if entities co-occur
                relation_type = self._determine_relation_type(entity1, entity2)
                if relation_type:
                    relationships.append(
                        (
                            entity1["id"],
                            entity2["id"],
                            relation_type,
                            {
                                "source": "co_occurrence",
                                "document": document.metadata.get(
                                    "proposal_id", "unknown"
                                ),
                                "weight": 0.5,
                            },
                        )
                    )

        return relationships

    def _determine_relation_type(
        self, entity1: Dict[str, Any], entity2: Dict[str, Any]
    ) -> Optional[str]:
        """Determine the type of relationship between two entities."""
        type1, type2 = entity1["type"], entity2["type"]

        # Define relationship rules
        if type1 == "dao" and type2 == "proposal":
            return "has_proposal"
        elif type1 == "proposal" and type2 == "dao":
            return "belongs_to"
        elif type1 == "dao" and type2 == "agent":
            return "has_agent"
        elif type1 == "proposal" and type2 == "concept":
            return "relates_to"
        elif type1 == type2:
            return "related_to"

        return "associated_with"

    def find_related_entities(
        self,
        entity_id: str,
        max_depth: int = 2,
        relation_types: Optional[List[str]] = None,
    ) -> List[GraphNode]:
        """Find entities related to a given entity."""
        if entity_id not in self.graph:
            return []

        related_nodes = []
        visited = set()

        def dfs(node_id: str, depth: int):
            if depth > max_depth or node_id in visited:
                return

            visited.add(node_id)

            # Get neighbors
            for neighbor in self.graph.neighbors(node_id):
                edge_data = self.graph[node_id][neighbor]
                relation = edge_data.get("relation", "")

                if relation_types is None or relation in relation_types:
                    node_data = self.graph.nodes[neighbor]
                    related_node = GraphNode(
                        id=neighbor,
                        type=node_data.get("type", "unknown"),
                        properties=node_data.get("properties", {}),
                        embedding=node_data.get("embedding"),
                    )
                    related_nodes.append(related_node)

                    dfs(neighbor, depth + 1)

        dfs(entity_id, 0)
        return related_nodes

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge graph."""
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "node_types": self._get_node_type_counts(),
            "relation_types": self._get_relation_type_counts(),
            "density": nx.density(self.graph),
            "connected_components": nx.number_weakly_connected_components(self.graph),
        }

    def _get_node_type_counts(self) -> Dict[str, int]:
        """Count nodes by type."""
        type_counts = {}
        for node_id, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1
        return type_counts

    def _get_relation_type_counts(self) -> Dict[str, int]:
        """Count edges by relation type."""
        relation_counts = {}
        for source, target, data in self.graph.edges(data=True):
            relation = data.get("relation", "unknown")
            relation_counts[relation] = relation_counts.get(relation, 0) + 1
        return relation_counts


class GraphRAGRetriever:
    """Retriever that combines vector search with graph traversal."""

    def __init__(
        self,
        collection_names: List[str],
        knowledge_graph: KnowledgeGraphBuilder,
        embeddings: Optional[Embeddings] = None,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
    ):
        self.collection_names = collection_names
        self.knowledge_graph = knowledge_graph
        self.embeddings = embeddings or OpenAIEmbeddings(model="text-embedding-3-large")
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight

    async def retrieve(
        self, query: str, limit: int = 10, use_graph_expansion: bool = True, **kwargs
    ) -> List[GraphRAGResult]:
        """Retrieve documents using both vector search and graph traversal."""
        logger.info(f"GraphRAG retrieval for query: '{query[:50]}...'")

        # Step 1: Vector search
        vector_results = await self._vector_search(query, limit * 2)

        # Step 2: Graph-based enhancement
        enhanced_results = []

        for doc, vector_score in vector_results:
            # Find related entities for this document
            doc_id = doc.metadata.get("proposal_id", f"doc_{hash(doc.page_content)}")
            related_entities = self.knowledge_graph.find_related_entities(doc_id)

            # Calculate graph score based on entity relationships
            graph_score = self._calculate_graph_score(query, doc, related_entities)

            # Find relationship paths
            paths = self._find_relationship_paths(query, doc_id)

            # Combine scores
            combined_score = (
                self.vector_weight * vector_score + self.graph_weight * graph_score
            )

            result = GraphRAGResult(
                document=doc,
                vector_score=vector_score,
                graph_score=graph_score,
                combined_score=combined_score,
                graph_context={
                    "related_entity_count": len(related_entities),
                    "relationship_path_count": len(paths),
                },
                related_entities=related_entities,
                relationship_paths=paths,
            )

            enhanced_results.append(result)

        # Sort by combined score
        enhanced_results.sort(key=lambda x: x.combined_score, reverse=True)

        # Graph expansion: Add related documents
        if use_graph_expansion and enhanced_results:
            expanded_results = await self._expand_with_graph(enhanced_results, query)
            enhanced_results.extend(expanded_results)

        # Remove duplicates and limit results
        unique_results = self._deduplicate_results(enhanced_results)

        logger.info(
            f"GraphRAG retrieval completed: {len(unique_results[:limit])} results"
        )

        return unique_results[:limit]

    async def _vector_search(
        self, query: str, limit: int
    ) -> List[Tuple[Document, float]]:
        """Perform vector similarity search."""
        all_results = []

        for collection_name in self.collection_names:
            try:
                results = await backend.query_vectors(
                    collection_name=collection_name,
                    query_text=query,
                    limit=limit // len(self.collection_names),
                    embeddings=self.embeddings,
                )

                for result in results:
                    doc = Document(
                        page_content=result.get("page_content", ""),
                        metadata={
                            **result.get("metadata", {}),
                            "collection_source": collection_name,
                        },
                    )
                    score = result.get("similarity", 0.5)
                    all_results.append((doc, score))

            except Exception as e:
                logger.error(
                    f"Vector search failed for collection {collection_name}: {e}"
                )
                continue

        return all_results

    def _calculate_graph_score(
        self, query: str, document: Document, related_entities: List[GraphNode]
    ) -> float:
        """Calculate relevance score based on graph structure."""
        if not related_entities:
            return 0.0

        try:
            # Get query embedding
            query_embedding = self.embeddings.embed_query(query)

            # Calculate similarity with related entities
            entity_scores = []
            for entity in related_entities:
                if entity.embedding:
                    similarity = self._cosine_similarity(
                        query_embedding, entity.embedding
                    )
                    entity_scores.append(similarity)

            if entity_scores:
                # Use max similarity as graph score
                return max(entity_scores)
            else:
                # Fallback: score based on number of relationships
                return min(len(related_entities) / 10.0, 1.0)

        except Exception as e:
            logger.error(f"Failed to calculate graph score: {e}")
            return 0.0

    def _find_relationship_paths(self, query: str, doc_id: str) -> List[List[str]]:
        """Find relationship paths that might be relevant to the query."""
        paths = []

        if doc_id not in self.knowledge_graph.graph:
            return paths

        # Find paths to entities that might be relevant to the query
        # This is a simplified implementation
        try:
            # Get all nodes within 2 hops
            for target in self.knowledge_graph.graph.nodes():
                if target != doc_id:
                    try:
                        path = nx.shortest_path(
                            self.knowledge_graph.graph, doc_id, target
                        )
                        if len(path) <= 3:  # Max 2 hops
                            paths.append(path)
                    except nx.NetworkXNoPath:
                        continue
        except Exception as e:
            logger.error(f"Failed to find relationship paths: {e}")

        return paths[:5]  # Limit to top 5 paths

    async def _expand_with_graph(
        self, initial_results: List[GraphRAGResult], query: str
    ) -> List[GraphRAGResult]:
        """Expand results using graph relationships."""
        expanded_results = []

        # Get entities from top results
        top_entities = set()
        for result in initial_results[:3]:  # Use top 3 results
            for entity in result.related_entities:
                top_entities.add(entity.id)

        # Find documents related to these entities
        for entity_id in top_entities:
            related_entities = self.knowledge_graph.find_related_entities(
                entity_id, max_depth=1
            )

            for entity in related_entities:
                if entity.type == "document":
                    # This would require additional document retrieval logic
                    # For now, we'll skip this expansion
                    pass

        return expanded_results

    def _deduplicate_results(
        self, results: List[GraphRAGResult]
    ) -> List[GraphRAGResult]:
        """Remove duplicate results based on document content."""
        seen_docs = set()
        unique_results = []

        for result in results:
            doc_id = result.document.metadata.get(
                "proposal_id", f"doc_{hash(result.document.page_content)}"
            )

            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                unique_results.append(result)

        return unique_results

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import numpy as np

        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)

        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Factory function
def create_graph_rag_system(
    collection_names: List[str],
    embeddings: Optional[Embeddings] = None,
    graph_config: Optional[Dict[str, Any]] = None,
) -> Tuple[KnowledgeGraphBuilder, GraphRAGRetriever]:
    """Factory function to create a complete GraphRAG system."""

    config = graph_config or {}

    # Create embeddings if not provided
    if embeddings is None:
        embeddings = OpenAIEmbeddings(
            model=config.get("embedding_model", "text-embedding-3-large"),
            dimensions=config.get("embedding_dimensions", 1536),
        )

    # Create knowledge graph builder
    graph_builder = KnowledgeGraphBuilder(embeddings)

    # Create GraphRAG retriever
    retriever = GraphRAGRetriever(
        collection_names=collection_names,
        knowledge_graph=graph_builder,
        embeddings=embeddings,
        vector_weight=config.get("vector_weight", 0.6),
        graph_weight=config.get("graph_weight", 0.4),
    )

    return graph_builder, retriever

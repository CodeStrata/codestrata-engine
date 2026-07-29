"""Assessment Graph domain package.

Projection/reference graph connecting Repository Graph observations to
Engineering Knowledge concepts for a single assessment. Peer to Repository
Graph and Engineering Knowledge Graph on the shared graph kernel.
"""

from codestrata.domain.assessment_graph.enums import (
    AssessmentNodeType,
    AssessmentRelationshipType,
)
from codestrata.domain.assessment_graph.factories import (
    ASSESSMENT_GRAPH_GENERATOR_VERSION,
    ASSESSMENT_GRAPH_SCHEMA_VERSION,
    AssessmentNodeFactory,
    AssessmentRelationshipFactory,
    build_assessment_graph_metadata,
)
from codestrata.domain.assessment_graph.ids import (
    AssessmentNodeIdFactory,
    AssessmentRelationshipIdFactory,
    build_assessment_graph_id,
    build_assessment_source_fingerprint,
)
from codestrata.domain.assessment_graph.models import AssessmentGraph
from codestrata.domain.assessment_graph.properties import (
    AssessmentBindingProperties,
    KnowledgeConceptReferenceProperties,
    RepositoryEntityReferenceProperties,
    properties_mapping,
)
from codestrata.domain.assessment_graph.schema import (
    AssessmentGraphSchema,
    AssessmentGraphSchemaError,
)

__all__ = [
    "ASSESSMENT_GRAPH_GENERATOR_VERSION",
    "ASSESSMENT_GRAPH_SCHEMA_VERSION",
    "AssessmentBindingProperties",
    "AssessmentGraph",
    "AssessmentGraphSchema",
    "AssessmentGraphSchemaError",
    "AssessmentNodeFactory",
    "AssessmentNodeIdFactory",
    "AssessmentNodeType",
    "AssessmentRelationshipFactory",
    "AssessmentRelationshipIdFactory",
    "AssessmentRelationshipType",
    "KnowledgeConceptReferenceProperties",
    "RepositoryEntityReferenceProperties",
    "build_assessment_graph_id",
    "build_assessment_graph_metadata",
    "build_assessment_source_fingerprint",
    "properties_mapping",
]

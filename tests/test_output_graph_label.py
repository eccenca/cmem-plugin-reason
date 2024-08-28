"""Tests for creating the output graph label"""

from cmem_plugin_reason.plugin_reason import ReasonPlugin
from tests.utils import needs_cmem


@needs_cmem
def test_output_graph_label() -> None:
    """Test creating the output graph label"""
    plugin = ReasonPlugin(
        data_graph_iri="https://vocab.eccenca.com/shacl/",
        ontology_graph_iri="http://xmlns.com/foaf/0.1/",
        output_graph_iri="https://vocab.eccenca.com/shacl/output/",
        reasoner="hermit",
        sub_class=False,
        class_assertion=True,
        property_assertion=True,
        validate_profile=True,
        import_ontology=True,
    )
    assert plugin.get_output_graph_label() == "CMEM Shapes Catalog - Reasoning Results"


@needs_cmem
def test_output_graph_label_fail() -> None:
    """Test creating the output graph label - fails"""
    plugin = ReasonPlugin(
        data_graph_iri="https://example.org/ttt/",
        ontology_graph_iri="http://xmlns.com/foaf/0.1/",
        output_graph_iri="https://vocab.eccenca.com/shacl/output/",
        reasoner="hermit",
        sub_class=False,
        class_assertion=True,
        property_assertion=True,
        validate_profile=True,
        import_ontology=True,
    )
    assert plugin.get_output_graph_label() == "Reasoning Results"

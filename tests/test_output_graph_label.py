"""Tests for creating the output graph label"""

from cmem_plugin_reason.plugin_reason import ReasonPlugin
from cmem_plugin_reason.plugin_validate import ValidatePlugin
from cmem_plugin_reason.utils import get_output_graph_label
from tests.utils import needs_cmem


@needs_cmem
def test_reason_output_graph_label() -> None:
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
    assert (
        get_output_graph_label(plugin.data_graph_iri, "Reasoning Results")
        == "CMEM Shapes Catalog - Reasoning Results"
    )


@needs_cmem
def test_reason_output_graph_label_fail() -> None:
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
    assert get_output_graph_label(plugin.data_graph_iri, "Reasoning Results") == "Reasoning Results"


@needs_cmem
def test_validate_output_graph_label() -> None:
    """Test creating the output graph label"""
    plugin = ValidatePlugin(
        ontology_graph_iri="https://vocab.eccenca.com/shacl/",
        output_graph_iri="https://vocab.eccenca.com/shacl/output/",
        reasoner="hermit",
    )
    assert (
        get_output_graph_label(plugin.ontology_graph_iri, "Validation Result")
        == "CMEM Shapes Catalog - Validation Result"
    )


@needs_cmem
def test_validate_output_graph_label_fail() -> None:
    """Test creating the output graph label"""
    plugin = ValidatePlugin(
        ontology_graph_iri="https://example.org/ttt/",
        output_graph_iri="https://vocab.eccenca.com/shacl/output/",
        reasoner="hermit",
    )
    assert (
        get_output_graph_label(plugin.ontology_graph_iri, "Validation Result")
        == "Validation Result"
    )

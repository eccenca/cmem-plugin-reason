"""Tests for creating the output graph label"""

from cmem_plugin_reason.plugin_reason import ReasonPlugin, get_output_graph_label


def test_reason_output_graph_label() -> None:
    """Test creating the output graph label"""
    plugin = ReasonPlugin(
        data_graph_iri="https://vocab.eccenca.com/shacl/",
        ontology_graph_iri="http://xmlns.com/foaf/0.1/",
        output_graph_iri="https://vocab.eccenca.com/shacl/output/",
        reasoner="hermit",
        sub_class=False,
        class_assertion=True,
    )
    assert (
        get_output_graph_label(plugin, plugin.data_graph_iri, "Reasoning Results")
        == "CMEM Shapes Catalog - Reasoning Results"
    )


def test_reason_output_graph_label_fail() -> None:
    """Test creating the output graph label - fails"""
    plugin = ReasonPlugin(
        data_graph_iri="https://example.org/ttt/",
        ontology_graph_iri="http://xmlns.com/foaf/0.1/",
        output_graph_iri="https://vocab.eccenca.com/shacl/output/",
        reasoner="hermit",
        sub_class=False,
        class_assertion=True,
    )
    assert (
        get_output_graph_label(plugin, plugin.data_graph_iri, "Reasoning Results")
        == "Reasoning Results"
    )

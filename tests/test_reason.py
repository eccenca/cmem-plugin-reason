"""Plugin tests."""

from pathlib import Path

import pytest
from cmem.cmempy.dp.proxy.graph import delete
from rdflib import Graph
from rdflib.compare import to_isomorphic

from cmem_plugin_reason.plugin_reason import ReasonPlugin
from cmem_plugin_reason.utils import REASONERS
from tests.utils import TestExecutionContext, needs_cmem
from tests.utils2 import get_remote_graph, import_graph

from . import __path__

UID = "e02aaed014c94e0c91bf960fed127750"
REASON_DATA_GRAPH_IRI = f"https://ns.eccenca.com/reasoning/{UID}/data/"
REASON_ONTOLOGY_GRAPH_IRI_1 = f"https://ns.eccenca.com/reasoning/{UID}/vocab/"
REASON_ONTOLOGY_GRAPH_IRI_2 = f"https://ns.eccenca.com/reasoning/{UID}/vocab2/"
REASON_ONTOLOGY_GRAPH_IRI_3 = f"https://ns.eccenca.com/reasoning/{UID}/vocab3/"
REASON_RESULT_GRAPH_IRI = f"https://ns.eccenca.com/reasoning/{UID}/result/"


@pytest.fixture()
def _setup(request: pytest.FixtureRequest) -> None:
    """Set up Reason test"""
    import_graph(REASON_DATA_GRAPH_IRI, "dataset_owl.ttl")
    import_graph(REASON_ONTOLOGY_GRAPH_IRI_1, "test_reason_ontology_1.ttl")
    import_graph(REASON_ONTOLOGY_GRAPH_IRI_2, "test_reason_ontology_2.ttl")
    import_graph(REASON_ONTOLOGY_GRAPH_IRI_3, "test_reason_ontology_3.ttl")

    request.addfinalizer(lambda: delete(REASON_DATA_GRAPH_IRI))
    request.addfinalizer(lambda: delete(REASON_ONTOLOGY_GRAPH_IRI_1))
    request.addfinalizer(lambda: delete(REASON_ONTOLOGY_GRAPH_IRI_2))
    request.addfinalizer(lambda: delete(REASON_ONTOLOGY_GRAPH_IRI_3))
    request.addfinalizer(lambda: delete(REASON_RESULT_GRAPH_IRI))  # noqa: PT021


@needs_cmem
def tests_reason(_setup: None) -> None:
    """Tests for Reason plugin"""

    def test_reasoner(reasoner: str, err_list: list) -> list:
        ReasonPlugin(
            data_graph_iri=REASON_DATA_GRAPH_IRI,
            ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
            output_graph_iri=REASON_RESULT_GRAPH_IRI,
            reasoner=reasoner,
            sub_class=False,
            class_assertion=True,
            property_assertion=True,
            validate_profile=True,
            import_ontology=True,
        ).execute(None, context=TestExecutionContext())

        result = get_remote_graph(REASON_RESULT_GRAPH_IRI)
        test = Graph().parse(Path(__path__[0]) / f"test_{reasoner}.ttl", format="turtle")
        if to_isomorphic(result) != to_isomorphic(test):
            err_list.append(reasoner)
        return err_list

    errors_list: list[str] = []
    for reasoner in REASONERS:
        errors_list = test_reasoner(reasoner, errors_list)

    if errors_list:
        errors = ""
        errors += f"Reason: test failed for reasoners {', '.join(errors_list)}. "
        raise AssertionError(errors[:-1])

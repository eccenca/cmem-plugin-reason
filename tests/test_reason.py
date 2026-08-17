"""Plugin tests."""

from collections.abc import Generator
from typing import Any

import pytest
from cmem_plugin_base.testing import TestExecutionContext
from rdflib import Graph
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_reason import ReasonPlugin
from cmem_plugin_reason.utils import REASONERS
from tests.utils import (
    FIXTURE_DIR,
    UID,
    get_remote_graph,
    get_test_client,
    import_graph,
    replace_uuid,
)

REASON_DATA_GRAPH_IRI = f"https://ns.eccenca.com/reasoning/{UID}/data/"
REASON_DATA_GRAPH_IRI_2 = f"https://ns.eccenca.com/reasoning/{UID}/data2/"
REASON_ONTOLOGY_GRAPH_IRI_1 = f"https://ns.eccenca.com/reasoning/{UID}/vocab/"
REASON_ONTOLOGY_GRAPH_IRI_2 = f"https://ns.eccenca.com/reasoning/{UID}/vocab2/"
REASON_ONTOLOGY_GRAPH_IRI_3 = f"https://ns.eccenca.com/reasoning/{UID}/vocab3/"
ONTOLOGY_GRAPH_IMPORT_FAIL_IRI = f"https://ns.eccenca.com/reasoning/{UID}/vocab4/"
REASON_RESULT_GRAPH_IRI = f"https://ns.eccenca.com/reasoning/{UID}/result/"
ASK_QUERY = f"""PREFIX owl: <http://www.w3.org/2002/07/owl#>
ASK {{
  GRAPH <{REASON_RESULT_GRAPH_IRI}> {{
    <{REASON_RESULT_GRAPH_IRI}> owl:imports <{REASON_ONTOLOGY_GRAPH_IRI_1}>
  }}
}}"""


@pytest.fixture
def reasoner_parameter() -> str | None:
    """Reasoner parameter fixture"""
    return None


@pytest.fixture
def setup() -> Generator[None, Any]:
    """Set up Reason test"""
    client = get_test_client()
    client.graphs.delete_item(REASON_RESULT_GRAPH_IRI, skip_if_missing=True)

    import_graph(client, REASON_DATA_GRAPH_IRI, f"{FIXTURE_DIR}/test_reason_data.ttl")
    import_graph(client, REASON_DATA_GRAPH_IRI_2, f"{FIXTURE_DIR}/test_reason_data_2.ttl")
    import_graph(client, REASON_ONTOLOGY_GRAPH_IRI_1, f"{FIXTURE_DIR}/test_reason_ontology_1.ttl")
    import_graph(client, REASON_ONTOLOGY_GRAPH_IRI_2, f"{FIXTURE_DIR}/test_reason_ontology_2.ttl")
    import_graph(client, REASON_ONTOLOGY_GRAPH_IRI_3, f"{FIXTURE_DIR}/test_reason_ontology_3.ttl")
    import_graph(
        client, ONTOLOGY_GRAPH_IMPORT_FAIL_IRI, f"{FIXTURE_DIR}/test_reason_ontology_4.ttl"
    )

    yield

    client = get_test_client()
    for iri in (
        REASON_DATA_GRAPH_IRI,
        REASON_DATA_GRAPH_IRI_2,
        REASON_ONTOLOGY_GRAPH_IRI_1,
        REASON_ONTOLOGY_GRAPH_IRI_2,
        REASON_ONTOLOGY_GRAPH_IRI_3,
        ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        REASON_RESULT_GRAPH_IRI,
    ):
        client.graphs.delete_item(iri, skip_if_missing=True)


@pytest.mark.parametrize("reasoner_parameter", REASONERS)
def test_reason(setup: None, reasoner_parameter: str) -> None:  # noqa: ARG001
    """Test reasoning"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner=reasoner_parameter,
        sub_class=False,
        class_assertion=True,
        property_assertion=True,
        validate_profile=True,
        imports="import_ontology",
    ).execute(inputs=(), context=TestExecutionContext())

    result = get_remote_graph(get_test_client(), REASON_RESULT_GRAPH_IRI)
    test = Graph().parse(
        data=replace_uuid(f"{FIXTURE_DIR}/test_{reasoner_parameter}.ttl"), format="turtle"
    )
    assert isomorphic(result, test)


def test_reason_input_not_exist(setup: None) -> None:  # noqa: ARG001
    """Test Reason with non-existing input graph"""
    plugin = ReasonPlugin(
        data_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist1/",
        ontology_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist2/",
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="elk",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        validate_profile=False,
        imports="import_ontology",
    )
    with pytest.raises(
        ValueError,
        match="Graphs do not exist: "
        f"https://ns.eccenca.com/reasoning/{UID}/not-exist1/, "
        f"https://ns.eccenca.com/reasoning/{UID}/not-exist2/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_reason_import_not_exist_not_ignore(setup: None) -> None:  # noqa: ARG001
    """Test Reason with missing import"""
    plugin = ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="elk",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        validate_profile=False,
        imports="import_ontology",
        ignore_missing_imports=False,
    )
    with pytest.raises(
        ImportError,
        match=f"Missing graph imports: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_reason_import_not_exist_ignore(setup: None) -> None:  # noqa: ARG001
    """Test Reason ignoring missing import"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="elk",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        validate_profile=False,
        imports="import_ontology",
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())


def test_reason_ontology_import(setup: None) -> None:  # noqa: ARG001
    """Test Reason remove ontology import"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="elk",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        validate_profile=False,
        imports="none",
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())

    assert not get_test_client().store.sparql.query(ASK_QUERY).askAnswer


def test_reason_ontology_import_2(setup: None) -> None:  # noqa: ARG001
    """Test Reason, do not remove ontology import if it exists in data graph"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI_2,
        ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="elk",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        validate_profile=False,
        imports="none",
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())

    assert get_test_client().store.sparql.query(ASK_QUERY).askAnswer

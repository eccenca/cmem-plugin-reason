"""Plugin tests."""

import json
from collections.abc import Generator
from typing import Any

import pytest
from cmem.cmempy.dp.proxy.graph import delete
from cmem.cmempy.dp.proxy.sparql import get
from rdflib import Graph
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_reason import ReasonPlugin
from cmem_plugin_reason.utils import REASONERS
from tests import FIXTURE_DIR
from tests.utils import TestExecutionContext
from tests.utils2 import UID, get_bytes_io, get_remote_graph, import_graph, replace_uuid

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
def setup() -> Generator[None, Any, None]:
    """Set up Reason test"""
    import_graph(REASON_DATA_GRAPH_IRI, get_bytes_io(f"{FIXTURE_DIR}/test_reason_data.ttl"))
    import_graph(REASON_DATA_GRAPH_IRI_2, get_bytes_io(f"{FIXTURE_DIR}/test_reason_data_2.ttl"))
    import_graph(
        REASON_ONTOLOGY_GRAPH_IRI_1, get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_1.ttl")
    )
    import_graph(
        REASON_ONTOLOGY_GRAPH_IRI_2, get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_2.ttl")
    )
    import_graph(
        REASON_ONTOLOGY_GRAPH_IRI_3, get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_3.ttl")
    )
    import_graph(
        ONTOLOGY_GRAPH_IMPORT_FAIL_IRI, get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_4.ttl")
    )

    yield

    delete(REASON_DATA_GRAPH_IRI)
    delete(REASON_DATA_GRAPH_IRI_2)
    delete(REASON_ONTOLOGY_GRAPH_IRI_1)
    delete(REASON_ONTOLOGY_GRAPH_IRI_2)
    delete(REASON_ONTOLOGY_GRAPH_IRI_3)
    delete(ONTOLOGY_GRAPH_IMPORT_FAIL_IRI)
    delete(REASON_RESULT_GRAPH_IRI)


@pytest.mark.parametrize("reasoner_parameter", list(REASONERS.keys()))
def test_reasoner(setup: None, reasoner_parameter: str) -> None:  # noqa: ARG001
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

    result = get_remote_graph(REASON_RESULT_GRAPH_IRI)
    result.serialize("result.ttl", format="turtle")
    test = Graph().parse(
        data=replace_uuid(f"{FIXTURE_DIR}/test_{reasoner_parameter}.ttl"), format="turtle"
    )
    test.serialize("test.ttl", format="turtle")
    assert isomorphic(result, test)


def test_reason_input_not_exist(setup: None) -> None:  # noqa: ARG001
    """Test Reason with non-existing input graph"""
    plugin = ReasonPlugin(
        data_graph_iri="http://not-exist1.org",
        ontology_graph_iri="http://not-exist2.org",
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="elk",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        validate_profile=False,
        imports="import_ontology",
    )
    with pytest.raises(
        ValueError, match="Graphs do not exist: http://not-exist1.org, http://not-exist2.org"
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_reasoner_import_not_exist_not_ignore(setup: None) -> None:  # noqa: ARG001
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


def test_reasoner_import_not_exist_ignore(setup: None) -> None:  # noqa: ARG001
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


def test_reasoner_ontology_import(setup: None) -> None:
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

    assert not json.loads(get(query=ASK_QUERY)).get("boolean")


def test_reasoner_ontology_import_2(setup: None) -> None:
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

    assert json.loads(get(query=ASK_QUERY)).get("boolean")

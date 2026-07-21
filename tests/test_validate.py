"""Plugin tests."""

from collections.abc import Generator
from typing import Any

import pytest
from cmem_client.client import Client
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.testing import TestExecutionContext
from rdflib import Graph
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_validate import VALIDATE_REASONERS, ValidatePlugin
from tests.utils import (
    FIXTURE_DIR,
    UID,
    get_bytes_io,
    get_client,
    get_remote_graph,
    import_graph,
    replace_uuid,
)

VALIDATE_ONTOLOGY_GRAPH_IRI_1 = f"https://ns.eccenca.com/validateontology/{UID}/vocab/"
VALIDATE_ONTOLOGY_GRAPH_IRI_2 = f"https://ns.eccenca.com/validateontology/{UID}/vocab2/"
VALIDATE_ONTOLOGY_GRAPH_IRI_3 = f"https://ns.eccenca.com/validateontology/{UID}/vocab3/"
ONTOLOGY_GRAPH_IMPORT_FAIL_IRI = f"https://ns.eccenca.com/reasoning/{UID}/vocab4/"
VALIDATE_OUTPUT_GRAPH_IRI = f"https://ns.eccenca.com/validateontology/{UID}/output/"


def get_value_dict(entities: Entities) -> dict:
    """Make result path to value map (single values unwrapped, multi-values kept as lists)"""
    value_dict = {}
    paths = [p.path for p in entities.schema.paths]
    for p in paths:
        values = next(iter(entities.entities)).values[paths.index(p)]  # type: ignore[union-attr]
        value_dict[p] = values[0] if len(values) == 1 else values
    return value_dict


@pytest.fixture
def reasoner_parameter() -> str | None:
    """Reasoner parameter fixture"""
    return None


@pytest.fixture
def client() -> Client:
    """CMEM client fixture"""
    return get_client()


@pytest.fixture
def setup(client: Client) -> Generator[None, Any]:
    """Set up Validate test"""
    import_graph(
        client,
        VALIDATE_ONTOLOGY_GRAPH_IRI_1,
        get_bytes_io(f"{FIXTURE_DIR}/test_validate_ontology_1.ttl"),
    )
    import_graph(
        client,
        VALIDATE_ONTOLOGY_GRAPH_IRI_2,
        get_bytes_io(f"{FIXTURE_DIR}/test_validate_ontology_2.ttl"),
    )
    import_graph(
        client,
        VALIDATE_ONTOLOGY_GRAPH_IRI_3,
        get_bytes_io(f"{FIXTURE_DIR}/test_validate_ontology_3.ttl"),
    )
    import_graph(
        client,
        ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_4.ttl"),
    )

    yield

    client.graphs.delete_item(VALIDATE_ONTOLOGY_GRAPH_IRI_1, skip_if_missing=True)
    client.graphs.delete_item(VALIDATE_ONTOLOGY_GRAPH_IRI_2, skip_if_missing=True)
    client.graphs.delete_item(VALIDATE_ONTOLOGY_GRAPH_IRI_3, skip_if_missing=True)
    client.graphs.delete_item(ONTOLOGY_GRAPH_IMPORT_FAIL_IRI, skip_if_missing=True)
    client.graphs.delete_item(VALIDATE_OUTPUT_GRAPH_IRI, skip_if_missing=True)


@pytest.mark.parametrize("reasoner_parameter", VALIDATE_REASONERS)
def test_validate(setup: None, reasoner_parameter: str) -> None:  # noqa: ARG001
    """Test Validate"""
    result = ValidatePlugin(
        ontology_graph_iri=VALIDATE_ONTOLOGY_GRAPH_IRI_1,
        reasoner=reasoner_parameter,
        validate_profile=True,
        mode="inconsistency",
    ).execute(inputs=(), context=TestExecutionContext())

    md_test = replace_uuid(f"{FIXTURE_DIR}/test_validate_{reasoner_parameter}.md")
    value_dict = get_value_dict(result)
    val_errors = ""

    if value_dict["explanation"] != md_test:
        val_errors += 'EntityPath "explanation" output error. '
    if value_dict["ontology_graph_iri"] != VALIDATE_ONTOLOGY_GRAPH_IRI_1:
        val_errors += 'EntityPath "ontology_graph_iri" output error. '
    if value_dict["reasoner"] != reasoner_parameter:
        val_errors += 'EntityPath "reasoner" output error. '
    if value_dict["profiles"] != ["Full", "DL", "EL", "QL", "RL"]:
        val_errors += 'EntityPath "profiles" output error. '

    if val_errors:
        raise OSError(val_errors[:-1])


def test_validate_output_graph(setup: None, client: Client) -> None:  # noqa: ARG001
    """Test Validate"""
    ValidatePlugin(
        ontology_graph_iri=VALIDATE_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=VALIDATE_OUTPUT_GRAPH_IRI,
        reasoner="hermit",
        validate_profile=True,
        mode="inconsistency",
    ).execute(inputs=(), context=TestExecutionContext())

    result = get_remote_graph(client, VALIDATE_OUTPUT_GRAPH_IRI)
    test = Graph().parse(
        data=replace_uuid(f"{FIXTURE_DIR}/test_validate_output_hermit.ttl"),
    )
    assert isomorphic(result, test)


def test_validate_input_not_exist(setup: None) -> None:  # noqa: ARG001
    """Test Validate with non-existing input graph"""
    plugin = ValidatePlugin(
        ontology_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist/",
        reasoner="hermit",
        validate_profile=False,
        mode="inconsistency",
    )
    with pytest.raises(
        ValueError,
        match=f"Ontology graph does not exist: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_validate_import_not_exist_not_ignore(setup: None) -> None:  # noqa: ARG001
    """Test Validate with missing import"""
    plugin = ValidatePlugin(
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        reasoner="hermit",
        validate_profile=False,
        mode="inconsistency",
        ignore_missing_imports=False,
    )
    with pytest.raises(
        ImportError,
        match=f"Missing graph imports: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_validate_import_not_exist_ignore(setup: None) -> None:  # noqa: ARG001
    """Test Validate ignoring missing import"""
    ValidatePlugin(
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        reasoner="hermit",
        validate_profile=False,
        mode="inconsistency",
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())

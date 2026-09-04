"""Plugin tests."""

from collections.abc import Generator
from typing import Any

import pytest
from cmem_client.models.project import Project
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.testing import TestExecutionContext
from rdflib import Graph
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_validate import ValidatePlugin
from cmem_plugin_reason.utils import REASONERS
from tests.utils import (
    FIXTURE_DIR,
    UID,
    get_remote_graph,
    get_test_client,
    import_graph,
    replace_uuid,
)

VALIDATE_ONTOLOGY_GRAPH_IRI_1 = f"https://ns.eccenca.com/validateontology/{UID}/vocab/"
VALIDATE_ONTOLOGY_GRAPH_IRI_2 = f"https://ns.eccenca.com/validateontology/{UID}/vocab2/"
VALIDATE_ONTOLOGY_GRAPH_IRI_3 = f"https://ns.eccenca.com/validateontology/{UID}/vocab3/"
ONTOLOGY_GRAPH_IMPORT_FAIL_IRI = f"https://ns.eccenca.com/reasoning/{UID}/vocab4/"
VALIDATE_RESULT_GRAPH_IRI = f"https://ns.eccenca.com/validateontology/{UID}/output/"
MD_FILENAME = f"{UID}.md"
PROJECT_ID = f"validate_plugin_test_project_{UID}"


def get_value_dict(entities: Entities) -> dict:
    """Make result path to value map"""
    value_dict = {}
    paths = [p.path for p in entities.schema.paths]
    for p in paths:
        value_dict[p] = next(iter(entities.entities)).values[paths.index(p)][0]  # type: ignore[union-attr]
    return value_dict


@pytest.fixture
def reasoner_parameter() -> str | None:
    """Reasoner parameter fixture"""
    return None


@pytest.fixture
def setup() -> Generator[None, Any]:
    """Set up Validate test"""
    client = get_test_client()
    client.projects.delete_item(PROJECT_ID, skip_if_missing=True)
    client.graphs.delete_item(VALIDATE_RESULT_GRAPH_IRI, skip_if_missing=True)

    client.projects.create_item(Project(name=PROJECT_ID))
    import_graph(
        client, VALIDATE_ONTOLOGY_GRAPH_IRI_1, f"{FIXTURE_DIR}/test_validate_ontology_1.ttl"
    )
    import_graph(
        client, VALIDATE_ONTOLOGY_GRAPH_IRI_2, f"{FIXTURE_DIR}/test_validate_ontology_2.ttl"
    )
    import_graph(
        client, VALIDATE_ONTOLOGY_GRAPH_IRI_3, f"{FIXTURE_DIR}/test_validate_ontology_3.ttl"
    )
    import_graph(
        client, ONTOLOGY_GRAPH_IMPORT_FAIL_IRI, f"{FIXTURE_DIR}/test_reason_ontology_4.ttl"
    )

    yield

    client = get_test_client()
    for iri in (
        VALIDATE_ONTOLOGY_GRAPH_IRI_1,
        VALIDATE_ONTOLOGY_GRAPH_IRI_2,
        VALIDATE_ONTOLOGY_GRAPH_IRI_3,
        ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        VALIDATE_RESULT_GRAPH_IRI,
    ):
        client.graphs.delete_item(iri, skip_if_missing=True)
    client.projects.delete_item(PROJECT_ID, skip_if_missing=True)


@pytest.mark.parametrize("reasoner_parameter", REASONERS)
def test_validate(setup: None, reasoner_parameter: str) -> None:
    """Test Validate"""
    result = ValidatePlugin(
        ontology_graph_iri=VALIDATE_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=VALIDATE_RESULT_GRAPH_IRI,
        reasoner=reasoner_parameter,
        validate_profile=True,
        md_filename=MD_FILENAME,
        output_entities=True,
        mode="inconsistency",
    ).execute(inputs=(), context=TestExecutionContext(PROJECT_ID))

    client = get_test_client()
    md_test = replace_uuid(f"{FIXTURE_DIR}/test_validate_{reasoner_parameter}.md")
    value_dict = get_value_dict(result)
    output_graph = get_remote_graph(client, VALIDATE_RESULT_GRAPH_IRI)
    test = Graph().parse(
        data=replace_uuid(f"{FIXTURE_DIR}/test_validate_output_{reasoner_parameter}.ttl"),
        format="turtle",
    )
    val_errors = ""

    if value_dict["markdown"] != md_test:
        val_errors += 'EntityPath "markdown" output error. '
    if value_dict["ontology_graph_iri"] != VALIDATE_ONTOLOGY_GRAPH_IRI_1:
        val_errors += 'EntityPath "ontology_graph_iri" output error. '
    if value_dict["reasoner"] != reasoner_parameter:
        val_errors += 'EntityPath "reasoner" output error. '
    if value_dict["valid_profiles"] != "Full,DL,EL,QL,RL":
        val_errors += 'EntityPath "valid_profiles" output error. '
    if md_test != client.files.read(f"{PROJECT_ID}:{MD_FILENAME}").decode():
        val_errors += "Markdown file error. "
    if not isomorphic(output_graph, test):
        val_errors += "Output graph error. "

    if val_errors:
        raise OSError(val_errors[:-1])


def test_validate_input_not_exist(setup: None) -> None:
    """Test Validate with non-existing input graph"""
    plugin = ValidatePlugin(
        ontology_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist/",
        output_graph_iri=VALIDATE_RESULT_GRAPH_IRI,
        reasoner="elk",
        validate_profile=False,
        md_filename=MD_FILENAME,
        output_entities=True,
        mode="inconsistency",
    )
    with pytest.raises(
        ValueError,
        match=f"Ontology graph does not exist: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext(PROJECT_ID))


def test_validate_import_not_exist_not_ignore(setup: None) -> None:
    """Test Validate with missing import"""
    plugin = ValidatePlugin(
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        output_graph_iri=VALIDATE_RESULT_GRAPH_IRI,
        reasoner="elk",
        validate_profile=False,
        md_filename=MD_FILENAME,
        output_entities=True,
        mode="inconsistency",
        ignore_missing_imports=False,
    )
    with pytest.raises(
        ImportError,
        match=f"Missing graph imports: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext(PROJECT_ID))


def test_validate_import_not_exist_ignore(setup: None) -> None:
    """Test Validate ignoring missing import"""
    ValidatePlugin(
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        output_graph_iri=VALIDATE_RESULT_GRAPH_IRI,
        reasoner="elk",
        validate_profile=False,
        md_filename=MD_FILENAME,
        output_entities=True,
        mode="inconsistency",
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext(PROJECT_ID))

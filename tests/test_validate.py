"""Plugin tests."""

from collections.abc import Generator
from contextlib import suppress
from typing import Any

import pytest
from cmem.cmempy.dp.proxy.graph import delete
from cmem.cmempy.workspace.projects.project import delete_project, make_new_project
from cmem.cmempy.workspace.projects.resources.resource import get_resource
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.testing import TestExecutionContext
from rdflib import Graph
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_validate import ValidatePlugin
from cmem_plugin_reason.utils import REASONERS
from tests.utils import FIXTURE_DIR, UID, get_bytes_io, get_remote_graph, import_graph, replace_uuid

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
def setup() -> Generator[None, Any, None]:
    """Set up Validate test"""
    with suppress(Exception):
        delete_project(PROJECT_ID)
    delete(VALIDATE_RESULT_GRAPH_IRI)

    make_new_project(PROJECT_ID)
    import_graph(
        VALIDATE_ONTOLOGY_GRAPH_IRI_1, get_bytes_io(f"{FIXTURE_DIR}/test_validate_ontology_1.ttl")
    )
    import_graph(
        VALIDATE_ONTOLOGY_GRAPH_IRI_2, get_bytes_io(f"{FIXTURE_DIR}/test_validate_ontology_2.ttl")
    )
    import_graph(
        VALIDATE_ONTOLOGY_GRAPH_IRI_3, get_bytes_io(f"{FIXTURE_DIR}/test_validate_ontology_3.ttl")
    )
    import_graph(
        ONTOLOGY_GRAPH_IMPORT_FAIL_IRI, get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_4.ttl")
    )

    yield

    delete(VALIDATE_ONTOLOGY_GRAPH_IRI_1)
    delete(VALIDATE_ONTOLOGY_GRAPH_IRI_2)
    delete(VALIDATE_ONTOLOGY_GRAPH_IRI_3)
    delete(ONTOLOGY_GRAPH_IMPORT_FAIL_IRI)
    delete(VALIDATE_RESULT_GRAPH_IRI)
    delete_project(PROJECT_ID)


@pytest.mark.parametrize("reasoner_parameter", list(REASONERS.keys()))
def test_validate(setup: None, reasoner_parameter: str) -> None:  # noqa: ARG001
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

    md_test = replace_uuid(f"{FIXTURE_DIR}/test_validate_{reasoner_parameter}.md")
    value_dict = get_value_dict(result)
    output_graph = get_remote_graph(VALIDATE_RESULT_GRAPH_IRI)
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
    if md_test != get_resource(PROJECT_ID, MD_FILENAME).decode():
        val_errors += "Markdown file error. "
    if not isomorphic(output_graph, test):
        val_errors += "Output graph error. "

    if val_errors:
        raise OSError(val_errors[:-1])


def test_validate_input_not_exist(setup: None) -> None:  # noqa: ARG001
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


def test_validate_import_not_exist_not_ignore(setup: None) -> None:  # noqa: ARG001
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


def test_validate_import_not_exist_ignore(setup: None) -> None:  # noqa: ARG001
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

"""Plugin tests."""

from contextlib import suppress
from pathlib import Path

import pytest
from cmem.cmempy.dp.proxy.graph import delete
from cmem.cmempy.workspace.projects.project import delete_project, make_new_project
from cmem.cmempy.workspace.projects.resources.resource import get_resource
from cmem_plugin_base.dataintegration.entity import Entities
from rdflib import Graph
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_validate import ValidatePlugin
from cmem_plugin_reason.utils import REASONERS
from tests.utils import TestExecutionContext, needs_cmem
from tests.utils2 import get_remote_graph, import_graph

from . import __path__

UID = "e02aaed014c94e0c91bf960fed127750"
VALIDATE_ONTOLOGY_GRAPH_IRI_1 = f"https://ns.eccenca.com/validateontology/{UID}/vocab/"
VALIDATE_ONTOLOGY_GRAPH_IRI_2 = f"https://ns.eccenca.com/validateontology/{UID}/vocab2/"
VALIDATE_ONTOLOGY_GRAPH_IRI_3 = f"https://ns.eccenca.com/validateontology/{UID}/vocab3/"
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
def _setup(request: pytest.FixtureRequest) -> None:
    """Set up Validate test"""
    with suppress(Exception):
        delete_project(PROJECT_ID)
    make_new_project(PROJECT_ID)

    import_graph(VALIDATE_ONTOLOGY_GRAPH_IRI_1, "test_validate_ontology_1.ttl")
    import_graph(VALIDATE_ONTOLOGY_GRAPH_IRI_2, "test_validate_ontology_2.ttl")
    import_graph(VALIDATE_ONTOLOGY_GRAPH_IRI_3, "test_validate_ontology_3.ttl")

    request.addfinalizer(lambda: delete_project(PROJECT_ID))
    request.addfinalizer(lambda: delete(VALIDATE_RESULT_GRAPH_IRI))
    request.addfinalizer(lambda: delete(VALIDATE_ONTOLOGY_GRAPH_IRI_1))
    request.addfinalizer(lambda: delete(VALIDATE_ONTOLOGY_GRAPH_IRI_2))
    request.addfinalizer(lambda: delete(VALIDATE_ONTOLOGY_GRAPH_IRI_3))  # noqa: PT021


@needs_cmem
def tests_validate(_setup: None) -> None:  # noqa: C901
    """Tests for Validate plugin"""

    def test_validate(reasoner: str, err_list: list) -> list:
        result = ValidatePlugin(
            ontology_graph_iri=VALIDATE_ONTOLOGY_GRAPH_IRI_1,
            output_graph_iri=VALIDATE_RESULT_GRAPH_IRI,
            reasoner=reasoner,
            validate_profile=True,
            md_filename=MD_FILENAME,
            output_entities=True,
            mode="inconsistency",
        ).execute(None, context=TestExecutionContext(PROJECT_ID))

        md_test = (Path(__path__[0]) / f"test_validate_{reasoner}.md").read_text()
        value_dict = get_value_dict(result)
        output_graph = get_remote_graph(VALIDATE_RESULT_GRAPH_IRI)
        test = Graph().parse(
            Path(__path__[0]) / f"test_validate_output_{reasoner}.ttl", format="turtle"
        )
        val_errors = ""

        if value_dict["markdown"] != md_test:
            val_errors += 'EntityPath "markdown" output error. '
        if value_dict["ontology_graph_iri"] != VALIDATE_ONTOLOGY_GRAPH_IRI_1:
            val_errors += 'EntityPath "ontology_graph_iri" output error. '
        if value_dict["reasoner"] != reasoner:
            val_errors += 'EntityPath "reasoner" output error. '
        if value_dict["valid_profiles"] != "Full,DL,EL,QL,RL":
            val_errors += 'EntityPath "valid_profiles" output error. '
        if md_test != get_resource(PROJECT_ID, MD_FILENAME).decode():
            val_errors += "Markdown file error. "
        if not isomorphic(output_graph, test):
            val_errors += "Output graph error. "

        if val_errors:
            err_list.append(f"{reasoner}: {val_errors[:-1]}")
        return err_list

    errors_list: list[str] = []
    for reasoner in REASONERS:
        errors_list = test_validate(reasoner, errors_list)

    if errors_list:
        errors = ""
        errors += f"Test failed for reasoners {', '.join(errors_list)}."
        raise AssertionError(errors[:-1])

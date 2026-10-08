"""Plugin tests."""

from collections.abc import Generator
from importlib.metadata import version
from typing import Any

import pytest
from cmem_client.client import Client
from cmem_plugin_base.dataintegration.entity import Entities
from cmem_plugin_base.testing import TestExecutionContext
from rdflib import DCTERMS, OWL, RDF, RDFS, BNode, Graph, Literal, URIRef
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_validate import VALIDATE_REASONERS, ValidatePlugin
from cmem_plugin_reason.utils import (
    MAX_RAM_PERCENTAGE_DEFAULT,
    REASONER_COMMIT,
    REASONER_VERSION,
    get_reasoner_version,
)
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
def test_validate(setup: None, reasoner_parameter: str) -> None:
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


def test_validate_output_graph(setup: None, client: Client) -> None:
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


def test_validate_provenance(setup: None, client: Client) -> None:
    """Test Validate writes provenance without needing the project graph"""
    ValidatePlugin(
        ontology_graph_iri=VALIDATE_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=VALIDATE_OUTPUT_GRAPH_IRI,
        reasoner="hermit",
        mode="inconsistency",
    ).execute(inputs=(), context=TestExecutionContext())

    result = get_remote_graph(client, VALIDATE_OUTPUT_GRAPH_IRI, provenance=True)
    tasks = list(result.objects(URIRef(VALIDATE_OUTPUT_GRAPH_IRI), DCTERMS.creator))
    assert len(tasks) == 1
    task = tasks[0]
    # a snapshot of the task, not the task itself
    assert str(task).startswith("http://dataintegration.eccenca.com/TestProject/TestTask_")
    assert str(task) != "http://dataintegration.eccenca.com/TestProject/TestTask"
    functions = "https://vocab.eccenca.com/di/functions/"
    assert (
        task,
        RDF.type,
        URIRef(f"{functions}Plugin_cmem_plugin_reason-plugin_validate-ValidatePlugin"),
    ) in result
    assert (task, RDFS.label, Literal("Validate OWL consistency plugin")) in result
    assert (task, OWL.versionInfo, Literal(version("cmem-plugin-reason"))) in result
    # the build of the bundled reasoner jar (needs a jar with --version)
    reasoner_version = get_reasoner_version(MAX_RAM_PERCENTAGE_DEFAULT)
    assert reasoner_version is not None
    assert (task, URIRef(REASONER_VERSION), Literal(reasoner_version[0])) in result
    assert (task, URIRef(REASONER_COMMIT), Literal(reasoner_version[1])) in result
    assert (
        task,
        URIRef(f"{functions}param_cmem_plugin_reason-plugin_validate-ValidatePlugin_reasoner"),
        Literal("hermit"),
    ) in result


def test_validate_input_not_exist(setup: None) -> None:
    """Test Validate with non-existing input graph"""
    plugin = ValidatePlugin(
        ontology_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist/",
        reasoner="jfact",
        validate_profile=False,
        mode="inconsistency",
    )
    with pytest.raises(
        ValueError,
        match=f"Ontology graph does not exist: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_validate_invalid_parameters() -> None:
    """Test Validate parameter validation at execution, not at creation"""
    plugin = ValidatePlugin(
        ontology_graph_iri="not an IRI",
        reasoner="not-a-reasoner",
        mode="not-a-mode",
        max_explanations=0,
        output_graph_iri="also not an IRI",
        max_ram_percentage=0,
    )
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        plugin.execute(inputs=(), context=TestExecutionContext())
    message = str(exc_info.value)
    for error in (
        'Invalid IRI for parameter "Ontology graph IRI".',
        'Invalid value for parameter "Reasoner".',
        'Invalid value for parameter "Mode".',
        'Invalid value for parameter "Maximum explanations".',
        'Invalid IRI for parameter "Output graph IRI".',
        'Invalid value for parameter "Maximum RAM Percentage".',
    ):
        assert error in message


def test_validate_missing_parameters() -> None:
    """Test Validate can be created without parameters and reports the missing ones at execution"""
    plugin = ValidatePlugin()
    with pytest.raises(ValueError, match=r'Parameter "Ontology graph IRI" must be specified\.'):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_validate_import_not_exist_not_ignore(setup: None) -> None:
    """Test Validate with missing import"""
    plugin = ValidatePlugin(
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        reasoner="jfact",
        validate_profile=False,
        mode="inconsistency",
        ignore_missing_imports=False,
    )
    with pytest.raises(
        ImportError,
        match=f"Missing graph imports: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_validate_import_not_exist_ignore(setup: None) -> None:
    """Test Validate ignoring missing import"""
    ValidatePlugin(
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        reasoner="jfact",
        validate_profile=False,
        mode="inconsistency",
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())


# --- skolemize ------------------------------------------------------------------------------

VALIDATE_SKOLEM_ONTOLOGY_IRI = f"https://ns.eccenca.com/validateontology/{UID}/skolem/"
SKOLEM_NS = f"https://ns.eccenca.com/validateontology/{UID}/skolem/vocab#"
#: skolem_base() of VALIDATE_OUTPUT_GRAPH_IRI
SKOLEM_BASE = "https://ns.eccenca.com/.well-known/genid/"


@pytest.fixture
def skolem_setup(client: Client) -> Generator[None, Any]:
    """Set up the skolemize tests"""
    client.graphs.delete_item(VALIDATE_OUTPUT_GRAPH_IRI, skip_if_missing=True)
    # x is in A ⊑ ∃p.B and in D ≡ ∀p.C with B and C disjoint: inconsistent, and the
    # explanation contains both restrictions, which RDF writes as blank nodes.
    import_graph(
        client,
        VALIDATE_SKOLEM_ONTOLOGY_IRI,
        get_bytes_io(f"{FIXTURE_DIR}/test_validate_skolem.ttl"),
    )

    yield

    client.graphs.fetch_data()
    client.graphs.delete_item(VALIDATE_SKOLEM_ONTOLOGY_IRI, skip_if_missing=True)
    client.graphs.delete_item(VALIDATE_OUTPUT_GRAPH_IRI, skip_if_missing=True)


def validate_skolem(skolemize: bool) -> Graph:
    """Explain the inconsistency of the skolem ontology, return the output graph"""
    ValidatePlugin(
        ontology_graph_iri=VALIDATE_SKOLEM_ONTOLOGY_IRI,
        output_graph_iri=VALIDATE_OUTPUT_GRAPH_IRI,
        reasoner="hermit",
        mode="inconsistency",
        skolemize=skolemize,
    ).execute(inputs=(), context=TestExecutionContext())
    return get_remote_graph(get_client(), VALIDATE_OUTPUT_GRAPH_IRI)


def restriction_nodes(output: Graph) -> set:
    """Get the nodes standing for the two restrictions of the explanation"""
    return set(output.subjects(OWL.onProperty, URIRef(f"{SKOLEM_NS}p")))


def test_validate_without_skolemize_keeps_blank_nodes(skolem_setup: None) -> None:
    """Test Validate writes blank nodes by default"""
    nodes = restriction_nodes(validate_skolem(skolemize=False))
    assert len(nodes) == 2  # noqa: PLR2004
    assert all(isinstance(node, BNode) for node in nodes)


def test_validate_skolemize(skolem_setup: None) -> None:
    """Test Validate replaces blank nodes in the output graph with stable IRIs"""
    output = validate_skolem(skolemize=True)

    assert not any(isinstance(term, BNode) for triple in output for term in triple)
    nodes = restriction_nodes(output)
    assert len(nodes) == 2  # noqa: PLR2004
    assert all(str(node).startswith(SKOLEM_BASE) for node in nodes)

    # re-running replaces the output graph with the same IRIs
    assert restriction_nodes(validate_skolem(skolemize=True)) == nodes


# --- unsatisfiability mode ------------------------------------------------------------------

UNSAT_NS = f"https://ns.eccenca.com/validateontology/{UID}/unsat/vocab#"
UNSAT_ONTOLOGY_IRI = f"https://ns.eccenca.com/validateontology/{UID}/unsat/"
SATISFIABLE_ONTOLOGY_IRI = f"https://ns.eccenca.com/validateontology/{UID}/satisfiable/"
INCONSISTENT_ONTOLOGY_IRI = f"https://ns.eccenca.com/validateontology/{UID}/inconsistent/"
#: graph IRI -> fixture file:
#: - unsat: C is a subclass of the disjoint classes A and B, so C is unsatisfiable; the ontology
#:   itself is consistent, since C has no instances
#: - satisfiable: a plain class hierarchy, consistent and every class satisfiable
#: - inconsistent: x is an instance of the disjoint classes A and B
UNSAT_GRAPHS = {
    UNSAT_ONTOLOGY_IRI: "test_validate_unsat.ttl",
    SATISFIABLE_ONTOLOGY_IRI: "test_validate_satisfiable.ttl",
    INCONSISTENT_ONTOLOGY_IRI: "test_validate_inconsistent.ttl",
}


@pytest.fixture
def unsat_setup(client: Client) -> Generator[None, Any]:
    """Set up the unsatisfiability tests"""
    for iri, fixture in UNSAT_GRAPHS.items():
        import_graph(client, iri, get_bytes_io(f"{FIXTURE_DIR}/{fixture}"))

    yield

    client.graphs.fetch_data()
    for iri in UNSAT_GRAPHS:
        client.graphs.delete_item(iri, skip_if_missing=True)


def validate_unsatisfiability(ontology_graph_iri: str, reasoner: str = "hermit") -> dict:
    """Run Validate in unsatisfiability mode, return the output entity's path -> value map"""
    result = ValidatePlugin(
        ontology_graph_iri=ontology_graph_iri,
        reasoner=reasoner,
        mode="unsatisfiability",
    ).execute(inputs=(), context=TestExecutionContext())
    return get_value_dict(result)


@pytest.mark.parametrize("reasoner_parameter", VALIDATE_REASONERS)
def test_validate_unsatisfiability(unsat_setup: None, reasoner_parameter: str) -> None:
    """Test Validate explains an unsatisfiable class"""
    value_dict = validate_unsatisfiability(UNSAT_ONTOLOGY_IRI, reasoner_parameter)

    explanation = value_dict["explanation"]
    assert not explanation.startswith("No explanations found."), explanation
    # the explained entailment is C SubClassOf owl:Nothing, justified by the three axioms
    assert f"[C]({UNSAT_NS}C) SubClassOf [Nothing]" in explanation, explanation
    for axiom in (
        f"[C]({UNSAT_NS}C) SubClassOf [A]({UNSAT_NS}A)",
        f"[C]({UNSAT_NS}C) SubClassOf [B]({UNSAT_NS}B)",
        f"[A]({UNSAT_NS}A) DisjointWith [B]({UNSAT_NS}B)",
    ):
        assert axiom in explanation, explanation
    assert value_dict["reasoner"] == reasoner_parameter


def test_validate_unsatisfiability_nothing_found(unsat_setup: None) -> None:
    """Test Validate in unsatisfiability mode on an ontology without unsatisfiable classes"""
    value_dict = validate_unsatisfiability(SATISFIABLE_ONTOLOGY_IRI)
    assert value_dict["explanation"].startswith("No explanations found.")


def test_validate_unsatisfiability_inconsistent(unsat_setup: None) -> None:
    """Test Validate in unsatisfiability mode fails on an inconsistent ontology"""
    # In an inconsistent ontology every class is unsatisfiable; the reasoner refuses and
    # points to inconsistency mode instead. (Older reasoner jars crashed here, after logging
    # "Consider '-M inconsistency'", so match the new message exactly.)
    with pytest.raises(OSError, match="Use '-M inconsistency' to explain the inconsistency"):
        validate_unsatisfiability(INCONSISTENT_ONTOLOGY_IRI)

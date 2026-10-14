"""Plugin tests."""

import os
import tempfile
from collections.abc import Generator
from importlib.metadata import version
from typing import Any

import pytest
from cmem_client.client import Client
from cmem_plugin_base.dataintegration.description import Plugin
from cmem_plugin_base.testing import TestExecutionContext
from rdflib import DCTERMS, OWL, RDF, RDFS, BNode, Graph, Literal, Node, URIRef
from rdflib.compare import isomorphic

from cmem_plugin_reason.plugin_reason import REASON_REASONERS, ReasonPlugin
from cmem_plugin_reason.utils import (
    MAX_RAM_PERCENTAGE_DEFAULT,
    REASONER_COMMIT,
    REASONER_VERSION,
    get_reasoner_version,
    is_release_version,
)
from tests.utils import (
    FIXTURE_DIR,
    REGISTRY_STATES,
    UID,
    get_bytes_io,
    get_client,
    get_remote_graph,
    import_graph,
    replace_uuid,
    simulate_dataintegration_discovery,
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
def client() -> Client:
    """CMEM client fixture"""
    return get_client()


@pytest.fixture
def setup(client: Client) -> Generator[None, Any]:
    """Set up Reason test"""
    client.graphs.delete_item(REASON_RESULT_GRAPH_IRI, skip_if_missing=True)

    import_graph(client, REASON_DATA_GRAPH_IRI, get_bytes_io(f"{FIXTURE_DIR}/test_reason_data.ttl"))
    import_graph(
        client, REASON_DATA_GRAPH_IRI_2, get_bytes_io(f"{FIXTURE_DIR}/test_reason_data_2.ttl")
    )
    import_graph(
        client,
        REASON_ONTOLOGY_GRAPH_IRI_1,
        get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_1.ttl"),
    )
    import_graph(
        client,
        REASON_ONTOLOGY_GRAPH_IRI_2,
        get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_2.ttl"),
    )
    import_graph(
        client,
        REASON_ONTOLOGY_GRAPH_IRI_3,
        get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_3.ttl"),
    )
    import_graph(
        client,
        ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        get_bytes_io(f"{FIXTURE_DIR}/test_reason_ontology_4.ttl"),
    )

    yield

    # the plugin under test creates/updates graphs via its own Client instance, so this
    # client's cached graph list needs refreshing before delete_item(skip_if_missing=True)
    # can correctly see them (otherwise it silently no-ops on a stale cache)
    client.graphs.fetch_data()
    client.graphs.delete_item(REASON_DATA_GRAPH_IRI, skip_if_missing=True)
    client.graphs.delete_item(REASON_DATA_GRAPH_IRI_2, skip_if_missing=True)
    client.graphs.delete_item(REASON_ONTOLOGY_GRAPH_IRI_1, skip_if_missing=True)
    client.graphs.delete_item(REASON_ONTOLOGY_GRAPH_IRI_2, skip_if_missing=True)
    client.graphs.delete_item(REASON_ONTOLOGY_GRAPH_IRI_3, skip_if_missing=True)
    client.graphs.delete_item(ONTOLOGY_GRAPH_IMPORT_FAIL_IRI, skip_if_missing=True)
    client.graphs.delete_item(REASON_RESULT_GRAPH_IRI, skip_if_missing=True)


@pytest.mark.parametrize("reasoner_parameter", REASON_REASONERS)
def test_reason(setup: None, client: Client, reasoner_parameter: str) -> None:
    """Test reasoning"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner=reasoner_parameter,
        sub_class=False,
        class_assertion=True,
        # ELK doesn't support property assertions
        property_assertion=reasoner_parameter not in ("elk", "elk_emr"),
    ).execute(inputs=(), context=TestExecutionContext())

    result = get_remote_graph(client, REASON_RESULT_GRAPH_IRI)
    test = Graph().parse(
        data=replace_uuid(f"{FIXTURE_DIR}/test_{reasoner_parameter}.ttl"), format="turtle"
    )

    assert isomorphic(result, test)


@REGISTRY_STATES
def test_reason_provenance(
    setup: None, client: Client, monkeypatch: pytest.MonkeyPatch, after_discovery: bool
) -> None:
    """Test Reason writes provenance without needing the project graph or the plugin registry"""
    if after_discovery:
        simulate_dataintegration_discovery(monkeypatch)
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="structural",
    ).execute(inputs=(), context=TestExecutionContext())

    result = get_remote_graph(client, REASON_RESULT_GRAPH_IRI, provenance=True)
    tasks = list(result.objects(URIRef(REASON_RESULT_GRAPH_IRI), DCTERMS.creator))
    assert len(tasks) == 1
    task = tasks[0]
    # a snapshot of the task, not the task itself
    assert str(task).startswith("http://dataintegration.eccenca.com/TestProject/TestTask_")
    assert str(task) != "http://dataintegration.eccenca.com/TestProject/TestTask"
    functions = "https://vocab.eccenca.com/di/functions/"
    assert (
        task,
        RDF.type,
        URIRef(f"{functions}Plugin_cmem_plugin_reason-plugin_reason-ReasonPlugin"),
    ) in result
    assert (task, RDFS.label, Literal("Reason plugin")) in result
    assert (task, OWL.versionInfo, Literal(version("cmem-plugin-reason"))) in result
    # the build of the bundled reasoner jar (needs a jar with --version)
    reasoner_version = get_reasoner_version(MAX_RAM_PERCENTAGE_DEFAULT)
    assert reasoner_version is not None
    assert (task, URIRef(REASONER_VERSION), Literal(reasoner_version[0])) in result
    # the commit only for versions that aren't releases
    assert ((task, URIRef(REASONER_COMMIT), Literal(reasoner_version[1])) in result) != (
        is_release_version(reasoner_version[0])
    )
    assert (
        task,
        URIRef(f"{functions}param_cmem_plugin_reason-plugin_reason-ReasonPlugin_reasoner"),
        Literal("structural"),
    ) in result


def test_reason_input_not_exist(setup: None) -> None:
    """Test Reason with non-existing input graph"""
    plugin = ReasonPlugin(
        data_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist1/",
        ontology_graph_iri=f"https://ns.eccenca.com/reasoning/{UID}/not-exist2/",
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="structural",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
    )
    with pytest.raises(
        ValueError,
        match="Graphs do not exist: "
        f"https://ns.eccenca.com/reasoning/{UID}/not-exist1/, "
        f"https://ns.eccenca.com/reasoning/{UID}/not-exist2/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_reason_invalid_parameters() -> None:
    """Test Reason parameter validation at execution, not at creation"""
    plugin = ReasonPlugin(
        output_graph_iri="not an IRI",
        reasoner="not-a-reasoner",
        class_assertion=False,
        property_assertion=False,
        max_ram_percentage=0,
    )
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        plugin.execute(inputs=(), context=TestExecutionContext())
    message = str(exc_info.value)
    for error in (
        "At least one of data graph IRI and ontology graph IRI must be specified.",
        'Invalid IRI for parameter "Output graph IRI".',
        'Invalid value for parameter "Reasoner".',
        "No axiom generator selected.",
        'Invalid value for parameter "Maximum RAM Percentage".',
    ):
        assert error in message


@pytest.mark.parametrize("reasoner", ["elk", "elk_emr"])
def test_reason_generators_elk_does_not_support(
    reasoner: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Reason rejects axiom generators ELK doesn't support, naming them

    The labels must not come from Plugin.plugins: at execution time, DataIntegration's plugin
    discovery may have emptied it.
    """
    monkeypatch.setattr(Plugin, "plugins", [])
    plugin = ReasonPlugin(
        data_graph_iri="https://example.org/data/",
        output_graph_iri="https://example.org/result/",
        reasoner=reasoner,
        class_assertion=True,
        property_assertion=True,
        disjoint_classes=True,
    )
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        plugin.execute(inputs=(), context=TestExecutionContext())
    message = str(exc_info.value)
    assert "does not support these axiom generators:" in message
    assert "Individual property assertions" in message
    assert "Class disjointness (owl:disjointWith)" in message
    assert "Individual class assertions" not in message


def test_reason_generators_hermit_supports() -> None:
    """Test Reason accepts with HermiT the axiom generators ELK doesn't support"""
    plugin = ReasonPlugin(
        data_graph_iri="https://example.org/data/",
        output_graph_iri="https://example.org/result/",
        reasoner="hermit",
        property_assertion=True,
        disjoint_classes=True,
    )
    plugin.validate_parameters()


def test_reason_missing_parameters() -> None:
    """Test Reason can be created without parameters and reports the missing ones at execution"""
    plugin = ReasonPlugin()
    with pytest.raises(ValueError) as exc_info:  # noqa: PT011
        plugin.execute(inputs=(), context=TestExecutionContext())
    message = str(exc_info.value)
    for error in (
        "At least one of data graph IRI and ontology graph IRI must be specified.",
        'Parameter "Output graph IRI" must be specified.',
    ):
        assert error in message
    assert "cannot be the same" not in message


def use_real_temp_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give the plugin a temporary directory whose path contains no symbolic link

    On macOS the default one is under /var, a link to /private/var. A reasoner then sees the input
    file and the same file resolved through the catalog under two different paths, which hides
    a document being loaded twice - on Linux (/tmp) it can fail.
    """
    monkeypatch.setattr(tempfile, "tempdir", os.path.realpath(tempfile.gettempdir()))


def reason_and_fetch(client: Client, data_graph_iri: str, ontology_graph_iri: str) -> Graph:
    """Run Reason into the result graph and fetch it"""
    ReasonPlugin(
        data_graph_iri=data_graph_iri,
        ontology_graph_iri=ontology_graph_iri,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="hermit",
        sub_class=True,
    ).execute(inputs=(), context=TestExecutionContext())
    return get_remote_graph(client, REASON_RESULT_GRAPH_IRI)


@pytest.mark.parametrize(
    ("data_graph_iri", "ontology_graph_iri"),
    [
        (REASON_DATA_GRAPH_IRI, ""),
        ("", REASON_ONTOLOGY_GRAPH_IRI_1),
        (REASON_ONTOLOGY_GRAPH_IRI_1, REASON_ONTOLOGY_GRAPH_IRI_1),
    ],
    ids=["data graph only", "ontology graph only", "same graph in both"],
)
def test_reason_single_input(
    setup: None,
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    data_graph_iri: str,
    ontology_graph_iri: str,
) -> None:
    """Test Reason with one input graph, whichever field it is in"""
    use_real_temp_path(monkeypatch)
    graph = data_graph_iri or ontology_graph_iri
    result = reason_and_fetch(client, data_graph_iri, ontology_graph_iri)

    output = URIRef(REASON_RESULT_GRAPH_IRI)
    comment = f"Reasoning results of graph <{graph}>"
    assert (output, RDFS.comment, Literal(comment, lang="en")) in result
    assert list(result.objects(output, DCTERMS.source)) == [URIRef(graph)]
    # the input graph's own imports are kept, but it does not import itself
    assert (output, OWL.imports, URIRef(graph)) not in result


def test_reason_same_graph_for_data_and_ontology(
    setup: None, client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test Reason with the same graph in both fields reasons over that graph alone"""
    use_real_temp_path(monkeypatch)
    same = reason_and_fetch(client, REASON_ONTOLOGY_GRAPH_IRI_1, REASON_ONTOLOGY_GRAPH_IRI_1)
    ontology_only = reason_and_fetch(client, "", REASON_ONTOLOGY_GRAPH_IRI_1)

    assert isomorphic(same, ontology_only)
    assert (None, RDFS.subClassOf, None) in same


def test_reason_import_not_exist_not_ignore(setup: None) -> None:
    """Test Reason with missing import"""
    plugin = ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="structural",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        ignore_missing_imports=False,
    )
    with pytest.raises(
        ImportError,
        match=f"Missing graph imports: https://ns.eccenca.com/reasoning/{UID}/not-exist/",
    ):
        plugin.execute(inputs=(), context=TestExecutionContext())


def test_reason_import_not_exist_ignore(setup: None) -> None:
    """Test Reason ignoring missing import"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=ONTOLOGY_GRAPH_IMPORT_FAIL_IRI,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="structural",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())


def test_reason_ontology_import(setup: None, client: Client) -> None:
    """Test Reason no ontology import"""
    ReasonPlugin(
        data_graph_iri=REASON_DATA_GRAPH_IRI,
        ontology_graph_iri=REASON_ONTOLOGY_GRAPH_IRI_1,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="structural",
        sub_class=False,
        class_assertion=True,
        property_assertion=False,
        ignore_missing_imports=True,
    ).execute(inputs=(), context=TestExecutionContext())

    assert not client.store.sparql.query(ASK_QUERY).askAnswer


# --- skolemize ------------------------------------------------------------------------------

REASON_SKOLEM_ONTOLOGY_IRI = f"https://ns.eccenca.com/reasoning/{UID}/skolem/"
SKOLEM_NS = f"https://ns.eccenca.com/reasoning/{UID}/skolem/vocab#"
#: skolem_base() of REASON_RESULT_GRAPH_IRI
SKOLEM_BASE = "https://ns.eccenca.com/.well-known/genid/"


@pytest.fixture
def skolem_setup(client: Client) -> Generator[None, Any]:
    """Set up the skolemize tests"""
    client.graphs.delete_item(REASON_RESULT_GRAPH_IRI, skip_if_missing=True)
    # hasStudent ⊑ studentOf⁻ is inferred; RDF writes the inverse property with a blank node.
    import_graph(
        client,
        REASON_SKOLEM_ONTOLOGY_IRI,
        get_bytes_io(f"{FIXTURE_DIR}/test_reason_skolem.ttl"),
    )

    yield

    client.graphs.fetch_data()
    client.graphs.delete_item(REASON_SKOLEM_ONTOLOGY_IRI, skip_if_missing=True)
    client.graphs.delete_item(REASON_RESULT_GRAPH_IRI, skip_if_missing=True)


def reason_skolem(skolemize: bool) -> None:
    """Infer the sub-property axioms of the skolem ontology into REASON_RESULT_GRAPH_IRI"""
    ReasonPlugin(
        ontology_graph_iri=REASON_SKOLEM_ONTOLOGY_IRI,
        output_graph_iri=REASON_RESULT_GRAPH_IRI,
        reasoner="hermit",
        sub_object_property=True,
        class_assertion=False,
        property_assertion=False,
        skolemize=skolemize,
    ).execute(inputs=(), context=TestExecutionContext())


def inverse_node(result: Graph) -> Node:
    """Get the node standing for studentOf⁻ in hasStudent rdfs:subPropertyOf studentOf⁻"""
    nodes = [
        node
        for node in result.objects(URIRef(f"{SKOLEM_NS}hasStudent"), RDFS.subPropertyOf)
        if (node, OWL.inverseOf, URIRef(f"{SKOLEM_NS}studentOf")) in result
    ]
    assert len(nodes) == 1, result.serialize(format="nt")
    return nodes[0]


def test_reason_without_skolemize_keeps_blank_nodes(skolem_setup: None, client: Client) -> None:
    """Test Reason writes blank nodes by default"""
    reason_skolem(skolemize=False)

    result = get_remote_graph(client, REASON_RESULT_GRAPH_IRI)
    assert isinstance(inverse_node(result), BNode)


def test_reason_skolemize(skolem_setup: None, client: Client) -> None:
    """Test Reason replaces blank nodes with stable IRIs"""
    reason_skolem(skolemize=True)
    result = get_remote_graph(client, REASON_RESULT_GRAPH_IRI)

    assert not any(isinstance(term, BNode) for triple in result for term in triple)
    node = inverse_node(result)
    assert str(node).startswith(SKOLEM_BASE)

    # re-running replaces the output graph with the same IRIs
    reason_skolem(skolemize=True)
    assert inverse_node(get_remote_graph(client, REASON_RESULT_GRAPH_IRI)) == node

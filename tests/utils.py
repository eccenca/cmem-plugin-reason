"""Common test functions"""

import tempfile
from io import BytesIO
from pathlib import Path

import pytest
from cmem_client.client import Client
from cmem_client.repositories.protocols.import_item import ImportConflictPolicy
from cmem_plugin_base.dataintegration.description import Plugin
from rdflib import DCTERMS, OWL, RDF, Graph, URIRef

UID = "e02aaed014c94e0c91bf960fed127750"

FIXTURE_DIR = Path(__file__).parent / "fixture_dir"


def get_client() -> Client:
    """Get a cmem-client Client configured from the test environment"""
    return Client.from_env()


def get_remote_graph(client: Client, iri: str, provenance: bool = False) -> Graph:
    """Get remote graph IRI, without the provenance data unless requested"""
    # the plugin under test uses its own Client instance internally, so this client's
    # cached graph list may not know about graphs created/updated since it was built
    client.graphs.fetch_data()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "graph.ttl"
        client.graphs.export_item(key=iri, path=path, replace=True)
        graph = Graph().parse(path, format="turtle")
    graph.remove((URIRef(iri), DCTERMS.created, None))
    graph.remove((None, RDF.type, OWL.AnnotationProperty))
    if not provenance:
        for task in list(graph.objects(URIRef(iri), DCTERMS.creator)):
            graph.remove((task, None, None))
        graph.remove((URIRef(iri), DCTERMS.creator, None))
    return graph


#: Parametrizes a test over the plugin registry as pytest leaves it and as DataIntegration does
REGISTRY_STATES = pytest.mark.parametrize(
    "after_discovery", [False, True], ids=["plugin registered", "after DataIntegration discovery"]
)


def simulate_dataintegration_discovery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leave Plugin.plugins as DataIntegration's plugin discovery does at execution time

    DataIntegration discovers every installed cmem_plugin_* package, and the import of each one
    starts with emptying Plugin.plugins. So when a task runs, the list holds only the plugins of
    the last package discovered - normally not this one. Within pytest only this package is
    imported, so the plugins stay registered unless a test empties the list.
    """
    monkeypatch.setattr(Plugin, "plugins", [])


def import_graph(client: Client, iri: str, file: BytesIO) -> None:
    """Import graph to CMEM"""
    with tempfile.NamedTemporaryFile(suffix=".ttl", delete=False) as tmp:
        tmp.write(file.read())
        tmp_path = Path(tmp.name)
    try:
        client.graphs.import_item(path=tmp_path, key=iri, on_conflict=ImportConflictPolicy.REPLACE)
    finally:
        tmp_path.unlink(missing_ok=True)


def replace_uuid(filepath: str) -> str:
    """Replace {uuid} in input files"""
    return Path(filepath).read_text().replace("{uuid}", UID)


def get_bytes_io(filepath: str) -> BytesIO:
    """Get BytesIO object from filepath"""
    return BytesIO(replace_uuid(filepath).encode(encoding="utf-8"))
